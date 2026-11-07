"""Development-only adapter around frozen constructors; no policy/navigation code."""
import json
from . import phase15_bprime as bp
from .phase15_bprime_records import validate_rejection


def plain(value):
    return json.loads(json.dumps(value,default=lambda v:sorted(v) if isinstance(v,(set,frozenset)) else (_ for _ in ()).throw(TypeError(type(v).__name__))))


class Builder:
    def __init__(self,backend):self.backend=backend;self.streams={};self.witness=None;self.geo=None

    def stream(self,identity,purpose):
        if purpose in self.streams:raise bp.IntegrityError('Duplicate stream construction')
        stream=bp.Stream(identity,purpose);self.streams[purpose]=stream;return stream

    def stream_counters(self):return {p:s.counters() for p,s in self.streams.items()}

    def rejection_evidence(self):
        if not self.witness:raise bp.IntegrityError('Missing saved rejection witness')
        return self.witness

    def geometry(self,job):
        self.streams={};self.witness=None
        identity=bp.Identity(job['partition'],job['mechanism'],bp.seed_for(job['partition'],job['mechanism'],job['index']))
        if identity.root!=job['identity']:raise bp.IntegrityError('Builder identity conflict')
        self.identity=identity
        try:self.geo=bp.geometry(identity,stream_factory=self.stream)
        except bp.legacy.Rejected as error:
            # Capture the already executed constructor's locals. No RNG replay,
            # resampling, geometry repair or replacement is involved.
            frame=error.__traceback__;v={};g={}
            while frame:
                if frame.tb_frame.f_code.co_name=='generate_v':v=frame.tb_frame.f_locals.copy()
                if frame.tb_frame.f_code.co_name=='geometry':g=frame.tb_frame.f_locals.copy()
                frame=frame.tb_next
            reason=str(error)
            if reason=='voronoi_seed_separation':self.witness=dict(seeds=v['seeds'])
            elif reason in ('voronoi_region_connectivity','voronoi_core'):
                region=v['region'];core={c for c in region if all(n in region for n in bp.legacy.neighbors(c))}
                self.witness=dict(region=region,core=core,seeds=v['seeds'],region_index=v['i'])
            elif reason=='voronoi_no_corridor':
                a,b=v['a'],v['b'];self.witness=dict(allowed=v['regions'][a]|v['regions'][b],core_a=v['cores'][a],core_b=v['cores'][b])
            elif reason=='voronoi_unintended_adjacency':self.witness=dict(free=v['free'],cores=v['cores'],chosen_edges=v['chosen'])
            else:self.witness=dict(free=g['free'])
            self.witness=plain(self.witness)
            validate_rejection(reason,self.witness,self.stream_counters())
            raise
        topology=bp.describe(self.geo.free,self.backend)
        return plain(dict(geometry=dict(width=25,height=25,free=sorted(self.geo.free,key=bp.legacy.row_key),construction=self.geo.construction),
                          topology=topology,roots=[identity.root],streams=self.stream_counters()))

    def complete(self,payload):
        pair=self.stream(self.identity,'start-goal')
        start,goal,distance=bp.choose_pair(self.geo.free,pair)
        schedules=[bp.build_schedule(self.geo,start,goal,self.stream(self.identity,f'dynamics-{i}')) for i in range(2)]
        payload.update(outcome='independent',reasons=['independent'],world=dict(start=start,goal=goal,distance=distance,schedules=schedules),streams=self.stream_counters())
        return plain(payload)
