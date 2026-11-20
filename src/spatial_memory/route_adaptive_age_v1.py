"""RAA v1: Age5 parent with bounded Age4 advance and one-decision deferral.

Only authorized last-write memory/history and public point-grid planning.
No simulator, emergency observations, shield, inference or future visibility.
"""
from dataclasses import dataclass
from time import perf_counter_ns
import math
import numpy as np
from .memory import Memory
from .navigation import plan,heading_index
from .evi import visible_cells

MODES=('raa_advance','raa_defer','raa_joint','raa_off')


def swept_prefix(route,yaw,moves,shape,extents=(.218954831277208,.3279970912029507),cell_size=.75):
    """Public conservative AABB/circumradius raster, at most five point edges."""
    cells=set();heading=heading_index(yaw);visits=0
    for start,end in zip(route[:moves],route[1:moves+1]):
        dx,dy=end[0]-start[0],end[1]-start[1]
        if abs(dx)+abs(dy)!=1:raise ValueError('Cardinal public route required')
        face={(1,0):0,(0,1):1,(-1,0):2,(0,-1):3}[dx,dy]
        if face!=heading:
            radius=math.hypot(*extents)/cell_size+.505
            for x in range(math.ceil(start[0]-radius),math.floor(start[0]+radius)+1):
                for y in range(math.ceil(start[1]-radius),math.floor(start[1]+radius)+1):
                    if 0<=x<shape[1] and 0<=y<shape[0]:cells.add((x,y));visits+=1
        hx,hy=(extents if face%2==0 else extents[::-1]);rx,ry=hx/cell_size+.505,hy/cell_size+.505
        # Movement is cardinal: union over segment of axis-aligned footprint.
        for x in range(math.ceil(min(start[0],end[0])-rx),math.floor(max(start[0],end[0])+rx)+1):
            for y in range(math.ceil(min(start[1],end[1])-ry),math.floor(max(start[1],end[1])+ry)+1):
                if 0<=x<shape[1] and 0<=y<shape[0]:cells.add((x,y));visits+=1
        heading=face
    return cells,visits


def mechanism_rule(detail,*,used,gap,enable_advance,enable_defer):
    """Pure decision gate; forced-next enforcement belongs to the controller."""
    protected=used<2 or not detail['route_available']
    advance=(enable_advance and not protected and detail['age4_request'] and not detail['age5_request']
             and gap>=4 and detail['observable_near_route_uncertainty'])
    defer=(enable_defer and not protected and detail['age5_request'] and gap<6
           and detail['prefix_free_fresh5'] and detail['predicted_view_known_fresh5']
           and not detail['prefix_recent_change'])
    return bool(advance),bool(defer)


