# rea-puppet-rebuild

Agent skill：制作或逐帧复刻「暗金 / 皮影」风格的历史短片。负责生成人物与关节动画、分镜与连续性、音乐卡点、字幕与画面同步、屏幕特效、打斗拟音、Canvas 渲染与 MP4 验收。适用于韩信封样片同款、历史人物叙事、纸偶动画和参考视频拆解。

## 结构

```
rea-puppet-rebuild/
├─ SKILL.md                        触发条件与五步流程
├─ references/
│  ├─ timeline.md                  分镜、节拍与字幕
│  ├─ generated-puppets.md         皮影视觉与生图人物
│  ├─ puppet-prompts.md            人物提示词
│  ├─ screen-and-render.md         动画、屏幕效果与验收
│  ├─ audio.md                     打斗拟音与混音
│  ├─ han-xin-opening.md           韩信封样片十秒实测
│  └─ reverse-analysis.md          逐帧逆向
└─ scripts/
   ├─ foley_mix.py                 拟音合成与混音
   └─ frame_scan.py                逐帧扫描
```

## 安装

把整个目录复制到 agent 的 skills 根目录：

```powershell
# Claude / DeepSeek Harness
Copy-Item -Recurse rea-puppet-rebuild "$env:USERPROFILE\.agents\skills\"

# Codex
Copy-Item -Recurse rea-puppet-rebuild "$env:USERPROFILE\.codex\skills\"
```

技能会以 `<root>/<name>/SKILL.md` 的形式被自动发现。

## 使用

触发词：做皮影短片 / 暗金风格历史片 / 复刻某条参考视频 / 纸偶动画 / 逐帧拆解。
未指定规格时默认横屏 1920×1080、30 fps 出样。
