import numpy as np


class Memory:
    """Unknown=-1, free=0, occupied=1; observations carry no persistence labels."""
    def __init__(self, shape):
        self.grid = np.full(shape, -1, dtype=np.int8)

    def update(self, observation):
        if observation.shape != self.grid.shape or not np.isin(observation, [-1, 0, 1]).all():
            raise ValueError('Invalid observation')
        visible = observation >= 0
        self.grid[visible] = observation[visible]


class Baseline:
    def __init__(self, shape, initial_observation, method, interval):
        if method not in {'static', 'periodic'} or interval < 1:
            raise ValueError('Invalid baseline or interval')
        self.memory = Memory(shape)
        self.memory.update(initial_observation)
        self.method, self.interval = method, interval

    def needs_observation(self, step):
        return self.method == 'periodic' and step > 0 and step % self.interval == 0

    def refresh(self, observation):
        if self.method != 'periodic':
            raise ValueError('Static memory is frozen')
        self.memory.update(observation)
