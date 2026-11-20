"""H=1 versus H=3 verification, without FIT access."""
import numpy as np
import pytest
from spatial_memory.multistep_depth_ablation import information_value_multistep as depth
from spatial_memory.multistep_evi import information_value_multistep as frozen
from spatial_memory.multistep_reference import reference_cell

SENSOR=dict(range_m=4.,cell_size=1.,horizontal_fov_deg=360.,ray_count=61)
KEYS=('value','delay_regret','net_value','no_information_cost','informed_movement_cost',
      'observe_now_cost','best_postpone_cost')

def strip_timing(value):
    if isinstance(value,dict):
        return {k:strip_timing(v) for k,v in value.items() if k not in
                ('scheduler_ns','graph_analysis_ns','analysis_ns')}
    if isinstance(value,list):return [strip_timing(v) for v in value]
    return value

@pytest.mark.parametrize('selector',['k','topology'])
def test_depth_against_independent_reference_and_frozen_h3(selector):
    rng=np.random.default_rng(2026111417)
    for i in range(60):
        grid=rng.choice([-1,0,1],size=(4,5),p=[.15,.65,.20]).astype(np.int8)
        start=(0,1);goal=(4,2);grid[1,0]=grid[2,4]=0
        q=rng.choice([0.,.2,.5,.8,1.],size=grid.shape)
        unknown='blocked' if i%2 else 'optimistic'
        args=(grid,q,start,goal,0.,unknown,SENSOR,19)
        h1=depth(*args,selector=selector,horizon=1,future_visibility=False)
        h3=depth(*args,selector=selector,horizon=3,future_visibility=False)
        old=frozen(*args,selector=selector,future_visibility=False)
        assert strip_timing(h3)==strip_timing(old)
        assert h1['shortlisted_candidates']==h3['shortlisted_candidates']
        assert h1['cost']==h3['cost']
        assert h1['plan_calls']==h3['plan_calls']
        assert h1['net_value']>=h3['net_value']-1e-9
        assert h1['future_visibility_computations']==h3['future_visibility_computations']==0
        for h,result in ((1,h1),(3,h3)):
            refs=[]
            for entry in result['candidate_evaluations']:
                cell=tuple(entry['cell'])
                ref=reference_cell(grid,cell,float(q[cell[1],cell[0]]),
                    start,goal,0.,unknown,SENSOR,result['cost'],False,horizon=h)
                for key in KEYS:assert entry[key]==pytest.approx(ref[key],abs=1e-9)
                refs.append(ref)
            if refs:
                expected=max(refs,key=lambda r:(r['net_value'],r['value']))
                assert result['net_value']==pytest.approx(expected['net_value'],abs=1e-9)
            else:assert result['net_value']<0
            k=result['candidate_limit_k']
            assert result['plan_calls']<=1+2*k
            assert result['prefix_step_visits']<=2*k*h*(h+1)
            assert result['recovery_checks']<=2*k*h*(h+3)
            assert result['future_option_evaluations']<=2*k*h

def test_horizon_restriction():
    grid=np.zeros((3,3),dtype=np.int8)
    for h in (0,2,4,True):
        with pytest.raises(ValueError):
            depth(grid,np.zeros(grid.shape),(0,0),(2,2),0.,
                  'optimistic',SENSOR,19,horizon=h)
