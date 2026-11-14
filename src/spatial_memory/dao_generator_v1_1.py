"""dao-nav-v1 TEST generator v1.1 connectivity correction. Production population generation is disabled."""
from collections import deque
import numpy as np
from .dao_admission_v1 import stream_seed,digest,occupancy_hash,endpoint_hash
FAMILIES=('tree','loop','rooms','mixed')
MASTER=b'DAO-engineering-TEST-only-v1-key'


def bfs(free,start,goal=None):
    q=deque([start]);parent={start:None}
    while q:
        p=q.popleft()
        if p==goal:break
        for dx,dy in ((1,0),(0,1),(-1,0),(0,-1)):
            c=p[0]+dx,p[1]+dy
            if c in free and c not in parent:parent[c]=p;q.append(c)
    if goal is None:return parent
    if goal not in parent:return []
    path=[];p=goal
    while p is not None:path.append(p);p=parent[p]
    return path[::-1]


def clearance_cells(occupancy):
    """Conservative3x3 free neighborhood certificate for all cardinal G1 poses/turns.

    Original max horizontal extent0.328m, cell0.75m and cell obstacle half0.37875m;
    a full free3x3 neighborhood is deliberately stronger than actual clearance.
    """
    a=np.asarray(occupancy);h,w=a.shape
    return {(x,y) for y in range(1,h-1) for x in range(1,w-1) if not a[y-1:y+2,x-1:x+2].any()}


def _attempt(rng,width,height,family,revisit):
    grid=np.ones((height,width),dtype=np.int8)
    nodes=[(x,y) for y in range(4,height-3,8) for x in range(4,width-3,8)]
    neighbors={p:[q for q in nodes if abs(p[0]-q[0])+abs(p[1]-q[1])==8] for p in nodes}
    visited={nodes[0]};stack=[nodes[0]];edges=[]
    while stack:
        p=stack[0] if revisit=='frequent' else stack[-1];eligible=[q for q in neighbors[p] if q not in visited]
        if not eligible:stack.pop(0 if revisit=='frequent' else -1);continue
        q=eligible[int(rng.integers(len(eligible)))];edges.append((p,q));visited.add(q);stack.append(q)
    all_edges=[(a,b) for a in nodes for b in neighbors[a] if a<b and (a,b) not in edges and (b,a) not in edges]
    extra=[]
    if family!='tree':
        fraction=float(rng.uniform(.1,.3)) if family=='loop' else float(rng.uniform(0,.2))
        count=min(len(all_edges),max(1 if family=='loop' else 0,int(np.ceil(fraction*len(all_edges)))))
        extra=[all_edges[int(i)] for i in rng.permutation(len(all_edges))[:count]]
    corridor_width=int(rng.integers(1,4))
    def paint(x,y,size):
        lo=(size-1)//2;hi=size//2
        grid[max(1,y-lo):min(height-1,y+hi+1),max(1,x-lo):min(width-1,x+hi+1)]=0
    for x,y in nodes:paint(x,y,int(rng.integers(4,7)) if family in ('rooms','mixed') else corridor_width)
    for a,b in edges+extra:
        if a[0]==b[0]:
            for y in range(min(a[1],b[1]),max(a[1],b[1])+1):paint(a[0],y,corridor_width)
        else:
            for x in range(min(a[0],b[0]),max(a[0],b[0])+1):paint(x,a[1],corridor_width)
    open_fraction=None
    if family=='mixed':
        open_fraction=float(rng.uniform(.2,.4));area=int(np.ceil(open_fraction*(width-2)*(height-2)))
        rw=max(3,min(width-2,int(np.ceil(np.sqrt(area)))));rh=min(height-2,int(np.ceil(area/rw)))
        x0=(width-rw)//2;y0=(height-rh)//2;grid[y0:y0+rh,x0:x0+rw]=0
    return grid,{'nodes':nodes,'tree_edges':edges,'extra_edges':extra,'corridor_width':corridor_width,
                 'open_fraction_target':open_fraction}


