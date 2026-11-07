"""Outcome-specific evidence validation. No RNG or navigation execution."""
from dataclasses import dataclass
from collections import deque
import hashlib
from . import phase15_generators as legacy
from . import phase15_topology as top
from . import phase15_bprime as bp
from .phase15_bprime_protocol import Record, Lineage, digest

SCIENTIFIC = {'independent','same_partition_related','cross_partition_or_historical','no_start_goal_pair'}
GEOMETRY_REJECTIONS={'outer_ring','free_count','density','connectivity','voronoi_seed_separation','voronoi_region_connectivity','voronoi_core','voronoi_no_corridor','voronoi_unintended_adjacency'}
TERMINAL = {'implementation_error','BackendFailure','DynamicLimit','integrity_failure'}
_TOKEN = object()


def require(condition, reason):
    if not condition:
        raise bp.IntegrityError(reason)


def distances(free,start):
    result={start:0};queue=deque([start])
    while queue:
        x,y=queue.popleft()
        for c in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
            if c in free and c not in result:
                result[c]=result[x,y]+1;queue.append(c)
    return result


def validate_counter(counter):
    require(isinstance(counter,dict),'Missing stream counter')
    require(isinstance(counter.get('identity'),str) and len(counter['identity'])==64 and all(c in '0123456789abcdef' for c in counter['identity']),'Missing stream commitment')
    bounds=counter.get('bounds');words=counter.get('words')
    require(isinstance(bounds,list) and type(words) is int and words>=len(bounds),'Invalid RNG consumption')
    require(all(type(n) is int and 0<n<=2**64 for n in bounds),'Invalid RNG bounds')


def validate_partition(construction):
    rooms=[tuple(r) for r in construction['rooms']]
    bp.validate_rooms(rooms)
    n=construction['desired'];splits=construction['splits'];leaves=[(0,0,5,5)]
    require(n in (12,16,20) and len(rooms)==n and len(splits)==n-1,'Room count/trace conflict')
    bounds=[3]
    for row in splits:
        eligible=sorted(r for r in leaves if r[0]<r[2] or r[1]<r[3])
        rect=tuple(row['rect']);axis=row['axis'];cut=row['cut']
        require(rect in eligible and type(axis) is int,'Invalid split leaf/axis')
        axes=[a for a in (0,1) if rect[a]<rect[a+2]]
        require(axis in axes and type(cut) is int and rect[axis]<cut<=rect[axis+2],'Invalid cut')
        a,b,c,d=rect
        children=[(a,b,cut-1,d),(cut,b,c,d)] if axis==0 else [(a,b,c,cut-1),(a,cut,c,d)]
        require([tuple(r) for r in row['children']]==children,'Changed split children')
        bounds.extend((len(eligible),len(axes),rect[axis+2]-rect[axis]))
        leaves.remove(rect);leaves.extend(children)
    require(sorted(leaves)==rooms,'Partition trace does not produce saved rooms')
    return rooms,bounds


