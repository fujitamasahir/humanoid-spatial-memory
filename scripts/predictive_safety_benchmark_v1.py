"""Prospective hand-defined engineering scenes; no random population generator."""
from copy import deepcopy
from dao_engineering_scenes_v1 import scenes as regressions


def benchmark():
    cases=[]
    for name in ('crossing','head_on','overtaking','sudden_stop','reversal','alternating',
                 'occluded','multiple','narrow','rotation','stationary','no_pedestrian','unavoidable_first','no_pedestrian_turn'):
        walls={(x,y) for x in range(17) for y in range(17) if x in (0,16) or y in (0,16)}
        start=(3,8);goal=(13,8);ped=[];expected='not_proven_unavoidable'
        if name=='crossing':ped=[[(8,y) for y in list(range(3,14))+list(range(12,3,-1))]]
        if name in ('head_on','narrow'):ped=[[(x,8) for x in list(range(13,2,-1))+list(range(4,13))]]
        if name=='overtaking':start=(5,8);ped=[[(x,8) for x in list(range(1,15))+list(range(13,1,-1))]]
        if name=='sudden_stop':ped=[[(8,y) for y in (3,4,5,6,7,8,8,8,8,9,10,9,8,7,6,5,4)]]
        if name=='reversal':ped=[[(8,y) for y in (6,7,8,7)]]
        if name=='alternating':ped=[[(7,y) for y in (7,8,9,8)]]
        if name=='occluded':
            walls|={(7,y) for y in range(2,8)};ped=[[(8,y) for y in (5,6,7,8,9,8,7,6)]]
        if name=='multiple':ped=[[(7,y) for y in (5,6,7,8,9,8,7,6)],[(10,y) for y in (11,10,9,8,7,8,9,10)]]
        if name=='narrow':walls|={(x,y) for x in range(1,16) for y in (6,10)}
        if name=='rotation':start=(4,4);goal=(4,13);ped=[[(6,y) for y in (3,4,5,4)]]
        if name=='stationary':ped=[[(8,8)]]
        if name=='unavoidable_first':start=(4,8);ped=[[(5,8),(4,8)]];expected='first_transition_unavoidable_before_any_robot_action'
        if name=='no_pedestrian_turn':start=(4,4);goal=(4,13)
        cases.append({'name':'predictive-safety-benchmark-'+name,'family':name,'split':'development',
            'width':17,'height':17,'start':start,'goal':goal,'walls':sorted(walls),'obstacles':[],
            'changes':[],'pedestrians':ped,'horizon':28,'role':'prospective_benchmark','declared_contact_class':expected})
    return cases


def all_cases():
    result=[]
    for d in regressions():
        d=deepcopy(d);d['role']='original_regression';d['declared_contact_class']='not_proven_unavoidable';result.append(d)
    return result+benchmark()
