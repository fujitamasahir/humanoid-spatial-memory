import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/export_phase2_portfolio_demo.py"
SOURCE = ROOT / "results/phase2_mujoco/g1_mujoco3d_heading_perception_smoke"
SPEC = importlib.util.spec_from_file_location("phase2_portfolio_export", SCRIPT)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def test_display_scene_has_readable_translucent_walls_and_cyan_gold_halo_pins():
    import mujoco

    root = ET.fromstring(exporter.make_display_xml(SOURCE))
    walls = [geom for geom in root.iter("geom") if geom.get("name", "").startswith("wall_")]
    assert walls and all(geom.get("rgba") == exporter.WALL_RGBA for geom in walls)
    for key in ("start", "goal"):
        stem = root.find(f".//geom[@name='portfolio_{key}_stem']")
        tip = root.find(f".//geom[@name='portfolio_{key}_tip']")
        assert stem is not None and tip is not None
        assert stem.get("type") == "cylinder"
        assert tip.get("type") == "ellipsoid"
        assert stem.get("contype") == tip.get("contype") == "0"
        assert stem.get("conaffinity") == tip.get("conaffinity") == "0"
        assert root.find(f".//geom[@name='portfolio_{key}_halo_outer']") is not None
        assert root.find(f".//geom[@name='portfolio_{key}_glint']") is not None
    model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    wall_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "wall_0_0")
    assert 0.30 <= model.geom_rgba[wall_id, 3] <= 0.50
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    floor_luma = float(np.dot(model.geom_rgba[floor_id, :3], (0.2126, 0.7152, 0.0722)))
    wall_luma = float(np.dot(model.geom_rgba[wall_id, :3], (0.2126, 0.7152, 0.0722)))
    assert floor_luma > wall_luma
    black_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_MATERIAL, "black")
    assert model.mat_rgba[black_id, 0] >= 0.4
    for key, expected in (("start", (0.04, 0.73, 0.96)),
                          ("goal", (1.0, 0.62, 0.10))):
        geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM,
                                    f"portfolio_{key}_tip")
        rgba = model.mat_rgba[model.geom_matid[geom_id]]
        assert tuple(rgba[:3]) == pytest.approx(expected)
    for key in ("start", "goal"):
        geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM,
                                    f"portfolio_{key}_stem")
        assert model.geom_contype[geom_id] == model.geom_conaffinity[geom_id] == 0


def test_display_scene_allocates_requested_offscreen_framebuffer():
    import mujoco

    root = ET.fromstring(exporter.make_display_xml(SOURCE, offwidth=1280, offheight=720))
    global_settings = root.find("visual/global")
    assert global_settings is not None
    assert global_settings.attrib["offwidth"] == "1280"
    assert global_settings.attrib["offheight"] == "720"
    compiled = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    assert compiled.vis.global_.offwidth >= 1280
    assert compiled.vis.global_.offheight >= 720

    with pytest.raises(ValueError, match="must be positive"):
        exporter.make_display_xml(SOURCE, offwidth=0)


def test_heading_relative_follow_camera_trails_and_looks_ahead_smoothly():
    import mujoco

    trajectory = json.loads((SOURCE / "trajectory.json").read_text())
    scenario = json.loads((SOURCE / "scenario.json").read_text())
    for mode in ("follow", "overview"):
        first = exporter.camera_for(mode, trajectory, scenario, trajectory[0], .75)
        second = exporter.camera_for(mode, trajectory, scenario, trajectory[0], .75)
        assert np.array_equal(first.lookat, second.lookat)
        assert first.distance == second.distance
        assert first.type == mujoco.mjtCamera.mjCAMERA_FREE
    first = dict(trajectory[0], heading_yaw=0.0)
    east = exporter.camera_for("follow", trajectory, scenario, first, .75)
    assert east.azimuth == pytest.approx(180.0)
    cell_x = (first["position"][0] - (scenario["width"] - 1) / 2) * .75
    assert east.lookat[0] == pytest.approx(cell_x + exporter.FOLLOW_LOOKAHEAD_M)
    north_frame = dict(first, heading_yaw=np.pi / 2)
    north = exporter.camera_for("follow", trajectory, scenario, north_frame, .75)
    assert north.azimuth == pytest.approx(270.0)
    assert north.lookat[1] > east.lookat[1]
    assert east.distance == pytest.approx(exporter.FOLLOW_DISTANCE_M)
    assert east.elevation == pytest.approx(exporter.FOLLOW_ELEVATION_DEG)
    tracker = exporter.FollowCamera(trajectory, scenario, .75, smoothing=.2)
    tracker.update(first)
    advanced = dict(first, position=[first["position"][0] + 2, first["position"][1]])
    smoothed = tracker.update(advanced)
    immediate = exporter.camera_for("follow", trajectory, scenario, advanced, .75)
    assert smoothed.lookat[0] < immediate.lookat[0]


