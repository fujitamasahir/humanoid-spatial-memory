"""A* accepts remembered occupancy only. Unknown handling is shared."""
import heapq
import math


def plan(grid, start, goal, unknown='optimistic'):
    if unknown not in {'optimistic', 'blocked'}:
        raise ValueError('Unknown handling must be optimistic or blocked')
    height, width = grid.shape
    frontier = [(0, start)]
    costs, parent = {start: 0}, {}
    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal:
            path = [current]
            while current in parent:
                current = parent[current]
                path.append(current)
            return path[::-1]
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            nxt = current[0]+dx, current[1]+dy
            x, y = nxt
            if not (0 <= x < width and 0 <= y < height):
                continue
            if grid[y, x] == 1 or (unknown == 'blocked' and grid[y, x] == -1):
                continue
            cost = costs[current]+1
            if cost < costs.get(nxt, float('inf')):
                costs[nxt], parent[nxt] = cost, current
                h = abs(x-goal[0])+abs(y-goal[1])
                heapq.heappush(frontier, (cost+h, nxt))
    return []


HEADINGS = (0.0, math.pi/2, math.pi, -math.pi/2)  # east, north, west, south
CARDINALS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def heading_index(yaw):
    """Nearest cardinal heading index for the kinematic G1 state."""
    return int(round(float(yaw)/(math.pi/2))) % 4


def blocked_action_key(position, heading, action):
    """Navigation feedback key; contains no sensed or hidden occupancy data."""
    x, y = position
    kind, value = action
    return (int(x), int(y), int(heading), kind,
            tuple(value) if kind in {'move', 'sidestep', 'retreat'} else int(value))


def blocked_action_evidence_signature(grid, key, radius=2):
    """Local memory snapshot around an attempted transition for reconsideration gating."""
    x, y, _, kind, value = key
    points = [(x, y)]
    if kind in {'move', 'sidestep', 'retreat'}:
        points.append(tuple(value))
    height, width = grid.shape
    x0 = max(0, min(px for px, _ in points)-radius)
    x1 = min(width, max(px for px, _ in points)+radius+1)
    y0 = max(0, min(py for _, py in points)-radius)
    y1 = min(height, max(py for _, py in points)+radius+1)
    return bytes(grid[y0:y1, x0:x1].tobytes())


def _rotated_extents(local_extents, yaw):
    hx, hy = local_extents
    return (abs(math.cos(yaw))*hx + abs(math.sin(yaw))*hy,
            abs(math.sin(yaw))*hx + abs(math.cos(yaw))*hy)


def _overlaps_known_occupied(grid, x, y, yaw, local_extents, cell_size):
    """AABB/cell overlap using remembered hits and public G1 collision bounds."""
    hx, hy = _rotated_extents(local_extents, yaw)
    obstacle_half = 0.505*cell_size  # documented MuJoCo cell-box geometry
    height, width = grid.shape
    radius_x = (hx+obstacle_half)/cell_size
    radius_y = (hy+obstacle_half)/cell_size
    min_x, max_x = math.ceil(x-radius_x), math.floor(x+radius_x)
    min_y, max_y = math.ceil(y-radius_y), math.floor(y+radius_y)
    for oy in range(max(0, min_y), min(height-1, max_y)+1):
        for ox in range(max(0, min_x), min(width-1, max_x)+1):
            if grid[oy, ox] == 1:
                return True
    return False


def _move_clear(grid, start, target, heading, local_extents, cell_size):
    x0, y0 = start
    x1, y1 = target
    distance = math.hypot(x1-x0, y1-y0)*cell_size
    samples = max(1, math.ceil(distance/(cell_size/10)))
    yaw = HEADINGS[heading]
    return all(not _overlaps_known_occupied(grid,
        x0+(x1-x0)*i/samples, y0+(y1-y0)*i/samples,
        yaw, local_extents, cell_size) for i in range(samples+1))


