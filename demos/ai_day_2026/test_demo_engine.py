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

def test_pedestrian_start_cannot_close_only_passage():
    maze=_small_maze();eng=_light_engine(maze)
    assert not eng.validate(maze['id'], [], [[3,3]])['valid']

def test_difficulty_enforces_hazard_caps():
    maze=_small_maze();eng=_light_engine(maze)
    assert eng.validate(maze['id'], [], [], 'hard')['valid']
    assert eng.validate(maze['id'], [[1,2]], [], 'hard')['valid']
    assert not eng.validate(maze['id'], [[1,2],[2,1]], [], 'hard')['valid']
    assert not eng.validate(maze['id'], [], [[1,2]], 'hard')['valid']
    assert not eng.validate(maze['id'], [], [[1,2],[4,4]], 'medium')['valid']
    assert not eng.validate(maze['id'], [[1,2],[2,1],[4,4]], [], 'medium')['valid']
    assert not eng.validate(maze['id'], [], [], 'unknown')['valid']

def test_wandering_covers_more_than_two_cells_and_never_overlaps():
    maze=_small_maze();starts=[[2,2],[4,4]]
    paths=make_pedestrian_paths(maze,starts,[],120)
    assert len(paths)==2 and all(len(p)>=121 for p in paths)
    assert all(len(set(map(tuple,p[:121])))>2 for p in paths)
    for i in range(1,len(paths[0])):
        assert paths[0][i]!=paths[1][i]
        assert not (paths[0][i]==paths[1][i-1] and paths[1][i]==paths[0][i-1])

def test_skip_and_review_are_scoped_to_completed_run():
    import threading
    engine=GameEngine.__new__(GameEngine)
    engine.lock=threading.RLock()
    engine.condition=threading.Condition(engine.lock)
    engine.skip_playback=threading.Event()
    engine.history={0:{'step':0},1:{'step':1,'memory':[[0]]}}
    engine.running=True
    engine.state={'status':'running'}
    assert engine.review_index() is None
    assert engine.skip()['ok'] and engine.skip_playback.is_set()
    assert engine.review_frame(1) is None
    engine.state={'status':'finished','result':{'winner':'AI WINS'}}
    engine.running=False
    assert engine.review_index()['steps']==[0,1]
    frame=engine.review_frame(1);frame['memory'][0][0]=1
    assert engine.review_frame(1)['memory']==[[0]]
    assert engine.review_frame(2) is None
    assert engine.reset()['ok'] and not engine.history and not engine.skip_playback.is_set()
    assert not engine.skip()['ok']


def test_difficulty_memory_budget_includes_initial_scan():
    import numpy as np
    from engine import DIFFICULTIES
    from spatial_memory.scheduling import ObservationController
    for level, expected in [('easy', (80,20)), ('medium',(120,30)), ('hard',(160,40))]:
        rules = DIFFICULTIES[level]
        assert (rules['step_limit'], rules['max_observations']) == expected
        for method in ('periodic','age','uncertainty'):
            initial = np.zeros((5,5), dtype=int)
            agent = ObservationController(initial, method, interval=1, max_observations=expected[1])
            for step in range(1, expected[1]):
                agent.refresh(initial, step)
            assert agent.used == expected[1]
            assert not agent.decide(expected[1]+100, (2,2))['observation_granted']


def _paused_test_engine(level='easy'):
    import threading
    eng=_light_engine(_small_maze())
    eng.lock=threading.RLock()
    eng.condition=threading.Condition(eng.lock)
    eng.skip_playback=threading.Event()
    eng.running=True
    eng.pause_requested=False
    eng.resume_layout=None
    eng.frame_delay_s=.5
    eng.state=dict(status='running',frame_seq=12,step=12,maze_id='test-maze',
                   difficulty=level,position=[2,2],heading_yaw=0.,objects=[],people=[],
                   observations=4,memory=[[0,-1]],trajectory=[[1,1],[2,2]],edit_events=[])
    return eng


def _enter_pause(eng):
    import threading
    import time
    result=[]
    assert eng.pause()['ok']
    assert eng.state['status']=='pausing'
    thread=threading.Thread(target=lambda: result.append(eng._wait_at_frame()),daemon=True)
    thread.start()
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        if eng.snapshot()['status']=='paused':
            return thread,result
        time.sleep(.005)
    raise AssertionError('Worker failed to enter pause')


def test_live_pause_preserves_evaluator_frame_and_rejects_skip():
    import time
    eng=_paused_test_engine()
    thread,result=_enter_pause(eng)
    before=eng.snapshot()
    time.sleep(.04)
    assert thread.is_alive() and not result
    assert eng.snapshot()==before
    assert not eng.skip()['ok']
    assert not eng.resume(11,[],[])['ok']
    assert eng.resume(12,[],[])['ok']
    thread.join(2)
    assert not thread.is_alive() and result==[None]
    assert eng.state['observations']==4 and eng.state['memory']==[[0,-1]]
    assert eng.state['trajectory']==[[1,1],[2,2]] and not eng.state['edit_events']


def test_live_resume_enforces_limits_and_preserves_draft_on_rejection():
    eng=_paused_test_engine('hard')
    thread,result=_enter_pause(eng)
    try:
        assert not eng.resume(12,[],[[4,4]])['ok']
        assert not eng.resume(12,[[4,4],[5,4]],[])['ok']
        assert not eng.resume(12,[[2,2]],[])['ok']
        assert not eng.resume(12,[[0,0]],[])['ok']
        assert not eng.resume(12,[[3,3]],[])['ok']  # only passage
        assert eng.state['status']=='paused' and thread.is_alive()
        assert eng.resume(12,[[4,4]],[])['ok']
        thread.join(2)
        assert not thread.is_alive() and result==[([[4,4]],[])]
        assert eng.state['edit_events'][0]['paused_step']==12
        assert eng.state['edit_events'][0]['effective_step']==13
        assert eng.state['observations']==4
    finally:
        if thread.is_alive():
            with eng.condition:
                eng.pause_requested=False
                eng.condition.notify_all()
            thread.join(2)


def test_terminal_frame_never_waits_for_resume():
    eng=_paused_test_engine()
    assert eng.pause()['ok']
    eng.frame_delay_s=0
    assert eng._wait_at_frame(terminal=True) is None
    assert not eng.pause_requested
    assert eng.state['status']!='paused'


def test_absolute_step_pedestrian_paths_after_live_edit():
    from engine import make_scenario
    maze=_small_maze()
    step=12
    starts=[[4,4]]
    paths=make_pedestrian_paths(maze,starts,[[1,2]],20)
    absolute=[[path[0]]*step+path for path in paths]
    scenario=make_scenario(maze,[[1,2]],absolute)
    assert scenario.pedestrians[0][step]==tuple(starts[0])
    assert all(abs(a[0]-b[0])+abs(a[1]-b[1])<=1 for a,b in
               zip(scenario.pedestrians[0],scenario.pedestrians[0][1:]+scenario.pedestrians[0][:1]))
