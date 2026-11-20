"""Prepare/freeze and once-only public-memory DAO mechanism execution.

Intentionally has no navigation/population-generation command or simulator import.
"""
from __future__ import annotations
import json, subprocess, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import write, sha, manifest, verify_manifest, commit
from spatial_memory.discovery_observation import (assess, predicted_footprints,
    request_rule, DiscoveryController, MODES, DAOParameters)
from spatial_memory.discovery_reference import footprint_reference, scalar_counts
from spatial_memory.evi import visible_cells
from dao_fixtures import fixtures
OUT=ROOT/'results/phase2_mujoco/dao_v1'
SOURCES=('src/spatial_memory/discovery_observation.py','src/spatial_memory/discovery_reference.py',
         'scripts/dao_fixtures.py','scripts/run_dao_synthetic.py','tests/test_discovery_observation.py','tests/test_dao_artifacts.py',
         'docs/dao_protocol.md','docs/dao_independent_navigation_protocol.md',
         'src/spatial_memory/evi.py','src/spatial_memory/memory.py','src/spatial_memory/scheduling.py',
         'src/spatial_memory/cadence_age.py','src/spatial_memory/change_aware_age.py')


def json_native(value):
    # Artifact boundary only: do not change arithmetic, counts or requests.
    return json.loads(json.dumps(value, default=lambda scalar: scalar.item()))


def fingerprints():return {p:sha(ROOT/p) for p in SOURCES}


def prepare():
    target=OUT/'prepared';target.mkdir(parents=True,exist_ok=False)
    write(target/'fixtures.json',fixtures())
    command=[sys.executable,'-m','pytest','-q','tests/test_discovery_observation.py',
        'tests/test_dao_artifacts.py','tests/test_change_aware_age.py','tests/test_caa_integration.py','tests/test_cadence_age.py',
        'tests/test_phase2_mujoco.py','tests/test_phase2_emergency_safety.py',
        'tests/test_persistence_evi_evaluation.py',f'--junitxml={target/"tests.xml"}']
    result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    (target/'tests.log').write_text(result.stdout+result.stderr)
    write(target/'correctness.json',{'command':command,'returncode':result.returncode,
        'status':'PASS' if result.returncode==0 else 'FAIL','source_sha256':fingerprints()})
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    manifest(target)
    write(OUT/'protocol_binding.json',{'source_sha256':fingerprints(),
       'fixtures_sha256':sha(target/'fixtures.json'),'prepared_manifest_sha256':sha(target/'artifact_manifest.json'),
       'starting_commit':'5cb40fce42e8791b1406245684be5d0df0964b93',
       'matrix':list(MODES),'formal_public_states':48,'formal_same_state_decisions':432,
       'navigation_runs_authorized':False})
    print(result.stdout)


def gate():
    binding=json.loads((OUT/'protocol_binding.json').read_text())
    assert binding['source_sha256']==fingerprints()
    assert sha(OUT/'prepared/fixtures.json')==binding['fixtures_sha256']
    assert sha(OUT/'prepared/artifact_manifest.json')==binding['prepared_manifest_sha256']
    verify_manifest(OUT/'prepared')
    assert json.loads((OUT/'prepared/correctness.json').read_text())['returncode']==0
    for p,h in {**binding['source_sha256'],
           'results/phase2_mujoco/dao_v1/protocol_binding.json':sha(OUT/'protocol_binding.json'),
           'results/phase2_mujoco/dao_v1/prepared/fixtures.json':binding['fixtures_sha256']}.items():
        raw=subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)
        import hashlib
        assert hashlib.sha256(raw).hexdigest()==h, f'Uncommitted prospective source/input: {p}'
    return binding


