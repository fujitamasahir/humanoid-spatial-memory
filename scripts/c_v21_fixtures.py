"""Prospective public-memory fixture generator. No admitted world population.

Annotations are verified by the independent reference before policy execution.
No imports from policy implementation or navigation evaluation.
"""
from __future__ import annotations
import hashlib,json,math
import numpy as np
FAMILIES=('immediate_divergence','shared_prefix','future_branch','last_chance',
 'continued_visibility','permanent_occlusion','occupied_shortcut','irrelevant',
 'no_benefit','correlated','competing','size_heading_range')
SEED=2026111401


def _base(family,index):
    grid=np.ones((9,11),dtype=np.int8)
    if family in ('last_chance','occupied_shortcut','correlated','competing') or (family=='size_heading_range' and index%2==0):
        start=(2,4);goal=(6,2);cell=(4,2);yaw=math.radians(1.)
        cells={(1,y) for y in range(2,7)}|{(x,2) for x in range(1,7)}|{(x,6) for x in range(1,7)}|{(6,y) for y in range(2,7)}|{start,(3,3)}
        expectation='opportunity'
    else:
        start=(1,4);goal=(8,4);cell=(5,4);yaw=0.
        fork=1 if family=='immediate_divergence' else 3
        cells={(x,4) for x in range(1,9)}|{(fork,y) for y in range(1,5)}|{(x,1) for x in range(fork,9)}|{(8,y) for y in range(1,5)}
        expectation='immediate' if family=='immediate_divergence' else 'postpone'
    for x,y in cells:grid[y,x]=0
    if family=='occupied_shortcut':grid[cell[1],cell[0]]=1
    if family=='future_branch':grid[cell[1],cell[0]]=-1
    if family=='permanent_occlusion':
        grid[4,3]=1
        # Route around the known wall, while the candidate remains hidden.
        for x in range(1,6):grid[3,x]=0
        cell=(6,4);expectation='ineligible'
    if family in ('irrelevant','no_benefit'):
        cell=(1,6)
        grid[5,1]=0;grid[6,1]=0
        expectation='no_benefit'
    q=np.where(grid==1,1.,0.)
    q[cell[1],cell[0]]=(.35,.5,.65)[index%3]
    extras=[]
    if family=='correlated':
        extras=[(5,2)];q[2,5]=q[cell[1],cell[0]]
        expectation='diagnostic'
    if family=='competing':
        extras=[(3,3),(1,3),(1,5),(3,6),(5,6),(6,4)]
        for x,y in extras:q[y,x]=.5
        expectation='diagnostic'
    sensor=dict(range_m=float(5+index%3),cell_size=1.,horizontal_fov_deg=360. if family in ('irrelevant','no_benefit') else 120.,ray_count=61)
    return grid,q,start,goal,cell,extras,yaw,sensor,expectation


def build():
    fixtures=[]
    for family in FAMILIES:
      for i in range(8):
        grid,q,start,goal,cell,extras,yaw,sensor,expectation=_base(family,i)
        rng=np.random.default_rng(SEED+FAMILIES.index(family)*100+i)
        pads=tuple(int(v) for v in rng.integers(0,3,4));top,bottom,left,right=pads
        grid=np.pad(grid,((top,bottom),(left,right)),constant_values=1)
        q=np.pad(q,((top,bottom),(left,right)),constant_values=1.)
        shift=lambda c:(c[0]+left,c[1]+top)
        start,goal,cell=map(shift,(start,goal,cell));extras=list(map(shift,extras))
        rotation=i%4
        for _ in range(rotation):
            width=grid.shape[1];rotate=lambda c:(c[1],width-1-c[0])
            start,goal,cell=map(rotate,(start,goal,cell));extras=list(map(rotate,extras))
            grid=np.rot90(grid).copy();q=np.rot90(q).copy();yaw-=math.pi/2
        fixtures.append({'id':f'{family}_{i:02}','family':family,'seed':SEED+FAMILIES.index(family)*100+i,'grid':grid.tolist(),'probability':q.tolist(),'start':start,'goal':goal,'target':cell,'extra_cells':extras,'yaw':yaw,'unknown':'blocked' if family=='future_branch' and i%2 else 'optimistic','sensor':sensor,'remaining':19,'expectation':expectation,'correlation_groups':[([cell,*extras])] if family=='correlated' else []})
    return fixtures


def digest(fixtures):return hashlib.sha256(json.dumps(fixtures,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
