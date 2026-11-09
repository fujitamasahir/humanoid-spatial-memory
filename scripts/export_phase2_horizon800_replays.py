#!/usr/bin/env python3
"""Render GIF/MP4 replays from the three saved 800-step diagnostic traces.

No evaluator is run. Saved poses, headings, actions, and evaluator-only
pedestrian coordinates are copied to presentation inputs; the latter are used
only to place proxies in the retrospective render.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys
from collections import Counter
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
SOURCE = ROOT / 'results/phase2_mujoco/g1_forward_first_61ray_emergency_safety_unreached_h400_h800_v1'
OUTPUT = ROOT / 'results/phase2_mujoco/g1_horizon800_residual_replays_v1'
FPS, WIDTH, HEIGHT, SPEED = 12, 800, 450, 0.10

EPISODES = (
    ('case_A', 'phase1.5-v0.4-BPRIME-1:fit:BP:80010004', 0, 'static'),
    ('case_B', 'phase1.5-v0.4-BPRIME-1:fit:BP:80010004', 1, 'static'),
    ('case_C', 'phase1.5-v0.4-BPRIME-1:fit:M:80030008', 1, 'static'),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8')


def import_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_artifacts(directory: Path):
    items = json.loads((directory / 'artifact_manifest.json').read_text(encoding='utf-8'))
    for item in items:
        raw = (directory / item['path']).read_bytes()
        if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
            raise ValueError(f'Source artifact hash mismatch: {item["path"]}')
    return items


def loop_diagnostics(steps):
    positions = [tuple(map(int, frame['position'])) for frame in steps]
    states = [(position, round(float(frame['heading_yaw']), 6))
              for position, frame in zip(positions, steps)]
    position_counts = Counter(positions)
    action_counts = Counter((frame.get('action') or ['no_action'])[0] for frame in steps)
    # Find the longest constant position+heading suffix. This distinguishes
    # standing at a dead end from a route that is still cycling.
    final_state = states[-1]
    def is_terminal_no_route(index):
        frame = steps[index]
        return (states[index] == final_state and frame.get('action') is None
                and not frame.get('moved')
                and frame.get('action_reason') == 'no_feasible_forward_route')
    suffix_start = len(states) - 1
    while suffix_start > 0 and is_terminal_no_route(suffix_start - 1):
        suffix_start -= 1
    final_step = int(steps[-1]['step'])
    suffix_step = int(steps[suffix_start]['step'])
    tail_no_route = all(frame.get('action') is None and
                        frame.get('action_reason') == 'no_feasible_forward_route'
                        for frame in steps[suffix_start:])
    final_position = positions[-1]
    first_final_position = next(i for i, pos in enumerate(positions) if pos == final_position)
    active_states = states[:suffix_start]
    exact_cycles = []
    for period in range(2, min(100, len(active_states) // 2) + 1):
        best_count, best_start = 1, None
        for start in range(len(active_states) - 2 * period + 1):
            repeats = 1
            while (start + (repeats + 1) * period <= len(active_states)
                   and active_states[start:start + period] ==
                       active_states[start + repeats * period:start + (repeats + 1) * period]):
                repeats += 1
            if repeats > best_count:
                best_count, best_start = repeats, start
        if best_count >= 2:
            exact_cycles.append({'period_steps': period, 'repetitions': best_count,
                                 'start_step': int(steps[best_start]['step'])})
    after_final_coordinate = steps[first_final_position:suffix_start]
    after_final_actions = Counter((frame.get('action') or ['no_action'])[0]
                                  for frame in after_final_coordinate)
    in_place_turns = [frame for frame in after_final_coordinate
                      if frame.get('action') and frame['action'][0] == 'turn']
    successful_moves_after_visit = [frame for frame in after_final_coordinate
                                    if frame.get('moved')]
    blocked_after_visit = [frame for frame in after_final_coordinate
                           if frame.get('blocked')]
    return {
        'trajectory_steps': final_step,
        'unique_grid_positions': len(set(positions)),
        'unique_position_heading_states': len(set(states)),
        'path_length_cells': round(sum(math.dist(a, b) for a, b in zip(positions, positions[1:])), 6),
        'action_kind_counts': dict(sorted(action_counts.items())),
        'moving_transitions': sum(bool(frame.get('moved')) for frame in steps),
        'most_visited_cells': [{'position': list(pos), 'saved_frames': count}
                               for pos, count in position_counts.most_common(5)],
        'final_coordinate_revisits': {
            'coordinate': list(final_position),
            'first_visit_step': int(steps[first_final_position]['step']),
            'steps_until_no_route_suffix': int(steps[suffix_start]['step']) - int(steps[first_final_position]['step']) if suffix_start < len(steps) else 0,
            'action_counts_in_interval': dict(sorted(after_final_actions.items())),
            'turn_actions_in_interval': len(in_place_turns),
            'first_turn_step': int(in_place_turns[0]['step']) if in_place_turns else None,
            'last_turn_step': int(in_place_turns[-1]['step']) if in_place_turns else None,
            'successful_translations_after_first_visit': len(successful_moves_after_visit),
            'blocked_actions_after_first_visit': len(blocked_after_visit),
        },
        'exact_repeated_position_heading_cycles_before_terminal_no_route': exact_cycles,
        'exact_repeated_position_heading_cycle_found': bool(exact_cycles),
        'exact_cycle_search_periods_checked': [2, min(100, len(active_states) // 2)],
        'constant_final_pose_suffix': {
            'start_step': suffix_step, 'end_step': final_step,
            'saved_frames_including_start': len(states) - suffix_start,
            'stationary_transitions_after_final_turn': final_step - suffix_step,
            'final_position': list(final_state[0]),
            'final_heading_yaw_rad': final_state[1],
            'all_suffix_frames_report_no_feasible_forward_route': tail_no_route,
        },
        'diagnosis': ('roamed_and_revisited_then_stopped_with_no_feasible_forward_route'
                      if tail_no_route and final_step > suffix_step else 'no_long_constant_pose_suffix'),
    }


def make_replay_source(case_dir: Path, case_name: str, trace: dict, row: dict,
                       payload: dict, schedule: int, source_trace_hash: str,
                       cell_size: float, timestep: float, scene_cls, scenario_from_bprime):
    from spatial_memory.simulation import World
    scenario = scenario_from_bprime(payload, schedule)
    scene = scene_cls(scenario, cell_size=cell_size, timestep=timestep)
    source = case_dir / 'replay_source'
    source.mkdir(parents=True, exist_ok=False)
    world = World(scenario)
    trajectory = []
    for record in trace['steps']:
        step = int(record['step'])
        while world.step < step:
            world.advance()
        people = record.get('evaluator_only_proxy_cells')
        if people is None:
            people = [None for _ in scenario.pedestrians]
        if len(people) != len(scenario.pedestrians):
            raise ValueError(f'{case_name} proxy count mismatch at step {step}')
        trajectory.append({
            'step': step, 'position': list(record['position']), 'planned': [],
            'moved': bool(record.get('moved', False)), 'blocked': bool(record.get('blocked', False)),
            'heading_yaw': float(record.get('heading_yaw', 0.0)), 'heading_changed': False,
            'navigation_action': record.get('action'),
            'navigation_action_reason': record.get('action_reason'),
            'people': people, 'active_objects': [list(cell) for cell in sorted(world.objects)],
            'g1_pedestrian_contact_pairs': int(record.get('contacts', {}).get('g1_pedestrian_contact_pairs', 0)),
            'g1_wall_contact_pairs': int(record.get('contacts', {}).get('g1_wall_contact_pairs', 0)),
            'g1_persistent_obstacle_contact_pairs': int(record.get('contacts', {}).get('g1_persistent_obstacle_contact_pairs', 0)),
        })
    write_json(source / 'scenario.json', {'width': scenario.width, 'height': scenario.height,
        'cell_size_m': scene.cell_size, 'start': list(scenario.start), 'goal': list(scenario.goal)})
    trajectory_path = source / 'trajectory.json'
    write_json(trajectory_path, trajectory)
    (source / 'scene.xml').write_text(scene.xml + '\n', encoding='utf-8')
    summary = {key: row.get(key) for key in ('success', 'goal_step', 'elapsed_steps',
        'final_position', 'g1_unwanted_contact_states', 'g1_unwanted_contact_pairs',
        'g1_pedestrian_contact_pairs', 'g1_forward_actions', 'g1_lateral_actions',
        'g1_backward_actions', 'g1_in_place_turns', 'g1_waits')}
    write_json(source / 'summary.json', summary)
    write_json(source / 'provenance.json', {
        'source_kind': 'presentation-only replay from saved 800-step episode trace',
        'source_trace_file': str((SOURCE / 'unreached_traces.jsonl.gz').relative_to(ROOT)),
        'source_trace_sha256': source_trace_hash,
        'source_experiment_directory': str(SOURCE.relative_to(ROOT)),
        'world_identity': trace['key'][0], 'schedule': schedule,
        'policy': trace['key'][2], 'seed': int(trace['key'][3]),
        'pose_and_heading_source': 'saved trajectory; not regenerated',
        'pedestrian_visualization_source': 'saved evaluator-only coordinates; display only',
        'trajectory_sha256': file_sha(trajectory_path),
        'scene_sha256': file_sha(source / 'scene.xml'), 'steps': len(trajectory),
    })
    return source, trajectory_path


def main(output: Path = OUTPUT):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    evaluator = import_module('eval_phase2_61ray', ROOT / 'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py')
    evaluator._verify_output(evaluator.DEFAULT_OUTPUT)
    source_artifacts = verify_artifacts(SOURCE)
    source_manifest = json.loads((SOURCE / 'experiment_manifest.json').read_text(encoding='utf-8'))
    replay_config = source_manifest['source_evaluation_conditions']['policy_config_used']
    rows = list(csv.DictReader((SOURCE / 'unreached_horizon800.csv').open(newline='', encoding='utf-8')))
    row_index = {(r['world_identity'], int(r['schedule']), r['method'], int(r['seed'])): r for r in rows}
    traces = {}
    trace_path = SOURCE / 'unreached_traces.jsonl.gz'
    with gzip.open(trace_path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            record = json.loads(line)
            traces[tuple(record['key'])] = record
    expected_keys = [(identity, schedule, policy, 42)
                     for _, identity, schedule, policy in EPISODES]
    if set(row_index) != set(expected_keys) or set(traces) != set(expected_keys):
        raise ValueError('Expected exactly the three committed horizon-800 traces')
    if any(row_index[key]['success'].lower() != 'true' and
           int(row_index[key]['elapsed_steps']) != 800 for key in expected_keys[:2]):
        raise ValueError('BP episodes no longer match the saved unsuccessful horizon-800 results')

    nav = evaluator.nav
    payloads = {item['identity']: item for item in nav.admitted_worlds()}
    from spatial_memory.mujoco_navigation import MujocoNavigationScene
    from spatial_memory.simulation import scenario_from_bprime
    exporter = import_module('phase2_export_portfolio', ROOT / 'scripts/export_phase2_portfolio_demo.py')
    output.mkdir(parents=True)
    try:
        validation = {}
        for case_name, identity, schedule, policy in EPISODES:
            key = (identity, schedule, policy, 42)
            row, trace = row_index[key], traces[key]
            if identity not in payloads or int(row['elapsed_steps']) != len(trace['steps']) - 1:
                raise ValueError(f'Invalid saved episode data: {key}')
            case_dir = output / case_name
            case_dir.mkdir()
            replay_source, trajectory_path = make_replay_source(
                case_dir, case_name, trace, row, payloads[identity], schedule,
                file_sha(trace_path), float(replay_config['mujoco_cell_size_m']),
                float(replay_config['mujoco_timestep_seconds']),
                MujocoNavigationScene, scenario_from_bprime)
            render_dir = case_dir / 'portfolio_export'
            render_info = exporter.render_frames(replay_source, render_dir,
                camera_mode='trailing', fps=FPS, width=WIDTH, height=HEIGHT,
                speed=SPEED, export_mp4=True, export_gif=True)
            exporter.encode_mp4(render_dir, FPS)
            exporter.encode_gif(render_dir, FPS)
            gif_path = render_dir / 'portfolio_demo.gif'
            with Image.open(gif_path) as gif:
                gif_frames, gif_size = gif.n_frames, gif.size
                gif_durations = []
                for frame_index in range(gif_frames):
                    gif.seek(frame_index)
                    gif_durations.append(int(gif.info.get('duration', 0)))
            if gif_frames != render_info['output_frames'] or gif_size != (WIDTH, HEIGHT):
                raise ValueError(f'GIF validation failed: {gif_frames} frames at {gif_size}')
            if not gif_durations or any(duration <= 0 for duration in gif_durations):
                raise ValueError(f'GIF has missing/invalid frame timing: {gif_durations[:10]}')
            # Retain MP4 master and representative image, omit thousands of
            # intermediate PNG frames to keep the result compact.
            shutil.rmtree(render_dir / 'frames')
            diagnostics = loop_diagnostics(trace['steps'])
            metadata_path = render_dir / 'metadata.json'
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            metadata.update({
                'source_saved_episode': {'world_identity': identity, 'schedule': schedule,
                                         'policy': policy, 'seed': 42},
                'source_horizon800_trace_sha256': file_sha(trace_path),
                'presentation_replay_only': True,
                'experiment_data_or_policy_modified': False,
                'loop_diagnostics': diagnostics,
                'trajectory_source_sha256': file_sha(trajectory_path),
                'gif_validation': {'frames': gif_frames, 'resolution': list(gif_size),
                                   'duration_ms_total': sum(gif_durations),
                                   'min_frame_delay_ms': min(gif_durations),
                                   'max_frame_delay_ms': max(gif_durations)},
            })
            write_json(metadata_path, metadata)
            write_json(case_dir / 'episode_diagnostics.json', diagnostics)
            exporter.write_artifact_manifest(render_dir)
            validation[case_name] = {
                'identity': identity, 'schedule': schedule, 'policy': policy,
                'result': {'success': row['success'], 'goal_step': row['elapsed_steps'] if row['success'].lower() == 'true' else None,
                           'final_position': json.loads(row['final_position']),
                           'unwanted_contact_pairs': int(row['g1_unwanted_contact_pairs'])},
                'loop_diagnostics': diagnostics,
                'replay': {k: render_info.get(k) for k in ('output_frames', 'duration_seconds', 'fps', 'resolution', 'camera_mode', 'seconds_per_saved_action')},
                'gif': {'path': f'{case_name}/portfolio_export/portfolio_demo.gif',
                        'bytes': (render_dir / 'portfolio_demo.gif').stat().st_size,
                        'sha256': file_sha(render_dir / 'portfolio_demo.gif')},
                'mp4': {'path': f'{case_name}/portfolio_export/portfolio_demo.mp4',
                        'bytes': (render_dir / 'portfolio_demo.mp4').stat().st_size,
                        'sha256': file_sha(render_dir / 'portfolio_demo.mp4')},
                'representative_png': f'{case_name}/portfolio_export/representative.png',
            }
        write_json(output / 'render_validation.json', validation)
        (output / 'README.md').write_text(
            '# Horizon-800 residual episode replays\n\n'
            'Three GIFs rendered from the committed horizon-800 traces. No evaluator or environment generation was run. '
            'Recorded G1 poses, headings, actions, and timing are replayed as saved; the visual gait is kinematic only. '
            'Saved evaluator-only proxy coordinates are used only to place proxies in the retrospective scene.\n\n'
            '- `case_A`: BP 80010004, Static, schedule 0\n'
            '- `case_B`: BP 80010004, Static, schedule 1\n'
            '- `case_C`: M 80030008, Static, schedule 1\n\n'
            'No exact repeated position-heading cycle of period 2–100 was detected in either BP trajectory. '
            'They revisit parts of the maze, turn repeatedly, and encounter blocked forward attempts, then stop '
            'when the saved action reason becomes `no_feasible_forward_route`. Exact per-case counts and the '
            'stationary dwell start are in '
            '`episode_diagnostics.json`; rendering metadata and source hashes accompany each GIF.\n',
            encoding='utf-8')
        verify_artifacts(SOURCE)
        evaluator._verify_output(evaluator.DEFAULT_OUTPUT)
        if nav.verify_preserved_prefix()['files_checked'] != 836:
            raise RuntimeError('Phase 1.5 preserved-prefix verification failed')
        write_json(output / 'source_validation.json', {
            'horizon800_source_manifest_sha256': file_sha(SOURCE / 'experiment_manifest.json'),
            'horizon800_artifacts_verified': len(source_artifacts),
            'original_288_result_verified': True,
            'phase15_files_verified': 836,
            'source_files_modified': False,
            'candidate_or_environment_generation': False,
            'experiment_reruns': 0,
        })
        manifest = []
        for path in sorted(p for p in output.rglob('*') if p.is_file() and p.name != 'artifact_manifest.json'):
            raw = path.read_bytes()
            manifest.append({'path': path.relative_to(output).as_posix(), 'bytes': len(raw), 'sha256': sha(raw)})
        write_json(output / 'artifact_manifest.json', manifest)
        for item in manifest:
            raw = (output / item['path']).read_bytes()
            if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
                raise ValueError(f'Artifact hash mismatch: {item["path"]}')
        print(json.dumps({'status': 'PASS_SAVED_HORIZON800_REPLAYS',
                          'output': str(output.relative_to(ROOT)), 'episodes': validation}, indent=2), flush=True)
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=OUTPUT)
    args = parser.parse_args()
    main(args.output_dir.resolve())