class RouteAdaptiveAgeV1:
    def __init__(self,initial,method='age',*,mode='raa_joint',interval=4,radius=3,
                 parameters=None,max_observations=20,sensor=None):
        if mode not in MODES or method!='age' or radius!=3 or type(max_observations) is not int or not 1<=max_observations<=20:
            raise ValueError('Frozen Age5-based RAA configuration required')
        initial=np.asarray(initial)
        if initial.ndim!=2 or initial.size>4096:raise ValueError('Bounded2D grid required')
        self.memory=Memory(initial.shape);self.memory.update(initial)
        self.last_observed=np.where(initial>=0,0,-1).astype(np.int64)
        self.changed=np.full(initial.shape,-1,np.int64);self.reobserved=np.zeros(initial.shape,np.int64)
        self.mode=mode;self.radius=radius;self.fraction=parameters.stale_fraction if parameters else .5
        self.sensor=dict(sensor or {'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61})
        if self.sensor!={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}:raise ValueError('Original sensor geometry required')
        self.used=1;self.cap=max_observations;self.requests=self.denied=0
        self.last_scan_step=0;self.latest_decision=0;self.pending=None;self.forced_step=None;self.context=None
        self.decisions=[];self.scheduler_ns=0;self.update_ns=0

    def set_navigation_context(self,*,goal,yaw,unknown='optimistic'):
        if unknown not in ('optimistic','blocked') or not math.isfinite(yaw):raise ValueError('Invalid public context')
        self.context=(tuple(goal),float(yaw),unknown)

    def age_scores(self,step,position):
        x,y=position;r=3;h,w=self.memory.grid.shape;x0,x1=max(0,x-r),min(w,x+r+1);y0,y1=max(0,y-r),min(h,y+r+1)
        yy,xx=np.ogrid[y0:y1,x0:x1];last=self.last_observed[y0:y1,x0:x1]
        known=(last>=0)&((xx-x)**2+(yy-y)**2<=9)
        return {str(a):float(np.mean(step-last[known]>=a)) if known.any() else 0. for a in (4,5,6)}

    def features(self,step,position,yaw,goal,unknown,scores):
        grid=self.memory.grid;last=self.last_observed;route=plan(grid,tuple(position),goal,unknown)
        if any(grid[y,x]==1 for x,y in route[:6]):route=[]
        p4,v4=swept_prefix(route,yaw,4,grid.shape);p5,v5=swept_prefix(route,yaw,5,grid.shape)
        view=visible_cells(grid,position,yaw,**self.sensor)-{tuple(position)}
        recent=lambda c:self.changed[c[1],c[0]]>=0 and step-self.changed[c[1],c[0]]<=5
        observable_uncertain={c for c in p4&view if grid[c[1],c[0]]<0 or recent(c)}
        free_fresh=bool(p5) and all(grid[y,x]==0 and 0<=step-last[y,x]<5 for x,y in p5)
        view_fresh=bool(view) and all(last[y,x]>=0 and step-last[y,x]<5 for x,y in view)
        return {'age_scores':scores,'age4_request':scores['4']>=self.fraction,'age5_request':scores['5']>=self.fraction,
           'route_available':len(route)>1,'prefix_free_fresh5':free_fresh,'predicted_view_known_fresh5':view_fresh,
           'prefix_recent_change':any(recent(c) for c in p5),'observable_near_route_uncertainty':bool(observable_uncertain),
           'observable_uncertain_cells':sorted(observable_uncertain),'route_prefix':route[:6],
           'prefix_swept_cells':sorted(p5),'predicted_visible':len(view),
           'predicted_unknown':sum(grid[y,x]<0 for x,y in view),
           'predicted_stale5':sum(last[y,x]>=0 and step-last[y,x]>=5 for x,y in view),
           'point_plan_calls':1,'predicted_footprints':1,'sweep_cell_visits':v4+v5,'actual_sensor_calls':0}

    def decide(self,step,position):
        if type(step) is not int or step<=self.latest_decision or self.pending is not None or self.context is None:raise RuntimeError('Fresh context, increasing step and consumed grant required')
        if len(position)!=2 or any(type(v) not in (int,np.int64,np.int32) for v in position):raise ValueError('Integer public pose required')
        position=tuple(map(int,position));h,w=self.memory.grid.shape
        if not(0<=position[0]<w and 0<=position[1]<h):raise ValueError('Public pose outside grid')
        started=perf_counter_ns();goal,yaw,unknown=self.context;scores=self.age_scores(step,position)
        age5=scores['5']>=self.fraction;detail={'age_scores':scores,'age4_request':scores['4']>=self.fraction,
            'age5_request':age5,'point_plan_calls':0,'predicted_footprints':0,'actual_sensor_calls':0}
        force=self.forced_step is not None
        if force and step!=self.forced_step:raise RuntimeError('Deferred request must be served on the next decision step')
        advance=defer=False
        eligible=self.used<self.cap and self.mode!='raa_off' and self.used>=2 and (age5 or (scores['4']>=self.fraction and step-self.last_scan_step>=4))
        if not force and eligible:
            detail=self.features(step,position,yaw,goal,unknown,scores)
            advance,defer=mechanism_rule(detail,used=self.used,gap=step-self.last_scan_step,
                enable_advance=self.mode in ('raa_advance','raa_joint'),enable_defer=self.mode in ('raa_defer','raa_joint'))
        raw_request=force or advance or (age5 and not defer)
        requested=bool(raw_request and self.used<self.cap)
        if defer:self.forced_step=step+1
        elif force:self.forced_step=None
        grant=bool(requested and self.used<self.cap)
        self.requests+=int(requested);self.denied+=int(requested and not grant)
        self.pending=step if grant else None;self.latest_decision=step;self.context=None
        record={'step':step,'requested':bool(requested),'granted':grant,'used_before':self.used,
            'raw_request_before_budget':bool(raw_request),'budget_exhausted':self.used>=self.cap,'scan_gap':step-self.last_scan_step,'age5_anchor':bool(age5),'advance':advance,'deferred':defer,
            'forced_next':force,'mode':self.mode,**detail}
        self.decisions.append(record);self.scheduler_ns+=perf_counter_ns()-started
        return {'observation_requested':bool(requested),'observation_granted':grant,
            'observation_score':None if self.used>=self.cap else (1. if requested else -1.),'observation_position':position}

    def refresh(self,observation,step):
        if self.pending!=step or self.pending is None or self.used>=self.cap:raise RuntimeError('Unauthorized reading')
        a=np.asarray(observation)
        if a.shape!=self.memory.grid.shape or not np.isin(a,[-1,0,1]).all():raise ValueError('Invalid ternary observation')
        start=perf_counter_ns();visible=a>=0;known=self.last_observed>=0
        change=visible&known&(a!=self.memory.grid);self.changed[change]=step
        self.reobserved[visible&known]+=1
        self.memory.update(a);self.last_observed[visible]=step;self.used+=1;self.last_scan_step=step;self.pending=None
        self.update_ns+=perf_counter_ns()-start
