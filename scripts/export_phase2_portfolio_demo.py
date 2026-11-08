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
DEFAULT_SOURCE = ROOT / "results/phase2_mujoco/g1_mujoco3d_heading_perception_smoke"
DEFAULT_OUTPUT = ROOT / "results/phase2_mujoco/portfolio_export_g1_heading_follow_v4"
WALL_RGBA = "0.40 0.48 0.56 0.38"
FLOOR_RGBA = "0.57 0.65 0.68 1"
FPS = 24
SECONDS_PER_ACTION = 0.18
FOLLOW_DISTANCE_M = 5.4
FOLLOW_ELEVATION_DEG = -44.0
FOLLOW_LOOKAHEAD_M = 0.65


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


def candidate_metrics(result_dir: Path) -> dict:
    """Score a saved actual-G1 successful, contact-free replay without rerunning it."""
    summary_path, trajectory_path, scene_path = (result_dir / "summary.json",
                                                  result_dir / "trajectory.json",
                                                  result_dir / "scene.xml")
    provenance_path = result_dir / "provenance.json"
    required = (summary_path.is_file() and trajectory_path.is_file() and
                scene_path.is_file() and provenance_path.is_file())
    if not required:
        return {"eligible": False, "reason": "missing saved provenance, scene, summary, or trajectory"}
    summary = json.loads(summary_path.read_text())
    provenance = json.loads(provenance_path.read_text())
    trajectory = json.loads(trajectory_path.read_text())
    robot_model = str(provenance.get("robot_model", ""))
    model_files = {entry.get("path") for entry in provenance.get("robot_model_files", [])}
    model_xml = scene_path.read_text(errors="ignore")
    actual_g1 = (("Unitree G1" in robot_model and "actual Unitree G1" in robot_model) or
                 ("third_party/unitree_g1/g1.xml" in model_files and
                  "floating_base_joint" in model_xml))
    if not actual_g1:
        return {"eligible": False, "reason": "provenance does not identify the actual Unitree G1 model"}
    if not trajectory:
        return {"eligible": False, "reason": "saved trajectory is empty"}
    if summary.get("success") is True:
        success = True
        safe = bool(summary.get("contact_free_success", summary.get("g1_contact_free_success", False)))
        unwanted = int(summary.get("g1_unwanted_contact_pairs", summary.get("collision_count", 0)))
    else:
        periodic = summary.get("summary", {}).get("methods", {}).get("periodic", {})
        success = int(periodic.get("goal_completions", 0)) > 0
        safe = int(periodic.get("g1_contact_free_completions", 0)) > 0
        unwanted = int(periodic.get("g1_unwanted_contact_pairs", 0))
    if not success:
        return {"eligible": False, "reason": "saved run did not complete its goal"}
    if not safe or unwanted:
        return {"eligible": False, "reason": "saved run is not contact-free"}
    positions = [tuple(map(float, frame["position"])) for frame in trajectory]
    route_length = sum(math.dist(a, b) for a, b in zip(positions, positions[1:]))
    span_x = max(p[0] for p in positions) - min(p[0] for p in positions)
    span_y = max(p[1] for p in positions) - min(p[1] for p in positions)
    heading_changes = sum(bool(frame.get("heading_changed")) for frame in trajectory)
    score = 10 * heading_changes + route_length + span_x + span_y
    return {
        "eligible": True,
        "successful": True,
        "contact_free": True,
        "unwanted_contact_pairs": unwanted,
        "heading_changes": heading_changes,
        "route_length_cells": route_length,
        "path_span_cells": {"x": span_x, "y": span_y},
        "saved_poses": len(trajectory),
        "score": score,
        "score_rule": "10 * heading_changes + route_length_cells + x_span_cells + y_span_cells",
    }


