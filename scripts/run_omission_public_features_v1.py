"""Read-only public-feature audit joined to frozen single-omission outcomes."""
from __future__ import annotations
import argparse,csv,hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest,sha,commit
from report_predictive_safety_v1 import read
from spatial_memory.omission_public_features_v1 import AuthorizedHistory,diagnostic_rules
OLD=ROOT/'results/phase2_mujoco/deadline_single_omission_v1'
OUT=ROOT/'results/phase2_mujoco/omission_public_features_v1'
BASE='1813cb3c94ff79e12500c01f99991ecf9a539310'
SOURCES=('src/spatial_memory/omission_public_features_v1.py','src/spatial_memory/discovery_observation.py',
 'src/spatial_memory/dao_navigation_compat_v1_1.py','src/spatial_memory/navigation.py',
 'tests/test_omission_public_features_v1.py','scripts/run_omission_public_features_v1.py',
 'docs/omission_public_features_v1_protocol.md')
def load(p):return json.loads(p.read_text())
def files():return {p:sha(ROOT/p) for p in SOURCES}
def csv_write(p,rows):
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def check():
    t=OUT/'prepared';t.mkdir(parents=True,exist_ok=False)
    for p in ('prepared','matrix','analysis'):verify_manifest(OLD/p)
    cmd=[sys.executable,'-m','pytest','-q','tests/test_omission_public_features_v1.py',
        'tests/test_discovery_observation.py','tests/test_route_gated_dao_veto_v1.py','tests/test_deadline_single_omission_v1.py']
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    (t/'tests.log').write_text(p.stdout+p.stderr);print(p.stdout+p.stderr,flush=True)
    write(t/'gate.json',{'returncode':p.returncode,'command':cmd});manifest(t)
    if p.returncode:raise SystemExit(p.returncode)
    write(OUT/'binding.json',{'base':BASE,'source_commit':commit(),'sources':files(),
        'prepared_manifest_sha256':sha(t/'artifact_manifest.json'),
        'old_manifests':{p:sha(OLD/p/'artifact_manifest.json') for p in ('prepared','matrix','analysis')}})
def gate():
    b=load(OUT/'binding.json');verify_manifest(OUT/'prepared')
    assert b['sources']==files() and b['prepared_manifest_sha256']==sha(OUT/'prepared/artifact_manifest.json')
    assert load(OUT/'prepared/gate.json')['returncode']==0
    for p,h in b['old_manifests'].items():
        verify_manifest(OLD/p);assert sha(OLD/p/'artifact_manifest.json')==h
    for p,h in b['sources'].items():
        assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h,p

def audit():
    gate();t=OUT/'audit';t.mkdir(parents=True,exist_ok=False)
    spec=load(OLD/'prepared/schedule.json')
    # Freeze public features before joining any actual omission outcomes.
    rows=[];start=time.perf_counter()
    try:
        for n,d in enumerate(spec['scenarios'],1):
            for safety in ('original','res_h1_phase_wait'):
                e=read(OLD/'matrix'/f'{n:02}_{safety}_base.json.gz')
                h=AuthorizedHistory((d['height'],d['width']))
                dec={x['step']:x for x in e['decisions']}
                sched={x['step']:x for x in e['scheduler_decisions']}
                init=e['trace']['steps'][0];assert init['step']==0
                for r in e['paid']:
                    k=r['step']
                    pose=tuple(init['position'] if k==0 else dec[k]['position'])
                    yaw=init['heading_yaw'] if k==0 else dec[k]['yaw']
                    if k:
                        # No access to this reading until public features are computed.
                        f=h.features(k,pose,yaw,tuple(d['goal']))
                        a=sched[k]
                        assert a['granted'] and f['prior_paid']==a['used_before']
                        assert f['frontier_new']==a['frontier']['new']
                        assert f['frontier_stale']==a['frontier']['stale']
                        assert f['frontier_band_unknown']==a['frontier']['route_new']
                        assert f['route_available']==a['route_available']
                        rows.append({'scene_index':n,'scene':d['family'],'role':d['role'],
                            'safety':safety,'step':k,**f,**{'mask_'+k:v for k,v in diagnostic_rules(f).items()}})
                    h.update(r['reading'],k,pose,yaw)
                assert h.readings==e['actual_calls']['memory']
        assert len(rows)==149
        target_ids={(x['scene_index'],x['safety'],x['step']) for x in spec['targets']}
        assert {(x['scene_index'],x['safety'],x['step']) for x in rows}==target_ids
        write(t/'public_features.json',rows);csv_write(t/'public_features.csv',rows)
        write(t/'summary.json',{'rows':len(rows),'new_navigation':0,'new_sensor_calls':0,
            'elapsed_seconds':time.perf_counter()-start,'outcomes_joined':False})
        manifest(t)
    except Exception:
        (t/'failure.txt').write_text(traceback.format_exc());write(t/'partial.json',{'rows_processed':len(rows)});manifest(t);raise

