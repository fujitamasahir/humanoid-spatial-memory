"""Prospective paired-lineage analysis infrastructure; thresholds remain proposals."""
from dataclasses import dataclass
from statistics import NormalDist
import math
import numpy as np

@dataclass(frozen=True)
class ProposedCriteria:
    ni_margin:float=.03
    benefit:float=.10
    alpha:float=.025
    scheduler_ms:float=5.
    wall_ratio:float=1.10


def paired_arrays(rows,candidate,reference):
    indexed={};lineages=sorted({r['lineage'] for r in rows})
    for r in rows:
        key=(r['lineage'],r['schedule'],r['arm'])
        if r['schedule'] not in (0,1) or key in indexed:raise ValueError('Duplicate/invalid paired schedule')
        for name in ('goal','contacts','paid','emergency_rays','steps','distance','wall','scheduler_ms'):
            if not math.isfinite(r[name]) or r[name]<0:raise ValueError('Invalid metric')
        if r['goal'] not in (0,1):raise ValueError('Binary completion')
        indexed[key]=r
    if len(lineages)<2:raise ValueError('At least two independent lineages')
    a=[];b=[]
    for ident in lineages:
        try:a.append([indexed[ident,s,candidate] for s in (0,1)]);b.append([indexed[ident,s,reference] for s in (0,1)])
        except KeyError as e:raise ValueError('Missing paired lineage/schedule/arm') from e
    return a,b


def mean_bounds(values,alpha=.025):
    x=np.asarray(values,dtype=float);n=len(x)
    if n<2:return None
    mean=float(x.mean());sd=float(x.std(ddof=1));z=NormalDist().inv_cdf(1-alpha)
    if sd==0:
        # D in[-1,1]; avoids a spurious exact zero-width completion interval.
        radius=math.sqrt(2*math.log(2/alpha)/n);method='bounded_Hoeffding_degenerate'
    else:radius=z*sd/math.sqrt(n);method='paired_lineage_normal_approximation'
    return {'mean':mean,'low':max(-1.,mean-radius),'high':min(1.,mean+radius),'sd':sd,'n':n,'method':method}


def bootstrap(values,draws,alpha=.025):
    x=np.asarray(values,dtype=float);means=x[draws].mean(axis=1)
    return {'mean':float(x.mean()),'low':float(np.quantile(means,alpha)),
            'high':float(np.quantile(means,1-alpha)),'degenerate':bool(np.ptp(means)==0)}


def contact_upper(k,n,alpha=.05):
    if type(k) is not int or type(n) is not int or not 0<=k<=n or n<1:raise ValueError('Invalid contact counts')
    if k==n:return 1.
    if k==0:return 1-alpha**(1/n)
    def cdf(p):
        if p<=0:return 1.
        if p>=1:return 0.
        logs=[math.lgamma(n+1)-math.lgamma(j+1)-math.lgamma(n-j+1)+j*math.log(p)+(n-j)*math.log1p(-p) for j in range(k+1)]
        m=max(logs);return math.exp(m)*sum(math.exp(v-m) for v in logs)
    lo,hi=0.,1.
    for _ in range(70):
        mid=(lo+hi)/2
        if cdf(mid)>alpha:lo=mid
        else:hi=mid
    return (lo+hi)/2


def holm(pvalues,alpha=.05):
    if any(not 0<=p<=1 for p in pvalues.values()):raise ValueError('Invalid pvalue')
    ordered=sorted(pvalues,key=lambda k:(pvalues[k],k));m=len(ordered);adjusted={};running=0.
    for i,k in enumerate(ordered):running=max(running,(m-i)*pvalues[k]);adjusted[k]=min(1.,running)
    return {k:{'adjusted_p':adjusted[k],'reject':adjusted[k]<=alpha} for k in ordered}


