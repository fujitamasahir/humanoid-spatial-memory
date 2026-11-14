"""Twelve hand-defined scenes; no random navigation cohort generation."""
FAMILIES=('corridor','unknown_obstacle','room','turn','repeat_view','explored',
          'known_stale','addition','removal','pedestrian','off_route','low_discovery')


def scenes():
    output=[]
    for name in FAMILIES:
        walls={(x,y) for y in range(15) for x in range(15) if x in (0,14) or y in (0,14)}
        start=(3,7);goal=(11,7);objects=[];changes=[];people=[]
        if name in ('corridor','low_discovery'):
            walls|={(x,y) for x in range(1,14) for y in (5,9)}
        if name=='unknown_obstacle':objects=[(7,7)]
        if name=='room':walls|={(5,y) for y in range(1,14) if y not in (6,7,8)}
        if name=='turn':start=(3,3);goal=(3,11)
        if name in ('repeat_view','known_stale'):
            walls|={(8,y) for y in range(1,14)}
        if name=='addition':changes=[{'step':6,'action':'add','cell':[6,7]}]
        if name=='removal':objects=[(6,7)];changes=[{'step':6,'action':'remove','cell':[6,7]}]
        if name=='pedestrian':people=[[(6,6),(6,7),(6,8),(6,7)]]
        if name=='off_route':goal=(3,11)
        if name=='low_discovery':objects=[(7,7)]
        output.append({'name':'DAO-engineering-'+name,'family':name,'split':'development','width':15,'height':15,
                       'start':start,'goal':goal,'walls':sorted(walls),'obstacles':objects,
                       'changes':changes,'pedestrians':people,'horizon':24,
                       'probe_schedule':[(0,0.),(1,1.5707963267948966),(2,3.141592653589793),
                                         (3,-1.5707963267948966),(4,0.),(5,0.),(10,0.),(11,0.),(12,0.),(13,0.)]})
    return output
