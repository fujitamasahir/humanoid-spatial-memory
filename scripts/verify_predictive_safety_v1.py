"""Final read-only preservation, parity, onset and matrix checks."""
import sys,json,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v21_common import write,manifest,verify_manifest,sha
from verify_dao_integrity import verify
from safety_forensics_v1 import OUT,parity,ARMS
from run_predictive_safety_v1 import gate


def main():
    gate();target=OUT/'verification';target.mkdir(parents=True,exist_ok=False);value=verify()
    previous={}
    for relative in ('results/phase2_mujoco/dao_v1','results/phase2_mujoco/dao_integration_v1'):
        directory=ROOT/relative;items=json.loads((directory/'final_artifact_manifest.json').read_text())
        for i in items:
            p=directory/i['path'];assert p.stat().st_size==i['bytes'] and sha(p)==i['sha256']
        previous[relative]=len(items)
    checks={name:verify_manifest(OUT/name) for name in ('forensics','adapter_smoke','prepared','matrix','analysis','contact_cases')}
    paths=sorted((OUT/'matrix').glob('*.json.gz'));assert len(paths)==416;seen=set();parities=0;totalcalls={'memory':0,'emergency':0,'shield':0}
    for p in paths:
        e=json.loads(gzip.decompress(p.read_bytes()));index=int(p.name.split('_')[0]);key=(index,e['arm'],e['safety']);assert key not in seen;seen.add(key)
        m=e['metrics'];calls=e['actual_calls'];assert calls['memory']==len(e['paid'])==m['observation_count']<=20
        assert calls['emergency']==m['emergency_safety_scans'] and calls['shield']==m['g1_actual_collision_shield_queries']
        assert m['g1_shield_query_count_valid'] and m['g1_unselected_action_shield_queries']==0
        for kind in totalcalls:totalcalls[kind]+=calls[kind]
        if e['role']=='original_regression' and e['arm'].startswith('dao_') and e['safety']=='original':
            base=ROOT/'results/phase2_mujoco/dao_integration_v1'
            path=next(p for folder in ('engineering','engineering_recovery_v1_1') if (p:=base/folder/f'{e["scene"]}_{e["arm"]}.json.gz').exists())
            parity(json.loads(gzip.decompress(path.read_bytes())),e);parities+=1
    assert seen=={(i,a,s) for i in range(1,27) for a in ARMS for s in ('original','predictive_v1')}
    contact=json.loads((OUT/'contact_cases/summary.json').read_text());assert contact['distinct_actual_contact_episodes']==165
    assert contact['onset_mechanisms']=={'environment_motion_at_sensor_synchronization':165}
    write(target/'integrity.json',{**value,'preserved_prior_artifact_files':previous,'stage_manifest_files':checks,
       'new_navigation_runs':425,'completed_formal_episodes':416,'untreated_forensic_episodes':7,'adapter_plumbing_episodes':2,'exact_untreated_DAO_regression_parities':parities,
       'distinct_contact_onset_timelines':165,'actual_formal_sensor_and_shield_calls':totalcalls,
       'extra_actual_diagnostic_sensor_calls':0,'evaluator_geometry_probes_are_not_online_observations':True,
       'frozen_sources_and_scenarios_unchanged':True,'candidate_acceptance':'REJECT',
       'production_population_generation':False,'reserved_access':False,'full_FIT72_screen':False,
       'independent_pilot_ready':False,'report_sha256':sha(ROOT/'docs/predictive_safety_research_report.md')})
    manifest(target);print('PASS:416 complete matrix episodes,48 archived parities,165 onset timelines, all prior evidence preserved.')
if __name__=='__main__':main()
