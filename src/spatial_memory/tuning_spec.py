"""Frozen Phase 1.4B grid and pinned tuning-only input validation."""
from collections import Counter
from dataclasses import asdict
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess
from .manifests import validate_manifest,digest,environment_hash
from .simulation import Scenario
from .task_policies import PolicyParameters

BASE_COMMIT='46253fe14b1e980031f75bea7e4338d45f3a1955'
MANIFEST_RELATIVE='results/phase1_4a/manifests/tuning.json'
MANIFEST_SHA256='99ba8664625cbcadcf8450a9f96558e122c6ecbc4b71c77f7676ec29d0625a45'
GRID={
    'fixed-rate':(('fixed_rate',(.01,.05,.15)),('entropy_threshold',(.65,.75,.85))),
    'route-weighted':(('route_weight',(1,3,9)),('route_threshold',(.65,.75,.85))),
    'disruption-visible':(('disruption_threshold',(.025,.1,.4)),('budget_price',(0,.1,.4))),
    'query-gate-conceptual':(('reliability_threshold',(.8,.9,.97)),('visibility_fraction',(.25,.5,.75)))}
CAPS=(2,4,8)
EPISODE_CONFIG=dict(max_steps=40,update_interval=2,observation_cost=1.5,unknown='optimistic',
    common_horizon_metrics=True,sensor=dict(radius=3,occlusion=True,noise=0.0))
SELECTION_VERSION='phase1.4b-equal-family-cap-lex-v1'


def file_sha256(path):
    sha=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            sha.update(chunk)
    return sha.hexdigest()


def candidates():
    result=[]
    for method,axes in GRID.items():
        for index,values in enumerate(product(*(axis[1] for axis in axes))):
            tuned=dict(zip((axis[0] for axis in axes),values))
            parameters={**asdict(PolicyParameters()),**tuned}
            result.append(dict(method=method,candidate=index,parameter_tuple=list(values),
                               tuned_parameters=tuned,parameters=parameters))
    return result


def load_tuning_manifest(root,path=None):
    root=Path(root).resolve();expected=(root/MANIFEST_RELATIVE).resolve()
    path=expected if path is None else Path(path).resolve()
    # Reject other files before opening; in particular never read assessment inputs.
    if path!=expected:
        raise ValueError('Only the existing pinned tuning manifest is accepted')
    if file_sha256(path)!=MANIFEST_SHA256:
        raise ValueError('Frozen tuning manifest hash mismatch')
    manifest=json.loads(path.read_text())
    if manifest['partition']!='tuning' or manifest['outcomes_generated'] is not False:
        raise ValueError('Expected policy-free tuning manifest')
    if len(validate_manifest(manifest))!=35 or set(Counter(r['family'] for r in manifest['records']).values())!={5}:
        raise ValueError('Require 35 unique environments, five per family')
    provenance=manifest['provenance']
    if digest(provenance['config'])!=provenance['config_sha256']:
        raise ValueError('Baseline configuration hash mismatch')
    stored=provenance['source_files_sha256']
    if hashlib.sha256(json.dumps(stored,sort_keys=True).encode()).hexdigest()!=provenance['source_sha256']:
        raise ValueError('Baseline source manifest mismatch')
    for name,sha in stored.items():
        # The guard-only adapter refactor is recorded separately in current provenance.
        if name=='src/spatial_memory/protocol_evaluation.py':
            raw=subprocess.check_output(['git','show',BASE_COMMIT+':'+name],cwd=root)
        else:
            raw=(root/name).read_bytes()
        if hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()!=sha:
            raise ValueError('Frozen policy/source changed: '+name)
    return manifest


def jobs(manifest):
    result=[]
    for candidate in candidates():
        for record in manifest['records']:
            for cap in CAPS:
                job={**candidate,'environment_sha256':record['environment_sha256'],
                     'layout_sha256':record['layout_sha256'],'family':record['family'],
                     'seed':record['seed'],'cap':cap}
                result.append({'episode_id':digest(job),**job})
    if len(result)!=3780 or len({j['episode_id'] for j in result})!=3780:
        raise ValueError('Incomplete/conflicting frozen job matrix')
    return result


def execute_tuning_job(job,record):
    from .protocol_evaluation import _run_instrumented_episode
    if record['partition']!='tuning' or not 10000<=record['seed']<20000:
        raise ValueError('Only tuning records accepted')
    scenario=Scenario.from_dict(record['scenario'])
    if (scenario.split!='development' or record['seed']!=job['seed']
        or environment_hash(scenario)!=job['environment_sha256']):
        raise ValueError('Job/realization mismatch')
    candidate=next((c for c in candidates() if c['method']==job['method'] and c['candidate']==job['candidate']),None)
    if candidate is None or job['parameters']!=candidate['parameters'] or job['cap'] not in CAPS:
        raise ValueError('Nonfrozen tuning configuration')
    cfg={**EPISODE_CONFIG,'max_observations':job['cap']}
    metrics,frames,samples=_run_instrumented_episode(scenario,cfg,job['method'],job['seed'],
        parameters=job['parameters'],purpose='tuning')
    return dict(metrics=metrics,frames=frames,feasibility_samples=samples)
