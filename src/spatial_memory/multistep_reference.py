"""Independent finite-prefix reference. No imports from C v2.1 policy code.

Enumeration uses only the frozen public A* and an independently written ray
footprint. Routes are checked separately with BFS for shortest-path validity.
"""
from __future__ import annotations
from collections import deque
import math
import numpy as np
from .navigation import plan


def footprint(grid,position,yaw,sensor):
    cells=set();limit=sensor['range_m']/sensor['cell_size']
    count=math.ceil(limit/.1)+1
    angles=np.linspace(-sensor['horizontal_fov_deg']/2,sensor['horizontal_fov_deg']/2,61)
    for angle in angles:
        a=yaw+math.radians(float(angle))
        for j in range(count):
            distance=limit*j/(count-1) if count>1 else 0
            xy=(math.floor(position[0]+math.cos(a)*distance+.5),math.floor(position[1]+math.sin(a)*distance+.5))
            x,y=xy
            if not 0<=x<grid.shape[1] or not 0<=y<grid.shape[0]:break
            cells.add(xy)
            if grid[y,x]==1:break
    return cells


def bfs_distance(grid,start,goal,unknown):
    queue=deque([(tuple(start),0)]);seen={tuple(start)}
    while queue:
        c,d=queue.popleft()
        if c==tuple(goal):return d
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nxt=c[0]+dx,c[1]+dy;x,y=nxt
            if 0<=x<grid.shape[1] and 0<=y<grid.shape[0] and nxt not in seen and grid[y,x]!=1 and not (unknown=='blocked' and grid[y,x]==-1):
                seen.add(nxt);queue.append((nxt,d+1))
    return None


def reference_cell(grid,cell,q,start,goal,yaw,unknown,sensor,price,visibility=True,horizon=3):
    routes=[]
    for outcome in (0,1):
        changed=grid.copy();changed[cell[1],cell[0]]=outcome
        route=plan(changed,tuple(start),tuple(goal),unknown)
        distance=bfs_distance(changed,start,goal,unknown)
        if (distance is None)!=(not route) or (route and len(route)-1!=distance):raise ValueError('Frozen planner is not shortest on fixture')
        routes.append(route)
    table=np.empty((2,2))
    for r in range(2):
      for o in range(2):
        table[r,o]=80 if not routes[r] else len(routes[r])-1+80*int(o==1 and cell in routes[r])
    weights=np.array([1-q,q]);noinfo=float(min(table@weights))
    perfect=float(weights@np.min(table,axis=0));future=[]
    for choice in range(2):
      for time in range(1,horizon+1):
        costs=[];predicted=[];states=[]
        for outcome in range(2):
            path=routes[choice];trail=[tuple(start)];heading=yaw;hit=False
            for action in path[1:time+1]:
                if hit:break
                pos=trail[-1];heading=math.atan2(action[1]-pos[1],action[0]-pos[0])
                if outcome==1 and action==cell:hit=True
                else:trail.append(action)
            visible=(cell in footprint(grid,trail[-1],heading,sensor)) if visibility else True
            winner=int(np.argmin(table[:,outcome]));optimal=routes[winner]
            if not visible:
                loss=float(table[choice,outcome])
            elif not optimal or (outcome and cell in optimal):
                loss=time+float(table[winner,outcome])
            else:
                # Brute-force all backward prefix lengths and all suffix joins.
                possible=[]
                for back in range(len(trail)):
                    at=trail[len(trail)-1-back]
                    for join in range(len(optimal)):
                        if optimal[join]==at:possible.append(time+back+len(optimal)-join-1)
                loss=min(possible)
            costs.append(loss);predicted.append(visible)
            states.append({'position':trail[-1],'yaw':heading,'visible':visible,
                           'blocked_in_hypothesis':hit})
        future.append({'route':choice,'h':time,'movement':float(weights@np.array(costs)),
                       'visible':predicted,'states':states})
    delayed=min(v['movement'] for v in future)
    now=perfect+price;alternative=min(noinfo,delayed+price)
    net=alternative-now
    if abs(net)<1e-12:net=0.
    shared=0
    for a,b in zip(*routes):
        if a!=b:break
        shared+=1
    return {'value':max(0.,noinfo-perfect),'delay_regret':max(0.,delayed-perfect),
            'no_information_cost':noinfo,'informed_movement_cost':perfect,
            'observe_now_cost':now,'best_postpone_cost':delayed+price,
            'net_value':net,'scan':net>0,'shared_prefix_moves':max(0,shared-1),
            'routes':routes,'options':future}
