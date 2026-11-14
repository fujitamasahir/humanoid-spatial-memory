from scripts.evaluate_c_v2_candidate_coverage_fit72 import baseline_trace_for_method


def test_periodic_and_age_use_their_own_saved_trace_keys():
    saved={('R80000001',1,'age',42):{'method':'age'},
           ('R80000001',1,'periodic',42):{'method':'periodic'}}
    age_key=('R80000001',1,'age',42)
    assert baseline_trace_for_method(saved,age_key,'age')=={'method':'age'}
    assert baseline_trace_for_method(saved,age_key,'periodic')=={'method':'periodic'}
