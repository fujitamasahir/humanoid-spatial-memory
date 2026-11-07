"""Independent stored-evidence verifier. No production loader/index/generator calls.
Raster quotient/union reconstruction is independent of production routines.
"""
import argparse
from collections import Counter,deque
import gzip,hashlib,json
from pathlib import Path
from spatial_memory.phase15_macos_monitored import MonitoredBackend,PROFILE
from spatial_memory.phase15_topology import Graph

def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def neighbors(c):
 x,y=c;return ((x,y-1),(x+1,y),(x,y+1),(x-1,y))
def components(cells):
 pending=set(cells);groups=[]
 while pending:
  start=min(pending,key=lambda c:(c[1],c[0]));group={start};queue=deque([start]);pending.remove(start)
  while queue:
   for n in neighbors(queue.popleft()):
    if n in pending:pending.remove(n);group.add(n);queue.append(n)
  groups.append(group)
 return groups

def quotient(free):
 marked=set()
 for x,y in free:
  square={(x,y),(x+1,y),(x,y+1),(x+1,y+1)}
  if square<=free:marked|=square
 rooms=components(marked);nodes=rooms+[{c} for c in free-marked]
 nodes.sort(key=lambda group:min((y,x) for x,y in group));owner={c:i for i,g in enumerate(nodes) for c in g}
 adj={i:{} for i in range(len(nodes))}
 for c,u in owner.items():
  for n in neighbors(c):
   v=owner.get(n)
   if v is not None and u!=v:adj[u][v]=1
 while True:
  choices=[u for u in sorted(adj) if sum(adj[u].values())+adj[u].get(u,0)==2 and adj[u].get(u,0)!=1]
  if not choices:break
  u=choices[0];ends=[v for v in adj[u] if v!=u]
  if len(ends)==1:
   v=ends[0];del adj[v][u];adj[v][v]=adj[v].get(v,0)+1
  else:
   assert len(ends)==2;v,w=ends;del adj[v][u];del adj[w][u]
   adj[v][w]=adj[v].get(w,0)+1;adj[w][v]=adj[w].get(v,0)+1
  del adj[u]
 ids=sorted(adj);matrix=[[adj[u].get(v,0) for v in ids] for u in ids]
 return matrix,dict(free_cells=len(free),marked_cells=len(marked),room_regions=len(rooms),quotient_vertices=len(nodes),normalized_vertices=len(ids))

def raster_key(free,w,h):
 choices=[]
 for transpose in (False,True):
  cells={(y,x) if transpose else (x,y) for x,y in free};a,b=(h,w) if transpose else (w,h)
  for fx in (False,True):
   for fy in (False,True):
    changed={(a-1-x if fx else x,b-1-y if fy else y) for x,y in cells}
    choices.append((a,b,''.join('1' if (x,y) in changed else '0' for y in range(b) for x in range(a))))
 return min(choices)


def literal_matrix(key):
 n=key[0];a=[[0]*n for _ in range(n)];p=1
 for i in range(n):a[i][i]=key[p];p+=1
 for i in range(n):
  for j in range(i+1,n):a[i][j]=a[j][i]=key[p];p+=1
 assert p==len(key)
 return a


