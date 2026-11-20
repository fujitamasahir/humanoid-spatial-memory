"""Single-scan omission for evaluator-only causal engineering experiments.

This is not a deployable observation policy: the intervention step is
stipulated by a frozen experiment schedule. It does not read omitted
observations or alter memory, planner, emergency sensing, or future decisions.
"""
from .route_gated_dao_veto_v1 import RouteGatedDAOVeto

class DeadlineSingleOmission(RouteGatedDAOVeto):
    def __init__(self,initial,method='age',*,omit_step,**options):
        if type(omit_step) is not int or omit_step<=0:
            raise ValueError('Only a specified noninitial observation may be omitted')
        super().__init__(initial,method,gate_mode='deadline',**options)
        self.omit_step=omit_step
        self.omissions=0

    def decide(self,step,position):
        answer=super().decide(step,position)
        if step!=self.omit_step:return answer
        if not answer['observation_granted'] or self._pending!=step or self.omissions:
            raise RuntimeError('Intervention requires a matching granted baseline scan')
        # The parent has counted a request but no refresh has occurred.
        # Account for the intervention as a suppressed request, not a cap denial.
        self._pending=None
        self.requests-=1
        self.omissions+=1
        self.decisions[-1].update(intervention_omitted=True,
            untreated_requested=True,untreated_granted=True,
            requested=False,granted=False)
        return {**answer,'observation_requested':False,'observation_granted':False}
