"""Separate conformance/numerical gate implementation, isolated error categories.

This module never imports the multi-step policy or its runner. It reconstructs
all scalar costs and predicted states using the independent reference.
"""
from __future__ import annotations
import math
import numpy as np
from .multistep_reference import reference_cell,footprint
from .candidate_coverage import information_value_original_audit,information_value_uncertainty_k
from .topology_evi_d import information_value_topology_d

NEW=('ms_k','ms_k_visibility','ms_topology','ms_topology_visibility')
FROZEN={'C0':information_value_original_audit,'C-K':information_value_uncertainty_k,'C-Topology3-d':information_value_topology_d}
ALL=tuple(FROZEN)+NEW


def review_document(document,fixtures,*,sources_ok=True,artifacts_ok=True,annotations_ok=True):
    errors={k:[] for k in ('schema','source','artifact','annotation','numerical','selection','prediction','accounting')}
    if not sources_ok:errors['source'].append('Frozen source fingerprint mismatch')
    if not artifacts_ok:errors['artifact'].append('Artifact manifest mismatch')
    if not annotations_ok:errors['annotation'].append('Independent annotation validation failed')
    rows=document.get('fixtures',[])
    if len(rows)!=len(fixtures) or {r.get('id') for r in rows}!={f['id'] for f in fixtures}:errors['schema'].append('Fixture population mismatch')
    by_id={r.get('id'):r for r in rows}
    max_error=0.;opportunity={a:0 for a in NEW};bad_controls={a:0 for a in NEW};fp={a:0 for a in NEW};fn={a:0 for a in NEW}
    def eq(a,b,label,category='numerical'):
        nonlocal max_error
        try:error=abs(float(a)-float(b))
        except (ValueError,TypeError):error=math.inf
        max_error=max(max_error,error)
        if not math.isfinite(error) or error>1e-9:errors[category].append(label)
    for f in fixtures:
      grid=np.array(f['grid'],dtype=np.int8);q=np.array(f['probability']);start=tuple(f['start']);goal=tuple(f['goal'])
      args=(grid,q,start,goal,f['yaw'],f['unknown'],f['sensor'],f['remaining'])
      row=by_id.get(f['id'],{}).get('results',{})
      if set(row)!=set(ALL):errors['schema'].append(f['id']+': arm population mismatch');continue
      originals={a:fn_(*args) for a,fn_ in FROZEN.items()}
      for a,expected in originals.items():
        actual=row[a]
        for field in ('value','delay_regret','cost','net_value','plan_calls'):eq(actual.get(field),expected[field],f'{f["id"]}/{a}/{field}')
      for arm in NEW:
        actual=row[arm];k=3 if 'topology' in arm else 5
        frozen=originals['C-Topology3-d' if k==3 else 'C-K']
        expected_cells=[tuple(v['cell']) for v in frozen['shortlisted_candidates']]
        chosen=[tuple(v['cell']) for v in actual.get('shortlisted_candidates',[])]
        if chosen!=expected_cells:errors['selection'].append(f'{f["id"]}/{arm}: changed frozen selection')
        calls=1+2*len(expected_cells);price=.5+.01*calls+.5/f['remaining']
        eq(actual.get('cost'),price,f'{f["id"]}/{arm}/price')
        eq(actual.get('plan_calls'),calls,f'{f["id"]}/{arm}/calls','accounting')
        refs=[];predicted_states=set();cell_rows=actual.get('candidate_evaluations',[])
        if [tuple(r['cell']) for r in cell_rows]!=expected_cells:errors['schema'].append(f'{f["id"]}/{arm}: candidate rows mismatch');continue
        for c,crow in zip(expected_cells,cell_rows):
            ref=reference_cell(grid,c,float(q[c[1],c[0]]),start,goal,f['yaw'],f['unknown'],f['sensor'],price,'visibility' in arm)
            refs.append(ref)
            for field in ('value','delay_regret','net_value','no_information_cost','informed_movement_cost','observe_now_cost','best_postpone_cost'):
                eq(crow.get(field),ref[field],f'{f["id"]}/{arm}/{c}/{field}')
            options=crow.get('delayed_options',[])
            if len(options)!=6:errors['schema'].append(f'{f["id"]}/{arm}/{c}: missing prefix options');continue
            for option,oracle in zip(options,ref['options']):
                if option.get('route_index')!=oracle['route'] or option.get('after_moves')!=oracle['h']:errors['prediction'].append(f'{f["id"]}/{arm}/{c}: prefix catalog mismatch')
                eq(option.get('expected_movement'),oracle['movement'],f'{f["id"]}/{arm}/{c}: delayed movement')
                predicted=option.get('predictions',[])
                if len(predicted)!=2:errors['schema'].append('missing outcome prediction');continue
                for state,expected_state in zip(predicted,oracle['states']):
                    if tuple(state['position'])!=tuple(expected_state['position']) or state['visible']!=expected_state['visible'] or state['blocked_in_hypothesis']!=expected_state['blocked_in_hypothesis']:
                        errors['prediction'].append(f'{f["id"]}/{arm}/{c}: position/visibility prediction mismatch')
                    eq(state['yaw'],expected_state['yaw'],f'{f["id"]}/{arm}/{c}: heading','prediction')
                    predicted_states.add((tuple(expected_state['position']),expected_state['yaw']))
        expected=max(refs,key=lambda r:(r['net_value'],r['value']),default=None)
        expected_net=expected['net_value'] if expected else -price
        eq(actual.get('net_value'),expected_net,f'{f["id"]}/{arm}: selected score')
        eq(actual.get('prefix_step_visits'),2*len(chosen)*3*4,f'{f["id"]}/{arm}: prefix loop count','accounting')
        eq(actual.get('visibility_computations'),1+(len(predicted_states) if 'visibility' in arm else 0),f'{f["id"]}/{arm}: visibility count','accounting')
        for field,bound in [('plan_calls',1+2*k),('visibility_computations',1+12*k),('prefix_step_visits',24*k),('recovery_checks',36*k),('future_option_evaluations',6*k),('counterfactual_grid_cells_copied',2*k*grid.size)]:
            value=actual.get(field)
            if not isinstance(value,int) or value<0 or value>bound:errors['accounting'].append(f'{f["id"]}/{arm}: {field} bound')
        scan=actual.get('net_value',-1)>0
        expectation=f['expectation']
        if f.get('family') in ('last_chance','occupied_shortcut'):opportunity[arm]+=int(scan)
        if expectation in ('postpone','no_benefit','ineligible'):bad_controls[arm]+=int(scan)
        eligible=[c for c in footprint(grid,start,f['yaw'],f['sensor']) if c!=start and .05<float(q[c[1],c[0]])<.95]
        global_scan=any(reference_cell(grid,c,float(q[c[1],c[0]]),start,goal,f['yaw'],f['unknown'],f['sensor'],price,'visibility' in arm)['scan'] for c in eligible)
        fp[arm]+=int(scan and not global_scan);fn[arm]+=int(not scan and global_scan)
    numeric={
      'no_false_positive_authorizations':not any(fp.values()),
      'negative_controls_defer':not any(bad_controls.values()),
      'opportunity_positives_k':opportunity['ms_k']==0 and opportunity['ms_k_visibility']==16,
      'opportunity_positives_topology':opportunity['ms_topology']==0 and opportunity['ms_topology_visibility']==16,
    }
    valid=not any(errors.values())
    status='INVALID_STOP_BEFORE_FIT' if not valid else ('ACCEPTED_FOR_FIT' if all(numeric.values()) else 'VALID_REJECTED_STOP_BEFORE_FIT')
    return {'status':status,'FIT_authorized':status=='ACCEPTED_FOR_FIT','validity_errors':errors,'checks':{k:not v for k,v in errors.items()},'numeric_checks':numeric,'max_absolute_scalar_error':max_error if math.isfinite(max_error) else None,'opportunity_authorizations':opportunity,'negative_control_authorizations':bad_controls,'global_oracle_false_positives':fp,'global_oracle_false_negatives':fn,'reviewer_imports_new_policy':False}
