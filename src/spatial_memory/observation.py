"""Sensor boundary: unlabeled ternary occupancy, never semantic identities."""
from dataclasses import dataclass
import numpy as np


def line_cells(a, b):
    """Conservative supercover line; blocks diagonal corner peeking."""
    x, y = a
    dx, dy = b[0]-x, b[1]-y
    nx, ny = abs(dx), abs(dy)
    sx, sy = int(np.sign(dx)), int(np.sign(dy))
    ix = iy = 0
    cells = [(x, y)]
    while ix < nx or iy < ny:
        lhs, rhs = (1+2*ix)*ny, (1+2*iy)*nx
        if lhs == rhs:
            cells.extend([(x+sx, y), (x, y+sy)])
            x, y, ix, iy = x+sx, y+sy, ix+1, iy+1
        elif lhs < rhs:
            x, ix = x+sx, ix+1
        else:
            y, iy = y+sy, iy+1
        cells.append((x, y))
    return cells


@dataclass(frozen=True)
class Sensor:
    radius: int = 3
    occlusion: bool = True
    noise: float = 0.0

    def __post_init__(self):
        if self.radius < 0 or not 0 <= self.noise <= 1:
            raise ValueError('Invalid sensor parameters')

    def observe(self, occupancy, position, rng):
        result = np.full(occupancy.shape, -1, dtype=np.int8)
        px, py = position
        for y in range(occupancy.shape[0]):
            for x in range(occupancy.shape[1]):
                if (x-px)**2 + (y-py)**2 > self.radius**2:
                    continue
                if self.occlusion and any(occupancy[cy, cx]
                    for cx, cy in line_cells(position, (x, y))[1:-1]):
                    continue
                value = bool(occupancy[y, x])
                result[y, x] = int(value ^ (rng.random() < self.noise))
        result.setflags(write=False)
        return result
