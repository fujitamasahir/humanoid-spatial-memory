"""Fresh deterministic C v2.0d mechanism/computational fixture population."""
from __future__ import annotations
import hashlib
import json
import numpy as np

SEED_NAMESPACE=2026111600
FAMILIES=(
    'sparse_unique_separator', 'serial_separators',
    'irrelevant_articulation', 'loop_rich', 'occupied_connectivity',
    'occupied_distance_only', 'no_benefit_topology_control',
    'dense_competing_ties',
)
SIZES=((17,17),(19,25),(25,25),(27,33),(33,33),(17,41),(41,25),(49,49))


def _wall(h,w):
    grid=np.ones((h,w),dtype=np.int8)
    prob=np.full((h,w),.01,dtype=float)
    return grid,prob


def _room(grid,x0,x1,y0,y1):
    grid[y0:y1+1,x0:x1+1]=0


def _open_cells(grid,cells):
    for x,y in cells:grid[y,x]=0


def _fixture(family,index):
    seed=SEED_NAMESPACE+index*97+sum((i+1)*ord(c) for i,c in enumerate(family))
    rng=np.random.default_rng(seed)
    h,w=SIZES[(index+FAMILIES.index(family))%len(SIZES)]
    cy=int(rng.integers(5,h-5));sx=int(rng.integers(2,4));gx=w-int(rng.integers(3,5))
    start=(sx,cy);goal=(gx,cy);grid,prob=_wall(h,w)
    unknown='optimistic';yaw=0.;annotation={};target=None;label=None

    if family=='sparse_unique_separator':
        cut=sx+4
        _room(grid,cut-4,cut,cy-3,cy);_room(grid,cut,cut+4,cy,cy+3)
        start=(cut-2,cy-1);goal=(cut+2,cy+1)
        grid[cy,cut]=-1;target=(cut,cy);yaw=float(np.arctan2(1,2))
        label='start_goal_separating_articulation'
        annotation={'exact_start_goal_separator_count':1,'density_class':'sparse'}

    elif family=='serial_separators':
        cuts=sorted({sx+3,sx+6,sx+9})
        _open_cells(grid,[(x,cy) for x in range(1,w-1)])
        for cut in cuts:grid[cy,cut]=-1
        target=(cuts[0],cy)
        label='start_goal_separating_articulation'
        annotation={'minimum_start_goal_separator_count':len(cuts),
                    'expected_separator_cells':[[x,cy] for x in cuts],
                    'density_class':'sparse'}

    elif family=='irrelevant_articulation':
        _room(grid,1,w-2,cy,cy)
        bx=sx+2;branch_y=max(1,cy-4)
        _open_cells(grid,[(bx,yy) for yy in range(branch_y,cy)])
        _open_cells(grid,[(bx-1,cy-1)])
        # A side lobe ensures the marked stem is a genuine articulation in
        # the branch, but it cannot disconnect the current terminal pair.
        _open_cells(grid,[(bx-1,branch_y),(bx+1,branch_y)])
        target=(bx,cy-1);grid[target[1],target[0]]=-1
        yaw=float(np.arctan2(-1,bx-sx))
        label='irrelevant_articulation'
        annotation={'must_be_articulation':True,'must_not_separate_terminals':True,'density_class':'sparse'}

    elif family=='loop_rich':
        _room(grid,1,w-2,cy-3,cy+3)
        target=(min(gx-2,sx+3),cy);grid[target[1],target[0]]=-1
        label='route_cell_with_alternative_cycle'
        annotation={'must_be_cycle_vertex':True,'must_not_separate_terminals':True,'density_class':'medium'}

    elif family=='occupied_connectivity':
        cut=sx+4
        _room(grid,1,cut-1,cy-2,cy+2);_room(grid,cut+1,w-2,cy-2,cy+2)
        grid[cy,cut]=1;target=(cut,cy)
        label='nontraversable_connectivity_restoration'
        annotation={'baseline_disconnected':True,'restore_connects_terminals':True,'density_class':'sparse'}

    elif family=='occupied_distance_only':
        _room(grid,1,w-2,cy,cy)
        cut=min(gx-3,sx+4);grid[cy,cut]=1;target=(cut,cy)
        # Upper detour rejoins the main corridor on both sides of the blocked
        # direct cell; restoring the target strictly shortens the public path.
        _open_cells(grid,[(x,cy-2) for x in range(cut-3,cut+4)])
        grid[cy-1,cut-3]=0;grid[cy-1,cut+3]=0
        label='nontraversable_distance_shortcut'
        annotation={'baseline_connected':True,'restore_strictly_shortens':True,'density_class':'sparse'}

    elif family=='no_benefit_topology_control':
        _room(grid,1,w-2,cy-2,cy+2)
        # The target lies in a side alcove attached through a single occupied
        # cell; the terminals already have a broad open route.
        tx=sx+3;grid[cy-3,tx]=1;target=(tx,cy-3)
        _open_cells(grid,[(tx,cy-2),(tx,cy-1)])
        label='nontraversable_no_route_benefit'
        annotation={'expected_no_benefit_family':True,'density_class':'medium'}

    elif family=='dense_competing_ties':
        _room(grid,1,w-2,1,h-2)
        # Deterministic sparse obstacles in a dense map, kept away from the
        # terminal row so the nominal route remains available.
        for _ in range(max(1,(h*w)//140)):
            x=int(rng.integers(sx+2,gx-1));y=int(rng.integers(1,h-1))
            if y!=cy:grid[y,x]=1
        target=(sx+2,cy-1);grid[target[1],target[0]]=-1
        label='other_cycle_vertex'
        annotation={'must_be_cycle_vertex':True,'density_class':'dense','tie_probabilities':True}
    else:raise AssertionError(family)

    # Assign probabilities only within the frozen current observation
    # footprint; this controls candidate density without changing occupancy.
    from spatial_memory.evi import visible_cells
    footprint=visible_cells(grid,start,yaw,range_m=6.,cell_size=.75,
                            horizontal_fov_deg=120.,ray_count=61)
    for cell in footprint:
        if cell!=start:
            prob[cell[1],cell[0]]=(.5 if family=='dense_competing_ties'
                                   else float(rng.choice((.35,.5,.65))))
    if target!=start:prob[target[1],target[0]]=.5
    if family=='no_benefit_topology_control':
        for cell in footprint:
            if cell!=start:prob[cell[1],cell[0]]=.01
        prob[target[1],target[0]]=.5
    return {'fixture_id':f'{family}_{index:03d}','family':family,
        'seed':int(seed),'grid':grid,'probability':prob,'start':start,'goal':goal,
        'unknown':unknown,'yaw':yaw,'target_cell':target,
        'expected_label':label,'annotation':annotation,
        'generation':'seeded_template_augmentation','density_class':annotation['density_class']}


def build_formal_fixtures():
    """80 cases: one anchor and nine seeded variants per predeclared family."""
    return [_fixture(family,index) for family in FAMILIES for index in range(10)]


def population_sha256(fixtures=None):
    """Hash the complete deterministic fixture population before policy runs."""
    fixtures=build_formal_fixtures() if fixtures is None else fixtures
    digest=hashlib.sha256()
    for f in fixtures:
        metadata={k:f[k] for k in ('fixture_id','family','seed','start','goal',
            'unknown','yaw','target_cell','expected_label','annotation','density_class')}
        digest.update(json.dumps(metadata,sort_keys=True,separators=(',',':')).encode())
        digest.update(np.ascontiguousarray(f['grid']).tobytes())
        digest.update(np.ascontiguousarray(f['probability'],dtype='<f8').tobytes())
    return digest.hexdigest()
