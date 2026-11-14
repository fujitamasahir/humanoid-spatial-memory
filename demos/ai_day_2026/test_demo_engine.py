import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from engine import (CATALOG_PATH, GameEngine, FootprintReachability,
                    make_pedestrian_paths, read_catalog, verify_runtime_binding)

ROOT = Path(__file__).resolve().parents[2]


def _small_maze():
    w=h=7
    rows=[]
    for y in range(h):
        row=[]
        for x in range(w):
            wall=x in (0,w-1) or y in (0,h-1) or (x==3 and y!=3)
            row.append('1' if wall else '0')
        rows.append(''.join(row))
    return {'id':'test-maze','mechanism':'R','candidate_index':0,'width':w,'height':h,
            'start':[1,1],'goal':[5,5],'wall_rows':rows}


def _light_engine(maze):
    eng=GameEngine.__new__(GameEngine)
    eng.catalog={'mazes':[maze]};eng.mazes={maze['id']:maze}
    eng.reachability=FootprintReachability((0.0,0.0))
    return eng


def test_catalog_roundtrips_admitted_source_geometry_and_hashes():
    doc=read_catalog()
    assert len(doc['mazes'])==36
    assert doc['provenance']['research_base_commit']=='b6cb1fa233fbcd30b7ea26e88b865a69db96b91e'
    assert doc['provenance']['phase15_preserved_files_rehashed']==836
    for maze in doc['mazes']:
        source=maze['source'];raw=(ROOT/source['checkpoint_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==source['checkpoint_sha256']
        body=json.loads(gzip.decompress(raw));payload=body['payload']
        assert payload['identity']==maze['id']
        assert hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==source['payload_sha256']
        free={tuple(c) for c in payload['geometry']['free']}
        rows=[''.join('0' if (x,y) in free else '1' for x in range(maze['width'])) for y in range(maze['height'])]
        assert rows==maze['wall_rows']
        assert list(payload['world']['start'])==maze['start']
        assert list(payload['world']['goal'])==maze['goal']


def test_runtime_binding_freezes_research_code_and_actual_g1_files():
    binding=verify_runtime_binding()
    assert len(binding['frozen_source_files'])==10
    assert len(binding['unitree_g1_files'])>=60
    assert set(binding['algorithm_policies'])=={'periodic','age','uncertainty'}


def test_every_admitted_maze_retains_a_g1_footprint_forward_first_route():
    reach=FootprintReachability.from_pinned_g1()
    catalog=read_catalog()
    assert all(reach.has_route(maze,[]) for maze in catalog['mazes'])


def test_editor_rejects_walls_bounds_start_goal_overlap_and_count_limits():
    maze=_small_maze();eng=_light_engine(maze)
    assert eng.validate(maze['id'],[],[])['valid']
    for cell in ([0,0],[-1,2],[7,2],maze['start'],maze['goal']):
        assert not eng.validate(maze['id'],[cell],[])['valid']
    assert not eng.validate(maze['id'],[[1,2],[1,2]],[])['valid']
    assert not eng.validate(maze['id'],[[1,2]],[[1,2]])['valid']
    assert not eng.validate(maze['id'],[[1,2],[2,1],[2,2],[4,2],[4,4]],[])['valid']


def test_static_object_closing_only_passage_is_rejected():
    maze=_small_maze();eng=_light_engine(maze)
    assert eng.validate(maze['id'],[],[])['valid']
    verdict=eng.validate(maze['id'],[[3,3]],[])
    assert verdict['valid'] is False
    assert 'all footprint-safe forward-first routes' in verdict['errors'][0]


def test_pedestrian_paths_are_seedless_deterministic_and_cardinal():
    maze=_small_maze();starts=[[2,2],[4,4]];objects=[[1,2]]
    a=make_pedestrian_paths(maze,starts,objects)
    b=make_pedestrian_paths(maze,starts,objects)
    assert a==b
    occupied={(x,y) for y,row in enumerate(maze['wall_rows']) for x,v in enumerate(row) if v=='1'}|{tuple(c) for c in objects}|{tuple(maze['goal'])}
    for p,start in zip(a,starts):
        assert p[0]==start
        assert all(tuple(c) not in occupied for c in p)
        assert all(abs(x1-x0)+abs(y1-y0)<=1 for (x0,y0),(x1,y1) in zip(p,p[1:]+p[:1]))
