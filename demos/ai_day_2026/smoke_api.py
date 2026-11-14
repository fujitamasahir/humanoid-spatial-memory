"""Loopback end-to-end smoke for the actual local FastAPI G1 demo."""
from __future__ import annotations
import argparse,json,time,urllib.request,hashlib,platform,subprocess,sys
from pathlib import Path

BASE_DIR=Path(__file__).resolve().parent

def request(url, payload=None):
    body=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'} if body else {})
    with urllib.request.urlopen(req,timeout=8) as response:
        return json.loads(response.read())

def wait_result(base, timeout=35):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        state=request(base+'/api/state')
        if state.get('status') in {'finished','error'}: return state
        time.sleep(.12)
    raise TimeoutError('challenge exceeded 35 second showcase smoke deadline')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--url',default='http://127.0.0.1:8765');ap.add_argument('--output',default=str(BASE_DIR/'validation'/'api_smoke_report.json'));a=ap.parse_args()
    base=a.url.rstrip('/');started=time.monotonic();catalog=request(base+'/api/catalog')
    assert len(catalog['mazes'])==36
    served={}
    for path,marker in [('/',b'BEAT THE HUMANOID'),('/static/style.css',b'--bg:'),('/static/game.js',b'gamepadLoop')]:
        with urllib.request.urlopen(base+path,timeout=8) as response: body=response.read()
        assert marker in body, f'UI asset did not load: {path}'
        served[path]=len(body)
    maze=catalog['mazes'][0]
    free=[(x,y) for y,row in enumerate(maze['wall_rows']) for x,v in enumerate(row) if v=='0']
    excluded={tuple(maze['start']),tuple(maze['goal'])}
    ped=next(([x,y] for x,y in free if (x,y) not in excluded and
              abs(x-maze['start'][0])+abs(y-maze['start'][1])>3 and
              abs(x-maze['goal'][0])+abs(y-maze['goal'][1])>3),None)
    validation=request(base+'/api/validate',{'maze_id':maze['id'],'objects':[],'pedestrians':[]})
    assert validation['valid'],validation
    challenges=[]
    for method,pedestrians in [('periodic',[]),('age',[]),('uncertainty',[]),('periodic',[ped])]:
        config={'maze_id':maze['id'],'objects':[],'pedestrians':pedestrians,'strategy':method}
        accepted=request(base+'/api/challenge',config)
        assert accepted['ok'],accepted
        state=wait_result(base)
        if state.get('status')=='error':raise RuntimeError(state.get('error'))
        result=state['result']
        challenges.append({'maze_id':maze['id'],'strategy':method,'seed':accepted['seed'],
          'objects':[],'pedestrian_starts':pedestrians,
          'winner':result['winner'],'success':result['success'],'elapsed_steps':result['elapsed_steps'],
          'observations':result['observation_count'],'distance_m':result['travel_distance_m'],
          'actual_unwanted_contacts':result['actual_unwanted_contacts'],
          'blocked_attempts_not_contacts':result['blocked_attempts_not_contacts'],
          'episode_wall_time_seconds':result.get('episode_wall_time_seconds'),
          'emergency_scans':result.get('emergency_safety_scans',0),
          'emergency_raycasts':result.get('emergency_safety_raycasts',0),
          'spatial_memory_rays':result.get('mujoco_sensor_rays',0)})
    binding=BASE_DIR/'data'/'runtime_binding.json';catalog_file=BASE_DIR/'data'/'maze_catalog.json'
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=BASE_DIR.parents[1],capture_output=True,text=True,check=True).stdout.strip()
    report={'status':'PASS','endpoint':'localhost only','ui_assets_served_bytes':served,
      'source_commit':commit,'branch':'demo/ai-day-2026','python':sys.version,'platform':platform.platform(),
      'maze_catalog_sha256':hashlib.sha256(catalog_file.read_bytes()).hexdigest(),
      'runtime_binding_sha256':hashlib.sha256(binding.read_bytes()).hexdigest(),
      'maze_catalog_count':len(catalog['mazes']),
      'maze_id':maze['id'],'layout_validation':'PASS','challenge_cases':challenges,
      'total_wall_seconds':time.monotonic()-started,
      'interpretation':'Actual existing Phase 2 G1 kinematic navigation stack. No 3D renderer is used; canvas playback is 2D.'}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True))
if __name__=='__main__':main()
