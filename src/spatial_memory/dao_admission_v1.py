"""Bounded structural duplicate checks and append-only TEST audit infrastructure."""
import hashlib,hmac,json,itertools,math,os
from pathlib import Path
from collections import Counter
import numpy as np


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def stream_seed(master,namespace,lineage,stream):
    if namespace!='TEST' or not isinstance(master,bytes) or len(master)<16:
        raise PermissionError('Only explicit TEST streams are enabled; production custody is not established')
    return int.from_bytes(hmac.new(master,f'dao-nav-v1|{namespace}|{lineage}|{stream}'.encode(),hashlib.sha256).digest(),'big')


def orientations(grid):
    a=np.asarray(grid)
    for k in range(4):
        b=np.rot90(a,k)
        yield b
        yield np.fliplr(b)


def crop(a):
    ys,xs=np.where(a!=0)
    return a[ys.min():ys.max()+1,xs.min():xs.max()+1] if len(xs) else np.zeros((1,1),dtype=a.dtype)


def occupancy_hash(grid):
    a=np.asarray(grid,dtype=np.int8)
    if a.ndim!=2 or not np.isin(a,[0,1]).all():raise ValueError('Binary occupancy required')
    return hashlib.sha256(min(canonical(crop(b).tolist()) for b in orientations(a))).hexdigest()


def endpoint_hash(grid,start,goal):
    a=np.asarray(grid,dtype=np.int8).copy()
    for point,value in ((start,2),(goal,3)):
        x,y=point
        if not(0<=y<a.shape[0] and 0<=x<a.shape[1]) or a[y,x]!=0:raise ValueError('Free distinct endpoints required')
        a[y,x]=value
    return hashlib.sha256(min(canonical(crop(b).tolist()) for b in orientations(a))).hexdigest()


def corridor_graph(grid):
    a=np.asarray(grid);h,w=a.shape
    free={(x,y) for y in range(h) for x in range(w) if a[y,x]==0}
    adj={p:sorted(q for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)) if (q:=(p[0]+dx,p[1]+dy)) in free) for p in free}
    vertices={p for p in free if len(adj[p])!=2};remaining=set(free)
    # Each disconnected degree-two cycle needs its own representative.
    while remaining:
        first=min(remaining);stack=[first];component=set()
        while stack:
            p=stack.pop()
            if p in component:continue
            component.add(p);stack.extend(adj[p])
        if not(component&vertices):vertices.add(min(component))
        remaining-=component
    nodes=sorted(vertices);ids={p:i for i,p in enumerate(nodes)};edges=[];visited=set()
    for p in nodes:
        for q in adj[p]:
            edge=frozenset((p,q))
            if edge in visited:continue
            visited.add(edge);path=[p,q];previous=p;current=q
            while current not in vertices:
                nxt=next(v for v in adj[current] if v!=previous)
                visited.add(frozenset((current,nxt)));path.append(nxt);previous,current=current,nxt
            edges.append([ids[p],ids[current],[len(path)-1,sorted(len(adj[v]) for v in path[1:-1])]])
    return {'nodes':[[len(adj[p])] for p in nodes],'edges':edges}


def graph_signature(graph):
    labels=[digest(v) for v in graph['nodes']]
    for _ in range(4):
        neighbors=[[] for _ in labels]
        for a,b,label in graph['edges']:
            neighbors[a].append((digest(label),labels[b]));neighbors[b].append((digest(label),labels[a]))
        labels=[digest([old,sorted(n)]) for old,n in zip(labels,neighbors)]
    return digest([sorted(labels),len(graph['edges'])])


def edge_table(g):
    d={}
    for a,b,label in g['edges']:d.setdefault(tuple(sorted((a,b))),Counter())[canonical(label)]+=1
    return d


def exact_isomorphic(a,b,budget=20000):
    if len(a['nodes'])!=len(b['nodes']) or len(a['edges'])!=len(b['edges']):return {'match':False,'work':0}
    if graph_signature(a)!=graph_signature(b):return {'match':False,'work':0}
    n=len(a['nodes'])
    if n>200:return {'match':None,'work':0,'reason':'node_bound'}
    ea,eb=edge_table(a),edge_table(b);mapping={};used=set();work=0;exhausted=False
    order=sorted(range(n),key=lambda i:(sum(v==a['nodes'][i] for v in a['nodes']),-sum(i in (x,y) for x,y in ea),i))
    def search(k):
        nonlocal work,exhausted
        if k==n:return True
        i=order[k]
        for j in range(n):
            if work>=budget:exhausted=True;return False
            work+=1
            if j in used or a['nodes'][i]!=b['nodes'][j] or ea.get((i,i),Counter())!=eb.get((j,j),Counter()):continue
            if any(ea.get(tuple(sorted((i,x))),Counter())!=eb.get(tuple(sorted((j,y))),Counter()) for x,y in mapping.items()):continue
            mapping[i]=j;used.add(j)
            if search(k+1):return True
            used.remove(j);mapping.pop(i)
        return False
    match=search(0)
    return {'match':True if match else None if exhausted else False,'work':min(work,budget),'reason':'budget' if exhausted else None}


