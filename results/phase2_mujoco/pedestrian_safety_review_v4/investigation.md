# Phase 2 pedestrian contact safety review

## Diagnosis

The baseline has two contact episodes. Both replay deterministically against saved episode outcomes and action traces. Detailed evaluator-only frame trajectories, permitted observations, and proxy positions are in [`../pedestrian_contact_diagnosis_v4/contact_episode_diagnosis.json`](../pedestrian_contact_diagnosis_v4/contact_episode_diagnosis.json). Hidden pedestrian positions are explicitly evaluator-only and never supplied to the online policy.

- **R, `phase1.5-v0.4-BPRIME-1:fit:R:80000001`, schedule 1, static, seed 42:** first contact at step 53, G1 cell `[11,4]`, heading east. The pedestrian moved from `[11,5]` into `[11,4]` while G1 held position. At that moment a selected move was blocked by the MuJoCo shield (`rotation_collision`); its attempted pose and the current pose each registered 39 pedestrian contact pairs, so the collision already existed when the shield evaluated the action. The static policy had only its initial observation, with zero pedestrian ray hits and zero visible pedestrian cells. This collision was not foreseeable under the permitted observation schedule.
- **M, `phase1.5-v0.4-BPRIME-1:fit:M:80030007`, schedule 1, periodic, seed 42:** first contact at step 55, G1 cell `[4,12]`, heading south. At step 52 the 3D rays detected the proxy one cell ahead at `[4,11]` (15 pedestrian ray hits), but there was only one observed cluster, so direction was uncertain. Retreat clearance was not observed behind G1; the policy waited and the prescribed proxy entered G1's cell before the next observation. A fully observed lateral escape was available.

The collision shield accounting was valid: only selected non-wait actions were checked, with zero unselected collision queries. At the M contact, the selected action was `wait`, which correctly makes no collision query. Contacts are pose overlaps with the prescribed nonreactive capsule proxy, distinct from blocked-attempt counters.

## Safety change and results

For a close, directly observed pedestrian threat with uncertain motion, the forward-first planner may now take one lateral escape only when the entire swept G1 footprint and destination are observed free, and only if that selected action has not already been rejected. The maneuver uses public footprint bounds and current observations; it uses no hidden occupancy or future positions. The existing oncoming-pedestrian retreat rule remains unchanged.

The focused replay of the M episode used one lateral move at step 52 and then completed successfully with zero pedestrian contacts. It made 60 selected-action shield queries, no unselected queries, and retained valid action accounting.

A matched 288-episode evaluation completed with the same 36 saved worlds, two schedules, four observation policies, seed 42, 80-step horizon, 20-observation budget, and 0.75 m/cell assumption. Goal completions stayed **225/288**; contact-free goal completions improved **224/288 → 225/288**; episodes with pedestrian contacts decreased **2 → 1**. The remaining contact is the R static-policy episode; it cannot be anticipated under its original observation schedule. This is a reduction, not full resolution.

| Measure | Baseline | New | Change |
|---|---:|---:|---:|
| Goal completions | 225 | 225 | 0 |
| Contact-free goal completions | 224 | 225 | +1 |
| Episodes with pedestrian contacts | 2 | 1 | -1 |
| Pedestrian contact pairs | 468 | 234 | -234 |
| Forward actions | 9,670 | 9,669 | -1 |
| Lateral actions | 1 | 2 | +1 |
| Backward actions | 0 | 0 | 0 |
| Turns | 3,964 | 3,964 | 0 |
| Waits | 9 | 5 | -4 |
| Observations / observation cost | 2,317 | 2,314 | -3 |

Selected-action shield checks remained 13,635, with zero unselected queries. Failure reasons were unchanged: 62 `deadline_before_goal`, one `deadline_no_footprint_aware_route`.

The preservation checker reverified all 836 protected Phase 1.5 files. The baseline 288-run artifact manifest validated, and the original episode CSV hash is recorded in the machine-readable report.

## Artifacts

- Baseline case diagnoses and frame-by-frame trajectories: [`../pedestrian_contact_diagnosis_v4/contact_episode_diagnosis.json`](../pedestrian_contact_diagnosis_v4/contact_episode_diagnosis.json)
- Focused M mitigation replay: [`../pedestrian_contact_m_probe_v4/contact_episode_diagnosis.json`](../pedestrian_contact_m_probe_v4/contact_episode_diagnosis.json)
- New matched 288 evaluation: [`../g1_forward_first_shield_turns_v3_pedestrian_avoidance_full_288/`](../g1_forward_first_shield_turns_v3_pedestrian_avoidance_full_288/)
- Aggregate counts and hashes: [`comparison.json`](comparison.json)

No prior experiment output or environment was overwritten.
