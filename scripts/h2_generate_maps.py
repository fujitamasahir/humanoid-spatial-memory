"""Authorized H2-only independent R/BP/M draw using original frozen laws.

Does not enable production namespaces in existing generators or read sealed worlds.
"""
import sys,json,hashlib
from dataclasses import dataclass
from collections import deque,Counter
import numpy as np
from h2_final_common import ROOT,OUT,write,manifest,sha,deadline_guard
from spatial_memory import phase15_bprime as bp
from spatial_memory import phase15_topology as topology
from spatial_memory.phase15_macos_monitored import MonitoredBackend
from spatial_memory.dao_admission_v1 import occupancy_hash,endpoint_hash,orientations
from spatial_memory.navigation import _move_clear,_turn_clear,CARDINALS
import phase2_mujoco_navigation as nav
NAMESPACE='h2-final-generalization-v1-20261114'
@dataclass(frozen=True)
class H2Identity(bp.Identity):
    def __post_init__(self):
        if self.partition!='h2_final_generalization_v1' or self.mechanism not in ('R','BP','M') or not 910000000<=self.seed<910040000:raise ValueError('H2-only identity')
    @property
    def root(self):return f'{NAMESPACE}:{self.mechanism}:{self.seed}'
class H2Stream(bp.Stream):
    def __init__(self,identity,purpose):
        if not isinstance(identity,H2Identity):raise TypeError('H2 identity required')
        fields=(NAMESPACE,str(identity.seed),purpose)
        framed=b''.join(len(f.encode()).to_bytes(4,'little')+f.encode() for f in fields)
        self.identity=hashlib.sha256(framed).hexdigest();self.raw=np.random.Philox(key=int.from_bytes(bytes.fromhex(self.identity)[:16],'little'));self.words=0;self.bounds=[]

def raster(free):
    a=np.ones((25,25),dtype=np.int8)
    for x,y in free:a[y,x]=0
    return a

def g1_certificate(grid,start,goal):
    """Static original-G1 geometric witness on predeclared shortest point path.

    Offline admission only, no model rollout/sensing or pedestrian information.
    A failed witness rejects, without searching controller outcomes.
    """
    from spatial_memory.navigation import plan,HEADINGS,heading_index
    from spatial_memory.simulation import Scenario,World
    from spatial_memory.mujoco_navigation import MujocoNavigationScene
    path=plan(grid,tuple(start),tuple(goal),'blocked')
    if not path:return []
    walls=[(x,y) for y in range(25) for x in range(25) if grid[y,x]]
    scenario=Scenario.from_dict(dict(name='H2-static-geometric-admission',split='development',width=25,height=25,start=start,goal=goal,walls=walls,obstacles=[],pedestrians=[],changes=[]))
    world=World(scenario);scene=MujocoNavigationScene(scenario,cell_size=.75,timestep=.02)
    heading=0;witness=[(*start,heading)]
    for a,b in zip(path,path[1:]):
        desired=CARDINALS.index((b[0]-a[0],b[1]-a[1]))
        scene._set_pose(a,HEADINGS[heading])
        if desired!=heading:
            blocked,*_=scene.check_turn(world,a,HEADINGS[heading],HEADINGS[desired])
            if blocked:return []
            heading=desired;witness.append((*a,heading))
        scene._set_pose(a,HEADINGS[heading])
        blocked,*_=scene.check_move(world,a,b,HEADINGS[heading],target_yaw=HEADINGS[heading])
        if blocked:return []
        witness.append((*b,heading))
    return witness

def prior_inventory():
    """Only already authorized FIT checkpoints, including rejected geometries."""
    records=[];seen=set()
    for p in nav.checkpoints():
        g=p.get('geometry',{})
        if 'free' not in g:continue
        a=raster(g['free']);h=occupancy_hash(a)
        if h not in seen:records.append({'identity':p['identity'],'grid':a,'hash':h,'topology':p.get('topology',{})});seen.add(h)
    return records

