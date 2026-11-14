"""Final read-only evidence verification; never simulates or changes policies."""
import hashlib,subprocess,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest,sha
from raa_preservation_v1 import verify_prior
from run_raa_fit72_v1 import OUT,OLD,ARMS,REFERENCES,gate
from run_c_v21a_depth_ablation import episode,parity

def main():
    gate();before=json.loads((OUT/'prior_preservation.json').read_text());after=verify_prior()
    for k in ('prior_manifest_issues','nonstandard_manifests_preserved','prior_manifest_records_checked','unique_prior_files_hashed'):
        assert before[k]==after[k],k
    for record in after['prior_manifests']:
        original=subprocess.check_output(['git','show','9333928aa52acb24d42b739549bcaaa8a2180dbc:'+record['path']],cwd=ROOT)
        assert hashlib.sha256(original).hexdigest()==record['sha256'],record['path']
    manifests={str(p.parent.relative_to(OUT)):verify_manifest(p.parent) for p in OUT.rglob('artifact_manifest.json')}
    count=0;refs=0;smoke_matches=0;totals={a:{'goals':0,'paid':0,'contacts':0} for a in ARMS}
    for stage,size in (('smoke',2),('fit72',72)):
        for n in range(1,size+1):
            for arm in ARMS:
                e=episode(OUT/stage,n,arm);r=e['row'];d=e['diagnostics'];calls=d['actual_memory_call_steps']
                assert len(calls)==r['observation_count']==d['actual_memory_sensor_calls']<=20
                assert calls==r['spatial_memory_observation_steps']
                assert d['actual_memory_raycasts']==61*len(calls)
                assert r['g1_unwanted_contact_pairs']==r['g1_unselected_action_shield_queries']==r['g1_unattempted_collision_queries']==0
                assert r['g1_shield_query_count_valid']
                if arm in REFERENCES:parity(episode(OLD,n,arm),r,e['trace']);refs+=1
                if stage=='fit72':
                    if n<=2:parity(episode(OUT/'smoke',n,arm),r,e['trace']);smoke_matches+=1
                    for key,value in (('goals',int(r['success'])),('paid',r['observation_count']),('contacts',r['g1_unwanted_contact_pairs'])):totals[arm][key]+=value
                count+=1
    root=ET.parse(OUT/'prepared/tests.xml').getroot();suites=list(root.iter('testsuite'))
    assert sum(int(s.attrib['tests']) for s in suites)==137
    assert all(int(s.attrib.get(k,0))==0 for s in suites for k in ('failures','errors','skipped'))
    m=json.loads((OUT/'mechanisms/summary.json').read_text());assert m['defer_exact_navigation_trace_matches_parent']==72 and m['advance_joint_exact_full_trace_matches']==72
    assert len(m['savings'])==2 and all(x['terminal_step'] and x['goal_reached'] for x in m['savings'])
    assert totals['raa_defer']=={'goals':66,'paid':768,'contacts':0}
    target=OUT/'verification';target.mkdir(exist_ok=False)
    after['status']='CORE_PASS_WITH_UNCHANGED_PREEXISTING_ARCHIVAL_ISSUES'
    write(target/'prior_preservation_after.json',after)
    write(target/'summary.json',{'status':after['status'],'verified_stage_manifests':manifests,'actual_episodes':count,'reference_parities':refs,'smoke_full_parities':smoke_matches,'tests_passed':137,'totals':totals,'preexisting_archival_issue_entries':len(after['prior_manifest_issues']),'no_new_archival_issues':True,'prospective_freeze_commit':'d91eee267cd5513027e7dd1679508646608b23a9','immediate_target_met':True,'strong_joint_target_met':False,'additional_revision_run':False})
    manifest(target);print(json.dumps({'episodes':count,'reference_parities':refs,'totals':totals,'status':after['status']},indent=2))
if __name__=='__main__':main()
