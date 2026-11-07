"""Production exact-backend preflight. Mathematical graphs only, no generators."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'scripts'))
from spatial_memory import phase15_topology as top
from spatial_memory.phase15_nauty import Backend,NAMESPACE
import benchmark_phase1_5b01 as previous


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    paths=['configs/phase15_nauty_backend.json','src/spatial_memory/phase15_nauty.py',
           'src/spatial_memory/phase15_nauty_worker.py','scripts/audit_phase1_5b02.py',
           'scripts/validate_phase1_5b02.py','tests/test_phase1_5b02.py',
           'src/spatial_memory/phase15_generators.py','src/spatial_memory/phase15_topology.py',
           'docs/phase1_5b02_canonicalization_amendment.md']
    return {p:sha(ROOT/p) for p in paths}


def main():
    output=ROOT/'results/phase1_5b02'; output.mkdir(exist_ok=True)
    if (output/'preflight.json').exists(): raise ValueError('Preserve completed preflight')
    xml=ROOT/'results/runs/phase1_5b02_resource_tests.xml'
    suite=ET.parse(xml).getroot().find('testsuite')
    assert int(suite.attrib['tests'])==7 and all(int(suite.attrib[k])==0 for k in ('errors','failures','skipped'))
    old=json.loads((ROOT/'results/phase1_5b0/provenance.json').read_text())
    for p,h in old['source_sha256'].items(): assert sha(ROOT/p)==h,p
    frozen=json.loads((ROOT/'results/phase1_5b0/historical_integrity.json').read_text())
    for p,h in frozen['initial_tracked_result_sha256'].items(): assert sha(ROOT/p)==h,p
    prior=json.loads((ROOT/'results/phase1_5b01/provenance.json').read_text())
    for p,h in prior['immutable_files_sha256'].items(): assert sha(ROOT/p)==h,p
    backend=Backend(); timings=[]; began=perf_counter()
    original=previous.proposal.certificate
    def production(g): return backend.exact_certificate(g)[1:]
    # Reuse immutable fixture enumeration and independent exhaustive oracle;
    # replace ONLY its proposal callable, not old literal/reference functions.
    previous.proposal.certificate=production
    try:
        correctness=previous.correctness()
        assert correctness['total_graphs']==1215
        history=json.loads((ROOT/'results/phase1_5b0/historical_topology.json').read_text())
        relation={}; calls=0
        for row in history:
            g=top.Graph(tuple(map(tuple,row['matrix'])))
            for _,v in previous.variants(g):
                reference=top.exact_certificate(v); key=backend.exact_certificate(v)
                assert relation.setdefault(reference,key)==key
                assert original(v)==key[1:]
                calls+=1
        assert len(set(relation.values()))==len(relation)
        storage=json.loads((ROOT/'results/phase1_5b0/trace_storage_manifest.json').read_text())['records']
        for archive in storage:
            assert sha(archive['path'])==archive['sha256']
            g=top.Graph(tuple(map(tuple,json.loads(gzip.decompress(Path(archive['path']).read_bytes()))['matrix'])))
            measured=[]; start=perf_counter(); keys=backend.near_certificates(g,measurements=measured)
            timings.append(dict(identity=archive['identity'],vertices=g.n,near_seconds=perf_counter()-start,
                calls=len(measured),unique_keys=len(keys),measurements=measured))
            expected=backend.exact_certificate(g)
            for order in (list(reversed(range(g.n))),list(range(1,g.n))+[0]):
                fresh=Backend()
                try: assert fresh.exact_certificate(top.induced(g,order))==expected
                finally: fresh.close()
        assert timings[1]['vertices']==75 and timings[1]['calls']==119 and timings[1]['unique_keys']==80
    finally:
        backend.close(); previous.proposal.certificate=original
    result=dict(all_checks_pass=True,namespace=NAMESPACE,correctness=correctness,
        historical_self_near_comparisons=calls,historical_class_bijection=True,
        preserved_graphs=timings,fresh_process_relabel_checks=4,
        resource_tests=dict(tests=7,all_pass=True,xml_sha256=sha(xml)),
        memory_enforcement_probe=json.loads((ROOT/'results/runs/phase1_5b02_memory_probe.json').read_text()),
        failure_probes=[json.loads(p.read_text()) for p in sorted((ROOT/'results/runs/phase1_5b02_failure_probes').glob('*.json'))],
        source_sha256=sources(),dependency_pin_sha256=sha(ROOT/'configs/phase15_nauty_backend.json'),
        elapsed_seconds=perf_counter()-began,old_node_guard_claimed=False,
        five_second_parent_timeout=True,hard_address_space_bytes=512*1024*1024,
        new_navigation_episodes=0,old_evidence_unchanged=True)
    (output/'preflight.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('all_checks_pass','historical_self_near_comparisons','elapsed_seconds')}))


if __name__=='__main__': main()
