"""Compact final integrity, resource, storage and feasibility evidence."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results/phase1_5b02'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    independent=json.loads((OUT/'independent_verification.json').read_text()); assert independent['all_checks_pass']
    summary=json.loads((OUT/'summary.json').read_text())
    pre=json.loads((OUT/'preflight.json').read_text())
    for name,expected in pre['source_sha256'].items(): assert sha(ROOT/name)==expected
    cfg=json.loads((ROOT/'configs/phase15_nauty_backend.json').read_text())
    for name,expected in cfg['dependency_sha256'].items(): assert sha(ROOT/name)==expected
    inventory=[json.loads(line) for line in gzip.decompress((OUT/'candidate_inventory.jsonl.gz').read_bytes()).splitlines()]
    feasibility={}
    for part in ('fit','calibration','selection'):
        for mechanism in ('R','B','V','M'):
            rows=[r for r in inventory if r['partition']==part and r['mechanism']==mechanism]
            valid=[r for r in rows if 'graph_vertices' in r]
            feasibility[part+'/'+mechanism]=dict(attempts=len(rows),raw_valid_geometries=len(valid),
                raw_geometry_fraction=len(valid)/len(rows) if rows else None,
                independent_admissions=sum(r['outcome']=='independent' for r in rows),
                final_independent_credits=summary['partitions'][part]['counts'][mechanism],
                outcomes=dict(Counter(r['outcome'] for r in rows)),
                graph_vertex_range=[min(r['graph_vertices'] for r in valid),max(r['graph_vertices'] for r in valid)] if valid else None)
    (OUT/'generator_feasibility.json').write_text(json.dumps(feasibility,indent=2)+'\n')
    xml=ROOT/'results/runs/phase1_5b02_full_suite.xml'
    suite=ET.parse(xml).getroot().find('testsuite')
    tests={k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}
    tests.update(seconds=float(suite.attrib['time']),xml_sha256=sha(xml))
    assert tests['tests']==243 and tests['failures']==tests['errors']==tests['skipped']==0
    old=json.loads((ROOT/'results/phase1_5b0/historical_integrity.json').read_text())
    for name,expected in old['initial_tracked_result_sha256'].items(): assert sha(ROOT/name)==expected
    for section in ('source_sha256','immutable_files_sha256'):
        for name,expected in json.loads((ROOT/'results/phase1_5b01/provenance.json').read_text())[section].items():
            assert sha(ROOT/name)==expected
    git=['git','-c',f'safe.directory={ROOT}']; base='d2c3f58672b6732305385d37079de9269f2ee9de'
    prior=set(subprocess.check_output(git+['ls-tree','-r','--name-only',base],cwd=ROOT,text=True).splitlines())
    changed=set(subprocess.check_output(git+['diff',base,'--name-only'],cwd=ROOT,text=True).splitlines())
    assert not prior.intersection(changed)
    documents=sorted((ROOT/'docs').glob('phase1_5b02_*.md')); assert len(documents)==3
    for doc in documents:
        for link in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            if not link.startswith('http'):
                path=(doc.parent/link.split('#')[0]).resolve()
                assert path==(OUT/'delivery_verification.json').resolve() or path.exists(),link
    bulk=ROOT/'results/raw/phase1_5b02_development'
    records=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(bulk.rglob('*')) if p.is_file()]
    storage=dict(files=len(records),bytes=sum(r['bytes'] for r in records),
        checkpoints=sum('/checkpoints/' in r['path'] for r in records),
        inventory_sha256=hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        reconstruction='sorted recursive files under results/raw/phase1_5b02_development; entries path,bytes,sha256; compact sorted-key JSON array, no newline',
        artifact_manifest_sha256=sha(OUT/'trace_storage_manifest.json'))
    runtime_evidence=[xml,ROOT/'results/runs/phase1_5b02_resource_tests.xml',ROOT/'results/runs/phase1_5b02_memory_probe.json']
    runtime_evidence+=list((ROOT/'results/runs/phase1_5b02_failure_probes').glob('*.json'))
    runtime_evidence.append(ROOT/'results/runs/phase1_5b02_exec_rss_probe.json')
    report=dict(all_checks_pass=True,base_commit=base,full_suite=tests,
        historical_regression_records=2212,all_original_tracked_files_unchanged=True,
        original_failed_audit_immutable=True,production_source_freeze_matches=True,
        dependency_hashes_match=True,storage=storage,
        final_resource_probe=json.loads((ROOT/'results/runs/phase1_5b02_memory_probe.json').read_text()),
        exec_rss_accounting_probe=json.loads((ROOT/'results/runs/phase1_5b02_exec_rss_probe.json').read_text()),
        verification_attempts=[dict(attempt=1,outcome='failed resource-evidence check before candidate reconstruction',
            cause='eager decompressed-artifact storage; inherited ru_maxrss accounting independently demonstrated',
            action='stream artifact bodies; frozen backend and audit unchanged'),
            dict(attempt=2,outcome='independent reconstruction passed')],
        runtime_evidence=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in runtime_evidence],
        final_source_sha256={str(p.relative_to(ROOT)):sha(p) for p in documents+sorted((ROOT/'scripts').glob('*phase1_5b02*.py'))},
        compact_evidence_sha256={str(p.relative_to(ROOT)):sha(p) for p in OUT.glob('*') if p.is_file() and p.name!='delivery_verification.json'},
        readiness_for_phase1_5b1=summary['ready_for_phase1_5b1'],
        new_research_navigation_episodes=0,assessment_final_generation=False,scientific_review_required=True)
    (OUT/'delivery_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(all_checks_pass=True,tests=tests,storage=storage,ready=report['readiness_for_phase1_5b1']),indent=2))


if __name__=='__main__': main()