def _turn_clear(grid, position, heading, target_heading, local_extents, cell_size):
    delta = ((HEADINGS[target_heading]-HEADINGS[heading]+math.pi)%(2*math.pi))-math.pi
    samples = max(1, math.ceil(abs(delta)/0.05))
    return all(not _overlaps_known_occupied(grid, position[0], position[1],
        HEADINGS[heading]+delta*i/samples, local_extents, cell_size)
        for i in range(samples+1))


def plan_g1(grid, start, goal, *, heading=0, unknown='optimistic',
            local_extents=(0.22, 0.33), cell_size=0.75, blocked_actions=frozenset()):
    """Plan moves and in-place turns from memory, public footprint and attempted-action feedback.

    The MuJoCo collision shield is not called here. Occupied cells come only
    from the agent's ternary observations; unknown cells follow the configured
    optimistic/blocked policy. The next selected action alone is checked by
    the shield. Translation is kinematic and may be lateral/backward while
    retaining heading, avoiding forced pivots in tight corridors.
    """
    if unknown not in {'optimistic', 'blocked'}:
        raise ValueError('Unknown handling must be optimistic or blocked')
    if len(local_extents) != 2 or min(local_extents) < 0 or cell_size <= 0:
        raise ValueError('Invalid footprint or grid scale')
    height, width = grid.shape
    start_state = (int(start[0]), int(start[1]), int(heading)%4)
    blocked_actions = set(blocked_actions)
    frontier = [(abs(start[0]-goal[0])+abs(start[1]-goal[1]), 0.0, 0, start_state)]
    costs, parent = {start_state: 0.0}, {}
    serial = 0
    final = None
    while frontier:
        _, cost, _, state = heapq.heappop(frontier)
        if cost != costs.get(state):
            continue
        x, y, face = state
        if (x, y) == tuple(goal):
            final = state
            break
        neighbors = []
        for dx, dy in CARDINALS:
            target = (x+dx, y+dy)
            tx, ty = target
            if not (0 <= tx < width and 0 <= ty < height):
                continue
            if grid[ty, tx] == 1 or (unknown == 'blocked' and grid[ty, tx] == -1):
                continue
            action = ('move', target)
            key = blocked_action_key((x, y), face, action)
            if key in blocked_actions or not _move_clear(grid, (x, y), target,
                    face, local_extents, cell_size):
                continue
            neighbors.append(((tx, ty, face), action, 1.0))
        for turn in ((face+1)%4, (face-1)%4):
            action = ('turn', turn)
            key = blocked_action_key((x, y), face, action)
            if key in blocked_actions or not _turn_clear(grid, (x, y), face,
                    turn, local_extents, cell_size):
                continue
            neighbors.append(((x, y, turn), action, 0.25))
        for next_state, action, step_cost in neighbors:
            new_cost = cost+step_cost
            if new_cost < costs.get(next_state, math.inf):
                costs[next_state] = new_cost
                parent[next_state] = (state, action)
                nx, ny, _ = next_state
                heuristic = abs(nx-goal[0])+abs(ny-goal[1])
                serial += 1
                heapq.heappush(frontier, (new_cost+heuristic, new_cost, serial, next_state))
    if final is None:
        return []
    actions = []
    state = final
    while state != start_state:
        previous, action = parent[state]
        actions.append(action)
        state = previous
    return list(reversed(actions))


