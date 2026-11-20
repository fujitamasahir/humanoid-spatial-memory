# dao-nav-v1 generator/admission implementation and resolved design choices

This is TEST-only engineering code, not production cohort approval. Existing
proposals remain preserved. `dao_generator_v1.py` implements explicitTEST seeds;
`generate_population` always raises PermissionError. Likewise stream derivation
and logging admission reject production namespaces. An owner-approved separate
custodian implementation is required before extending these paths. No master
for production partitions is created here.

## Deterministic construction

Each TEST seed/family/dimension tuple derives independent layout, objects,
persistent, start_goal, pedestrian_geometry, phase0 and phase1 RNGs with
HMAC-SHA256 over a versioned namespace. NumPy version is pinned. ExplicitTEST
master/salt are PUBLIC test constants and confer no independent access control.
Production must use independent secret partition masters and source commitments.

Dimensions independently support25/33/41, cell0.75m. Nodes are Cartesian lattice
centers4,12,20,… below dimension-3, spacing8. Spanning construction is breadth-
first for frequent-revisit stratum and depth-first for rare-revisit stratum;
these are structural treatments, not measured robot revisit rates. Tree uses
only spanning edges. Loop adds ceil(p*available_non_tree_edges), at least1,
p uniform.1–.3. Rooms/mixed add ceil(p*eligible_edges), p uniform0–.2. Edges carve
axis-aligned centerline rectangles, integer width drawn uniformly1/2/3 per
attempt; even width paints floor((w-1)/2) cells below and floor(w/2) above center.
All boundary cells remain occupied. Room sides uniformly4/5/6, a deliberate
resolution of the prior4–8 proposal to prevent accidental merging on spacing8;
this narrower distribution still requires owner approval. Mixed additionally
carves a centered rectangle of ceil(p*(W-2)*(H-2)) target area, p uniform.2–.4,
width ceil(sqrt(area)), height ceil(area/width), clipped to interior dimensions.
Construction abstract edges and actual raster descriptors are both retained;
raster loops/room adjacency can differ from the abstract tree/loop graph.

Certificate cells require an entirely free3x3 neighborhood. This is a deliberately
conservative sufficient condition for original G1 extents and in-place turns,
not the point-grid optimistic plan nor a claim of necessary traversability.
Start candidates are a deterministic random permutation of those cells, first24;
choose goal uniformly among conservative-BFS distances12–60; actual certificate
path is stored. At most100 attempts; failed attempts/quarantine are reported.
This acceptance tends to favor wider corridors and MUST be measured in pilot
coverage; it cannot be advertised as an unbiased width1/2/3 admitted distribution.
Start heading is uniform four cardinals in payload; future population runner
must explicitly initialize it (the current hand-scene evaluator starts east).

The occluded-discovery treatment places one3x3 island off a reserved certificate
if space exists; long treatment leaves geometry unchanged. Realized opening,
island availability and visibility must be audited, not assumed successful.
Reserve the certificate's3x3 neighborhood for static/dynamic G1 clearance.
Up to3 movable cells are placed uniformly off that reserve, never walls. Persistent
condition unchanged/add/remove/relocate is uniform unless explicitly supplied
in TEST;1–3 events at independently uniform integer steps10–50, through80.
Additions target distinct unoccupied movable positions; removals target initial
objects; relocations pair them. Validate certificate at base and EVERY event.
Keeping one reserved clear route is a generator bias, documented prospectively;
alternative routes can change but guaranteed connectivity must not depend on
candidate policy success.

