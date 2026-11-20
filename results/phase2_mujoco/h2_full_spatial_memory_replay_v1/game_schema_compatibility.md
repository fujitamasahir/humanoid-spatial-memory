# H2 replay schema compatibility review

Read-only review of the portfolio game's H2 replay reader. The portfolio repository was not modified.

## Reviewed upstream snapshot

- Repository: `fujitamasahir/fujitamasahir.github.io`
- Branch: `experiment/browser-humanoid-game`
- Commit: `c86476a2fb44e8f399d25e2e2149d81d8e10c5a3`
- `games/beat-the-humanoid/h2/index.json` blob: `b1fd3f0d9efae07bda4403ea6390274de514d067`
- `games/beat-the-humanoid/h2/replay-data.js` blob: `80c5f18536500c23204b94289eb7b4342a33c39c`
- `games/beat-the-humanoid/h2/review.js` blob: `6135b8e5fea45c0c20b02cf68f05d61e38fcfc5e`

## Findings

The game reader's recorded-replay path expects a top-level `row` and `replay` object. It validates `replay.schema_version == "1.0.0"`, `episode_key == [identity, schedule, model_id, seed]`, 25×25 grid, map family, `steps == elapsed_steps + 1`, per-frame position/heading/event/objects/pedestrians, scan counts, contact totals, and final goal state. New recovery episode payloads retain this `row` + `replay` structure and schema version; they also add full before/after memory and controller-state snapshots. H2 unseen-map records therefore fit the episode payload reader's data contract.

The current website index loader is still pinned to `h2_comprehensive_replay_index_v1` with exactly 7,776 entries. The corrected archive is `phase2_combined_replay_index_v3` with 12,528 entries: the original 7,776 prior entries are retained exactly and the 4,752 recovery additions point to the reconciled replay files. It is intentionally not accepted by the current loader. The current local map catalog also contains the 36 unseen H2 maps, not the FIT72 map identities, so FIT72 records need an explicit map-catalog extension before they can be selected in the game. This is a compatibility finding, not a game implementation change.

The viewer's `historicalTrace` path can present old traces without memory only when memory is explicitly null; this recovery does not synthesize memory for those old records. The full-memory episodes are a separate payload type and the new game index/version would need to distinguish them from the legacy archive.
