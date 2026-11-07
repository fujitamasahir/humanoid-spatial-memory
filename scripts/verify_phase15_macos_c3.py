"""Read-only Linux/macOS certificate comparison using verified saved graphs.

No generator imports/calls, no historical near-key completion, no inventory seal.
Outputs only a new aggregate macOS validation report; never old artifact files.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spatial_memory import phase15_topology as top
from spatial_memory.phase15_nauty import NAMESPACE
from spatial_memory.phase15_nauty_macos import MacBackend,VALIDATION_NAMESPACE


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root',type=Path,required=True)
    args=parser.parse_args();evidence=args.evidence_root.resolve()
    output=ROOT/'results/phase1_5_bprime_macos/cross_platform_verification.json'
    if output.exists():raise ValueError('Preserve completed validation report')
    out=ROOT/'results/phase1_5b02'
    manifest=out/'trace_storage_manifest.json';inventory=out/'candidate_inventory.jsonl.gz'
    if sha(manifest)!='64624d28cad2a2f5ef83eb6863dcb5c5a4ee5a852231bc7b320a4ab9e94fc355':raise ValueError('Stored manifest changed')
    if sha(inventory)!='4281101d7d1631742f2c59b14b6b1af27409a03e8e07fc648f4a587a040473f6':raise ValueError('Stored candidate ledger changed')
    provisional=evidence/'derived-review/reference-inventory.PROVISIONAL.json'
    provisional_before=sha(provisional)
    archive=evidence/'phase15-original-evidence.tgz'
    if sha(archive)!='00451b854aee9ee4fede4531d1a0896404aa6bcb762e581aead95b4909565c6f':raise ValueError('Transport archive changed')
    backend=MacBackend(validation_only=True);started=perf_counter()
    calls=0;maxwall=0;maxrss=0;cpu=0;class_pairs={};reverse={};history_count=0
    def key(g):
        nonlocal calls,maxwall,maxrss,cpu
        stats={};value=backend.exact_certificate(g,statistics=stats)
        if value[0]!=VALIDATION_NAMESPACE:raise ValueError('Candidate namespace mismatch')
        calls+=1;maxwall=max(maxwall,stats['seconds']);maxrss=max(maxrss,stats['peak_rss_bytes']);cpu+=stats['cpu_seconds']
        return (NAMESPACE,*value[1:])  # comparison projection only; never inserted/sealed
    try:
        # Original stored historical matrices, exact keys only. Enumerated near
        # variants are checked transiently against the independent literal oracle;
        # their missing C3 records are deliberately not written or completed.
        history=json.loads((out/'historical_topology.json').read_text())
        for row in history:
            graph=top.Graph(tuple(map(tuple,row['matrix'])))
            if key(graph)!=tuple(row['exact']):raise ValueError('Historical exact C3 byte mismatch: '+row['identity'])
            variants=[top.suppress(graph)]
            variants += [top.delete_leaf(graph,u) for u in range(graph.n) if graph.degree(u)==1]
            variants += [top.contract_edge(graph,u,v) for u,v in graph.edges()]
            for variant in variants:
                actual=key(variant);literal=top.exact_certificate(variant)
                if class_pairs.setdefault(literal,actual)!=actual or reverse.setdefault(actual,literal)!=literal:
                    raise ValueError('Historical literal/C3 relation disagreement')
                history_count+=1
        rows=json.loads(manifest.read_text())['records'];matched=0;near_values=0
        for row in rows:
            path=evidence/'raw/phase1_5b02_development'/Path(row['path']).name
            if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:raise ValueError('Original archive changed: '+str(path))
            payload=json.loads(gzip.decompress(path.read_bytes()))
            graph=top.Graph(tuple(map(tuple,payload['matrix'])))
            if key(graph)!=tuple(payload['exact']):raise ValueError('Saved exact C3 byte mismatch: '+row['identity'])
            variants=[top.suppress(graph)]
            variants += [top.delete_leaf(graph,u) for u in range(graph.n) if graph.degree(u)==1]
            variants += [top.contract_edge(graph,u,v) for u,v in graph.edges()]
            actual=frozenset(key(g) for g in variants)
            if actual!=frozenset(map(tuple,payload['near_certificates'])):
                raise ValueError('Saved near-key set byte mismatch: '+row['identity'])
            near_values+=len(actual);matched+=1
            if matched%500==0:print(f'Compared {matched}/{len(rows)} stored graphs; no discrepancies',flush=True)
        # Fresh processes on preserved large M, reverse/cyclic labels, old key only.
        m=json.loads(gzip.decompress((evidence/'raw/phase1_5b02_development/fit_M_50030000.json.gz').read_bytes()))
        graph=top.Graph(tuple(map(tuple,m['matrix'])))
        for order in (list(reversed(range(graph.n))),list(range(1,graph.n))+[0]):
            fresh=MacBackend(validation_only=True)
            try:
                actual=fresh.exact_certificate(top.induced(graph,order))
                if (NAMESPACE,*actual[1:])!=tuple(m['exact']):raise ValueError('Fresh M relabel mismatch')
            finally:fresh.close()
        if sha(provisional)!=provisional_before:raise ValueError('Provisional inventory changed')
        report=dict(status='PASS_BYTE_COMPATIBILITY_ONLY',saved_graphs=matched,saved_near_values_compared=near_values,
            historical_exact_certificates=110,historical_literal_variant_checks=history_count,
            historical_class_bijection=len(class_pairs)==len(reverse),historical_65_records_updated=False,
            discrepancies=0,canonical_calls=calls+2,max_recorded_wall_seconds=maxwall,
            max_worker_rss_bytes=maxrss,summed_worker_cpu_seconds=cpu,elapsed_seconds=perf_counter()-started,
            candidate_namespace=VALIDATION_NAMESPACE,comparison_target_namespace=NAMESPACE,
            c3_payload_bytes_compatible=True,production_namespace_enabled=False,
            hard_memory_enforcement='BLOCKED',production_generation_authorized=False,
            restored_evidence_root=str(evidence),provisional_inventory_unchanged_sha256=provisional_before,
            transport_sha256=sha(archive),validation_pin_sha256=backend.pin_sha256,
            source_sha256={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'src/spatial_memory/phase15_nauty_macos.py',ROOT/'src/spatial_memory/phase15_nauty_macos_worker.py')})
        output.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:backend.close()


if __name__=='__main__':main()
