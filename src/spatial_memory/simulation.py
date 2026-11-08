"""Hidden simulator state. Only the experiment harness owns World."""
from dataclasses import dataclass
import numpy as np

Cell = tuple[int, int]  # x, y


@dataclass(frozen=True)
class Scenario:
    name: str
    split: str
    width: int
    height: int
    start: Cell
    goal: Cell
    walls: tuple[Cell, ...]
    obstacles: tuple[Cell, ...]
    pedestrians: tuple[tuple[Cell, ...], ...]
    changes: tuple[dict, ...]

    @classmethod
    def from_dict(cls, data):
        obj = cls(
            data['name'], data['split'], data['width'], data['height'],
            tuple(data['start']), tuple(data['goal']),
            tuple(map(tuple, data.get('walls', []))),
            tuple(map(tuple, data.get('obstacles', []))),
            tuple(tuple(map(tuple, path)) for path in data.get('pedestrians', [])),
            tuple(data.get('changes', [])),
        )
        if obj.width < 3 or obj.height < 3 or obj.split not in {'development', 'held_out'}:
            raise ValueError('Invalid dimensions or split')
        cells = [obj.start, obj.goal, *obj.walls, *obj.obstacles]
        for path in obj.pedestrians:
            if not path:
                raise ValueError('Pedestrian paths must be nonempty')
            for a, b in zip(path, path[1:] + path[:1]):
                if abs(a[0]-b[0]) + abs(a[1]-b[1]) > 1:
                    raise ValueError('Pedestrians must wait or move one cardinal cell')
            cells.extend(path)
        for event in obj.changes:
            if event['step'] < 1 or event['action'] not in {'add', 'remove', 'relocate'}:
                raise ValueError('Invalid change')
            cells.append(tuple(event['cell']))
            if event['action'] == 'relocate':
                cells.append(tuple(event['to']))
        if any(not (0 <= x < obj.width and 0 <= y < obj.height) for x, y in cells):
            raise ValueError('Cell outside world')
        if any(c in obj.walls for c in [obj.start, obj.goal, *obj.obstacles]):
            raise ValueError('Start, goal and objects must be outside walls')
        dynamic_cells = [c for p in obj.pedestrians for c in p]
        dynamic_cells += [tuple(e['cell']) for e in obj.changes]
        dynamic_cells += [tuple(e['to']) for e in obj.changes if 'to' in e]
        if any(c in obj.walls for c in dynamic_cells):
            raise ValueError('Dynamic occupancy cannot overwrite walls')
        if obj.start in obj.obstacles or any(p[0] == obj.start for p in obj.pedestrians):
            raise ValueError('Robot must start free')
        return obj


class World:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.step = 0
        self.objects = set(scenario.obstacles)
        self.initial_geometry = self.geometry().copy()

    def geometry(self):
        grid = np.zeros((self.scenario.height, self.scenario.width), dtype=bool)
        for x, y in (*self.scenario.walls, *self.objects):
            grid[y, x] = True
        return grid

    def people(self):
        return {p[self.step % len(p)] for p in self.scenario.pedestrians}

    def occupancy(self):
        grid = self.geometry()
        for x, y in self.people():
            grid[y, x] = True
        return grid

    def advance(self):
        self.step += 1
        for event in self.scenario.changes:
            if event['step'] != self.step:
                continue
            cell = tuple(event['cell'])
            if event['action'] in {'remove', 'relocate'}:
                self.objects.discard(cell)
            if event['action'] == 'add':
                self.objects.add(cell)
            elif event['action'] == 'relocate':
                self.objects.add(tuple(event['to']))

    def move(self, position: Cell, target: Cell):
        if abs(position[0]-target[0]) + abs(position[1]-target[1]) != 1:
            raise ValueError('Movement must be one cardinal cell')
        x, y = target
        blocked = not (0 <= x < self.scenario.width and 0 <= y < self.scenario.height)
        blocked = blocked or bool(self.occupancy()[y, x])
        return (position if blocked else target), int(blocked)


def scenario_from_bprime(payload, schedule_index=0):
    """Adapt a saved, admitted R/BP/M world to the existing navigation simulator.

    Caller must supply an independently validated candidate record. This adapter
    never invokes geometry generation or changes the saved experiment evidence.
    """
    from .phase15_bprime import ACTIVE_MECHANISMS
    if (not isinstance(payload, dict) or payload.get('mechanism') not in ACTIVE_MECHANISMS
            or payload.get('outcome') != 'independent' or payload.get('partition') != 'fit'):
        raise ValueError('An admitted R/BP/M fit world is required')
    if type(schedule_index) is not int or schedule_index not in (0, 1):
        raise ValueError('Schedule index must be 0 or 1')
    geometry = payload['geometry']
    world = payload['world']
    width, height = geometry['width'], geometry['height']
    free = {tuple(cell) for cell in geometry['free']}
    if not free or any(not (0 <= x < width and 0 <= y < height) for x, y in free):
        raise ValueError('Invalid saved free-space raster')
    schedule = world['schedules'][schedule_index]
    walls = tuple((x, y) for y in range(height) for x in range(width) if (x, y) not in free)
    initial = tuple(map(tuple, schedule['initial']))
    events = tuple(dict(step=e['step'], action=e['action'], cell=tuple(e['cell']),
                        **({'to': tuple(e['to'])} if 'to' in e else {}))
                   for e in schedule['events'])
    positions = tuple(map(tuple, schedule['positions']))
    data = dict(
        name=f"{payload['identity']}:schedule-{schedule_index}",
        split='development',
        width=width, height=height,
        start=world['start'], goal=world['goal'],
        walls=walls, obstacles=initial,
        pedestrians=(positions,) if positions else (),
        changes=events,
    )
    return Scenario.from_dict(data)
