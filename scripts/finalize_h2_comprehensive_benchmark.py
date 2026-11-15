"""Write integrity indexes, replay checks, and a representative comparison GIF.

Postprocessing only: reads saved gzipped episodes and never re-enters the simulator.
"""
from __future__ import annotations

import base64, csv, gzip, hashlib, json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/phase2_mujoco/h2_comprehensive_benchmark_v1'
ANALYSIS = OUT / 'analysis'
ARMS = ('periodic5', 'age4', 'uncertainty', 'caa_full', 'rdao_v2')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_episode(path: Path) -> dict:
    with gzip.open(path, 'rt') as stream:
        return json.load(stream)


def index_and_verify() -> dict:
    with (ANALYSIS / 'replay_index.csv').open(newline='') as stream:
        entries = list(csv.DictReader(stream))
    if len(entries) != 7776:
        raise RuntimeError(f'Expected 7,776 replay index rows, got {len(entries)}')
    index = []
    stage_counts = defaultdict(int)
    new_hf = {'episodes': 0, 'steps': 0, 'expected_steps': 0, 'changes': 0, 'event_types': defaultdict(int)}
    for entry in entries:
        path = ROOT / entry['path']
        if not path.is_file() or sha(path) != entry['sha256']:
            raise RuntimeError(f'Replay hash mismatch: {entry["path"]}')
        item = read_episode(path)
        row = item['row']
        payload_type = 'replay' if 'replay' in item else 'trace'
        replay = item.get('replay') or item.get('trace')
        steps = replay['steps']
        if len(steps) != int(row['elapsed_steps']) + 1:
            raise RuntimeError(f'Frame count mismatch: {entry["path"]}')
        if int(row['observation_count']) > 20:
            raise RuntimeError(f'Observation cap exceeded: {entry["path"]}')
        if not row.get('g1_shield_query_count_valid') or int(row.get('g1_unselected_action_shield_queries', 0)):
            raise RuntimeError(f'Shield integrity failure: {entry["path"]}')
        step_key = 'step' if payload_type == 'replay' else 'step'
        if [int(step[step_key]) for step in steps] != list(range(len(steps))):
            raise RuntimeError(f'Non-contiguous replay steps: {entry["path"]}')
        if entry['condition'] == 'high_frequency' and payload_type == 'replay':
            for step in steps[1:]:
                if step.get('event', {}).get('event_type') not in ('addition', 'removal', 'relocation', 'no_op'):
                    raise RuntimeError(f'Missing dynamic transition event: {entry["path"]}')
            if 'h2_comprehensive_benchmark_v1/high_frequency_environment/' in entry['path']:
                new_hf['episodes'] += 1
                new_hf['expected_steps'] += int(row['elapsed_steps'])
                walls = {tuple(cell) for cell in replay['static_walls_xy']}
                current = {obj['object_id']: tuple(obj['cell']) for obj in replay['initial_objects']}
                for index_step, step in enumerate(steps):
                    event = step.get('event', {})
                    before = {obj['object_id']: tuple(obj['cell']) for obj in step['objects_before']}
                    after = {obj['object_id']: tuple(obj['cell']) for obj in step['objects_after']}
                    if before != current:
                        raise RuntimeError(f'Object state before-event mismatch: {entry["path"]}:{index_step}')
                    kind = event.get('event_type', 'initial')
                    if index_step:
                        new_hf['steps'] += 1
                        new_hf['event_types'][kind] += 1
                        if kind != 'no_op': new_hf['changes'] += 1
                        if not event.get('connectivity_preserved') or not event.get('exclusion_zone_validated'):
                            raise RuntimeError(f'Constraint validation not recorded: {entry["path"]}:{index_step}')
                        if kind == 'addition' and (len(after) != len(current) + 1 or set(after) - set(current) != {event['object_id']}):
                            raise RuntimeError(f'Invalid addition transition: {entry["path"]}:{index_step}')
                        if kind == 'removal' and (len(after) != len(current) - 1 or set(current) - set(after) != {event['object_id']}):
                            raise RuntimeError(f'Invalid removal transition: {entry["path"]}:{index_step}')
                        if kind == 'relocation' and (set(after) != set(current) or after[event['object_id']] == current[event['object_id']]):
                            raise RuntimeError(f'Non-atomic relocation: {entry["path"]}:{index_step}')
                        if kind == 'no_op' and after != current:
                            raise RuntimeError(f'No-op changed object state: {entry["path"]}:{index_step}')
                    object_cells = list(after.values())
                    if len(object_cells) != len(set(object_cells)) or len(after) > 4:
                        raise RuntimeError(f'Object overlap/count violation: {entry["path"]}:{index_step}')
                    if set(object_cells) & walls:
                        raise RuntimeError(f'Object-wall overlap: {entry["path"]}:{index_step}')
                    packed_gt = decode_bool(step['ground_truth_static_and_object_occupancy_packed_bits_base64'])
                    # This legacy-named bitfield includes the pedestrian proxy
                    # occupancy as well as static walls and movable objects.
                    pedestrian_cells = {tuple(person['cell']) for person in step.get('pedestrians_xy', [])}
                    expected = walls | set(object_cells) | pedestrian_cells
                    for y in range(25):
                        for x in range(25):
                            if bool(packed_gt[y, x]) != ((x, y) in expected):
                                raise RuntimeError(f'Ground-truth occupancy replay mismatch: {entry["path"]}:{index_step}')
                    current = after
        stage_counts[entry['condition']] += 1
        index.append({**entry, 'payload_type': payload_type,
                      'seed': int(entry['seed']), 'schedule': int(entry['schedule'])})
    if stage_counts != {'original': 3888, 'high_frequency': 3888}:
        raise RuntimeError(f'Unexpected indexed condition counts: {dict(stage_counts)}')
    index_path = OUT / 'combined_dataset/replay_index.json'
    index_path.write_text(json.dumps({
        'schema_version': 'h2_comprehensive_replay_index_v1',
        'entries': index,
    }, indent=2, sort_keys=True) + '\n')
    if new_hf['episodes'] != 2952:
        raise RuntimeError(f'Expected 2,952 new HF replays, got {new_hf["episodes"]}')
    if new_hf['steps'] != new_hf['expected_steps']:
        raise RuntimeError(f'High-frequency event steps ({new_hf["steps"]}) != metric steps ({new_hf["expected_steps"]})')
    if new_hf['event_types']['addition'] + new_hf['event_types']['removal'] + new_hf['event_types']['relocation'] + new_hf['event_types']['no_op'] != new_hf['steps']:
        raise RuntimeError('High-frequency step/event totals do not reconcile')
    return {'indexed': len(index), 'condition_counts': dict(stage_counts), 'new_high_frequency_replay': {
        'episodes': new_hf['episodes'], 'environment_steps': new_hf['steps'], 'changes': new_hf['changes'],
        'change_rate': new_hf['changes'] / max(1, new_hf['steps']), 'event_types': dict(new_hf['event_types'])}, 'status': 'PASS'}


