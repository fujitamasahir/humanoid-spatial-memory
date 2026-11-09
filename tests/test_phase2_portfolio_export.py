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


def test_display_scene_restores_compact_cyan_gold_markers_and_native_robot_materials():
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
        assert root.find(f".//geom[@name='portfolio_{key}_aura_outer']") is None
        assert root.find(f".//geom[@name='portfolio_{key}_tip']").get("size") == "0.115 0.115 0.12"
        assert root.find(f".//geom[@name='portfolio_{key}_halo_outer']").get("size") == "0.27 0.27 0.020"
        assert root.find(f".//geom[@name='portfolio_{key}_core']") is not None
        assert root.find(f".//geom[@name='portfolio_{key}_base']") is not None
        assert root.find(f".//geom[@name='portfolio_{key}_glint']") is not None
    model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    wall_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "wall_0_0")
    assert 0.48 <= model.geom_rgba[wall_id, 3] <= 0.58
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    floor_luma = float(np.dot(model.geom_rgba[floor_id, :3], (0.2126, 0.7152, 0.0722)))
    wall_luma = float(np.dot(model.geom_rgba[wall_id, :3], (0.2126, 0.7152, 0.0722)))
    assert floor_luma > wall_luma
    black_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_MATERIAL, "black")
    assert tuple(model.mat_rgba[black_id]) == pytest.approx((0.2, 0.2, 0.2, 1.0))
    metal_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_MATERIAL, "metal")
    assert tuple(model.mat_rgba[metal_id]) == pytest.approx((0.7, 0.7, 0.7, 1.0))
    native_g1 = ET.parse(ROOT / "third_party/unitree_g1/g1.xml").getroot()
    for mesh_name in ("head_link", "left_ankle_roll_link", "right_ankle_roll_link"):
        native = native_g1.find(f".//geom[@mesh='{mesh_name}']")
        assert native is not None and native.get("material") == "black"
    # Every geom belonging to the G1 subtree and its bound material stays opaque.
    robot_geom_ids = set()
    for geom_id in range(model.ngeom):
        body_id = int(model.geom_bodyid[geom_id])
        while body_id > 0:
            body_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id) or ""
            if body_name == "pelvis":
                robot_geom_ids.add(geom_id)
                break
            body_id = int(model.body_parentid[body_id])
    assert robot_geom_ids
    assert all(model.geom_rgba[geom_id, 3] == pytest.approx(1.0)
               for geom_id in robot_geom_ids)
    robot_material_ids = {int(model.geom_matid[geom_id]) for geom_id in robot_geom_ids
                          if int(model.geom_matid[geom_id]) >= 0}
    assert robot_material_ids
    assert all(model.mat_rgba[material_id, 3] == pytest.approx(1.0)
               for material_id in robot_material_ids)
    for key, expected in (("start", (0.0, 0.78, 1.0)),
                          ("goal", (1.0, 0.76, 0.08))):
        geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM,
                                    f"portfolio_{key}_tip")
        rgba = model.mat_rgba[model.geom_matid[geom_id]]
        assert tuple(rgba[:3]) == pytest.approx(expected)
        core_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM,
                                    f"portfolio_{key}_core")
        core_mat = int(model.geom_matid[core_id])
        assert model.mat_emission[core_mat] >= 0.99
        assert model.mat_rgba[core_mat, 3] == pytest.approx(1.0)
        core_expected = (0.48, 1.0, 1.0) if key == "start" else (1.0, 0.94, 0.42)
        assert tuple(model.mat_rgba[core_mat, :3]) == pytest.approx(core_expected)
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
    visual = root.find("visual")
    headlight = visual.find("headlight")
    assert headlight is not None
    assert headlight.get("ambient") == "0.36 0.39 0.44"
    fills = [light for light in root.findall("./worldbody/light")
             if (light.get("name") or "").startswith("portfolio_fill_")]
    assert len(fills) == 4
    assert all(light.get("directional") == "true" and light.get("castshadow") == "false"
               for light in fills)

    with pytest.raises(ValueError, match="must be positive"):
        exporter.make_display_xml(SOURCE, offwidth=0)


def test_render_options_do_not_globally_fade_dynamic_robot_or_waypoint_geoms():
    import mujoco

    options = exporter.make_render_options()
    assert options.geomgroup[5] == 1
    assert options.flags[mujoco.mjtVisFlag.mjVIS_TRANSPARENT] == 0


