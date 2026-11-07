"""Independent saved-trace verification and preregistered paired analysis.

Never executes an assessment policy or selects parameters.
"""
from collections import defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from spatial_memory.assessment_spec import load_inputs, jobs, METHODS, CAPS, LOCK_SHA256
from spatial_memory.assessment_store import atomic_bytes, canonical_bytes
from spatial_memory.tuning_spec import file_sha256
from spatial_memory.simulation import Scenario, World

COMPACT = ROOT / 'results/phase1_4c'
OUTCOMES = ('contact_free_success', 'success', 'observation_count', 'observation_cost',
            'dynamic_contacts', 'dynamic_contact_rate', 'blocked_movement_attempts',
            'elapsed_steps', 'travel_distance', 'observation_requests',
            'observation_requests_denied', 'budget_exhausted',
            'stale_map_errors', 'false_persistent_occupancy_updates', 'missed_persistent_changes',
            'final_stale_map_errors', 'final_false_persistent_occupancy_updates', 'final_missed_persistent_changes',
            'common_horizon_stale_map_errors', 'common_horizon_false_persistent_occupancy_updates',
            'common_horizon_missed_persistent_changes', 'scheduler_seconds', 'diagnostic_seconds',
            'common_planner_seconds', 'scheduler_astar_calls', 'common_planner_calls', 'total_astar_calls',
            'episode_runtime_seconds', 'scheduler_latency_median', 'scheduler_latency_p95')


def write_json(name, value):
    atomic_bytes(COMPACT / name, canonical_bytes(value))


