#!/usr/bin/env python3
"""Compare the two saved Phase 2 outcome changes and render synchronized GIFs.

All primary trajectories come from the committed baseline/sensor traces. The
small intervention-ablation replays are explicitly diagnostic and do not write
to either evaluation directory or tune the controller.
"""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / 'src')
import sys
sys.path[:0] = [sys_path, str(ROOT / 'scripts')]

BASELINE_DIR = ROOT / 'results/phase2_mujoco/g1_forward_first_shield_turns_v3_pedestrian_avoidance_full_288'
SENSOR_DIR = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_full_288_v1'
OUTPUT_DIR = ROOT / 'results/phase2_mujoco/phase2_safety_outcome_causal_diagnostics_v1'
FPS = 20
SECONDS_PER_STEP = 0.15
PANEL = (800, 450)
CASES = {
    'case_A': {
        'label': 'M80030007 / schedule 1 / Periodic / seed 42',
        'identity': 'phase1.5-v0.4-BPRIME-1:fit:M:80030007',
        'schedule': 1, 'method': 'periodic', 'seed': 42,
        'gif': 'M80030007_periodic_before_after_safety_sensor.gif',
        'before_label': 'BEFORE: no safety sensor | Goal reached at 64 | Contact: 0',
        'after_label': 'AFTER: 61-ray sensor | Goal not reached by 80 | Contact: 0',
        'closeup': (34, 44), 'window': (34, 44),
    },
    'case_B': {
        'label': 'R80000001 / schedule 1 / Static / seed 42',
        'identity': 'phase1.5-v0.4-BPRIME-1:fit:R:80000001',
        'schedule': 1, 'method': 'static', 'seed': 42,
        'gif': 'R80000001_static_before_after_safety_sensor.gif',
        'before_label': 'BEFORE: no safety sensor | Goal not reached | Contact: 6 states / 234 pairs',
        'after_label': 'AFTER: 61-ray sensor | Goal reached at 76 | Contact: 0',
        'closeup': (48, 60), 'window': (48, 60),
    },
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def import_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_trace_index(path: Path):
    records = {}
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            record = json.loads(line)
            key = tuple(record['key'])
            if key in records:
                raise ValueError(f'Duplicate trace key in {path}: {key}')
            records[key] = record
    return records


def read_csv_index(path: Path):
    with path.open(newline='', encoding='utf-8') as stream:
        return {(r['world_identity'], int(r['schedule']), r['method'], int(r['seed'])): r
                for r in csv.DictReader(stream)}


def action_differences(a: dict, b: dict) -> list[str]:
    checks = (
        ('position', a.get('position') != b.get('position')),
        ('heading', not math.isclose(float(a.get('heading_yaw', 0)), float(b.get('heading_yaw', 0)), abs_tol=1e-9)),
        ('action', a.get('action') != b.get('action')),
        ('moved', bool(a.get('moved')) != bool(b.get('moved'))),
        ('blocked', bool(a.get('blocked')) != bool(b.get('blocked'))),
        ('observation_granted', bool(a.get('observation_granted')) != bool(b.get('observation_granted'))),
        ('observation_count', int(a.get('observation_count', 0)) != int(b.get('observation_count', 0))),
    )
    return [name for name, differs in checks if differs]


def first_divergence(before: dict, after: dict):
    left, right = before['steps'], after['steps']
    for a, b in zip(left, right):
        if action_differences(a, b):
            return int(a['step']), action_differences(a, b)
    if len(left) != len(right):
        return int(left[min(len(left), len(right))-1]['step']) + 1, ['episode_length']
    return None, []


def _json_cell(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')) if value is not None else ''


def executed_description(frame: dict | None, previous_heading: float | None = None) -> str:
    if frame is None:
        return 'episode_already_finished'
    action = frame.get('action')
    if action is None:
        return 'no_action_episode_complete'
    kind = action[0]
    if frame.get('blocked'):
        return f'collision_shield_blocked:{kind}'
    if kind == 'wait':
        return 'waited'
    if kind == 'turn':
        if previous_heading is not None and not math.isclose(
                float(frame.get('heading_yaw', 0)), previous_heading, abs_tol=1e-9):
            return f'turned_to:{frame.get("heading_yaw", 0):.6f}'
        return 'turn_selected_no_heading_change'
    if frame.get('moved'):
        return f'{kind}_executed_to:{_json_cell(action[1])}'
    return f'{kind}_selected_no_translation'


def action_before_safety(frame: dict) -> object:
    intervention = frame.get('emergency_intervention') or {}
    return intervention.get('selected_action_before', frame.get('action'))


def rejection_reasons(row: dict) -> dict[int, str]:
    raw = row.get('g1_rejected_actions', '[]')
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = ast.literal_eval(raw)
    return {int(item['step']): str(item.get('reason', 'unknown')) for item in raw}


def compare_trace_rows(before: dict, after: dict, baseline_row: dict, safety_row: dict):
    divergence, changed = first_divergence(before, after)
    left, right = before['steps'], after['steps']
    left_by_step = {int(row['step']): row for row in left}
    right_by_step = {int(row['step']): row for row in right}
    base_rejects, safety_rejects = rejection_reasons(baseline_row), rejection_reasons(safety_row)
    rows = []
    for step in range(max(max(left_by_step), max(right_by_step)) + 1):
        a, b = left_by_step.get(step), right_by_step.get(step)
        if a is None or b is None:
            fields = []
        else:
            fields = action_differences(a, b)
        previous_a = left_by_step.get(step - 1)
        previous_b = right_by_step.get(step - 1)
        intervention = (b or {}).get('emergency_intervention') or {}
        sensor = (b or {}).get('emergency_scan') or {}
        rows.append({
            'step': step,
            'first_divergent_step': step == divergence,
            'divergence_components': _json_cell(fields),
            'before_position': _json_cell((a or {}).get('position')),
            'after_position': _json_cell((b or {}).get('position')),
            'before_heading_yaw_rad': (a or {}).get('heading_yaw', ''),
            'after_heading_yaw_rad': (b or {}).get('heading_yaw', ''),
            'before_selected_action': _json_cell((a or {}).get('action')),
            'after_planner_action_before_safety': _json_cell(action_before_safety(b) if b else None),
            'after_selected_action': _json_cell((b or {}).get('action')),
            'before_executed_action': executed_description(a, float(previous_a['heading_yaw']) if previous_a else None),
            'after_executed_action': executed_description(b, float(previous_b['heading_yaw']) if previous_b else None),
            'before_moved': (a or {}).get('moved', ''), 'after_moved': (b or {}).get('moved', ''),
            'before_blocked': (a or {}).get('blocked', ''), 'after_blocked': (b or {}).get('blocked', ''),
            'before_shield_block_reason': base_rejects.get(step, ''),
            'after_shield_block_reason': safety_rejects.get(step, ''),
            'before_memory_observation_granted': (a or {}).get('observation_granted', ''),
            'after_memory_observation_granted': (b or {}).get('observation_granted', ''),
            'before_memory_observation_count': (a or {}).get('observation_count', ''),
            'after_memory_observation_count': (b or {}).get('observation_count', ''),
            'before_evaluator_only_pedestrian_cells': _json_cell((a or {}).get('evaluator_only_proxy_cells')),
            'after_evaluator_only_pedestrian_cells': _json_cell((b or {}).get('evaluator_only_proxy_cells')),
            'after_sensor_visible_pedestrian_cells': _json_cell(sensor.get('visible_pedestrian_cells')),
            'after_safety_intervention_reason': intervention.get('reason', ''),
            'after_safety_action_before': _json_cell(intervention.get('selected_action_before')),
            'after_safety_action_after': _json_cell(intervention.get('selected_action_after')),
            'before_pedestrian_contact_pairs': int((a or {}).get('contacts', {}).get('g1_pedestrian_contact_pairs', 0)),
            'after_pedestrian_contact_pairs': int((b or {}).get('contacts', {}).get('g1_pedestrian_contact_pairs', 0)),
            'before_contact_categories': _json_cell((a or {}).get('contacts')),
            'after_contact_categories': _json_cell((b or {}).get('contacts')),
        })
    return rows, divergence, changed


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def paired_indices(before_count: int, after_count: int):
    """Return synchronized indices; completed streams hold their final frame."""
    if before_count <= 0 or after_count <= 0:
        raise ValueError('Both rendered streams must contain at least one frame')
    return [(min(i, before_count - 1), min(i, after_count - 1))
            for i in range(max(before_count, after_count))]


def _load_font(size=20):
    for path in ('/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if Path(path).is_file():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _overlay_panel(image: Image.Image, title: str, step: int, panel_width: int) -> Image.Image:
    draw = ImageDraw.Draw(image)
    font = _load_font(17)
    small = _load_font(14)
    draw.text((14, 104), title, font=font, fill='black', stroke_width=3, stroke_fill='white')
    draw.text((panel_width - 94, 129), f'STEP {step:02d}', font=small,
              fill='black', stroke_width=3, stroke_fill='white')
    return image


def _palette_from_frames(frames: list[Path]) -> Image.Image:
    picks = sorted({0, len(frames)//4, len(frames)//2, (3*len(frames))//4, len(frames)-1})
    montage = Image.new('RGB', (PANEL[0], PANEL[1] * len(picks)))
    for row, index in enumerate(picks):
        with Image.open(frames[index]) as im:
            montage.paste(im.convert('RGB'), (0, row * PANEL[1]))
    return montage.quantize(colors=256, method=Image.Quantize.MEDIANCUT)


def encode_gif(frames: list[Path], output: Path, fps: int = FPS) -> dict:
    palette = _palette_from_frames(frames)
    images = []
    for frame in frames:
        with Image.open(frame) as image:
            images.append(image.convert('RGB').quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG))
    duration = round(1000 / fps)
    images[0].save(output, save_all=True, append_images=images[1:], optimize=True,
                   duration=duration, loop=0, disposal=2)
    with Image.open(output) as check:
        count = check.n_frames
        size = check.size
        delays = []
        for index in range(count):
            check.seek(index)
            delays.append(int(check.info.get('duration', 0)))
    if count != len(frames) or size != (PANEL[0] * 2, PANEL[1]) or any(d != duration for d in delays):
        raise ValueError(f'GIF validation failed: frames={count}, size={size}, delays={set(delays)}')
    return {'frame_count': count, 'resolution': list(size), 'fps_nominal': fps,
            'frame_delay_ms': duration, 'duration_seconds': sum(delays) / 1000,
            'loop': 0, 'bytes': output.stat().st_size, 'sha256': file_sha(output)}


def _load_result_metadata():
    evaluator = import_module('phase2_full_61ray_eval', ROOT / 'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py')
    evaluator._verify_output(SENSOR_DIR)
    baseline_rows, baseline_index, baseline_provenance, baseline_hashes = evaluator.load_baseline()
    if len(baseline_index) != 288:
        raise ValueError('Expected the full saved 288-case baseline')
    # The run selected by the 61-ray evaluation retained matched no-sensor traces.
    after_baseline_index = read_trace_index(SENSOR_DIR / 'baseline_traces.jsonl.gz')
    after_index = read_trace_index(SENSOR_DIR / 'episode_traces.jsonl.gz')
    if not after_baseline_index or not after_index:
        raise FileNotFoundError('Expected saved baseline and sensor traces in the 61-ray evaluation output')
    before_rows = read_csv_index(BASELINE_DIR / 'episodes.csv')
    sensor_rows = read_csv_index(SENSOR_DIR / 'episodes.csv')
    for case in CASES.values():
        key = (case['identity'], case['schedule'], case['method'], case['seed'])
        if key not in baseline_index or key not in after_baseline_index or key not in after_index:
            raise ValueError(f'Missing matched traces or result row for {key}')
    return evaluator, baseline_provenance, baseline_hashes, after_baseline_index, after_index, before_rows, sensor_rows


def _make_source(result_dir: Path, case_key: str, side: str, trace: dict, payload: dict,
                 schedule: int, output: Path, summary: dict):
    from spatial_memory.simulation import World, scenario_from_bprime
    from spatial_memory.mujoco_navigation import MujocoNavigationScene

    scenario = scenario_from_bprime(payload, schedule)
    scene = MujocoNavigationScene(scenario)
    source = output / 'replay_sources' / case_key / side
    source.mkdir(parents=True, exist_ok=False)
    world = World(scenario)
    trajectory = []
    for record in trace['steps']:
        frame_step = int(record['step'])
        while world.step < frame_step:
            world.advance()
        cells = record.get('evaluator_only_proxy_cells')
        if cells is None:
            cells = [None for _ in scenario.pedestrians]
        if len(cells) != len(scenario.pedestrians):
            raise ValueError(f'Pedestrian visualization count mismatch at {case_key}/{side}/step {frame_step}')
        action = record.get('action')
        trajectory.append({
            'step': frame_step, 'position': list(record['position']),
            'planned': [], 'moved': bool(record.get('moved', False)),
            'blocked': bool(record.get('blocked', False)),
            'heading_yaw': float(record.get('heading_yaw', 0.0)),
            'heading_changed': False,
            'navigation_action': action,
            'navigation_action_reason': record.get('action_reason'),
            'people': cells, 'active_objects': [list(cell) for cell in sorted(world.objects)],
            'g1_pedestrian_contact_pairs': int(record.get('contacts', {}).get('g1_pedestrian_contact_pairs', 0)),
            'g1_wall_contact_pairs': int(record.get('contacts', {}).get('g1_wall_contact_pairs', 0)),
            'g1_persistent_obstacle_contact_pairs': int(record.get('contacts', {}).get('g1_persistent_obstacle_contact_pairs', 0)),
        })
    scenario_json = {'width': scenario.width, 'height': scenario.height,
        'cell_size_m': scene.cell_size, 'start': list(scenario.start), 'goal': list(scenario.goal)}
    (source / 'scenario.json').write_text(json.dumps(scenario_json, sort_keys=True, indent=2)+'\n')
    trajectory_path = source / 'trajectory.json'
    trajectory_path.write_text(json.dumps(trajectory, sort_keys=True, indent=2)+'\n')
    (source / 'scene.xml').write_text(scene.xml+'\n')
    write_json(source / 'summary.json', summary)
    write_json(source / 'provenance.json', {
        'kind': 'presentation-only replay source from saved per-step trace',
        'source_trace_file': str((SENSOR_DIR / ('baseline_traces.jsonl.gz' if side == 'before' else 'episode_traces.jsonl.gz')).relative_to(ROOT)),
        'source_trace_sha256': file_sha(SENSOR_DIR / ('baseline_traces.jsonl.gz' if side == 'before' else 'episode_traces.jsonl.gz')),
        'result_directory': str(result_dir.relative_to(ROOT)),
        'world_identity': CASES[case_key]['identity'], 'schedule': schedule,
        'policy': CASES[case_key]['method'], 'seed': CASES[case_key]['seed'],
        'pose_source': 'saved trace; positions and headings are unchanged',
        'pedestrian_pose_source': 'evaluator-only positions copied from saved trace for retrospective visualization only',
        'object_state_source': 'saved schedule reconstructed only to display scene objects; not used by an agent or controller',
        'trajectory_sha256': file_sha(trajectory_path), 'scene_sha256': file_sha(source / 'scene.xml'),
        'frame_count': len(trajectory),
    })
    return source


def _render_pair(case_key: str, case: dict, before_trace: dict, after_trace: dict,
                 before_row: dict, after_row: dict, payload: dict, output: Path,
                 exporter, temp_root: Path):
    source_before = _make_source(BASELINE_DIR, case_key, 'before', before_trace, payload,
                                 case['schedule'], output, before_row)
    source_after = _make_source(SENSOR_DIR, case_key, 'after', after_trace, payload,
                                case['schedule'], output, after_row)
    render_before = temp_root / f'{case_key}_before'
    render_after = temp_root / f'{case_key}_after'
    meta_before = exporter.render_frames(source_before, render_before,
        camera_mode='trailing', fps=FPS, width=PANEL[0], height=PANEL[1],
        speed=SECONDS_PER_STEP, export_mp4=False, export_gif=False)
    meta_after = exporter.render_frames(source_after, render_after,
        camera_mode='trailing', fps=FPS, width=PANEL[0], height=PANEL[1],
        speed=SECONDS_PER_STEP, export_mp4=False, export_gif=False)
    before_frames = sorted((render_before/'frames').glob('frame_*.png'))
    after_frames = sorted((render_after/'frames').glob('frame_*.png'))
    sync = paired_indices(len(before_frames), len(after_frames))
    composite_dir = temp_root / f'{case_key}_composite'
    composite_dir.mkdir()
    output_frames = []
    steps_per_action = math.ceil(SECONDS_PER_STEP * FPS)
    for i, (li, ri) in enumerate(sync):
        with Image.open(before_frames[li]) as left, Image.open(after_frames[ri]) as right:
            left = _overlay_panel(left.convert('RGB'), case['before_label'], min(i//steps_per_action, len(before_trace['steps'])-1), PANEL[0])
            right = _overlay_panel(right.convert('RGB'), case['after_label'], min(i//steps_per_action, len(after_trace['steps'])-1), PANEL[0])
            canvas = Image.new('RGB', (PANEL[0]*2, PANEL[1]), (250, 250, 250))
            canvas.paste(left, (0, 0)); canvas.paste(right, (PANEL[0], 0))
            ImageDraw.Draw(canvas).line((PANEL[0],0,PANEL[0],PANEL[1]), fill=(255,255,255), width=2)
            frame_path = composite_dir / f'frame_{i:05d}.png'
            canvas.save(frame_path, optimize=False)
            output_frames.append(frame_path)
    main_gif = output / case['gif']
    gif_info = encode_gif(output_frames, main_gif)
    divergence, _ = first_divergence(before_trace, after_trace)
    preview_index = min(len(output_frames)-1, max(0, int(divergence or 0) * steps_per_action))
    shutil.copyfile(output_frames[preview_index], output / f'{case_key}_first_divergence.png')
    close_start, close_end = case['closeup']
    close_lo = min(len(output_frames)-1, max(0, close_start * steps_per_action))
    close_hi = min(len(output_frames), max(close_lo+1, (close_end+1)*steps_per_action))
    close_frames = output_frames[close_lo:close_hi]
    closeup_name = f'{case_key}_first_divergence_closeup.gif'
    closeup_info = encode_gif(close_frames, output/closeup_name)
    return {
        'main_gif': {'path': main_gif.name, **gif_info},
        'closeup_gif': {'path': closeup_name, **closeup_info,
                        'step_window_inclusive': [close_start, close_end]},
        'divergence_preview': f'{case_key}_first_divergence.png',
        'before_render': {k: meta_before[k] for k in ('output_frames','duration_seconds','resolution','fps','camera_mode','seconds_per_saved_action','visual_only_contact_audit') if k in meta_before},
        'after_render': {k: meta_after[k] for k in ('output_frames','duration_seconds','resolution','fps','camera_mode','seconds_per_saved_action','visual_only_contact_audit') if k in meta_after},
        'synchronized_frame_count': len(sync), 'frozen_panel': 'before' if len(before_frames)<len(after_frames) else 'after' if len(after_frames)<len(before_frames) else None,
        'fps': FPS, 'seconds_per_simulation_step': SECONDS_PER_STEP,
        'frame_indices': {'before_end':len(before_frames)-1,'after_end':len(after_frames)-1},
    }


def _controlled_replays(evaluator, cases: dict, worlds: list[dict], baseline_rows: dict):
    from spatial_memory.emergency_safety import EmergencySafetyController
    original = EmergencySafetyController.choose
    requested = (
        ('case_A_sensor_only', 'case_A', None),
        ('case_A_bypass_step38', 'case_A', {38}),
        ('case_A_bypass_steps38_39', 'case_A', {38,39}),
        ('case_B_sensor_only', 'case_B', None),
        ('case_B_bypass_step52', 'case_B', {52}),
        ('case_B_bypass_step54', 'case_B', {54}),
    )
    reports = {}
    for name, case_key, disabled in requested:
        case = cases[case_key]
        payload = next(p for p in worlds if p['identity'] == case['identity'])
        def choose(self, memory, position, goal, yaw, action, measurement, step, blocked,
                   _disabled=disabled):
            if _disabled is None or step in _disabled:
                return None
            return original(self, memory, position, goal, yaw, action, measurement, step, blocked)
        EmergencySafetyController.choose = choose
        try:
            row, trace = evaluator.run_case(payload, case['schedule'], case['method'],
                json.loads(json.dumps(evaluator.frozen_config(evaluator.load_baseline()[2]))),
                with_safety=True, keep_trace=True)
        finally:
            EmergencySafetyController.choose = original
        saved_base = baseline_rows[(case['identity'], case['schedule'], case['method'], case['seed'])]
        if disabled is None and evaluator._current_signature(row) != evaluator._baseline_signature(saved_base):
            raise RuntimeError(f'Sensor-only replay no longer matches the saved baseline for {name}')
        start, end = case['window']
        reports[name] = {
            'case': case_key, 'disabled_override_steps': 'all' if disabled is None else sorted(disabled),
            'emergency_scans_retained': True,
            'scope_note': 'Diagnostic action-override ablation only; not part of the 288-episode evaluation.',
            'success': bool(row['success']), 'goal_step': row['goal_step'] or None,
            'elapsed_steps': int(row['elapsed_steps']), 'final_position': list(row['final_position']),
            'unwanted_contact_states': int(row['g1_unwanted_contact_states']),
            'unwanted_contact_pairs': int(row['g1_unwanted_contact_pairs']),
            'pedestrian_contact_pairs': int(row['g1_pedestrian_contact_pairs']),
            'spatial_memory_observations': int(row['observation_count']),
            'safety_interventions': int(row['emergency_safety_interventions']),
            'action_counts': {'forward':int(row['g1_forward_actions']), 'lateral':int(row['g1_lateral_actions']),
                'backward':int(row['g1_backward_actions']), 'turn':int(row['g1_in_place_turns']), 'wait':int(row['g1_waits'])},
            'trace_window': [{k:s.get(k) for k in ('step','position','heading_yaw','action','action_reason','moved','blocked','emergency_scan','emergency_intervention','contacts')}
                for s in trace['steps'] if start <= s['step'] <= end],
        }
    return reports


def _capture_memory_observations(evaluator, selected, payload_by_identity,
                                 baseline_rows, sensor_rows):
    """Replay only the two matched cases to capture raw scheduled ray grids.

    The saved traces preserve observation timestamps/counts but not their
    ternary grid payloads. This read-only instrumentation captures those
    payloads while verifying each replay still matches its saved outcome.
    """
    from spatial_memory.mujoco_perception import MujocoRayPerception
    original = MujocoRayPerception.observe
    report = {}
    for case_key, (key, case, *_rest) in selected.items():
        captures = {'before': [], 'after': []}
        for side, with_safety in (('before', False), ('after', True)):
            def capture(self, world, position, heading_yaw, _side=side):
                observation = original(self, world, position, heading_yaw)
                # The emergency scanner also uses MujocoRayPerception every
                # step, but has a 360-degree FOV and a different ray budget.
                # Capture only the agent's scheduled 120-degree memory sensor.
                if (not math.isclose(self.horizontal_fov_deg, 120.0, abs_tol=1e-9)
                        or self.ray_count != 61):
                    return observation
                grid = observation.astype('int8', copy=False)
                captures[_side].append({
                    'step': int(world.step), 'position': list(position),
                    'heading_yaw_rad': float(heading_yaw),
                    'grid_shape': list(grid.shape),
                    'grid_sha256': sha(grid.tobytes(order='C')),
                    'unknown_cells': int((grid < 0).sum()),
                    'observed_free_cells': int((grid == 0).sum()),
                    'observed_occupied_cells': int((grid > 0).sum()),
                    'observed_occupied_coordinates_xy': [
                        [int(x), int(y)] for y, x in zip(*((grid > 0).nonzero()))],
                })
                return observation
            MujocoRayPerception.observe = capture
            try:
                baseline_provenance = evaluator.load_baseline()[2]
                config = json.loads(json.dumps(evaluator.frozen_config(baseline_provenance)))
                row, _ = evaluator.run_case(payload_by_identity[case['identity']],
                    case['schedule'], case['method'], config, with_safety=with_safety,
                    keep_trace=False)
            finally:
                MujocoRayPerception.observe = original
            expected = baseline_rows[key] if side == 'before' else sensor_rows[key]
            if evaluator._current_signature(row) != evaluator._baseline_signature(expected):
                raise RuntimeError(f'{case_key} {side} observation-capture replay diverged from saved result')
        report[case_key] = {
            'scope': 'diagnostic replay; no evaluation output or controller input was modified',
            'before_saved_outcome_signature_verified': True,
            'after_saved_outcome_signature_verified': True,
            'before': captures['before'], 'after': captures['after'],
            'comparison': [{
                'step': left['step'],
                'before_position': left['position'], 'after_position': right['position'],
                'before_grid_sha256': left['grid_sha256'], 'after_grid_sha256': right['grid_sha256'],
                'grid_equal': left['grid_sha256'] == right['grid_sha256'],
                'before_observed_occupied_cells': left['observed_occupied_cells'],
                'after_observed_occupied_cells': right['observed_occupied_cells'],
                'before_observed_free_cells': left['observed_free_cells'],
                'after_observed_free_cells': right['observed_free_cells'],
            } for left, right in zip(captures['before'], captures['after'])],
            'same_observation_timestamps_through_first_divergence': [
                x['step'] for x in captures['before']
                if x['step'] <= selected[case_key][6]] == [
                x['step'] for x in captures['after']
                if x['step'] <= selected[case_key][6]],
        }
    return report


def _analysis_text(case_key, case, before, after, base_row, sensor_row, divergence,
                   changed, controls):
    from collections import Counter
    obs_before=[int(s['step']) for s in before['steps'] if s.get('observation_granted')]
    obs_after=[int(s['step']) for s in after['steps'] if s.get('observation_granted')]
    same_people=all((a.get('evaluator_only_proxy_cells') or []) == (b.get('evaluator_only_proxy_cells') or [])
        for a,b in zip(before['steps'],after['steps']))
    if case_key=='case_A':
        return f'''# Case A — M80030007 / Periodic regression

## Verified outcomes and first divergence

The saved baseline reached the goal at step 64 with no unwanted proxy contacts. The 61-ray run did not reach it within 80 steps and also had no unwanted contacts. Comparing the saved per-step records, the first divergence is **step {divergence}**, in: {', '.join(changed)}.

At step 38, both runs were at the same pose before action (position `(8, 10)`, heading π). The planner selected a move to `(7, 10)` in both. The safety scan saw the pedestrian at `(6, 10)` and replaced the move with a wait; it repeated that wait at step 39. In the baseline, G1 moved to `(7, 10)` at step 38, then its step-39 move to `(6, 10)` was rejected by the selected-action collision shield as `translation_collision`. No contact was recorded. This block reason is read from the saved baseline episode metrics.

At step 40, both Periodic policies granted an observation on schedule. The baseline observed from `(7, 10)` and selected `dynamic_threat_uncertain_no_safe_retreat`, remaining there until the pedestrian cleared; it then followed the short lower corridor and reached the goal at step 64. The sensor run observed from `(8, 10)`, turned north at step 40, and took a much longer route around the upper/right corridors. The pedestrian schedule was identical at every aligned step (`matching ground-truth proxy positions: {same_people}`); only G1's position relative to that schedule changed. Neither trajectory recorded contact.

## Observation timing, route, and horizon

The Periodic observation step schedule is unchanged through the common interval: baseline `{obs_before}`; safety run `{obs_after}`. The longer safety run therefore has more total observations ({len(obs_before)} versus {len(obs_after)}) because it continued beyond the baseline goal time, not because the sensor wrote into memory or changed the scheduler. At step 40 the observation occurred at the same time but from a different pose and therefore supplied different local evidence. The safety trajectory used {len(after['steps'])-1} simulated steps and ended at `{after['steps'][-1]['position']}`; it exceeded the baseline completion time by {80-64} steps and hit the 80-step horizon before reaching the goal.

## Controlled causal checks

- With all emergency action overrides suppressed but the 61-ray scans still computed, the replay matched the saved no-sensor baseline and again reached the goal at step 64. The sensor measurement alone did not alter the route.
- Suppressing only the step-38 override did not restore success. Suppressing the step-38 and step-39 overrides also did not restore success: after the baseline-like step-39 collision-shield rejection, the enabled controller intervened at step 40 with an observation-based retreat and the episode took another long route. The exact counterfactual rows are in `controlled_replays.json`.

## Causal conclusion

**Verified mechanism:** safety action selection, beginning with the two waits, changed the robot's position at the periodic observation boundary. The altered pose changed the planner's route, and the resulting detour exhausted the 80-step budget. The all-overrides-suppressed replay returning to the baseline outcome establishes that the action overrides, rather than scanning alone, caused the branch change.

**Limit:** the ablations show that the two waits in isolation are not sufficient to explain the failure; the later state-dependent retreat/action branch matters too. The result does not establish that every safe alternative route would fail. It establishes this controller's saved rollout and the bounded counterfactuals above.
'''
    return f'''# Case B — R80000001 / Static improvement

## Verified outcomes and first divergence

The saved baseline failed by step 80, with 6 contact states and 234 pedestrian-proxy geometry pairs. The 61-ray run reached the goal at step 76 with zero contacts. The first trace divergence is **step {divergence}**, in: {', '.join(changed)}.

Both trajectories match through step 51: G1 is at `(10, 4)`, heading 0, and Static spatial memory has only its initial observation (step 0). At step 52 the planner selects a move to `(11, 4)`. The independent scan observes the proxy at `(11, 5)`; the measured reachable set includes the planned destination, so the controller waits at `(10, 4)`. In the baseline, G1 enters `(11, 4)` at step 52. At step 53 the prescribed proxy moves into `(11, 4)`, where it overlaps the robot. The baseline accumulates 39 contact pairs on each of six states (steps 53–58), totaling 234. Subsequent selected moves are blocked while the overlap persists.

In the safety run, step 53's scan observes the proxy at `(11, 4)`. At step 54 the controller replaces the planned forward move with a one-cell lateral sidestep to `(10, 5)` after its measured reachable set marks `(11, 4)` as unsafe. It waits through step 58 while the proxy traverses the occupied cell, then resumes at step 59 and reaches the goal at step 76. The Static memory observation schedule remains `[0]` in both runs; emergency measurements do not refresh the memory.

## Controlled causal checks

- With scans retained but all emergency action overrides suppressed, the replay matches the saved baseline: no goal by step 80, 6 contact states, 234 pairs.
- Suppressing only the step-52 wait causes the same 6 contact states and 234 pairs to recur, although the robot eventually reaches the goal at step 79. Thus that wait was decisive for avoiding this contact in the tested rollout, but not strictly necessary for binary goal completion if contact is allowed.
- Suppressing the step-54 sidestep leaves the base move selected; the collision shield blocks it. The sensor then sidesteps at step 55, and the robot still reaches the goal at step 76 with zero contacts. Therefore the *exact timing* of the step-54 lateral move is not necessary; avoiding `(11, 4)` and moving laterally once clearance is observed is the effective mechanism.

## Causal conclusion

**Verified mechanism:** step-52 sensing changes the action before G1 enters the proxy's next occupied cell. The step-54 sidestep (or its safe step-55 alternative) keeps the robot out of that cell until the proxy passes. The controlled bypass reproduces the contact episode; no-overrides reproduces baseline. The saved safe trajectory reaches the goal.

**Limit:** this establishes the contact mechanism and outcomes for this fixed schedule and seed. The counterfactual that reaches the goal with contact shows the changed trajectory was necessary for the contact-free result in that intervention ablation, not for goal completion in every possible policy rollout.
'''


def main(output: Path = OUTPUT_DIR):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite diagnostic directory: {output}')
    output.mkdir(parents=True)
    evaluator, baseline_provenance, baseline_hashes, matched_base, sensor_traces, base_rows, sensor_rows = _load_result_metadata()
    if set(base_rows) != set(sensor_rows) or len(base_rows) != 288:
        raise ValueError('Saved baseline and 61-ray episode keys must match exactly')
    from spatial_memory.phase15_bprime_protocol import digest
    payloads = evaluator.nav.admitted_worlds()
    payload_by_identity={p['identity']:p for p in payloads}
    before_records=read_trace_index(SENSOR_DIR/'baseline_traces.jsonl.gz')
    # All episode trace outcomes are matched to saved episode-level rows.
    full_rows={}
    with (SENSOR_DIR/'episodes.csv').open(newline='',encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            full_rows[(row['world_identity'],int(row['schedule']),row['method'],int(row['seed']))]=row
    selected={}
    comparisons={}
    for case_key,case in CASES.items():
        key=(case['identity'],case['schedule'],case['method'],case['seed'])
        before=matched_base[key];after=sensor_traces[key]
        base_row=base_rows[key];sensor_row=sensor_rows[key]
        if int(base_row['elapsed_steps']) != len(before['steps'])-1:
            raise ValueError(f'Baseline trace length/outcome mismatch for {case_key}')
        if int(sensor_row['elapsed_steps']) != len(after['steps'])-1:
            raise ValueError(f'Sensor trace length/outcome mismatch for {case_key}')
        rows,divergence,changed=compare_trace_rows(before,after,base_row,full_rows[key])
        if divergence is None:
            raise ValueError(f'Expected an outcome-change trace divergence for {case_key}')
        write_csv(output / f'{case_key}_trace_comparison.csv',rows)
        selected[case_key]=(key,case,before,after,base_row,sensor_row,divergence,changed)
        comparisons[case_key]={'first_divergent_step':divergence,'changed_fields':changed,
            'baseline_success':base_row['success']=='True','sensor_success':sensor_row['success']=='True',
            'baseline_elapsed_steps':int(base_row['elapsed_steps']),'sensor_elapsed_steps':int(sensor_row['elapsed_steps']),
            'baseline_contact_states':sum(bool(s.get('contact_event')) for s in before['steps']),
            'sensor_contact_states':int(sensor_row['g1_unwanted_contact_states']),
            'baseline_pedestrian_contact_pairs':int(base_row['g1_pedestrian_contact_pairs']),
            'sensor_pedestrian_contact_pairs':int(sensor_row['g1_pedestrian_contact_pairs']),
            'baseline_observation_steps':[int(s['step']) for s in before['steps'] if s.get('observation_granted')],
            'sensor_observation_steps':[int(s['step']) for s in after['steps'] if s.get('observation_granted')],
            'same_ground_truth_pedestrian_positions_by_aligned_step':all(
                (a.get('evaluator_only_proxy_cells') or [])==(b.get('evaluator_only_proxy_cells') or [])
                for a,b in zip(before['steps'],after['steps']))}
    # Minimal action-override ablations use the same saved scenarios and seed;
    # they are diagnostics, not edits or additions to the 288-episode result.
    memory_observations=_capture_memory_observations(evaluator,selected,payload_by_identity,
        base_rows,sensor_rows)
    write_json(output/'observation_grid_diagnostics.json',memory_observations)
    controls=_controlled_replays(evaluator,CASES,payloads,base_rows)
    write_json(output/'controlled_replays.json',controls)
    for case_key,(key,case,before,after,base_row,sensor_row,divergence,changed) in selected.items():
        (output/f'{case_key}_analysis.md').write_text(
            _analysis_text(case_key,case,before,after,base_row,sensor_row,divergence,changed,controls),encoding='utf-8')
    for case_key, (key, case, before, after, *_rest) in selected.items():
        divergence = comparisons[case_key]['first_divergent_step']
        side_summary = {}
        for side in ('before', 'after'):
            latest = max((item for item in memory_observations[case_key][side]
                          if item['step'] <= divergence), key=lambda x: x['step'])
            trace_step = next(item for item in (before if side == 'before' else after)['steps']
                              if int(item['step']) == divergence)
            gt_cells = trace_step.get('evaluator_only_proxy_cells') or []
            # Ground truth is consulted only here, in retrospective reporting.
            latest['retrospective_proxy_cells_at_divergence'] = gt_cells
            latest['retrospective_proxy_cell_in_latest_observed_occupied_cells'] = any(
                cell in latest['observed_occupied_coordinates_xy'] for cell in gt_cells)
            side_summary[side] = latest
        appendix = (
            '\n## Latest scheduled spatial-memory observation at divergence\n\n'
            f"The latest scheduled memory observation before step {divergence} was step "
            f"{side_summary['before']['step']} in the baseline and step {side_summary['after']['step']} "
            f"in the 61-ray run. Their raw ray-grid hashes were "
            f"`{side_summary['before']['grid_sha256']}` and "
            f"`{side_summary['after']['grid_sha256']}`; same grid: "
            f"{side_summary['before']['grid_sha256'] == side_summary['after']['grid_sha256']}. "
            f"At divergence, evaluator-only proxy cell(s) were "
            f"`{side_summary['after']['retrospective_proxy_cells_at_divergence']}`; a proxy cell "
            f"appeared among the latest scheduled ray observation's occupied cells: baseline "
            f"`{side_summary['before']['retrospective_proxy_cell_in_latest_observed_occupied_cells']}`, "
            f"61-ray `{side_summary['after']['retrospective_proxy_cell_in_latest_observed_occupied_cells']}`. "
            "This cell matching is retrospective only and was not an online controller input. "
            "The independent 360-degree emergency scan runs every step and is recorded separately.\n")
        with (output/f'{case_key}_analysis.md').open('a', encoding='utf-8') as stream:
            stream.write(appendix)
    # Source replay data is newly generated under this diagnostic directory;
    # saved evaluation inputs remain read-only.
    exporter=import_module('phase2_portfolio_exporter',ROOT/'scripts/export_phase2_portfolio_demo.py')
    with tempfile.TemporaryDirectory(prefix='phase2_causal_render_',dir='/private/tmp') as temp_name:
        temp_root=Path(temp_name)
        render_info={}
        for case_key,(key,case,before,after,base_row,sensor_row,divergence,changed) in selected.items():
            render_info[case_key]=_render_pair(case_key,case,before,after,
                base_row,sensor_row,payload_by_identity[case['identity']],output,exporter,temp_root)
    write_json(output/'render_validation.json',render_info)
    source_hashes={
        'baseline_provenance_sha256':file_sha(BASELINE_DIR/'provenance.json'),
        'baseline_episodes_sha256':file_sha(BASELINE_DIR/'episodes.csv'),
        'matched_timing_baseline_trace_sha256':file_sha(SENSOR_DIR/'baseline_traces.jsonl.gz'),
        '61ray_episode_trace_sha256':file_sha(SENSOR_DIR/'episode_traces.jsonl.gz'),
        '61ray_episodes_sha256':file_sha(SENSOR_DIR/'episodes.csv'),
        '61ray_manifest_sha256':file_sha(SENSOR_DIR/'experiment_manifest.json'),
        'evaluation_script_sha256':file_sha(ROOT/'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py'),
        'portfolio_renderer_sha256':file_sha(ROOT/'scripts/export_phase2_portfolio_demo.py'),
        'viewer_helpers_sha256':file_sha(ROOT/'scripts/view_phase2_g1_navigation.py'),
    }
    if evaluator.nav.verify_preserved_prefix()['files_checked'] != 836:
        raise RuntimeError('Protected Phase 1.5 file verification failed')
    write_json(output/'metadata.json',{
        'task':'causal saved-trace comparison for two Phase 2 outcome changes',
        'baseline_result_dir':str(BASELINE_DIR.relative_to(ROOT)),
        'safety_result_dir':str(SENSOR_DIR.relative_to(ROOT)),
        'baseline_trace_origin':'Three matched no-sensor replay traces in the 61-ray result; episode signatures match original saved baseline rows.',
        'sensor_trace_origin':'Primary saved 61-ray evaluation trace; original rows and trace files are read-only.',
        'episodes':comparisons,'controlled_replays':'controlled_replays.json',
        'visualization':{'fps':FPS,'seconds_per_simulated_step':SECONDS_PER_STEP,
            'width':1600,'height':450,'camera':'same fixed-world-direction trailing camera and scale on both panels',
            'synchronization':'both start at frame 0; shorter stream holds its last frame; combined GIF loops from the beginning after the longer stream ends',
            'trajectory_source':'saved trace poses/headings; no navigation episode rerun for GIF generation',
            'g1_animation':'presentation-only kinematic gait; not physical locomotion'},
        'phase15_preservation':evaluator.nav.verify_preserved_prefix(),
        'source_hashes':source_hashes,
        'original_evaluation_files_modified':False,
        'result_scope':'retrospective diagnostics only; no policy or experiment parameters changed',
        'software':{'python':sys.version.split()[0],'pillow':Image.__version__},
    })
    (output/'README.md').write_text(
        '# Phase 2 safety outcome diagnostics\n\n'
        'This directory compares the saved no-sensor and optimized 61-ray outcomes for M80030007/Periodic and R80000001/Static. The 288-episode results are not modified.\n\n'
        '- `case_A_trace_comparison.csv`, `case_B_trace_comparison.csv`: aligned saved poses, headings, selected/executed actions, observations, pedestrian states, interventions, and contacts. Ground-truth pedestrian cells are explicitly evaluator-only and used retrospectively.\n'
        '- `case_A_analysis.md`, `case_B_analysis.md`: first divergence, causal interpretation, and controlled action-override ablations.\n'
        '- `M80030007_periodic_before_after_safety_sensor.gif`, `R80000001_static_before_after_safety_sensor.gif`: synchronized 1600×450 side-by-side MuJoCo replays. Panels start together; the shorter panel freezes at its final frame; the GIF loops after the longer run.\n'
        '- `case_A_first_divergence_closeup.gif`, `case_B_first_divergence_closeup.gif`: short synchronized windows around the first meaningful divergence.\n'
        '- `controlled_replays.json`: small, diagnostic override ablations. They are not part of the 288-episode evaluation.\n'
        '- `observation_grid_diagnostics.json`: raw ternary ray-grid hashes and cell counts from matched deterministic replays; each replay was checked against its saved episode signature.\n'
        '- `render_validation.json`, `metadata.json`: GIF dimensions, duration, frame counts, source hashes, and rendering settings.\n\n'
        'The G1 gait and camera are display-only. Pedestrian locations shown in frames are saved evaluator diagnostics, never online controller inputs.\n',encoding='utf-8')
    artifact_manifest=[]
    for path in sorted(p for p in output.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'):
        raw=path.read_bytes();artifact_manifest.append({'path':path.relative_to(output).as_posix(),
            'bytes':len(raw),'sha256':sha(raw)})
    write_json(output/'artifact_manifest.json',artifact_manifest)
    for item in artifact_manifest:
        raw=(output/item['path']).read_bytes()
        if len(raw)!=item['bytes'] or sha(raw)!=item['sha256']:
            raise ValueError(f'Diagnostic artifact hash mismatch: {item["path"]}')
    if sha((BASELINE_DIR/'episodes.csv').read_bytes()) != source_hashes['baseline_episodes_sha256']:
        raise RuntimeError('Baseline results changed during diagnostic generation')
    if sha((SENSOR_DIR/'episodes.csv').read_bytes()) != source_hashes['61ray_episodes_sha256']:
        raise RuntimeError('61-ray evaluation results changed during diagnostic generation')
    print(json.dumps({'status':'PASS_CAUSAL_DIAGNOSTICS','output':str(output.relative_to(ROOT)),
        'first_divergences':{k:v['first_divergent_step'] for k,v in comparisons.items()},
        'gifs':render_info,'artifacts':len(artifact_manifest)},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT_DIR)
    args=parser.parse_args()
    main(args.output.resolve())