def validate_geometry(geometry, streams, mechanism):
    require(isinstance(geometry,dict),'Missing raster geometry')
    require(geometry.get('width')==25 and geometry.get('height')==25,'Wrong raster domain')
    cells=geometry.get('free');require(isinstance(cells,list),'Missing full raster')
    require(cells==sorted(cells,key=lambda c:(c[1],c[0])),'Raster cells must retain row-major serialization')
    free=frozenset(map(tuple,cells))
    require(len(free)==len(cells) and all(type(x) is int and type(y) is int and 1<=x<=23 and 1<=y<=23 for x,y in free),'Malformed raster')
    require(len(free)>=80 and .15<=1-len(free)/625<=.85 and len(distances(free,min(free)))==len(free),'Geometry constraint failure')
    construction=geometry.get('construction');require(isinstance(construction,dict),'Missing construction trace')
    purposes=('partition','tree','chords','doors') if mechanism=='BP' else ('geometry',)
    require(set(purposes)<=set(streams),'Missing construction RNG streams')
    for purpose in purposes:validate_counter(streams[purpose])
    if mechanism=='BP':
        rooms,bounds=validate_partition(construction)
        require(streams['partition']['bounds']==bounds,'Partition draw-order conflict')
        adjacency=bp.adjacency(rooms)
        require([tuple(e) for e in construction['adjacency']]==adjacency,'Adjacency conflict')
        tree=[tuple(e) for e in construction['tree']]
        require(len(tree)==len(rooms)-1 and len(set(tree))==len(tree) and set(tree)<=set(adjacency),'Invalid spanning tree')
        reach={0}
        while True:
            added=reach|{v for a,b in tree for u,v in ((a,b),(b,a)) if u in reach}
            if added==reach:break
            reach=added
        require(len(reach)==len(rooms),'Disconnected spanning tree')
        unused=sorted(set(adjacency)-set(tree));k=construction['K']
        extra=[tuple(e) for e in construction['extra']]
        selected=[tuple(e) for e in construction['selected']]
        require(type(k) is int and 0<=k<=len(unused) and len(extra)==k and len(set(extra))==k and set(extra)<=set(unused),'Invalid additional edges')
        require(selected==sorted(tree+extra) and construction['available_rank']==len(unused),'Selected graph conflict')
        require([tuple(e) for e in construction['unused']]==unused,'Unused-edge conflict')
        require(streams['tree']['bounds']==list(range(len(adjacency),1,-1)),'Tree permutation consumption conflict')
        require(streams['chords']['bounds']==[len(unused)+1]+list(range(len(unused),1,-1)),'Chord consumption conflict')
        expected={(x,y) for a,b,c,d in rooms for x in range(4*a+1,4*c+4) for y in range(4*b+1,4*d+4)}
        doors=construction['doors'];require(len(doors)==len(selected),'Missing doors')
        door_bounds=[]
        for row,edge in zip(doors,selected):
            options=bp.door_options(rooms[edge[0]],rooms[edge[1]])
            require(tuple(row['edge'])==edge and tuple(row['cell']) in options,'Door does not realize selected edge')
            expected.add(tuple(row['cell']));door_bounds.append(len(options))
        require(expected==free and streams['doors']['bounds']==door_bounds,'Raster or door consumption conflict')
    return free


def validate_schedules(world, free):
    start,goal=tuple(world['start']),tuple(world['goal'])
    require(start in free and goal in free and start!=goal,'Invalid protected endpoints')
    d=distances(free,start).get(goal)
    require(d==world['distance'] and 12<=d<=40 and abs(start[0]-goal[0])+abs(start[1]-goal[1])>=5,'Pair eligibility conflict')
    schedules=world.get('schedules');require(isinstance(schedules,list) and len(schedules)==2,'Exactly two schedules required')
    for schedule in schedules:
        category=schedule.get('category');require(category in legacy.CATEGORIES,'Unknown dynamics category')
        attempts=schedule.get('attempts');failures=schedule.get('failures')
        require(type(attempts) is int and isinstance(failures,list) and all(isinstance(x,str) and x for x in failures),'Missing proposal failure trace')
        if category=='none':
            require(attempts==0 and not failures and not schedule['events'] and not schedule['initial'] and not schedule['positions'],'Malformed no-change schedule')
            continue
        require(1<=attempts<=128 and len(failures)==attempts-1,'Dynamics retry accounting conflict')
        length=schedule['length'];footprint=list(map(tuple,schedule['footprint']))
        require(length in ((4,6,8) if category=='moving' else (2,3,4)),'Wrong footprint length')
        paths=[footprint]
        if category=='swap':paths.append(list(map(tuple,schedule['other_footprint'])))
        for path in paths:
            require(len(path)==length and len(set(path))==length and set(path)<=free-{start,goal},'Invalid footprint')
            require(all(abs(a[0]-b[0])+abs(a[1]-b[1])==1 for a,b in zip(path,path[1:])),'Noncardinal footprint')
        require(len(paths)==1 or not set(paths[0])&set(paths[1]),'Overlapping swap')
        if category=='moving':
            require(schedule['onset'] is None and not schedule['initial'] and not schedule['events'],'Invalid moving static state')
            dwells=schedule['dwells'];require(dwells and dwells[0] in (2,3,4) and all(x in (2,3,4,5,6) for x in dwells[1:]),'Invalid dwells')
            require(sum(dwells[:-1])<81<=sum(dwells),'Incorrect dwell truncation')
            expanded=[];i=0;direction=1
            for dwell in dwells:
                expanded.extend([footprint[i]]*dwell)
                if i==length-1:direction=-1
                elif i==0:direction=1
                i+=direction
            require(list(map(tuple,schedule['positions']))==expanded[:81],'Moving trajectory conflict')
        else:
            onset=schedule['onset'];require(type(onset) is int and 2<=onset<=12 and not schedule['positions'],'Invalid static timing')
            initial=footprint if category in ('removal','swap') else []
            expected=[]
            if category in ('removal','swap'):expected += [('remove',c) for c in footprint]
            if category in ('addition','swap'):expected += [('add',c) for c in (paths[1] if category=='swap' else footprint)]
            actual=[(e['action'],tuple(e['cell'])) for e in schedule['events']]
            require(actual==expected and all(e['step']==onset for e in schedule['events']) and list(map(tuple,schedule['initial']))==initial,'Static event conflict')
            final=set(initial)
            for action,c in expected:
                if action=='remove':final.remove(c)
                else:final.add(c)
            require(goal in distances(free-set(initial),start) and goal in distances(free-final,start),'Dynamics disconnects protected pair')


