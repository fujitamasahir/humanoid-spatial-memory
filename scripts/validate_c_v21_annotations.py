"""Independent annotation gate; deliberately never imports a candidate policy."""
from __future__ import annotations
import argparse,json,sys
import numpy as np
from c_v21_common import ROOT,OUT,write
sys.path.insert(0,str(ROOT/'src'))
from c_v21_fixtures import build,digest,FAMILIES
from spatial_memory.multistep_reference import footprint,reference_cell


def validate(fixtures):
    rows=[];errors=[]
    for f in fixtures:
        grid=np.array(f['grid'],dtype=np.int8);prob=np.array(f['probability']);cell=tuple(f['target'])
        eligible=cell in footprint(grid,f['start'],f['yaw'],f['sensor'])
        price=.5+.01*11+.5/f['remaining'] # conservative K=5 charge
        refs={mode:reference_cell(grid,cell,float(prob[cell[1],cell[0]]),f['start'],f['goal'],f['yaw'],f['unknown'],f['sensor'],price,mode=='visibility') for mode in ('blind','visibility')}
        expected=f['expectation'];local=[]
        if expected=='ineligible':
            if eligible:local.append('annotated hidden target is visible')
        else:
            if not eligible:local.append('annotated visible target is hidden')
        if expected=='opportunity':
            if refs['blind']['scan'] or not refs['visibility']['scan'] or refs['blind']['shared_prefix_moves']<1:local.append('last-opportunity annotation fails independent enumeration')
        elif expected=='immediate':
            if not all(r['scan'] for r in refs.values()) or refs['blind']['shared_prefix_moves']!=0:local.append('immediate divergence annotation fails')
        elif expected in ('postpone','no_benefit'):
            if any(r['scan'] for r in refs.values()):local.append('negative-control annotation fails')
            if expected=='postpone' and refs['blind']['shared_prefix_moves']<1:local.append('postpone fixture has no shared prefix')
            if expected=='postpone' and refs['blind']['value']<=price:local.append('postpone control has no valuable information')
            if expected=='postpone' and not any(o['h']<=refs['blind']['shared_prefix_moves'] and all(o['visible']) for o in refs['visibility']['options']):local.append('postpone control lacks a shared-prefix observation opportunity')
            if expected=='no_benefit' and refs['blind']['value']>1e-9:local.append('no-benefit fixture has positive V')
        rows.append({'id':f['id'],'target_visible':eligible,'expected_behavior':expected,'reference':refs,'errors':local})
        errors.extend(f['id']+': '+e for e in local)
    return {'status':'PASS' if not errors else 'FAIL','fixture_count':len(fixtures),'population_sha256':digest(fixtures),'families':list(FAMILIES),'errors':errors,'rows':rows,'policy_imported_or_executed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='prepolicy_annotation_validation.json');args=parser.parse_args()
    result=validate(build())
    write(OUT/args.output,result)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 2)
