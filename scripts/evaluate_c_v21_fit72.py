"""Fail-closed conditional C v2.1 smoke/full descriptive FIT screen."""
from __future__ import annotations
import argparse,gzip,json,sys
from collections import Counter
from c_v21_common import ROOT,OUT,write,manifest,verify_manifest,sha,commit
from c_v21_navigation import run_case
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_c_v2_candidate_coverage_fit72 as fit
import evaluate_event_observation_fit72 as ref
from spatial_memory.multistep_evi import ARMS


def require_gate():
    result=json.loads((OUT/'synthetic/results.json').read_text())
    review=json.loads((OUT/'gate_review.json').read_text())
    binding=json.loads((OUT/'protocol_binding.json').read_text())
    if result['numeric_gate']['status']!='PASS' or review['status']!='ACCEPTED_FOR_FIT' or not review['FIT_authorized'] or review['result_sha256']!=sha(OUT/'synthetic/results.json'):raise RuntimeError('Synthetic/conformance gate blocks navigation')
    if any(sha(ROOT/n)!=s for n,s in binding['source_sha256'].items()):raise RuntimeError('Frozen source drift blocks navigation')
    verify_manifest(OUT/'synthetic');verify_manifest(OUT/'reference_replays')
    if json.loads((OUT/'environment/verification.json').read_text())['status']!='PASS' or json.loads((OUT/'reference_replays/summary.json').read_text())['status']!='PASS_EXACT_ALL_360_REFERENCE_REPLAYS':raise RuntimeError('Migration/reference compatibility gate failed')


def flatten(n,arm,row,diag):
    flat=fit.flat(arm,row,diag)
    for k in list(flat):
        if k.startswith('evi_'):flat.pop(k)
    decisions=diag['decisions'];reasons=Counter(d.get('reason','budget_exhausted' if d['used_before']>=20 else 'not_scored') for d in decisions)
    flat.update(episode=n,identity=row['world_identity'],schedule=row['schedule'],
        contact_free_success=bool(row['success'] and row['g1_unwanted_contact_pairs']==0),
        visibility_computations=sum(d.get('visibility_computations',0) for d in decisions),
        future_visibility_computations=sum(d.get('future_visibility_computations',0) for d in decisions),
        prefix_step_visits=sum(d.get('prefix_step_visits',0) for d in decisions),
        recovery_checks=sum(d.get('recovery_checks',0) for d in decisions),
        estimated_net_value_mean=sum(d.get('net_value',0) for d in decisions)/len(decisions) if decisions else None,
        authorization_reasons=json.dumps(dict(reasons),sort_keys=True),
        unselected_shield_queries=row['g1_unselected_action_shield_queries'])
    return flat


def run(smoke):
    require_gate() # Always before any new-policy FIT-store access.
    fit.verify_original_data_integrity()
    target=OUT/('fit_smoke2' if smoke else 'fit72')
    if not smoke:
        verify_manifest(OUT/'fit_smoke2')
        if json.loads((OUT/'fit_smoke2/summary.json').read_text())['status']!='PASS_SMOKE':raise RuntimeError('Two-case smoke gate failed')
    target.mkdir(parents=True,exist_ok=False)
    _,_,prov,_=ref.base.load_baseline();config=ref.base.frozen_config(prov)
    worlds={p['identity']:p for p in ref.navigation.admitted_worlds()}
    write(target/'provenance.json',{'source_commit':commit(),'binding_sha256':sha(OUT/'protocol_binding.json'),'review_sha256':sha(OUT/'gate_review.json'),'same_machine_references':'../reference_replays','config':config,'FIT_is_descriptive_not_independent':True})
    rows=[]
    for n in range(1,3 if smoke else 73):
        saved=json.load(gzip.open(OUT/f'reference_replays/episode_{n:03}_age.json.gz','rt'))
        identity,schedule,_,seed=saved['trace']['key']
        for arm in ARMS:
            row,trace,diag=run_case(worlds[identity],schedule,arm,config)
            if smoke and int(row['g1_unwanted_contact_pairs'])!=0:raise RuntimeError('Smoke unwanted contact')
            if not smoke and n<=2:
                old=json.load(gzip.open(OUT/f'fit_smoke2/episode_{n:03}_{arm}.json.gz','rt'))
                if ref.rdao_evaluator._signature(row)!=ref.rdao_evaluator._signature(old['row']):raise RuntimeError('Full/smoke metric mismatch')
                ref._compare_trace(old['trace'],ref.base._jsonable_row(trace))
            fit.save_episode(target,n,arm,row,trace,diag)
            rows.append(flatten(n,arm,row,diag))
        if smoke or n%6==0:print(f'{"Smoke" if smoke else "FIT"} {n}/{2 if smoke else 72} keys, four new arms',flush=True)
    fit.verify_original_data_integrity()
    fit.csv_write(target/'episodes.csv',rows)
    write(target/'summary.json',{'status':'PASS_SMOKE' if smoke else 'COMPLETED_DESCRIPTIVE_FIT_NOT_VALIDATION','keys':2 if smoke else 72,'episodes':len(rows),'arms':{a:{'goals':sum(r['success'] for r in rows if r['arm']==a),'contact_free_goals':sum(r['contact_free_success'] for r in rows if r['arm']==a),'paid_scans':sum(r['paid_memory_scans'] for r in rows if r['arm']==a),'h80_steps':sum(r['elapsed_steps'] for r in rows if r['arm']==a),'unwanted_contacts':sum(r['unwanted_contacts'] for r in rows if r['arm']==a)} for a in ARMS},'preserved_phase15':ref.navigation.verify_preserved_prefix()})
    manifest(target)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--smoke',action='store_true');args=p.parse_args();run(args.smoke)
