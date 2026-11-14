"""Pre-observation public features for retrospective omission diagnostics.

The functions accept only authorized earlier readings, public poses and goal.
No world, current/future scan, emergency scan, truth, or outcome input.
"""
from __future__ import annotations
import numpy as np
from .discovery_observation import DAOParameters,predicted_footprints
from .dao_navigation_compat_v1_1 import safe_public_route
from .navigation import heading_index

class AuthorizedHistory:
    def __init__(self,shape):
        self.grid=np.full(shape,-1,np.int8)
        self.last=np.full(shape,-1,np.int64)
        self.changed=np.full(shape,-1,np.int64)
        self.last_step=-1
        self.last_pose=None
        self.last_yaw=None
        self.last_mask=np.zeros(shape,bool)
        self.last_change_count=0
        self.readings=0

    def update(self,reading,step,pose,yaw):
        a=np.asarray(reading)
        if (type(step) is not int or step<=self.last_step or a.shape!=self.grid.shape
                or not np.isin(a,[-1,0,1]).all()):
            raise ValueError('Ordered authorized ternary reading required')
        visible=a>=0
        changed=visible&(self.grid>=0)&(a!=self.grid)
        self.changed[changed]=step
        self.grid[visible]=a[visible]
        self.last[visible]=step
        self.last_mask=visible.copy()
        self.last_step=step
        self.last_pose=tuple(pose)
        self.last_yaw=float(yaw)
        self.last_change_count=int(changed.sum())
        self.readings+=1

    def features(self,step,pose,yaw,goal,parameters=None):
        if self.readings==0 or type(step) is not int or step<=self.last_step:
            raise ValueError('Strictly pre-observation history required')
        p=parameters or DAOParameters();pose=tuple(pose);goal=tuple(goal)
        grid=self.grid;last=self.last
        route=safe_public_route(grid,pose,goal,'optimistic')
        prefix=route[1:p.route_moves+1]
        band={(x,y) for rx,ry in prefix
              for x in range(max(0,rx-p.route_band),min(grid.shape[1],rx+p.route_band+1))
              for y in range(max(0,ry-p.route_band),min(grid.shape[0],ry+p.route_band+1))
              if abs(x-rx)+abs(y-ry)<=p.route_band}
        footprints=predicted_footprints(grid,pose,yaw)
        opt=footprints['optimistic'];frontier=footprints['frontier']
        unknown=lambda c:grid[c[1],c[0]]<0
        occupied=lambda c:grid[c[1],c[0]]==1
        stale=lambda c:last[c[1],c[0]]>=0 and step-last[c[1],c[0]]>=p.age
        recent=lambda c:self.changed[c[1],c[0]]>=0 and step-self.changed[c[1],c[0]]<=p.fallback_age
        vis=opt&band
        last_overlap=sum(bool(self.last_mask[y,x]) for x,y in opt)
        return {'prior_paid':self.readings,'gap':step-self.last_step,
            'previous_changed_known':self.last_change_count,
            'same_pose':pose==self.last_pose,'same_heading':heading_index(yaw)==heading_index(self.last_yaw),
            'displacement_cells':sum(abs(a-b) for a,b in zip(pose,self.last_pose)),
            'route_available':bool(prefix),'route_length':len(route)-1 if route else None,
            'prefix_length':len(prefix),'prefix_unknown':sum(unknown(c) for c in prefix),
            'route_unknown':sum(unknown(c) for c in route[1:]),
            'visible_band_unknown':sum(unknown(c) for c in vis),
            'frontier_band_unknown':sum(unknown(c) for c in frontier&band),
            'visible_band_stale_occupied':sum(occupied(c) and stale(c) for c in vis),
            'band_recent_changed':sum(recent(c) for c in band),
            'visible_recent_changed':sum(recent(c) for c in opt),
            'frontier_new':sum(unknown(c) for c in frontier),
            'optimistic_new':sum(unknown(c) for c in opt),
            'frontier_stale':sum(stale(c) for c in frontier),
            'optimistic_visible':len(opt),'previous_view_overlap_count':last_overlap,
            'previous_view_overlap_fraction':last_overlap/len(opt) if opt else 0.}

def diagnostic_rules(f,p=None):
    """Fixed descriptive masks, not a selected or validated rollout policy."""
    p=p or DAOParameters()
    route_known=f['route_available'] and f['prefix_unknown']==0
    stable=route_known and f['band_recent_changed']==0 and f['visible_band_stale_occupied']==0
    later=f['prior_paid']>=2
    return {
        'all':True,
        'frontier_no_new':f['frontier_new']==0,
        'previous_no_change':f['previous_changed_known']==0,
        'known_prefix':bool(route_known),
        'known_prefix_no_visible_unknown':bool(route_known and f['visible_band_unknown']==0),
        'stable_prefix':bool(stable),
        'stable_prefix_later':bool(stable and later),
        'stable_prefix_later_previous_no_change':bool(stable and later and f['previous_changed_known']==0),
        'stable_prefix_high_overlap':bool(stable and later and f['previous_view_overlap_fraction']>=p.fraction),
        'stable_prefix_same_pose':bool(stable and later and f['same_pose'] and f['same_heading']),
        'fully_known_route':bool(route_known and f['route_unknown']==0),
    }