def plan_g1_forward_facing(grid, start, goal, *, heading=0, unknown='optimistic',
                           local_extents=(0.22, 0.33), cell_size=0.75,
                           blocked_actions=frozenset()):
    """Observed-map A* allowing only cardinal turns and forward translations.

    The planner never queries hidden simulator state or the MuJoCo action
    shield. Forward translations use the public footprint and observed cells
    for conservative clearance. In-place turns are not prefiltered with the
    footprint AABB: only the selected turn is checked by the evaluator's
    actual-model action shield. A rejected turn is returned as attempted-action
    feedback in ``blocked_actions`` and A* replans without repeating it until
    local observation evidence changes.
    """
    if unknown not in {'optimistic', 'blocked'}:
        raise ValueError('Unknown handling must be optimistic or blocked')
    if len(local_extents) != 2 or min(local_extents) < 0 or cell_size <= 0:
        raise ValueError('Invalid footprint or grid scale')
    height, width = grid.shape
    start_state = (int(start[0]), int(start[1]), int(heading) % 4)
    blocked_actions = set(blocked_actions)
    frontier = [(abs(start[0]-goal[0])+abs(start[1]-goal[1]), 0.0, 0, start_state)]
    costs, parent = {start_state: 0.0}, {}
    serial = 0
    final = None
    while frontier:
        _, cost, _, state = heapq.heappop(frontier)
        if cost != costs.get(state):
            continue
        x, y, face = state
        if (x, y) == tuple(goal):
            final = state
            break
        neighbors = []
        dx, dy = CARDINALS[face]
        target = (x+dx, y+dy)
        tx, ty = target
        if (0 <= tx < width and 0 <= ty < height
                and grid[ty, tx] != 1
                and not (unknown == 'blocked' and grid[ty, tx] == -1)):
            action = ('move', target)
            key = blocked_action_key((x, y), face, action)
            if key not in blocked_actions and _move_clear(
                    grid, (x, y), target, face, local_extents, cell_size):
                neighbors.append(((tx, ty, face), action, 1.0))
        for turn in ((face+1) % 4, (face-1) % 4):
            action = ('turn', turn)
            key = blocked_action_key((x, y), face, action)
            # A rotated footprint AABB can overlap diagonal cell boxes even
            # when the pinned articulated G1 collision geoms clear the turn.
            # Defer this one action to the existing actual-geometry shield;
            # never probe unselected turns or consult hidden occupancy here.
            if key not in blocked_actions:
                neighbors.append(((x, y, turn), action, 0.25))
        for next_state, action, step_cost in neighbors:
            new_cost = cost + step_cost
            if new_cost < costs.get(next_state, math.inf):
                costs[next_state], parent[next_state] = new_cost, (state, action)
                nx, ny, _ = next_state
                heuristic = abs(nx-goal[0]) + abs(ny-goal[1])
                serial += 1
                heapq.heappush(frontier,
                    (new_cost+heuristic, new_cost, serial, next_state))
    if final is None:
        return []
    actions = []
    state = final
    while state != start_state:
        previous, action = parent[state]
        actions.append(action)
        state = previous
    return list(reversed(actions))


def _move_clear_observed_free(grid, start, target, heading, local_extents, cell_size):
    """Require every cell touched by the public swept AABB to be observed free."""
    x0, y0 = start
    x1, y1 = target
    distance = math.hypot(x1-x0, y1-y0)*cell_size
    samples = max(1, math.ceil(distance/(cell_size/10)))
    height, width = grid.shape
    hx, hy = _rotated_extents(local_extents, HEADINGS[int(heading)%4])
    rx, ry = (hx+0.505*cell_size)/cell_size, (hy+0.505*cell_size)/cell_size
    for i in range(samples+1):
        x, y = x0+(x1-x0)*i/samples, y0+(y1-y0)*i/samples
        min_x, max_x = math.ceil(x-rx), math.floor(x+rx)
        min_y, max_y = math.ceil(y-ry), math.floor(y+ry)
        if min_x < 0 or min_y < 0 or max_x >= width or max_y >= height:
            return False
        if any(grid[cy, cx] != 0 for cy in range(min_y, max_y+1)
               for cx in range(min_x, max_x+1)):
            return False
    return True


