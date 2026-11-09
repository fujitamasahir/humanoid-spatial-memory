# Presentation-only moving pedestrian proxy replay

- Replayed saved episode: `phase1.5-v0.4-BPRIME-1:fit:R:80000001`, schedule 1, method `static`.
- The pedestrian is a 0.19 m radius MuJoCo mocap capsule following the stored B-prime schedule; it is not a humanoid model. Its centerline is 1.08 m and total capsule height is 1.46 m.
- The full 288 run did not retain per-frame poses. This trace was reconstructed by deterministic replay; saved episode metrics and all recorded non-move action events matched.
- Presentation wall RGBA: `0.18 0.23 0.30 0.16`. The proxy display alpha is `0.24`; geometry, filters, and G1 are unchanged.
- Presentation-only kinematic replay; no walking controller. Contact in the source episode is intentionally visible and remains reported in the source experiment metrics.
