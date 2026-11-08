"""Critical recovery continuation gate; only scripted synthetic fixtures."""
import pytest
from spatial_memory import phase15_bprime as bp,phase15_generators as old
from spatial_memory.phase15_bprime_coordinator import Coordinator
from test_phase1_5_bprime import Oracle
from test_phase1_5_bprime_hardening import setup_coordinator,Builder
from bprime_test_support import toy_store


@pytest.mark.parametrize('boundary',[
    'after_stage_fsync','after_link','after_destination_fsync',
    'after_stage_unlink','after_stage_dir_fsync'])
def test_continue_after_complete_staged_record_recovery_without_resampling(tmp_path,monkeypatch,boundary):
    def deny(*a,**k):pytest.fail('Registered execution prohibited')
    monkeypatch.setattr(bp.Stream,'__init__',deny);monkeypatch.setattr(old.Stream,'__init__',deny)
    monkeypatch.setattr(bp,'geometry',deny);monkeypatch.setattr(old,'geometry',deny)
    fired=[]
    def crash(point,path):
        if path.name.endswith('.json.gz') and point==boundary and not fired:
            fired.append(point);raise OSError('explicit synthetic publication interruption')
    store,refs,coordinator=setup_coordinator(tmp_path,fault=crash);first=Builder()
    with pytest.raises(OSError):
        with store.writer():coordinator.execute_one(first)
    assert first.geometry_calls==1
    restored=toy_store(store.root,binding=store.binding,backend=Oracle())
    restarted=Coordinator(restored,refs,backend=Oracle(),synthetic=True);next_builder=Builder()
    with restored.writer():
        recovered_rows=restarted.restore()
        assert restarted.sequence==1
        assert len(recovered_rows)==1
        assert recovered_rows[0][1]['identity']=='synthetic:fit:R:0'
        assert next_builder.geometry_calls==0
        restarted.execute_one(next_builder)
        rows=sorted((v for _,v in restored.scan()),key=lambda v:v['sequence'])
        assert [v['identity'] for v in rows]==['synthetic:fit:R:0','synthetic:fit:BP:0']
    assert first.geometry_calls==1 and next_builder.geometry_calls==1
