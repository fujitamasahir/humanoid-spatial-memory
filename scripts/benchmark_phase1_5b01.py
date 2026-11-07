"""Reproducible mathematical-only backend comparison; refuses result overwrite."""
import cProfile
import gzip
import hashlib
import inspect
from itertools import combinations, permutations
import json
import os
from pathlib import Path
import platform
import random
import resource
import signal
import subprocess
import sys
from time import perf_counter, process_time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory import phase15_topology as old
from spatial_memory import phase15_exact_bnb as bnb
import phase1_5b01_backend as proposal


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference(matrix):
    n=len(matrix)
    return min(((n,)+tuple(matrix[u][u] for u in p)+tuple(
        matrix[p[i]][p[j]] for i in range(n) for j in range(i+1,n))
        for p in permutations(range(n))),default=(0,))


def variants(g):
    return [('self',old.suppress(g))]+[
        (f'leaf:{u}',old.delete_leaf(g,u)) for u in range(g.n) if g.degree(u)==1]+[
        (f'edge:{u}:{v}',old.contract_edge(g,u,v)) for u,v in g.edges()]


def correctness():
    forward={}; reverse={}; count=0; mismatch=0; witness=None
    def check(g):
        nonlocal count,mismatch,witness
        expected=reference(g.matrix); actual=bnb.exact_certificate(g)
        assert actual==old.exact_certificate(g)==expected
        other=proposal.certificate(g)
        assert reference(g.matrix)==reference(old.induced(g,list(reversed(range(g.n)))).matrix)
        assert proposal.certificate(old.induced(g,list(reversed(range(g.n)))))==other
        assert forward.setdefault(expected,other)==other, 'isomorphic split'
        assert reverse.setdefault(other,expected)==expected, 'nonisomorphic merge'
        if other!=expected:
            mismatch+=1
            if witness is None: witness=dict(matrix=g.matrix,lex_min=expected,proposal=other)
        count+=1
    for n in range(1,6):
        edges=list(combinations(range(n),2))
        for mask in range(1<<len(edges)):
            check(old.graph_from_edges(n,[e for i,e in enumerate(edges) if mask>>i&1]))
    simple=count; rng=random.Random(150150)
    for n in range(1,7):
        for _ in range(15):
            a=[[0]*n for _ in range(n)]
            for i in range(n):
                for j in range(i,n): a[i][j]=a[j][i]=rng.randrange(3)
            check(old.Graph(tuple(map(tuple,a))))
    random_count=count-simple
    for g in (old.graph_from_edges(6,[(i,(i+1)%6) for i in range(6)]),
              old.graph_from_edges(6,[(0,i) for i in range(1,6)]),
              old.graph_from_edges(4,[(0,1)]*3+[(1,2),(2,3),(3,0),(0,0)])):
        check(g)
        for _,v in variants(g): check(v)
    # Preserve exact intersection and transitive/cross-partition semantics.
    index=old.IndependenceIndex()
    def admit(identity,keys,part='fit'):
        return index.admit(partition=part,mechanism='fixture',keys=frozenset(keys),
            exact=(identity,),raster=(identity,),lineage=identity,identity=identity)
    key1=proposal.certificate(old.graph_from_edges(1,[]))
    key2=proposal.certificate(old.graph_from_edges(1,[(0,0)]))
    assert admit('a',{key1})['accepted'] and admit('b',{key2})['accepted']
    assert admit('bridge',{key1,key2})['merged_components']==2
    assert len(index.clusters('fit'))==1
    assert not admit('cross',{key2},'calibration')['accepted']
    assert len(index.records)==3
    return dict(total_graphs=count,simple_graphs=simple,random_multigraphs=random_count,
        distinct_reference_classes=len(forward),relation_bijection=True,
        byte_mismatches=mismatch,first_byte_mismatch=witness,
        independent_oracle=True,reversed_relabel_checks=count,
        near_and_cross_partition_fixtures=True)


