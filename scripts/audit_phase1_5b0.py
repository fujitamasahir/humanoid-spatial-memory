"""Development-only environment artifact audit; never runs navigation policies."""
import argparse
from collections import Counter
import csv
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory import phase15_generators as gen
from spatial_memory import phase15_topology as top

HISTORICAL_RESULTS=(
    'results/representative/results.json',
    'results/phase1_1/development/results.json','results/phase1_1/diagnostic/results.json',
    'results/phase1_2/development/results.json','results/phase1_3/development/results.json',
    'results/phase1_3/corridor_diagnostic/results.json')
STORED_METADATA=HISTORICAL_RESULTS+(
    'results/phase1_4a/manifests/tuning.json','results/phase1_4a/manifests/assessment.json',
    'results/phase1_4a/smoke/results.json','results/phase1_4a/benchmark/results.json')


def sha(data): return hashlib.sha256(data).hexdigest()


def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('wb') as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary,path)


def write_json(path,data): atomic(path,json.dumps(data,sort_keys=True,indent=2).encode()+b'\n')


def source_hashes():
    files=['scripts/audit_phase1_5b0.py','src/spatial_memory/phase15_generators.py',
           'src/spatial_memory/phase15_topology.py','tests/test_phase1_5b0.py',
           'docs/phase1_5a2_generator_specification.md']
    return {p:sha((ROOT/p).read_bytes()) for p in files}


def frozen_inventory():
    # Public tracked results only; no held-out scenario/configuration is opened.
    paths=subprocess.check_output(['git','-c',f'safe.directory={ROOT}','ls-files','results'],cwd=ROOT,text=True).splitlines()
    return {p:sha((ROOT/p).read_bytes()) for p in paths if not p.startswith(('results/phase1_5b0/','results/raw/','results/runs/'))}


def historical_geometries():
    grids={}; sources={}; missing=[]; regressions={}
    for relative in STORED_METADATA:
        payload=json.loads((ROOT/relative).read_text(encoding='utf-8-sig'))
        if relative in HISTORICAL_RESULTS: regressions[relative]=len(payload['episodes'])
        records=[r['scenario'] for r in payload.get('realized_scenarios',[])]
        records.extend(r['scenario'] for r in payload.get('records',[]) if 'scenario' in r)
        # Representative has complete stored configurations, not realized records.
        if relative=='results/representative/results.json':
            records.extend(payload.get('config',{}).get('scenarios',[]))
        if not records:
            missing.append(dict(path=relative,reason='no stored scenario arrays'))
        for scenario in records:
            if scenario.get('split') not in (None,'development'):
                raise ValueError('Reserved historical scenario rejected before use')
            if not {'width','height','walls','obstacles'}<=scenario.keys():
                missing.append(dict(path=relative,reason='incomplete raster metadata')); continue
            width,height=scenario['width'],scenario['height']
            for interpretation,blocked in (
                ('walls_only',scenario['walls']),
                ('walls_plus_initial_objects',scenario['walls']+scenario['obstacles'])):
                walls=set(map(tuple,blocked))
                free=frozenset((x,y) for y in range(height) for x in range(width) if (x,y) not in walls)
                identity=sha(gen.canonical_bytes(dict(width=width,height=height,free=sorted(free,key=gen.row_key))))
                grids[identity]=(width,height,free)
                sources.setdefault(identity,[]).append(dict(path=relative,interpretation=interpretation))
    return grids,sources,missing,regressions


def credits(index,partition,manifest_records):
    result=Counter()
    for cluster in index.clusters(partition):
        accepted=[i for i in cluster if i in manifest_records]
        if accepted: result[index.records[min(accepted)]['mechanism']]+=1
    return result