def write_csv(name, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(COMPACT / name, stream.getvalue().encode())


def verify_trace(bundle, scenario):
    """Recompute scientific ledgers from full truth/observation frames, not saved totals."""
    m = bundle['result']['metrics']
    frames = bundle['result']['frames']
    world = World(scenario)
    memory = np.full((scenario.height, scenario.width), -1, dtype=np.int8)
    changed = np.zeros(memory.shape, bool)
    source = changed.copy()
    errors = defaultdict(int)
    contacts = blocked = moved = granted = requested = denied = 0
    previous_position = tuple(scenario.start)
    previous_geometry = world.geometry().copy()
    previous_people = set(world.people())
    last = {}
    for step in range(41):
        if step:
            world.advance()
            changed |= previous_geometry != world.geometry()
        geometry = world.geometry()
        people = np.zeros(memory.shape, bool)
        for x, y in world.people():
            people[y, x] = True
        if step < len(frames):
            f = frames[step]
            assert f['step'] == step
            assert np.array_equal(f['geometry'], geometry) and np.array_equal(f['people'], people)
            observation = f['received_observation']
            assert bool(observation is not None) == f['observation_granted']
            if observation is not None:
                observation = np.asarray(observation)
                visible = observation >= 0
                memory[visible] = observation[visible]
                source[visible] = ((observation == 1) & people & ~geometry)[visible]
                granted += 1
            assert np.array_equal(memory, f['memory'])
            assert granted == f['observation_count']
            if step:
                requested += int(f['observation_requested'])
                denied += int(f['observation_requested'] and not f['observation_granted'])
                x, y = previous_position
                contacts += int((geometry[y, x] and not previous_geometry[y, x])
                                or (previous_position in world.people() and previous_position not in previous_people))
                blocked += int(f['blocked'])
                moved += int(tuple(f['position']) != previous_position)
                assert bool(tuple(f['position']) != previous_position) == f['moved']
            previous_position = tuple(f['position'])
        known = memory >= 0
        mismatch = memory != geometry.astype(np.int8)
        current = dict(stale_map_errors=int(np.sum(known & mismatch)),
                       false_persistent_occupancy_updates=int(np.sum((memory == 1) & ~geometry & source & ~people)),
                       missed_persistent_changes=int(np.sum(changed & (~known | mismatch))))
        for k, value in current.items():
            errors['common_horizon_' + k] += value
            if step < len(frames):
                assert frames[step]['errors'][k] == value
                errors[k] += value
                last['final_' + k] = value
        previous_geometry = geometry.copy()
        previous_people = set(world.people())
    expected = dict(**errors, **last, dynamic_contacts=contacts, blocked_movement_attempts=blocked,
                    collision_count=contacts+blocked, travel_distance=moved,
                    observation_count=granted, observation_cost=1.5*granted,
                    observation_requests=requested, observation_requests_denied=denied,
                    elapsed_steps=len(frames)-1, success=previous_position == tuple(scenario.goal))
    expected['contact_free_success'] = expected['success'] and contacts == 0
    expected['dynamic_contact_rate'] = contacts / max(1, len(frames)-1)
    expected['budget_exhausted'] = m['max_observations'] is not None and granted >= m['max_observations']
    for k, value in expected.items():
        assert m[k] == value, (bundle['job']['episode_id'], k, m[k], value)
    assert m['common_planner_calls'] == len(frames)
    assert m['scheduler_astar_calls'] == sum(f['scheduler_astar_calls'] for f in frames[1:])
    assert m['total_astar_calls'] == m['scheduler_astar_calls'] + len(frames)
    return len(expected)


def bootstrap_weights(records):
    """Global layout resampling, fixed before outcome access; equal family weighting."""
    layouts = sorted({r['layout_sha256'] for r in records})
    families = sorted({r['family'] for r in records})
    audit = {f: len({r['layout_sha256'] for r in records if r['family'] == f}) for f in families}
    if len(layouts) < 30 or min(audit.values()) <= 1:
        return None, dict(clusters=len(layouts), per_family=audit, inferential_intervals=False)
    rng = np.random.default_rng(1404001)
    indices = np.array([layouts.index(r['layout_sha256']) for r in records])
    family_indices = [np.array([i for i, r in enumerate(records) if r['family'] == f]) for f in families]
    weights = []
    rejected = attempts = 0
    while len(weights) < 10000 and attempts < 100000:
        attempts += 1
        counts = np.bincount(rng.integers(len(layouts), size=len(layouts)), minlength=len(layouts))[indices].astype(float)
        denominators = [counts[ix].sum() for ix in family_indices]
        if min(denominators) == 0:
            rejected += 1
            continue
        for ix, denominator in zip(family_indices, denominators):
            counts[ix] /= denominator * len(families)
        weights.append(counts)
    eligible = len(weights) == 10000
    return (np.array(weights) if eligible else None), dict(
        clusters=len(layouts), per_family=audit, inferential_intervals=eligible,
        seed=1404001, requested_replicates=10000, accepted=len(weights),
        rejected_missing_family=rejected, attempts=attempts,
        unit='global layout hash; shared layouts across families resampled together')


def analyze():
    begin = perf_counter()
    manifest, lock = load_inputs(ROOT)
    records = manifest['records']
    expected = {j['episode_id']: j for j in jobs(manifest, lock)}
    rows = {}
    for line in (COMPACT / 'episodes.jsonl').read_text().splitlines():
        row = json.loads(line)
        key = row['episode_id']
        assert key not in rows and key in expected
        assert {k: row[k] for k in expected[key]} == expected[key]
        rows[key] = row
    assert set(rows) == set(expected)
    storage = json.loads((COMPACT / 'trace_storage_manifest.json').read_text())
    raw = Path(storage['storage_root'])
    assert {p.name for p in (raw / 'episodes').iterdir()} == {k+'.json.gz' for k in expected}
    entries = storage['episodes']
    assert len(entries) == len({e['episode_id'] for e in entries}) == 13440
    scenarios = {r['environment_sha256']: Scenario.from_dict(r['scenario']) for r in records}
    calibration = defaultdict(lambda: np.zeros((2, 5, 4)))
    signatures = {}
    dv_requests = dv_decisions = dv_extra = 0
    uncompressed = 0
    metric_checks = 0
    for index, entry in enumerate(entries):
        key = entry['episode_id']
        path = raw / entry['path']
        assert path.resolve() == (raw / 'episodes' / (key+'.json.gz')).resolve()
        assert path.stat().st_size == entry['compressed_bytes'] and file_sha256(path) == entry['sha256']
        with gzip.open(path, 'rb') as stream:
            data = stream.read()
        uncompressed += len(data)
        bundle = json.loads(data)
        assert bundle['job'] == expected[key] and bundle['run_id'] == storage['run_id']
        result = bundle['result']
        assert result['metrics'] == rows[key]['metrics']
        m = result['metrics']
        j = expected[key]
        assert m['purpose'] == 'assessment' and m['replicate'] == j['replicate']
        assert m['method'] == j['method'] and m['seed'] == j['seed'] and m['max_observations'] == j['cap']
        assert m['policy_parameters'] == j['parameters'] and m['ablation'] is None
        metric_checks += verify_trace(bundle, scenarios[j['environment_sha256']])
        samples = result['feasibility_samples']
        if samples:
            brier = sum((s['probability']-s['visible'])**2 for s in samples)/len(samples)
            mae = sum(abs(s['probability']-s['visible']) for s in samples)/len(samples)
            assert abs(brier-m['feasibility']['brier']) < 1e-12
            assert abs(mae-m['feasibility']['mae']) < 1e-12
        assert len(samples) == m['feasibility']['samples']
        group = (j['method'], j['cap'], j['noise'], j['environment_sha256'], j['replicate'])
        for s in samples:
            bucket = min(4, int(5*s['probability']))
            calibration[group][int(s['unknown_blocker']), bucket] += [1, s['probability'], s['visible'], (s['probability']-s['visible'])**2]
        frames = result['frames']
        if j['method'] in ('static', 'disruption-visible'):
            trajectory = [dict(position=f['position'], planned=f['planned'], executed=f['executed'],
                               memory=f['memory'], received_observation=f['received_observation']) for f in frames]
            signature = hashlib.sha256(canonical_bytes(trajectory)).hexdigest()
            signatures[(j['environment_sha256'], j['cap'], j['noise'], j['method'])] = signature
        if j['method'] == 'disruption-visible':
            dv_decisions += len(frames)-1
            dv_requests += sum(f['observation_requested'] for f in frames[1:])
            dv_extra += m['observation_count']-1
        if (index+1) % 1000 == 0:
            print(f'Independently verified {index+1}/13440 traces', flush=True)
    # Average random replicates before any comparisons or summaries.
    cells = defaultdict(list)
    for row in rows.values():
        cells[(row['environment_sha256'], row['method'], row['cap'], row['noise'])].append(row['metrics'])
    means = {}
    for key, values in cells.items():
        assert len(values) == (5 if key[1] == 'random-quota' else 1)
        means[key] = {k: float(np.mean([m[k] for m in values if m[k] is not None]))
                      if any(m[k] is not None for m in values) else None for k in OUTCOMES}
    families = sorted({r['family'] for r in records})
    def family_mean(method, cap, noise, outcome, family=None):
        return float(np.mean([means[(r['environment_sha256'], method, cap, noise)][outcome]
                              for r in records if family is None or r['family'] == family]))
    tables = []
    per_family = []
    for method in METHODS:
        for cap in CAPS:
            for noise in (0., .05):
                table = dict(method=method, cap='unlimited' if cap is None else cap, noise=noise)
                table.update({k: float(np.mean([family_mean(method, cap, noise, k, f) for f in families])) for k in OUTCOMES})
                tables.append(table)
                for f in families:
                    per_family.append(dict(method=method, cap=table['cap'], noise=noise, family=f,
                                           **{k: family_mean(method, cap, noise, k, f) for k in OUTCOMES}))
    write_csv('comparison.csv', tables)
    write_csv('per_family.csv', per_family)
    ranking = sorted([dict(method=m, **{k: float(np.mean([t[k] for t in tables if t['method'] == m])) for k in OUTCOMES})
                      for m in METHODS], key=lambda x: (-x['contact_free_success'], x['method']))
    write_csv('ranking.csv', ranking)
    weights, audit = bootstrap_weights(records)
    write_json('layout_cluster_audit.json', dict(**audit, records=[{k:r[k] for k in ('family','seed','environment_sha256','layout_sha256')} for r in records]))
    contrasts = []
    for comparator in METHODS:
        if comparator == 'disruption-visible':
            continue
        for cap in CAPS:
            for noise in (0., .05):
                for outcome in OUTCOMES[:4]:
                    differences = np.array([means[(r['environment_sha256'], 'disruption-visible', cap, noise)][outcome]
                                            - means[(r['environment_sha256'], comparator, cap, noise)][outcome] for r in records])
                    family_diffs = {f: float(np.mean([d for d,r in zip(differences, records) if r['family']==f])) for f in families}
                    estimate = float(np.mean(list(family_diffs.values())))
                    c = dict(comparator=comparator, cap='unlimited' if cap is None else cap,
                             noise=noise, outcome=outcome, difference=estimate,
                             confirmatory=comparator=='route-weighted' and cap==4 and noise==0 and outcome=='contact_free_success',
                             family_differences=family_diffs,
                             leave_one_family_out={f: float(np.mean([v for g,v in family_diffs.items() if g != f])) for f in families})
                    if weights is not None:
                        samples = weights @ differences
                        c.update(ci95=list(np.quantile(samples, [.025,.975])),
                                 bootstrap_unique_statistics=len(np.unique(samples)),
                                 bootstrap_degenerate=bool(np.ptp(samples)==0))
                    contrasts.append(c)
    write_json('paired_contrasts.json', contrasts)
    primary = next(c for c in contrasts if c['confirmatory'])
    # Calibration is descriptive sensed-only, pooled rays plus environment-level scores.
    bins = []
    env_calibration = []
    pooled = defaultdict(lambda: np.zeros((2,5,4)))
    for (method, cap, noise, env, replicate), values in calibration.items():
        pooled[(method, cap, noise)] += values
        count = values[:,:,0].sum()
        env_calibration.append(dict(method=method, cap='unlimited' if cap is None else cap, noise=noise,
                                    environment_sha256=env, replicate=replicate, samples=int(count),
                                    brier=values[:,:,3].sum()/count))
    for (method,cap,noise),values in pooled.items():
        for blocker in range(2):
            for b in range(5):
                n,p,v,sq = values[blocker,b]
                if n:
                    bins.append(dict(method=method,cap='unlimited' if cap is None else cap,noise=noise,
                                     blocker='unknown' if blocker else 'all_known', bin=b,
                                     samples=int(n),mean_prediction=p/n,fraction_visible=v/n,brier=sq/n))
    write_csv('feasibility_calibration.csv', bins)
    write_csv('feasibility_per_environment.csv', env_calibration)
    feasibility = []
    for method in METHODS:
        for cap in CAPS:
            for noise in (0., .05):
                selected = [r['metrics']['feasibility'] for r in rows.values() if r['method']==method and r['cap']==cap and r['noise']==noise]
                n = sum(m['samples'] for m in selected)
                feasibility.append(dict(method=method, cap='unlimited' if cap is None else cap, noise=noise, samples=n,
                                        brier=sum(m['brier']*m['samples'] for m in selected if m['samples'])/n if n else None,
                                        mae=sum(m['mae']*m['samples'] for m in selected if m['samples'])/n if n else None))
    write_csv('feasibility_summary.csv', feasibility)
    static_differences = []
    scientific_keys = [k for k in OUTCOMES if 'seconds' not in k and 'latency' not in k and 'astar' not in k and 'planner' not in k]
    for r in records:
        env = r['environment_sha256']
        for cap in CAPS:
            for noise in (0.,.05):
                a = means[(env,'disruption-visible',cap,noise)]
                b = means[(env,'static',cap,noise)]
                static_differences.append(dict(environment_sha256=env, cap=cap, noise=noise,
                    trajectory_equal=signatures[(env,cap,noise,'static')]==signatures[(env,cap,noise,'disruption-visible')],
                    differing_metrics={k:[a[k],b[k]] for k in scientific_keys if a[k]!=b[k]}))
    diagnostics = dict(episodes=840, noninitial_observations=dv_extra, triggered_requests=dv_requests,
                       decisions=dv_decisions, request_fraction=dv_requests/max(1,dv_decisions),
                       matching_static_trajectories=sum(d['trajectory_equal'] for d in static_differences),
                       differing_static_metric_pairs=sum(bool(d['differing_metrics']) for d in static_differences),
                       pairs=static_differences)
    write_json('disruption_static_diagnostics.json', diagnostics)
    for outcome, label in (('contact_free_success','Contact-free goal completion'),('success','Goal completion')):
        fig, axes = plt.subplots(1,2,figsize=(14,6),sharey=True)
        for ax, noise in zip(axes,(0.,.05)):
            for method in METHODS:
                selected = [next(t for t in tables if t['method']==method and t['cap']==('unlimited' if cap is None else cap) and t['noise']==noise) for cap in CAPS]
                ax.plot([t['observation_cost'] for t in selected],[t[outcome] for t in selected],marker='.',label=method)
            ax.set(xlabel='Mean observation cost',ylabel=label,title=f'Noise {noise:g}',ylim=(0,1))
            ax.grid(alpha=.2)
        axes[-1].legend(bbox_to_anchor=(1.02,1),loc='upper left',fontsize=8)
        fig.tight_layout()
        fig.savefig(COMPACT / (outcome+'_cost.png'),dpi=160)
        plt.close(fig)
    sessions = [json.loads(p.read_text()) for p in sorted(raw.glob('session-*.json'))]
    assert sum(s['executed_this_session'] for s in sessions) == 13440
    report = dict(episodes=13440, unique_environments=70, complete_matrix=True, duplicate_records=0,
                  missing_records=0, trace_checksums_verified=13440, recomputed_metric_checks=metric_checks,
                  parameter_lock_sha256=file_sha256(ROOT/'results/phase1_4b/parameter_lock.json'),
                  primary_contrast=primary, ranking=ranking,
                  storage_root=raw.as_posix(), compressed_bytes=storage['compressed_bytes'],
                  uncompressed_json_bytes=uncompressed, sessions=sessions,
                  independent_verification_analysis_seconds=perf_counter()-begin,
                  scope='Saved traces only; no policies executed. Runtime counters and scientific ledgers checked; no parameter selection.',
                  limitations=['Sensed-only calibration selection bias; rays are not independent samples.',
                               'Fixed families, related layouts, last-write memory, zero sensor latency.',
                               'Random replicas averaged within environment; executions are not independent samples.',
                               'Secondary intervals are descriptive pointwise intervals; ranking averages all prespecified caps and sensors.'])
    assert report['parameter_lock_sha256'] == LOCK_SHA256
    write_json('independent_verification.json', report)
    print(json.dumps(dict(episodes=13440, primary=primary, seconds=perf_counter()-begin)),flush=True)


if __name__ == '__main__':
    analyze()
