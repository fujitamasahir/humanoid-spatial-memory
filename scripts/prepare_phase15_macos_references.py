"""Derive new reference packages from verified stored evidence; no generators.

This prepares, but does not seal, an inventory. Independent verification is a
separate entry point. Original inputs are opened read-only; output is exclusive.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from spatial_memory.phase15_macos_monitored import MonitoredBackend, PROFILE
from spatial_memory.phase15_topology import Graph
from spatial_memory.phase15_bprime_protocol import canonical_bytes, digest


def sha(raw):return hashlib.sha256(raw).hexdigest()

def write(path,value):
    raw=canonical_bytes(value)
    with path.open('xb') as f:f.write(raw)
    return sha(raw)


def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();source=a.evidence.resolve();out=a.output.resolve()
    provisional=source/'derived-review/reference-inventory.PROVISIONAL.json'
    raw=provisional.read_bytes()
    if sha(raw)!='08755f052164be1028f40aba6ed3d23812b156b05770e8f7c09c2a9b9cd1c0d1':raise RuntimeError('Restoration inventory changed')
    old=json.loads(raw);out.mkdir(parents=True,exist_ok=False);(out/'archives').mkdir()
    rows=[];ledger={};completed=[];backend=MonitoredBackend()
    try:
        for item in old['entries']:
            row=dict(item);identity=row['identity'];data=(source/row['path']).read_bytes()
            original_digest=sha(data)
            if row['category']=='original_history':
                if original_digest!=identity:raise RuntimeError('Historical stored raster identity changed')
                geometry=json.loads(data);graph=Graph(tuple(map(tuple,row['matrix'])))
                keys=backend.near_certificates(graph);exact=backend.exact_certificate(graph)
                if exact!=tuple(row['exact']):raise RuntimeError('Historical exact C3 mismatch')
                if row['near_keys'] is not None and keys!=frozenset(map(tuple,row['near_keys'])):raise RuntimeError('Historical near C3 mismatch')
                if row['near_keys'] is None:completed.append(dict(identity=identity,source_raster_sha256=identity,source_matrix_sha256=digest(row['matrix']),near_keys=sorted(keys),exact=exact))
                body=dict(geometry=geometry,matrix=row['matrix'],exact=exact,near_certificates=sorted(keys),
                    derivation=dict(kind='stored-raster-interpretation-not-regenerated-world',source_sha256=identity,sources=row['sources']))
                data=gzip.compress(canonical_bytes(body),mtime=0)
                row.update(outcome='historical',near_keys=sorted(keys),source_commit=row['source_commit'],
                    source_path=';'.join(s['path'] for s in row['sources']),
                    interpretation=';'.join(sorted({s['interpretation'] for s in row['sources']})))
            else:
                if original_digest!=row['sha256'] or len(data)!=row['bytes']:raise RuntimeError('Original archive changed')
                body=json.loads(gzip.decompress(data));g=body['geometry']
                if identity!=f"{g['partition']}:{g['mechanism']}:{g['seed']}" or row['roots']!=[g['lineage']]:raise RuntimeError('Identity/lineage conflict')
                row.update(source_commit=row['sources'][0]['commit'],source_path=row['sources'][0]['path'],
                    interpretation='original-immutable-B02-archive',mechanism=g['mechanism'])
            name=sha(identity.encode())+'.json.gz'
            with (out/'archives'/name).open('xb') as f:f.write(data)
            row.update(path='archives/'+name,sha256=sha(data),bytes=len(data),canonical_status='C3_VERIFIED_BUILD_OR_NEW_HISTORY',resource_profile=PROFILE)
            ledger[identity]={k:row[k] for k in ('outcome','sha256','bytes','roots','aliases','source_commit','source_path','interpretation')}
            rows.append(row)
        if len(completed)!=65:raise RuntimeError('Unexpected incomplete-history count')
        rows.sort(key=lambda r:(r['category'],r['identity']))
        assert Counter(r['category'] for r in rows)==Counter(original_history=110,admitted_development=2258,rejected_valid=2276)
        inventory=dict(version=old['version'],schema=1,profile='production',namespace=old['namespace'],entries=rows,ledger_sha256=digest(ledger))
        write(out/'inventory.json',inventory);write(out/'ledger.json',ledger)
        write(out/'historical-completion.json',dict(schema=1,resource_profile=PROFILE,backend_pin_sha256=backend.pin_sha,records=completed))
        write(out/'resource-events.json',backend.events)
        write(out/'preparation.json',dict(status='PREPARED_NOT_SEALED',source_inventory_sha256=sha(raw),inventory_sha256=digest(inventory),ledger_sha256=digest(ledger),historical_completed=65,included=2368,nonreferences=2276,resource_calls=len(backend.events),source=str(source)))
        print(json.dumps(dict(output=str(out),inventory_sha256=digest(inventory),status='PREPARED_NOT_SEALED')))
    finally:backend.close()

if __name__=='__main__':main()
