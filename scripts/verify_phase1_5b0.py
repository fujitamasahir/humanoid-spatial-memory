"""Read-only artifact verification and exhaustive small-graph reference checks."""
from collections import Counter
import gzip
import hashlib
from itertools import permutations
import json
from pathlib import Path
import sys
from time import perf_counter
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory import phase15_generators as gen
from spatial_memory import phase15_topology as top


def digest(data): return hashlib.sha256(data).hexdigest()


def flood_distance(free,start,goal):
    """Independent level-set flood, not the production deque implementation."""
    frontier={start}; seen=set(); depth=0
    while frontier:
        if goal in frontier: return depth
        seen.update(frontier)
        frontier={(x+dx,y+dy) for x,y in frontier for dx,dy in ((-1,0),(0,-1),(1,0),(0,1))
                  if (x+dx,y+dy) in free}-seen
        depth+=1
    return None


def verify_world(body):
    data=body['geometry']; free=set(map(tuple,data['free']))
    assert all(1<=x<=23 and 1<=y<=23 for x,y in free)
    assert len(free)>=80 and .15<=1-len(free)/625<=.85
    start=tuple(data['start']); goal=tuple(data['goal'])
    distance=flood_distance(free,start,goal)
    assert distance==data['distance'] and 12<=distance<=40
    assert abs(start[0]-goal[0])+abs(start[1]-goal[1])>=5
    for schedule in data['schedules']:
        blocked=set(map(tuple,schedule['initial']))
        assert not {start,goal}&blocked and flood_distance(free-blocked,start,goal) is not None
        events=schedule['events']
        for event in events:
            cell=tuple(event['cell']); assert cell in free and cell not in (start,goal)
            assert 2<=event['step']<=12
            if event['action']=='remove': blocked.remove(cell)
            else: blocked.add(cell)
        assert flood_distance(free-blocked,start,goal) is not None
        if schedule['category']=='moving':
            positions=list(map(tuple,schedule['positions']))
            assert len(positions)==81 and set(positions)<=free-{start,goal}
            assert all(abs(a[0]-b[0])+abs(a[1]-b[1])<=1 for a,b in zip(positions,positions[1:]))
        if schedule['category'] in ('addition','removal','swap'):
            footprint=list(map(tuple,schedule['footprint']))
            assert len(footprint)==schedule['length'] in (2,3,4)
            assert len(set(footprint))==len(footprint)
            assert all(abs(a[0]-b[0])+abs(a[1]-b[1])==1 for a,b in zip(footprint,footprint[1:]))


def independent_reference(graph):
    """All orders, no production serializer/refinement/pruning."""
    candidates=[]
    for labels in permutations(range(len(graph))):
        diagonal=tuple(graph[u][u] for u in labels)
        edges=tuple(graph[labels[i]][labels[j]] for i in range(len(graph)) for j in range(i+1,len(graph)))
        candidates.append((len(graph),)+diagonal+edges)
    return min(candidates) if candidates else (0,)