def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
 a=p.parse_args();base=a.evidence;root=a.inventory;repo=Path(__file__).resolve().parents[1]
 assert not a.report.exists()
 inv=json.loads((root/'inventory.json').read_bytes());ledger=json.loads((root/'ledger.json').read_bytes())
 old=json.loads((base/'derived-review/reference-inventory.PROVISIONAL.json').read_bytes());original={r['identity']:r for r in old['entries']}
 assert len(original)==4644 and sha(canon(ledger))==inv['ledger_sha256']
 assert Counter(r['category'] for r in inv['entries'])==dict(original_history=110,admitted_development=2258,rejected_valid=2276)
 assert sum(r['included'] for r in inv['entries'])==2368
 table={};files=[];backend=MonitoredBackend();native_checks=0;newhistory={}
 try:
  for row in inv['entries']:
   identity=row['identity'];prior=original[identity];raw=(root/row['path']).read_bytes();body=json.loads(gzip.decompress(raw));g=body['geometry']
   assert sha(raw)==row['sha256'] and len(raw)==row['bytes']
   for k in ('category','included','roots','aliases','matrix','exact','width','height'):assert row[k]==prior[k],(identity,k)
   assert ledger[identity]=={k:row[k] for k in ('outcome','sha256','bytes','roots','aliases','source_commit','source_path','interpretation')}
   free=set(map(tuple,g['free']));m,d=quotient(free);assert m==row['matrix']==body['matrix']
   if row['category']=='original_history':
    stored=(base/prior['path']).read_bytes();assert sha(stored)==identity and json.loads(stored)==g
    graph=Graph(tuple(map(tuple,m)));exact=backend.exact_certificate(graph);keys=backend.near_certificates(graph)
    # Independent enumeration retained from the literal reference, then encode
    # each class with C3. This does not reuse the C3 near-enumeration code.
    literal_keys={backend.exact_certificate(Graph(tuple(map(tuple,literal_matrix(k))))) for k in prior['independent_literal_near_keys']}
    assert keys==literal_keys==set(map(tuple,row['near_keys'])) and exact==tuple(row['exact'])
    native_checks+=1;newhistory[identity]=keys
   else:
    assert raw==(base/prior['path']).read_bytes()
    assert row['near_keys']==prior['near_keys']==body['near_certificates']
    assert identity==f"{g['partition']}:{g['mechanism']}:{g['seed']}" and row['roots']==[g['lineage']]
   files.append(dict(path=row['path'],sha256=sha(raw),bytes=len(raw)))
   table[identity]=dict(row,free=free,raster=raster_key(free,row['width'],row['height']))
  # Independently replay the saved admission *records*, never constructors.
  candidate=repo/'results/phase1_5b02/candidate_inventory.jsonl.gz'
  assert sha(candidate.read_bytes())=='4281101d7d1631742f2c59b14b6b1af27409a03e8e07fc648f4a587a040473f6'
  events=[json.loads(l) for l in gzip.decompress(candidate.read_bytes()).splitlines()]
  assert len(events)==19279==len({e['identity'] for e in events})
  records=[];parent=[];ki={};ri={};li={}
  def leader(i):
   while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
   return i
  def matches(row):
   found=set(ri.get(row['raster'],()))
   for r in row['roots']:found.update(li.get(r,()))
   for k in row['near_keys']:found.update(ki.get(tuple(k),()))
   return sorted(found)
  def insert(row):
   found=matches(row);i=len(records);records.append(row);parent.append(i)
   for j in found:parent[leader(j)]=i
   for k in row['near_keys']:ki.setdefault(tuple(k),[]).append(i)
   ri.setdefault(row['raster'],[]).append(i)
   for r in row['roots']:li.setdefault(r,[]).append(i)
  for identity in [r['identity'] for r in json.loads((repo/'results/phase1_5b02/historical_topology.json').read_bytes())]:insert(table[identity])
  for e in events:
   cp=base/'raw/phase1_5b02_development/checkpoints'/(e['identity'].replace(':','_')+'.json')
   assert json.loads(cp.read_bytes())==e
   if e['identity'] not in table:continue
   row=table[e['identity']];found=matches(row);assert row['outcome']==e['outcome']
   if e['outcome']=='independent':assert not found
   else:
    assert e['matches']==[records[i]['identity'] for i in found]
    assert any(records[i]['category']=='original_history' for i in found)==(e['outcome']=='cross_partition_or_historical')
    if e['outcome']=='same_partition_related':
     assert e['exact_matches']==sum(records[i]['exact']==row['exact'] for i in found)
     assert e['merged_components']==len({leader(i) for i in found})
   if row['included']:insert(row)
  groups={}
  for i,r in enumerate(records):
   if r['category']=='admitted_development':groups.setdefault(leader(i),[]).append(r['identity'])
  expected=json.loads((repo/'results/phase1_5b02/development_manifest.json').read_bytes())
  assert {frozenset(m) for m in groups.values()}=={frozenset(r['cluster_members']) for r in expected['records']}
  assert len(groups)==38
  bgroups=sorted(len(m) for m in groups.values() if any(table[i].get('mechanism')=='B' for i in m));assert bgroups==[529,1687]
  completion=json.loads((root/'historical-completion.json').read_bytes());assert len(completion['records'])==65
  report=dict(status='PASS_INDEPENDENT_RECONSTRUCTION_NOT_YET_SEALED',inventory_sha256=sha(canon(inv)),ledger_sha256=sha(canon(ledger)),
   included_identities=2368,original_history=110,admitted_development=2258,rejected_nonreferences=2276,completed_history=65,
   checkpoint_records=19279,geometry_archives=4534,historical_native_checks=native_checks,
   b02_final_components=38,B_component_sizes=bgroups,resource_profile=PROFILE,backend_pin_sha256=backend.pin_sha,
   unique_included_geometries=len({r['raster'] for r in table.values() if r['included']}),
   unique_included_topologies=len({tuple(r['exact']) for r in table.values() if r['included']}),
   files_sha256=sha(canon(sorted(files,key=lambda f:f['path']))),verifier_sha256=sha(Path(__file__).read_bytes()),
   scientific_generators_executed=0,resource_calls=len(backend.events))
  with a.report.open('xb') as f:f.write(canon(report))
  with a.report.with_suffix('.resource-events.json').open('xb') as f:f.write(canon(backend.events))
  print(json.dumps(report))
 finally:backend.close()

if __name__=='__main__':main()
