import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),
             str(Path(__file__).resolve().parents[1]/'src')]
import numpy as np

from h2_comprehensive_adapters import ADDITIONAL, _factory
import h2_final_common as frozen
from spatial_memory.scheduling import AdaptiveParameters

def test_every_eligible_arm_constructs_with_the_frozen_controller_api():
    cfg=frozen.config()
    grid=np.zeros((25,25),dtype=np.int8)
    grid[0,:]=grid[-1,:]=1;grid[:,0]=grid[:,-1]=1
    state={'goal':(23,23),'controller':None,'overrides':0,'events':[]}
    options={'interval':4,'radius':3,'parameters':AdaptiveParameters(),
             'max_observations':20}
    for arm in ADDITIONAL:
        controller=_factory(arm,cfg,state)(grid,'age',**options)
        assert controller.memory.grid.shape==(25,25),arm
        assert controller.used==1 and controller.cap==20,arm
        assert callable(controller.decide) and callable(controller.refresh),arm
