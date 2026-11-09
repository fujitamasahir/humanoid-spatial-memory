#!/bin/bash
set -euo pipefail

BASE="results/phase2_mujoco"
LEFT="$BASE/g1_pedestrian_capsule_replay_M80030007_periodic_s1_v6/portfolio_export/portfolio_demo.gif"
RIGHT="$BASE/g1_pedestrian_capsule_replay_M80030007_periodic_s1_v7/portfolio_export/portfolio_demo.gif"
OUT="$BASE/g1_pedestrian_capsule_replay_M80030007_periodic_s1_v7/portfolio_export/portfolio_demo_side_by_side.gif"

# Create a temporary transparent image for the titles.
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

python - "$TMP_DIR/titles.png" <<'PY'
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import sys

# Each video panel: 800 x 450.
W, H = 1600, 450

im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(im)

font_paths = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

font_path = next(
    (p for p in font_paths if Path(p).exists()), None
)
if font_path is None:
    raise RuntimeError("No suitable macOS font found")

font = ImageFont.truetype(font_path, 30)

titles = [
    (400, "Before Lateral Avoidance Fix"),
    (1200, "After Lateral Avoidance Fix"),
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

# Combine both GIFs and overlay the titles.
ffmpeg -hide_banner \
  -ignore_loop 1 -i "$LEFT" \
  -ignore_loop 1 -i "$RIGHT" \
  -loop 1 -framerate 24 -i "$TMP_DIR/titles.png" \
  -filter_complex "\
[0:v]fps=24,scale=800:450:flags=lanczos,setsar=1,setpts=PTS-STARTPTS[left]; \
[1:v]fps=24,scale=800:450:flags=lanczos,setsar=1,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=60[right]; \
[left][right]hstack=inputs=2:shortest=1[stack]; \
[stack][2:v]overlay=0:0:shortest=1:format=auto,format=rgb24,split[a][b]; \
[b]palettegen=stats_mode=full:max_colors=256[pal]; \
[a][pal]paletteuse=dither=sierra2_4a[out]" \
  -map "[out]" -loop 0 -y "$OUT"

echo "Created: $OUT"
