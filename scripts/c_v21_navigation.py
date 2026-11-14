"""Scoped C v2.1 integration through the frozen G1 observation factory."""
from __future__ import annotations
import sys
from c_v21_common import ROOT
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import evaluate_c_v2_candidate_coverage_fit72 as fit
import evaluate_persistence_evi_fit72 as runner
from spatial_memory.multistep_evi import ARMS,MultiStepParameters


def run_case(payload,schedule,arm,config):
    if arm not in ARMS:raise ValueError('Unknown multi-step arm')
    original=runner.PersistenceEVIController
    selector='topology' if 'topology' in arm else 'k'
    class MultiStepController(original):
        def __init__(self,*a,**kw):
            if kw.get('persistence'):raise RuntimeError('No B changes permitted')
            kw['evi_function']=ARMS[arm]
            kw['evi_parameters']=MultiStepParameters(3 if selector=='topology' else 5)
            super().__init__(*a,**kw)
    runner.PersistenceEVIController=MultiStepController
    try:row,trace,diag=fit.run_measured(payload,schedule,'c_topology3d' if selector=='topology' else 'c_k',config)
    finally:runner.PersistenceEVIController=original
    diag['multistep_arm']=arm
    row['multistep_arm']=arm
    return row,trace,diag
