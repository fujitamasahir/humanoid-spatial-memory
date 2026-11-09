#!/bin/bash
set -euo pipefail

BASE="results/phase2_mujoco"
LEFT="$BASE/g1_pedestrian_capsule_replay_R80000001_static_s1_v7/portfolio_export/portfolio_demo.gif"
RIGHT="$BASE/g1_pedestrian_capsule_replay_R80000001_static_s1_v8/portfolio_export/portfolio_demo.gif"
OUT="$BASE/g1_pedestrian_capsule_replay_R80000001_static_s1_v8/portfolio_export/portfolio_demo_side_by_side.gif"

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

python - "$TMP_DIR/titles.png" <<'PY'
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import sys

W, H = 1600, 450
im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(im)

font_paths = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
font_path = next((p for p in font_paths if Path(p).exists()), None)
if font_path is None:
    raise RuntimeError("No suitable macOS font found")

font = ImageFont.truetype(font_path, 29)

titles = [
    (400, "Before Emergency Safety Sensor"),
    (1200, "After Emergency Safety Sensor"),
]

for center_x, title in titles:
    bbox = draw.textbbox((0, 0), title, font=font)
    text_w = bbox[2] - bbox[0]

    draw.text(
        (center_x - text_w / 2, 16),
        title,
        font=font,
        fill="black",
        stroke_width=4,
        stroke_fill="white",
    )

im.save(sys.argv[1])
PY

ffmpeg -hide_banner \
  -ignore_loop 1 -i "$LEFT" \
  -ignore_loop 1 -i "$RIGHT" \
  -loop 1 -framerate 24 -i "$TMP_DIR/titles.png" \
  -filter_complex "\
[0:v]fps=24,scale=800:450:flags=lanczos,setsar=1,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=60[left]; \
[1:v]fps=24,scale=800:450:flags=lanczos,setsar=1,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=60[right]; \
[left][right]hstack=inputs=2:shortest=1[stack]; \
[stack][2:v]overlay=0:0:shortest=1:format=auto,format=rgb24,split[a][b]; \
[b]palettegen=stats_mode=full:max_colors=256[pal]; \
[a][pal]paletteuse=dither=sierra2_4a[out]" \
  -map "[out]" \
  -loop 0 \
  -y "$OUT"

echo "Created: $OUT"
