"""History-gated Deadline variants for a reused FIT development comparison."""
from time import perf_counter_ns
from .route_gated_dao_veto_v1 import RouteGatedDAOVeto
from .omission_public_features_v1 import AuthorizedHistory,diagnostic_rules

MODES={'deadline_stable':'stable_prefix_later',
       'deadline_stable_quiet':'stable_prefix_later_previous_no_change'}

class HistoryGatedDeadline(RouteGatedDAOVeto):
    def __init__(self,initial,method='age',*,history_mode,**options):
        if history_mode not in MODES:raise ValueError('Unknown frozen history mask')
        super().__init__(initial,method,gate_mode='deadline',**options)
        self.history_mode=history_mode
        self.history=AuthorizedHistory(initial.shape)
        self.initial_reading=initial.copy()
        self.pending_pose=None
        self.pending_yaw=None

    def decide(self,step,position):
        if self.public_context is None:raise RuntimeError('Fresh public context required')
        goal,yaw,unknown=self.public_context
        started=perf_counter_ns()
        if not self.history.readings:
            # Step1 is before the first action, at the initial paid scan pose.
            if step!=1:raise RuntimeError('Initial pose contract')
            self.history.update(self.initial_reading,0,position,yaw)
            self.initial_reading=None
        answer=super().decide(step,position)
        extra_started=perf_counter_ns()
        row=self.decisions[-1]
        row['history_veto']=False
        row['history_mask']=self.history_mode
        # Never suppress the initial or first noninitial scan, a missing route,
        # or an original grant once ten steps have elapsed since the last scan.
        if answer['observation_granted'] and self.history.readings>=2 and step-self.last_scan_step<self.parameters.fallback_age:
            if self.history.readings!=self.used:raise RuntimeError('History authorization drift')
            f=self.history.features(step,position,yaw,goal,self.parameters)
            mask=diagnostic_rules(f,self.parameters)[MODES[self.history_mode]]
            row['history_features']=f
            if mask and unknown=='optimistic':
                self._pending=None
                self.requests-=1
                row.update(history_veto=True,deadline_requested=True,deadline_granted=True,requested=False,granted=False)
                answer={**answer,'observation_requested':False,'observation_granted':False}
        if answer['observation_granted']:
            self.pending_pose=tuple(position)
            self.pending_yaw=yaw
        self.scheduler_ns+=perf_counter_ns()-extra_started
        return answer

    def refresh(self,observation,step):
        super().refresh(observation,step)
        self.history.update(observation,step,self.pending_pose,self.pending_yaw)
        self.pending_pose=None
        self.pending_yaw=None
        if self.history.readings!=self.used:raise RuntimeError('Authorized history count drift')
