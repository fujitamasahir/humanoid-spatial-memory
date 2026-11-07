"""Independent reconstruction from saved development checkpoints; no RNG replay.

Does not import the production admission index, builder or coordinator. No
candidate generation, navigation or reserved-stage path can be requested.
"""
import argparse
from collections import Counter,deque
import gzip,hashlib,json
from pathlib import Path
from spatial_memory.phase15_macos_monitored import MonitoredBackend,PROFILE
from spatial_memory.phase15_topology import Graph
from verify_phase15_macos_references import quotient,raster_key,canon,sha
ROOT=Path(__file__).resolve().parents[1]
VERSION='phase1.5-v0.4-BPRIME-1';METHODS=('R','BP','V','M')
PARTS={'fit':(80000000,12),'calibration':(80100000,6),'selection':(80200000,6)}


def distances(free,start):
 queue=deque([start]);seen={start:0}
 while queue:
  x,y=queue.popleft()
  for c in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
   if c in free and c not in seen:seen[c]=seen[x,y]+1;queue.append(c)
 return seen


def main():
 p=argparse.ArgumentParser();p.add_argument('--partition',choices=list(PARTS),required=True);a=p.parse_args()
 stage=a.partition;base,target=PARTS[stage];rawroot=ROOT/'results/raw/phase15_macos_development';out=ROOT/'results/phase15_macos_development'
 output=out/f'{stage}_independent_verification.json';assert not output.exists()
 inventory=json.loads((rawroot/'references/inventory.json').read_bytes());seal=json.loads((out/'reference_seal.json').read_bytes());assert sha(canon(inventory))==seal['inventory_sha256']
 records=[];parent=[];key_index={};raster_index={};lineage_index={};complete=set()
 def leader(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def found(r):
  ids=set(raster_index.get(r['raster'],()))
  for k in r['keys']:ids.update(key_index.get(k,()))
  for root in r['roots']:ids.update(lineage_index.get(root,()))
  return sorted(ids)
 def insert(r,credit=False):
  matches=found(r);i=len(records);records.append(r);parent.append(i)
  for j in matches:parent[leader(j)]=i
  for k in r['keys']:key_index.setdefault(k,[]).append(i)
  raster_index.setdefault(r['raster'],[]).append(i)
  for root in r['roots']:lineage_index.setdefault(root,[]).append(i)
  if credit:complete.add(i)
 def credits():
  earliest={}
  for i in sorted(complete):earliest.setdefault(leader(i),i)
  return Counter(records[i]['mechanism'] for i in earliest.values())
 for r in inventory['entries']:
  if not r['included']:continue
  g=json.loads(gzip.decompress((rawroot/'references'/r['path']).read_bytes()))['geometry']
  insert(dict(identity=r['identity'],partition='reference',mechanism=r.get('mechanism','historical'),keys=frozenset(map(tuple,r['near_keys'])),raster=raster_key(set(map(tuple,g['free'])),r['width'],r['height']),roots=set(r['roots'])))
 # Completed previous development partitions are references, not fit credits.
 for previous in list(PARTS)[:list(PARTS).index(stage)]:
  review=json.loads((out/f'{previous}_population_review.json').read_bytes());assert review['status']=='PASS'
  for path in sorted((rawroot/previous/'records').glob('*.json.gz')):
   v=json.loads(gzip.decompress(path.read_bytes()))['payload']
   if v['outcome'] not in ('independent','same_partition_related'):continue
   g=v['geometry'];insert(dict(identity=v['identity'],partition='reference',mechanism=v['mechanism'],keys=frozenset(map(tuple,v['topology']['keys'])),raster=raster_key(set(map(tuple,g['free'])),25,25),roots=set(v['roots'])))
 store=rawroot/stage;lock=json.loads((store/'run.json').read_bytes());run_id=sha(canon(lock));bodies=[];files=[]
 for path in sorted((store/'records').glob('*.json.gz')):
  data=path.read_bytes();body=json.loads(gzip.decompress(data));v=body['payload']
  assert body['run_id']==run_id and body['payload_sha256']==sha(canon(v)) and body['identity']==v['identity']
  assert path.name==sha(v['identity'].encode())+'.json.gz'
  bodies.append(v);files.append(dict(path=str(path.relative_to(rawroot)),sha256=sha(data),bytes=len(data)))
 assert len({v['identity'] for v in bodies})==len(bodies)
 bodies.sort(key=lambda v:v['sequence']);position=0;cursors=Counter();outcomes=Counter();relations=Counter();backend=MonitoredBackend();terminal=False
 try:
  for seq,v in enumerate(bodies):
   assert not terminal and v['sequence']==seq and v['partition']==stage and v['profile']=='production' and v['version']==VERSION
   current=credits()
   while True:
    mechanism=METHODS[position%4];position+=1
    if current[mechanism]<target:break
   index=cursors[mechanism];assert index<10000;cursors[mechanism]+=1;seed=base+METHODS.index(mechanism)*10000+index
   assert v['mechanism']==mechanism and v['index']==index and v['identity']==f'{VERSION}:{stage}:{mechanism}:{seed}'
   outcome=v['outcome'];assert v['reasons'][0]==outcome;outcomes[outcome]+=1
   if outcome in ('BackendFailure','DynamicLimit','implementation_error','integrity_failure'):
    assert v['error'];terminal=True;continue
   for purpose,counter in v['streams'].items():
    fields=(VERSION,str(seed),purpose);framed=b''.join(len(s.encode()).to_bytes(4,'little')+s.encode() for s in fields)
    assert counter['identity']==sha(framed) and counter['words']>=len(counter['bounds'])
   if 'geometry' not in v:assert v['rejection_evidence'];continue
   g=v['geometry'];free=set(map(tuple,g['free']));matrix,detail=quotient(free);t=v['topology']
   assert matrix==t['matrix'] and len(distances(free,min(free)))==len(free)
   assert all(1<=x<=23 and 1<=y<=23 for x,y in free)
   graph=Graph(tuple(map(tuple,matrix)));exact=backend.exact_certificate(graph);keys=backend.near_certificates(graph)
   assert exact==tuple(t['exact']) and keys==frozenset(map(tuple,t['keys']))
   for m in t['measurements']:
    assert m['status']=='certified' and m['profile']==PROFILE and m['hard_memory_enforced'] is False
    assert 0<m['peak_rss_bytes']<=536870912 and m['parent_samples'] and 0<=m['seconds']<=5
    assert all(0<s['rss_bytes']<=536870912 for s in m['parent_samples'])
   r=dict(identity=v['identity'],partition=stage,mechanism=mechanism,keys=keys,raster=raster_key(free,25,25),roots=set(v['roots']))
   matches=found(r)
   expected='cross_partition_or_historical' if any(records[i]['partition']!=stage for i in matches) else 'same_partition_related' if matches else 'independent'
   if outcome=='no_start_goal_pair':
    assert not matches and not any(12<=d<=40 and abs(s[0]-e[0])+abs(s[1]-e[1])>=5 for s in free for e,d in distances(free,s).items());continue
   assert outcome==expected
   if outcome=='cross_partition_or_historical':continue
   if matches:
    relations['related_insertions']+=1;relations['transitive_component_merges']+=max(0,len({leader(i) for i in matches})-1)
   if outcome=='independent':
    w=v['world'];s,e=tuple(w['start']),tuple(w['goal']);assert distances(free,s)[e]==w['distance'] and 12<=w['distance']<=40
    assert len(w['schedules'])==2 and abs(s[0]-e[0])+abs(s[1]-e[1])>=5
    for schedule in w['schedules']:
     assert s not in map(tuple,schedule.get('footprint',[])) and e not in map(tuple,schedule.get('footprint',[]))
     assert schedule['category'] in ('none','addition','removal','swap','moving')
     initial=set(map(tuple,schedule['initial']));final=set(initial)
     for event in schedule['events']:
      c=tuple(event['cell'])
      if event['action']=='remove':final.remove(c)
      else:final.add(c)
     assert e in distances(free-initial,s) and e in distances(free-final,s)
   insert(r,outcome=='independent')
  counts=credits();finished=not terminal and all(counts[m]==target for m in METHODS)
  groups={}
  for i,r in enumerate(records):
   if r['partition']==stage:groups.setdefault(leader(i),[]).append(i)
  components=[]
  for members in groups.values():
   comp=sorted(set(members)&complete)
   if comp:components.append(dict(representative=records[comp[0]]['identity'],mechanism=records[comp[0]]['mechanism'],members=[records[i]['identity'] for i in members]))
  report=dict(status='PASS_SAVED_EVIDENCE',population_complete=finished,partition=stage,attempts=len(bodies),counts=dict(counts),outcomes=dict(outcomes),candidate_counts=dict(cursors),relations=dict(relations),components=components,
    record_inventory_sha256=sha(canon(files)),run_id=run_id,inventory_sha256=seal['inventory_sha256'],native_checks=len(backend.events),registered_candidates_generated=0,terminal=terminal)
  with output.open('xb') as f:f.write(canon(report))
  with (rawroot/f'{stage}_independent_resources.json.gz').open('xb') as f:f.write(gzip.compress(canon(backend.events),mtime=0))
  print(json.dumps({k:v for k,v in report.items() if k!='components'}))
 finally:backend.close()

if __name__=='__main__':main()
