"""Independent, pre-policy validation of v2d structural fixture annotations."""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from c_v2d_fixtures import FAMILIES,build_formal_fixtures
from spatial_memory.evi import visible_cells
from spatial_memory.navigation import plan
from spatial_memory.topology_reference import _components,_ref_graph,_shortest

SENSOR={'range_m':6.,'cell_size':.75,'horizontal_fov_deg':120.,'ray_count':61}


def _target_reference(grid,start,goal,mode,target):
    """Independent BFS checks for one annotation; no policy scores are read."""
    vertices,adj=_ref_graph(grid,mode);labels,groups=_components(adj)
    baseline=_shortest(adj,start,goal);target=tuple(target)
    result={'vertices':set(vertices),'adjacency':adj,
        'baseline_reachable':bool(np.isfinite(baseline)),'baseline_distance':baseline,
        'target_articulation':False,'target_separating':False,'target_cycle':False,
        'target_relevant_bridge_endpoint':False,'shortcut':None,'separator_count':None}
    if target in adj:
        _,without=_ref_graph(grid,mode,removed_vertex=target)
        _,after_groups=_components(without)
        result['target_articulation']=len(after_groups)>len(groups)
        result['target_separating']=(target not in (start,goal) and np.isfinite(baseline)
                                     and not np.isfinite(_shortest(without,start,goal)))
        neighbors=adj[target]
        for i,a in enumerate(neighbors):
            for b in neighbors[i+1:]:
                if np.isfinite(_shortest(without,a,b)):
                    result['target_cycle']=True;break
            if result['target_cycle']:break
        if np.isfinite(baseline):
            for neighbor in neighbors:
                edge=tuple(sorted((target,neighbor)))
                _,without_edge=_ref_graph(grid,mode,removed_edge=edge)
                if not np.isfinite(_shortest(without_edge,start,goal)):
                    result['target_relevant_bridge_endpoint']=True;break
    else:
        _,restored=_ref_graph(grid,mode,extra_open=(target,))
        distance=_shortest(restored,start,goal)
        if not np.isfinite(baseline) and np.isfinite(distance):result['shortcut']='nontraversable_connectivity_restoration'
        elif np.isfinite(baseline) and np.isfinite(distance) and distance<baseline:result['shortcut']='nontraversable_distance_shortcut'
        else:result['shortcut']='nontraversable_no_route_benefit'
    return result


def _label(f,ref,route):
    cell=tuple(f['target_cell'])
    if cell in ref['adjacency']:
        if cell in (f['start'],f['goal']):return 'traversable_terminal'
        if ref['target_separating']:return 'start_goal_separating_articulation'
        if ref['target_relevant_bridge_endpoint']:return 'terminal_relevant_bridge_endpoint'
        if ref['target_articulation'] and cell in set(route):return 'other_route_articulation'
        if ref['target_cycle'] and cell in set(route):return 'route_cell_with_alternative_cycle'
        if ref['target_articulation']:return 'irrelevant_articulation'
        if ref['target_cycle']:return 'other_cycle_vertex'
        return 'other_traversable'
    return ref['shortcut']


def _count_terminal_separators(grid,start,goal,mode):
    vertices,adj=_ref_graph(grid,mode);baseline=_shortest(adj,start,goal)
    if not np.isfinite(baseline):return 0
    count=0
    for vertex in vertices:
        if vertex in (start,goal):continue
        _,without=_ref_graph(grid,mode,removed_vertex=vertex)
        if not np.isfinite(_shortest(without,start,goal)):count+=1
    return count


