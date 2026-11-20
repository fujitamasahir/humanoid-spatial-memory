"""Versioned public-context compatibility adapter; frozen DAO remains unedited."""
from time import perf_counter_ns
from .discovery_observation import DiscoveryController
from .navigation import plan


class DAONavigationV1(DiscoveryController):
    def __init__(self, initial, method='age', *, mode, interval=4, radius=3,
                 parameters=None, max_observations=20, sensor=None):
        if method!='age' or radius!=3 or mode not in ('dao_veto','dao_trigger','dao_route','dao_combined'):
            raise ValueError('Frozen DAO integration only')
        super().__init__(initial, mode=mode, max_observations=max_observations,sensor=sensor)
        self.public_context=None;self.last_route=None
        self.route_plan_calls=0;self.route_plan_ns=0;self.scheduler_ns=0

    def set_navigation_context(self, *, goal, yaw, unknown='optimistic'):
        if unknown not in ('optimistic','blocked'):raise ValueError('Invalid public unknown rule')
        self.public_context=(tuple(goal),yaw,unknown)

    def decide(self,step,position):
        if self.public_context is None:raise RuntimeError('Fresh public context required')
        goal,yaw,unknown=self.public_context;route=None;started=perf_counter_ns()
        if self.mode=='dao_route':
            before=perf_counter_ns();route=plan(self.memory.grid,tuple(position),goal,unknown)
            self.route_plan_ns+=perf_counter_ns()-before;self.route_plan_calls+=1
        self.last_route=route
        super().set_navigation_context(goal=goal,yaw=yaw,route=route)
        result=super().decide(step,position)
        self.scheduler_ns+=perf_counter_ns()-started;self.public_context=None
        self.decisions[-1]['integration_route_plan_calls']=int(self.mode=='dao_route')
        return result
