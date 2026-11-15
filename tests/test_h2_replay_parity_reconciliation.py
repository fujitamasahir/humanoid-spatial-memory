from reconcile_h2_full_spatial_memory_replay import _first_trace_difference


def test_first_trace_difference_uses_identity_matched_step_fields():
    saved = {"steps": [
        {"step": 0, "position": [1, 1], "heading_yaw": 0.0,
         "action": None, "observation_granted": True},
        {"step": 1, "position": [1, 2], "heading_yaw": 0.0,
         "action": ["move", [1, 2]], "observation_granted": False},
    ]}
    replay = {"steps": [
        {"step": 0, "position": [1, 1], "heading_yaw": 0.0,
         "action": None, "observation_granted": True},
        {"step": 1, "position": [1, 1], "heading_yaw": 1.57,
         "action": ["turn", 1], "observation_granted": False},
    ]}
    step, fields, old, new = _first_trace_difference(saved, replay)
    assert step == 1
    assert fields == "position,heading_yaw,action"
    assert old["position"] == [1, 2]
    assert new["position"] == [1, 1]


def test_first_trace_difference_reports_frame_count_change():
    step, fields, old, new = _first_trace_difference({"steps": [{"step": 0}]}, {"steps": []})
    assert step == 0
    assert fields == "frame_count"
    assert old == {"step": 0}
    assert new is None