def compare(rows,candidate,reference,*,replicates=2000,seed=2026111408,criteria=None):
    c=criteria or ProposedCriteria();a,b=paired_arrays(rows,candidate,reference);n=len(a)
    if type(replicates) is not int or replicates<100:raise ValueError('At least100 whole-lineage replicates')
    draws=np.random.default_rng(seed).integers(0,n,size=(replicates,n))
    array=lambda records,key:np.array([[r[key] for r in pair] for pair in records],dtype=float)
    goal_a,goal_b=array(a,'goal'),array(b,'goal');difference=(goal_a-goal_b).mean(axis=1)
    completion=mean_bounds(difference,c.alpha);boot=bootstrap(difference,draws,c.alpha)
    contacts_a=array(a,'contacts');contacts_b=array(b,'contacts')
    result={'lineages':n,'schedules':2*n,'candidate':candidate,'reference':reference,
       'completion':completion,'completion_bootstrap':boot,'completion_superiority':completion['low']>0,
       'completion_noninferiority_proposed':completion['low']>-c.ni_margin,
       'rescues':int(np.sum((goal_a==1)&(goal_b==0))),'harms':int(np.sum((goal_a==0)&(goal_b==1))),
       'contact_lineages':int(np.any(contacts_a>0,axis=1).sum()),
       'contact_upper95':contact_upper(int(np.any(contacts_a>0,axis=1).sum()),n),
       'original_owner_descriptive_target':bool(contacts_a.sum()==0 and (goal_a.sum()>goal_b.sum() or (goal_a.sum()==goal_b.sum() and array(a,'paid').sum()<array(b,'paid').sum()))),
       'scientific_criteria_status':'PROPOSED_NOT_APPROVED'}
    costs={}
    for key in ('paid','combined'):
        x=array(a,'paid')*61+array(a,'emergency_rays') if key=='combined' else array(a,key)
        y=array(b,'paid')*61+array(b,'emergency_rays') if key=='combined' else array(b,key)
        contrast=(x-(1-c.benefit)*y).mean(axis=1)
        costs[key]={'difference':bootstrap((x-y).mean(axis=1),draws,c.alpha),'benefit_contrast':bootstrap(contrast,draws,c.alpha)}
    common=(goal_a==1)&(goal_b==1);den=common.sum(axis=1);total=int(den.sum());movement={}
    for key in ('steps','distance'):
        x=array(a,key);y=array(b,key);sums=((x-(1-c.benefit)*y)*common).sum(axis=1);delta=((x-y)*common).sum(axis=1)
        denominators=den[draws].sum(axis=1);valid=denominators>0
        estimates=sums[draws].sum(axis=1)[valid]/denominators[valid]
        movement[key]={'common_successes':total,'contributing_lineages':int(np.count_nonzero(den)),
          'missing_lineages':int(np.sum(den==0)),'bootstrap_missing_fraction':float(np.mean(~valid)),
          'difference':float(delta.sum()/total) if total else None,
          'benefit_contrast':{'mean':float(sums.sum()/total),'low':float(np.quantile(estimates,c.alpha)),
             'high':float(np.quantile(estimates,1-c.alpha))} if total and len(estimates) else None,
          'failure_penalized_difference':bootstrap((np.where(goal_a,x,80 if key=='steps' else 60)-np.where(goal_b,y,80 if key=='steps' else 60)).mean(axis=1),draws,c.alpha)}
    wall=bootstrap((array(a,'wall')-c.wall_ratio*array(b,'wall')).mean(axis=1),draws,c.alpha)
    gate=[('safety',not bool(np.any(contacts_a>contacts_b))),('completion',result['completion_noninferiority_proposed']),
        ('combined',costs['combined']['benefit_contrast']['high']<0),('paid',costs['paid']['benefit_contrast']['high']<0)]
    gate.extend((key,movement[key]['benefit_contrast'] is not None and movement[key]['bootstrap_missing_fraction']==0 and movement[key]['benefit_contrast']['high']<0) for key in ('steps','distance'))
    gate.append(('compute',float(array(a,'scheduler_ms').max())<=c.scheduler_ms and wall['high']<=0))
    alive=True;sequence=[]
    for name,passed in gate:sequence.append({'name':name,'criterion_passed':bool(passed),'eligible':alive,'sequence_passed':bool(alive and passed)});alive=bool(alive and passed)
    result.update(costs=costs,movement=movement,wall_overhead=wall,fixed_sequence=sequence,joint_proposed_pass=alive)
    return result


