"""Gate-guarded C v2.0c FIT72 descriptive runner.

This wrapper supplies the v2.0c protocol and arm matrix to the shared
read-only evaluator. It will refuse until the synthetic result and its
separate conformance review both pass.
"""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_c_v2_candidate_coverage_fit72 as shared


def main():
    defaults=['--gate','results/phase2_mujoco/c_v2c_topology_v2/synthetic_mechanism_results.json',
        '--protocol','docs/phase2_c_v2c_topology_protocol_v2.md',
        '--output','results/phase2_mujoco/c_v2c_topology_v2/fit72_descriptive_screen',
        '--arms','c0_audit','c_k','c_topology3c']
    sys.argv=[sys.argv[0],*defaults,*sys.argv[1:]]
    shared.main()


if __name__=='__main__':main()
