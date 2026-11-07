"""Instrumented calls to unchanged A*: accepts remembered maps only."""
from time import perf_counter
from .navigation import plan


class PlanningMeter:
    def __init__(self):
        self.calls = 0
        self.seconds = 0.0
        self.durations = []

    def __call__(self, grid, start, goal, unknown='optimistic'):
        begin = perf_counter()
        try:
            return plan(grid, start, goal, unknown)
        finally:
            self.calls += 1
            duration = perf_counter() - begin
            self.seconds += duration
            self.durations.append(duration)

    def snapshot(self):
        return self.calls, self.seconds
