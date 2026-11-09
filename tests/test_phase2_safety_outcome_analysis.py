import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'phase2_safety_outcome_analysis',
    ROOT / 'scripts/analyze_phase2_safety_outcome_changes.py')
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def frame(step, *, position=(0, 0), heading=0.0, action=None, moved=False,
          blocked=False, observation=False, count=0):
    return {'step': step, 'position': list(position), 'heading_yaw': heading,
            'action': action, 'moved': moved, 'blocked': blocked,
            'observation_granted': observation, 'observation_count': count}


def test_first_divergence_detects_intervention_action():
    before = {'steps': [frame(0), frame(1, position=(1, 0), action=['move', [1, 0]], moved=True)]}
    after = {'steps': [frame(0), frame(1, action=['wait', None])]}
    assert analysis.first_divergence(before, after) == (1, ['position', 'action', 'moved'])


def test_first_divergence_detects_truncated_episode():
    before = {'steps': [frame(0), frame(1)]}
    after = {'steps': [frame(0)]}
    assert analysis.first_divergence(before, after) == (1, ['episode_length'])


def test_paired_indices_freeze_shorter_animation():
    assert analysis.paired_indices(2, 4) == [(0, 0), (1, 1), (1, 2), (1, 3)]
    assert analysis.paired_indices(4, 2) == [(0, 0), (1, 1), (2, 1), (3, 1)]


def test_pairing_rejects_empty_render_stream():
    try:
        analysis.paired_indices(0, 1)
    except ValueError as exc:
        assert 'at least one frame' in str(exc)
    else:
        raise AssertionError('empty render stream must be rejected')


def test_intervention_keeps_planner_action_separate():
    frame_data = {'action': ['wait', None], 'emergency_intervention': {
        'selected_action_before': ['move', [11, 4]],
        'selected_action_after': ['wait', None]}}
    assert analysis.action_before_safety(frame_data) == ['move', [11, 4]]
    assert analysis.executed_description(frame_data) == 'waited'