def generate_test(seed,*,family='tree',width=25,height=25,namespace='TEST',category=None,
                  persistent=None,discovery='long',revisit='frequent'):
    if namespace!='TEST':raise PermissionError('Production pilot/dev/sealed generation disabled')
    if type(seed) is not int or seed<0 or family not in FAMILIES or width not in (25,33,41) or height not in (25,33,41):raise ValueError('Invalid TEST schema parameters')
    if discovery not in ('long','occluded') or revisit not in ('frequent','rare'):raise ValueError('Invalid strata')
    def rng(name):return np.random.default_rng(stream_seed(MASTER,namespace,f'{family}|{width}|{height}|{seed}',name))
    layout=rng('layout');placement=rng('start_goal');grid=None;certificate=[]
    for attempt in range(100):
        candidate,construction=_attempt(layout,width,height,family,revisit)
        clear=clearance_cells(candidate)
        for i in placement.permutation(len(clear))[:min(24,len(clear))]:
            start=sorted(clear)[int(i)];reachable=bfs(clear,start)
            distances={start:0}
            for point,parent in reachable.items():
                if parent is not None:distances[point]=distances[parent]+1
            choices=sorted(point for point,d in distances.items() if 12<=d<=60)
            if choices:
                goal=choices[int(placement.integers(len(choices)))];certificate=bfs(clear,start,goal);grid=candidate;break
        if grid is not None:break
    if grid is None:raise RuntimeError('TEST quarantine:100 failed layout/clearance attempts')
    # Revisit treatment uses breadth-first versus depth-first spanning construction.
    # Occluded treatment adds an off-certificate3x3 island when space permits.
    reserve={(x+dx,y+dy) for x,y in certificate for dx in (-1,0,1) for dy in (-1,0,1)}
    island_applied=False;island_rejected=False
    if discovery=='occluded':
        options=[(x,y) for y in range(2,height-2) for x in range(2,width-2)
                 if (x,y) not in reserve and all((x+dx,y+dy) not in reserve for dx in (-1,0,1) for dy in (-1,0,1)) and not grid[y,x]]
        if options:
            x,y=options[int(layout.integers(len(options)))];before_island=grid.copy();grid[y-1:y+2,x-1:x+2]=1
            after_free={(xx,yy) for yy in range(height) for xx in range(width) if grid[yy,xx]==0}
            if len(bfs(after_free,min(after_free)))!=len(after_free):grid=before_island;island_rejected=True
            else:island_applied=True
    free={(x,y) for y in range(height) for x in range(width) if grid[y,x]==0}
    objects_rng=rng('objects');events_rng=rng('persistent');available=sorted(free-reserve)
    objects=[available[int(i)] for i in objects_rng.permutation(len(available))[:min(3,len(available))]]
    condition=persistent or ('unchanged','add','remove','relocate')[int(events_rng.integers(4))]
    if condition not in ('unchanged','add','remove','relocate'):raise ValueError('Invalid persistent condition')
    additions=[c for c in available if c not in objects];events=[]
    if condition!='unchanged':
        count=min(int(events_rng.integers(1,4)),len(objects),len(additions))
        for i in range(count):
            event={'step':int(events_rng.integers(10,51)),'action':condition,'cell':list(additions[i] if condition=='add' else objects[i])}
            if condition=='relocate':event['to']=list(additions[i])
            events.append(event)
    category=('none','static','moving')[seed%3] if category is None else category
    if category not in ('none','static','moving'):raise ValueError('Invalid pedestrian category')
    people_rng=rng('pedestrian_geometry');paths=[];speed=None
    if category!='none':
        all_objects=set(objects)|{tuple(e.get('to',e['cell'])) for e in events if e['action'] in ('add','relocate')}
        pedestrian_free=free-all_objects-{start}
        choices=sorted(pedestrian_free);count=int(people_rng.integers(1,3))
        for j in range(count):
            a=choices[int(people_rng.integers(len(choices)))];near=[p for p in choices if 2<=abs(p[0]-a[0])+abs(p[1]-a[1])<=5]
            route=bfs(pedestrian_free,a,near[int(people_rng.integers(len(near)))]) if near else []
            if not route:paths.append([a]);continue
            if category=='static':paths.append([a]);continue
            cycle=route+route[-2:0:-1];speed=float(people_rng.choice([.25,.5,.75]));expanded=[]
            for k,cell in enumerate(cycle):expanded.extend([cell]*(4 if speed==.25 else 2 if speed==.5 else 2 if k%3==0 else 1))
            paths.append(expanded)
    schedules=[]
    for index in (0,1):
        phase=rng(f'phase{index}');schedules.append([path[(offset:=int(phase.integers(len(path)))):]+path[:offset] for path in paths])
    result={'schema_version':'dao-nav-v1','generator_version':'dao-generator-v1.1-engineering','admission_version':'dao-admission-v1-engineering','partition':'TEST','lineage_id':f'TEST:v1_1:{family}:{width}x{height}:{seed}',
        'parent_seed_commitment':digest(['TEST',seed]),'family':family,'width':width,'height':height,'cell_size_m':.75,
        'occupancy':grid.tolist(),'start':list(start),'goal':list(goal),'start_heading':int(placement.integers(4)),
        'objects':[list(c) for c in objects],'events':events,'persistent_condition':condition,'pedestrian_category':category,
        'pedestrian_speed_cells_step':speed,'schedules':schedules,'discovery_stratum':discovery,'revisit_stratum':revisit,
        'construction':construction,'attempts':attempt+1,'certificate':[list(c) for c in certificate],
        'stream_names':['layout','objects','persistent','start_goal','pedestrian_geometry','phase0','phase1'],
        'occlusion_island_applied':island_applied,'occlusion_island_rejected_for_connectivity':island_rejected,'revisit_treatment_implemented':True,'production_ready':False}
    result['roots']=[result['lineage_id']]
    result['occupancy_hash']=occupancy_hash(grid);result['endpoint_hash']=endpoint_hash(grid,start,goal)
    validate(result);return result