Pedestrian category is explicit or TEST seed modulo3: none/static/moving.
The pilot's per-family six lineages would assign two to each category, resolving
prior contradictory uniform-count/category language. None has0 people; static/
moving has uniformly1–2. Geometry paths use free cells outside initial objects,
all addition destinations and start, with cardinal-BFS out-and-back paths to a
Manhattan2–5 endpoint. Static holds one cell. Moving repeats cells to approximate
speeds.25/.5/.75 cells/step; .75 repeats every third path cell twice. Actual
cyclic speed depends on cycle length and is recorded/should be audited.
Each phase stream independently rotates the SAME path geometry for its schedule;
identical sampled phases are legitimate correlated conditions. These are discrete
kinematic proxies, not continuous pedestrian dynamics. Pause0–3 encoded by cell
repetition; all cyclic steps must wait or move one cardinal cell. No policy
position triggers an event. This exact implementation differs from the earlier
suggested4–12 waypoints and must be approved before production use.

## Schema validation and admission

Payload includes TEST lineage namespace/seed commitment, dimensions/family,
occupancy, start/goal/heading, objects/events, two schedules, treatment metadata,
construction, certificate and occupancy/endpoint hashes. Schema validates
binary maps, boundaries, cardinal cyclic pedestrian paths, object/wall conflicts,
certificate continuity/endpoints/length, and conservative clearance through all
event maps. It does not certify controller efficacy or actual pedestrian occlusion.
Production payload provenance must additionally bind generator/admission commits
and a custodian signature; TEST payloads deliberately have production_ready=false.

Occupancy-only canonicalization crops empty exterior padding and enumerates8
rotations/reflections, preserving true boundary walls. Endpoint hash marks
start/goal separately before the same transform normalization. Occupancy hash
therefore catches rotated/reflected/translated structural copies even if start/
goal move; endpoint hash cannot conceal a structural match.

Corridor graph compresses degree2 free-cell chains, preserving lengths and
local degree profiles. Every disconnected all-degree2 cycle gets a representative
self-loop. Dense room rasters retain many junction nodes, a scalability limit.
Four-round WL label hash is a PREFILTER only. Exact labeled multigraph backtracking
checks node labels, loops and edge-label multiplicities, with node bound200 and
work budget20000. A WL collision is not automatically an isomorphism: tests use
one6-cycle versus two triangles. Unresolved => quarantine, never unique.

Near occupancy distance is minimum occupied/free Jaccard distance over8 orientations
with cropped matching shapes, proposed threshold.05. Graph edit uses exact small
(equal-order <=8-node) permutations with node substitution and edge insert/delete
cost, normalized by nodes+max edges, threshold.10. Larger/different-order/budget-
exhausted cases are explicitly unresolved and quarantine. This is conservative
but may quarantine many realistic dense maps: production admission/scalability
is NOT complete, and prior authorized opaque signatures are unavailable here.
No protected/reserved world is opened to fill that gap. Exact duplicates are
rejected before unresolved near-matching, independently of endpoints.

Generation intent/completion and admission decisions use exclusive numbered JSON
log entries, previous-entry digest and fsync. Existing entries cannot be overwritten
by the API; verify sequence/digest chain on read. File permissions/admin tampering
are outside that API; a hash chain or inventory commitment is NOT access control.
Inventory commitment sorts lineage/payload hashes under a supplied salt; tests
check order invariance, seed separation and tamper detection. Production needs
single-writer service ownership, protected signing keys, separate machines or OS
accounts and enforced ACLs, signed read logs and atomic runner admission.

## Practical custody workflow (design only)

Owner appoints an independent custodian account with a private sealed directory,
no read permission for policy authors and a distinct secret master. The custodian
reviews/executes the approved generator and admission commit, receives authorized
opaque FIT/prior signatures through an approved channel, and signs partition
inventories. Authors see schema and signed coverage/inventory commitments only.
A fixed-source gated job accepts frozen container/source/config hashes; custodian
checks signatures and complete comparison matrix, executes all arms, and exports
only approved aggregated diagnostics until the final analysis is committed.
Read logs and immutable full trajectories remain custodian-controlled; unseal
only after all comparisons finish. No such independent account/ACL/key workflow
was established here. Production generation/admission remains disabled and
requires those mechanisms plus the explicit approvals in the pilot protocol.
