"""Export admitted FIT maze geometry into a compact standalone JSON asset.

Read-only: uses the repository's checkpoint validator and never opens a store
for writing. Experimental object-change schedules are intentionally excluded.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import phase2_mujoco_navigation as nav

OUTPUT = Path(__file__).resolve().parent / 'data' / 'maze_catalog.json'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    worlds = nav.admitted_worlds()
    preservation = nav.verify_preserved_prefix()
    rows = []
    for payload in worlds:
        geometry = payload['geometry']
        width, height = int(geometry['width']), int(geometry['height'])
        free = {tuple(map(int, cell)) for cell in geometry['free']}
        wall_rows = [
            ''.join('0' if (x, y) in free else '1' for x in range(width))
            for y in range(height)
        ]
        canonical_geometry = json.dumps({
            'width': width, 'height': height,
            'free': [list(xy) for xy in sorted(free, key=lambda c: (c[1], c[0]))],
            'start': list(payload['world']['start']),
            'goal': list(payload['world']['goal']),
        }, sort_keys=True, separators=(',', ':')).encode()
        record_path = None
        record_sha = None
        for rel in nav.STORES:
            path = ROOT / rel / 'records' / (sha(payload['identity'].encode()) + '.json.gz')
            if path.is_file():
                record_path = path.relative_to(ROOT).as_posix()
                record_sha = sha(path.read_bytes())
                break
        if record_path is None:
            raise FileNotFoundError(f'No committed checkpoint for {payload["identity"]}')
        rows.append({
            'id': payload['identity'], 'mechanism': payload['mechanism'],
            'candidate_index': int(payload['index']), 'width': width, 'height': height,
            'start': list(map(int, payload['world']['start'])),
            'goal': list(map(int, payload['world']['goal'])),
            'wall_rows': wall_rows,
            'geometry_sha256': sha(canonical_geometry),
            'source': {'checkpoint_path': record_path, 'checkpoint_sha256': record_sha,
                       'payload_sha256': sha(json.dumps(payload, sort_keys=True,
                           separators=(',', ':'), allow_nan=False).encode())},
        })
    document = {
        'schema': 'ai-day-2026-maze-catalog-v1',
        'provenance': {
            'source': '36 already-admitted Phase 1.5 FIT worlds, read-only checkpoint validation',
            'research_base_commit': 'b6cb1fa233fbcd30b7ea26e88b865a69db96b91e',
            'phase15_preservation_manifest_sha256': preservation['manifest_sha256'],
            'phase15_preserved_files_rehashed': preservation['files_checked'],
            'world_count': len(rows),
            'object_change_schedules_included': False,
            'geometry_encoding': 'wall_rows: one exact-width 0/1 string per row; 1=original wall, 0=original free cell',
        },
        'mazes': rows,
    }
    if len(rows) != 36:
        raise ValueError(f'Expected exactly 36 admitted worlds, found {len(rows)}')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
    OUTPUT.write_bytes(raw)
    print(json.dumps({'status': 'EXPORTED_VERIFIED', 'mazes': len(rows),
                      'path': str(OUTPUT.relative_to(ROOT)), 'bytes': len(raw),
                      'sha256': sha(raw), 'preserved_files_rehashed': preservation['files_checked']}, indent=2))

if __name__ == '__main__':
    main()
