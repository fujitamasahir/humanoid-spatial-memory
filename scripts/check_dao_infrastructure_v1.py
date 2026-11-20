"""Formal TEST-only generator/admission evidence and SYNTHETIC statistical checks."""
import json,sys,itertools,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import write,manifest,sha
from run_dao_integration_v1 import gate,OUT,native
from spatial_memory.dao_generator_v1 import generate_test_logged,FAMILIES
from spatial_memory.dao_admission_v1 import (admit_test_logged,inventory_commitment,ImmutableLog,occupancy_hash,
    exact_isomorphic,corridor_graph,graph_signature)
from spatial_memory.dao_statistics_v1 import compare,select_candidate,simulate_completion,simulate_conditional_cost,contact_upper


def synthetic_table(n=80):
    rng=np.random.default_rng(2026111410);rows=[]
    for i in range(n):
        baseline=rng.random()<.9
        for schedule in (0,1):
            goal=int(baseline if rng.random()<.7 else rng.random()<.9)
            for arm in ('age5','dao_veto','dao_trigger','dao_route','dao_combined'):
                candidate=arm!='age5';paid=10-int(candidate)*2+(i%3)
                rows.append({'lineage':f'SYNTHETIC:{i}','schedule':schedule,'partition':'SYNTHETIC','arm':arm,
                  'goal':goal,'contacts':0,'paid':paid,'emergency_rays':61*(20+i%7),
                  'steps':20+i%7-int(candidate)*3,'distance':15+i%3-int(candidate)*2,
                  'wall':.2+.001*(i%5),'scheduler_ms':2. if candidate else 1.})
    return rows


def main():
    gate();target=OUT/'infrastructure';target.mkdir(parents=True,exist_ok=False);started=time.perf_counter()
    payloads=[];records=[]
    for family,size in itertools.product(FAMILIES,(25,33,41)):
        p=generate_test_logged(101,target/'TEST_logs',family=family,width=size,height=size,
            category='moving',persistent='relocate',discovery='occluded',revisit='rare')
        result=admit_test_logged(p,payloads,target/'TEST_logs')
        records.append({'lineage_id':p['lineage_id'],'family':family,'size':size,'attempts':p['attempts'],
            'certificate_steps':len(p['certificate'])-1,'admission':result})
        payloads.append(p)
    # Test transform/endpoint hiding without any protected or reserved signature read.
    p=payloads[0];rotated=np.rot90(p['occupancy']);assert occupancy_hash(rotated)==p['occupancy_hash']
    log=ImmutableLog(target/'TEST_logs/generation');assert len(log.read())==24
    assert len(ImmutableLog(target/'TEST_logs/admission').read())==12
    write(target/'generator_checks.json',{'namespace':'TEST','explicit_seed':101,'payload_count':12,'records':records,
       'inventory_commitment':inventory_commitment(payloads,b'public-TEST-salt-v1'),
       'production_admission_complete':False,'authorized_prior_signatures_available':False,
       'custodian_or_access_control_established':False,'production_population_generated':False,
       'test_salt_not_a_secret_or_access_control':True})
    table=synthetic_table();write(target/'synthetic_outcomes.json',table)
    comparisons={arm:compare(table,arm,'age5',replicates=2000) for arm in ('dao_veto','dao_trigger','dao_route','dao_combined')}
    selected=select_candidate(table);confirmation=select_candidate(table,stage='confirmation',confirmed_candidate=selected['candidate'])
    write(target/'synthetic_analysis.json',native({'role':'SYNTHETIC_ANALYSIS_VALIDATION_ONLY_NO_REAL_WINNER',
       'comparisons':comparisons,'synthetic_selection':selected,'synthetic_confirmation':confirmation}))
    simulations=[]
    for n,rho,q,loss in itertools.product((80,200,800), (0.,.8),(.05,.2),(0.,.03)):
        simulations.append(simulate_completion(n=n,repetitions=1000,correlation=rho,discordance=q,loss=loss,
            seed=2026111411+len(simulations)))
    write(target/'coverage_power.json',{'role':'SYNTHETIC_MONTE_CARLO_NOT_NAVIGATION_EFFICACY',
       'simulations':simulations,'repetitions_per_condition':1000,'conditions':len(simulations),
       'production_sealed_n_chosen':None,'null_NI_boundary_loss':.03,
       'limitations':['Normal approximation evaluated, not universally certified.','Contact and conditional cost power require their own model.',
       'A 200-lineage size is not automatically sufficient.','Monte Carlo interval error is material at1000 repeats.']})
    costs=[simulate_conditional_cost(n=n,reduction=red,skew=skew,seed=2026111412+i) for i,(n,red,skew) in enumerate(itertools.product((80,200),(0.,.1,.2),(.2,.8)))]
    rng=np.random.default_rng(2026111413);observed=rng.binomial(200,.01,size=10000);upper={int(k):contact_upper(int(k),200) for k in np.unique(observed)}
    write(target/'conditional_cost_contact_checks.json',{'conditional_cost_scenarios':costs,'contact_n':200,'contact_true_risk':.01,'contact_repetitions':10000,'contact_upper_bound_coverage':float(np.mean([upper[int(k)]>=.01 for k in observed])),'conditional_cost_simulations_are_not_joint_navigation_power':True})
    write(target/'summary.json',{'status':'COMPLETE_TEST_AND_SYNTHETIC_ONLY','test_generator_payloads':12,
        'statistical_table_lineages':80,'simulation_conditions':len(simulations),'wall_seconds':time.perf_counter()-started})
    manifest(target);print('Completed12 TEST generator payloads and',len(simulations),'synthetic coverage/power conditions.')
if __name__=='__main__':main()