def validate(payload):
    if payload['schema_version']!='dao-nav-v1' or payload['partition']!='TEST':raise PermissionError('TEST schema only')
    g=np.asarray(payload['occupancy']);h,w=g.shape
    if w not in (25,33,41) or h not in (25,33,41) or (w,h)!=(payload['width'],payload['height']) or payload['cell_size_m']!=.75 or not np.isin(g,[0,1]).all():raise ValueError('Bad occupancy schema')
    if not(g[0].all() and g[-1].all() and g[:,0].all() and g[:,-1].all()):raise ValueError('Boundary required')
    free={(x,y) for y in range(h) for x in range(w) if g[y,x]==0}
    if not free or len(bfs(free,min(free)))!=len(free):raise ValueError('Disconnected free layout')
    if payload['start_heading'] not in (0,1,2,3):raise ValueError('Invalid public initial heading')
    path=list(map(tuple,payload['certificate']));start=tuple(payload['start']);goal=tuple(payload['goal'])
    if not path or path[0]!=start or path[-1]!=goal or not 12<=len(path)-1<=60:raise ValueError('Certificate endpoints/length')
    if any(abs(a[0]-b[0])+abs(a[1]-b[1])!=1 for a,b in zip(path,path[1:])):raise ValueError('Invalid path')
    objects=set(map(tuple,payload['objects']));events=sorted(payload['events'],key=lambda e:e['step'])
    for event in [None]+events:
        if event:
            if not 10<=event['step']<=50 or event['action'] not in ('add','remove','relocate'):raise ValueError('Bad event')
            cell=tuple(event['cell'])
            if event['action'] in ('remove','relocate'):objects.discard(cell)
            if event['action']=='add':objects.add(cell)
            if event['action']=='relocate':objects.add(tuple(event['to']))
        occupancy=g.copy()
        for x,y in objects:
            if not(0<=x<w and 0<=y<h) or g[y,x]:raise ValueError('Object in wall')
            occupancy[y,x]=1
        if not set(path)<=clearance_cells(occupancy):raise ValueError('G1 conservative certificate invalid')
    if len(payload['schedules'])!=2:raise ValueError('Exactly two schedules')
    for schedule in payload['schedules']:
        for trajectory in schedule:
            if not trajectory:raise ValueError('Empty pedestrian')
            cells=list(map(tuple,trajectory))
            if any(not(0<=x<w and 0<=y<h) or g[y,x] for x,y in cells):raise ValueError('Pedestrian in wall')
            if any(abs(a[0]-b[0])+abs(a[1]-b[1])>1 for a,b in zip(cells,cells[1:]+cells[:1])):raise ValueError('Noncardinal pedestrian')
    if payload['occupancy_hash']!=occupancy_hash(g) or payload['endpoint_hash']!=endpoint_hash(g,start,goal):raise ValueError('Hash mismatch')
    return True


def generate_population(*args,**kwargs):raise PermissionError('Production generation requires separately approved custodian workflow; disabled')


def generate_test_logged(seed,log_directory,**kwargs):
    from pathlib import Path
    from .dao_admission_v1 import ImmutableLog,canonical
    log=ImmutableLog(Path(log_directory)/'generation')
    log.append({'event':'TEST_generation_intent','seed':seed,'parameters':kwargs})
    payload=generate_test(seed,**kwargs);directory=Path(log_directory)/'payloads';directory.mkdir(parents=True,exist_ok=True)
    filename=digest(payload)+'.json'
    with (directory/filename).open('x') as f:f.write(canonical(payload).decode()+'\n')
    log.append({'event':'TEST_generated','lineage_id':payload['lineage_id'],'payload_digest':digest(payload),'path':filename})
    return payload
