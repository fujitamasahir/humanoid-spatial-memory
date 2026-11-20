"""Independent final evidence audit. No policy navigation or hidden data access."""
import sys,json,hashlib,subprocess,gzip,xml.etree.ElementTree as ET
from collections import Counter
import numpy as np
from h2_final_common import *
from run_h2_final import gate,verify_episode,compare_saved
from verify_dao_integrity import verify as original_integrity
from spatial_memory.dao_admission_v1 import occupancy_hash,endpoint_hash
from h2_generate_maps import H2Identity,H2Stream,raster,bp

def main():
    deadline_guard(120);gate();before=json.loads((OUT/'prior_preservation.json').read_text());checked=0;issues=[]
    # Check only preexisting manifests, so new H2 evidence is never mislabeled old.
    for rec in before['prior_manifests']:
        p=ROOT/rec['path'];assert sha(p)==rec['sha256']
        doc=json.loads(p.read_text());items=doc if isinstance(doc,list) else doc.get('files',[])
        for item in items:
            target=p.parent/item['path']
            if not target.exists() or sha(target)!=item['sha256'] or ('bytes' in item and target.stat().st_size!=item['bytes']):
                issues.append({'manifest':rec['path'],'path':item['path'],'error':'preexisting_manifest_mismatch_or_missing'})
                if target.exists():
                    # Existing mismatches must also remain byte-identical to base.
                    raw=subprocess.check_output(['git','show','2466d17c68cbcbd5add815b05f541a47d1af921c:'+str(target.relative_to(ROOT))],cwd=ROOT)
                    assert hashlib.sha256(raw).hexdigest()==sha(target)
            else:checked+=1
    assert issues==before['prior_manifest_issues'];assert checked==before['prior_manifest_records_checked']
    raa=verify_manifest(ROOT/'results/phase2_mujoco/raa_v1');core=original_integrity()
    stages={};counts={};journals={}
    for stage,num in (('fit_replay',864),('smoke',48),('primary',864),('timing_repeat',864)):
        stages[stage]=verify_manifest(OUT/stage);paths=sorted((OUT/stage).glob('episode_*.json.gz'));assert len(paths)==num
        ledger=[json.loads(l) for l in (OUT/stage/'journal.jsonl').read_text().splitlines()];assert len(ledger)==num and len({x['path'] for x in ledger})==num
        assert all(sha(OUT/stage/x['path'])==x['sha256'] for x in ledger);journals[stage]=len(ledger)
        counts[stage]=Counter()
        for n in range(1,5 if stage=='smoke' else 73):
            for arm in ARMS:
                e=episode(OUT/stage,n,arm);verify_episode(e);r,t=e['row'],e['trace'];counts[stage][arm]+=1
                if stage=='fit_replay':compare_saved(saved_episode(n,arm),r,t)
                if stage=='primary' and n<=4:parity(episode(OUT/'smoke',n,arm),r,t)
                if stage=='timing_repeat':parity(episode(OUT/'primary',n,arm),r,t)
                # Original max80, cap20 and emergency independent of paid requests.
                assert r['elapsed_steps']<=80 and r['max_observations']==20 and r['seed']==42
                assert r['emergency_safety_raycasts']==61*r['elapsed_steps']
    verify_manifest(OUT/'maps');maps=json.loads((OUT/'maps/summary.json').read_text())['maps'];assert len(maps)==36
    families=Counter();identities=set();roots=set();seeds=set();grids=set();keys=set()
    for rec in maps:
        p=json.loads((OUT/'maps'/rec['path']).read_text());assert sha(OUT/'maps'/rec['path'])==rec['sha256'];families[p['mechanism']]+=1
        assert p['partition']=='h2_final_generalization_v1' and p['identity'] not in identities and p['seed'] not in seeds
        identities.add(p['identity']);seeds.add(p['seed']);roots.update(p['ancestral_roots']);a=raster(p['geometry']['free']);h=occupancy_hash(a);assert h not in grids;grids.add(h)
        assert p['admission']['occupancy_hash']==h and p['admission']['endpoint_hash']==endpoint_hash(a,p['world']['start'],p['world']['goal'])
        key=tuple(p['topology']['exact']);assert key not in keys;keys.add(key)
        assert len(p['world']['schedules'])==2 and all(c['path'] for c in p['admission']['G1_static_certificates'])
        assert p['admission']['minimum_prior_free_jaccard_D4']>.05
        # Reconstruct exact frozen draws; this is deterministic verification only.
        streams={};i=H2Identity(p['partition'],p['mechanism'],p['seed'])
        def stream(_,purpose):
            s=H2Stream(i,purpose);streams[purpose]=s;return s
        geo=bp.geometry(i,stream_factory=stream);start,goal,distance=bp.choose_pair(geo.free,stream(i,'start-goal'));schedules=[bp.build_schedule(geo,start,goal,stream(i,f'dynamics-{j}')) for j in (0,1)]
        reconstructed=ref.base._jsonable_row({'start':start,'goal':goal,'distance':distance,'schedules':schedules})
        assert reconstructed==p['world'] and sorted(map(tuple,p['geometry']['free']))==sorted(geo.free)
        assert ref.base._jsonable_row({k:s.counters() for k,s in streams.items()})==p['streams']
    assert families=={'R':12,'BP':12,'M':12} and len(roots)==36
    from h2_generate_maps import prior_inventory
    prior=prior_inventory();oldhashes={p['hash'] for p in prior};oldkeys={tuple(p['topology']['exact']) for p in prior if 'exact' in p['topology']}
    assert not grids&oldhashes and not keys&oldkeys
    # Validate tests and paired/source-analysis scope, not only text claims.
    suites=list(ET.parse(OUT/'tests_final.xml').getroot().iter('testsuite'));assert sum(int(s.attrib['tests']) for s in suites)==163
    assert all(int(s.attrib.get(k,0))==0 for s in suites for k in ('failures','errors','skipped'))
    verify_manifest(OUT/'analysis');analysis=json.loads((OUT/'analysis/summary.json').read_text());assert analysis['primary_policy_episodes']==864 and analysis['lineages']==36
    for arm in ARMS:
        rows=[episode(OUT/'primary',n,arm)['row'] for n in range(1,73)];s=analysis['summary'][arm]
        assert s['goals']==sum(r['success'] for r in rows) and s['paid_total']==sum(r['observation_count'] for r in rows)
        assert s['contacts_total']==sum(r['g1_unwanted_contact_pairs'] for r in rows)
    verify_manifest(OUT/'interpretation');verify_manifest(OUT/'final_report')
    report=ROOT/'docs/h2_final_research_report.md';assert report.read_bytes()==(OUT/'final_report/research_report.md').read_bytes()
    target=OUT/'verification';target.mkdir(exist_ok=False)
    write(target/'summary.json',{'status':'PASS_WITH_UNCHANGED_20_PREEXISTING_ARCHIVAL_ISSUE_ENTRIES','original_integrity':core,'original_integrity_scope':'Read-only historical helper; new_navigation_runs=0 inside that helper describes verifier activity only, not the H2 execution.','old_manifest_entries_unchanged':checked,'old_archival_issues_unchanged':issues,'prior_RAA_recursive_entries_unchanged':raa,'stages':stages,'episode_counts':{k:dict(v) for k,v in counts.items()},'journal_entries':journals,'exact_FIT_reproductions':864,'smoke_primary_parities':48,'timing_repeat_parities':864,'primary_independent_map_lineages':36,'primary_correlated_cases':72,'primary_policy_episodes':864,'timing_repeats_not_independent':864,'tests_passed':163,'all36_draws_reconstructed':True,'report_sha256':sha(report),'original_freeze_commit':'4bb5486','backend_recovery_commit':'f60de27','portfolio_unchanged':True,'reserved_or_sealed_data_used':False})
    manifest(target);print('PASS: full evidence, original data,864 exact FIT +48 smoke +864 primary +864 repeat; all36 map draws reproduced.',flush=True)
if __name__=='__main__':main()
