"""Frozen public-grid fixture constructors for C v2.0c mechanism evaluation."""
from __future__ import annotations
import numpy as np

BASE_SEED=2026111400
FAMILY_NAMES=('single_separator','serial_separators','irrelevant_articulation',
    'alternative_loop','occupied_connectivity','occupied_shortcut_or_none',
    'no_benefit_and_C0_controls','nonarticulation_value_and_terminal_pairs')


def _wall():
    g=np.ones((17,17),dtype=np.int8);p=np.full(g.shape,.01,dtype=float)
    return g,p


def _open(g,*cells):
    for x,y in cells:g[y,x]=0


def _uncertain(g,p,cells,q=.5):
    for x,y in cells:g[y,x]=-1;p[y,x]=q


def _add_decoys(g,p,y,positions,q):
    for x in positions:
        if g[y,x]==1:g[y,x]=0
        p[y,x]=q;g[y,x]=-1


def build_formal_fixtures():
    """48 cases, six in each predeclared family (one manual, five seeded)."""
    fixtures=[]
    for family_index,family in enumerate(FAMILY_NAMES):
        for variant in range(6):
            seed=BASE_SEED+family_index*100+variant
            rng=np.random.default_rng(seed)
            y=int(rng.integers(6,11))
            q=float((.35,.5,.65)[variant%3])
            g,p=_wall();start=(2,y);goal=(14,y);target=None;expected=None;mode='optimistic';annotation={};yaw=0.
            source='manual' if variant==0 else 'seeded_generated'

            if family=='single_separator':
                # Two chambers touch the center through two cells each, so only
                # the center itself separates start and goal.
                for x in range(1,7):
                    for yy in range(y-2,y+3):
                        if x<6 or yy<=y:g[yy,x]=0
                for x in range(8,16):
                    for yy in range(y-2,y+3):
                        if x>8 or yy>=y:g[yy,x]=0
                _open(g,(6,y-1),(7,y-1),(6,y),(7,y),(8,y),(8,y+1),(7,y+1))
                target=(7,y);_uncertain(g,p,[target],q)
                decoys=[(x,y) for x in (3,4,5)]
                _uncertain(g,p,decoys,.5)
                expected='start_goal_separating_articulation';annotation={'exact_separator_count':1}

            elif family=='serial_separators':
                _open(g,*[(x,y) for x in range(1,16)])
                loc=8+(variant%2)
                target=(loc,y);others=[(x,y) for x in (5,11) if x!=loc]
                if variant==5:
                    _uncertain(g,p,[target],q);mode='blocked'
                    expected='nontraversable_connectivity_restoration';annotation={'baseline_disconnected':True,'restore_connects_terminals':True}
                else:
                    _uncertain(g,p,[target,*others],q)
                    expected='start_goal_separating_articulation';annotation={'minimum_separator_count':3}

            elif family=='irrelevant_articulation':
                _open(g,*[(x,y) for x in range(1,16)])
                branch_x=2
                for yy in (y-1,y-2,y-3):g[yy,branch_x]=0
                g[y-3,branch_x-1]=0;g[y-3,branch_x+1]=0
                yaw=-np.pi/2
                target=(branch_x,y-3);_uncertain(g,p,[target,(branch_x,y-2)],q)
                expected='irrelevant_articulation';annotation={'must_be_articulation':True,'must_not_separate_terminals':True}

            elif family=='alternative_loop':
                _open(g,*[(x,y) for x in range(1,16)])
                lx=4+(variant%2);rx=11
                for xx in (lx,rx):
                    for yy in range(y-1,y-4,-1):g[yy,xx]=0
                for xx in range(lx,rx+1):g[y-3,xx]=0
                target=(7+(variant%3),y);_uncertain(g,p,[target],q)
                expected='route_cell_with_alternative_cycle';annotation={'must_be_cycle_vertex':True,'must_not_separate_terminals':True}

            elif family=='occupied_connectivity':
                split=7+(variant%3)
                _open(g,*[(x,y) for x in range(1,split)])
                _open(g,*[(x,y) for x in range(split+1,16)])
                target=(split,y);g[y,split]=1;p[y,split]=q
                _uncertain(g,p,[(x,y) for x in range(max(3,split-3),split)],.5)
                expected='nontraversable_connectivity_restoration';annotation={'baseline_disconnected':True,'restore_connects_terminals':True}

            elif family=='occupied_shortcut_or_none':
                if variant<3:
                    _open(g,*[(x,y) for x in range(1,16)])
                    # Force a top detour while retaining an existing route.
                    for x in range(2,15):g[y-1,x]=1
                    detour_x1=4;detour_x2=12
                    for x in range(detour_x1,detour_x2+1):g[y-2,x]=0
                    g[y-1,detour_x1]=g[y-1,detour_x2]=0
                    xx=8+(variant%2);target=(xx,y);g[y,xx]=1;p[y,xx]=q
                    expected='nontraversable_distance_shortcut';annotation={'baseline_connected':True,'restore_shortens_path':True}
                else:
                    _open(g,*[(x,y) for x in range(1,16)])
                    bx=5+(variant%3)
                    for xx in range(2,bx):g[y-1,xx]=0
                    g[y-1,bx]=1;g[y-2,bx]=0
                    target=(bx,y-1);g[y-1,bx]=1;p[y-1,bx]=q
                    expected='nontraversable_no_route_benefit';annotation={'baseline_connected':True,'restore_distance_unchanged':True}

            elif family=='no_benefit_and_C0_controls':
                _open(g,*[(x,y) for x in range(1,16)])
                if variant<3:
                    bx=2
                    g[y-1,bx]=0;g[y-2,bx]=0
                    target=(bx,y-2);_uncertain(g,p,[target],q)
                    expected='other_traversable';annotation={'expected_no_scan':True}
                    yaw=-np.pi/2
                    if variant==2:goal=start
                else:
                    xx=4+(variant-3);target=(xx,y);_uncertain(g,p,[target],q)
                    expected='start_goal_separating_articulation';annotation={'C0_control_candidate_on_nominal_route':True}

            elif family=='nonarticulation_value_and_terminal_pairs':
                if variant<3:
                    # Main line has a bypass loop with a distinct first action.
                    _open(g,*[(x,y) for x in range(1,16)])
                    for yy in (y-1,y-2):g[yy,2]=0
                    for x in range(2,9):g[y-1,x]=0
                    g[y-1,8]=0
                    xx=3;target=(xx,y);_uncertain(g,p,[target],q)
                    expected='route_cell_with_alternative_cycle';annotation={'target_is_nonarticulation':True,'target_expected_high_EVI':True}
                else:
                    # Same graph across three terminal pairs, with two crossings.
                    y=8
                    g,p=_wall();upper=y-2;lower=y+2
                    _open(g,*[(x,upper) for x in range(1,16)])
                    _open(g,*[(x,lower) for x in range(1,16)])
                    _open(g,*[(8,yy) for yy in range(upper,lower+1)])
                    _open(g,*[(x,yy) for x in (1,15) for yy in range(upper,lower+1)])
                    g[1:16,8]=1;g[upper,8]=-1;g[lower,8]=-1
                    yy=y-2 if variant==3 else y+2
                    start=(2,yy);goal=(14,yy);target=(8,yy)
                    _uncertain(g,p,[target],q)
                    expected='route_cell_with_alternative_cycle';annotation={'same_graph_terminal_pair_group':1,'target_is_cycle_vertex':True}
            else:raise AssertionError(family)

            fixtures.append({'fixture_id':f'{family}_v{variant:02d}','family':family,
                'source':source,'seed':seed,'grid':g,'probability':p,
                'start':start,'goal':goal,'unknown':mode,'yaw':float(yaw),'target_cell':target,
                'expected_label':expected,'annotation':annotation})
    return fixtures
