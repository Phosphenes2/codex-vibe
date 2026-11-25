"""Render frame-timed theatrical foley and optionally mix it with a music stem."""

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import wave

import numpy as np


RATE = 48000
LENGTHS = {
    'cloth': .24, 'whoosh': .24, 'metal': .36, 'wood': .17,
    'ceramic': .23, 'step': .18, 'impact': .32, 'stamp': .16,
}


def synthesize(cue, rng):
    count = round(LENGTHS[cue] * RATE)
    t = np.arange(count) / RATE
    phase = np.linspace(0, 1, count)
    noise = rng.standard_normal(count)
    edge = np.diff(noise, prepend=0) * .45
    grain = np.convolve(noise, np.ones(15) / 15, mode='same')

    def ring(hz, rate):
        return np.sin(2 * np.pi * hz * t) * np.exp(-rate * t)

    if cue == 'whoosh':
        signal = (.85 * grain + .06 * edge) * np.sin(np.pi * phase) ** 2
    elif cue == 'cloth':
        flutter = .55 + .45 * np.sin(2 * np.pi * 31 * t + .6) ** 2
        signal = (.8 * grain + .11 * edge) * np.sin(np.pi * phase) ** 2 * flutter
    elif cue == 'metal':
        signal = .43 * ring(1680, 18) + .25 * ring(2631, 24) + .16 * ring(4033, 35)
        signal += .25 * edge * np.exp(-185 * t)
    elif cue == 'ceramic':
        signal = .45 * ring(1130, 31) + .31 * ring(1927, 41) + .16 * ring(2723, 49)
        signal += .09 * edge * np.exp(-170 * t)
    elif cue == 'wood':
        signal = .68 * ring(181, 34) + .26 * ring(371, 55) + .38 * grain * np.exp(-75 * t)
    elif cue == 'step':
        signal = .66 * ring(74, 31) + .24 * ring(129, 38) + .33 * grain * np.exp(-32 * t)
    elif cue == 'stamp':
        signal = .63 * ring(119, 33) + .33 * grain * np.exp(-48 * t)
        signal += .13 * edge * np.exp(-95 * t)
    else:
        signal = .81 * ring(52, 13) + .29 * ring(107, 29) + .42 * grain * np.exp(-39 * t)

    # Smooth the edges of the event without moving its trigger time.
    signal *= np.minimum(1, t * 1800) * np.minimum(1, (1 - phase) * 12)
    return signal / np.max(np.abs(signal))


def gain(db):
    return 10.0 ** (db / 20.0)


def render_events(spec):
    fps = Fraction(str(spec['fps']))
    frames = spec['frames']
    if fps <= 0 or type(frames) is not int or frames <= 0:
        raise ValueError('fps and integer frames must be positive')
    count = round(frames * RATE / fps)
    if count < 1:
        raise ValueError('timeline is shorter than one audio sample')
    rng = np.random.default_rng(spec.get('seed', 0))
    foley = np.zeros((count, 2), dtype=np.float64)
    for index, event in enumerate(spec.get('events', []), 1):
        if ('frame' in event) == ('time' in event):
            raise ValueError(f'event {index} needs exactly one of frame and time')
        if 'frame' in event:
            frame = event['frame']
            if type(frame) is not int or not 0 <= frame < frames:
                raise ValueError(f'event {index} frame must be inside the timeline')
            offset = round(frame * RATE / fps)
        else:
            seconds = float(event['time'])
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError(f'event {index} time must be nonnegative')
            offset = round(seconds * RATE)
        cue = event['cue']
        pan = float(event.get('pan', 0))
        level = float(event.get('level_db', -20))
        if not 0 <= offset < count or not -1 <= pan <= 1 or not -100 <= level <= 0:
            raise ValueError(f'event {index} time, pan or level is outside its range')
        if cue not in LENGTHS:
            raise ValueError(f'event {index} has unknown cue {cue!r}')
        mono = synthesize(cue, rng)
        length = min(len(mono), count - offset)
        mono = mono[:length] * gain(level)
        if length < round(LENGTHS[cue] * RATE):
            fade = min(round(.01 * RATE), length)
            mono[-fade:] *= np.linspace(1, 0, fade, endpoint=True) if fade > 1 else 0
        angle = (pan + 1) * np.pi / 4
        foley[offset:offset + length] += mono[:, None] * [np.cos(angle), np.sin(angle)]
    return foley


