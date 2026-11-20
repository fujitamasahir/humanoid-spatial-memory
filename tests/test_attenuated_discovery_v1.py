"""Independent axial depth reference and footprint parity."""
import numpy as np
import pytest
from spatial_memory.attenuated_discovery_v1 import attenuated_footprints
from spatial_memory.discovery_observation import predicted_footprints

def test_axial_corridor_distinct_unknowns_not_sample_count():
    grid=np.ones((9,11),np.int8)
    grid[4,1:4]=0;grid[4,4:9]=-1
    result=attenuated_footprints(grid,(2,4),0.,horizontal_fov_deg=.001,factors=(0.,.5,1.))
    assert result['unknown_depth']=={(x,4):x-4 for x in range(4,9)}
    assert sum(result['weights'][.5].values())==pytest.approx(sum(.5**k for k in range(5)))
    assert sum(result['weights'][0.].values())==1
    assert sum(result['weights'][1.].values())==5

def test_known_free_between_unknowns_does_not_increase_depth():
    g=np.ones((7,9),np.int8);g[3,1:7]=[-1,0,-1,0,-1,0]
    d=attenuated_footprints(g,(1,3),0.,horizontal_fov_deg=.001)
    assert d['unknown_depth']=={(3,3):0,(5,3):1}

def test_legacy_footprints_and_weight_bounds_randomized():
    rng=np.random.default_rng(2026111418)
    for _ in range(80):
        g=rng.choice([-1,0,1],size=(15,15),p=[.4,.5,.1]).astype(np.int8)
        pose=tuple(map(int,rng.integers(2,13,size=2)));yaw=float(rng.uniform(-np.pi,np.pi))
        before=g.copy()
        r=attenuated_footprints(g,pose,yaw,factors=(0.,.5,.8,1.))
        old=predicted_footprints(g,pose,yaw)
        assert r['frontier']==old['frontier'] and r['optimistic']==old['optimistic']
        assert r['sample_visits']==old['samples']<=4941
        assert sum(r['weights'][0.].values())==sum(g[y,x]==-1 for x,y in old['frontier'])
        assert sum(r['weights'][1.].values())==sum(g[y,x]==-1 for x,y in old['optimistic'])
        assert all(0<=r['weights'][.5][c]<=r['weights'][.8][c]<=1 for c in r['unknown_depth'])
        assert np.array_equal(g,before) and r['actual_sensor_calls']==0

@pytest.mark.parametrize('q',[-.1,1.1,float('nan')])
def test_invalid_factor(q):
    with pytest.raises(ValueError):attenuated_footprints(np.zeros((5,5),np.int8),(2,2),0.,factors=(q,))
