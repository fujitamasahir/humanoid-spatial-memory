"""Run a read-only navigation pilot on existing admitted R/BP/M fit checkpoints.

No environment generation, no checkpoint writes, no calibration/selection leakage.
This is a pilot, not a replacement for the original cryptographic stage audit.
"""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
import time
from pathlib import Path

from spatial_memory.phase15_bprime import ACTIVE_MECHANISMS, VERSION, seed_for
from spatial_memory.phase15_bprime_protocol import digest
from spatial_memory.simulation import scenario_from_bprime
from spatial_memory.evaluation import run_episode

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORES = (
    'results/raw/phase15_macos_development',
    'results/raw/phase15_bprime_fit_recovery_1',
    'results/raw/phase15_bprime_fit_recovery_2',
)
METHODS = ('static', 'periodic', 'age', 'uncertainty')


def checkpoints(roots):
    seen = set()
    for root in roots:
        directory = root / 'records'
        if not directory.is_dir():
            raise FileNotFoundError(f'Missing checkpoint directory: {directory}')
        for path in sorted(directory.glob('*.json.gz')):
            packed = path.read_bytes()
            body = json.loads(gzip.decompress(packed))
            payload = body['payload']
            identity = body['identity']
            if (path.name != hashlib.sha256(identity.encode()).hexdigest() + '.json.gz'
                    or body.get('payload_sha256') != digest(payload)
                    or payload.get('identity') != identity):
                raise ValueError(f'Checkpoint integrity mismatch: {path}')
            if identity in seen:
                raise ValueError(f'Duplicate checkpoint identity: {identity}')
            seen.add(identity)
            yield payload


def admitted_worlds(roots):
    worlds = {}
    for payload in checkpoints(roots):
        if payload.get('partition') != 'fit' or payload.get('outcome') != 'independent':
            continue
        mechanism = payload.get('mechanism')
        if mechanism not in ACTIVE_MECHANISMS:
            continue
        index = payload['index']
        identity = f'{VERSION}:fit:{mechanism}:{seed_for("fit", mechanism, index)}'
        if payload['identity'] != identity:
            raise ValueError(f'Invalid seed identity: {payload["identity"]}')
        worlds.setdefault(mechanism, []).append(payload)
    counts = Counter({m: len(worlds.get(m, ())) for m in ACTIVE_MECHANISMS})
    if any(counts[m] != 12 for m in ACTIVE_MECHANISMS):
        raise ValueError(f'Expected exactly 12 admitted fit worlds per method; got {dict(counts)}. '
                         'Pass the actual checkpoint store directories using --store.')
    return [p for m in ACTIVE_MECHANISMS for p in sorted(worlds[m], key=lambda p: p['index'])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, action='append', help='Checkpoint store root; repeat for each epoch')
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'phase2_navigation_pilot.csv')
    parser.add_argument('--max-steps', type=int, default=80)
    args = parser.parse_args()
    if args.max_steps < 1:
        parser.error('--max-steps must be positive')
    roots = args.store or [ROOT / p for p in DEFAULT_STORES]
    worlds = admitted_worlds(roots)
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0),
                  update_interval=4, unknown='optimistic', max_steps=args.max_steps,
                  observation_cost=1, max_observations=20)
    rows = []
    total = len(worlds) * 2 * len(METHODS)
    started = last_report = time.monotonic()
    print(f'Starting Phase 2 pilot: 0/{total} episodes (0.0%)', flush=True)
    for payload in worlds:
        for schedule in (0, 1):
            scenario = scenario_from_bprime(payload, schedule)
            for method in METHODS:
                metrics, _ = run_episode(scenario, config, method, seed=42)
                rows.append(dict(mechanism=payload['mechanism'],
                                 world_identity=payload['identity'], schedule=schedule, **metrics))
                now = time.monotonic()
                completed = len(rows)
                if now - last_report >= 900 or completed == total:
                    elapsed = now - started
                    remaining = elapsed / completed * (total - completed)
                    print(f'Progress: {completed}/{total} ({100 * completed / total:.1f}%) | '
                          f'elapsed {elapsed / 60:.1f} min | ETA {remaining / 60:.1f} min',
                          flush=True)
                    last_report = now
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'PASS: {len(worlds)} fit worlds, {len(rows)} navigation episodes')
    print(f'Results: {args.output}')
    for method in METHODS:
        subset = [r for r in rows if r['method'] == method]
        print(f'{method}: success={sum(r["success"] for r in subset)}/{len(subset)}, '
              f'mean_observations={sum(r["observation_count"] for r in subset)/len(subset):.2f}')


if __name__ == '__main__':
    main()
