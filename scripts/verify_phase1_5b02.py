"""Independent archive, candidate-order and topology-union reconstruction.

No navigation/policies. Replays artifact constructors only to verify identities.
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results/phase1_5b02'
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'scripts'))
from spatial_memory import phase15_generators as gen
from spatial_memory import phase15_topology as top
from spatial_memory.phase15_nauty import Backend,NAMESPACE
from audit_phase1_5b0 import historical_geometries
from verify_phase1_5b0 import verify_world


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    start=perf_counter(); summary=json.loads((OUT/'summary.json').read_text())
    pre=json.loads((OUT/'preflight.json').read_text())
    for path,expected in pre['source_sha256'].items(): assert sha(ROOT/path)==expected,path
    for group in ('source_sha256','immutable_files_sha256'):
        for path,expected in json.loads((ROOT/'results/phase1_5b01/provenance.json').read_text())[group].items():
            assert sha(ROOT/path)==expected,path
    historical=json.loads((ROOT/'results/phase1_5b0/historical_integrity.json').read_text())
    for path,expected in historical['initial_tracked_result_sha256'].items(): assert sha(ROOT/path)==expected,path
    counts={p:len(json.loads((ROOT/p).read_text())['episodes']) for p in historical['regression_counts']}
    assert counts==historical['regression_counts'] and sum(counts.values())==2212
    inventory=[json.loads(line) for line in gzip.decompress((OUT/'candidate_inventory.jsonl.gz').read_bytes()).splitlines()]
    assert len(inventory)==len({r['identity'] for r in inventory})==summary['candidates']
    old=[json.loads(line) for line in gzip.decompress((ROOT/'results/phase1_5b0/candidate_inventory.jsonl.gz').read_bytes()).splitlines()]
    assert [r['identity'] for r in inventory[:4]]==[r['identity'] for r in old]
    assert inventory[1]['outcome']==old[1]['outcome'] and inventory[2]['outcome']==old[2]['outcome']
    archives=json.loads((OUT/'trace_storage_manifest.json').read_text())['records']
    bodies={}; archive_bytes=0
    for row in archives:
        path=Path(row['path']); assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
        assert row['identity'] not in bodies
        json.loads(gzip.decompress(path.read_bytes()))
        bodies[row['identity']]=path; archive_bytes+=row['bytes']
    def read_body(identity): return json.loads(gzip.decompress(bodies[identity].read_bytes()))
    old_storage=json.loads((ROOT/'results/phase1_5b0/trace_storage_manifest.json').read_text())['records']
    for row in old_storage:
        assert sha(row['path'])==row['sha256']
        old_body=json.loads(gzip.decompress(Path(row['path']).read_bytes()))
        new_body=read_body(row['identity'])
        assert new_body['matrix']==old_body['matrix']
        for key in ('free','construction','seed','mechanism','partition'):
            assert new_body['geometry'][key]==old_body['geometry'][key]
        if old_body['geometry']['start'] is not None:
            assert new_body['geometry']==old_body['geometry']
    records=[]; parent=[]; relations=Counter(); checked_variants=0; rejections=Counter(); complete=set()
    transitions=[]; last_credits=None
    def root(i):
        while parent[i]!=i: i=parent[i]
        return i
    def matches(keys,raster,lineage):
        return [i for i,r in enumerate(records) if keys.intersection(r['keys']) or raster==r['raster'] or lineage==r['lineage']]
    def add(identity,part,mechanism,keys,exact,raster,lineage):
        found=matches(keys,raster,lineage)
        if any(records[i]['partition']!=part for i in found): return False,found
        i=len(records); parent.append(i)
        records.append(dict(identity=identity,partition=part,mechanism=mechanism,keys=keys,exact=exact,raster=raster,lineage=lineage))
        for j in found: parent[root(j)]=i
        return True,found
    def credits(part):
        components={}
        for i,r in enumerate(records):
            if r['partition']==part and r['identity'] in complete: components.setdefault(root(i),[]).append(i)
        return Counter(records[min(v)]['mechanism'] for v in components.values())
    backend=Backend(); history_grids,_,_,_=historical_geometries()
    history_rows=json.loads((OUT/'historical_topology.json').read_text())
    try:
        for row in history_rows:
            graph=top.Graph(tuple(map(tuple,row['matrix'])))
            keys=backend.near_certificates(graph); exact=backend.exact_certificate(graph)
            assert exact==tuple(row['exact']) and len(keys)==row['near_count']
            width,height,free=history_grids[row['identity']]
            add(row['identity'],'historical','historical',keys,exact,top.raster_certificate(free,width,height),row['identity'])
        cursor=Counter(); expected_part='fit'; round_index=0
        order=list(gen.MECHANISMS)
        for event in inventory:
            part=event['partition']; mechanism=event['mechanism']
            # Independently simulate original under-quota round-robin order.
            while True:
                if all(credits(expected_part)[m]>=gen.PARTITIONS[expected_part][1] for m in order):
                    expected_part=list(gen.PARTITIONS)[list(gen.PARTITIONS).index(expected_part)+1]; round_index=0
                candidate=order[round_index%4]; round_index+=1
                if credits(expected_part)[candidate]<gen.PARTITIONS[expected_part][1]: break
            assert (part,mechanism)==(expected_part,candidate)
            seed=gen.seed_for(part,mechanism,cursor[(part,mechanism)]); cursor[(part,mechanism)]+=1
            assert event['seed']==seed and event['identity']==f'{part}:{mechanism}:{seed}'
            checkpoint=ROOT/'results/raw/phase1_5b02_development/checkpoints'/(event['identity'].replace(':','_')+'.json')
            assert json.loads(checkpoint.read_text())==event
            try: geo=gen.geometry(part,mechanism,seed,v_tie_rule='lex_yx')
            except gen.Rejected as error:
                assert event['outcome']==str(error); rejections[str(error)]+=1; continue
            assert event['identity'] in bodies
            body=read_body(event['identity']); graph,detail=top.raster_quotient(geo.free)
            assert body['matrix']==list(map(list,graph.matrix)) and body['topology']==detail
            assert set(map(tuple,body['geometry']['free']))==geo.free
            if 'near_certificates' not in body:
                assert summary['stop'] is not None and event['outcome'] in ('BackendFailure','CanonicalizationLimit')
                continue
            measured=[]; keys=backend.near_certificates(graph,measurements=measured)
            checked_variants+=len(measured); exact=backend.exact_certificate(graph)
            assert keys==frozenset(map(tuple,body['near_certificates'])) and exact==tuple(body['exact'])
            assert all(key[0]==NAMESPACE for key in keys)
            raster=top.raster_certificate(geo.free); lineage=f'{mechanism}:{seed}'
            found=matches(keys,raster,lineage)
            if found:
                assert event['matches']==[records[i]['identity'] for i in found]
                expected='cross_partition_or_historical' if any(records[i]['partition']!=part for i in found) else 'same_partition_related'
                assert event['outcome']==expected
                relations[expected]+=1
                relations['historical_exclusion_events']+=int(any(records[i]['partition']=='historical' for i in found))
                relations['other_development_partition_events']+=int(any(records[i]['partition'] not in (part,'historical') for i in found))
                relations['exact_match_events']+=int(any(records[i]['exact']==exact for i in found))
                relations['near_only_match_events']+=int(all(records[i]['exact']!=exact for i in found))
                add(event['identity'],part,mechanism,keys,exact,raster,lineage)
            else:
                if event['outcome']=='DynamicLimit':
                    assert summary['stop'] is not None; continue
                assert event['outcome']=='independent'
                s,g,d=gen.choose_pair(geo)
                schedules=[gen.dynamic_schedule(geo,s,g,j,retry_rule='fixed') for j in (0,1)]
                assert gen.canonical_bytes(gen.artifact(geo,s,g,d,schedules))==gen.canonical_bytes(body['geometry'])
                verify_world(body); complete.add(event['identity'])
                add(event['identity'],part,mechanism,keys,exact,raster,lineage)
            now=dict(credits(part))
            if now!=last_credits:
                transitions.append(dict(identity=event['identity'],outcome=event['outcome'],credits=now))
                last_credits=now
            if sum(cursor.values())%500==0: print('Verified',sum(cursor.values()),'candidate identities',flush=True)
    finally: backend.close()
    reconstructed={part:{m:credits(part)[m] for m in order} for part in gen.PARTITIONS}
    assert all(reconstructed[p]==summary['partitions'][p]['counts'] for p in reconstructed)
    manifest=json.loads((OUT/'development_manifest.json').read_text())
    independent=[]
    for part in gen.PARTITIONS:
        groups={}
        for i,r in enumerate(records):
            if r['partition']==part: groups.setdefault(root(i),[]).append(i)
        for members in groups.values():
            candidates=[i for i in members if records[i]['identity'] in complete]
            if candidates: independent.append((records[min(candidates)]['identity'],[records[i]['identity'] for i in members]))
    assert dict(independent)=={r['identity']:r['cluster_members'] for r in manifest['records']}
    if summary['stop'] and summary['stop']['reason']=='candidate_limit':
        assert cursor[(summary['stop']['partition'],summary['stop']['mechanism'])]==10000
    assert archive_bytes==summary['bulk_bytes']
    metrics=json.loads(gzip.decompress((OUT/'canonicalization_measurements.json.gz').read_bytes()))
    storage=json.loads((OUT/'measurement_storage.json').read_text())
    assert sha(storage['original_path'])==storage['original_sha256']
    assert sha(ROOT/storage['compact_path'])==storage['compact_sha256']
    assert Path(storage['original_path']).read_bytes()==gzip.decompress((ROOT/storage['compact_path']).read_bytes())
    assert all(r['status']=='certified' and r['seconds']<=5 and r['peak_rss_kib']<=524288 for r in metrics)
    for path,expected in pre['source_sha256'].items(): assert sha(ROOT/path)==expected
    result=dict(all_checks_pass=True,verifier_sha256=sha(Path(__file__)),
        historical_regression_records=2212,historical_regression_counts=counts,
        old_evidence_unchanged=True,candidate_records=len(inventory),unique_identities=True,
        original_four_identities_preserved=True,original_B_V_rejections_preserved=True,
        original_two_geometry_archives_preserved=True,
        candidate_order_reconstructed=True,candidate_checkpoints_verified=len(inventory),
        geometry_rejections_replayed=dict(rejections),archives_verified=len(archives),
        archived_bytes=archive_bytes,candidate_variants_recomputed=checked_variants,
        independent_union_counts=reconstructed,independent_clusters=len(independent),
        match_events=dict(relations),historical_geometries=len(history_rows),
        cluster_credit_transitions=transitions,
        component_member_sizes=sorted((len(members) for _,members in independent),reverse=True),
        historical_exact_classes=len({tuple(r['exact']) for r in history_rows}),
        historical_near_components=len({root(i) for i,r in enumerate(records) if r['partition']=='historical'}),
        complete_worlds_verified=len(complete),measured_near_canonical_calls=len(metrics),
        additional_guarded_self_calls=len(history_rows)+len(archives),
        maximum_measured_near_canonical_seconds=max(r['seconds'] for r in metrics),
        maximum_worker_peak_rss_kib=max(r['peak_rss_kib'] for r in metrics),
        elapsed_seconds=perf_counter()-start,new_navigation_episodes=0,
        namespace=NAMESPACE,source_freeze_unchanged=True)
    result['verification_memory_strategy']='Stream archive bodies; preliminary eager-load attempt failed worker resource-evidence check before candidate reconstruction; audit not rerun'
    (OUT/'independent_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
