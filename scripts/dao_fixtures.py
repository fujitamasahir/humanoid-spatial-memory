"""Hand-defined public engineering states, never navigation populations.

No RNG, FIT input, production generator or simulator imports. Four observation
ages cross twelve named public-memory mechanisms. Not efficacy examples.
"""
import math
import numpy as np

FAMILIES = ('explored', 'corridor', 'new_room', 'turn', 'repeat_view',
            'unknown_occluder', 'irrelevant_discovery', 'stale_important',
            'persistent_addition', 'persistent_removal', 'temporary_occlusion',
            'no_route_no_benefit')


def fixtures():
    output = []
    for family in FAMILIES:
        for step in (3, 5, 9, 10):
            g = np.zeros((15, 15), dtype=np.int8); pos = (3, 7); yaw = 0.
            route = [(x, 7) for x in range(3, 9)]; goal = (12, 7)
            followup = None
            if family == 'corridor':
                g[6, :] = 1; g[8, :] = 1; g[7, 5:] = -1
            elif family in ('new_room', 'unknown_occluder'):
                g[:, 6:] = -1
            elif family == 'turn':
                yaw = math.pi/2; g[10:, :] = -1
                route = [(3, y) for y in range(7, 13)]
            elif family in ('repeat_view', 'stale_important'):
                # Fresh forward view, old cells behind the current FOV.
                pass
            elif family == 'irrelevant_discovery':
                g[:, 6:] = -1; route = [(3, y) for y in range(7, 13)]; goal = (3, 12)
            elif family == 'no_route_no_benefit':
                g[6, :] = 1; g[8, :] = 1; g[7, 4] = 1; route = None
            elif family in ('persistent_removal', 'temporary_occlusion'):
                g[7, 6] = 1; route = None
                followup = {'cell':[6,7], 'value':0}
            elif family == 'persistent_addition':
                followup = {'cell':[6,7], 'value':1}
            last = np.where(g>=0, 0, -1).astype(np.int64)
            if family in ('repeat_view','stale_important'):
                last[:, 3:] = step-1
            output.append({'id':f'{family}_t{step}', 'family':family,'step':step,
                'last_scan_step':0 if family not in ('repeat_view','stale_important') else step-1,
                'position':list(pos),'yaw':yaw,'goal':list(goal),'route':route,
                'grid':g.tolist(),'last_observed':last.tolist(),'followup':followup,
                'unknown_occluder_hypothesis':[6,7] if family=='unknown_occluder' else None})
    return output
