"""Old inspected v2c fixtures are regression inputs, not fresh formal data."""
import numpy as np

from scripts.c_v2c_fixtures import build_formal_fixtures as old_fixture_set
from spatial_memory.evi import EVIParameters,visible_cells
from spatial_memory.topology_evi_c import (
    analyze_public_topology_c,information_value_topology_c,
    rank_topology_candidates_c,
)
from spatial_memory.topology_evi_d import (
    information_value_topology_d,rank_topology_candidates_d,
)

SENSOR={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}


def test_inspected_v2c_48_fixtures_keep_exact_v2c_decisions_without_rescreening():
    fixtures=old_fixture_set()
    assert len(fixtures)==48
    for f in fixtures:
        grid=f['grid'];prob=f['probability'];start=f['start'];goal=f['goal']
        args=(grid,prob,start,goal,f['yaw'],f['unknown'],SENSOR,20,EVIParameters(max_candidates=3))
        old=information_value_topology_c(*args)
        new=information_value_topology_d(*args)
        assert new['shortlisted_candidates']==old['shortlisted_candidates'],f['fixture_id']
        for name in ('value','delay_regret','cell','occupied_probability','cost','net_value','plan_calls'):
            assert new[name]==old[name],(f['fixture_id'],name)
        assert (new['net_value']>0)==(old['net_value']>0)
        assert new['stage_accounting']['passes'],(f['fixture_id'],new['stage_accounting']['checks'])
        footprint=visible_cells(grid,start,f['yaw'],**SENSOR)
        candidates=[c for c in footprint if c!=start and .05<prob[c[1],c[0]]<.95]
        graph=analyze_public_topology_c(grid,start,goal,f['unknown'])
        full=rank_topology_candidates_c(grid,prob,candidates,graph,start,goal,old['nominal_route'] or [])[0]
        selected=rank_topology_candidates_d(grid,prob,candidates,graph,start,goal,old['nominal_route'] or [],3)[0]
        assert selected==full[:3],f['fixture_id']
