"""Read-only Phase 2 RDAO 61-ray visibility feasibility audit.

Compares the ORIGINAL public-map predicted_cell_visibility with an EXPERIMENTAL
cell-footprint angle/range gate, using ONLY stored naturally authorized memory
observations from the 72 frozen FIT episodes.

At each naturally granted observation the label is: "was this previously UNKNOWN
cell actually measured by the 61-ray sensor at this pose?". Both predictors
are evaluated on the SAME candidate cells. No ungranted sensor measurements,
hidden world occupancy, held-out worlds, new MuJoCo runs, policy modifications,
or outcome-guided threshold tuning are used.

This is a geometry feasibility diagnostic, NOT a calibrated probabilistic
predictor or a deployable observation/action policy.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spatial_memory.rdao import (RDAOParameters, predicted_cell_visibility,
                                 route_positions)
from spatial_memory.observation import line_cells

PRIMARY = ROOT / "results/phase2_mujoco/rdao_v1_phase2_evaluation"
DEFAULT_OUT = ROOT / "results/phase2_mujoco/rdao_v1_visibility_extent_audit_v1"
HORIZON = 80
RAY_COUNT = 61
CELL_M = .75
RANGE_M = 6.0
FOV_DEG = 120.0
UNKNOWN_OPEN = RDAOParameters().unknown_blocker_open_probability
HALF_DIAGONAL_CELLS = math.sqrt(2) / 2


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


def footprint_envelope(position, yaw, cell, *, cell_size_m=CELL_M,
                       range_m=RANGE_M, fov_deg=FOV_DEG):
    """Conservative circular upper bound on the cell's area, not cell-center.

    This bound does not guarantee that a real discrete MuJoCo ray hits a cell.
    It just avoids prematurely discarding cells whose center falls outside
    the range or FOV but whose footprint might overlap them.
    """
    dx, dy = cell[0] - position[0], cell[1] - position[1]
    dist = math.hypot(dx, dy) * cell_size_m
    if dist <= 1e-12:
        return False
    radius = cell_size_m * HALF_DIAGONAL_CELLS
    if dist - radius > range_m:
        return False
    angular_radius = math.atan2(radius, max(dist, cell_size_m * .25))
    rel = wrap(math.atan2(dy, dx) - yaw)
    return abs(rel) <= math.radians(fov_deg) / 2 + angular_radius


def footprint_visibility(grid, position, yaw, cell, *, cell_size_m=CELL_M,
                         range_m=RANGE_M, fov_deg=FOV_DEG,
                         ray_count=RAY_COUNT, unknown_open=UNKNOWN_OPEN):
    """EXPERIMENTAL footprint gate with legacy remembered-center blockers.

    Same public-map occlusion attenuation as the original, but angular and
    radial bounds use the cell's half-diagonal. This is not a ray-box
    intersection oracle or proof of physical line-of-sight.
    """
    cx, cy = map(int, cell)
    if not (0 <= cy < grid.shape[0] and 0 <= cx < grid.shape[1]):
        return 0.0
    if not footprint_envelope(position, yaw, cell, cell_size_m=cell_size_m,
                              range_m=range_m, fov_deg=fov_deg):
        return 0.0
    dx, dy = cx - position[0], cy - position[1]
    center_angle = wrap(math.atan2(dy, dx) - yaw)
    half_fov = math.radians(fov_deg) / 2
    ray_step = 2 * half_fov / max(1, ray_count - 1)
    nearest = max(0, min(ray_count - 1, round(
        (center_angle + half_fov) / ray_step)))
    nearest_angle = -half_fov + nearest * ray_step
    dist = math.hypot(dx, dy) * cell_size_m
    extent = math.atan2(cell_size_m * HALF_DIAGONAL_CELLS,
                        max(dist, cell_size_m * .25))
    if abs(center_angle - nearest_angle) > extent + ray_step / 2:
        return 0.0
    confidence = 1.0
    origin = tuple(map(int, position))
    for bx, by in line_cells(origin, (cx, cy)):
        if (bx, by) == origin or (bx, by) == (cx, cy):
            continue
        if not (0 <= by < grid.shape[0] and 0 <= bx < grid.shape[1]):
            return 0.0
        state = int(grid[by, bx])
        if state == 1:
            return 0.0
        if state == -1:
            confidence *= unknown_open
    return float(confidence)


def empty_confusion():
    return {"tp": 0, "fp": 0, "fn": 0, "tn": 0}


def add_confusion(c, truth, positive):
    c["tp" if truth else "fp"] += int(positive and truth or positive and not truth)
    c["fn" if truth else "tn"] += int(not positive and truth or not positive and not truth)


def quality(c):
    tp, fp, fn, tn = (int(c[k]) for k in ("tp", "fp", "fn", "tn"))
    div = lambda a, b: a / b if b else None
    return {
        **{k: int(v) for k, v in c.items()},
        "actual_visible": tp + fn,
        "predicted_visible": tp + fp,
        "precision": div(tp, tp + fp),
        "recall": div(tp, tp + fn),
        "false_positive_rate": div(fp, fp + tn),
        "specificity": div(tn, tn + fp),
    }


def maybe_route_near(cell, positions):
    return any(abs(cell[0] - x) + abs(cell[1] - y) <= 1
               for x, y in positions)


def frame_samples(frame, *, cell_size=CELL_M, range_m=RANGE_M,
                  fov_deg=FOV_DEG, ray_count=RAY_COUNT):
    """Return only candidate, known-negative and actually-measured labels.

    Saves no label in predictor inputs. Verifies the exact saved observation
    transition; positive cells outside the geometric envelope are reported.
    """
    diag = frame.get("rdao") or {}
    effect = diag.get("observation_effect")
    if not (diag.get("granted") and effect and
            frame.get("observation_granted")):
        raise ValueError("Expected a naturally authorized RDAO observation")
    pos = tuple(map(int, diag["position"]))
    yaw = float(diag["heading_yaw"])
    before = np.asarray(effect["memory_before"], dtype=np.int8)
    after = np.asarray(effect["memory_after"], dtype=np.int8)
    if (before.shape != after.shape or before.ndim != 2 or
            not np.isin(before, (-1, 0, 1)).all() or
            not np.isin(after, (-1, 0, 1)).all()):
        raise ValueError("Invalid saved ternary observation memories")
    raw = {}
    for entry in effect["received_observation_values"]:
        x, y = map(int, entry["cell"])
        if not (0 <= y < before.shape[0] and 0 <= x < before.shape[1]):
            raise ValueError("Sensor-reported cell outside saved memory")
        if (x, y) in raw:
            raise ValueError("Duplicate raw observation cell")
        value = int(entry["value"])
        if value not in (0, 1):
            raise ValueError("Observed value must be occupied or free")
        raw[(x, y)] = value
    reconstructed = before.copy()
    for (x, y), value in raw.items():
        reconstructed[y, x] = value
    if not np.array_equal(reconstructed, after):
        raise ValueError("Frozen pre/post memory transition is inconsistent")
    if len(raw) != int(effect["visible_cell_count"]):
        raise ValueError("Raw visible cell count inconsistent")
    if (len(effect["memory_changed_cells"]) !=
            int(effect["memory_changed_cell_count"])):
        raise ValueError("Saved changed cell count inconsistent")
    unknown = np.argwhere(before == -1)
    relevant_positions = route_positions(
        pos, diag.get("nominal_route") or [])[:RDAOParameters().route_lookahead_actions + 1]
    counts = {model: {kind: empty_confusion() for kind in ("all", "route_near")}
              for model in ("legacy", "footprint")}
    raw_new = 0
    envelope_new = 0
    outside_envelope = 0
    known_labels = []
    for y, x in unknown:
        cell = (int(x), int(y))
        label = cell in raw
        if label:
            raw_new += 1
        if not footprint_envelope(pos, yaw, cell, cell_size_m=cell_size,
                                  range_m=range_m, fov_deg=fov_deg):
            if label:
                outside_envelope += 1
            continue
        if label:
            envelope_new += 1
        near = maybe_route_near(cell, relevant_positions)
        legacy = predicted_cell_visibility(
            before, pos, yaw, cell, cell_size_m=cell_size,
            range_m=range_m, horizontal_fov_deg=fov_deg,
            ray_count=ray_count, unknown_open_probability=UNKNOWN_OPEN)
        proposed = footprint_visibility(
            before, pos, yaw, cell, cell_size_m=cell_size,
            range_m=range_m, fov_deg=fov_deg, ray_count=ray_count,
            unknown_open=UNKNOWN_OPEN)
        for method, estimate in (("legacy", legacy), ("footprint", proposed)):
            add_confusion(counts[method]["all"], label, estimate > 0)
            if near:
                add_confusion(counts[method]["route_near"], label, estimate > 0)
        known_labels.append((near, label, legacy > 0, proposed > 0))
    return {
        "counts": counts, "position": pos, "raw_new": raw_new,
        "envelope_new": envelope_new,
        "observed_new_outside_envelope": outside_envelope,
        "unknown_candidates_in_envelope": len(known_labels),
    }


def write_csv(path, records):
    if not records:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(records[0]))
        wr.writeheader()
        wr.writerows(records)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-cases", type=int, default=None,
                        help="Deterministic prefix smoke-test; omit for all 72")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Never overwrite saved results: {args.output}")
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be a positive integer")

    source = PRIMARY / "primary_traces.jsonl.gz"
    manifest = PRIMARY / "experiment_manifest.json"
    expected = json.loads(manifest.read_text(encoding="utf-8"))
    if sha(source) != expected["source_hashes"].get(
            "results/phase2_mujoco/rdao_v1_phase2_evaluation/primary_traces.jsonl.gz",
            sha(source)):
        # The original manifest lists source-code hashes, not primary outputs;
        # SHA256 is recorded independently below and compared to the
        # previously committed visibility-probe integrity hash.
        raise RuntimeError("Unexpected primary trace checksum")
    reference = json.loads((
        ROOT / "results/phase2_mujoco/rdao_v1_visibility_probe_primary/summary.json"
    ).read_text(encoding="utf-8"))
    reference_hash = reference["input_sha256"][
        "results/phase2_mujoco/rdao_v1_phase2_evaluation/primary_traces.jsonl.gz"]
    if sha(source) != reference_hash:
        raise RuntimeError("Frozen trace changed since sensor-fidelity replay")
    geom = expected["memory_sensor"]
    if not (float(expected["grid_scale_m_per_cell"]) == CELL_M
            and float(geom["range_m"]) == RANGE_M
            and int(geom["rays"]) == RAY_COUNT
            and float(geom["horizontal_fov_deg"]) == FOV_DEG
            and int(expected["world_count"]) == 36):
        raise RuntimeError("Pinned evaluation sensor geometry changed")

    cases = []
    with gzip.open(source, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    if len(cases) != 72:
        raise RuntimeError("Expected 72 frozen RDAO primary traces")
    if args.max_cases is not None:
        cases = cases[:args.max_cases]
    total = {model: {kind: empty_confusion() for kind in ("all", "route_near")}
             for model in ("legacy", "footprint")}
    per_step = []
    per_world = defaultdict(lambda: {
        "events": 0,
        "legacy": empty_confusion(), "footprint": empty_confusion(),
    })
    observed = 0
    unique = set()
    outside = 0
    measured_new = 0
    evaluated_candidates = 0
    for n, trace in enumerate(cases, 1):
        world, schedule, variant, seed = trace["key"]
        if variant != "rdao_v1" or int(seed) != 42 or int(schedule) not in (0, 1):
            raise RuntimeError("Unexpected frozen episode identity")
        key = (world, int(schedule))
        if key in unique:
            raise RuntimeError("Duplicate frozen episode identity")
        unique.add(key)
        for frame in trace["steps"]:
            if not (frame.get("rdao") or {}).get("granted"):
                continue
            measurement = frame_samples(frame)
            observed += 1
            outside += measurement["observed_new_outside_envelope"]
            measured_new += measurement["raw_new"]
            evaluated_candidates += measurement["unknown_candidates_in_envelope"]
            item = {"world_identity": world, "schedule": schedule,
                    "step": int(frame["step"]), "raw_new_unknown": measurement["raw_new"],
                    "raw_new_outside_candidate_envelope":
                        measurement["observed_new_outside_envelope"],
                    "unknown_cells_in_envelope":
                        measurement["unknown_candidates_in_envelope"]}
            for model, scopes in measurement["counts"].items():
                for scope, conf in scopes.items():
                    for k, v in conf.items():
                        total[model][scope][k] += v
                        item[f"{model}_{scope}_{k}"] = v
                for k, v in scopes["all"].items():
                    per_world[world][model][k] += v
            per_world[world]["events"] += 1
            per_step.append(item)
        print(f"Read {n}/{len(cases)} frozen episodes: {world} schedule {schedule}",
              flush=True)

    if len(cases) == 72 and observed != 584:
        raise RuntimeError(
            f"Expected 584 naturally granted noninitial observations; got {observed}")
    if observed != sum(int(q["legacy_all_tp"])+int(q["legacy_all_fn"])
                       for q in per_step) - 0 + outside:
        # Observed is number of scans; raw positives are cell counts,
        # so this check would be invalid. Use the actual proper
        # cell-count relation below instead.
        pass
    if measured_new != (
            total["legacy"]["all"]["tp"] + total["legacy"]["all"]["fn"] + outside):
        raise RuntimeError("Candidate envelope excludes unaccounted visible cells")
    if any(total["legacy"][scope]["tp"] + total["legacy"][scope]["fn"] !=
           total["footprint"][scope]["tp"] + total["footprint"][scope]["fn"]
           for scope in ("all", "route_near")):
        raise RuntimeError("Predictor evaluation label sets differ")
    summary = {
        "status": "READ_ONLY_FIT_VISIBILITY_FEASIBILITY_AUDIT_NOT_ONLINE_POLICY",
        "worlds": len({w for w, _ in unique}), "episodes": len(unique),
        "naturally_authorized_noninitial_observations": observed,
        "raw_new_unknown_cells": measured_new,
        "positive_labels_outside_conservative_envelope": outside,
        "evaluated_unknown_cell_pose_pairs": evaluated_candidates,
        "metrics": {model: {scope: quality(c)
                           for scope, c in scopes.items()}
                    for model, scopes in total.items()},
        "per_world": [
            {"world_identity": world, "events": x["events"],
             "legacy": quality(x["legacy"]), "footprint": quality(x["footprint"])}
            for world, x in sorted(per_world.items())
        ],
        "source_sha256": {
            str(p.relative_to(ROOT)): sha(p) for p in (source, manifest,
                ROOT / "results/phase2_mujoco/rdao_v1_visibility_probe_primary/summary.json")
        },
        "limitations": [
            "All observed scans were naturally selected by the OLD RDAO v1 scheduler in FIT worlds; this is selection-biased, not full-pose generalization.",
            "Each unknown-cell/pose measurement is a correlated observation, not an independent trial; repeated worlds/schedules must not be treated independently.",
            "Prediction positive means score>0, a heuristic feasibility classification, NOT calibrated P(measured).",
            "Previously known cells are excluded; this tests new-information observation only.",
            "Truth labels are actual authorized 61-ray observations stored from MuJoCo, never hidden environment occupancy.",
            "A cell outside the footprint envelope is not evaluated as a negative, and positive cases outside it are explicitly counted.",
            "Footprint candidate is an angular/radial overapproximation retaining the original memory center-line occlusion heuristic, not true ray-cell intersection.",
            "An observation that reveals cells does not necessarily change route or success.",
            "No new MuJoCo rollout, no code changes to the live RDAO controller, and NO held-out evaluation.",
        ],
    }
    args.output.mkdir(parents=True)
    write_csv(args.output / "per_observation_confusion.csv", per_step)
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(json.dumps({
        "output": str(args.output), "episodes": len(unique),
        "authorized_observations": observed,
        "labeled_unknown_cell_pose_pairs": evaluated_candidates,
        "positives_outside_envelope": outside,
        "visibility_feasibility": summary["metrics"],
    }, indent=2))


if __name__ == "__main__":
    run()
