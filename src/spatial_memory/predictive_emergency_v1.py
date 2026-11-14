"""Common predictive safety candidate; independent emergency measurements only.

Conditional discrete-model certification, NOT real-world/occluded-world safety.
No scene, world, actual collision checker or future trajectory is retained.
"""
from dataclasses import dataclass
import math
from .navigation import CARDINALS,HEADINGS,heading_index,blocked_action_key

@dataclass(frozen=True)
class PredictiveParameters:
    speed_cells_per_transition:int=1
    lookahead_transitions:int=2
    max_track_age:int=2
    proxy_radius_m:float=.19


def reachable(cells,transitions,width,height):
    if type(transitions) is not int or transitions<0:raise ValueError('Nonnegative integer horizon')
    return {(x+dx,y+dy) for x,y in cells for dx in range(-transitions,transitions+1)
            for dy in range(-transitions,transitions+1) if abs(dx)+abs(dy)<=transitions
            and 0<=x+dx<width and 0<=y+dy<height}


def segment_box(start,end,point,hx,hy):
    """Exact slab intersection of a center segment with an expanded XY box."""
    lo,hi=0.,1.
    for a,b,c,r in zip(start,end,point,(hx,hy)):
        delta=b-a
        if abs(delta)<1e-12:
            if abs(a-c)>r:return False
        else:
            u,v=(c-r-a)/delta,(c+r-a)/delta;lo=max(lo,min(u,v));hi=min(hi,max(u,v))
            if lo>hi:return False
    return True


def action_geometry(position,yaw,action,extents,cell_size):
    kind,value=action
    if kind in ('move','sidestep','retreat'):
        end=tuple(value);c,s=abs(math.cos(yaw)),abs(math.sin(yaw))
        hx=(c*extents[0]+s*extents[1])/cell_size;hy=(s*extents[0]+c*extents[1])/cell_size
        return end,(hx,hy),False
    if kind=='turn':
        # Circumradius box covers every intermediate orientation, even at45deg.
        radius=math.hypot(*extents)/cell_size
        return tuple(position),(radius,radius),True
    c,s=abs(math.cos(yaw)),abs(math.sin(yaw))
    return tuple(position),((c*extents[0]+s*extents[1])/cell_size,(s*extents[0]+c*extents[1])/cell_size),False


def swept_cells(position,end,half,width,height,padding=.505):
    hx,hy=half[0]+padding,half[1]+padding
    return {(x,y) for x in range(math.ceil(min(position[0],end[0])-hx),math.floor(max(position[0],end[0])+hx)+1)
        for y in range(math.ceil(min(position[1],end[1])-hy),math.floor(max(position[1],end[1])+hy)+1)
        if 0<=x<width and 0<=y<height and segment_box(position,end,(x,y),hx,hy)}


