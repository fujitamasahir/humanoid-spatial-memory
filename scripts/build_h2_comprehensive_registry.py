"""Build the hash-bound, human-reviewed H2 comprehensive model registry."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/phase2_mujoco/h2_comprehensive_benchmark_v1/protocol'

# id, display name, family, source module, implementation, historical runner,
# fixed arm/mode, fixed parameter note, authorization status
SPECS = [
('periodic4','Periodic-4','Periodic','src/spatial_memory/scheduling.py','ObservationController','scripts/h2_final_common.py','periodic4','interval=4; cap=20','historical'),
('periodic5','Periodic-5','Periodic','src/spatial_memory/cadence_age.py','CadenceController','scripts/run_age_cadence_fit72.py','periodic5','original saved cadence parameters','historical'),
('age4','Age-4','Age','src/spatial_memory/scheduling.py','ObservationController','scripts/h2_final_common.py','age4','AdaptiveParameters defaults from frozen H2 config','historical'),
('age5','Age-5','Age','src/spatial_memory/cadence_age.py','CadenceController','scripts/run_age_cadence_fit72.py','age5','original saved cadence parameters','historical'),
('age6','Age-6','Age','src/spatial_memory/scheduling.py','ObservationController','scripts/h2_final_common.py','age6','age_steps=6; remaining frozen H2 age parameters','historical'),
('age_route_rescue','Age-Route-Rescue','Age-based','src/spatial_memory/route_age.py','RouteAgeController','scripts/h2_final_common.py','age_route_rescue','frozen source defaults','historical'),
('age_route_clock','Age-Route-Clock','Age-based','src/spatial_memory/route_age.py','RouteAgeController','scripts/h2_final_common.py','age_route_clock','frozen source defaults','historical'),
('rdao_v2','RDAO v2','RDAO','src/spatial_memory/rdao_v2.py','RDAOv2ViewpointController','scripts/h2_final_common.py','rdao_v2','source defaults; 61-ray memory sensor','historical'),
('rdao_v21','RDAO v2.1','RDAO','src/spatial_memory/rdao_v21_quality.py','RDAOv21CurrentQualityController','scripts/h2_final_common.py','rdao_v21','source defaults; 61-ray memory sensor','historical'),
('caa_fast','CAA-Fast','CAA','src/spatial_memory/change_aware_age.py','ChangeAwareAgeController','scripts/h2_final_common.py','caa_fast','frozen source defaults','historical'),
('caa_full','CAA-Full','CAA','src/spatial_memory/change_aware_age.py','ChangeAwareAgeController','scripts/h2_final_common.py','caa_full','frozen source defaults','historical'),
('raa_defer','RAA-Defer','RAA','src/spatial_memory/route_adaptive_age_v1.py','RouteAdaptiveAgeV1','scripts/h2_final_common.py','raa_defer','frozen source defaults','historical'),
('uncertainty','Uncertainty','Uncertainty','src/spatial_memory/scheduling.py','ObservationController','scripts/h2_high_frequency_dynamics.py','uncertainty','frozen H2 uncertainty configuration','historical'),
('static','Static','Baseline','src/spatial_memory/scheduling.py','ObservationController','scripts/h2_final_common.py','static','initial observation only; cap=20; emergency safety retained','eligible'),
('age_gap4','Age-Gap4','Age','src/spatial_memory/cadence_age.py','CadenceController','scripts/run_age_cadence_fit72.py','age_gap4','frozen Age-4 parameters; minimum scan gap=4','eligible'),
('age_motion','Age-Motion','Age','src/spatial_memory/cadence_age.py','CadenceController','scripts/run_age_cadence_fit72.py','age_motion','frozen Age-4 parameters; motion/viewpoint deferral and deadline','eligible'),
('age_view_veto','Age-View-Veto','Age','src/spatial_memory/view_age.py','ViewAgeController','scripts/run_age_view_fit72.py','age_view_veto','frozen Age parameters; visible stale fraction veto','eligible'),
('age_view_clock','Age-View-Clock','Age','src/spatial_memory/view_age.py','ViewAgeController','scripts/run_age_view_fit72.py','age_view_clock','frozen Age parameters; visible-view clock','eligible'),
('periodic_event','Periodic+Event','Event-triggered','src/spatial_memory/event_observation.py','EventTriggeredObservationController','scripts/evaluate_event_observation_fit72.py','periodic','cooldowns: 2 steps since any scan, 3 since event scan','eligible'),
('age_event','Age+Event','Event-triggered','src/spatial_memory/event_observation.py','EventTriggeredObservationController','scripts/evaluate_event_observation_fit72.py','age','cooldowns: 2 steps since any scan, 3 since event scan','eligible'),
('rdao_v1','RDAO v1','RDAO','src/spatial_memory/rdao.py','RDAOController','scripts/evaluate_rdao_phase2.py','rdao_v1','RDAOParameters source defaults; 61-ray sensor','eligible'),
('rdao_v1_footprint','RDAO v1 Footprint','RDAO','src/spatial_memory/rdao.py','RDAOController + footprint visibility patch','scripts/evaluate_rdao_footprint_visibility_online.py','rdao_v1_footprint','original footprint predictor and source defaults','eligible'),
('rdao_v1_gate_first','RDAO v1 Gate First','RDAO','src/spatial_memory/rdao.py','CandidateOnlineGateRDAO + online_gate_decision','scripts/evaluate_rdao_online_safe_gate_screen.py','first','existing online gate; one override maximum','eligible'),
('rdao_v1_gate_every','RDAO v1 Gate Every','RDAO','src/spatial_memory/rdao.py','CandidateOnlineGateRDAO + online_gate_decision','scripts/evaluate_rdao_online_safe_gate_screen.py','every','existing online gate; no step allowlist','eligible'),
('rdao_v22','RDAO v2.2','RDAO','src/spatial_memory/rdao_v22_decision_protected.py','RDAOv22DecisionProtectedController','scripts/evaluate_rdao_v22_decision_protected.py','rdao_v22','frozen v2.2 parameters','eligible'),
('b_age','B + Age','Persistence/EVI','src/spatial_memory/evi.py','PersistenceEVIController','scripts/evaluate_persistence_evi_fit72.py','b_age','PersistenceParameters defaults; Age scheduler','eligible'),
('c_ternary','C + Ternary','Persistence/EVI','src/spatial_memory/evi.py','PersistenceEVIController','scripts/evaluate_persistence_evi_fit72.py','c_ternary','EVIParameters defaults; ternary memory','eligible'),
('bc','B+C','Persistence/EVI','src/spatial_memory/evi.py','PersistenceEVIController','scripts/evaluate_persistence_evi_fit72.py','bc','PersistenceParameters and EVIParameters defaults','eligible'),
('c0_audit','C0','Candidate coverage','src/spatial_memory/candidate_coverage.py','information_value_original_audit','scripts/evaluate_c_v2_candidate_coverage_fit72.py','c0_audit','source defaults; C-v2d authorization scope','eligible'),
('c_k','C-K','Candidate coverage','src/spatial_memory/candidate_coverage.py','information_value_uncertainty_k','scripts/evaluate_c_v2_candidate_coverage_fit72.py','c_k','K=5; C-v2d authorization scope','eligible'),
('c_route3','C-Route3','Candidate coverage','src/spatial_memory/candidate_coverage.py','information_value_route','scripts/evaluate_c_v2_candidate_coverage_fit72.py','c_route3','K=3 route-ranked; shared mechanism gate rejected','blocked: no FIT authorization'),
('c_routek','C-RouteK','Candidate coverage','src/spatial_memory/candidate_coverage.py','information_value_route','scripts/evaluate_c_v2_candidate_coverage_fit72.py','c_routek','K=5 route-ranked; shared mechanism gate rejected','blocked: no FIT authorization'),
('c_topology3c','C-Topology3-c','Topology EVI','src/spatial_memory/topology_evi_c.py','information_value_topology_c','scripts/evaluate_c_v2c_topology_fit72.py','c_topology3c','K=3; c-v2c review INVALID_STOP_BEFORE_FIT','blocked: invalid gate'),
('c_topology3d','C-Topology3-d','Topology EVI','src/spatial_memory/topology_evi_d.py','information_value_topology_d','scripts/evaluate_c_v2d_topology_fit72.py','c_topology3d','K=3; C-v2d accepted gate','eligible'),
('ms_k','MS-K','Multi-step EVI','src/spatial_memory/multistep_evi.py','information_value_multistep','scripts/evaluate_c_v21_fit72.py','ms_k','H=3, K=5; frozen source defaults','eligible'),
('ms_k_visibility','MS-K-Visibility','Multi-step EVI','src/spatial_memory/multistep_evi.py','information_value_multistep','scripts/evaluate_c_v21_fit72.py','ms_k_visibility','H=3, K=5; visibility selector','eligible'),
('ms_topology','MS-Topology','Multi-step EVI','src/spatial_memory/multistep_evi.py','information_value_multistep','scripts/evaluate_c_v21_fit72.py','ms_topology','H=3, topology selector; frozen source defaults','eligible'),
('ms_topology_visibility','MS-Topology-Visibility','Multi-step EVI','src/spatial_memory/multistep_evi.py','information_value_multistep','scripts/evaluate_c_v21_fit72.py','ms_topology_visibility','H=3, topology visibility selector','eligible'),
('h1_k','H1-K','Multi-step depth','src/spatial_memory/multistep_depth_ablation.py','information_value_multistep','scripts/run_c_v21a_depth_ablation.py','h1_k','H=1, K=5; frozen depth-control parameters','eligible'),
('h3_k','H3-K','Multi-step depth','src/spatial_memory/multistep_depth_ablation.py','information_value_multistep','scripts/run_c_v21a_depth_ablation.py','h3_k','H=3, K=5; frozen depth-control parameters','eligible'),
('h1_topology','H1-Topology','Multi-step depth','src/spatial_memory/multistep_depth_ablation.py','information_value_multistep','scripts/run_c_v21a_depth_ablation.py','h1_topology','H=1, topology selector; frozen depth-control parameters','eligible'),
('h3_topology','H3-Topology','Multi-step depth','src/spatial_memory/multistep_depth_ablation.py','information_value_multistep','scripts/run_c_v21a_depth_ablation.py','h3_topology','H=3, topology selector; frozen depth-control parameters','eligible'),
('caa_slow','CAA-Slow','CAA','src/spatial_memory/change_aware_age.py','ChangeAwareAgeController','scripts/run_age_cadence_fit72.py','caa_slow','frozen source defaults','eligible'),
('dao_veto','DAO-Veto','DAO','src/spatial_memory/dao_navigation_compat_v1_1.py','DAONavigationCompatV1_1','scripts/run_dao_integration_v1_1.py','dao_veto','DAOParameters defaults; age radius=3','eligible'),
('dao_trigger','DAO-Trigger','DAO','src/spatial_memory/dao_navigation_compat_v1_1.py','DAONavigationCompatV1_1','scripts/run_dao_integration_v1_1.py','dao_trigger','DAOParameters defaults; age radius=3','eligible'),
('dao_route','DAO-Route','DAO','src/spatial_memory/dao_navigation_compat_v1_1.py','DAONavigationCompatV1_1','scripts/run_dao_integration_v1_1.py','dao_route','DAOParameters defaults; public route mode','eligible'),
('dao_combined','DAO-Combined','DAO','src/spatial_memory/dao_navigation_compat_v1_1.py','DAONavigationCompatV1_1','scripts/run_dao_integration_v1_1.py','dao_combined','DAOParameters defaults; combined mode','eligible'),
('dao_veto_q50','DAO-Veto-Q50','DAO','src/spatial_memory/attenuated_dao_veto_v1.py','AttenuatedDAOVeto','scripts/run_attenuated_dao_veto_v1.py','dao_veto_q50','discovery factor=0.5','eligible'),
('dao_veto_q80','DAO-Veto-Q80','DAO','src/spatial_memory/attenuated_dao_veto_v1.py','AttenuatedDAOVeto','scripts/run_attenuated_dao_veto_v1.py','dao_veto_q80','discovery factor=0.8','eligible'),
('dao_veto_optimistic','DAO-Veto-Optimistic','DAO','src/spatial_memory/attenuated_dao_veto_v1.py','AttenuatedDAOVeto','scripts/run_attenuated_dao_veto_v1.py','dao_veto_optimistic','discovery factor=1.0','eligible'),
('dao_veto_route_gate','DAO-Route-Gate','DAO','src/spatial_memory/route_gated_dao_veto_v1.py','RouteGatedDAOVeto','scripts/run_route_gated_dao_veto_v1.py','dao_veto_route_gate','gate_mode=route','eligible'),
('dao_veto_deadline','DAO-Deadline','DAO','src/spatial_memory/route_gated_dao_veto_v1.py','RouteGatedDAOVeto','scripts/run_history_gated_deadline_fit72_v1.py','dao_veto_deadline','gate_mode=deadline','eligible'),
('dao_veto_joint','DAO-Joint','DAO','src/spatial_memory/route_gated_dao_veto_v1.py','RouteGatedDAOVeto','scripts/run_history_gated_deadline_fit72_v1.py','dao_veto_joint','gate_mode=joint','eligible'),
('deadline_stable','DAO-Deadline-Stable','DAO','src/spatial_memory/history_gated_deadline_v1.py','HistoryGatedDeadline','scripts/run_history_gated_deadline_fit72_v1.py','deadline_stable','history_mode=stable_prefix_later','eligible'),
('deadline_stable_quiet','DAO-Deadline-Stable-Quiet','DAO','src/spatial_memory/history_gated_deadline_v1.py','HistoryGatedDeadline','scripts/run_history_gated_deadline_fit72_v1.py','deadline_stable_quiet','history_mode=stable_prefix_later_previous_no_change','eligible'),
('raa_advance','RAA-Advance','RAA','src/spatial_memory/route_adaptive_age_v1.py','RouteAdaptiveAgeV1','scripts/run_route_adaptive_age_v1.py','raa_advance','frozen RAA v1 parameters','eligible'),
('raa_joint','RAA-Joint','RAA','src/spatial_memory/route_adaptive_age_v1.py','RouteAdaptiveAgeV1','scripts/run_route_adaptive_age_v1.py','raa_joint','frozen RAA v1 parameters','eligible'),
]

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    if len(SPECS) != 57 or sum(x[-1] == 'historical' for x in SPECS) != 13:
        raise RuntimeError('Registry cardinality mismatch')
    rows = []
    for ident, name, family, source, impl, runner, arm, params, auth in SPECS:
        p = ROOT / source
        if not p.is_file():
            raise FileNotFoundError(p)
        commit = subprocess.run(['git','log','-1','--format=%H','--',source],cwd=ROOT,
                                check=True,text=True,capture_output=True).stdout.strip()
        rows.append({
            'model_id':ident, 'display_name':name, 'family':family,
            'source_file':source, 'implementation':impl,
            'historical_evaluation_script':runner,
            'source_commit':commit, 'source_sha256':_sha(p),
            'fixed_arm_or_mode':arm, 'fixed_parameters':params,
            'observation_decision':f'{impl}; see exact mode and source commitment',
            'memory_representation':'Original spatial memory API; model-specific state is disclosed by source',
            'additional_action_selection_logic':'Only for source models whose frozen policy includes it; common selected-action shield and emergency safety retained',
            'previously_evaluated':auth == 'historical',
            'authorization_status':auth,
        })
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'model_registry.json').write_text(json.dumps(rows,indent=2,sort_keys=True)+'\n')
    fields=list(rows[0])
    with (OUT/'model_registry.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print(f'Wrote {len(rows)} rows: {sum(x["authorization_status"] == "eligible" for x in rows)} eligible, '
          f'{sum(x["authorization_status"].startswith("blocked") for x in rows)} blocked')

if __name__ == '__main__':
    build()
