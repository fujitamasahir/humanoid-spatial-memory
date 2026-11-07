"""Independent delivery integrity checks; no generator or episode execution."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/phase1_5b01'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    evidence=json.loads((OUT/'provenance.json').read_text())
    checked={}
    for section in ('source_sha256','isolated_dependency_sha256','immutable_files_sha256','fixture_sha256'):
        for name,expected in evidence[section].items():
            assert sha(ROOT/name)==expected,name
        checked[section]=len(evidence[section])
    old=json.loads((ROOT/'results/phase1_5b0/provenance.json').read_text())
    for name,expected in old['source_sha256'].items(): assert sha(ROOT/name)==expected,name
    historical=json.loads((ROOT/'results/phase1_5b0/historical_integrity.json').read_text())
    for name,expected in historical['initial_tracked_result_sha256'].items():
        assert sha(ROOT/name)==expected,name
    counts={}
    for name,expected in evidence['historical_regression_counts'].items():
        counts[name]=len(json.loads((ROOT/name).read_text())['episodes'])
        assert counts[name]==expected
    assert sum(counts.values())==2212
    for row in json.loads((ROOT/'results/phase1_5b0/trace_storage_manifest.json').read_text())['records']:
        assert sha(row['path'])==row['sha256']
        assert Path(row['path']).stat().st_size==row['bytes']
    frozen={
        'results/phase1_4b/parameter_lock.json':'ecdd2f11e0c279bfa6c8557fcc646c4f714d2c7627deb731cbb366138a64d2f1',
        'results/phase1_4a/manifests/assessment.json':'6335b77dd5838b2ea312d3293c939354e0b7f454eccbc679f0c59d4fe031c822'}
    for name,expected in frozen.items(): assert sha(ROOT/name)==expected
    xml=ROOT/'results/runs/phase1_5b01_benchmarks/full_suite.xml'
    suite=ET.parse(xml).getroot().find('testsuite')
    tests={k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}
    tests.update(seconds=float(suite.attrib['time']),xml_sha256=sha(xml))
    assert tests['tests']==236 and tests['failures']==tests['errors']==tests['skipped']==0
    correctness=json.loads((OUT/'correctness.json').read_text())
    assert correctness['total_graphs']==1215 and correctness['relation_bijection']
    assert correctness['historical_variant_comparisons']==709
    benchmarks=json.loads((OUT/'benchmarks.json').read_text()); assert len(benchmarks)==48
    m=[r for r in benchmarks if r['fixture']=='preserved_M_75']
    assert len(m)==6
    assert all(r['status']=='guard' for r in m if r['backend']!='nauty_proposal')
    assert all(r['status']=='certified' and max(s['wall_seconds'] for s in r['measurements'])<5
               for r in m if r['backend']=='nauty_proposal')
    files=[p for p in (ROOT/'results/runs/phase1_5b01_benchmarks').rglob('*') if p.is_file()]
    files += [p for p in (ROOT/'results/runs/phase1_5b01_dependencies').rglob('*') if p.is_file()]
    storage=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    documents=list((ROOT/'docs').glob('phase1_5b01_*.md'))
    assert len(documents)==3
    links=0
    for doc in documents:
        for target in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            if not target.startswith('http'):
                resolved=(doc.parent/target.split('#')[0]).resolve()
                assert resolved==(OUT/'verification.json').resolve() or resolved.exists(),target
                links+=1
    # Every path existing at base must remain byte-unmodified by this task.
    git=['git','-c',f'safe.directory={ROOT}']
    base=evidence['base_commit']
    prior=set(subprocess.check_output(git+['ls-tree','-r','--name-only',base],cwd=ROOT,text=True).splitlines())
    changed=subprocess.check_output(git+['diff',base,'--name-only'],cwd=ROOT,text=True).splitlines()
    assert not prior.intersection(changed),prior.intersection(changed)
    report=dict(all_checks_pass=True,checked_inventory_sizes=checked,
        old_frozen_source_files_verified=len(old['source_sha256']),
        historical_result_files_verified_against_original_inventory=len(historical['initial_tracked_result_sha256']),
        original_tracked_files_unchanged=True,historical_regression_records=2212,
        regression_counts=counts,frozen_sha256=frozen,original_archive_checksums_verified=2,
        full_suite=tests,correctness_graphs=1215,historical_variant_comparisons=709,
        benchmark_records=48,local_document_links_checked=links,
        document_sha256={str(p.relative_to(ROOT)):sha(p) for p in documents},
        verifier_sha256=sha(Path(__file__)),
        compact_evidence_sha256={str(p.relative_to(ROOT)):sha(p) for p in OUT.glob('*.json') if p.name!='verification.json'},
        bulk_storage=storage,bulk_bytes=sum(r['bytes'] for r in storage),
        new_development_candidates=0,new_research_navigation_episodes=0,
        full_development_population_established=False,representation_amendment_adopted=False,
        limitations=['Native node statistics unavailable','Only reference-sized graphs exhaustively verified',
                    'No new development audit; carried forward fit1/calibration0/selection0'])
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k in ('all_checks_pass','full_suite','bulk_bytes','historical_regression_records','original_tracked_files_unchanged')},indent=2))


if __name__=='__main__': main()
