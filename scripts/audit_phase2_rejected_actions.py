"""Audit and correct rejected-action attempt vs unique-transition metrics post-run."""
import argparse
import ast
import csv
import copy
import hashlib
import json
from pathlib import Path
import subprocess


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def transition_key(record):
    action = tuple(record['action']) if record['action_kind'] == 'move' else int(record['action'])
    return (tuple(record['position']), int(record['heading_index']),
            record['action_kind'], action)


def audit_records(records):
    keys = {transition_key(record) for record in records}
    return {'attempts': len(records), 'unique_transitions': len(keys),
            'retries_after_local_observation_change': len(records)-len(keys)}


def audit_result(result_dir):
    result_dir = Path(result_dir).resolve()
    csv_path = result_dir/'episodes.csv'
    summary_path = result_dir/'summary.json'
    provenance_path = result_dir/'provenance.json'
    manifest_path = result_dir/'artifact_manifest.json'
    for path in (csv_path, summary_path, provenance_path, manifest_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    outputs = [result_dir/'artifact_manifest_pre_action_audit.json',
               result_dir/'episodes_action_metrics_corrected.csv',
               result_dir/'summary_action_metrics_corrected.json',
               result_dir/'action_history_audit.json']
    if any(path.exists() for path in outputs):
        raise FileExistsError('Action-history audit outputs already exist; refusing to overwrite')

    original_manifest_raw = manifest_path.read_bytes()
    original_summary_raw = summary_path.read_bytes()
    csv_raw = csv_path.read_bytes()
    rows = list(csv.DictReader(csv_path.open(newline='', encoding='utf-8')))
    report_groups = {}
    corrected_rows = []
    episode_repeats = 0
    for row in rows:
        records = ast.literal_eval(row['g1_rejected_actions'])
        action_stats = audit_records(records)
        if int(row['g1_footprint_blocked_attempts']) != action_stats['attempts']:
            raise ValueError(f"Movement-block count mismatch for {row['world_identity']} schedule {row['schedule']}")
        # The runner version used in this matrix stored attempts under the
        # legacy 'distinct' label. Verify and retain the raw CSV unchanged.
        if int(row['g1_distinct_rejected_actions']) != action_stats['attempts']:
            raise ValueError('Legacy action-count field has an unexpected definition')
        resets = int(row['g1_blocked_feedback_resets_after_changed_observation'])
        if action_stats['retries_after_local_observation_change'] and resets == 0:
            raise ValueError('Repeated transition has no recorded local-evidence reconsideration')
        episode_repeats += int(action_stats['retries_after_local_observation_change'] > 0)
        for group in ('overall', row['mechanism'], row['method'],
                      f"{row['mechanism']}:{row['method']}"):
            slot = report_groups.setdefault(group, dict(episodes=0, attempts=0,
                unique_transitions=0, retries=0, episodes_with_retry=0))
            slot['episodes'] += 1
            slot['attempts'] += action_stats['attempts']
            slot['unique_transitions'] += action_stats['unique_transitions']
            slot['retries'] += action_stats['retries_after_local_observation_change']
            slot['episodes_with_retry'] += int(action_stats['retries_after_local_observation_change'] > 0)
        corrected = dict(row)
        corrected['g1_rejected_action_attempts'] = action_stats['attempts']
        corrected['g1_distinct_rejected_actions'] = action_stats['unique_transitions']
        corrected['g1_blocked_action_records'] = action_stats['attempts']
        corrected_rows.append(corrected)

    # Preserve the exact pre-audit manifest and CSV. The corrected CSV and
    # summary are separately named derivations, both linked to raw file hashes.
    outputs[0].write_bytes(original_manifest_raw)
    corrected_csv_path = outputs[1]
    fields = list(corrected_rows[0])
    with corrected_csv_path.open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(corrected_rows)
        handle.flush()

    original_summary = json.loads(original_summary_raw)
    corrected_summary = copy.deepcopy(original_summary)
    for method, metrics in corrected_summary['summary']['methods'].items():
        selected_rows = [row for row in corrected_rows if row['method'] == method]
        metrics['g1_rejected_action_attempts'] = sum(
            int(row['g1_rejected_action_attempts']) for row in selected_rows)
        metrics['g1_blocked_action_records'] = metrics['g1_rejected_action_attempts']
        metrics['g1_distinct_rejected_actions'] = sum(
            int(row['g1_distinct_rejected_actions']) for row in selected_rows)
    for mechanism, method_map in corrected_summary['summary']['mechanisms'].items():
        for method, metrics in method_map.items():
            selected_rows = [row for row in corrected_rows if row['mechanism'] == mechanism
                             and row['method'] == method]
            metrics['g1_rejected_action_attempts'] = sum(
                int(row['g1_rejected_action_attempts']) for row in selected_rows)
            metrics['g1_blocked_action_records'] = metrics['g1_rejected_action_attempts']
            metrics['g1_distinct_rejected_actions'] = sum(
                int(row['g1_distinct_rejected_actions']) for row in selected_rows)
    corrected_summary['action_metric_note'] = (
        'Raw summary is preserved unchanged. This derived summary distinguishes '
        'rejected action attempts from unique (position, heading, action) transitions.')
    outputs[2].write_text(json.dumps(corrected_summary, sort_keys=True, indent=2)+'\n', encoding='utf-8')

    git_commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True,
        text=True, check=True).stdout.strip()
    git_status = subprocess.run(['git', 'status', '--short', '--branch'], capture_output=True,
        text=True, check=True).stdout.strip()
    report = {
        'status': 'PASS_ACTION_HISTORY_AUDIT',
        'experiment_git_commit': json.loads(provenance_path.read_text())['git_commit'],
        'postprocessing_git_commit': git_commit,
        'postprocessing_git_status_at_start': git_status,
        'episodes_csv_sha256': sha(csv_raw),
        'original_summary_sha256': sha(original_summary_raw),
        'original_artifact_manifest_sha256': sha(original_manifest_raw),
        'episodes': len(rows),
        'definition': {
            'attempt': 'one action submitted to the MuJoCo safety shield and rejected',
            'unique_transition': '(position, cardinal heading, action kind, destination/turn target), counted within each episode',
            'retry_condition': 'local observed-memory signature changed before the transition could be reconsidered',
            'raw_episode_csv_modified': False,
            'raw_summary_copied_unchanged': True,
        },
        'totals': report_groups,
        'episodes_with_retried_transition': episode_repeats,
        'corrected_csv': outputs[1].name,
        'corrected_summary': outputs[2].name,
        'original_manifest_copy': outputs[0].name,
    }
    outputs[3].write_text(json.dumps(report, sort_keys=True, indent=2)+'\n', encoding='utf-8')

    entries = []
    for path in sorted(result_dir.iterdir()):
        if path.is_file() and path.name != 'artifact_manifest.json':
            raw = path.read_bytes()
            entries.append({'path': path.name, 'bytes': len(raw), 'sha256': sha(raw)})
    manifest_path.write_text(json.dumps(entries, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_result(args.result_dir), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