def decode_ternary(encoded: str) -> np.ndarray:
    packed = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
    out = np.empty(packed.size * 4, dtype=np.int8)
    for i in range(4):
        out[i::4] = ((packed >> (2 * i)) & 3).astype(np.int8) - 1
    return out[:625].reshape(25, 25)


def decode_bool(encoded: str) -> np.ndarray:
    packed = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
    return np.unpackbits(packed, bitorder='little')[:625].reshape(25, 25).astype(bool)


def select_representative() -> tuple[str, int, dict[str, dict]]:
    rows = list(csv.DictReader((OUT / 'combined_dataset/episode_metrics.csv').open()))
    grouped = defaultdict(dict)
    for row in rows:
        if row['condition'] == 'high_frequency' and row['model_id'] in ARMS:
            grouped[(row['world_identity'], int(row['schedule']))][row['model_id']] = row
    candidates = []
    for key, models in grouped.items():
        if len(models) != len(ARMS):
            continue
        outcomes = [int(models[mid]['success']) for mid in ARMS]
        observation_spread = sum(abs(float(models[a]['paid_observations']) - float(models[b]['paid_observations']))
                                 for i, a in enumerate(ARMS) for b in ARMS[i + 1:])
        # Preregistered deterministic rule: maximize distinct outcomes, then
        # observation-count spread; lexicographically smallest key breaks ties.
        candidates.append((-len(set(outcomes)), -observation_spread, key[0], key[1], models))
    if not candidates:
        raise RuntimeError('No complete five-model HF comparison key')
    _, _, identity, schedule, models = min(candidates)
    return identity, schedule, models


