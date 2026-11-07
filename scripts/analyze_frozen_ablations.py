"""Independent saved-trace ledgers and diagnostic paired analysis; no policy execution."""
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from spatial_memory.ablation_spec import (preflight, FROZEN_ABLATIONS, PARAMETERS,
    CAPS, NOISES, original_snapshot, BASE_COMMIT)
from spatial_memory.assessment_store import atomic_bytes, canonical_bytes
from spatial_memory.tuning_spec import EPISODE_CONFIG, file_sha256
from spatial_memory.manifests import digest
from spatial_memory.simulation import Scenario
from spatial_memory.observation import line_cells
from analyze_locked_assessment import OUTCOMES, verify_trace, bootstrap_weights

COMPACT = ROOT/'results/phase1_4d'
INACTIVE = ('fixed-rate', 'exclude-unknown', 'no-budget-threshold', 'no-alternative-candidates')


def save_json(name, obj):
    atomic_bytes(COMPACT/name, canonical_bytes(obj))


def save_csv(name, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v,sort_keys=True) if isinstance(v,(dict,list,tuple)) else v for k,v in row.items()})
    atomic_bytes(COMPACT/name, stream.getvalue().encode())


def signature(result):
    fields = ('position','memory','planned','executed','received_observation','blocked','moved','errors')
    return digest([{k:f[k] for k in fields} for f in result['frames']])