def test_fixed_direction_tracking_camera_never_orbits_and_tracks_by_translation_only():
    import mujoco

    trajectory = json.loads((SOURCE / "trajectory.json").read_text())
    scenario = json.loads((SOURCE / "scenario.json").read_text())
    for mode in ("tracking", "trailing", "follow", "portfolio", "overview"):
        first = exporter.camera_for(mode, trajectory, scenario, trajectory[0], .75)
        second = exporter.camera_for(mode, trajectory, scenario, trajectory[0], .75)
        assert np.array_equal(first.lookat, second.lookat)
        assert first.distance == second.distance
        assert first.type == mujoco.mjtCamera.mjCAMERA_FREE
    first = dict(trajectory[0], heading_yaw=0.0)
    east = exporter.camera_for("tracking", trajectory, scenario, first, .75)
    assert east.azimuth == pytest.approx(exporter.FOLLOW_AZIMUTH_DEG)
    cell_x = (first["position"][0] - (scenario["width"] - 1) / 2) * .75
    assert east.lookat[0] == pytest.approx(cell_x + exporter.FOLLOW_LOOKAHEAD_M)
    north_frame = dict(first, heading_yaw=np.pi / 2)
    north = exporter.camera_for("tracking", trajectory, scenario, north_frame, .75)
    assert north.azimuth == east.azimuth
    assert north.elevation == east.elevation
    assert np.array_equal(north.lookat, east.lookat), "camera must not use heading to change direction or lookahead"
    assert east.distance == pytest.approx(exporter.FOLLOW_DISTANCE_M)
    assert east.elevation == pytest.approx(exporter.FOLLOW_ELEVATION_DEG)
    tracker = exporter.FollowCamera(trajectory, scenario, .75)
    tracker.update(first)
    advanced = dict(first, position=[first["position"][0] + 2, first["position"][1]])
    smoothed = tracker.update(advanced)
    immediate = exporter.camera_for("trailing", trajectory, scenario, advanced, .75)
    assert smoothed.lookat[0] < immediate.lookat[0]

    helper = exporter.load_viewer_helpers()
    orientations = []
    for frame, _, _, _, _ in helper.playback_samples(trajectory, .18, .75, fps=24):
        camera = tracker.update(frame)
        orientations.append((camera.azimuth, camera.elevation))
    assert all(pair == pytest.approx((exporter.FOLLOW_AZIMUTH_DEG,
                                     exporter.FOLLOW_ELEVATION_DEG)) for pair in orientations)
    # Changing heading alone must leave every camera field except look-at fixed;
    # this guards against regressions where camera control references robot yaw.
    turned = dict(first, heading_yaw=2.4)
    direct = exporter.camera_for("tracking", trajectory, scenario, turned, .75)
    assert direct.azimuth == east.azimuth and direct.elevation == east.elevation
    assert direct.distance == east.distance


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
                                      speed=.01, camera_mode="tracking", export_mp4=True,
                                      export_gif=True) for output in outputs]
    assert metadata[0] == metadata[1]
    assert metadata[0]["source_trajectory_or_metrics_modified"] is False
    assert metadata[0]["g1_rendered_alpha"] == 1.0
    assert metadata[0]["global_dynamic_geom_transparency"] is False
    assert "Disabled mjVIS_TRANSPARENT" in metadata[0]["opacity_fix"]
    assert "Compact cyan/gold" in metadata[0]["marker_glow_design"]
    assert "native Unitree G1" in metadata[0]["robot_appearance_source"]
    assert "reference image 1" in metadata[0]["start_goal_markers"]
    assert metadata[0]["thumbnail_framing"]["camera_distance_m"] == exporter.FOLLOW_DISTANCE_M
    assert metadata[0]["lighting"]["directional_fill_count"] == 4
    assert metadata[0]["video_outputs"] == {"mp4": True, "gif": True}
    assert "palettegen stats_mode=full" in metadata[0]["gif_conversion"]["method"]
    for output in outputs:
        frame_paths = sorted((output / "frames").glob("frame_*.png"))
        assert len(frame_paths) == metadata[0]["output_frames"]
        assert (output / "representative.png").is_file()
        note = (output / "presentation_note.md").read_text()
        assert "reference image 1" in note and "reference image 4" in note
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


def test_gif_encoding_generates_and_uses_palette_from_mp4_master(monkeypatch, tmp_path):
    monkeypatch.setattr(exporter.shutil, "which", lambda _: "/usr/local/bin/ffmpeg")
    commands = []
    monkeypatch.setattr(exporter.subprocess, "run", lambda command, **kwargs: commands.append(command))
    (tmp_path / "portfolio_demo.mp4").write_bytes(b"mp4-master")
    exporter.encode_gif(tmp_path, 24)
    assert len(commands) == 2
    assert str(tmp_path / "portfolio_demo.mp4") in commands[0]
    palette_filter = commands[0][commands[0].index("-vf") + 1]
    assert "palettegen=stats_mode=full:max_colors=256:reserve_transparent=0" in palette_filter
    assert str(tmp_path / "portfolio_demo.mp4") in commands[1]
    gif_filter = commands[1][commands[1].index("-filter_complex") + 1]
    assert "paletteuse=dither=sierra2_4a:diff_mode=rectangle" in gif_filter
    assert str(tmp_path / "portfolio_demo.gif") == commands[1][-1]
    assert "MP4 master" in exporter.GIF_CONVERSION_METHOD