@dataclass(frozen=True)
class CandidateEvidence:
    payload: dict
    sha256: str
    record: Record | None
    complete: bool
    token: object
    seal: tuple

    def check(self):
        require(self.token is _TOKEN and digest(self.payload)==self.sha256
                and self.seal==(self.sha256,self.record,self.complete),'Evidence changed after validation')
        return self


def _evidence(payload,record,complete):
    checksum=digest(payload)
    return CandidateEvidence(payload,checksum,record,complete,_TOKEN,(checksum,record,complete))


def graph_fixture_evidence(record, complete):
    require(record.partition.startswith('synthetic-') and all(k[0]=='synthetic-exact-oracle' for k in record.keys),'Graph fixture profile required')
    payload={'kind':'synthetic-graph','identity':record.identity,'complete':bool(complete)}
    return _evidence(payload,record,bool(complete))


def validate_rejection(outcome,witness,streams):
    """Check a saved deterministic failure witness, never redraw the sampler."""
    require(isinstance(witness,dict) and bool(witness),'Missing rejection witness')
    if outcome=='voronoi_seed_separation':
        seeds=list(map(tuple,witness['seeds']))
        require(len(seeds) in (12,16,20) and len(set(seeds))==len(seeds)
                and all(1<=x<=23 and 1<=y<=23 for x,y in seeds),'Incomplete Voronoi seed witness')
        require(any(abs(a[0]-b[0])+abs(a[1]-b[1])<4 for i,a in enumerate(seeds) for b in seeds[i+1:]),'Claimed seed rejection does not hold')
        require(streams['geometry']['bounds']==[3]+list(range(529,1,-1)),'Voronoi seed draw trace incomplete')
    elif outcome in ('voronoi_region_connectivity','voronoi_core'):
        region=set(map(tuple,witness['region']))
        require(bool(region),'Missing region witness')
        if outcome=='voronoi_region_connectivity':
            require(len(distances(region,min(region)))!=len(region),'Region is connected')
        else:
            core={c for c in region if all(n in region for n in legacy.neighbors(c))}
            require(core==set(map(tuple,witness['core'])),'Wrong saved core')
            require(not core or len(distances(core,min(core)))!=len(core) or
                    not any({(x,y),(x+1,y),(x,y+1),(x+1,y+1)}<=core for x,y in core),'Core is valid')
    elif outcome=='voronoi_no_corridor':
        allowed=set(map(tuple,witness['allowed']));a=set(map(tuple,witness['core_a']));b=set(map(tuple,witness['core_b']))
        require(a and b and a|b<=allowed and not (set(distances(allowed,min(a)))&b),'Corridor exists or witness incomplete')
    elif outcome=='voronoi_unintended_adjacency':
        free=set(map(tuple,witness['free']));cores=[set(map(tuple,c)) for c in witness['cores']]
        require(cores and all(cores),'Missing corridor/core witness')
        owner={c:i for i,core in enumerate(cores) for c in core}
        remaining=free-owner.keys();touches=set()
        while remaining:
            component=set(distances(remaining,min(remaining)));remaining-=component
            ids=sorted({owner[n] for c in component for n in legacy.neighbors(c) if n in owner})
            touches.update((a,b) for i,a in enumerate(ids) for b in ids[i+1:])
        touches.update(tuple(sorted((i,owner[n]))) for c,i in owner.items() for n in legacy.neighbors(c) if n in owner and owner[n]!=i)
        require(touches!=set(map(tuple,witness['chosen_edges'])),'No unintended adjacency')
    else:
        free=set(map(tuple,witness['free']))
        outer=any(not (1<=x<=23 and 1<=y<=23) for x,y in free)
        require(outcome=='outer_ring' or not outer,'Wrong rejection priority')
        if outcome=='outer_ring':require(outer,'Outer ring is valid')
        elif outcome=='free_count':require(len(free)<80,'Free count is valid')
        elif outcome=='density':require(len(free)>=80 and not .15<=1-len(free)/625<=.85,'Density is valid')
        elif outcome=='connectivity':require(len(free)>=80 and .15<=1-len(free)/625<=.85 and len(distances(free,min(free)))!=len(free),'Geometry is connected')


