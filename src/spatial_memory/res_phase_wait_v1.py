"""RES-H1 phase escape: one certified wait to break a stationary turn cycle.

All ordinary choices and certificate geometry remain the frozen H1. This is a
bounded action-selection heuristic, not a guarantee of liveness or safety.
"""
from .risk_ranked_emergency_v1 import RESH1
from .navigation import heading_index

TRANSLATIONS=('move','sidestep','retreat')


class RESH1PhaseWait(RESH1):
    def __init__(self,scene):
        super().__init__(scene)
        self.pose_cell=None
        self.last_face=None
        self.visited_faces=set()
        self.cycle=False
        self.wait_used=False

    def choose(self,memory_grid,position,goal,heading_yaw,selected_action,measurement,step,blocked_actions=frozenset()):
        answer=super().choose(memory_grid,position,goal,heading_yaw,selected_action,measurement,step,blocked_actions)
        record=self.diagnostics[-1]
        position=tuple(position);face=heading_index(heading_yaw)
        if position!=self.pose_cell:
            self.pose_cell=position
            self.visited_faces={face}
            self.cycle=False
            self.wait_used=False
        elif face!=self.last_face:
            if face in self.visited_faces:self.cycle=True
            self.visited_faces.add(face)
        self.last_face=face
        chosen=record['selected_after']
        record.update(rotation_cycle=self.cycle,phase_wait_used_before=self.wait_used,
                      phase_wait_applied=False,pre_phase_selected=chosen)
        # Only replace a fallback turn caused by a rejected nominal translation.
        # A certified planned turn may be necessary to see or navigate new space.
        if (not self.cycle or self.wait_used or not record['had_observed_tracks']
                or record['no_certifiably_safe_action'] or selected_action is None
                or selected_action[0] not in TRANSLATIONS or chosen[0]!='turn'
                or record['selected_assessment'].get('certified',False)):
            return answer
        waits=[a for a in record.get('alternatives',[])
               if a['action'][0]=='wait' and a.get('certified',False)]
        if not waits:return answer
        # Reuse the exact H1 same-state assessment. One intervention until
        # the observed cell changes; unsuccessful waits do not trigger a loop.
        action=tuple(waits[0]['action'])
        self.wait_used=True
        record.update(reason='certified_single_phase_wait',selected_after=action,
                      phase_wait_applied=True,phase_wait_certificate=waits[0])
        return {'action':action,'intervention':{'step':step,'position_before_action':list(position),
            'heading_yaw':heading_yaw,'selected_action_before':selected_action,
            'selected_action_after':action,'reason':'certified_single_phase_wait',
            'motion_estimate':measurement['motion_estimate'],
            'visible_pedestrian_cells':[list(c) for c in measurement['visible_pedestrian_cells']],
            'reachable_proxy_cells_from_observations':[list(c) for c in record['one_transition_reachable']],
            'no_certifiably_safe_action':False,'uncertified_selection':False,'no_admissible_fallback':False,
            'escape_clearance_source':'existing certified H1 wait; one per stationary cell dwell'}}