def _eligible_obstacle_sidestep(grid, position, heading, static_obstacle_cells,
                                local_extents, cell_size, blocked_actions):
    """Offer one side-step only around an observed static object in the front cell."""
    x, y = map(int, position)
    face = int(heading) % 4
    dx, dy = CARDINALS[face]
    ahead = (x+dx, y+dy)
    if (not (0 <= ahead[0] < grid.shape[1] and 0 <= ahead[1] < grid.shape[0])
            or ahead not in static_obstacle_cells or grid[ahead[1], ahead[0]] != 1):
        return None
    for sign in (1, -1):
        side = (-dy*sign, dx*sign)
        target = (x+side[0], y+side[1])
        beyond = (target[0]+dx, target[1]+dy)
        if not (0 <= target[0] < grid.shape[1] and 0 <= target[1] < grid.shape[0]
                and 0 <= beyond[0] < grid.shape[1] and 0 <= beyond[1] < grid.shape[0]):
            continue
        if grid[target[1], target[0]] != 0 or grid[beyond[1], beyond[0]] != 0:
            continue
        action = ('sidestep', target)
        if blocked_action_key(position, face, action) in blocked_actions:
            continue
        if (_move_clear_observed_free(grid, position, target, face,
                local_extents, cell_size)
                and _move_clear_observed_free(grid, target, beyond, face,
                    local_extents, cell_size)):
            return action
    return None


def assess_observed_pedestrian_risk(position, heading, context, *, step,
                                    horizon_steps=2.0, near_cells=1.75,
                                    body_clearance_cells=0.75):
    """Assess only recent observed pedestrian cells and measured motion history."""
    cells = context.get('visible_cells', ())
    if not cells:
        return None
    face = int(heading) % 4
    fx, fy = CARDINALS[face]
    close = []
    for px, py in cells:
        rx, ry = float(px)-position[0], float(py)-position[1]
        along, lateral = rx*fx+ry*fy, -rx*fy+ry*fx
        if 0 < along <= near_cells and abs(lateral) <= body_clearance_cells:
            close.append((along, lateral))
    if not close:
        return None
    history = context.get('history', ())
    if (not context.get('reliable', False) or len(history) < 2
            or step-context.get('last_step', step) > context.get('max_age_steps', 8)):
        return 'dynamic_motion_uncertain'
    (old_step, old_x, old_y), (new_step, new_x, new_y) = history[-2:]
    elapsed = new_step-old_step
    if elapsed <= 0:
        return 'dynamic_motion_uncertain'
    vx, vy = (new_x-old_x)/elapsed, (new_y-old_y)/elapsed
    closing_speed = -(vx*fx+vy*fy)
    if closing_speed <= 0.05:
        return None
    along, lateral = min(close, key=lambda value: value[0])
    projected_along = along - closing_speed*horizon_steps
    if projected_along <= body_clearance_cells and abs(lateral) <= body_clearance_cells:
        return 'observed_oncoming_pedestrian_imminent'
    return None


def plan_g1_default_policy(grid, start, goal, *, heading=0, unknown='optimistic',
                           local_extents=(0.22, 0.33), cell_size=0.75,
                           blocked_actions=frozenset(), static_obstacle_cells=frozenset(),
                           pedestrian_context=None, step=0):
    """Forward-first plan with explicitly eligible side/back safety actions."""
    face = int(heading) % 4
    blocked_actions = set(blocked_actions)
    risk = assess_observed_pedestrian_risk(start, face, pedestrian_context or {}, step=step)
    if risk:
        if risk == 'dynamic_motion_uncertain':
            return [('wait', 'dynamic_threat_uncertain_no_safe_retreat')]
        dx, dy = CARDINALS[face]
        retreat_target = (start[0]-dx, start[1]-dy)
        retreat = ('retreat', retreat_target)
        retreat_key = blocked_action_key(start, face, retreat)
        if (retreat_key not in blocked_actions
                and _move_clear_observed_free(grid, start, retreat_target, face,
                    local_extents, cell_size)):
            return [retreat]
        return [('wait', 'imminent_dynamic_threat_retreat_not_observed_clear')]
    sidestep = _eligible_obstacle_sidestep(grid, start, face,
        set(static_obstacle_cells), local_extents, cell_size, blocked_actions)
    if sidestep is not None:
        return [sidestep]
    return plan_g1_forward_facing(grid, start, goal, heading=face,
        unknown=unknown, local_extents=local_extents, cell_size=cell_size,
        blocked_actions=blocked_actions)