def worker(backend,path,near):
    g=old.Graph(tuple(map(tuple,json.loads(Path(path).read_text()))))
    funcs={'old':old.exact_certificate,'bnb':bnb.exact_certificate,'nauty_proposal':proposal.certificate}
    measurements=[]; keys=set(); wall=perf_counter(); cpu=process_time()
    status='certified'
    for operation,v in variants(g) if near else [('self',g)]:
        stats={}; start=perf_counter()
        def timeout(*args): raise old.CanonicalizationLimit('five-second alarm')
        signal.signal(signal.SIGALRM,timeout); signal.setitimer(signal.ITIMER_REAL,5.)
        try:
            key=funcs[backend](v,statistics=stats) if backend!='nauty_proposal' else funcs[backend](v)
            keys.add(key)
        except old.CanonicalizationLimit: status='guard'; break
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            measurements.append(dict(operation=operation,wall_seconds=perf_counter()-start,**stats))
    return dict(backend=backend,status=status,vertices=g.n,near=near,
        wall_seconds=perf_counter()-wall,cpu_seconds=process_time()-cpu,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        planned_variants=len(variants(g)) if near else 1,completed_unique_keys=len(keys),
        measurements=measurements,
        certificate_sha256=hashlib.sha256(json.dumps(sorted(keys)).encode()).hexdigest() if status=='certified' else None,
        native_search_nodes=None if backend=='nauty_proposal' else sum(x.get('nodes',0) for x in measurements))


