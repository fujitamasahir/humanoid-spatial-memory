"""Headless figures: hidden truth beside the map available to planning."""
import os
import tempfile

# Keep headless font caches in a writable temporary directory on both platforms.
_cache = tempfile.TemporaryDirectory(prefix='spatial-memory-mpl-')
os.environ.setdefault('MPLCONFIGDIR', _cache.name)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


def save_figure(scenario, frame, output):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    truth = np.zeros(frame['geometry'].shape, dtype=int)
    for x, y in scenario.walls:
        truth[y, x] = 1
    truth[frame['geometry'] & (truth == 0)] = 2
    truth[frame['people']] = 3
    axes[0].imshow(truth, cmap=ListedColormap(['white', '#333333', '#e99a24', '#ba55d3']),
                   vmin=0, vmax=3, origin='lower')
    axes[1].imshow(frame['memory'], cmap=ListedColormap(['#aaaaaa', 'white', '#333333']),
                   vmin=-1, vmax=1, origin='lower')
    for ax in axes:
        if frame['planned']:
            xs, ys = zip(*frame['planned'])
            ax.plot(xs, ys, '--', color='#148f77', label='planned before move')
        xs, ys = zip(*frame['executed'])
        ax.plot(xs, ys, color='#2471a3', label='executed')
        ax.scatter(*frame['position'], color='red', label='robot', zorder=5)
        ax.scatter(*scenario.goal, marker='*', s=120, color='green', label='goal', zorder=5)
        ax.set_xticks(range(scenario.width))
        ax.set_yticks(range(scenario.height))
        ax.set_xlabel('x')
        ax.set_ylabel('y')
    axes[0].set_title('Hidden truth\nWalls gray, objects orange, people purple', fontsize=10)
    axes[1].set_title('Robot memory\nUnknown gray, free white, occupied dark', fontsize=10)
    axes[1].legend(fontsize=7, loc='upper left')
    fig.suptitle(f'{scenario.name}, step {frame["step"]}')
    fig.savefig(output, dpi=120)
    plt.close(fig)
