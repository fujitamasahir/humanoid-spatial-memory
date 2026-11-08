"""Chained-lock continuation: scripted fixtures only, no registered RNG."""
import gzip,hashlib,json
from copy import deepcopy
import pytest
from spatial_memory import phase15_bprime as bp,phase15_generators as old
from spatial_memory.phase15_bprime_access import StageBinding,packed,sha
from spatial_memory.phase15_bprime_prefix import ReadOnlyPrefix
from spatial_memory.phase15_bprime_coordinator import Coordinator
from test_phase1_5_bprime import Oracle
from test_phase1_5_bprime_hardening import setup_coordinator,Builder
from bprime_test_support import binding_for,toy_store

@pytest.fixture(autouse=True)
def prohibit_registered(monkeypatch):
    def deny(*a,**k):pytest.fail('Registered execution prohibited')
    monkeypatch.setattr(bp.Stream,'__init__',deny);monkeypatch.setattr(old.Stream,'__init__',deny)
    monkeypatch.setattr(bp,'geometry',deny);monkeypatch.setattr(old,'geometry',deny)


def setup(tmp_path):
    original,refs,c=setup_coordinator(tmp_path)
    first=Builder()
    with original.writer():c.execute_one(first)
    original_bytes={p.relative_to(original.root).as_posix():p.read_bytes() for p in original.root.rglob('*') if p.is_file()}
    descriptor=dict(schema=1,partition='fit',root='store',original_binding=str(original.binding.manifest_path.relative_to(tmp_path)),original_binding_sha256=original.binding.approved_sha256,
        source_commit='synthetic-fixture',run_id=original.run_id,records=1,files=[dict(path=n,bytes=len(v),sha256=sha(v)) for n,v in sorted(original_bytes.items())])
    path=tmp_path/'prefix.json';path.write_bytes(packed(descriptor))
    inv=json.loads(original.binding.read(original.binding.root/'store.approval/references.json'));ledger=json.loads(original.binding.read(original.binding.root/'store.approval/ledger.json'))
    draft=binding_for(tmp_path/'continuation',inventory=inv,ledger=ledger)
    value=json.loads(draft.manifest_bytes);value['readonly_prefix_root']='store';value['continuation_prefix']=dict(path='prefix.json',sha256=sha(path.read_bytes()))
    value['files']['references']['prefix.json']=sha(path.read_bytes())
    value['files']['references'][descriptor['original_binding']]=descriptor['original_binding_sha256']
    draft.manifest_path.write_bytes(packed(value))
    binding=StageBinding.load(draft.manifest_path,approved_sha256=sha(packed(value)),synthetic=True)
    prefix=ReadOnlyPrefix.load(binding,backend=Oracle());store=toy_store(tmp_path/'continuation',binding=binding,backend=Oracle())
    return original,original_bytes,refs,store,prefix


def test_continuation_retains_prefix_credits_and_next_identity(tmp_path):
    original,snapshot,refs,store,prefix=setup(tmp_path)
    c=Coordinator(store,refs,backend=Oracle(),synthetic=True,prefix=prefix);builder=Builder()
    with store.writer():
        rows=c.restore();assert len(rows)==1 and c.sequence==1 and c.index.credits('synthetic-fit')=={'R':1}
        entry=c.execute_one(builder);body=json.loads(gzip.decompress((store.root/entry['path']).read_bytes()))
        assert body['run_id']==store.run_id!=original.run_id
        assert body['payload']['identity']=='synthetic:fit:BP:0' and body['payload']['sequence']==1
        restarted=Coordinator(store,refs,backend=Oracle(),synthetic=True,prefix=prefix);rows=restarted.restore()
        assert len(rows)==2 and restarted.sequence==2 and restarted.index.credits('synthetic-fit')=={'R':1}
    assert builder.geometry_calls==1 and builder.world_calls==0
    assert snapshot=={p.relative_to(original.root).as_posix():p.read_bytes() for p in original.root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('kind',['delete','change','lock','receipt','extra'])
def test_changed_original_prefix_stops_before_next_builder(tmp_path,kind):
    original,snapshot,refs,store,prefix=setup(tmp_path);c=Coordinator(store,refs,backend=Oracle(),synthetic=True,prefix=prefix);builder=Builder()
    with store.writer():
        c.restore()
        target=next((original.root/'records').iterdir())
        if kind=='delete':target.unlink()
        elif kind=='change':target.write_bytes(b'conflicting checkpoint')
        elif kind=='lock':(original.root/'run.json').write_bytes(b'conflicting lock')
        elif kind=='receipt':next((original.root/'recovered').iterdir()).write_bytes(b'conflicting receipt')
        else:(original.root/'unexpected').write_bytes(b'conflicting input')
        with pytest.raises(bp.IntegrityError):c.execute_one(builder)
    assert builder.geometry_calls==0


def test_declared_prefix_cannot_be_omitted(tmp_path):
    _,_,refs,store,_=setup(tmp_path)
    with pytest.raises(bp.IntegrityError,match='requires its verified'):
        Coordinator(store,refs,backend=Oracle(),synthetic=True)


@pytest.mark.parametrize('boundary',['after_stage_fsync','after_link','after_destination_fsync','after_stage_unlink','after_stage_dir_fsync'])
def test_recovery_and_continuation_across_chained_epoch(tmp_path,boundary):
    original,snapshot,refs,store,prefix=setup(tmp_path);fired=[]
    def crash(point,path):
        if path.name.endswith('.json.gz') and point==boundary and not fired:fired.append(point);raise OSError('scripted epoch crash')
    store.fault=crash;c=Coordinator(store,refs,backend=Oracle(),synthetic=True,prefix=prefix);first=Builder()
    with pytest.raises(OSError):
        with store.writer():c.execute_one(first)
    store.fault=lambda *a:None
    restart=Coordinator(store,refs,backend=Oracle(),synthetic=True,prefix=prefix);second=Builder()
    with store.writer():
        rows=restart.restore();assert len(rows)==2 and restart.sequence==2
        restart.execute_one(second)
        assert restart.sequence==3
        assert [p['sequence'] for _,p in sorted(restart._scan(),key=lambda row:row[1]['sequence'])]==[0,1,2]
    assert first.geometry_calls==1 and second.geometry_calls==1
    assert snapshot=={p.relative_to(original.root).as_posix():p.read_bytes() for p in original.root.rglob('*') if p.is_file()}


def test_new_binding_cannot_open_original_prefix_for_writing(tmp_path):
    original,_,_,store,_=setup(tmp_path)
    with pytest.raises(bp.IntegrityError,match='not in approved manifest'):
        toy_store(original.root,binding=store.binding,backend=Oracle())
