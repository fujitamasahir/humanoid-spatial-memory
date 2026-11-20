"""Frozen TEST-only connectivity correction and optional conservative analysis."""
import json,sys,subprocess,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import write,manifest,sha,commit
from spatial_memory.dao_generator_v1_1 import generate_test_logged,FAMILIES,bfs
from spatial_memory.dao_admission_v1 import admit_test_logged,inventory_commitment
from spatial_memory.dao_statistical_bounds_v1_1 import bounded_mean,conservative_components


def main():
    sources=('src/spatial_memory/dao_generator_v1_1.py','src/spatial_memory/dao_statistical_bounds_v1_1.py',
       'tests/test_dao_generator_connectivity_v1_1.py','tests/test_dao_statistical_bounds_v1_1.py',
       'scripts/check_dao_corrections_v1_1.py','docs/dao_generator_v1_1_recovery.md')
    for p in sources:
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==sha(ROOT/p)
    out=ROOT/'results/phase2_mujoco/dao_integration_v1/corrections_v1_1';out.mkdir(parents=True,exist_ok=False)
    records=[];payloads=[]
    for family in FAMILIES:
        for size in (25,33,41):
            p=generate_test_logged(101,out/'TEST_logs',family=family,width=size,height=size,
                discovery='occluded',revisit='rare',category='moving',persistent='relocate')
            free={(x,y) for y,row in enumerate(p['occupancy']) for x,v in enumerate(row) if v==0}
            assert len(bfs(free,min(free)))==len(free)
            result=admit_test_logged(p,payloads,out/'TEST_logs')
            records.append({'lineage':p['lineage_id'],'connected':True,'island_applied':p['occlusion_island_applied'],
              'island_rejected_connectivity':p['occlusion_island_rejected_for_connectivity'],'admission':result})
            payloads.append(p)
    write(out/'generator_validation.json',{'source_commit':commit(),'records':records,'namespace':'TEST:v1_1',
        'original_v1_payloads_retained':12,'new_v1_1_TEST_payloads':12,'production_payloads':0,
        'inventory_commitment':inventory_commitment(payloads,b'public-TEST-v1_1-salt')})
    rows=json.loads((ROOT/'results/phase2_mujoco/dao_integration_v1/infrastructure/synthetic_outcomes.json').read_text())
    write(out/'conservative_synthetic_components.json',conservative_components(rows,'dao_veto','age5'))
    results=[];rng=np.random.default_rng(2026111415)
    for n in (200,2181,10000):
        for q in (.05,.2):
            for loss in (0.,.03):
                covered=ni=0
                for _ in range(1000):
                    a=rng.choice([-1.,0.,1.],n,p=[(q+loss)/2,1-q,(q-loss)/2])
                    b=rng.choice([-1.,0.,1.],n,p=[(q+loss)/2,1-q,(q-loss)/2]);b=np.where(rng.random(n)<.8,a,b)
                    interval=bounded_mean((a+b)/2,-1,1);covered+=interval['low']<=-loss<=interval['high'];ni+=interval['low']>-.03
                results.append({'n':n,'discordance':q,'schedule_correlation':.8,'true_loss':loss,'repetitions':1000,
                                'coverage':covered/1000,'proposed_NI_probability':ni/1000})
    write(out/'conservative_coverage_power.json',{'method':'finite_sample_Hoeffding','conditions':results,
       'lineages_are_independent_assumption':True,'scientific_margins_not_approved':True,'sealed_n_chosen':None,
       'does_not_validate_joint_compute_or_navigation_efficacy':True})
    write(out/'source_binding.json',{p:sha(ROOT/p) for p in sources});manifest(out)
    print('PASS:12 corrected connected TEST payloads;12 conservative synthetic coverage/power scenarios.')
if __name__=='__main__':main()
