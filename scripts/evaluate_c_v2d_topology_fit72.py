"""Gate-guarded descriptive FIT72 comparison for C v2.0d."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_c_v2_candidate_coverage_fit72 as shared


def main():
    defaults=['--gate','results/phase2_mujoco/c_v2d_topology_v1/synthetic_mechanism_results.json',
      '--protocol','docs/phase2_c_v2d_fit_intervention_protocol.md',
      '--output','results/phase2_mujoco/c_v2d_topology_v1/fit72_descriptive_screen',
      '--arms','c0_audit','c_k','c_topology3d']
    sys.argv=[sys.argv[0],*defaults,*sys.argv[1:]]
    shared.main()


if __name__=='__main__':main()