def select_source_result(results_root: Path = ROOT / "results/phase2_mujoco") -> tuple[Path, dict]:
    """Choose the most visually rich saved successful contact-free actual-G1 route."""
    reports = []
    for candidate in sorted((p for p in results_root.iterdir() if p.is_dir()), key=lambda p: p.name):
        if not (candidate / "trajectory.json").exists():
            continue
        metrics = candidate_metrics(candidate)
        try:
            relative = candidate.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            relative = candidate.name
        reports.append({"_path": candidate.resolve(), "result_dir": relative, **metrics})
    eligible = sorted((item for item in reports if item.get("eligible")),
                      key=lambda item: (-item["score"], item["result_dir"]))
    if not eligible:
        raise ValueError("No saved successful, contact-free actual-G1 trajectory is eligible")
    public_reports = [{key: value for key, value in item.items() if key != "_path"}
                      for item in reports]
    public_ranking = [{key: value for key, value in item.items() if key != "_path"}
                      for item in eligible]
    report = {
        "rule": "Require a saved actual-Unitree-G1 successful goal completion, zero unwanted contacts, and a preserved trajectory. Rank eligible runs by 10 * heading changes + route length in cells + x span + y span; ties break by result directory name.",
        "candidates": public_reports,
        "eligible_ranking": public_ranking,
        "selected": public_ranking[0],
        "reason": ("Selected the highest-scoring eligible saved route. The rule rewards recorded turns, route length, and spatial coverage; it does not alter or regenerate the trajectory."),
    }
    return eligible[0]["_path"], report


def make_display_xml(source: Path, *, offwidth: int = 1280,
                     offheight: int = 720) -> str:
    """Create a view-only MJCF with translucent walls and adequate offscreen buffers."""
    if offwidth < 1 or offheight < 1:
        raise ValueError("Offscreen framebuffer dimensions must be positive")
    viewer = load_viewer_helpers()
    root = ET.fromstring(viewer.display_scene_xml(source))
    # The saved MuJoCo scene defaults to a 640 x 480 framebuffer. A Renderer
    # request larger than that raises an error before its first image. Configure
    # only the derived presentation XML; never edit source experiment scenes.
    visual = root.find("visual")
    if visual is None:
        visual = ET.Element("visual")
        worldbody_index = next((i for i, child in enumerate(root)
                                if child.tag == "worldbody"), len(root))
        root.insert(worldbody_index, visual)
    global_settings = visual.find("global")
    if global_settings is None:
        global_settings = ET.SubElement(visual, "global")
    global_settings.set("offwidth", str(offwidth))
    global_settings.set("offheight", str(offheight))
    scenario = json.loads((source / "scenario.json").read_text())
    trajectory = json.loads((source / "trajectory.json").read_text())
    scenario.setdefault("start", trajectory[0]["position"])
    scenario.setdefault("goal", trajectory[-1]["position"])
    width, height, spacing = scenario["width"], scenario["height"], scenario["cell_size_m"]
    asset = root.find("asset")
    if asset is None:
        asset = ET.SubElement(root, "asset")
    materials = (
        ("portfolio_start_pin", "0.04 0.73 0.96 1", "0.28"),
        ("portfolio_start_halo", "0.04 0.73 0.96 0.24", "0.42"),
        ("portfolio_goal_pin", "1 0.62 0.10 1", "0.30"),
        ("portfolio_goal_halo", "1 0.62 0.10 0.25", "0.45"),
        ("portfolio_marker_glint", "1 0.94 0.68 0.95", "0.18"),
    )
    for name, rgba, emission in materials:
        ET.SubElement(asset, "material", {"name": name, "rgba": rgba,
                                           "emission": emission, "specular": "0.45",
                                           "shininess": "0.65"})
    # A small presentation-only material lift makes the dark G1 meshes legible
    # when translucent wall geometry overlaps the camera ray.
    for material_name, rgba, emission in (("black", "0.58 0.65 0.70 1", "0.12"),
                                          ("metal", "0.82 0.86 0.89 1", "0.05")):
        material = asset.find(f"material[@name='{material_name}']")
        if material is not None:
            material.set("rgba", rgba)
            material.set("emission", emission)
            material.set("specular", "0.48")
            material.set("shininess", "0.58")
    for geom in root.iter("geom"):
        name = geom.get("name", "")
        if name.startswith("wall_"):
            geom.set("rgba", WALL_RGBA)
        elif name == "floor":
            geom.set("rgba", FLOOR_RGBA)
    worldbody = root.find("worldbody")
    if worldbody is None:
        raise ValueError("Saved scene has no worldbody")
    for key, label, material, halo in (("start", "START", "portfolio_start_pin", "portfolio_start_halo"),
                                       ("goal", "GOAL", "portfolio_goal_pin", "portfolio_goal_halo")):
        cell = scenario[key]
        x = (float(cell[0]) - (width - 1) / 2) * spacing
        y = (float(cell[1]) - (height - 1) / 2) * spacing
        body = ET.SubElement(worldbody, "body", {
            "name": f"portfolio_{key}_marker", "pos": f"{x:.6f} {y:.6f} 0",
        })
        # Layered flat ellipsoids make a restrained halo around a small pin.
        for suffix, z, sizes, mat in (("halo_outer", 1.43, "0.25 0.25 0.022", halo),
                                      ("halo_inner", 1.46, "0.16 0.16 0.026", halo)):
            ET.SubElement(body, "geom", {"name": f"portfolio_{key}_{suffix}",
                "type": "ellipsoid", "pos": f"0 0 {z}", "size": sizes,
                "material": mat, "contype": "0", "conaffinity": "0", "group": "0"})
        ET.SubElement(body, "geom", {"name": f"portfolio_{key}_stem", "type": "cylinder",
            "pos": "0 0 1.75", "size": "0.032 0.25", "material": material,
            "contype": "0", "conaffinity": "0", "group": "0"})
        ET.SubElement(body, "geom", {"name": f"portfolio_{key}_tip", "type": "ellipsoid",
            "pos": "0 0 2.02", "size": "0.105 0.105 0.12", "material": material,
            "contype": "0", "conaffinity": "0", "group": "0"})
        ET.SubElement(body, "geom", {"name": f"portfolio_{key}_glint", "type": "sphere",
            "pos": "0.035 -0.032 2.06", "size": "0.028", "material": "portfolio_marker_glint",
            "contype": "0", "conaffinity": "0", "group": "0"})
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
    else:
        yaw = float(frame.get("heading_yaw", 0.0))
        x, y = world(frame["position"])
        camera.lookat[:] = (x + FOLLOW_LOOKAHEAD_M * math.cos(yaw),
                            y + FOLLOW_LOOKAHEAD_M * math.sin(yaw), 0.95)
        camera.azimuth = (math.degrees(yaw) + 180.0) % 360.0
        camera.elevation = FOLLOW_ELEVATION_DEG
        camera.distance = FOLLOW_DISTANCE_M
    return camera