def validate_candidate(payload, *, synthetic=False, backend=None):
    """Validate saved evidence without replaying registered RNG streams."""
    try:
        require(isinstance(payload,dict) and payload.get('kind')=='candidate','Candidate schema required')
        require(payload.get('version')==bp.VERSION and payload.get('profile')==('synthetic' if synthetic else 'production'),'Candidate version/profile conflict')
        identity=payload['identity'];part=payload['partition'];mechanism=payload['mechanism'];outcome=payload['outcome']
        bp.development_partition(part)
        require(mechanism in bp.MECHANISMS and type(payload['index']) is int and 0<=payload['index']<10000,'Invalid candidate position')
        if synthetic:require(identity==f'synthetic:{part}:{mechanism}:{payload["index"]}','Synthetic identity conflict')
        else:require(identity==bp.Identity(part,mechanism,bp.seed_for(part,mechanism,payload['index'])).root,'Registered identity conflict')
        require(type(payload.get('sequence')) is int and payload['sequence']>=0,'Missing decision sequence')
        require(outcome in SCIENTIFIC|TERMINAL|GEOMETRY_REJECTIONS,'Unknown outcome')
        require(isinstance(payload.get('reasons'),list) and payload['reasons'] and payload['reasons'][0]==outcome,'Missing exclusive rejection/outcome trace')
        if outcome in TERMINAL:
            require(isinstance(payload.get('error'),str) and payload['error'] and payload.get('phase') in ('geometry','canonicalization','pair','dynamics','integrity'),'Incomplete terminal failure evidence')
            return _evidence(payload,None,False)
        if outcome in GEOMETRY_REJECTIONS:
            require(mechanism!='BP' and payload.get('phase')=='geometry','B-prime invariant failure is terminal')
            require(not outcome.startswith('voronoi_') or mechanism=='V','Wrong mechanism for rejection reason')
            require(isinstance(payload.get('rejection_evidence'),dict) and bool(payload['rejection_evidence']),'Missing scientific rejection evidence')
            require(set(payload['streams'])=={'geometry'},'Wrong rejection stream set')
            validate_counter(payload['streams']['geometry'])
            validate_rejection(outcome,payload['rejection_evidence'],payload['streams'])
            return _evidence(payload,None,False)
        streams=payload['streams'];free=validate_geometry(payload['geometry'],streams,mechanism)
        graph,detail=top.raster_quotient(free);evidence=payload['topology']
        construction=payload['geometry']['construction']
        if mechanism=='BP':
            require(construction['room_count']==construction['selected_graph_vertices']==len(construction['rooms']),'Construction room-count descriptors conflict')
            require(all(construction[k]==v for k,v in detail.items()),'Construction quotient descriptors conflict')
        if 'stream_counters' in construction:
            require(all(streams[p]==c for p,c in construction['stream_counters'].items()),'Duplicate RNG counters conflict')
        namespace='synthetic-exact-oracle' if synthetic else bp.CANONICAL_NAMESPACE
        require(evidence['matrix']==list(map(list,graph.matrix)),'Quotient matrix conflict')
        exact=tuple(evidence['exact']);keys=frozenset(map(tuple,evidence['keys']))
        require(exact in keys and all(k[0]==namespace for k in keys),'Wrong canonical namespace/self key')
        require(backend is not None,'Independent guarded/oracle key verification required')
        if not synthetic:require(isinstance(backend,bp.Backend),'Approved C3 backend required')
        require(backend.exact_certificate(graph)==exact and backend.near_certificates(graph)==keys,'Canonical evidence conflict')
        require(evidence['cycle_rank']==bp.cycle_rank(graph) and evidence['normalized_vertices']==graph.n,'Topology descriptors conflict')
        roots=Lineage(frozenset(payload['roots']))
        require(set(payload['geometry']['construction']['ancestral_roots'])<=roots.roots,'Known geometry ancestry erased')
        record=Record(identity,'synthetic-'+part if synthetic else part,mechanism,exact,keys,
                      top.raster_certificate(free),roots)
        complete=outcome=='independent'
        purposes={'partition','tree','chords','doors'} if mechanism=='BP' else {'geometry'}
        if complete:
            validate_schedules(payload['world'],free)
            eligible=sum(12<=d<=40 and abs(a[0]-b[0])+abs(a[1]-b[1])>=5
                         for a in free for b,d in distances(free,a).items())
            require(streams['start-goal']['bounds']==[eligible],'Pair draw bound conflict')
            for i,schedule in enumerate(payload['world']['schedules']):
                bounds=streams[f'dynamics-{i}']['bounds'];category=schedule['category']
                if category=='none':require(bounds==[5],'No-change consumed extra draws')
                elif category=='moving':
                    suffix=[2,3]+[5]*(len(schedule['dwells'])-1)
                    require(bounds[:2]==[5,3] and bounds[-len(suffix):]==suffix,'Moving RNG consumption conflict')
                else:require(bounds[:3]==[5,11,3],'Static RNG consumption conflict')
            purposes |= {'start-goal','dynamics-0','dynamics-1'}
        elif outcome=='no_start_goal_pair':
            require(not any(12<=d<=40 and abs(a[0]-b[0])+abs(a[1]-b[1])>=5 for a in free for b,d in distances(free,a).items()),'Claimed empty pair list is nonempty')
            purposes.add('start-goal')
        else:require(payload.get('world') is None,'Related records must not contain complete worlds')
        require(set(streams)==purposes,'Extra or missing RNG purposes')
        for purpose,counter in streams.items():
            validate_counter(counter)
            if not synthetic:
                seed=bp.seed_for(part,mechanism,payload['index'])
                fields=(bp.VERSION,str(seed),purpose)
                raw=b''.join(len(f.encode()).to_bytes(4,'little')+f.encode() for f in fields)
                require(counter['identity']==hashlib.sha256(raw).hexdigest(),'Stream namespace/identity conflict')
        measurements=evidence.get('measurements')
        require(isinstance(measurements,list),'Missing canonicalization runtime evidence')
        if not synthetic:
            require(bool(measurements),'Missing production canonicalization measurements')
            for m in measurements:
                require(m['status']=='certified' and 0<=m['seconds']<=5 and 0<m['peak_rss_kib']<=524288
                        and m['native_search_nodes'] is None,'Canonicalization resource evidence conflict')
        return _evidence(payload,record,complete)
    except (KeyError,TypeError,ValueError,IndexError) as error:
        if isinstance(error,bp.IntegrityError):raise
        raise bp.IntegrityError('Malformed or partial candidate evidence') from error


def checkpoint_payload(payload, *, synthetic, backend=None):
    if synthetic and isinstance(payload,dict) and payload.get('kind')=='synthetic-storage-fixture':
        require(isinstance(payload.get('data'),dict) and bool(payload['data']),'Explicit noncandidate storage fixture required')
        digest(payload)
        return None
    return validate_candidate(payload,synthetic=synthetic,backend=backend)
