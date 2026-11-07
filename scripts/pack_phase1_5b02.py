"""Lossless packaging only: retain original measurements outside Git."""
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'results/phase1_5b02'


def main():
    assert (OUT/'summary.json').exists(), 'Audit must finish first'
    source=(OUT/'canonicalization_measurements.json').resolve()
    archive=(ROOT/'results/raw/phase1_5b02_development/measurements/canonicalization_measurements.json').resolve()
    target=OUT/'canonicalization_measurements.json.gz'
    assert source.parent==OUT.resolve() and archive.is_relative_to((ROOT/'results/raw/phase1_5b02_development').resolve())
    assert not archive.exists() and not target.exists()
    body=source.read_bytes(); packed=gzip.compress(body,mtime=0)
    assert gzip.decompress(packed)==body
    target.write_bytes(packed); archive.parent.mkdir(exist_ok=False)
    os.replace(source,archive)
    assert archive.read_bytes()==gzip.decompress(target.read_bytes())
    report=dict(original_path=str(archive),original_bytes=len(body),
        original_sha256=hashlib.sha256(body).hexdigest(),
        compact_path=str(target.relative_to(ROOT)),compact_bytes=len(packed),
        compact_sha256=hashlib.sha256(packed).hexdigest(),lossless_roundtrip=True,
        packaging_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (OUT/'measurement_storage.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