def report():
    gate();verify_manifest(OUT/'audit');t=OUT/'analysis';t.mkdir(parents=True,exist_ok=False)
    public=load(OUT/'audit/public_features.json')
    outcomes=load(OLD/'analysis/paired.json')
    key=lambda r:(r['scene_index'],r['safety'],r['step'])
    idx={key(r):r for r in outcomes}
    assert len(idx)==len(public)==149 and set(idx)=={key(r) for r in public}
    rows=[]
    for f in public:
        o=idx[key(f)]
        safety_harm=(o['goal_delta']<0 or o['contact_free_goal_delta']<0
                     or o['contact_episode_delta']>0 or o['contact_pair_delta']>0 or o['nonfirst_onset_delta']>0)
        movement_harm=any(o[k] is not None and o[k]>0 for k in ('common_steps_delta','common_distance_delta_m'))
        rows.append({**f,'actual_changed_known_offline':o['actual_changed_known'],
            'actual_new_offline':o['actual_new'],'harm_goal_or_contact':bool(safety_harm),
            'harm_common_movement':bool(movement_harm),'saving_no_worse':o['common_success_observation_saving'],
            'paid_delta':o['paid_delta'],'combined_rays_delta':o['combined_rays_delta']})
    masks=[k for k in public[0] if k.startswith('mask_')]
    groups=defaultdict(list)
    for r in rows:
        groups[r['safety'],'all'].append(r)
        groups[r['safety'],r['role']].append(r)
    metrics=[]
    for (s,role),rr in sorted(groups.items()):
        for m in masks:
            selected=[r for r in rr if r[m]]
            metrics.append({'safety':s,'role':role,'rule':m[5:],'total':len(rr),'selected':len(selected),
                'total_savings':sum(r['saving_no_worse'] for r in rr),
                'savings_selected':sum(r['saving_no_worse'] for r in selected),
                'total_goal_contact_harms':sum(r['harm_goal_or_contact'] for r in rr),
                'goal_contact_harms_selected':sum(r['harm_goal_or_contact'] for r in selected),
                'movement_harms_selected':sum(r['harm_common_movement'] for r in selected),
                'paid_increase_selected':sum(r['paid_delta']>0 for r in selected),
                'combined_rays_increase_selected':sum(r['combined_rays_delta']>0 for r in selected),
                'distinct_scenes_selected':len({r['scene_index'] for r in selected})})
    # Conflicting labels for identical aggregate features: evidence against
    # treating an observed feature signature as an oracle.
    feature_keys=('prior_paid','gap','frontier_new','frontier_stale','previous_changed_known',
        'prefix_unknown','visible_band_unknown','visible_band_stale_occupied','band_recent_changed')
    signatures=defaultdict(list)
    for r in rows:signatures[(r['safety'],*(r[k] for k in feature_keys))].append(r)
    conflicts=[]
    for sig,rr in signatures.items():
        if any(r['saving_no_worse'] for r in rr) and any(r['harm_goal_or_contact'] for r in rr):
            conflicts.append({'signature':list(sig),'rows':[{k:r[k] for k in
                ('scene','step','safety','saving_no_worse','harm_goal_or_contact')} for r in rr]})
    write(t/'joined.json',rows);csv_write(t/'rule_metrics.csv',metrics)
    write(t/'summary.json',{'rows':len(rows),'rules':len(masks),'goal_contact_harms':sum(r['harm_goal_or_contact'] for r in rows),
        'no_worse_savings':sum(r['saving_no_worse'] for r in rows),'conflicting_signatures':conflicts,
        'selection_authorized':False,'navigation_runs':0,'new_sensor_calls':0})
    lines=['# Pre-scan public omission features: retrospective audit','',
      '|Safety|Rule|Selected|No-worse savings|Goal/contact harms|Movement harms|Paid increases|',
      '|---|---|---:|---:|---:|---:|---:|']
    for r in metrics:
        if r['role']!='all':continue
        lines.append(f"|{r['safety']}|{r['rule']}|{r['selected']}|{r['savings_selected']}|{r['goal_contact_harms_selected']}|{r['movement_harms_selected']}|{r['paid_increase_selected']}|")
    lines+=['','All masks are retrospective diagnostics; none is selected for rollout.',
        'A mask with no observed harms is not a safety guarantee. Repeated scans and scenes are correlated.',
        'Realized omitted scan content is joined only after public features were written; no sensing or navigation was rerun.',
        'Multiple omissions are not additive. New independent development environments remain necessary.']
    (t/'research_report.md').write_text('\n'.join(lines)+'\n');manifest(t);print('\n'.join(lines))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('check','audit','report'))
    {'check':check,'audit':audit,'report':report}[p.parse_args().stage]()
