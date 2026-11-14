from scripts.c_v2c_fixtures import build_formal_fixtures
from scripts.validate_c_v2c_fixture_annotations import validate_annotations


def test_formal_fixture_set_is_deterministic_balanced_and_reference_validated():
    first=build_formal_fixtures();second=build_formal_fixtures()
    assert len(first)==len(second)==48
    assert all(a['fixture_id']==b['fixture_id'] and
        (a['grid']==b['grid']).all() and (a['probability']==b['probability']).all()
        for a,b in zip(first,second))
    validation=validate_annotations()
    assert validation['status']=='PASS'
    assert validation['all_structural_annotations_consistent']
    assert validation['policy_values_computed'] is False
    assert validation['candidate_arms_executed'] is False
    assert all(x['target_visible'] and not x['errors'] for x in validation['fixtures'])