def graph_edit(a,b,budget=20000):
    """Exact node-substitution/edge insert-delete distance only on small equal orders."""
    n=len(a['nodes']);den=max(1,n+max(len(a['edges']),len(b['edges'])))
    if n!=len(b['nodes']) or n>8:return {'distance':None,'reason':'bounded_unresolved'}
    target=edge_table(b);best=math.inf
    for work,perm in enumerate(itertools.permutations(range(n)),1):
        if work>budget:return {'distance':None,'best_upper':best/den if math.isfinite(best) else None,'reason':'budget'}
        mapped={}
        for x,y,label in a['edges']:mapped.setdefault(tuple(sorted((perm[x],perm[y]))),Counter())[canonical(label)]+=1
        cost=sum(a['nodes'][i]!=b['nodes'][perm[i]] for i in range(n))
        for key in mapped.keys()|target.keys():
            x=mapped.get(key,Counter());y=target.get(key,Counter());cost+=sum((x-y).values())+sum((y-x).values())
        best=min(best,cost)
        if best==0:break
    return {'distance':best/den,'work':work}


def near_occupancy(a,b):
    a=crop(np.asarray(a));best=1.
    for orient in orientations(b):
        v=crop(orient)
        if v.shape!=a.shape:continue
        union=np.count_nonzero((a!=0)|(v!=0));intersection=np.count_nonzero((a!=0)&(v!=0))
        best=min(best,1-intersection/union if union else 0.)
    return best


def admission(candidate,previous,*,prior_opaque_signatures=None,budget=20000):
    grid=candidate['occupancy'];graph=corridor_graph(grid);identity=occupancy_hash(grid)
    for other in previous:
        if occupancy_hash(other['occupancy'])==identity:return {'status':'STRUCTURAL_DUPLICATE','endpoint_independent':True}
        iso=exact_isomorphic(graph,corridor_graph(other['occupancy']),budget)
        if iso['match'] is True:return {'status':'GRAPH_DUPLICATE'}
        if iso['match'] is None:return {'status':'QUARANTINE','reason':'isomorphism_unresolved'}
        if candidate['family']==other['family'] and np.shape(grid)==np.shape(other['occupancy']):
            if near_occupancy(grid,other['occupancy'])<=.05:return {'status':'NEAR_DUPLICATE','metric':'occupancy'}
            edit=graph_edit(graph,corridor_graph(other['occupancy']),budget)
            if edit['distance'] is None:return {'status':'QUARANTINE','reason':'graph_edit_unresolved'}
            if edit['distance']<=.1:return {'status':'NEAR_DUPLICATE','metric':'graph_edit'}
    if prior_opaque_signatures is None:return {'status':'INCOMPLETE','reason':'no_authorized_prior_opaque_signatures'}
    if identity in prior_opaque_signatures:return {'status':'PRIOR_DUPLICATE'}
    return {'status':'TEST_UNIQUE','production_admission_authorized':False}


class ImmutableLog:
    def __init__(self,path):self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
    def read(self):
        entries=[];previous=None
        for index,p in enumerate(sorted(self.path.glob('*.json'))):
            body=json.loads(p.read_text());assert p.name==f'{index:06}.json' and body['previous']==previous
            assert body['digest']==digest({k:v for k,v in body.items() if k!='digest'})
            previous=body['digest'];entries.append(body)
        return entries
    def append(self,event):
        prior=self.read();body={'sequence':len(prior),'previous':prior[-1]['digest'] if prior else None,'event':event}
        body['digest']=digest(body)
        with (self.path/f'{len(prior):06}.json').open('x') as f:f.write(canonical(body).decode()+'\n');f.flush();os.fsync(f.fileno())
        return body['digest']


def inventory_commitment(records,salt):
    if not isinstance(salt,bytes) or len(salt)<16:raise ValueError('At least128-bit salt')
    keys=[r['lineage_id'] for r in records]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate inventory lineage')
    entries=sorted((r['lineage_id'],digest(r)) for r in records)
    return hashlib.sha256(salt+canonical(entries)).hexdigest()


def admit_test_logged(candidate,previous,log_directory,**kwargs):
    if candidate.get('partition')!='TEST':raise PermissionError('Production admission disabled')
    decision=admission(candidate,previous,**kwargs)
    ImmutableLog(Path(log_directory)/'admission').append({'event':'TEST_admission_check',
        'lineage_id':candidate['lineage_id'],'payload_digest':digest(candidate),'decision':decision})
    return decision
