import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/export_phase2_portfolio_demo.py"
SOURCE = ROOT / "results/phase2_mujoco/g1_forward_facing_portfolio_fit_BP_80010011_schedule0"
SPEC = importlib.util.spec_from_file_location("phase2_portfolio_export", SCRIPT)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def test_display_scene_has_translucent_walls_and_noncolliding_start_goal_pins():
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
    model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    wall_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "wall_0_0")
    assert model.geom_rgba[wall_id, 3] == pytest.approx(0.30)
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


def test_camera_modes_are_deterministic_and_keep_portfolio_route_framed():
    import mujoco

    trajectory = json.loads((SOURCE / "trajectory.json").read_text())
    scenario = json.loads((SOURCE / "scenario.json").read_text())
    for mode in ("portfolio", "follow", "overview"):
        first = exporter.camera_for(mode, trajectory, scenario, trajectory[0], .75)
        second = exporter.camera_for(mode, trajectory, scenario, trajectory[0], .75)
        assert np.array_equal(first.lookat, second.lookat)
        assert first.distance == second.distance
        assert first.type == mujoco.mjtCamera.mjCAMERA_FREE
    portfolio = exporter.camera_for("portfolio", trajectory, scenario, trajectory[0], .75)
    assert portfolio.distance >= 8.5


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
                                      speed=.01) for output in outputs]
    assert metadata[0] == metadata[1]
    assert metadata[0]["source_trajectory_or_metrics_modified"] is False
    for output in outputs:
        frame_paths = sorted((output / "frames").glob("frame_*.png"))
        assert len(frame_paths) == metadata[0]["output_frames"]
        assert (output / "representative.png").is_file()
        assert json.loads((output / "metadata.json").read_text()) == metadata[0]
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
