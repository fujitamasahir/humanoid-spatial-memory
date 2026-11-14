"""Reviewer fault injection on independent development fixtures only."""
from copy import deepcopy
from pathlib import Path
import numpy as np
from spatial_memory.multistep_evi import ARMS
from spatial_memory.multistep_review import review_document,FROZEN


def example():
    g=np.zeros((4,6),dtype=np.int8);q=np.zeros(g.shape);q[1,2]=.5
    f={'id':'review-unit-not-formal','grid':g.tolist(),'probability':q.tolist(),
       'start':(1,1),'goal':(5,1),'target':(2,1),'yaw':0.,'unknown':'optimistic',
       'sensor':dict(range_m=4.,cell_size=1.,horizontal_fov_deg=360.,ray_count=61),
       'remaining':19,'expectation':'diagnostic'}
    args=(g,q,f['start'],f['goal'],0.,'optimistic',f['sensor'],19)
    return {'fixtures':[{'id':f['id'],'results':{name:fn(*args) for name,fn in {**FROZEN,**ARMS}.items()}}]},[f]


def test_clean_independent_development_evidence_has_no_conformance_errors():
    doc,fixtures=example();review=review_document(doc,fixtures)
    assert all(review['checks'].values())
    # One development case cannot satisfy the prospective 96-case positive gate.
    assert review['status']=='VALID_REJECTED_STOP_BEFORE_FIT'


def test_reviewer_source_and_artifact_checks_do_not_contaminate_numerics():
    doc,fixtures=example()
    for key in ('sources_ok','artifacts_ok','annotations_ok'):
        result=review_document(doc,fixtures,**{key:False})
        assert result['status']=='INVALID_STOP_BEFORE_FIT'
        assert result['checks']['numerical']
        assert result['checks']['selection']
        assert result['checks']['accounting']


def test_numeric_fault_detected_independently():
    doc,fixtures=example()
    doc['fixtures'][0]['results']['ms_k']['candidate_evaluations'][0]['best_postpone_cost']+=1
    result=review_document(doc,fixtures)
    assert result['validity_errors']['numerical']
    assert result['checks']['source'] and result['checks']['selection']


def test_visibility_and_pose_fault_detected():
    doc,fixtures=example()
    prediction=doc['fixtures'][0]['results']['ms_k_visibility']['candidate_evaluations'][0]['delayed_options'][0]['predictions'][0]
    prediction['visible']=not prediction['visible']
    result=review_document(doc,fixtures)
    assert result['validity_errors']['prediction']
    assert result['checks']['numerical']


def test_planning_and_visibility_counter_faults_detected():
    for field in ('plan_calls','visibility_computations','prefix_step_visits'):
        doc,fixtures=example();doc['fixtures'][0]['results']['ms_k_visibility'][field]+=1
        result=review_document(doc,fixtures)
        assert result['validity_errors']['accounting']
        assert result['checks']['numerical']


def test_selection_mutation_cannot_masquerade_as_timing_gain():
    doc,fixtures=example()
    doc['fixtures'][0]['results']['ms_k']['shortlisted_candidates'][0]['cell']=(3,2)
    result=review_document(doc,fixtures)
    assert result['validity_errors']['selection']


def test_reference_review_imports_are_isolated_from_policy_and_runner():
    text=(Path(__file__).parents[1]/'src/spatial_memory/multistep_review.py').read_text()
    assert 'from .multistep_evi' not in text
    assert 'run_c_v21_synthetic' not in text
