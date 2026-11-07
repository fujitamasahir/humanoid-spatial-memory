"""Frozen matrix gates, independent ledgers and POSIX recovery on synthetic data."""
from copy import deepcopy
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import sys
import pytest

from spatial_memory.ablation_spec import (load_frozen,jobs,execute_job,make_job,
    PARAMETERS,FROZEN_ABLATIONS)
from spatial_memory.ablation_store import (checkpoint,inventory,recover_staging,
    writer_lease,canonical_bytes)
from spatial_memory.protocol_evaluation import run_protocol_episode
from spatial_memory.robustness import generate_robustness
from spatial_memory.tuning_spec import EPISODE_CONFIG,file_sha256

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_frozen_ablations import verify_decisions,verify_trace,expected_jobs


def synthetic(ablation='no-route-disruption'):
    scenario=generate_robustness('detour',6102)
    m,fs,samples=run_protocol_episode(scenario,{**EPISODE_CONFIG,'max_observations':4},
        'disruption-visible',6102,parameters=PARAMETERS,ablation=ablation)
    m['purpose']='assessment'
    job=dict(episode_id='synthetic',method='disruption-visible',seed=6102,cap=4,
             replicate=0,parameters=PARAMETERS,ablation=ablation)
    return scenario,job,dict(metrics=m,frames=fs,feasibility_samples=samples)


def test_matrix_matches_independent_plan_and_rejects_alternate_paths(tmp_path):
    manifest,lock=load_frozen(ROOT)
    plan=jobs(manifest)
    assert len(plan)==len({j['episode_id'] for j in plan})==1680
    assert {j['episode_id']:j for j in plan}==expected_jobs(manifest)
    assert all(sum(j['ablation']==a for j in plan)==280 for a in FROZEN_ABLATIONS)
    assert lock['selected']['disruption-visible']['parameters']==PARAMETERS
    for path in (tmp_path/'assessment.json',ROOT/'configs/held_out.json',ROOT/'results/phase1_4a/manifests/tuning.json'):
        with pytest.raises(ValueError,match='pinned assessment'):
            load_frozen(ROOT,path)


def test_adapter_rejects_changed_jobs_before_episode_execution(monkeypatch):
    manifest,_=load_frozen(ROOT);record=manifest['records'][0]
    def forbidden(*args,**kwargs):
        pytest.fail('Unexpected real episode execution')
    monkeypatch.setattr('spatial_memory.protocol_evaluation._run_instrumented_episode',forbidden)
    job=make_job(record,4,0.,'fixed-rate')
    for field,value in [('cap',2),('noise',.1),('ablation','invented'),('seed',10000),('parameters',{})]:
        changed={**job,field:value}
        with pytest.raises(ValueError):
            execute_job(changed,record)
    changed=deepcopy(job);changed['configuration']['sensor']['radius']=4
    with pytest.raises(ValueError):
        execute_job(changed,record)
    held=deepcopy(record);held['scenario']['split']='held_out'
    with pytest.raises(ValueError):
        execute_job(job,held)


@pytest.mark.parametrize('ablation',FROZEN_ABLATIONS)
def test_independent_reconstruction_and_tamper_detection(ablation):
    scenario,job,result=synthetic(ablation)
    bundle=json.loads(canonical_bytes(dict(job=job,result=result,run_id='test')))
    assert verify_trace(bundle,scenario)>=20
    assert verify_decisions(bundle)
    bundle['result']['frames'][1]['observation_score']+=.5
    with pytest.raises(AssertionError):
        verify_decisions(bundle)


def test_checksum_receipt_and_duplicate_detection(tmp_path):
    _,job,result=synthetic()
    with writer_lease(tmp_path):
        with pytest.raises(ValueError,match='writer'):
            with writer_lease(tmp_path):
                pass
        path=checkpoint(tmp_path,job,result,'test')
        rows,entries,missing=inventory(tmp_path,{'synthetic':job},'test',require_complete=True)
        assert len(rows)==1 and not missing
        with pytest.raises(ValueError,match='Duplicate'):
            checkpoint(tmp_path,job,result,'test')
        assert file_sha256(path)==entries[0]['sha256']
        # Gzip's timestamp does not affect decoded data, but must fail the byte receipt.
        data=bytearray(path.read_bytes());data[4]=1;path.write_bytes(data)
        with pytest.raises(ValueError,match='checksum'):
            inventory(tmp_path,{'synthetic':job},'test')


def test_stage_and_missing_receipt_recovery_without_reexecution(tmp_path):
    _,job,result=synthetic()
    root=tmp_path/'complete';(root/'staging').mkdir(parents=True)
    with gzip.open(root/'staging/synthetic.complete.part','wb') as stream:
        stream.write(canonical_bytes(dict(job=job,result=result,run_id='test')))
    actions=recover_staging(root,{'synthetic':job},'test')
    assert len(actions)==1
    assert len(inventory(root,{'synthetic':job},'test',require_complete=True)[0])==1
    # Simulate a crash after trace publication but before receipt publication.
    (root/'receipts/synthetic.json').chmod(0o644)
    (root/'receipts/synthetic.json').unlink()
    assert len(recover_staging(root,{'synthetic':job},'test'))==1
    assert not inventory(root,{'synthetic':job},'test',require_complete=True)[2]


def test_torn_checkpoint_preserved_and_conflicting_ablation_rejected(tmp_path):
    _,job,result=synthetic()
    result['metrics']['ablation']='fixed-rate'
    with pytest.raises(ValueError,match='configuration'):
        checkpoint(tmp_path,job,result,'test')
    stage=tmp_path/'staging';stage.mkdir(exist_ok=True)
    partial=stage/'synthetic.broken.part';partial.write_bytes(b'partial gzip')
    h=file_sha256(partial)
    actions=recover_staging(tmp_path,{'synthetic':job},'test')
    assert len(actions)==1
    assert file_sha256(tmp_path/'quarantine/synthetic.broken.part')==h
    assert inventory(tmp_path,{'synthetic':job},'test')[2]==['synthetic']


def test_runner_json_roundtrip_and_zero_reexecution_resume(monkeypatch,tmp_path):
    import run_frozen_ablations as runner
    _,job,result=synthetic()
    job.update(environment_sha256='synthetic-env',configuration={**EPISODE_CONFIG,'max_observations':4})
    second={**job,'episode_id':'synthetic-second'}
    manifest=dict(records=[dict(environment_sha256='synthetic-env')])
    audit=dict(parent_trace_checksums_verified=13440)
    monkeypatch.setattr(runner,'RAW',tmp_path/'raw')
    monkeypatch.setattr(runner,'COMPACT',tmp_path/'compact')
    monkeypatch.setattr(runner,'preflight',lambda *a,**kw:(manifest,audit.copy()))
    monkeypatch.setattr(runner,'jobs',lambda m:[job,second])
    monkeypatch.setattr(runner,'provenance',lambda *a,**kw:dict(source_sha256='synthetic-source',
        python='synthetic-python',platform='synthetic-platform',packages={}))
    calls=[]
    def execute(j,r):
        calls.append(j['episode_id'])
        return deepcopy(result)
    monkeypatch.setattr(runner,'execute_job',execute)
    first=runner.run(1)
    h=file_sha256(tmp_path/'raw/episodes/synthetic.json.gz')
    zero=runner.run(0)
    final=runner.run(1)
    assert first['executed_this_session']==1 and zero['executed_this_session']==0
    assert final['already_completed']==1 and calls==['synthetic','synthetic-second']
    assert file_sha256(tmp_path/'raw/episodes/synthetic.json.gz')==h
