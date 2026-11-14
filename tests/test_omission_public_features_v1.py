"""Authorized-only reconstruction and prespecified diagnostic rule tests."""
import json
import numpy as np
import pytest
from spatial_memory.omission_public_features_v1 import AuthorizedHistory,diagnostic_rules

def test_readings_never_update_unknown_timestamps_or_count_new_as_change():
    h=AuthorizedHistory((15,15))
    a=np.full((15,15),-1,np.int8);a[7,7:10]=[0,0,1]
    h.update(a,0,(7,7),0.)
    assert h.last_change_count==0 and h.changed.max()==-1
    b=np.full_like(a,-1);b[7,8:11]=[1,0,0]
    h.update(b,5,(7,7),0.)
    assert h.last_change_count==2 and h.changed[7,8]==h.changed[7,9]==5
    assert h.changed[7,10]==-1 and h.last[7,7]==0 and h.grid[7,7]==0
    assert h.last[0,0]==-1
    with pytest.raises(ValueError):h.features(5,(7,7),0.,(12,7))

def test_known_stable_route_and_history_unchanged():
    g=np.zeros((15,15),np.int8);h=AuthorizedHistory(g.shape)
    h.update(g,0,(7,7),0.);h.update(g,5,(7,7),0.)
    f=h.features(10,(7,7),0.,(12,7));r=diagnostic_rules(f)
    assert f['prefix_unknown']==f['route_unknown']==f['band_recent_changed']==0
    assert f['previous_view_overlap_fraction']==1.
    assert r['stable_prefix_later_previous_no_change'] and r['stable_prefix_same_pose']
    assert h.last.max()==5 and h.readings==2 and not h.grid.any()

def test_unknown_route_and_occupied_route_start_not_stable():
    a=np.full((15,15),-1,np.int8);a[7,7]=0
    h=AuthorizedHistory(a.shape);h.update(a,0,(7,7),0.)
    assert not diagnostic_rules(h.features(5,(7,7),0.,(12,7)))['known_prefix']
    b=np.full_like(a,-1);b[7,7]=1;h.update(b,5,(7,7),0.)
    f=h.features(10,(7,7),0.,(12,7))
    assert not f['route_available'] and not diagnostic_rules(f)['stable_prefix']

def test_change_history_and_pose_are_from_previous_scan_only():
    g=np.zeros((15,15),np.int8);h=AuthorizedHistory(g.shape);h.update(g,0,(5,7),0.)
    b=g.copy();b[6,8]=1;h.update(b,5,(6,7),0.)
    f=h.features(10,(7,7),0.,(12,7))
    assert f['previous_changed_known']==1 and f['band_recent_changed']==1
    assert f['visible_band_stale_occupied']==1 and f['displacement_cells']==1
    assert not diagnostic_rules(f)['stable_prefix']
    with pytest.raises(ValueError):h.update(b,5,(6,7),0.)


@pytest.mark.parametrize('kind',('known','mixed','unavailable'))
def test_complete_audit_row_is_strict_json_serializable(kind):
    g=np.zeros((15,15),np.int8)
    if kind=='mixed':
        g[6:9,9:]=-1
        g[6,8]=1
    elif kind=='unavailable':
        g[7,7]=1
    h=AuthorizedHistory(g.shape)
    h.update(g,0,(7,7),0.)
    b=g.copy()
    b[6,8]=0 if g[6,8]==1 else 1
    h.update(b,5,(7,7),0.)
    f=h.features(10,(7,7),0.,(12,7))
    row={'scene_index':1,'scene':'fixture','safety':'original','step':10,
         **f,**{'mask_'+k:v for k,v in diagnostic_rules(f).items()}}
    assert all(type(v) in (str,int,float,bool,type(None)) for v in row.values())
    encoded=json.dumps([row],indent=2,sort_keys=True,allow_nan=False)
    assert json.loads(encoded)==[row]
