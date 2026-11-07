"""Scripted integration fixtures; registered RNG entrypoints are prohibited."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from spatial_memory import phase15_bprime as bp,phase15_generators as old
from spatial_memory.phase15_bprime_development import Builder
from spatial_memory.phase15_bprime_records import validate_candidate
from spatial_memory.phase15_macos_monitored import MonitoredBackend
from test_phase1_5_bprime import Tape,Oracle
from test_phase1_5_bprime_hardening import bp_geometry_fixture,counter


@pytest.fixture(autouse=True)
def deny_registered_rng(monkeypatch):
    def deny(*a,**k):pytest.fail('Registered RNG is prohibited in adapter fixtures')
    monkeypatch.setattr(bp.Stream,'__init__',deny);monkeypatch.setattr(old.Stream,'__init__',deny)
    monkeypatch.setattr(old,'geometry',deny)


def synthetic_identity(monkeypatch,mechanism):
    job=dict(identity=f'synthetic:fit:{mechanism}:0',partition='fit',mechanism=mechanism,index=0,sequence=0)
    monkeypatch.setattr(bp,'Identity',lambda *args:SimpleNamespace(root=job['identity'],partition='fit',mechanism=mechanism,seed=7))
    monkeypatch.setattr(bp,'seed_for',lambda *args:7)
    return job


def test_scripted_bp_adapter_native_keys_pair_and_schedules(monkeypatch):
    job=synthetic_identity(monkeypatch,'BP');free,construction,counters=bp_geometry_fixture(job)
    class Script(Tape):
        def __init__(self,identity,purpose):super().__init__([0]);self.purpose=purpose
        def counters(self):return counter(self,self.purpose)
    monkeypatch.setattr(bp,'Stream',Script)
    backend=MonitoredBackend();builder=Builder(backend)
    def geometry(identity,stream_factory):
        for p,c in counters.items():builder.streams[p]=SimpleNamespace(counters=lambda c=c:deepcopy(c))
        return old.Geometry('synthetic-fit','BP',7,free,construction)
    monkeypatch.setattr(bp,'geometry',geometry)
    try:
        payload=builder.geometry(job)
        assert set(payload['streams'])=={'partition','tree','chords','doors'}
        payload.update(job,kind='candidate',version=bp.VERSION,profile='synthetic')
        payload=builder.complete(payload)
        assert set(payload['streams'])=={'partition','tree','chords','doors','start-goal','dynamics-0','dynamics-1'}
        # This explicitly scripted Hamiltonian-room fixture reduces to an edge;
        # its C3/literal ordering agrees, allowing the independent literal oracle.
        payload['topology']['exact'][0]='synthetic-exact-oracle'
        for k in payload['topology']['keys']:k[0]='synthetic-exact-oracle'
        assert validate_candidate(payload,synthetic=True,backend=Oracle()).complete
        assert [s['category'] for s in payload['world']['schedules']]==['none','none']
    finally:backend.close()


def test_v_rejection_witness_uses_failed_frame_without_replay(monkeypatch):
    job=synthetic_identity(monkeypatch,'V')
    class Script(Tape):
        def __init__(self,identity,purpose):super().__init__([0]+list(range(528,0,-1)))
        def counters(self):return counter(self,'geometry')
    monkeypatch.setattr(bp,'Stream',Script)
    def geometry(identity,stream_factory):return old.generate_v(stream_factory(identity,'geometry'),'lex_yx')
    monkeypatch.setattr(bp,'geometry',geometry)
    builder=Builder(None)
    with pytest.raises(old.Rejected,match='voronoi_seed_separation'):builder.geometry(job)
    assert len(builder.rejection_evidence()['seeds'])==12
    assert builder.stream_counters()['geometry']['bounds']==[3]+list(range(529,1,-1))