class PredictiveEmergencySafetyV1:
    def __init__(self,scene,parameters=None):
        self.width=scene.scenario.width;self.height=scene.scenario.height;self.cell_size=scene.cell_size
        self.extents=tuple(scene.footprint_half_extents_local);self.p=parameters or PredictiveParameters()
        self.tracks=[];self.last_step=-1;self.diagnostics=[]

    def choose(self,memory_grid,position,goal,heading_yaw,selected_action,measurement,step,blocked_actions=frozenset()):
        del memory_grid
        if type(step) is not int or step<=self.last_step or int(measurement['record']['step'])!=step:raise ValueError('Fresh monotonic independent scan required')
        current={tuple(c) for c in measurement['visible_pedestrian_cells']}
        if any(not(0<=x<self.width and 0<=y<self.height) for x,y in current):raise ValueError('Invalid measured hit')
        # Unique fresh reacquisition can replace its previous unique cell. Multiple
        # ambiguous tracks retain unmatched possibilities rather than using velocity.
        old=[(t,c) for t,c in self.tracks if step-t<=self.p.max_track_age]
        unique=(len(current)==1 and len(old)==1 and abs(next(iter(current))[0]-old[0][1][0])+abs(next(iter(current))[1]-old[0][1][1])<=step-old[0][0])
        if unique:old=[]
        self.tracks=old+[(step,c) for c in sorted(current)]
        possibilities=set()
        for timestamp,cell in self.tracks:
            possibilities|=reachable({cell},(step-timestamp)*self.p.speed_cells_per_transition,self.width,self.height)
        next_set=reachable(possibilities,self.p.lookahead_transitions*self.p.speed_cells_per_transition,self.width,self.height)
        selected=selected_action or ('wait','no_feasible_base_action')
        self.last_step=step;scan=measurement['grid'];face=heading_index(heading_yaw);dx,dy=CARDINALS[face]
        def assess(action):
            kind,value=action
            if kind in ('move','sidestep','retreat'):
                target=tuple(value)
                if abs(target[0]-position[0])+abs(target[1]-position[1])!=1:return {'certified':False,'reason':'noncardinal'}
            elif kind=='turn':
                if value not in range(4):return {'certified':False,'reason':'invalid_turn'}
            elif kind!='wait':return {'certified':False,'reason':'unsupported'}
            if kind!='wait' and blocked_action_key(position,face,action) in blocked_actions:return {'certified':False,'reason':'prior_rejection'}
            end,half,rotation=action_geometry(position,heading_yaw,action,self.extents,self.cell_size)
            if not(0<=end[0]<self.width and 0<=end[1]<self.height):return {'certified':False,'reason':'bounds'}
            cells=swept_cells(position,end,half,self.width,self.height)
            # Allow robot's CURRENT grid cell as the existing public pose, but no
            # inferred memory update: all other clearance cells must be measured free.
            static_clear=all(scan[y,x]==0 for x,y in cells if (x,y)!=tuple(position))
            radius=self.p.proxy_radius_m/self.cell_size
            hit_current=any(segment_box(position,end,c,half[0]+radius,half[1]+radius) for c in possibilities)
            if rotation:
                # Endpoint retains the actual target orientation after a turn.
                target_yaw=HEADINGS[int(value)];c,s=abs(math.cos(target_yaw)),abs(math.sin(target_yaw))
                endpoint=((c*self.extents[0]+s*self.extents[1])/self.cell_size,(s*self.extents[0]+c*self.extents[1])/self.cell_size)
            else:endpoint=half
            hit_future=any(abs(end[0]-c[0])<=endpoint[0]+radius and abs(end[1]-c[1])<=endpoint[1]+radius for c in next_set)
            return {'certified':bool(static_clear and not hit_current and not hit_future),
                'static_measured_clear':bool(static_clear),'current_sweep_risk':hit_current,'future_endpoint_risk':hit_future,
                'swept_cells':sorted(cells),'end':end,'rotation_circumradius_bound':rotation}
        before=assess(selected)
        record={'step':step,'current_possible_cells':sorted(possibilities),'two_transition_reachable':sorted(next_set),
            'track_samples':[[t,list(c)] for t,c in self.tracks],'selected_assessment':before,
            'certification_scope':'grid-centered radius.19 proxy, speed<=1 cardinal/transition, stationary pedestrians during action, observed tracks only; unseen entries not certified',
            'no_certifiably_safe_action':False,'had_observed_tracks':bool(possibilities)}
        if not possibilities:
            record.update(reason='no_observed_tracks_no_global_guarantee',selected_after=selected);self.diagnostics.append(record);return None
        if before['certified']:
            record.update(reason='selected_sweep_and_endpoint_conditionally_safe',selected_after=selected);self.diagnostics.append(record);return None
        left=(-dy,dx);catalog=[selected,('move',(position[0]+dx,position[1]+dy)),
            ('sidestep',(position[0]+left[0],position[1]+left[1])),('sidestep',(position[0]-left[0],position[1]-left[1])),
            ('retreat',(position[0]-dx,position[1]-dy)),('turn',(face+1)%4),('turn',(face-1)%4),('wait','predictive_wait')]
        candidates=[];seen=set();assessments=[]
        for rank,action in enumerate(catalog):
            key=str(action)
            if key in seen:continue
            seen.add(key);detail=assess(action);assessments.append({'action':action,**detail})
            if detail['certified']:
                end=detail['end'];distance=abs(end[0]-goal[0])+abs(end[1]-goal[1])
                candidates.append((distance,rank,action))
        if candidates:chosen=min(candidates,key=lambda x:(x[0],x[1]))[2];reason='bounded_reachable_sweep_override'
        else:chosen=('wait','predictive_no_certifiably_safe_action');reason='no_certifiably_safe_action';record['no_certifiably_safe_action']=True
        record.update(reason=reason,selected_after=chosen,alternatives=assessments);self.diagnostics.append(record)
        if chosen==selected:return None
        return {'action':chosen,'intervention':{'step':step,'position_before_action':list(position),'heading_yaw':heading_yaw,
            'selected_action_before':selected,'selected_action_after':chosen,'reason':reason,
            'motion_estimate':measurement['motion_estimate'],'visible_pedestrian_cells':[list(c) for c in sorted(current)],
            'reachable_proxy_cells_from_observations':[list(c) for c in sorted(next_set)],
            'no_certifiably_safe_action':record['no_certifiably_safe_action'],
            'escape_clearance_source':'current independent scan and public swept bounds, never actual alternative shield probes'}}