class FollowCamera:
    """Smoothed trailing camera that looks slightly ahead along recorded yaw."""
    def __init__(self, trajectory: list[dict], scenario: dict, spacing: float,
                 *, smoothing: float = 0.22):
        self.trajectory = trajectory
        self.scenario = scenario
        self.spacing = spacing
        self.smoothing = smoothing
        self.camera = None

    def update(self, frame: dict) -> mujoco.MjvCamera:
        desired = camera_for("follow", self.trajectory, self.scenario, frame, self.spacing)
        if self.camera is None:
            self.camera = mujoco.MjvCamera()
            mujoco.mjv_defaultCamera(self.camera)
            self.camera.type = desired.type
            self.camera.distance = desired.distance
            self.camera.elevation = desired.elevation
            self.camera.azimuth = desired.azimuth
            self.camera.lookat[:] = desired.lookat
            return self.camera
        alpha = self.smoothing
        self.camera.lookat[:] += alpha * (desired.lookat - self.camera.lookat)
        delta = (desired.azimuth - self.camera.azimuth + 180.0) % 360.0 - 180.0
        self.camera.azimuth = (self.camera.azimuth + alpha * delta) % 360.0
        self.camera.elevation += alpha * (desired.elevation - self.camera.elevation)
        return self.camera


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
    draw.text((48, 68), "PRESENTATION REPLAY  |  KINEMATIC ROOT MOTION",
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
    draw.ellipse((width - 214, 67, width - 198, 83), fill=(255, 166, 31, 255))
    draw.text((width - 187, 65), "GOAL", fill=(245, 249, 252, 255), font=small)
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _set_group(options, group: int, enabled: bool) -> None:
    options.geomgroup[group] = int(enabled)


def render_frames(source: Path, output: Path, *, camera_mode="follow", fps=FPS,
                  width=1280, height=720, speed=SECONDS_PER_ACTION,
                  source_selection: dict | None = None) -> dict:
    viewer = load_viewer_helpers()
    scenario = json.loads((source / "scenario.json").read_text())
    trajectory_path = source / "trajectory.json"
    trajectory_bytes = trajectory_path.read_bytes()
    trajectory = json.loads(trajectory_bytes)
    if len(trajectory) < 2:
        raise ValueError("Portfolio source trajectory must contain multiple saved poses")
    scenario.setdefault("start", trajectory[0]["position"])
    scenario.setdefault("goal", trajectory[-1]["position"])
    if trajectory[0]["position"] != scenario["start"] or trajectory[-1]["position"] != scenario["goal"]:
        raise ValueError("Source trajectory does not match its saved start and goal")
    if output.exists():
        raise FileExistsError(f"Output directory already exists; refusing to overwrite: {output}")

    xml = make_display_xml(source, offwidth=width, offheight=height)
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

    floor_geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    g1_geoms, allowed_foot_geoms = set(), set()
    for geom in range(model.ngeom):
        body = int(model.geom_bodyid[geom])
        while body > 0:
            body_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body) or ""
            if body_name == "pelvis":
                g1_geoms.add(geom)
                geom_body_name = mujoco.mj_id2name(
                    model, mujoco.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[geom])) or ""
                if ("ankle_roll_link" in geom_body_name and
                    int(model.geom_type[geom]) == int(mujoco.mjtGeom.mjGEOM_SPHERE) and
                    float(model.geom_size[geom, 0]) <= 0.0051):
                    allowed_foot_geoms.add(geom)
                break
            body = int(model.body_parentid[body])
    visual_audit = {"rendered_poses": 0, "foot_floor_contact_pairs": 0,
                    "unwanted_contact_pairs": 0, "unwanted_contact_frames": 0,
                    "contact_categories": {}}

    spacing = scenario["cell_size_m"]
    samples = list(viewer.playback_samples(trajectory, speed, spacing, fps=fps))
    try:
        renderer = mujoco.Renderer(model, height=height, width=width)
    except Exception as error:
        raise RuntimeError(
            "MuJoCo offscreen rendering failed. The presentation scene requests "
            f"a {width}x{height} framebuffer; verify the display-only MJCF "
            "offwidth/offheight settings. On macOS, run in a logged-in Terminal "
            "using `.venv/bin/mjpython` if native graphics access is unavailable. "
            f"Renderer error: {error}"
        ) from error
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True)
    option = mujoco.MjvOption()
    mujoco.mjv_defaultOption(option)
    _set_group(option, 5, True)
    option.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] = 1
    follow_camera = FollowCamera(trajectory, scenario, spacing) if camera_mode == "follow" else None
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
            bad_this_frame = 0
            for contact_index in range(data.ncon):
                contact = data.contact[contact_index]
                geom_a, geom_b = int(contact.geom1), int(contact.geom2)
                if ((geom_a in allowed_foot_geoms and geom_b == floor_geom) or
                    (geom_b in allowed_foot_geoms and geom_a == floor_geom)):
                    visual_audit["foot_floor_contact_pairs"] += 1
                    continue
                if geom_a in g1_geoms or geom_b in g1_geoms:
                    bad_this_frame += 1
                    visual_audit["unwanted_contact_pairs"] += 1
                    other = geom_b if geom_a in g1_geoms else geom_a
                    other_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, other) or ""
                    category = ("wall" if other_name.startswith("wall_") else
                                "pedestrian" if other_name.startswith("pedestrian_geom_") else
                                "persistent_obstacle" if other_name.startswith("object_geom_") else
                                "floor" if other == floor_geom else "other")
                    categories = visual_audit["contact_categories"]
                    categories[category] = categories.get(category, 0) + 1
            visual_audit["rendered_poses"] += 1
            if bad_this_frame:
                visual_audit["unwanted_contact_frames"] += 1
            camera = (follow_camera.update(frame) if follow_camera is not None else
                      camera_for(camera_mode, trajectory, scenario, frame, spacing))
            renderer.update_scene(data, camera=camera, scene_option=option)
            pixels = renderer.render()
            image = apply_hud(Image.fromarray(pixels), count, len(samples), fps)
            image.save(frames_dir / f"frame_{count:05d}.png", optimize=False)
    finally:
        renderer.close()
    total = count + 1
    # Save a representative image outside the frame sequence for convenient previews.
    representative = frames_dir / f"frame_{max(0, total // 2):05d}.png"
    shutil.copyfile(representative, output / "representative.png")
    visual_audit["status"] = ("PASS" if visual_audit["unwanted_contact_pairs"] == 0 else "FAIL")
    visual_audit["interpretation"] = (
        "Presentation-only MuJoCo pose contact audit; kinematic root poses and visual gait, "
        "separate from navigation safety metrics.")
    (output / "visual_only_contact_audit.json").write_text(
        json.dumps(visual_audit, indent=2, sort_keys=True) + "\n")
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
        "camera": {"style": "smoothed heading-relative trailing/over-shoulder follow",
                   "distance_m": FOLLOW_DISTANCE_M,
                   "elevation_deg": FOLLOW_ELEVATION_DEG,
                   "lookahead_m": FOLLOW_LOOKAHEAD_M,
                   "target_smoothing_alpha": 0.22,
                   "azimuth_rule": "recorded heading yaw + 180 degrees"},
        "seconds_per_saved_action": speed,
        "walls_rgba": WALL_RGBA,
        "floor_rgba": FLOOR_RGBA,
        "g1_presentation_materials": "view-only brighter blue-slate black material and neutral silver metal material; source MJCF and collision geometry unchanged",
        "start_goal_markers": "non-colliding cyan/gold emissive pin with layered translucent halo and specular highlight",
        "visual_gait": "reused deterministic viewer gait_joint_targets and playback_samples; display-only, not physical locomotion",
        "visual_only_contact_audit_file": "visual_only_contact_audit.json",
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
    if source_selection is not None:
        settings["source_selection"] = source_selection["selected"]
        (output / "source_selection.json").write_text(
            json.dumps(source_selection, indent=2, sort_keys=True) + "\n")
    (output / "metadata.json").write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n")
    write_artifact_manifest(output)
    return settings


