"""A* accepts remembered occupancy only. Unknown handling is shared."""
import heapq


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
