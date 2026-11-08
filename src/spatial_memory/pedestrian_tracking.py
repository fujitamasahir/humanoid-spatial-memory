"""Conservative tracking from pedestrian cells actually returned by 3D rays."""


def _clusters(cells):
    remaining = {tuple(map(int, cell)) for cell in cells}
    result = []
    while remaining:
        cluster = {remaining.pop()}
        frontier = list(cluster)
        while frontier:
            x, y = frontier.pop()
            neighbors = {cell for cell in remaining
                         if max(abs(cell[0]-x), abs(cell[1]-y)) <= 1}
            remaining.difference_update(neighbors)
            cluster.update(neighbors)
            frontier.extend(neighbors)
        result.append((sum(x for x, _ in cluster)/len(cluster),
                       sum(y for _, y in cluster)/len(cluster)))
    return tuple(sorted(result))


class ObservedPedestrianTracker:
    """Two-observation motion estimate; never reads simulator trajectories."""

    def __init__(self, *, max_age_steps=8):
        self.max_age_steps = int(max_age_steps)
        self.samples = []
        self.visible_cells = ()
        self.last_step = None

    def observe(self, step, visible_cells):
        centers = _clusters(visible_cells)
        unique = centers[0] if len(centers) == 1 else None
        self.samples.append((int(step), unique))
        self.samples = self.samples[-2:]
        self.visible_cells = centers
        self.last_step = int(step)

    def context(self):
        history = []
        if len(self.samples) == 2 and all(sample[1] is not None for sample in self.samples):
            history = [(step, *center) for step, center in self.samples]
        delta = self.samples[-1][0]-self.samples[-2][0] if len(self.samples) == 2 else 0
        reliable = (len(history) == 2 and 0 < delta <= self.max_age_steps)
        return {
            'visible_cells': self.visible_cells,
            'history': history,
            'reliable': reliable,
            'last_step': self.last_step if self.last_step is not None else 0,
            'max_age_steps': self.max_age_steps,
        }
