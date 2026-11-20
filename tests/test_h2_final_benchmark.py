"""Tests of new benchmark plumbing; frozen policies are not modified."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts')]
import h2_final_common as h
import h2_generate_maps as g
from spatial_memory.scheduling import AdaptiveParameters
@pytest.mark.parametrize('arm',h.ARMS)
def test_factory_authorized_inputs(arm):
    initial=np.zeros((8,8),np.int8);cfg=h.config()
    c=h.factory(initial,arm,cfg,dict(interval=4,radius=3,parameters=AdaptiveParameters(),max_observations=20),(6,6))
    assert c.used==1 and c.cap==20
    np.testing.assert_array_equal(c.memory.grid,initial)
    assert not hasattr(c,'world')

def test_disjoint_stream_reproducibility():
    i=g.H2Identity('h2_final_generalization_v1','R',910000000)
    a=g.H2Stream(i,'geometry');b=g.H2Stream(i,'geometry')
    assert [a.integer(1000) for _ in range(20)]==[b.integer(1000) for _ in range(20)]
    old=g.bp.Stream(g.bp.Identity('fit','R',80000000),'geometry')
    assert a.identity!=old.identity
    with pytest.raises(ValueError):g.H2Identity('fit','R',80000000)

def test_geometry_certificate_requires_reachability():
    a=np.ones((7,7),np.int8);a[1:6,1:6]=0
    # Certificate routine supports frozen25 grid only.
    a=np.pad(a,((0,18),(0,18)),constant_values=1)
    assert g.g1_certificate(a,(2,2),(4,4))
    a[3,:]=1
    assert not g.g1_certificate(a,(2,2),(4,4))

def test_adapter_restored_after_failure(monkeypatch):
    old=h.ref.base.run_episode;scenario=h.ref.base.scenario_from_bprime
    def fail(*a,**kw):raise RuntimeError('fixture')
    monkeypatch.setattr(h.ref.base,'run_case',fail)
    with pytest.raises(RuntimeError):h.run_case({},0,'age5')
    assert h.ref.base.run_episode is old and h.ref.base.scenario_from_bprime is scenario
