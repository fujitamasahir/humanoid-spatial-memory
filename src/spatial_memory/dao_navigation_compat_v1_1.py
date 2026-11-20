"""v1.1 compatibility for a public route whose start is remembered occupied.

Does NOT clear that cell or change DAO mathematics. An inadmissible optional
route is absent, exactly the frozen no-route interface. v1 source is preserved.
"""
from time import perf_counter_ns
from .dao_navigation_v1 import DAONavigationV1
from .discovery_observation import DiscoveryController
from .navigation import plan


def safe_public_route(grid,position,goal,unknown='optimistic'):
    route=plan(grid,tuple(position),tuple(goal),unknown)
    return route if all(grid[y,x]!=1 for x,y in route[:6]) else []


class DAONavigationCompatV1_1(DAONavigationV1):
    def decide(self,step,position):
        if self.public_context is None:raise RuntimeError('Fresh public context required')
        goal,yaw,unknown=self.public_context;route=None;started=perf_counter_ns()
        if self.mode=='dao_route':
            before=perf_counter_ns();route=safe_public_route(self.memory.grid,position,goal,unknown)
            self.route_plan_ns+=perf_counter_ns()-before;self.route_plan_calls+=1
        self.last_route=route
        DiscoveryController.set_navigation_context(self,goal=goal,yaw=yaw,route=route)
        result=DiscoveryController.decide(self,step,position)
        self.scheduler_ns+=perf_counter_ns()-started;self.public_context=None
        self.decisions[-1]['integration_route_plan_calls']=int(self.mode=='dao_route')
        self.decisions[-1]['integration_route_unavailable_occupied_start']=bool(self.memory.grid[position[1],position[0]]==1)
        return result