def main():
    output=ROOT/'results/phase1_5b01'; raw=ROOT/'results/runs/phase1_5b01_benchmarks'
    output.mkdir(exist_ok=False); raw.mkdir(exist_ok=False)
    old_paths=list((ROOT/'results/phase1_5b0').glob('*'))
    old_paths += [ROOT/p for p in json.loads((ROOT/'results/phase1_5b0/historical_integrity.json').read_text())['initial_tracked_result_sha256']]
    initial={str(p.relative_to(ROOT)):sha(p) for p in old_paths if p.is_file()}
    archives=json.loads((ROOT/'results/phase1_5b0/trace_storage_manifest.json').read_text())['records']
    for row in archives: assert sha(row['path'])==row['sha256']
    m=old.Graph(tuple(map(tuple,json.loads(gzip.decompress(Path(archives[1]['path']).read_bytes()))['matrix'])))
    assert m.n==75
    report=correctness(); print('Independent correctness complete',flush=True)
    history=json.loads((ROOT/'results/phase1_5b0/historical_topology.json').read_text())
    history_map={}; historical_calls=0
    for row in history:
        g=old.Graph(tuple(map(tuple,row['matrix'])))
        assert old.exact_certificate(g)==tuple(row['exact'])==bnb.exact_certificate(g)
        for _,v in variants(g):
            lex=old.exact_certificate(v); assert bnb.exact_certificate(v)==lex
            native=proposal.certificate(v)
            assert history_map.setdefault(lex,native)==native
            historical_calls+=1
    assert len(set(history_map.values()))==len(history_map)
    report['historical_variant_comparisons']=historical_calls
    report['historical_near_class_bijection']=True
    (output/'correctness.json').write_text(json.dumps(report,indent=2)+'\n')
    fixtures={'preserved_M_75':m,
        'preserved_R_11':old.Graph(tuple(map(tuple,json.loads(gzip.decompress(Path(archives[0]['path']).read_bytes()))['matrix'])))}
    for n in (8,16,32,75):
        fixtures[f'path_{n}']=old.graph_from_edges(n,[(i,i+1) for i in range(n-1)])
        fixtures[f'cycle_{n}']=old.graph_from_edges(n,[(i,(i+1)%n) for i in range(n)])
    fixtures['clique_16']=old.graph_from_edges(16,list(combinations(range(16),2)))
    fixtures['star_32']=old.graph_from_edges(32,[(0,i) for i in range(1,32)])
    fixtures['loops_parallel_6']=old.graph_from_edges(6,[(0,0),(1,1)]+[(i,i+1) for i in range(5)]*2)
    results=[]
    for name,g in fixtures.items():
        path=raw/(name+'.json'); path.write_text(json.dumps(g.matrix))
        for backend in ('old','bnb','nauty_proposal'):
            for near in (False,True) if name in ('preserved_M_75','preserved_R_11','loops_parallel_6') else (False,):
                result=subprocess.run([sys.executable,__file__,'--worker',backend,str(path),str(int(near))],
                    capture_output=True,text=True,timeout=30 if near and backend=='nauty_proposal' else 8)
                assert result.returncode==0,result.stderr
                row=json.loads(result.stdout); row['fixture']=name; results.append(row)
                print(name,backend,'near' if near else 'self',row['status'],round(row['wall_seconds'],4),flush=True)
    (output/'benchmarks.json').write_text(json.dumps(results,indent=2)+'\n')
    # Instrument the old cache without editing its frozen source. Separate from timings.
    source=inspect.getsource(old.exact_certificate).replace(
        'statistics.update(vertices=graph.n,nodes=visited,seconds=perf_counter()-started)',
        'statistics.update(vertices=graph.n,nodes=visited,seconds=perf_counter()-started,cache_hits=search.cache_info().hits,cache_misses=search.cache_info().misses,cache_entries=search.cache_info().currsize)')
    namespace=vars(old).copy(); exec(source,namespace); stats={}; profile=cProfile.Profile()
    profile.enable()
    try: namespace['exact_certificate'](m,statistics=stats)
    except old.CanonicalizationLimit: pass
    finally: profile.disable()
    profile.dump_stats(str(raw/'old_M_profile.pstats'))
    functions=[]
    for entry in profile.getstats():
        if not isinstance(entry.code,str):
            functions.append(dict(function=entry.code.co_name,line=entry.code.co_firstlineno,
                                  calls=entry.callcount,recursive_calls=entry.reccallcount,
                                  total_seconds=entry.totaltime,own_seconds=entry.inlinetime))
    aut=proposal.pynauty.autgrp(proposal.encode(m))
    diagnostics=dict(old_profile_statistics=stats,profile_functions=sorted(functions,key=lambda r:-r['own_seconds'])[:15],
        M=dict(vertices=m.n,nonloop_pairs=len(m.edges()),leaves=sum(m.degree(i)==1 for i in range(m.n)),
            loops=sum(m.matrix[i][i] for i in range(m.n)),degree_counts={d:sum(m.degree(i)==d for i in range(m.n)) for d in sorted({m.degree(i) for i in range(m.n)})},
            automorphism_group_mantissa=aut[1],automorphism_group_exponent=aut[2],encoded_vertex_orbits=aut[4],
            original_vertex_orbits=len(set(aut[3][:m.n])),planned_near_calls=len(variants(m))))
    (output/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2)+'\n')
    for p,h in initial.items(): assert sha(ROOT/p)==h,p
    historical=json.loads((ROOT/'results/phase1_5b0/historical_integrity.json').read_text())
    assert sum(historical['regression_counts'].values())==2212
    provenance=dict(base_commit='2ed8393b715ffc66036258678fda0e1f98155e41',python=sys.version,
        platform=platform.platform(),pynauty=proposal.pynauty.__version__,
        source_sha256={p:sha(ROOT/p) for p in ['scripts/benchmark_phase1_5b01.py','scripts/phase1_5b01_backend.py','src/spatial_memory/phase15_exact_bnb.py','tests/test_phase1_5b01.py']},
        isolated_dependency_sha256={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'results/runs/phase1_5b01_dependencies').rglob('*') if p.is_file() and p.suffix in ('.so','.py')},
        immutable_files_sha256=initial,historical_regression_counts=historical['regression_counts'],
        historical_regression_records=2212,original_archives_verified=2,
        new_development_candidates=0,new_navigation_episodes=0,assessment_held_out_generated=False,
        representation_proposal_adopted=False,development_audit_started=False,
        reason='Literal v0.2 backends fail M guard; v0.3 representation requires scientific review',
        fixture_sha256={str(p.relative_to(ROOT)):sha(p) for p in raw.glob('*.json')},
        profile_sha256=sha(raw/'old_M_profile.pstats'))
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print('DONE: no new artifact audit authorized by literal-backend results',flush=True)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':
        print(json.dumps(worker(sys.argv[2],sys.argv[3],bool(int(sys.argv[4])))))
    else: main()