def validate():
    fixtures=build_formal_fixtures();errors=[];rows=[];family_counts={}
    if len(fixtures)!=80:errors.append({'id':'suite','reason':f'expected 80, got {len(fixtures)}'})
    for f in fixtures:
        family_counts[f['family']]=family_counts.get(f['family'],0)+1
        g=f['grid'];start=f['start'];goal=f['goal'];mode=f['unknown'];cell=tuple(f['target_cell'])
        ann=f['annotation'];ref=_target_reference(g,start,goal,mode,cell)
        route=plan(g,start,goal,mode);observed=_label(f,ref,route)
        footprint=visible_cells(g,start,f['yaw'],**SENSOR)
        eligible=[c for c in footprint if c!=start and .05<float(f['probability'][c[1],c[0]])<.95]
        issues=[]
        if observed!=f['expected_label']:issues.append(f'expected {f["expected_label"]}, got {observed}')
        if cell not in footprint:issues.append('annotated target is outside the frozen visible footprint')
        if cell not in eligible:issues.append('annotated target fails frozen probability eligibility')
        if ann.get('exact_start_goal_separator_count') is not None:
            actual=_count_terminal_separators(g,start,goal,mode)
            if actual!=ann['exact_start_goal_separator_count']:issues.append(f'exact separator count expected {ann["exact_start_goal_separator_count"]}, got {actual}')
        if ann.get('minimum_start_goal_separator_count') is not None:
            for expected_cell in ann.get('expected_separator_cells',[]):
                sep_ref=_target_reference(g,start,goal,mode,tuple(expected_cell))
                if not sep_ref['target_separating']:issues.append(f'expected serial separator {expected_cell} does not separate')
            if len(ann.get('expected_separator_cells',[]))<ann['minimum_start_goal_separator_count']:
                issues.append('fixture annotation under-specifies serial separators')
        if ann.get('must_be_articulation') and not ref['target_articulation']:issues.append('target is not an articulation')
        if ann.get('must_not_separate_terminals') and ref['target_separating']:issues.append('target unexpectedly separates terminals')
        if ann.get('must_be_cycle_vertex') and not ref['target_cycle']:issues.append('target is not on a cycle')
        if ann.get('baseline_disconnected') and ref['baseline_reachable']:issues.append('baseline unexpectedly connected')
        if ann.get('restore_connects_terminals') and ref['shortcut']!='nontraversable_connectivity_restoration':issues.append('restoration does not connect terminals')
        if ann.get('baseline_connected') and not ref['baseline_reachable']:issues.append('baseline expected connected')
        if ann.get('restore_strictly_shortens') and ref['shortcut']!='nontraversable_distance_shortcut':issues.append('restoration is not distance-only shortcut')
        if ann.get('expected_no_benefit_family') and ref['shortcut']!='nontraversable_no_route_benefit':issues.append('target unexpectedly improves route')
        n=int(g.size);v=len(ref['vertices']);density=v/n
        if ann['density_class']=='sparse' and density>.45:issues.append(f'sparse density {density:.3f} exceeds .45')
        if ann['density_class']=='dense' and density<.55:issues.append(f'dense density {density:.3f} below .55')
        if issues:errors.append({'id':f['fixture_id'],'issues':issues})
        edges=sum(len(x) for x in ref['adjacency'].values())//2
        rows.append({'fixture_id':f['fixture_id'],'family':f['family'],'seed':f['seed'],
            'shape':list(g.shape),'N':n,'V':v,'E':edges,'density':density,
            'candidate_M':len(eligible),'target_visible':cell in footprint,
            'target_label_expected':f['expected_label'],'target_label_observed':observed,
            'terminal_pair':[start,goal],'baseline_reachable':ref['baseline_reachable'],
            'baseline_distance':None if not np.isfinite(ref['baseline_distance']) else ref['baseline_distance'],
            'target_is_articulation':ref['target_articulation'],
            'target_is_cycle_vertex':ref['target_cycle'],'issues':issues})
    if family_counts!={name:10 for name in FAMILIES}:errors.append({'id':'family_counts','actual':family_counts})
    if sum(row['candidate_M']>5 for row in rows)<60:errors.append({'id':'candidate_population','reason':'fewer than 60 fixtures have more than five eligible candidates'})
    if sum(row['candidate_M']>20 for row in rows)<20:errors.append({'id':'candidate_population','reason':'fewer than 20 fixtures have more than twenty eligible candidates'})
    return {'status':'PASS' if not errors else 'INVALID_FIXTURE_SET','fixture_count':len(fixtures),
        'family_counts':family_counts,'seed_namespace':2026111600,
        'independent_reference':'topology_reference._ref_graph/_components/_shortest (BFS)',
        'candidate_values_computed':False,'candidate_arms_executed':False,
        'fixtures_with_M_gt_5':sum(row['candidate_M']>5 for row in rows),
        'fixtures_with_M_gt_20':sum(row['candidate_M']>20 for row in rows),
        'errors':errors,'fixtures':rows}


if __name__=='__main__':
    result=validate()
    print(json.dumps({k:v for k,v in result.items() if k!='fixtures'},indent=2))
    if result['status']!='PASS':raise SystemExit(2)