def main():
    from run_h2_final import gate
    gate();assert json.loads((OUT/'fit_replay/summary.json').read_text())['completed']==864
    deadline_guard(300);target=OUT/'maps';target.mkdir(exist_ok=False)
    prior=prior_inventory();hashes={p['hash'] for p in prior};priorgrids=np.array([b==0 for p in prior for b in orientations(p['grid'])]);keys={tuple(p['topology']['exact']) for p in prior if 'exact' in p['topology']}
    write(target/'prior_inventory.json',{'scope':'All available authorized FIT checkpoint geometries; no protected/reserved world payload read for novelty. Protected opaque signatures unavailable.','unique_rasters':len(prior),'exact_topology_keys':len(keys),'identities':[p['identity'] for p in prior]})
    backend=MonitoredBackend();accepted=[];counts=Counter();serial=0
    try:
        for family,offset in (('R',0),('BP',10000),('M',30000)):
            n=0
            for i in range(10000):
                deadline_guard(300);seed=910000000+offset+i;ident=H2Identity('h2_final_generalization_v1',family,seed);streams={}
                def stream(_,purpose):
                    s=H2Stream(ident,purpose);streams[purpose]=s;return s
                record={'identity':ident.root,'seed':seed,'family':family,'candidate_index':i}
                try:
                    geo=bp.geometry(ident,stream_factory=stream);a=raster(geo.free);h=occupancy_hash(a)
                    record['occupancy_hash']=h
                    if h in hashes:record['rejection']='exact_D4_raster_duplicate'
                    else:
                        free=a==0;union=np.logical_or(priorgrids,free).sum(axis=(1,2));diff=np.logical_xor(priorgrids,free).sum(axis=(1,2));dist=float(np.min(diff/union)) if len(priorgrids) else 1.
                        record['minimum_free_jaccard_distance_D4']=dist
                        if dist<=.05:record['rejection']='near_D4_raster_duplicate'
                        else:
                            graph,detail=topology.raster_quotient(geo.free);key=backend.exact_certificate(graph);record['exact_topology_key']=key
                            if key in keys:record['rejection']='exact_normalized_topology_duplicate'
                            else:
                                start,goal,distance=bp.choose_pair(geo.free,stream(ident,'start-goal'))
                                schedules=[bp.build_schedule(geo,start,goal,stream(ident,f'dynamics-{j}')) for j in (0,1)]
                                certificates=[]
                                for schedule in schedules:
                                    g=a.copy()
                                    for x,y in schedule['initial']:g[y,x]=1
                                    steps=sorted({0,*[e['step'] for e in schedule['events']]})
                                    for t in steps:
                                        for e in schedule['events']:
                                            if e['step']==t:g[e['cell'][1],e['cell'][0]]=int(e['action']=='add')
                                        path=g1_certificate(g,start,goal);certificates.append({'event_step':t,'path':path})
                                        if not path:record['rejection']='shortest_path_G1_static_witness_rejected';break
                                    if 'rejection' in record:break
                                if 'rejection' not in record:
                                    payload={'identity':ident.root,'partition':ident.partition,'index':i,'mechanism':family,'seed':seed,'outcome':'independent','ancestral_roots':[ident.root],
                                    'geometry':{'width':25,'height':25,'free':sorted(geo.free,key=bp.legacy.row_key),'construction':geo.construction},
                                    'world':{'start':start,'goal':goal,'distance':distance,'schedules':schedules},
                                    'topology':{'exact':key,'matrix':graph.matrix,**detail},'streams':{p:s.counters() for p,s in streams.items()},
                                    'admission':{'occupancy_hash':h,'endpoint_hash':endpoint_hash(a,start,goal),'minimum_prior_free_jaccard_D4':dist,'G1_static_certificates':certificates,'pedestrian_safety_certified':False,'initial_heading':0}}
                                    filename=f'map_{len(accepted)+1:02}_{family}.json';write(target/filename,payload);record.update(admitted=True,path=filename,sha256=sha(target/filename));accepted.append(record.copy());n+=1
                                    hashes.add(h);keys.add(tuple(key));priorgrids=np.concatenate([priorgrids,np.array([b==0 for b in orientations(a)])]);print(f'Admitted {family} {n}/12 seed{seed}',flush=True)
                except bp.legacy.Rejected as e:record['rejection']=str(e)
                # Dynamics exhaustion / backend errors stop instead of outcome-dependent replacement.
                record['streams']={p:s.counters() for p,s in streams.items()};write(target/'admission'/f'candidate_{serial:05}.json',record);serial+=1;counts[record.get('rejection','admitted')]+=1
                if n==12:break
            if n!=12:raise RuntimeError('Predeclared candidate allowance exhausted')
        write(target/'summary.json',{'status':'ADMITTED_36','maps':accepted,'candidate_counts':dict(counts),'initial_heading':0,'generator':'Original R/BP/M geometry + pair + dynamics laws with H2-only Philox namespace','limitations':'G1 certificates are conservative static geometry only, not dynamic safety. No reserved signatures available; no full graph-edit near-duplicate proof.','source_commit':__import__('h2_final_common').commit()});manifest(target)
    except BaseException:
        import traceback
        (target/'failure.txt').write_text(traceback.format_exc());manifest(target);raise
    finally:backend.close()
if __name__=='__main__':main()