def run(output,bulk):
    if output.exists() or bulk.exists():
        raise ValueError('Audit outputs must be new; preserve existing evidence')
    output.mkdir(parents=True); bulk.mkdir(parents=True)
    lease=(bulk/'writer.lock').open('w'); fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
    started=perf_counter(); before=frozen_inventory()
    sources=source_hashes()
    provenance=dict(python=sys.version,numpy=gen.np.__version__,platform=platform.platform(),
                    source_sha256=sources,development_only=True,
                    v_tie_rule='lex_yx',event_retry_rule='fixed',
                    resolution='User clarification: lexicographic (y,x); onset/length drawn once',
                    candidate_limit=10000,dynamic_proposal_limit=128,
                    canonical_node_limit=100000,canonical_seconds_limit=5,
                    scan_order='fit/calibration/selection; repeated R,B,V,M, one underquota candidate per round')
    write_json(output/'provenance.json',provenance)
    events=[]; archived=[]; measurements=[]; index=top.IndependenceIndex()
    manifest_records={}; historical_records=[]; stop=None
    partitions={p:dict(target=gen.PARTITIONS[p][1]*4,counts={m:0 for m in gen.MECHANISMS},status='not_started') for p in gen.PARTITIONS}
    histories,history_sources,missing,regressions=historical_geometries()
    if sum(regressions.values())!=2212: raise ValueError('Historical inventory count changed')
    write_json(output/'historical_integrity.json',dict(regression_counts=regressions,total=2212,
               input_geometries=len(histories),metadata_missing=missing,permitted_paths=list(STORED_METADATA),
               initial_tracked_result_sha256=before))
    try:
        for identity,(width,height,free) in sorted(histories.items()):
            graph,detail=top.raster_quotient(free)
            measured=[]
            try: keys=top.near_certificates(graph,measurements=measured)
            finally:
                measurements.extend(dict(scope='historical',identity=identity,**row) for row in measured)
            exact=top.exact_certificate(graph)
            row=dict(identity=identity,width=width,height=height,detail=detail,
                     matrix=graph.matrix,exact=exact,near_count=len(keys),sources=history_sources[identity])
            historical_records.append(row)
            index.admit(partition='historical',mechanism='historical',keys=keys,exact=exact,
                        raster=top.raster_certificate(free,width,height),lineage=identity,identity=identity)
        print(f'Historical metadata: {len(histories)} raw geometries; {len(index.clusters("historical"))} relation clusters; {len(missing)} missing metadata entries',flush=True)
        for partition in gen.PARTITIONS:
            cursors=Counter(); target=gen.PARTITIONS[partition][1]
            partitions[partition]['status']='running'
            while any(credits(index,partition,manifest_records)[m]<target for m in gen.MECHANISMS):
                for mechanism in gen.MECHANISMS:
                    if credits(index,partition,manifest_records)[mechanism]>=target: continue
                    if cursors[mechanism]>=10000:
                        stop=dict(reason='candidate_limit',partition=partition,mechanism=mechanism)
                        raise gen.DynamicLimit('Frozen 10000 candidate limit reached')
                    seed=gen.seed_for(partition,mechanism,cursors[mechanism]); cursors[mechanism]+=1
                    event=dict(partition=partition,mechanism=mechanism,seed=seed,identity=f'{partition}:{mechanism}:{seed}')
                    begin=perf_counter(); body=None; measured=[]
                    try:
                        geo=gen.geometry(partition,mechanism,seed,v_tie_rule='lex_yx')
                        graph,detail=top.raster_quotient(geo.free)
                        body=dict(geometry=gen.artifact(geo,None,None,None,[]),topology=detail,matrix=graph.matrix)
                        event.update(graph_vertices=graph.n,free_cells=len(geo.free))
                        keys=top.near_certificates(graph,measurements=measured)
                        exact=top.exact_certificate(graph)
                        body.update(exact=exact,near_certificates=sorted(keys))
                        raster=top.raster_certificate(geo.free); lineage=f'{mechanism}:{seed}'
                        matched=index.matches(keys,raster,lineage)
                        if matched:
                            outcome=index.admit(partition=partition,mechanism=mechanism,keys=keys,exact=exact,
                                                raster=raster,lineage=lineage,identity=event['identity'])
                            event.update(outcome=outcome['reason'],matches=[index.records[i]['identity'] for i in outcome['matches']],
                                         exact_matches=len(outcome.get('exact_matches',[])),merged_components=outcome.get('merged_components',0))
                        else:
                            start,goal,distance=gen.choose_pair(geo)
                            schedules=[gen.dynamic_schedule(geo,start,goal,s,retry_rule='fixed') for s in (0,1)]
                            body['geometry']=gen.artifact(geo,start,goal,distance,schedules)
                            outcome=index.admit(partition=partition,mechanism=mechanism,keys=keys,exact=exact,
                                                raster=raster,lineage=lineage,identity=event['identity'])
                            if not outcome['accepted']: raise AssertionError('Unexpected mutation during admission')
                            manifest_records[outcome['record_index']]=body
                            event.update(outcome='independent',distance=distance,start=list(start),goal=list(goal),
                                         dynamic_categories=[s['category'] for s in schedules])
                    except gen.Rejected as error:
                        event.update(outcome=str(error))
                    except (top.CanonicalizationLimit,gen.DynamicLimit,gen.SpecificationAmbiguity) as error:
                        event.update(outcome=type(error).__name__,error=str(error))
                        stop=dict(reason=type(error).__name__,partition=partition,mechanism=mechanism,seed=seed,detail=str(error))
                        raise
                    except Exception as error:
                        event.update(outcome='implementation_error',error=repr(error))
                        stop=dict(reason='implementation_error',partition=partition,mechanism=mechanism,seed=seed,detail=repr(error))
                        raise
                    finally:
                        event['seconds']=perf_counter()-begin
                        measurements.extend(dict(scope='candidate',identity=event['identity'],**row) for row in measured)
                        if body is not None:
                            packed=gzip.compress(gen.canonical_bytes(body),mtime=0)
                            path=bulk/(event['identity'].replace(':','_')+'.json.gz'); atomic(path,packed)
                            event['artifact_sha256']=sha(packed); event['artifact_bytes']=len(packed)
                            archived.append(dict(identity=event['identity'],path=str(path),sha256=sha(packed),bytes=len(packed)))
                        events.append(event)
                        if len(events)%25==0 or stop:
                            print(f'{len(events)} candidates; {partition} credits={dict(credits(index,partition,manifest_records))}; last={event["outcome"]}',flush=True)
                            write_json(output/'progress.json',dict(candidates=len(events),partition=partition,
                                       credits=dict(credits(index,partition,manifest_records)),stop=stop))
            partitions[partition]['status']='complete'
            print(f'{partition} complete: {dict(credits(index,partition,manifest_records))}',flush=True)
    except (top.CanonicalizationLimit,gen.DynamicLimit,gen.SpecificationAmbiguity) as error:
        if stop is None: stop=dict(reason=type(error).__name__,scope='historical',detail=str(error))
        print(f'STOP: {stop}',flush=True)
    finally:
        final=[]
        for partition in gen.PARTITIONS:
            counts=credits(index,partition,manifest_records)
            partitions[partition]['counts']={m:counts[m] for m in gen.MECHANISMS}
            if partitions[partition]['status']=='running': partitions[partition]['status']='stopped'
            for cluster in index.clusters(partition):
                ids=[i for i in cluster if i in manifest_records]
                if not ids: continue
                representative=min(ids); body=manifest_records[representative]; record=index.records[representative]
                final.append(dict(identity=record['identity'],partition=partition,mechanism=record['mechanism'],
                                  seed=body['geometry']['seed'],public_domain=body['geometry']['public_domain'],
                                  distance=body['geometry']['distance'],matrix=body['matrix'],exact=body['exact'],
                                  near_count=len(body['near_certificates']),
                                  cluster_members=[index.records[i]['identity'] for i in cluster],
                                  mechanisms=sorted({index.records[i]['mechanism'] for i in cluster})))
        after=frozen_inventory()
        if before!=after: raise RuntimeError('Historical tracked result bytes changed')
        summary=dict(partitions=partitions,stop=stop,candidates=len(events),
                     outcomes=dict(Counter(e['outcome'] for e in events)),
                     by_partition_mechanism={f'{p}/{m}':dict(attempts=sum(e['partition']==p and e['mechanism']==m for e in events),
                       outcomes=dict(Counter(e['outcome'] for e in events if e['partition']==p and e['mechanism']==m)))
                       for p in gen.PARTITIONS for m in gen.MECHANISMS},
                     independent_clusters=len(final),cross_mechanism_clusters=sum(len(r['mechanisms'])>1 for r in final),
                     historical_geometries_total=len(histories),historical_geometries_certified=len(historical_records),
                     historical_metadata_missing=missing,seconds=perf_counter()-started,
                     peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     bulk_bytes=sum(r['bytes'] for r in archived),navigation_episodes=0,
                     assessment_or_final_generated=False,old_held_out_accessed=False,
                     historical_result_bytes_unchanged=True,regression_records=2212,
                     ready_for_phase1_5c=stop is None and not missing)
        write_json(output/'summary.json',summary)
        write_json(output/'development_manifest.json',dict(provisional=True,records=final,
                   full_protocol_ready=summary['ready_for_phase1_5c'],navigation_authorized=False))
        write_json(output/'historical_topology.json',historical_records)
        write_json(output/'trace_storage_manifest.json',dict(artifact_only=True,archive_root=str(bulk),records=archived))
        atomic(output/'candidate_inventory.jsonl.gz',gzip.compress(b''.join(gen.canonical_bytes(e)+b'\n' for e in events),mtime=0))
        write_json(output/'canonicalization_measurements.json',measurements)
        # Validate every stored payload hash independently of in-memory artifact bodies.
        for record in archived:
            data=Path(record['path']).read_bytes()
            if sha(data)!=record['sha256'] or len(data)!=record['bytes']: raise ValueError('Archive checksum mismatch')
            json.loads(gzip.decompress(data))
        write_json(output/'archive_verification.json',dict(checked=len(archived),all_sha256_match=True,
                   all_payloads_parse=True,frozen_inventory_matches=True))
        fcntl.flock(lease,fcntl.LOCK_UN); lease.close()
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/phase1_5b0')
    parser.add_argument('--bulk',type=Path,default=ROOT/'results/raw/phase1_5b0_development')
    args=parser.parse_args()
    # Never overwrite frozen folders or write bulk artifacts outside ignored storage.
    out=args.output.resolve(); bulk=args.bulk.resolve()
    if out!=ROOT/'results/phase1_5b0' or not bulk.is_relative_to(ROOT/'results/raw'):
        raise ValueError('Only designated new compact output and ignored raw archive admitted')
    result=run(out,bulk)
    print(json.dumps(result,sort_keys=True),flush=True)
