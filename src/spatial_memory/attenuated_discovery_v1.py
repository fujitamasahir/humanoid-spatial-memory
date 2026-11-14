"""Attenuated discovery estimate using only public ternary raster geometry.

q is an assumed per-unknown-cell transmission factor, NOT a learned or
calibrated occupation probability. Max across rays avoids counting the
same cell repeatedly or assuming independence between overlapping rays.
"""
import math
import numpy as np
from .discovery_observation import _grid,_point

FACTORS=(.5,.8)

def attenuated_footprints(grid,position,yaw,*,range_m=6.,cell_size=.75,
                          horizontal_fov_deg=120.,ray_count=61,factors=FACTORS):
    grid=_grid(grid);position=_point(position,grid.shape)
    if (ray_count!=61 or not all(math.isfinite(v) for v in
            (yaw,range_m,cell_size,horizontal_fov_deg)) or cell_size<=0
            or not 0<range_m/cell_size<=8 or not 0<horizontal_fov_deg<=120):
        raise ValueError('Unsupported bounded geometry')
    if not factors or any(not math.isfinite(q) or not 0<=q<=1 for q in factors):
        raise ValueError('Transmission factor must be in [0,1]')
    # The least number of distinct preceding unknown cells encountered along
    # any individual ray. The target unknown itself is not an occluder.
    depth={};samples=0
    distances=np.linspace(0,range_m/cell_size,math.ceil(range_m/cell_size/.1)+1)
    for angle in np.linspace(-horizontal_fov_deg/2,horizontal_fov_deg/2,61):
        theta=yaw+math.radians(angle);seen_unknown=set()
        for d in distances:
            samples+=1
            x=math.floor(position[0]+d*math.cos(theta)+.5)
            y=math.floor(position[1]+d*math.sin(theta)+.5)
            if not(0<=x<grid.shape[1] and 0<=y<grid.shape[0]):break
            cell=(x,y)
            if cell!=position:
                k=len(seen_unknown)-(cell in seen_unknown)
                depth[cell]=min(depth.get(cell,k),k)
                if grid[y,x]==-1:seen_unknown.add(cell)
            if grid[y,x]==1:break
    unknown={c:k for c,k in depth.items() if grid[c[1],c[0]]==-1}
    return {'optimistic':set(depth),'frontier':{c for c,k in depth.items() if k==0},
            'unknown_depth':unknown,'weights':{q:{c:q**k for c,k in unknown.items()} for q in factors},
            'sample_visits':samples,'actual_sensor_calls':0}