def read_music(path, start, count):
    result = subprocess.run(
        ['ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(path), '-map', '0:a:0',
         '-t', f'{count / RATE:.9f}', '-ar', str(RATE), '-ac', '2',
         '-f', 'f32le', 'pipe:1'],
        check=True, capture_output=True,
    )
    music = np.frombuffer(result.stdout, dtype='<f4').reshape(-1, 2)
    if len(music) < count:
        raise ValueError(f'music is {count - len(music)} samples short of the timeline')
    return music[:count].astype(np.float64)


def fit_mix(music, foley, ceiling):
    if not np.isfinite(music).all() or not np.isfinite(foley).all():
        raise ValueError('audio contains a non-finite sample')
    if np.max(np.abs(music)) > ceiling:
        raise ValueError('music exceeds the ceiling by itself; set --music-gain-db explicitly')

    # Limit globally so repeated sounds keep their relative dynamics.
    factor = 1.0
    for sign in (1.0, -1.0):
        active = sign * foley > 0
        if np.any(active):
            allowed = (ceiling - sign * music[active]) / (sign * foley[active])
            factor = min(factor, float(np.min(allowed)))
    adjusted = foley * factor
    return adjusted, music + adjusted, factor


def write_wav(path, signal):
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.rint(np.clip(signal, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as handle:
        handle.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
        handle.writeframes(pcm.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cues', type=Path)
    parser.add_argument('--sfx-out', required=True, type=Path)
    parser.add_argument('--music', type=Path)
    parser.add_argument('--music-start', type=float, default=0)
    parser.add_argument('--music-gain-db', type=float, default=0)
    parser.add_argument('--mix-out', type=Path)
    parser.add_argument('--ceiling-dbfs', type=float, default=-1.5)
    args = parser.parse_args()

    if bool(args.music) != bool(args.mix_out):
        parser.error('--music and --mix-out must be provided together')
    paths = [p.resolve() for p in [args.cues, args.music, args.sfx_out, args.mix_out] if p]
    if len(paths) != len(set(paths)):
        parser.error('inputs and outputs need distinct paths')
    if (not math.isfinite(args.music_start) or args.music_start < 0
            or not -100 <= args.music_gain_db <= 24 or not -40 <= args.ceiling_dbfs <= 0):
        parser.error('music start, music gain or ceiling is outside its range')

    try:
        with args.cues.open(encoding='utf-8-sig') as source:
            foley = render_events(json.load(source))
        music = (read_music(args.music, args.music_start, len(foley)) * gain(args.music_gain_db)
                 if args.music else np.zeros_like(foley))
        foley, mixed, factor = fit_mix(music, foley, gain(args.ceiling_dbfs))
        write_wav(args.sfx_out, foley)
        if args.mix_out:
            write_wav(args.mix_out, mixed)
        print(f'{len(foley)} samples per channel at {RATE} Hz, foley gain multiplier {factor:.4f}')
        print(f'{"mix" if args.mix_out else "foley"} sample peak {np.max(np.abs(mixed)):.6f}')
    except subprocess.CalledProcessError as exc:
        parser.exit(1, exc.stderr.decode(errors='replace'))
    except (ValueError, KeyError, TypeError, OSError, ZeroDivisionError) as exc:
        parser.exit(1, f'{parser.prog}: {exc}\n')


if __name__ == '__main__':
    main()