def select_candidate(rows,*,stage='selection',confirmed_candidate=None):
    if stage not in ('selection','confirmation') or any(r.get('partition') not in ('SYNTHETIC', 'development') for r in rows):raise PermissionError('Never select on sealed/evaluation outcomes')
    arms=sorted({r['arm'] for r in rows if r['arm'].startswith('dao_')})
    order=('dao_veto','dao_trigger','dao_route','dao_combined');scores=[]
    for arm in arms:
        a,b=paired_arrays(rows,arm,'age5');flat=lambda records:[r for pair in records for r in pair];aa,bb=flat(a),flat(b)
        if any(x['contacts']>y['contacts'] for x,y in zip(aa,bb)) or np.mean([x['goal']-y['goal'] for x,y in zip(aa,bb)])<-.03:continue
        common=[(x,y) for x,y in zip(aa,bb) if x['goal'] and y['goal']]
        if not common:continue
        score=(sum(x['paid']*61+x['emergency_rays'] for x in aa),sum(x['paid'] for x in aa),
               np.mean([x['steps'] for x,y in common]),np.mean([x['distance'] for x,y in common]),order.index(arm))
        if stage=='confirmation':
            if arm!=confirmed_candidate:continue
            passed=score[0]<sum(x['paid']*61+x['emergency_rays'] for x in bb) and all(np.mean([x[k]-y[k] for x,y in common])<0 for k in ('steps','distance'))
            return {'candidate':arm if passed else None,'stage':stage,'switching_allowed':False}
        scores.append((score,arm))
    return {'candidate':min(scores)[1] if scores and stage=='selection' else None,'stage':stage,'switching_allowed':False}


def simulate_completion(*,n=200,repetitions=1000,correlation=.5,discordance=.1,loss=0.,seed=2):
    if n<2 or repetitions<1 or not 0<=correlation<=1 or not 0<=discordance<=1 or abs(loss)>discordance:raise ValueError('Invalid simulation')
    rng=np.random.default_rng(seed);coverage=ni=superiority=0;sds=[]
    for _ in range(repetitions):
        # Explicit paired differences per schedule with controlled discordance;
        # copy the first schedule with probability rho, else independent draw.
        first=rng.choice([-1.,0.,1.],n,p=[(discordance+loss)/2,1-discordance,(discordance-loss)/2])
        second=rng.choice([-1.,0.,1.],n,p=[(discordance+loss)/2,1-discordance,(discordance-loss)/2])
        second=np.where(rng.random(n)<correlation,first,second);d=(first+second)/2
        bounds=mean_bounds(d);coverage+=bounds['low']<=-loss<=bounds['high'];ni+=bounds['low']>-.03;superiority+=bounds['low']>0;sds.append(bounds['sd'])
    return {'n':n,'repetitions':repetitions,'schedule_correlation':correlation,'discordance':discordance,'true_loss':loss,
        'coverage':coverage/repetitions,'proposed_NI_probability':ni/repetitions,'superiority_probability':superiority/repetitions,
        'mean_lineage_sd':float(np.mean(sds)),'monte_carlo_SE_max':.5/math.sqrt(repetitions)}


def simulate_conditional_cost(*,n=200,repetitions=200,replicates=200,correlation=.8,
                              discordance=.2,reduction=.1,skew=.5,seed=9):
    rng=np.random.default_rng(seed);coverage=power=missing=0;truth=20*(.1-reduction)
    for _ in range(repetitions):
        shared=rng.normal(size=(n,1));noise=np.sqrt(correlation)*shared+np.sqrt(1-correlation)*rng.normal(size=(n,2))
        cost=20*(1-reduction)*np.exp(skew*noise-.5*skew**2)-18
        # Policy-independent common-success exposure for this validation scenario.
        common_shared=rng.random((n,1));common=np.where(rng.random((n,2))<correlation,common_shared,rng.random((n,2)))>discordance
        sums=(cost*common).sum(axis=1);den=common.sum(axis=1)
        draws=rng.integers(0,n,size=(replicates,n));denominators=den[draws].sum(axis=1);valid=denominators>0
        if not valid.all():missing+=1
        if not valid.any():continue
        sample=sums[draws].sum(axis=1)[valid]/denominators[valid];lo,hi=np.quantile(sample,[.025,.975])
        coverage+=lo<=truth<=hi;power+=hi<0
    return {'n':n,'repetitions':repetitions,'bootstrap_replicates':replicates,'schedule_correlation':correlation,
        'common_success_missing_rate':discordance,'true_cost_reduction':reduction,'lognormal_skew':skew,
        'coverage':coverage/repetitions,'power_or_boundary_error':power/repetitions,
        'repetitions_with_missing_bootstrap_denominator':missing,'MC_SE_max':.5/math.sqrt(repetitions)}