def render_comparison(identity: str, schedule: int, models: dict[str, dict]) -> Path:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter
    from matplotlib.colors import ListedColormap

    items = {}
    for arm in ARMS:
        item = read_episode(ROOT / models[arm]['replay_path'])
        items[arm] = item['replay']
    nframes = max(len(x['steps']) for x in items.values())
    fig, axes = plt.subplots(2, 5, figsize=(16, 6.5), constrained_layout=True)
    cmap = ListedColormap(['#e5ebef', '#dff5f7', '#e9a66c'])
    arm_names = {'periodic5': 'Periodic-5', 'age4': 'Age-4', 'uncertainty': 'Uncertainty',
                 'caa_full': 'CAA-Full', 'rdao_v2': 'RDAO v2'}
    def animate(frame_index):
        for col, arm in enumerate(ARMS):
            replay = items[arm]
            step = replay['steps'][min(frame_index, len(replay['steps']) - 1)]
            gt_ax, mem_ax = axes[0, col], axes[1, col]
            gt_ax.clear(); mem_ax.clear()
            gt = decode_bool(step['ground_truth_static_and_object_occupancy_packed_bits_base64'])
            mem = decode_ternary(step['spatial_memory_ternary_packed_2bit_base64'])
            gt_ax.imshow(gt, origin='lower', cmap=ListedColormap(['#f2f5f6', '#34404b']), vmin=0, vmax=1)
            mem_ax.imshow(mem, origin='lower', cmap=cmap, vmin=-1, vmax=1, interpolation='nearest')
            for ax in (gt_ax, mem_ax):
                for person in step.get('pedestrians_xy', []):
                    x, y = person['cell']; ax.scatter([x], [y], s=32, c='#ef514c', edgecolors='white', linewidths=.4)
                route = step.get('planned_path_xy') or []
                if len(route) > 1:
                    ax.plot([p[0] for p in route], [p[1] for p in route], color='#8356d6', lw=1.2)
                sx, sy = replay['start_xy']; gx, gy = replay['goal_xy']
                ax.scatter([sx], [sy], marker='*', s=54, c='#12b8d1', edgecolors='white', linewidths=.4)
                ax.scatter([gx], [gy], marker='*', s=54, c='#e4b02b', edgecolors='white', linewidths=.4)
                rx, ry = step['robot_position_after_action_xy']; yaw = float(step['robot_heading_after_action_rad'])
                ax.scatter([rx], [ry], s=34, c='#174e9a', edgecolors='white', linewidths=.5, zorder=5)
                ax.arrow(rx, ry, .48*np.cos(yaw), .48*np.sin(yaw), color='#14365f', width=.025,
                         head_width=.16, length_includes_head=True, zorder=6)
                ax.set_xlim(-.5, 24.5); ax.set_ylim(-.5, 24.5); ax.set_aspect('equal')
                ax.set_xticks([]); ax.set_yticks([])
            event = step.get('event', {}).get('event_type', 'initial')
            outcome = 'GOAL' if replay.get('outcome', {}).get('success') else 'NO GOAL'
            gt_ax.set_title(f'{arm_names[arm]} · {outcome}', fontsize=9)
            detail = step.get('event', {})
            source = detail.get('from_cell') or detail.get('previous_cell')
            target = detail.get('to_cell') or detail.get('new_cell')
            transition = f'{source}→{target}' if source and target else (str(target) if target else '')
            mem_ax.set_title(f"step {step['step']} · {event} {transition} · objects {len(step['objects_after'])} · paid obs {step['paid_observation_count']}", fontsize=7.5)
        fig.suptitle(f'High-frequency saved replay · {identity} · schedule {schedule}\nTop: ground-truth occupancy   Bottom: spatial memory', fontsize=12)
        return []
    path = OUT / 'analysis' / 'representative_hf_comparison.gif'
    animation = FuncAnimation(fig, animate, frames=nframes, interval=180, blit=False, repeat=True)
    animation.save(path, writer=PillowWriter(fps=6))
    animate(nframes - 1)
    fig.savefig(OUT / 'analysis' / 'representative_hf_trajectory.png', dpi=150)
    plt.close(fig)
    return path


def main() -> None:
    integrity = index_and_verify()
    identity, schedule, models = select_representative()
    gif = render_comparison(identity, schedule, models)
    gif_manifest = {'gif': gif.relative_to(ROOT).as_posix(), 'sha256': sha(gif),
                    'selection_rule': 'Maximize distinct outcome labels among Periodic-5, Age-4, Uncertainty, CAA-Full, RDAO v2; then maximize pairwise paid-observation-count spread; lexicographic map/schedule tie-break.',
                    'selected_world_identity': identity, 'selected_schedule': schedule,
                    'models': {arm: {'success': bool(int(row['success'])), 'replay_path': row['replay_path']}
                               for arm, row in models.items()}}
    (OUT / 'analysis' / 'representative_selection.json').write_text(json.dumps(gif_manifest, indent=2, sort_keys=True) + '\n')
    manifest_path = OUT / 'artifact_manifest.json'
    manifest = []
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path != manifest_path:
            manifest.append({'path': path.relative_to(OUT).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    manifest_path.write_text(json.dumps({'schema_version': 'h2_comprehensive_artifact_manifest_v1',
        'benchmark_binding_commit': json.loads((OUT / 'binding_amendment_2.json').read_text())['commit'],
        'files': manifest}, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'integrity': integrity, 'representative': gif_manifest,
                      'artifact_manifest_files': len(manifest)}, indent=2), flush=True)


if __name__ == '__main__':
    main()