def formal():
    gate();target=OUT/'synthetic';target.mkdir(parents=True,exist_ok=False)
    states=json.loads((OUT/'prepared/fixtures.json').read_text());rows=[];failures=[];contract_count=0
    started=time.perf_counter();maximum=0;counts=Counter()
    for state in states:
        g=np.asarray(state['grid'],dtype=np.int8);t=np.asarray(state['last_observed'],dtype=np.int64)
        position=tuple(state['position']);step=state['step'];yaw=state['yaw'];route=state['route']
        try:
            saved=g.copy();start=time.perf_counter_ns()
            d=assess(g,t,step,position,yaw,route=route)
            elapsed=time.perf_counter_ns()-start
            footprints=predicted_footprints(g,position,yaw)
            reference=footprint_reference(g.tolist(),position,yaw)
            assert footprints['optimistic']==reference['optimistic']==visible_cells(g,position,yaw,
                range_m=6.,cell_size=.75,horizontal_fov_deg=120.)-{position}
            assert footprints['frontier']==reference['frontier']
            assert footprints['frontier']<=footprints['optimistic']
            for name in ('frontier','optimistic'):
                assert d[name]==scalar_counts(g.tolist(),t.tolist(),step,reference[name],route or ())
            assert np.array_equal(g,saved) and d['sample_visits']<=4941
            assert d['actual_sensor_calls']==d['plan_calls']==0
            maximum=max(maximum,d['sample_visits'])
            if state['family']=='explored':assert d['frontier']['new']==0
            if d['oldest_local_age']>=10:
                for mode in MODES[:4]:assert request_rule(d,step,step-state['last_scan_step'],mode)['requested']
            for mode in MODES:
                result=request_rule(d,step,step-state['last_scan_step'],mode)
                assert result==request_rule(d,step,step-state['last_scan_step'],mode)
                counts[f'{mode}_requests']+=int(result['requested'])
                rows.append({'id':state['id'],'family':state['family'],'mode':mode,'step':step,
                    'assessment_ns':elapsed,'detail':d,**result})
                # Exercise actual controller authorization; no sensor/scene exists.
                controller=DiscoveryController(g,mode=mode,max_observations=2)
                for now in range(1,21):
                    current_route=route if route and all(controller.memory.grid[c[1],c[0]]!=1 for c in route) else None
                    controller.set_navigation_context(goal=state['goal'],yaw=yaw,route=current_route)
                    decision=controller.decide(now,position)
                    if decision['observation_granted']:
                        observation=np.full(g.shape,-1,dtype=np.int8)
                        if state['followup']:
                            x,y=state['followup']['cell'];observation[y,x]=state['followup']['value']
                        controller.refresh(observation,now)
                        if state['followup']:assert controller.memory.grid[y,x]==state['followup']['value']
                    assert controller.used<=2
                assert controller.used==2 and controller.denied>0
                contract_count+=1
            if state['unknown_occluder_hypothesis']:
                # Evaluator-only 2D hypothetical blocker: never a production input.
                x,y=state['unknown_occluder_hypothesis'];hypothesis=g.copy();hypothesis[y,x]=1
                blocked=footprint_reference(hypothesis.tolist(),position,yaw)['optimistic']
                counts['occluder_hypotheses']+=1
                counts['occluder_lost_optimistic_cells']+=len(footprints['optimistic']-blocked)
        except Exception as exc:
            failures.append({'id':state['id'],'error':type(exc).__name__+': '+str(exc)})
    write(target/'decisions.json',json_native(rows))
    summary={'status':'PASS' if not failures else 'FAIL','source_freeze_commit':commit(),
        'source_sha256':fingerprints(),'states':len(states),'same_state_decisions':len(rows),
        'controller_contracts':contract_count,'failures':failures,'counts':dict(counts),
        'maximum_sample_visits':maximum,'bound_sample_visits':4941,
        'scheduler_astar_calls':0,'actual_sensor_calls':0,'navigation_episodes':0,
        'wall_seconds':time.perf_counter()-started,
        'assessment_ns_quantiles':np.quantile([r['assessment_ns'] for r in rows],[0,.5,.95,1]).tolist(),
        'caveat':'Public-raster geometric/rule conformance only; no physical visibility, calibrated information gain or navigation efficacy conclusion.'}
    write(target/'summary.json',summary);manifest(target);print(json.dumps(summary,indent=2))
    if failures:raise RuntimeError('Formal failures preserved; no automatic retuning/rerun')

if __name__=='__main__':
    {'prepare':prepare,'formal':formal}[sys.argv[1]]()