def verify_decisions(bundle):
    """Reconstruct public-history probabilities, gating and movement from saved observations."""
    result = bundle['result']
    job = bundle['job']
    fs = result['frames']
    memory = np.array(fs[0]['memory'], dtype=np.int8)
    last = np.where(memory>=0, 0, -1)
    flips = np.zeros(memory.shape)
    exposure = np.zeros(memory.shape)
    samples = []
    components = []
    for f in fs[1:]:
        step = f['step']
        d = f['policy_details']
        ablation = job['ablation']
        rate = .05 if ablation == 'fixed-rate' else np.clip((.3+flips)/(6+exposure), .01, .35)
        probability = .5 + np.where(memory==1,1.,-1.)*.45*np.exp(-2*rate*np.maximum(0,step-last))
        probability[last<0] = .5
        assert np.allclose(probability,d['probabilities'],atol=2e-15,rtol=0)
        position = tuple(f['observation_position'])
        x0,y0 = position
        disk = [(x,y) for x in range(memory.shape[1]) for y in range(memory.shape[0])
                if (x-x0)**2+(y-y0)**2<=9]
        visibility = {}
        for x,y in disk:
            blockers = sorted(set(line_cells(position,(x,y)))-{position,(x,y)})
            value = 1.
            for x1,y1 in blockers:
                value *= 1-probability[y1,x1]
            visibility[(x,y)] = (1. if ablation=='no-visibility' else value,
                                 any(last[y1,x1]<0 for x1,y1 in blockers))
        assert len(d['visibility'])==len(disk)
        for item,(x,y) in zip(d['visibility'],disk):
            assert item['cell']==[x,y]
            assert abs(item['probability']-visibility[(x,y)][0])<2e-14
            assert item['unknown_blocker']==visibility[(x,y)][1]
        eligible = [c for c in disk if c!=position]
        if ablation=='exclude-unknown':
            eligible = [(x,y) for x,y in eligible if last[y,x]>=0]
        if ablation=='no-alternative-candidates':
            eligible = [c for c in eligible if list(c) in d['route']]
        assert [c['cell'] for c in d['candidates']]==[list(c) for c in eligible]
        score = mass = 0.
        for c in d['candidates']:
            x,y = c['cell']
            risk = probability[y,x] if memory[y,x]==0 else 1-probability[y,x] if memory[y,x]==1 else .5
            disruption = 1. if ablation=='no-route-disruption' else min(memory.size,abs(c['costs'][1]-c['costs'][0]))/memory.size
            v = visibility[(x,y)][0]
            assert abs(c['risk']-risk)<2e-15 and c['disruption']==disruption
            assert abs(c['visibility']-v)<2e-14
            score += v*risk*disruption
            mass += v
        assert abs(score-f['observation_score'])<2e-12
        assert abs(mass-d['visible_mass'])<2e-12
        threshold = PARAMETERS['disruption_threshold']*1.5
        assert f['threshold']==threshold
        request = bool(eligible) and score>threshold and mass>=.25
        assert f['observation_requested']==request
        assert f['observation_granted']==(request and f['remaining_budget']>0)
        assert f['scheduler_astar_calls']==1+2*len(eligible)
        assert f['policy_details']['ablation']==ablation
        obs = f['received_observation']
        if obs is not None:
            obs = np.array(obs)
            for item in d['visibility']:
                x,y = item['cell']
                samples.append(dict(step=step,**item,visible=int(obs[y,x]>=0)))
            visible = obs>=0
            repeated = visible & (last>=0)
            flips[repeated] += obs[repeated]!=memory[repeated]
            exposure[repeated] += step-last[repeated]
            memory[visible] = obs[visible]
            last[visible] = step
        assert np.array_equal(memory,f['memory'])
        # Verify blocked/moved flags from the saved plan and evaluator occupancy.
        planned = f['planned']
        target = tuple(planned[1]) if len(planned)>1 else position
        blocked = False
        if target!=position:
            assert abs(target[0]-x0)+abs(target[1]-y0)==1
            x,y = target
            blocked = not (0<=x<memory.shape[1] and 0<=y<memory.shape[0])
            if not blocked:
                blocked = bool(f['geometry'][y][x] or f['people'][y][x])
        assert f['blocked']==blocked
        assert tuple(f['position'])==(position if blocked else target)
        assert f['moved']==(not blocked and target!=position)
        components.append(dict(score=score,threshold=threshold,visible_mass=mass,
                               candidates=len(eligible),request=request,granted=f['observation_granted'],
                               mean_disruption=float(np.mean([c['disruption'] for c in d['candidates']])) if eligible else 0.,
                               mean_risk=float(np.mean([c['risk'] for c in d['candidates']])) if eligible else 0.,
                               mean_visibility=float(np.mean([c['visibility'] for c in d['candidates']])) if eligible else 0.))
    assert samples==result['feasibility_samples']
    m = result['metrics']
    assert len(samples)==m['feasibility']['samples']
    if samples:
        assert abs(np.mean([(s['probability']-s['visible'])**2 for s in samples])-m['feasibility']['brier'])<1e-12
        assert abs(np.mean([abs(s['probability']-s['visible']) for s in samples])-m['feasibility']['mae'])<1e-12
    for metric,field in [('scheduler_seconds','scheduler_seconds'),('diagnostic_seconds','diagnostic_seconds'),
                         ('scheduler_astar_seconds','scheduler_astar_seconds')]:
        assert abs(m[metric]-sum(f[field] for f in fs[1:]))<1e-10
    assert abs(m['common_planner_seconds']-sum(f['common_planner_seconds'] for f in fs))<1e-10
    if len(fs)>1:
        assert m['scheduler_latency_median']==float(np.median([f['scheduler_seconds'] for f in fs[1:]]))
        assert m['scheduler_latency_p95']==float(np.percentile([f['scheduler_seconds'] for f in fs[1:]],95))
    return components