def main():
    output=ROOT/'results/phase1_5b0'
    provenance=json.loads((output/'provenance.json').read_text())
    for path,expected in provenance['source_sha256'].items():
        assert digest((ROOT/path).read_bytes())==expected,path
    historical=json.loads((output/'historical_integrity.json').read_text())
    for path,expected in historical['initial_tracked_result_sha256'].items():
        assert digest((ROOT/path).read_bytes())==expected,path
    assert sum(historical['regression_counts'].values())==2212
    archive=json.loads((output/'trace_storage_manifest.json').read_text())
    manifest=json.loads((output/'development_manifest.json').read_text())
    accepted={row['identity'] for row in manifest['records']}
    verified=[]; categories=Counter()
    for record in archive['records']:
        packed=Path(record['path']).read_bytes()
        assert len(packed)==record['bytes'] and digest(packed)==record['sha256']
        body=json.loads(gzip.decompress(packed)); data=body['geometry']
        geo=gen.geometry(data['partition'],data['mechanism'],data['seed'],v_tie_rule='lex_yx')
        graph,detail=top.raster_quotient(geo.free)
        assert graph.matrix==tuple(map(tuple,body['matrix'])) and detail==body['topology']
        assert set(map(tuple,data['free']))==geo.free
        if record['identity'] in accepted:
            start,goal,distance=gen.choose_pair(geo)
            schedules=[gen.dynamic_schedule(geo,start,goal,s,retry_rule='fixed') for s in (0,1)]
            replay=gen.artifact(geo,start,goal,distance,schedules)
            assert gen.canonical_bytes(replay)==gen.canonical_bytes(data)
            verify_world(body)
            categories.update(s['category'] for s in schedules)
        # Do not rerun failed 75-node canonicalization. Its result is explicitly absent.
        verified.append(dict(identity=record['identity'],checksum=True,geometry_replay=True,
                             complete_world=record['identity'] in accepted))
    inventory=[json.loads(line) for line in gzip.decompress((output/'candidate_inventory.jsonl.gz').read_bytes()).splitlines()]
    assert len({row['identity'] for row in inventory})==len(inventory)
    rejected_replay=0
    for row in inventory:
        if row['outcome'] in ('connectivity','voronoi_seed_separation'):
            try: gen.geometry(row['partition'],row['mechanism'],row['seed'],v_tie_rule='lex_yx')
            except gen.Rejected as error: assert str(error)==row['outcome']; rejected_replay+=1
            else: raise AssertionError('Rejection replay changed')
    history_rows=json.loads((output/'historical_topology.json').read_text())
    history_index=top.IndependenceIndex(); history_exact=Counter()
    for row in history_rows:
        graph=top.Graph(tuple(map(tuple,row['matrix'])))
        keys=top.near_certificates(graph)
        exact=tuple(row['exact']); assert top.exact_certificate(graph)==exact
        history_exact[exact]+=1
        history_index.admit(partition='historical',mechanism='historical',keys=keys,exact=exact,
                            raster=(row['identity'],),lineage=row['identity'],identity=row['identity'])
    historical_relations=dict(raw_geometries=len(history_rows),exact_classes=len(history_exact),
                              exact_collision_pairs=sum(n*(n-1)//2 for n in history_exact.values()),
                              transitive_near_lineage_components=len(history_index.clusters('historical')),
                              component_sizes=sorted((len(c) for c in history_index.clusters('historical')),reverse=True))
    scaling=[]; comparisons=0
    for n in range(1,6):
        edges=[(a,b) for a in range(n) for b in range(a+1,n)]
        canonical_seconds=reference_seconds=0.
        for mask in range(1<<len(edges)):
            g=top.graph_from_edges(n,[edge for i,edge in enumerate(edges) if mask&(1<<i)])
            start=perf_counter(); actual=top.exact_certificate(g); canonical_seconds+=perf_counter()-start
            start=perf_counter(); expected=independent_reference(g.matrix); reference_seconds+=perf_counter()-start
            assert actual==expected,(n,mask)
            comparisons+=1
        scaling.append(dict(vertices=n,graphs=1<<len(edges),exact_seconds=canonical_seconds,
                            exhaustive_reference_seconds=reference_seconds))
    xml_path=ROOT/'results/runs/phase1_5b0_test_evidence/full_suite.xml'
    suite=ET.parse(xml_path).getroot().find('testsuite')
    tests=dict(tests=int(suite.attrib['tests']),failures=int(suite.attrib['failures']),
               errors=int(suite.attrib['errors']),skipped=int(suite.attrib['skipped']),seconds=float(suite.attrib['time']),
               xml_sha256=digest(xml_path.read_bytes()))
    assert tests['failures']==tests['errors']==0
    report=dict(scope='artifact verification; existing regression test exception recorded',
                source_and_historical_hashes_match=True,historical_regression_records=2212,
                archive_records=verified,rejected_candidates_replayed=rejected_replay,
                accepted_dynamic_categories=dict(categories),unique_candidate_identities=len(inventory),
                independent_small_graph_comparisons=comparisons,scaling=scaling,full_suite=tests,
                historical_relation_summary=historical_relations,
                historical_metadata_scope=dict(
                    machine_flag='benchmark/results.json contains no scenario arrays',
                    source_review='scripts/benchmark_phase1_4a.py defines public ternary memory workloads, not world scenarios',
                    benchmark_source_sha256=digest((ROOT/'scripts/benchmark_phase1_4a.py').read_bytes()),
                    no_true_benchmark_layout_inferred=True,
                    stored_physical_scenario_geometries_audited=110,
                    reserved_historical_held_out_not_opened=True),
                verifier_sha256=digest(Path(__file__).read_bytes()),
                new_policy_experiment_episodes=0,assessment_or_held_out_generated=False,
                failed_canonicalization_retried=False)
    (output/'independent_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
