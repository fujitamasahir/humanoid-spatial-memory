"""Read-only supplemental comparison; never executes an episode."""
from collections import Counter
import gzip,hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
new=[json.loads(l) for l in (R/'results/phase1_4d/episodes.jsonl').read_text().splitlines()]
old=[json.loads(l) for l in (R/'results/phase1_4c/episodes.jsonl').read_text().splitlines()]
key=lambda r:(r['environment_sha256'],r['cap'],r['noise'])
parents={key(r):r for r in old if r['method']=='disruption-visible' and r['cap'] in (4,8)}
periodic={key(r):r for r in old if r['method']=='periodic1' and r['cap'] in (4,8)}
sn=json.loads((R/'results/phase1_4d/trace_storage_manifest.json').read_text())
so=json.loads((R/'results/phase1_4c/trace_storage_manifest.json').read_text())
en={e['episode_id']:e for e in sn['episodes']};eo={e['episode_id']:e for e in so['episodes']}
fields=('position','memory','planned','executed','received_observation','blocked','moved','errors')
def trace_sig(s,e):
    p=R/s['repository_relative_root']/e['path']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256']
    with gzip.open(p,'rt') as f:fs=json.load(f)['result']['frames']
    digest=hashlib.sha256(json.dumps([{k:f[k] for k in fields} for f in fs],sort_keys=True).encode()).hexdigest()
    return digest,[f['step'] for f in fs if f['observation_granted']]
skip=('scheduler','diagnostic','planner','astar','runtime','latency')
excluded={'method','purpose','ablation','policy_parameters','feasibility','schedule'}
count=0;metric_keys=None
for r in new:
    if r['ablation']!='no-route-disruption':continue
    p=periodic[key(r)];a=r['metrics'];b=p['metrics']
    selected=[k for k in a if k not in excluded and not any(w in k for w in skip)]
    assert all(a[k]==b[k] for k in selected)
    assert trace_sig(sn,en[r['episode_id']])==trace_sig(so,eo[p['episode_id']])
    assert a['observation_requests']==a['elapsed_steps']
    count+=1;metric_keys=selected
activated=[]
for r in new:
    if r['ablation']=='no-visibility' and r['metrics']['observation_count']>1:
        m=r['metrics'];p=parents[key(r)]['metrics']
        activated.append({k:r[k] for k in ('family','seed','cap','noise','environment_sha256','layout_sha256')}|
                         dict(cf_before=p['contact_free_success'],cf_after=m['contact_free_success'],
                              goal_before=p['success'],goal_after=m['success']))
report=dict(episodes=count,exact_periodic1_scientific_metrics=True,exact_periodic1_full_trace_signatures=True,
            exact_observation_steps=True,all_decisions_request_observation=True,verified_metric_fields=metric_keys,
            no_visibility_activated_pairs=activated,
            no_visibility_unique_activated_environments=len({r['environment_sha256'] for r in activated}),
            no_visibility_unique_activated_layouts=len({r['layout_sha256'] for r in activated}),
            audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            interpretation='Read-only saved-record comparison; no new policy episodes.')
(R/'results/phase1_4d/periodic1_equivalence.json').write_text(
    json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report,indent=2))
