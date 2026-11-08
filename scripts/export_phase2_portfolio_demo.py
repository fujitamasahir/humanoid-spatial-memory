"""Render a saved Phase 2 G1 portfolio trajectory directly through MuJoCo."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont
import mujoco


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "results/phase2_mujoco/g1_forward_facing_portfolio_fit_BP_80010011_schedule0"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/portfolio_export_g1_bp_80010011"
WALL_RGBA = "0.23 0.25 0.29 0.30"
FPS = 24


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tree_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(file for file in path.rglob("*") if file.is_file()):
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256(item.read_bytes())))
    return digest.hexdigest()


def load_viewer_helpers():
    path = ROOT / "scripts/view_phase2_g1_navigation.py"
    spec = importlib.util.spec_from_file_location("phase2_g1_viewer_helpers", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_display_xml(source: Path) -> str:
    """Create a view-only MJCF variant with translucent walls and route pins."""
    viewer = load_viewer_helpers()
    root = ET.fromstring(viewer.display_scene_xml(source))
    scenario = json.loads((source / "scenario.json").read_text())
    width, height, spacing = scenario["width"], scenario["height"], scenario["cell_size_m"]
    for geom in root.iter("geom"):
        name = geom.get("name", "")
        if name.startswith("wall_"):
            geom.set("rgba", WALL_RGBA)
    worldbody = root.find("worldbody")
    if worldbody is None:
        raise ValueError("Saved scene has no worldbody")
    for key, label, rgba in (("start", "START", "0.12 0.72 0.96 1"),
                             ("goal", "GOAL", "1 0.48 0.18 1")):
        cell = scenario[key]
        x = (float(cell[0]) - (width - 1) / 2) * spacing
        y = (float(cell[1]) - (height - 1) / 2) * spacing
        body = ET.SubElement(worldbody, "body", {
            "name": f"portfolio_{key}_marker", "pos": f"{x:.6f} {y:.6f} 0",
        })
        ET.SubElement(body, "geom", {
            "name": f"portfolio_{key}_stem", "type": "cylinder",
            "pos": "0 0 1.58", "size": "0.055 0.20", "rgba": rgba,
            "contype": "0", "conaffinity": "0", "group": "0",
        })
        ET.SubElement(body, "geom", {
            "name": f"portfolio_{key}_tip", "type": "ellipsoid",
            "pos": "0 0 1.82", "size": "0.14 0.14 0.16", "rgba": rgba,
            "contype": "0", "conaffinity": "0", "group": "0",
        })
    return ET.tostring(root, encoding="unicode")


def camera_for(mode: str, trajectory: list[dict], scenario: dict, frame: dict,
               spacing: float) -> mujoco.MjvCamera:
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(camera)
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.azimuth = 138.0
    camera.elevation = -48.0
    def world(cell):
        return ((float(cell[0]) - (scenario["width"] - 1) / 2) * spacing,
                (float(cell[1]) - (scenario["height"] - 1) / 2) * spacing)
    if mode == "overview":
        camera.lookat[:] = (0.0, 0.0, 0.85)
        camera.distance = max(scenario["width"], scenario["height"]) * spacing * 1.45
    elif mode == "follow":
        x, y = world(frame["position"])
        camera.lookat[:] = (x, y, 0.95)
        camera.distance = 5.8
    else:
        positions = [world(item["position"]) for item in trajectory]
        xs, ys = zip(*positions)
        center_x, center_y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        camera.lookat[:] = (center_x, center_y, 0.95)
        route_span = max(max(xs) - min(xs), max(ys) - min(ys), 3.0)
        camera.distance = max(8.5, route_span * 1.65)
    return camera


def apply_hud(frame: Image.Image, index: int, total: int, fps: int) -> Image.Image:
    """Add restrained title, endpoint labels, and timeline to the rendered image."""
    image = frame.convert("RGB")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = image.size
    font = ImageFont.load_default(size=max(16, width // 72))
    small = ImageFont.load_default(size=max(12, width // 100))
    draw.rounded_rectangle((28, 24, min(width - 28, 360), 96), radius=16,
                           fill=(10, 20, 30, 168), outline=(255, 255, 255, 52), width=1)
    draw.text((48, 37), "UNITREE G1  /  MAZE NAVIGATION", fill=(245, 249, 252, 255), font=font)
    draw.text((48, 68), "PRESENTATION REPLAY  •  KINEMATIC ROOT MOTION",
              fill=(171, 198, 214, 255), font=small)
    draw.rounded_rectangle((28, height - 46, width - 28, height - 28), radius=9,
                           fill=(9, 18, 27, 155))
    progress = index / max(1, total - 1)
    bar_right = 28 + int((width - 56) * progress)
    draw.rounded_rectangle((28, height - 46, max(38, bar_right), height - 28),
                           radius=9, fill=(49, 190, 229, 235))
    # Endpoint legend keeps START/GOAL readable even when the 3D pins are distant.
    draw.rounded_rectangle((width - 238, 24, width - 28, 96), radius=16,
                           fill=(10, 20, 30, 168), outline=(255, 255, 255, 52), width=1)
    draw.ellipse((width - 214, 43, width - 198, 59), fill=(31, 184, 239, 255))
    draw.text((width - 187, 41), "START", fill=(245, 249, 252, 255), font=small)
    draw.ellipse((width - 214, 67, width - 198, 83), fill=(255, 122, 46, 255))
    draw.text((width - 187, 65), "GOAL", fill=(245, 249, 252, 255), font=small)
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _set_group(options, group: int, enabled: bool) -> None:
    options.geomgroup[group] = int(enabled)


def render_frames(source: Path, output: Path, *, camera_mode="portfolio", fps=FPS,
                  width=1280, height=720, speed=0.8) -> dict:
    viewer = load_viewer_helpers()
    scenario = json.loads((source / "scenario.json").read_text())
    trajectory_path = source / "trajectory.json"
    trajectory_bytes = trajectory_path.read_bytes()
    trajectory = json.loads(trajectory_bytes)
    if len(trajectory) < 2:
        raise ValueError("Portfolio source trajectory must contain multiple saved poses")
    if trajectory[0]["position"] != scenario["start"] or trajectory[-1]["position"] != scenario["goal"]:
        raise ValueError("Source trajectory does not match its saved start and goal")
    if output.exists():
        raise FileExistsError(f"Output directory already exists; refusing to overwrite: {output}")

    xml = make_display_xml(source)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "stand")
    free_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "floating_base_joint")
    if key < 0 or free_joint < 0:
        raise ValueError("Scene is missing the G1 stand key or floating_base_joint")
    mujoco.mj_resetDataKeyframe(model, data, key)
    qadr = int(model.jnt_qposadr[free_joint])
    root_qpos = data.qpos[qadr:qadr + 7].copy()
    stand_pose, gait_addresses = {}, {}
    for name in viewer.gait_joint_targets(model, 0.0, 0.0):
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if jid >= 0 and model.jnt_type[jid] == mujoco.mjtJoint.mjJNT_HINGE:
            address = int(model.jnt_qposadr[jid])
            stand_pose[name] = float(data.qpos[address])
            gait_addresses[name] = (jid, address)
    object_ids, pedestrian_ids = {}, {}
    for body in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body) or ""
        if name.startswith("object_body_"):
            cell = tuple(map(int, name.removeprefix("object_body_").split("_")))
            object_ids[cell] = int(model.body_mocapid[body])
        elif name.startswith("pedestrian_"):
            pedestrian_ids[int(name.removeprefix("pedestrian_"))] = int(model.body_mocapid[body])

    spacing = scenario["cell_size_m"]
    samples = viewer.playback_samples(trajectory, speed, spacing, fps=fps)
    try:
        renderer = mujoco.Renderer(model, height=height, width=width)
    except Exception as error:
        raise RuntimeError(
            "MuJoCo offscreen rendering could not initialize a macOS graphics context. "
            "Run from a logged-in macOS Terminal session; if needed use `.venv/bin/mjpython`. "
            f"Renderer error: {error}"
        ) from error
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True)
    option = mujoco.MjvOption()
    mujoco.mjv_defaultOption(option)
    _set_group(option, 5, True)
    option.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = 1
    count = 0
    try:
        for count, (frame, env_frame, phase, amplitude, travel_sign) in enumerate(samples):
            x, y = frame["position"]
            world_x = (x - (scenario["width"] - 1) / 2) * spacing
            world_y = (y - (scenario["height"] - 1) / 2) * spacing
            data.qpos[qadr:qadr + 7] = root_qpos
            data.qpos[qadr:qadr + 2] = (world_x, world_y)
            yaw = float(frame.get("heading_yaw", 0.0))
            data.qpos[qadr + 3:qadr + 7] = (math.cos(yaw / 2), 0, 0, math.sin(yaw / 2))
            for name, base in stand_pose.items():
                data.qpos[gait_addresses[name][1]] = base
            for name, offset in viewer.gait_joint_targets(model, phase, amplitude, travel_sign).items():
                jid, address = gait_addresses[name]
                low, high = map(float, model.jnt_range[jid])
                data.qpos[address] = min(high, max(low, stand_pose[name] + offset))
            data.qvel[:] = 0
            for cell, mocap in object_ids.items():
                cx, cy = cell
                data.mocap_pos[mocap] = ((cx - (scenario["width"] - 1) / 2) * spacing,
                                         (cy - (scenario["height"] - 1) / 2) * spacing,
                                         0 if list(cell) in env_frame["active_objects"] else -1000)
            for person, mocap in pedestrian_ids.items():
                cell = env_frame["people"][person] if person < len(env_frame["people"]) else None
                if cell is None:
                    data.mocap_pos[mocap] = (0, 0, -1000)
                else:
                    data.mocap_pos[mocap] = ((cell[0] - (scenario["width"] - 1) / 2) * spacing,
                                             (cell[1] - (scenario["height"] - 1) / 2) * spacing, 0)
            data.time = count / fps
            mujoco.mj_forward(model, data)
            camera = camera_for(camera_mode, trajectory, scenario, frame, spacing)
            if camera_mode == "follow":
                camera.lookat[:] = (world_x, world_y, 0.95)
            renderer.update_scene(data, camera=camera, scene_option=option)
            pixels = renderer.render()
            image = apply_hud(Image.fromarray(pixels), count, 1, fps)
            image.save(frames_dir / f"frame_{count:05d}.png", optimize=False)
    finally:
        renderer.close()
    total = count + 1
    # Save a representative image outside the frame sequence for convenient previews.
    representative = frames_dir / f"frame_{max(0, total // 2):05d}.png"
    shutil.copyfile(representative, output / "representative.png")
    viewer_path = ROOT / "scripts/view_phase2_g1_navigation.py"
    source_scene = source / "scene.xml"
    settings = {
        "source_result_dir": str(source.relative_to(ROOT)),
        "source_trajectory_sha256": sha256(trajectory_bytes),
        "source_scene_sha256": sha256(source_scene.read_bytes()),
        "trajectory_frames": len(trajectory),
        "output_frames": total,
        "fps": fps,
        "duration_seconds": total / fps,
        "resolution": {"width": width, "height": height},
        "camera_mode": camera_mode,
        "camera": {"azimuth_deg": 138.0, "elevation_deg": -48.0,
                   "portfolio_distance_rule": "max(8.5 m, 1.65 x saved route span)"},
        "seconds_per_saved_action": speed,
        "walls_rgba": WALL_RGBA,
        "start_goal_markers": "non-colliding MuJoCo cylinder stem plus floating ellipsoid head; blue START, orange GOAL",
        "visual_gait": "reused deterministic viewer gait_joint_targets and playback_samples; display-only, not physical locomotion",
        "source_trajectory_or_metrics_modified": False,
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     check=True, capture_output=True, text=True).stdout.strip(),
        "renderer": {"mujoco_version": mujoco.__version__, "backend": "MuJoCo offscreen Renderer",
                     "python": sys.version.split()[0]},
        "model_hashes": {
            "saved_scene_sha256": sha256(source_scene.read_bytes()),
            "unitree_g1_mjcf_sha256": sha256((ROOT / "third_party/unitree_g1/g1.xml").read_bytes()),
            "unitree_g1_assets_tree_sha256": tree_sha256(ROOT / "third_party/unitree_g1/assets"),
        },
        "source_code_sha256": {
            "export_script": sha256(Path(__file__).read_bytes()),
            "viewer_helpers": sha256(viewer_path.read_bytes()),
        },
    }
    (output / "metadata.json").write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n")
    write_artifact_manifest(output)
    return settings


def encode_mp4(output: Path, fps: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("MP4 export requires ffmpeg. Install it with `brew install ffmpeg`, then rerun the export command.")
    subprocess.run([ffmpeg, "-y", "-framerate", str(fps), "-i",
                    str(output / "frames" / "frame_%05d.png"), "-c:v", "libx264",
                    "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(output / "portfolio_demo.mp4")], check=True)


def encode_gif(output: Path, fps: int) -> None:
    files = sorted((output / "frames").glob("frame_*.png"))
    duration_ms = round(1000 / fps)
    images = [Image.open(path).convert("RGB") for path in files]
    if not images:
        raise ValueError("No rendered frames available for GIF")
    # Sample every frame into a compact contact sheet so the shared GIF palette
    # includes colors that appear later in the sequence as well as at frame 0.
    palette_sheet = Image.new("RGB", (96, 54 * len(images)))
    for index, image in enumerate(images):
        palette_sheet.paste(image.resize((96, 54), Image.Resampling.BILINEAR), (0, index * 54))
    palette = palette_sheet.quantize(colors=192, method=Image.Quantize.MEDIANCUT)
    converted = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
    converted[0].save(output / "portfolio_demo.gif", save_all=True,
                      append_images=converted[1:], duration=duration_ms, loop=0,
                      optimize=False, disposal=2)


def write_artifact_manifest(output: Path) -> None:
    records = []
    for path in sorted(item for item in output.rglob("*")
                       if item.is_file() and item.name != "artifact_manifest.json"):
        raw = path.read_bytes()
        records.append({"path": path.relative_to(output).as_posix(),
                        "bytes": len(raw), "sha256": sha256(raw)})
    (output / "artifact_manifest.json").write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--camera", choices=("portfolio", "follow", "overview"), default="portfolio")
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--speed", type=float, default=0.8,
                        help="Seconds per saved action; default yields a 10-12 second highlight")
    parser.add_argument("--mp4", action="store_true")
    parser.add_argument("--gif", action="store_true")
    args = parser.parse_args(argv)
    source = args.result_dir.resolve()
    output = args.output_dir.resolve()
    if not (source / "trajectory.json").is_file() or not (source / "scene.xml").is_file():
        parser.error(f"Source must contain saved trajectory.json and scene.xml: {source}")
    if args.fps < 1 or args.fps > 60 or not (320 <= args.width <= 3840) or not (180 <= args.height <= 2160):
        parser.error("Use 1..60 fps, width 320..3840, and height 180..2160")
    if args.speed <= 0:
        parser.error("--speed must be positive")
    if args.mp4 and shutil.which("ffmpeg") is None:
        parser.error("MP4 export needs ffmpeg; install it with `brew install ffmpeg` and rerun")
    if output.exists():
        parser.error(f"Refusing to overwrite existing output directory: {output}")
    try:
        metadata = render_frames(source, output, camera_mode=args.camera, fps=args.fps,
                                 width=args.width, height=args.height, speed=args.speed)
        if args.mp4:
            encode_mp4(output, args.fps)
        if args.gif:
            encode_gif(output, args.fps)
        write_artifact_manifest(output)
    except (RuntimeError, ValueError, FileExistsError, OSError) as error:
        parser.error(str(error))
    print(json.dumps({"status": "PASS_PRESENTATION_EXPORT", "output": str(output),
                      "frames": metadata["output_frames"], "duration_seconds": metadata["duration_seconds"],
                      "mp4": (output / "portfolio_demo.mp4").exists(),
                      "gif": (output / "portfolio_demo.gif").exists()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
