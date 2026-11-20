import sys
from pathlib import Path
import numpy as np
import pytest
from spatial_memory.dao_navigation_compat_v1_1 import DAONavigationCompatV1_1,safe_public_route
from spatial_memory.discovery_observation import DiscoveryController


def test_occupied_current_public_cell_is_not_erased_and_route_is_missing():
    grid=np.zeros((15,15),np.int8);grid[7,3]=1
    assert safe_public_route(grid,(3,7),(12,7))==[]
    a=DAONavigationCompatV1_1(grid,mode='dao_route');b=DiscoveryController(grid,mode='dao_route')
    a.set_navigation_context(goal=(12,7),yaw=0.);b.set_navigation_context(goal=(12,7),yaw=0.,route=[])
    assert a.decide(1,(3,7))==b.decide(1,(3,7))
    assert a.memory.grid[7,3]==1 and a.route_plan_calls==1


@pytest.mark.parametrize('mode',('dao_veto','dao_route'))
def test_actual_pedestrian_scene_diagnostic_compatibility(mode):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
    from run_dao_integration_v1_1 import run_navigation
    from dao_engineering_scenes_v1 import scenes
    d=next(s for s in scenes() if s['family']=='pedestrian')
    e=run_navigation(d,mode)
    assert len(e['scans'])==e['metrics']['observation_count']<=20
    assert all(s['computed_before_actual_reading'] for s in e['scans'])
