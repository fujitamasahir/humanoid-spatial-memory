
#!/usr/bin/env python3
"""Create 8x-speed split-screen G1 replay videos and GIFs."""

from pathlib import Path
import json
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(
    "results/phase2_mujoco/g1_horizon800_residual_replays_v1"
)

SPEED = 8
OUTPUT_FPS = 12

CASES = {
    "A": {"stop": 460, "end": 800},
    "B": {"stop": 440, "end": 800},
    "C": {"stop": None, "end": 479},
}


def run(command):
    subprocess.run(command, check=True)


def probe_video(path):
    """Read actual source video timing."""
    result = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries",
            "stream=avg_frame_rate,nb_frames,duration",
            "-of", "json",
            str(path),
        ],
        text=True,
    )
    stream = json.loads(result)["streams"][0]
    numerator, denominator = map(
        int, stream["avg_frame_rate"].split("/")
    )
    fps = numerator / denominator

    if stream.get("nb_frames", "N/A") != "N/A":
        frames = int(stream["nb_frames"])
    else:
        frames = round(float(stream["duration"]) * fps)

    return fps, frames


def make_message_image(path, stop_step):
    """Create the English stop message using Pillow."""
    image = Image.new("RGBA", (1100, 115), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    font_path = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    )
    if Path(font_path).exists():
        font = ImageFont.truetype(font_path, 23)
    else:
        font = ImageFont.load_default()

    lines = [
        f"From step {stop_step}, the planner returned",
        "no_feasible_forward_route; G1 remained stationary through step 800.",
    ]

    draw.rounded_rectangle(
        (0, 0, 1099, 114),
        radius=14,
        fill=(25, 50, 71, 235),
    )

    for i, line in enumerate(lines):
        draw.text(
            (25, 17 + i * 43),
            line,
            font=font,
            fill="white",
        )

    image.save(path)


def create_video(case, config, temp_dir):
    folder = ROOT / f"case_{case}" / "split_screen_export"
    source = folder / "g1_split_screen.mp4"

    if not source.exists():
        raise FileNotFoundError(
            f"Source video not found: {source}"
        )

    source_fps, source_frames = probe_video(source)

    # The existing composer generates two frames per step
    # when using --fps 12 --speed 0.1.
    frames_per_step = 2
    required_frames = config["end"] * frames_per_step + 1

    if source_frames < required_frames:
        raise ValueError(
            f"case_{case}: source has {source_frames} frames, "
            f"but {required_frames} are required."
        )

    output = folder / "g1_split_screen_8x.mp4"

    # Set timestamps to 1/8 of their original values.
    base_filter = (
        f"trim=end_frame={required_frames},"
        f"setpts=(PTS-STARTPTS)/{SPEED},"
        f"fps={OUTPUT_FPS}"
    )

    command = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-i", str(source),
    ]

    if config["stop"] is not None:
        overlay_path = (
            Path(temp_dir) / f"stop_message_{case}.png"
        )
        make_message_image(
            overlay_path, config["stop"]
        )

        stop_time = (
            config["stop"]
            * frames_per_step
            / source_fps
            / SPEED
        )

        command += [
            "-loop", "1",
            "-i", str(overlay_path),
        ]

        filter_complex = (
            f"[0:v]{base_filter}[base];"
            "[base][1:v]overlay="
            "x=(W-w)/2:"
            "y=H-h-15:"
            f"enable='gte(t,{stop_time:.6f})':"
            "shortest=1[out]"
        )

        command += [
            "-filter_complex", filter_complex,
            "-map", "[out]",
        ]
    else:
        command += ["-vf", base_filter]

    command += [
        "-an",
        "-c:v", "libx264",
        "-crf", "20",
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]

    print(f"Creating case_{case} MP4...")
    run(command)

    return output


def create_gif(mp4, gif):
    palette = gif.with_name(
        gif.stem + "_palette.png"
    )

    gif_filter = (
        "fps=12,"
        "scale=1280:-1:flags=lanczos"
    )

    try:
        run([
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-i", str(mp4),
            "-vf",
            gif_filter + ",palettegen=stats_mode=diff",
            str(palette),
        ])

        run([
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-i", str(mp4),
            "-i", str(palette),
            "-lavfi",
            f"[0:v]{gif_filter}[v];"
            "[v][1:v]paletteuse="
            "dither=bayer:bayer_scale=3",
            str(gif),
        ])
    finally:
        palette.unlink(missing_ok=True)


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        for case, config in CASES.items():
            mp4 = create_video(case, config, temp_dir)

            gif = mp4.with_suffix(".gif")

            print(f"Creating case_{case} GIF...")
            create_gif(mp4, gif)

            print(f"Completed case_{case}")
            print(f"  MP4: {mp4}")
            print(f"  GIF: {gif}")

    print("\nAll cases completed!")


if __name__ == "__main__":
    main()