def encode_mp4(output: Path, fps: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("MP4 export requires ffmpeg. Install it with `brew install ffmpeg`, then rerun the export command.")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-framerate", str(fps), "-i",
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
    parser.add_argument("--result-dir", type=Path,
                        help="Optional saved eligible source; default uses the deterministic best-route score")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--camera", choices=("follow", "overview"), default="follow")
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--speed", type=float, default=SECONDS_PER_ACTION,
                        help="Seconds per saved action; default frames this route in about 15 seconds")
    parser.add_argument("--mp4", action="store_true")
    parser.add_argument("--gif", action="store_true")
    args = parser.parse_args(argv)
    selected_source, selection_report = select_source_result()
    source = args.result_dir.resolve() if args.result_dir else selected_source
    source_metrics = candidate_metrics(source)
    if not source_metrics.get("eligible"):
        parser.error(f"Source is not a saved successful, contact-free actual-G1 route: {source_metrics.get('reason')}")
    if args.result_dir:
        selection_report = dict(selection_report)
        selection_report["selected"] = {"result_dir": source.relative_to(ROOT).as_posix(),
                                         **source_metrics}
        selection_report["reason"] = "An explicit eligible saved source was requested; its score and all candidates remain recorded."
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
                                 width=args.width, height=args.height, speed=args.speed,
                                 source_selection=selection_report)
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
