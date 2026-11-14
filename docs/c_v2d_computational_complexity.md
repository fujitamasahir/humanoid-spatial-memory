# C v2.0d Computational Complexity and Accounting

## Symbols and semantic scope

Let `N = height*width` be total grid cells, `V` the cells traversable under the
frozen unknown-cell mode, `E` the undirected cardinal graph edges, `M` the
cells passing the existing visible-footprint and probability filter, `L` the
nominal A* route length, and `K=3` the fixed C-Topology candidate budget.
Maximum graph degree is four. This audit leaves the v2.0c graph definitions,
structural priority classes, probability model, visibility, V/D, delay regret,
scan price, scarcity price, and observation cap unchanged.

## Complexity of the frozen v2.0c pipeline

The old expression `O(N + V + E + L + M log M)` describes only the
topology-preprocessing part when the nominal route has already been computed:

* grid scan / graph materialization: `O(N + V + E)`;
* iterative Tarjan, bridge components, terminal analysis and two BFS maps:
  `O(V + E)`;
* route set creation and membership: expected `O(L)`;
* fixed-degree candidate features: expected `O(M)`; each candidate considers
  at most four neighbors and at most 16 ordered neighbor pairs;
* full deterministic sort in v2.0c: `O(M log M)`.

It is **not** a bound for the complete EVI call. The sensor visibility
approximation traces up to `R*S` samples (`R=61`; `S` is set by range and the
0.1-cell sampling step). The nominal route is computed by `navigation.plan`,
not supplied for free. For each of up to `K` candidates, two occupancy
counterfactual grids are copied (`O(2*K*N)`) and planned with A*. EVI scores
also test whether each candidate occurs in each counterfactual route, costing
up to `O(K*V)` with Python list membership. The complete expression is thus:

```
O(R*S + A(V) + N + V + E + L + M*F + M log M
  + 2*K*N + 2*K*A(V+1) + K*V)
```

where `F` is constant because grid degree is four and `A(V)` denotes the
actual frozen A* implementation. For that implementation, integer path costs
range from 0 to at most V-1. Each strict improvement inserts a new heap item;
in the conservative worst case each of V nodes can improve at most V times.
At most `O(V^2)` entries are pushed/popped, each with heap cost `O(log V)`,
so a safe (loose) bound is `A(V)=O(V^2 log(V+1))`. The implementation does not
discard stale heap entries. Typical measured A* work can be much lower; that
does not justify replacing this bound with a linear claim. At most seven A*
calls remain: one nominal call plus two per each of three candidates.

## C v2.0d bounded selection

V2.0d computes the same structural feature and the same exact lexicographic
key as v2.0c:

```
(class, -severity, -distance_gain, -q*(1-q), y, x)
```

A fixed-size max-priority view over a binary min-heap retains the best K keys.
The root is the worst retained item; each new candidate is compared with it
and replaces it only if its key is smaller. The retained K items are ordered
by deterministic insertion sort, requiring at most `K*(K-1)/2` comparisons.
The selection stage is `O(M log(K+1) + K^2)` and for fixed K=3 is O(M).
All M candidates still receive one feature computation. The implementation
does not full-sort in its online path. Full sorting remains in v2.0c as an
offline equivalence oracle.

## Stage-separated loop bounds

The instrument reports a vector of named stage counts and bounds; unlike the
rejected `20*(V+E)` scalar, these unlike events are not added into a synthetic
“work unit.” The bounds come from explicit loops and graph degree:

| Stage | Counted event | Derived upper bound |
| --- | --- | ---: |
| Grid scan | grid-cell reads | N |
| Vertex collection | accepted open-cell records | V |
| Adjacency build | directional neighbor slots | 4V |
| Adjacency build | directed adjacency records | 2E |
| Tarjan | vertex enter/exit events | 2V |
| Tarjan | directed adjacency inspections | 2E |
| Tarjan blocks | edge stack pushes/pops; block edge visits | E each |
| Tarjan blocks | endpoint visits for cycle identification | 2E |
| Bridge components | vertex visits / directed edge inspections | V / 2E |
| Bridge forest | bridge records / tree adjacency inspections / path recovery | B / 2B / B, B≤E |
| Terminal separator | articulation checks / DFS-child checks | A / V-C, A≤V |
| Terminal BFS | vertex visits / directed edge inspections, two BFS | 2V / 4E |
| Candidate feature | feature evaluations, key builds | M each |
| Candidate feature | neighbor slots / neighbor membership checks | 4M each |
| Candidate feature | ordered connectivity pairs / distance pairs | 16M each |
| Candidate feature | route membership checks | 2M |
| Top-K | rank-key comparisons | implementation formula below |
| Route/A* | route-set insertions / calls | L / 1+2K |
| Counterfactual preparation | copied grid-cell reads | 2KN |

For top-K with `m=M`, `k=min(K,M)`, and `d=ceil(log2(max(2,K)))`, the
instrumented bound is `k*d + (m-k)*(1+2*d) + k*(k-1)/2`. It covers heap
insertions, one root comparison for each later candidate, at most two
comparisons per sift-down level for each replacement, and the bounded final
insertion order. The counter reports total rank-key comparisons, heap
comparisons (including root screening), and final-prefix ordering comparisons
separately. The heap comparison limit is `k*d + (m-k)*(1+2*d)`; the prefix
limit is `k*(k-1)/2`; their sum is the total limit. Heap swaps and replacements
are not rank-key comparisons.

Stage event units are literal loop visits, neighbor slots, edge records,
pair comparisons, rank-key comparisons, route entries, grid-cell copies, and
A* calls. They are reported separately and never summed across categories.
Hash-table dictionary/set operations are expected O(1) for these fixed integer
coordinate keys; theoretical worst-case hash collision behavior is not
represented by loop-count bounds. Wall-clock measurements are a separate
resource metric.

## Runtime benchmark protocol

The reference-scale latency criterion applies only to 17x17 public maps:
10 unrecorded warm-up calls and 100 measured calls per reference-scale map,
with graph analysis and feature/ranking work timed together using
`perf_counter_ns`. Aggregate p95 must be at most 5 ms on the recorded host.
No 5 ms criterion is applied to larger maps. The formal suite separately
records median, p95 and maximum for each N/V/E size band and candidate-count
band, and a dense 128x128 stress benchmark. These are scaling observations,
not independent pass thresholds. Scheduler timing, nominal A* time, and each
counterfactual A* time are reported separately from graph timing.
