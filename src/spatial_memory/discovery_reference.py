"""Independent scalar sampled-geometry certificate for DAO engineering tests.

No imports from the DAO implementation; input is a public ternary raster.
Not an independent model of the real 3D sensor.
"""
import math


def footprint_reference(grid, position, yaw, range_m=6., cell_size=.75,
                        horizontal_fov_deg=120., ray_count=61):
    height, width = len(grid), len(grid[0]); endpoints = [set(), set()]
    count = math.ceil(range_m/cell_size/.1)+1
    for j in range(ray_count):
        angle = yaw+math.radians(-horizontal_fov_deg/2+j*(horizontal_fov_deg/(ray_count-1)))
        path = []
        for k in range(count):
            distance = k*((range_m/cell_size)/(count-1))
            c = (math.floor(position[0]+distance*math.cos(angle)+.5),
                 math.floor(position[1]+distance*math.sin(angle)+.5))
            if not (0 <= c[0] < width and 0 <= c[1] < height):
                break
            if c != position and (not path or path[-1] != c):
                path.append(c)
            if grid[c[1]][c[0]] == 1:
                break
        endpoints[0].update(path)
        for c in path:
            endpoints[1].add(c)
            if grid[c[1]][c[0]] == -1:
                break
    return {'optimistic': endpoints[0], 'frontier': endpoints[1]}


def scalar_counts(grid, timestamps, step, cells, route=()):
    result = {'visible': len(cells), 'new': 0, 'stale': 0, 'known': 0, 'route_new': 0}
    for x, y in cells:
        value = grid[y][x]
        if value == -1:
            result['new'] += 1
            if any(abs(x-a)+abs(y-b) <= 1 for a, b in route[1:6]):
                result['route_new'] += 1
        else:
            result['known'] += 1
            result['stale'] += int(step-timestamps[y][x] >= 5)
    result['stale_fraction'] = result['stale']/result['known'] if result['known'] else 0.
    return result
