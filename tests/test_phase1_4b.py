"""Tuning-only gates, atomic storage recovery, and exact selection (synthetic data)."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import numpy as np
import pytest
from spatial_memory.tuning_spec import (load_tuning_manifest,candidates,jobs,GRID,MANIFEST_SHA256,
                                      EPISODE_CONFIG,file_sha256)
from spatial_memory.tuning_store import (checkpoint,read_bundle,inventory,recover_staging,canonical_bytes,
                                        atomic_bytes,writer_lease)
from spatial_memory.tuning_selection import select_parameters
from spatial_memory.protocol_evaluation import run_protocol_episode
from spatial_memory.robustness import generate_robustness
ROOT=Path(__file__).resolve().parents[1]


def test_exact_pinned_manifest_and_grid_and_no_assessment_read(monkeypatch,tmp_path):
    m=load_tuning_manifest(ROOT)
    assert len(m['records'])==35
    assert len(jobs(m))==3780
    assert len(candidates())==36
    assert all(len([c for c in candidates() if c['method']==method])==9 for method in GRID)
    original=Path.read_text
    def watch(path,*a,**kw):
        assert 'assessment' not in path.name and 'held_out' not in path.name
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'read_text',watch)
    for path in (ROOT/'results/phase1_4a/manifests/assessment.json',ROOT/'configs/held_out.json',tmp_path/'tuning.json'):
        with pytest.raises(ValueError,match='pinned tuning'):
            load_tuning_manifest(ROOT,path)


def synthetic_bundle():
    s=generate_robustness('detour',6102)
    m,frames,samples=run_protocol_episode(s,{**EPISODE_CONFIG,'max_observations':2},'fixed-rate',6102)
    # Storage contract fixture uses development smoke mechanics, never a real tuning environment.
    m['purpose']='tuning'
    job=dict(episode_id='synthetic',method='fixed-rate',seed=6102,cap=2,parameters=m['policy_parameters'])
    return job,dict(metrics=m,frames=frames,feasibility_samples=samples)


def test_checkpoint_exact_resume_missing_duplicate_and_corruption(tmp_path):
    job,result=synthetic_bundle();expected={job['episode_id']:job}
    with writer_lease(tmp_path):
        path=checkpoint(tmp_path,job,result,'test')
        before=file_sha256(path)
        rows,index,missing=inventory(tmp_path,expected,'test',require_complete=True)
        assert len(rows)==1 and missing==[] and index[0]['sha256']==before
        assert file_sha256(path)==before
        with pytest.raises(ValueError,match='Duplicate'):
            checkpoint(tmp_path,job,result,'test')
        duplicate=path.with_name('duplicate.json.gz');duplicate.write_bytes(path.read_bytes())
        with pytest.raises(ValueError,match='Duplicate'):
            inventory(tmp_path,expected,'test')
        duplicate.unlink()
        with pytest.raises(ValueError,match='Missing'):
            inventory(tmp_path,{**expected,'missing':{}},'test',require_complete=True)
        with pytest.raises(ValueError,match='Conflicting'):
            inventory(tmp_path,expected,'different-run')
    with writer_lease(tmp_path):
        with pytest.raises(ValueError,match='writer'):
            with writer_lease(tmp_path):
                pass


def test_recovery_adopts_complete_and_preserves_torn_checkpoint(tmp_path):
    job,result=synthetic_bundle()
    path=checkpoint(tmp_path,job,result,'test')
    pending=tmp_path/'staging'/'complete.part';path.rename(pending)
    actions=recover_staging(tmp_path,{job['episode_id']:job},'test')
    assert 'adopted' in actions[0]['reason'] and path.exists()
    (tmp_path/'staging'/'torn.part').write_bytes(b'partial trace')
    recover_staging(tmp_path,{job['episode_id']:job},'test')
    assert (tmp_path/'quarantine/torn.part').read_bytes()==b'partial trace'
    assert json.loads((tmp_path/'quarantine/torn.part.json').read_text())['bytes']==13


def test_atomic_immutable_lock_refuses_changes(tmp_path):
    path=tmp_path/'lock.json'
    atomic_bytes(path,b'original',immutable=True)
    atomic_bytes(path,b'original',immutable=True)
    with pytest.raises(ValueError,match='Immutable'):
        atomic_bytes(path,b'changed',immutable=True)
    assert path.read_bytes()==b'original'


def selection_rows():
    result=[]
    for c in candidates():
        for family in range(7):
            for cap in (2,4,8):
                for environment in range(5):
                    result.append(dict(method=c['method'],candidate=c['candidate'],family=str(family),cap=cap,
                        metrics=dict(contact_free_success=True,success=True,observation_count=2,elapsed_steps=8)))
    return result


def test_exact_equal_weight_selection_and_lexicographic_tie():
    rows=selection_rows();picked=select_parameters(rows)
    assert all(r['candidate']==0 for r in picked['selected'].values())
    # A single contact-free failure outranks all observation/time improvements.
    rows[0]['metrics']['contact_free_success']=False
    rows[1]['metrics']['observation_count']=1
    picked=select_parameters(rows)
    assert picked['selected']['fixed-rate']['candidate']==1
    assert picked['candidates'][0]['exact_means']['contact_free_success']==[104,105]
    with pytest.raises(ValueError,match='Incomplete'):
        select_parameters(rows[:-1])


@pytest.mark.parametrize('metric',['success','observation_count','elapsed_steps'])
def test_secondary_selection_tie_break_order(metric):
    rows=selection_rows()
    for r in rows:
        if r['method']=='fixed-rate' and r['candidate']==1:
            r['metrics'][metric]=2 if metric=='success' else (1 if metric=='observation_count' else 7)
    # Nonbinary synthetic success=2 tests ordering algebra only, not valid episode data.
    picked=select_parameters(rows)
    assert picked['selected']['fixed-rate']['candidate']==1