def test_source_selection_uses_a_deterministic_score_and_prefers_complex_safe_route():
    first_path, first = exporter.select_source_result()
    second_path, second = exporter.select_source_result()
    assert first_path == second_path
    assert first == second
    assert first_path.name == "g1_mujoco3d_heading_perception_smoke"
    selected = first["selected"]
    assert selected["eligible"] and selected["successful"] and selected["contact_free"]
    assert selected["heading_changes"] == 23
    assert selected["route_length_cells"] == pytest.approx(69)
    assert selected["path_span_cells"] == {"x": 14, "y": 14}
    assert selected["score"] == pytest.approx(327)
    assert "10 * heading changes" in first["rule"]


def test_offscreen_frame_export_is_deterministic_and_preserves_source(monkeypatch, tmp_path):
    class FakeRenderer:
        def __init__(self, model, *, height, width):
            self.height, self.width = height, width

        def update_scene(self, data, *, camera, scene_option):
            self.camera = camera

        def render(self):
            return np.full((self.height, self.width, 3), (40, 80, 120), dtype=np.uint8)

        def close(self):
            pass

    monkeypatch.setattr(exporter.mujoco, "Renderer", FakeRenderer)
    source_paths = [SOURCE / "trajectory.json", SOURCE / "scene.xml", SOURCE / "scenario.json"]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    outputs = [tmp_path / "first", tmp_path / "second"]
    metadata = [exporter.render_frames(SOURCE, output, fps=1, width=320, height=180,
                                      speed=.01, camera_mode="follow") for output in outputs]
    assert metadata[0] == metadata[1]
    assert metadata[0]["source_trajectory_or_metrics_modified"] is False
    for output in outputs:
        frame_paths = sorted((output / "frames").glob("frame_*.png"))
        assert len(frame_paths) == metadata[0]["output_frames"]
        assert (output / "representative.png").is_file()
        assert json.loads((output / "metadata.json").read_text()) == metadata[0]
        audit = json.loads((output / "visual_only_contact_audit.json").read_text())
        assert audit["rendered_poses"] == metadata[0]["output_frames"]
        assert audit["status"] in {"PASS", "FAIL"}
        assert json.loads((output / "artifact_manifest.json").read_text())
        with pytest.raises(FileExistsError):
            exporter.render_frames(SOURCE, output, fps=1, width=320, height=180, speed=.01)
    manifests = [(output / "artifact_manifest.json").read_bytes() for output in outputs]
    assert manifests[0] == manifests[1]
    after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    assert before == after


def test_mp4_failure_explains_ffmpeg_requirement(monkeypatch, tmp_path):
    monkeypatch.setattr(exporter.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="brew install ffmpeg"):
        exporter.encode_mp4(tmp_path, 24)


def test_hud_generation_is_deterministic():
    from PIL import Image

    source = Image.new("RGB", (640, 360), (45, 60, 75))
    first = exporter.apply_hud(source, 10, 20, 24)
    second = exporter.apply_hud(source, 10, 20, 24)
    assert first.size == (640, 360)
    assert first.tobytes() == second.tobytes()


def test_gif_encoding_works_from_saved_png_frames(tmp_path):
    from PIL import Image

    frames = tmp_path / "frames"
    frames.mkdir()
    Image.new("RGB", (40, 24), (0, 100, 200)).save(frames / "frame_00000.png")
    Image.new("RGB", (40, 24), (200, 100, 0)).save(frames / "frame_00001.png")
    exporter.encode_gif(tmp_path, 24)
    with Image.open(tmp_path / "portfolio_demo.gif") as gif:
        assert gif.n_frames == 2
        assert gif.size == (40, 24)
