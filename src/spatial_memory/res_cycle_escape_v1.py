"""RES-H1 cycle escape: unchanged conditional certificate, bounded action choice.

No hidden geometry, additional sensor calls or unselected shield checks.
The only online history added is the observed public pose sequence.
"""
from .risk_ranked_emergency_v1 import RESH1,action_geometry,swept_cells,segment_box
from .navigation import CARDINALS,heading_index,blocked_action_key

TRANSLATION=('move','sidestep','retreat')


def certified_translation(position,yaw,action,scan,current,next_cells,extents,cell_size,width,height,proxy_radius,blocked):
    """Same H1 translation certificate as the frozen RES-H1, not a new bound."""
    if action[0] not in TRANSLATION:return False
    end=tuple(action[1]);face=heading_index(yaw)
    if abs(end[0]-position[0])+abs(end[1]-position[1])!=1:return False
    if not(0<=end[0]<width and 0<=end[1]<height):return False
    if blocked_action_key(position,face,action) in blocked:return False
    end,half,_=action_geometry(position,yaw,action,extents,cell_size)
    cells=swept_cells(position,end,half,width,height)
    if not all(scan[y,x]==0 for x,y in cells if (x,y)!=tuple(position)):return False
    radius=proxy_radius/cell_size
    hx,hy=half[0]+radius,half[1]+radius
    if any(segment_box(position,end,c,hx,hy) for c in current):return False
    return not any(abs(end[0]-c[0])<=hx and abs(end[1]-c[1])<=hy for c in next_cells)


class RESH1CycleEscape(RESH1):
    """Intervene only on a repeated stationary heading and a selected turn.

    Ordinary turns, translations, waits, no-certificate behavior and no-track
    behavior retain H1. Only an alternative certified by the identical H1
    translation certificate may replace the turn.
    """
    def __init__(self,scene):
        super().__init__(scene)
        self.pose_cell=None
        self.last_face=None
        self.visited_faces=set()
        self.rotation_cycle=False

    def choose(self,memory_grid,position,goal,heading_yaw,selected_action,measurement,step,blocked_actions=frozenset()):
        answer=super().choose(memory_grid,position,goal,heading_yaw,selected_action,measurement,step,blocked_actions)
        record=self.diagnostics[-1]
        position=tuple(position);face=heading_index(heading_yaw)
        if position!=self.pose_cell:
            self.pose_cell=position
            self.visited_faces={face}
            self.rotation_cycle=False
        elif face!=self.last_face:
            # A,B,A is a cycle; A,B,C (a legitimate 180-degree turn) is not.
            if face in self.visited_faces:self.rotation_cycle=True
            self.visited_faces.add(face)
        self.last_face=face
        chosen=record['selected_after']
        record.update(rotation_cycle=self.rotation_cycle,cycle_escape_applied=False,
                      cycle_escape_candidates=[],pre_cycle_selected=chosen)
        if (not self.rotation_cycle or chosen[0]!='turn' or not record['had_observed_tracks']
                or record['no_certifiably_safe_action']):
            return answer
        current=record['current_possible_cells'];next_cells=record['one_transition_reachable']
        dx,dy=CARDINALS[face];lx,ly=-dy,dx
        catalog=[('move',(position[0]+dx,position[1]+dy)),
                 ('sidestep',(position[0]+lx,position[1]+ly)),
                 ('sidestep',(position[0]-lx,position[1]-ly)),
                 ('retreat',(position[0]-dx,position[1]-dy))]
        eligible=[]
        for i,action in enumerate(catalog):
            valid=certified_translation(position,heading_yaw,action,measurement['grid'],
                current,next_cells,self.extents,self.cell_size,self.width,self.height,
                self.p.proxy_radius_m,blocked_actions)
            distance=abs(action[1][0]-goal[0])+abs(action[1][1]-goal[1])
            record['cycle_escape_candidates'].append({'action':action,'certified':valid,'goal_distance':distance})
            if valid:eligible.append((distance,i,action))
        if not eligible:return answer
        escape=min(eligible,key=lambda v:v[:2])[2]
        record.update(reason='certified_rotation_cycle_escape',selected_after=escape,
                      cycle_escape_applied=True)
        return {'action':escape,'intervention':{'step':step,'position_before_action':list(position),
            'heading_yaw':heading_yaw,'selected_action_before':selected_action or ('wait','no_feasible_base_action'),
            'selected_action_after':escape,'reason':'certified_rotation_cycle_escape',
            'motion_estimate':measurement['motion_estimate'],
            'visible_pedestrian_cells':[list(c) for c in measurement['visible_pedestrian_cells']],
            'reachable_proxy_cells_from_observations':[list(c) for c in next_cells],
            'no_certifiably_safe_action':False,'uncertified_selection':False,'no_admissible_fallback':False,
            'escape_clearance_source':'unchanged H1 certificate; public repeated-heading cycle only'}}
