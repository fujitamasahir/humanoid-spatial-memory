"""Optional finite-sample bounds; original approximate analysis is preserved.

Independent LINEAGES are required; schedules can be arbitrarily correlated.
No margin or sample size is approved by this implementation.
"""
import math
import numpy as np
from .dao_statistics_v1 import paired_arrays


def bounded_mean(values,lower,upper,alpha=.05):
    x=np.asarray(values,dtype=float)
    if x.ndim!=1 or len(x)<2 or not np.isfinite(x).all() or not lower<upper or not 0<alpha<1 or np.any(x<lower) or np.any(x>upper):raise ValueError('Known bounds and independent lineage means required')
    radius=(upper-lower)*math.sqrt(math.log(2/alpha)/(2*len(x)))
    return {'mean':float(x.mean()),'low':max(lower,float(x.mean())-radius),'high':min(upper,float(x.mean())+radius),
            'method':'finite_sample_Hoeffding','independent_units':len(x),'two_sided_error_bound':alpha}


def conservative_components(rows,candidate,reference,benefit=.1,ni_margin=.03):
    if not 0<benefit<1 or not 0<ni_margin<1:raise ValueError('Proposed margins')
    a,b=paired_arrays(rows,candidate,reference)
    arr=lambda records,key:np.array([[r[key] for r in pair] for pair in records],float)
    ga,gb=arr(a,'goal'),arr(b,'goal');completion=bounded_mean((ga-gb).mean(axis=1),-1,1)
    common=(ga==1)&(gb==1);prob=bounded_mean(common.mean(axis=1),0,1)
    metrics={}
    for key,bounds in [('paid',(1,20)),('combined',(61,6100)),('steps',(0,80)),('distance',(0,60))]:
        x=61*arr(a,'paid')+arr(a,'emergency_rays') if key=='combined' else arr(a,key)
        y=61*arr(b,'paid')+arr(b,'emergency_rays') if key=='combined' else arr(b,key)
        lo,hi=bounds
        if np.any(x<lo) or np.any(x>hi) or np.any(y<lo) or np.any(y>hi):raise ValueError('Declared H80/cap20 metric bound violated')
        contrast=x-(1-benefit)*y;lower=lo-(1-benefit)*hi;upper=hi-(1-benefit)*lo
        if key in ('steps','distance'):
            contrast=contrast*common;lower=min(0,lower);upper=max(0,upper)
        metrics[key]=bounded_mean(contrast.mean(axis=1),lower,upper)
        metrics[key]['proposed_benefit_supported']=metrics[key]['high']<0 and (key not in ('steps','distance') or prob['low']>0)
    return {'completion':completion,'common_success_probability':prob,'costs':metrics,
            'proposed_completion_NI_supported':completion['low']>-ni_margin,
            'full_joint_claim':False,'compute_and_population_assumptions_require_validation':True,
            'margins_status':'PROPOSED_NOT_APPROVED','warning':'Conservative marginal bounds; no multiplicity shortcut or joint-power guarantee.'}
