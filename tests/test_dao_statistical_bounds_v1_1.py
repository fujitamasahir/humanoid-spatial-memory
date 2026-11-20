import math
import numpy as np
import pytest
from spatial_memory.dao_statistical_bounds_v1_1 import bounded_mean,conservative_components
from test_dao_navigation_infrastructure_v1 import outcomes


def test_zero_variance_does_not_fake_exact_completion_and_width_contracts():
    small=bounded_mean(np.zeros(200),-1,1);large=bounded_mean(np.zeros(20000),-1,1)
    assert small['low']<-.03 and large['low']>-.03
    assert large['high']<small['high']


def test_declared_metric_bounds_and_missing_common_successes():
    result=conservative_components(outcomes(goal_a=0),'dao_veto','age5')
    assert result['common_success_probability']['low']==0
    assert not result['costs']['steps']['proposed_benefit_supported']
    rows=outcomes();rows[0]['paid']=21
    with pytest.raises(ValueError):conservative_components(rows,'dao_veto','age5')


def test_finite_sample_coverage_and_null_boundary_smoke():
    rng=np.random.default_rng(8);reject=0;covered=0
    for _ in range(1000):
        x=rng.choice([-1.,0.,1.],80,p=[.04,.95,.01]);interval=bounded_mean(x,-1,1)
        covered+=interval['low']<=-.03<=interval['high'];reject+=interval['low']>-.03
    assert covered>=950 and reject<=25


@pytest.mark.parametrize('values',([0,float('nan')],[-2,0]))
def test_bad_bounded_values(values):
    with pytest.raises(ValueError):bounded_mean(values,-1,1)
