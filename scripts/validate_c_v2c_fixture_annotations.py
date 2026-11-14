"""Pre-policy structural/visibility validator for frozen v2.0c fixtures."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v2c_fixtures import build_formal_fixtures
from spatial_memory.evi import visible_cells
from spatial_memory.navigation import plan
from spatial_memory.topology_reference import brute_force_topology_reference

SENSOR={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}


def _label(f,ref,route):
    cell=tuple(f['target_cell']);start=f['start'];goal=f['goal']
    if cell in ref['vertices']:
        if cell in (start,goal):return 'traversable_terminal'
        if cell in ref['start_goal_separating']:return 'start_goal_separating_articulation'
        if any(cell in e for e in ref['terminal_relevant_bridges']):return 'terminal_relevant_bridge_endpoint'
        if cell in ref['articulation'] and cell in set(route):return 'other_route_articulation'
        if cell in ref['cycle_vertices'] and cell in set(route):return 'route_cell_with_alternative_cycle'
        if cell in ref['articulation']:return 'irrelevant_articulation'
        return 'other_traversable'
    return ref['nontraversable_shortcuts'][cell]['kind']


def validate_annotations():
    fixtures=build_formal_fixtures();errors=[];observed=[];pairs={}
    for f in fixtures:
        grid=f['grid'];mode=f['unknown'];start=f['start'];goal=f['goal'];cell=tuple(f['target_cell'])
        nontrav=[(x,y) for y in range(grid.shape[0]) for x in range(grid.shape[1])
                 if int(grid[y,x])==1 or (mode=='blocked' and int(grid[y,x])==-1)]
        ref=brute_force_topology_reference(grid,start,goal,mode,nontrav)
        route=plan(grid,start,goal,mode)
        label=_label(f,ref,route)
        reasons=[]
        if label!=f['expected_label']:reasons.append(f'label expected {f["expected_label"]}, got {label}')
        if cell not in visible_cells(grid,start,f['yaw'],**SENSOR):reasons.append('target not in frozen 61-ray visibility estimate')
        q=float(f['probability'][cell[1],cell[0]])
        if not .05<q<.95:reasons.append(f'target probability {q} is outside frozen eligibility range')
        ann=f['annotation']
        if ann.get('exact_separator_count') is not None and len(ref['start_goal_separating'])!=ann['exact_separator_count']:
            reasons.append(f'exact separator count expected {ann["exact_separator_count"]}, got {len(ref["start_goal_separating"])}')
        if ann.get('minimum_separator_count') is not None and len(ref['start_goal_separating'])<ann['minimum_separator_count']:
            reasons.append(f'separator count below {ann["minimum_separator_count"]}')
        if ann.get('must_be_articulation') and cell not in ref['articulation']:reasons.append('target is not an articulation point')
        if ann.get('must_not_separate_terminals') and cell in ref['start_goal_separating']:reasons.append('target unexpectedly separates terminals')
        if ann.get('must_be_cycle_vertex') and cell not in ref['cycle_vertices']:reasons.append('target is not in an alternate cycle')
        shortcut=ref['nontraversable_shortcuts'].get(cell,{})
        if 'baseline_disconnected' in ann and (ref['baseline_reachable']==ann['baseline_disconnected']):
            reasons.append('baseline connectivity annotation mismatch')
        if ann.get('restore_connects_terminals') and not shortcut.get('connectivity_restored'):
            reasons.append('target restoration does not connect terminals')
        if ann.get('baseline_connected') and not ref['baseline_reachable']:reasons.append('baseline expected connected')
        if ann.get('restore_shortens_path') and shortcut.get('kind')!='nontraversable_distance_shortcut':
            reasons.append('restoration did not produce distance-only shortcut')
        if ann.get('restore_distance_unchanged') and shortcut.get('kind')!='nontraversable_no_route_benefit':
            reasons.append('restoration changed route distance/connectivity')
        if f['family']=='nonarticulation_value_and_terminal_pairs' and f['source']=='seeded_generated' and f['fixture_id'].endswith(('v03','v04','v05')):
            pairs.setdefault(ann['same_graph_terminal_pair_group'],[]).append((f['fixture_id'],hashlib.sha256(grid.tobytes()).hexdigest(),start,goal))
        observed.append({'fixture_id':f['fixture_id'],'family':f['family'],'source':f['source'],
            'seed':f['seed'],'expected_label':f['expected_label'],'observed_label':label,
            'yaw':f['yaw'],'target_visible':cell in visible_cells(grid,start,f['yaw'],**SENSOR),
            'baseline_reachable':ref['baseline_reachable'],'baseline_distance':None if not np.isfinite(ref['baseline_distance']) else ref['baseline_distance'],
            'articulation_count':len(ref['articulation']),'separator_count':len(ref['start_goal_separating']),
            'bridge_count':len(ref['bridges']),'terminal_relevant_bridge_count':len(ref['terminal_relevant_bridges']),
            'cycle_vertex_count':len(ref['cycle_vertices']),'errors':reasons})
        if reasons:errors.append({'fixture_id':f['fixture_id'],'errors':reasons})
    for group,values in pairs.items():
        hashes={x[1] for x in values};pairs_set={x[2:] for x in values}
        if len(hashes)!=1:errors.append({'fixture_id':'same_graph_pair_group','errors':['grid maps differ within terminal-pair group']})
        if len(pairs_set)<2:errors.append({'fixture_id':'same_graph_pair_group','errors':['terminal pairs are not distinct']})
    return {'status':'PASS' if not errors and len(fixtures)==48 else 'INVALID_FIXTURE_SET',
        'fixture_count':len(fixtures),'family_counts':{name:sum(x['family']==name for x in fixtures) for name in sorted({x['family'] for x in fixtures})},
        'all_structural_annotations_consistent':not errors,'errors':errors,
        'independent_reference':'spatial_memory.topology_reference.brute_force_topology_reference',
        'policy_values_computed':False,'candidate_arms_executed':False,'fixtures':observed}


def main():
    result=validate_annotations();print(json.dumps({k:v for k,v in result.items() if k!='fixtures'},indent=2))
    if result['status']!='PASS':raise SystemExit(2)

if __name__=='__main__':main()