def expected_jobs(manifest):
    """Independently construct the fixed matrix without the producer's jobs/make_job."""
    expected = {}
    for r in manifest['records']:
        for cap in (4,8):
            for noise in (0.,.05):
                for ablation in ('no-route-disruption','no-visibility','fixed-rate','exclude-unknown',
                                 'no-budget-threshold','no-alternative-candidates'):
                    j = {k:r[k] for k in ('environment_sha256','layout_sha256','family','seed')}
                    j.update(schema='phase1.4d-job-v1',method='disruption-visible',cap=cap,noise=noise,
                             replicate=0,ablation=ablation,parameters=PARAMETERS,
                             configuration=dict(max_steps=40,update_interval=2,observation_cost=1.5,
                                 unknown='optimistic',common_horizon_metrics=True,max_observations=cap,
                                 sensor=dict(radius=3,occlusion=True,noise=noise)))
                    key = hashlib.sha256(json.dumps(j,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    if key in expected:
                        raise ValueError('Duplicate independent expected job')
                    expected[key] = dict(episode_id=key,**j)
    if len(expected)!=1680:
        raise ValueError('Incomplete independent matrix')
    return expected


def analyze():
    begin = perf_counter()
    manifest, audit = preflight(ROOT)
    expected = expected_jobs(manifest)
    stored_preflight = json.loads((COMPACT/'preflight.json').read_text())
    assert audit==stored_preflight
    run = json.loads((COMPACT/'run_provenance.json').read_text())
    assert digest(run['identity'])==run['run_id']
    assert digest(list(expected.values()))==run['identity']['config']['job_plan_sha256']
    for name,sha in run['provenance']['source_files_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==sha,name
    rows = {}
    for line in (COMPACT/'episodes.jsonl').read_text().splitlines():
        r=json.loads(line); key=r['episode_id']
        assert key not in rows and key in expected
        assert {k:r[k] for k in expected[key]}==expected[key]
        rows[key]=r
    assert set(rows)==set(expected)
    storage=json.loads((COMPACT/'trace_storage_manifest.json').read_text())
    raw=(ROOT/storage['repository_relative_root']).resolve()
    assert not (raw/'episodes').is_symlink() and not (raw/'receipts').is_symlink()
    assert storage['run_id']==run['run_id']
    assert json.loads((raw/'run.json').read_text())==run
    entries=storage['episodes']
    assert len(entries)==len({e['episode_id'] for e in entries})==1680
    assert {p.name for p in (raw/'episodes').iterdir()}=={k+'.json.gz' for k in expected}
    assert {p.name for p in (raw/'receipts').iterdir()}=={k+'.json' for k in expected}
    scenarios={r['environment_sha256']:Scenario.from_dict(r['scenario']) for r in manifest['records']}
    parent_rows=[json.loads(line) for line in (ROOT/'results/phase1_4c/episodes.jsonl').read_text().splitlines()]
    paired={}
    static={}
    for r in parent_rows:
        if r['method'] in ('disruption-visible','static') and r['cap'] in (4,8):
            (paired if r['method']=='disruption-visible' else static)[(r['environment_sha256'],r['cap'],r['noise'])]=r
    assert len(paired)==len(static)==280
    parent_storage=json.loads((ROOT/'results/phase1_4c/trace_storage_manifest.json').read_text())
    parent_entries={e['episode_id']:e for e in parent_storage['episodes']}
    parent_raw=ROOT/parent_storage['repository_relative_root']
    parent_sig={};static_sig={}
    scientific=[k for k in OUTCOMES if 'seconds' not in k and 'latency' not in k and 'astar' not in k and 'planner' not in k]
    for pool,signatures in ((paired,parent_sig),(static,static_sig)):
        for key,r in pool.items():
            e=parent_entries[r['episode_id']]
            with gzip.open(parent_raw/e['path'],'rt') as stream:b=json.load(stream)
            assert b['result']['metrics']==r['metrics'] and b['run_id']==parent_storage['run_id']
            signatures[key]=signature(b['result'])
    activations=[];components=[];uncompressed=0;checks=0;new_sigs={}
    calibration=defaultdict(lambda:np.zeros(6))
    for index,e in enumerate(entries):
        key=e['episode_id'];j=expected[key];p=raw/e['path']
        assert e['path']=='episodes/'+key+'.json.gz' and not p.is_symlink()
        assert p.stat().st_size==e['compressed_bytes'] and file_sha256(p)==e['sha256']
        receipt=json.loads((raw/'receipts'/(key+'.json')).read_text())
        assert receipt==dict(episode_id=key,sha256=e['sha256'],compressed_bytes=e['compressed_bytes'])
        with gzip.open(p,'rb') as stream:data=stream.read()
        uncompressed+=len(data);b=json.loads(data);result=b['result'];m=result['metrics']
        assert b['run_id']==run['run_id'] and b['job']==j and m==rows[key]['metrics']
        assert m['purpose']=='assessment' and m['ablation']==j['ablation'] and m['replicate']==0
        assert m['method']=='disruption-visible' and m['policy_parameters']==PARAMETERS
        assert m['seed']==j['seed'] and m['max_observations']==j['cap']
        checks+=verify_trace(b,scenarios[j['environment_sha256']])
        cs=verify_decisions(b)
        for sample in result['feasibility_samples']:
            pvalue=sample['probability'];label=sample['visible'];bucket=min(4,int(pvalue*5))
            calibration[(j['ablation'],j['cap'],j['noise'],sample['unknown_blocker'],bucket)]+=np.array(
                [1,pvalue,label,(pvalue-label)**2,abs(pvalue-label),0.])
        for c in cs:
            components.append(dict(ablation=j['ablation'],cap=j['cap'],noise=j['noise'],family=j['family'],**c))
        fs=result['frames'];steps=[f['step'] for f in fs[1:] if f['observation_granted']]
        pairkey=(j['environment_sha256'],j['cap'],j['noise'])
        sig=signature(result);new_sigs[(pairkey,j['ablation'])]=sig
        same_parent=sig==parent_sig[pairkey];same_static=sig==static_sig[pairkey]
        metric_diffs={k:[m[k],paired[pairkey]['metrics'][k]] for k in scientific if m[k]!=paired[pairkey]['metrics'][k]}
        if j['ablation'] in INACTIVE:
            assert same_parent and same_static and not metric_diffs
        activations.append(dict(episode_id=key,environment_sha256=j['environment_sha256'],family=j['family'],
            ablation=j['ablation'],cap=j['cap'],noise=j['noise'],observation_steps=steps,
            first_additional_step=steps[0] if steps else None,additional_observations=len(steps),
            requests=m['observation_requests'],denied=m['observation_requests_denied'],
            same_parent_trajectory=same_parent,same_static_trajectory=same_static,
            differing_parent_metrics=metric_diffs))
        if (index+1)%200==0:
            print(f'Independently reconstructed {index+1}/1680 traces',flush=True)
    assert sum(e['compressed_bytes'] for e in entries)==storage['compressed_bytes']
    save_csv('episodes.csv',[{k:v for k,v in r.items() if k!='metrics'}|r['metrics'] for r in rows.values()])
    save_csv('paired_episode_differences.csv',[dict(episode_id=r['episode_id'],
        parent_episode_id=paired[(r['environment_sha256'],r['cap'],r['noise'])]['episode_id'],
        environment_sha256=r['environment_sha256'],family=r['family'],ablation=r['ablation'],
        cap=r['cap'],noise=r['noise'],
        **{k:r['metrics'][k]-paired[(r['environment_sha256'],r['cap'],r['noise'])]['metrics'][k]
           for k in OUTCOMES}) for r in rows.values()])
    save_json('observation_activation.json',activations)
    records=manifest['records'];families=sorted({r['family'] for r in records})
    weights,cluster_audit=bootstrap_weights(records)
    save_json('layout_cluster_audit.json',cluster_audit)
    indexed={(r['environment_sha256'],r['cap'],r['noise'],r['ablation']):r['metrics'] for r in rows.values()}
    def vectors(ablation,settings,metric):
        av=[];pv=[]
        for r in records:
            env=r['environment_sha256']
            av.append(np.mean([indexed[(env,cap,noise,ablation)][metric] for cap,noise in settings]))
            pv.append(np.mean([paired[(env,cap,noise)]['metrics'][metric] for cap,noise in settings]))
        return np.array(av,float),np.array(pv,float)
    summary=[];contrasts=[];family_table=[];activation_summary=[]
    for ablation in FROZEN_ABLATIONS:
        for settings,label in [([(c,n) for c in CAPS for n in NOISES],'all')]+[([(c,n)],f'cap{c}-noise{n:g}') for c in CAPS for n in NOISES]:
            common=dict(ablation=ablation,setting=label,cap='both' if label=='all' else settings[0][0],
                        noise='both' if label=='all' else settings[0][1])
            selected=[a for a in activations if a['ablation']==ablation and (a['cap'],a['noise']) in settings]
            summary_row={**common,'episodes':len(selected)}
            contrast={**common,'interpretation':'Exploratory diagnostic; descriptive pointwise intervals'}
            # Family-balanced point estimates and globally clustered paired draws.
            diffs=[]
            for metric in OUTCOMES:
                av,pv=vectors(ablation,settings,metric)
                diff=av-pv;diffs.append(diff)
                fm={f:float(np.mean([v for v,r in zip(diff,records) if r['family']==f])) for f in families}
                summary_row[metric]=float(np.mean([np.mean([v for v,r in zip(av,records) if r['family']==f]) for f in families]))
                contrast[metric]=dict(difference=float(np.mean(list(fm.values()))),family_differences=fm,
                    leave_one_family_out={f:float(np.mean([v for g,v in fm.items() if g!=f])) for f in families})
            if weights is not None:
                draws=weights@np.array(diffs).T
                for i,metric in enumerate(OUTCOMES):
                    contrast[metric].update(ci95=list(np.quantile(draws[:,i],[.025,.975])),
                        bootstrap_degenerate=bool(np.ptp(draws[:,i])==0))
            summary.append(summary_row);contrasts.append(contrast)
            activation_summary.append(dict(**common,episodes=len(selected),
                episodes_with_additional_observations=sum(a['additional_observations']>0 for a in selected),
                fraction_activated=float(np.mean([a['additional_observations']>0 for a in selected])),
                total_additional_observations=sum(a['additional_observations'] for a in selected),
                total_requests=sum(a['requests'] for a in selected),total_denied=sum(a['denied'] for a in selected),
                matches_parent=sum(a['same_parent_trajectory'] for a in selected),
                matches_static=sum(a['same_static_trajectory'] for a in selected),
                contact_free_gains=sum(indexed[(a['environment_sha256'],a['cap'],a['noise'],ablation)]['contact_free_success']
                    and not paired[(a['environment_sha256'],a['cap'],a['noise'])]['metrics']['contact_free_success'] for a in selected),
                contact_free_losses=sum(not indexed[(a['environment_sha256'],a['cap'],a['noise'],ablation)]['contact_free_success']
                    and paired[(a['environment_sha256'],a['cap'],a['noise'])]['metrics']['contact_free_success'] for a in selected),
                grant_step_counts=dict(sorted(Counter(t for a in selected for t in a['observation_steps']).items())),
                first_additional_step_counts=dict(sorted(Counter(a['first_additional_step'] for a in selected if a['first_additional_step'] is not None).items()))))
        for cap in CAPS:
            for noise in NOISES:
                for family in families:
                    ms=[indexed[(r['environment_sha256'],cap,noise,ablation)] for r in records if r['family']==family]
                    family_table.append(dict(ablation=ablation,cap=cap,noise=noise,family=family,
                        **{k:float(np.mean([m[k] for m in ms])) for k in OUTCOMES}))
    save_csv('summary.csv',summary);save_csv('per_family.csv',family_table)
    save_json('paired_comparisons.json',contrasts)
    flat=[{k:c[k] for k in ('ablation','setting','cap','noise')}|dict(metric=k,difference=v['difference'],
        ci95_lower=v.get('ci95',[None,None])[0],ci95_upper=v.get('ci95',[None,None])[1],
        bootstrap_degenerate=v.get('bootstrap_degenerate')) for c in contrasts for k,v in c.items() if k in OUTCOMES]
    save_csv('paired_comparisons.csv',flat);save_json('activation_summary.json',activation_summary)
    component_table=[]
    for ablation in FROZEN_ABLATIONS:
        for cap in CAPS:
            for noise in NOISES:
                cs=[c for c in components if c['ablation']==ablation and c['cap']==cap and c['noise']==noise]
                component_table.append(dict(ablation=ablation,cap=cap,noise=noise,decisions=len(cs),
                    mean_score=float(np.mean([c['score'] for c in cs])),max_score=max(c['score'] for c in cs),
                    threshold=.6,mean_visible_mass=float(np.mean([c['visible_mass'] for c in cs])),
                    mean_candidates=float(np.mean([c['candidates'] for c in cs])),
                    mean_disruption=float(np.mean([c['mean_disruption'] for c in cs])),
                    mean_disagreement=float(np.mean([c['mean_risk'] for c in cs])),
                    mean_visibility=float(np.mean([c['mean_visibility'] for c in cs])),
                    score_failed=sum(c['score']<=c['threshold'] for c in cs),
                    visibility_failed=sum(c['visible_mass']<.25 for c in cs),
                    empty_candidates=sum(c['candidates']==0 for c in cs),
                    requested=sum(c['request'] for c in cs),granted=sum(c['granted'] for c in cs)))
    save_csv('trigger_components.csv',component_table)
    save_csv('feasibility_calibration.csv',[dict(ablation=k[0],cap=k[1],noise=k[2],
        blocker='unknown' if k[3] else 'all_known',bin=k[4],samples=int(v[0]),
        mean_prediction=v[1]/v[0],fraction_visible=v[2]/v[0],brier=v[3]/v[0],mae=v[4]/v[0])
        for k,v in sorted(calibration.items())])
    controls=[]
    for method in ('disruption-visible','static','quota-periodic','random-quota','periodic1'):
        for cap in CAPS:
            for noise in NOISES:
                per_env=[]
                for r in records:
                    ms=[p['metrics'] for p in parent_rows if p['environment_sha256']==r['environment_sha256']
                        and p['method']==method and p['cap']==cap and p['noise']==noise]
                    assert len(ms)==(5 if method=='random-quota' else 1)
                    per_env.append({k:float(np.mean([m[k] for m in ms])) for k in OUTCOMES[:4]})
                controls.append(dict(method=method,cap=cap,noise=noise,
                    **{k:float(np.mean([m[k] for m in per_env])) for k in OUTCOMES[:4]}))
    save_csv('assessment_context_controls.csv',controls)
    for outcome,ylabel in [('contact_free_success','Contact-free goal completion'),('success','Goal completion')]:
        fig,axes=plt.subplots(1,2,figsize=(13,5),sharey=True)
        for ax,noise in zip(axes,NOISES):
            for ablation in FROZEN_ABLATIONS:
                ts=[next(t for t in summary if t['ablation']==ablation and t['cap']==cap and t['noise']==noise) for cap in CAPS]
                ax.plot([t['observation_cost'] for t in ts],[t[outcome] for t in ts],marker='o',label=ablation)
                if ablation=='no-route-disruption':
                    for cap,t in zip(CAPS,ts):ax.annotate(f'cap{cap}',(t['observation_cost'],t[outcome]),fontsize=8)
            p=[c for c in controls if c['method']=='disruption-visible' and c['noise']==noise]
            ax.scatter([t['observation_cost'] for t in p],[t[outcome] for t in p],marker='x',s=70,c='black',label='Locked parent / Static')
            ax.set(xlabel='Mean observation cost',ylabel=ylabel,title=f'Noise {noise:g}',ylim=(0,1));ax.grid(alpha=.2)
        axes[-1].legend(bbox_to_anchor=(1.02,1),loc='upper left',fontsize=8)
        fig.tight_layout();fig.savefig(COMPACT/(outcome+'_cost.png'),dpi=160);plt.close(fig)
    sessions=[json.loads(p.read_text()) for p in sorted(raw.glob('session-*.json'))]
    assert sum(s['executed_this_session'] for s in sessions)==1680
    assert all(s['run_id']==run['run_id'] and s['recovery_actions']==0 for s in sessions)
    assert sessions[0]['already_completed']==0 and sessions[-1]['completed']==1680
    assert all(a['completed']==b['already_completed'] for a,b in zip(sessions,sessions[1:]))
    assert not list((raw/'staging').iterdir())
    assert original_snapshot(ROOT)==stored_preflight['original_file_sha256']
    report=dict(status='verified',episodes=1680,trace_checksums_verified=1680,
        missing_records=0,duplicate_records=0,independently_reconstructed_metric_values=checks,
        reconstructed_decisions=len(components),source_files_verified=len(run['provenance']['source_files_sha256']),
        parent_assessment_trace_checksums_reverified=13440,original_files_unchanged=True,
        historical_records_unchanged=2212,locked_parameter_sha256=audit['parameter_lock_sha256'],
        four_inactive_controls_verified=True,inactive_episode_pairs=1120,
        bootstrap=cluster_audit,sessions=sessions,storage_root=raw.resolve().as_posix(),
        compressed_bytes=storage['compressed_bytes'],uncompressed_json_bytes=uncompressed,
        execution_checkpoint_seconds=sum(s['session_seconds'] for s in sessions),
        independent_verification_analysis_seconds=perf_counter()-begin,
        no_policy_episodes_executed_by_verifier=True,
        interpretation='Exploratory diagnostic ablations; original confirmatory comparison unchanged.')
    save_json('independent_verification.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    analyze()
