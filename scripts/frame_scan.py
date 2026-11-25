"""Write rea-video's per-frame observations and candidate shot boundaries."""
import argparse
import csv
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--rea-root', type=Path, help='Checkout containing the rea_video package')
    args = parser.parse_args()
    if args.rea_root:
        sys.path.insert(0, str(args.rea_root.resolve()))
    from rea_video.media import video_info
    from rea_video.shots import build_track, detect_shots

    info = video_info(args.video)
    track = build_track(str(args.video), info)
    if not track.n:
        parser.error('No decoded video frames')
    shots = detect_shots(track)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / 'frames.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['frame', 'seconds', 'luma_0_255', 'hist_distance', 'pixel_difference', 'changed_fraction'])
        for frame in range(track.n):
            seconds = track.times[frame] if track.times is not None else frame / track.fps
            observations = (seconds, track.luma[frame], track.hist_dist[frame],
                            track.pix_diff[frame], track.changed[frame])
            writer.writerow([frame, *(round(float(value), 6) for value in observations)])
    result = {'frame_count': track.n, 'fps': track.fps,
              'time_source': 'packet_pts' if track.times is not None else 'frame_index_over_fps',
              'candidate_shots': [shot.to_dict() for shot in shots]}
    (args.out / 'candidate-shots.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{track.n} frames, {len(shots)} candidate shots')


if __name__ == '__main__':
    main()

