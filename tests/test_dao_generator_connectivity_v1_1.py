import copy
import pytest
from spatial_memory.dao_generator_v1_1 import generate_test,validate,bfs,FAMILIES


@pytest.mark.parametrize('family',FAMILIES)
@pytest.mark.parametrize('size',(25,33,41))
def test_corrected_test_generator_preserves_connected_free_geometry(family,size):
    p=generate_test(101,family=family,width=size,height=size,discovery='occluded',revisit='rare',category='moving',persistent='relocate')
    free={(x,y) for y,row in enumerate(p['occupancy']) for x,v in enumerate(row) if v==0}
    assert len(bfs(free,min(free)))==len(free)
    assert p['partition']=='TEST' and p['generator_version']=='dao-generator-v1.1-engineering'
    assert validate(p)
    assert not(p['occlusion_island_applied'] and p['occlusion_island_rejected_for_connectivity'])


def test_validator_rejects_off_certificate_isolated_free_pocket():
    p=generate_test(101,category='none');bad=copy.deepcopy(p)
    # A boundary wall ring shields a deliberately isolated free pocket off path.
    reserve={tuple(c) for c in p['certificate']}
    for y in range(2,23):
        for x in range(2,23):
            if all((x+dx,y+dy) not in reserve for dx in (-1,0,1) for dy in (-1,0,1)):
                for dx in (-1,0,1):
                    for dy in (-1,0,1):bad['occupancy'][y+dy][x+dx]=1
                bad['occupancy'][y][x]=0
                with pytest.raises(ValueError,match='Disconnected'):validate(bad)
                return
    raise AssertionError('No engineering pocket position')
