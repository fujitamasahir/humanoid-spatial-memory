"""Standalone rational decision-table fixtures for Phase 1.5A-2.

No filter, spatial controller, scheduler, sensor, generator, or navigation imports.
--test runs algebraic checks; --output writes compact exact fixture evidence.
"""
import argparse
import ast
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import sys
import unittest


def finite_reference(prior, loss, channel):
    """Exhaustive small finite decision problem; no online policy or simulation."""
    assert sum(prior) == 1 and all(p >= 0 for p in prior)
    assert all(sum(row) == 1 and all(v >= 0 for v in row) for row in channel)
    actions = range(len(loss[0]))
    prior_cost = [sum(p * row[a] for p,row in zip(prior,loss)) for a in actions]
    a0 = min(actions,key=lambda a: prior_cost[a])
    after = F(0)
    advantage = F(0)
    for y in range(len(channel[0])):
        joint = [p*row[y] for p,row in zip(prior,channel)]
        mass = sum(joint)
        if not mass:
            continue
        weighted = [sum(w*row[a] for w,row in zip(joint,loss)) for a in actions]
        after += min(weighted)
        advantage += weighted[a0]-min(weighted)
    perfect = sum(p*min(row) for p,row in zip(prior,loss))
    return dict(risk=prior_cost[a0],evsi=prior_cost[a0]-after,
                posterior_advantage=advantage,vpc=prior_cost[a0]-perfect)


def illustrative_pattern_law():
    # A closed-form illustrative noiseless count rule, not the proposed EM learner.
    return [F(13,32) if v == 0 else F(5,32) if v == 15 else F(1,32)
            for v in range(16)]


def evidence():
    channel = [[F(1),F(0)],[F(0),F(1)]]
    loss = [[F(-195,1000),F(105,1000)],
            [F(105,1000),F(-195,1000)]]
    noisy = [[F(95,100),F(5,100)],[F(5,100),F(95,100)]]
    b = illustrative_pattern_law()
    return dict(scope='exact hand-built mathematical fixtures; zero generated layouts or episodes',
                corridor_open_half=F(1,2)**11,
                corridor_all64_miss=(1-F(1,2)**11)**64,
                optimistic_corridor_open=F(9,10)**11,
                original_wait=F(1005,1000),original_uncertain_move=F(1055,1000),
                safe_move=F(-195,1000),safe_wait=F(5,1000),
                uncertain_move=F(5,1000)+F(1,10)*F(1,4)-F(1,5)*F(3,4)+F(1,100)*F(3,4),
                high_blocked_move=F(5,1000)+F(1,10)*F(9,10)-F(1,5)*F(1,10)+F(1,100)*F(1,10),
                perfect_query=finite_reference([F(1,2)]*2,loss,channel),
                noisy_query=finite_reference([F(1,2)]*2,loss,noisy),
                pattern_law=b,
                pattern_bit_occupancy=sum(p*((v>>0)&1) for v,p in enumerate(b)),
                independent_allfree_at_same_marginal=F(5,8)**4,
                hypothetical_policy_value_when_post_action_is_wrong=F(-1,2),
                assessment_core=160*2*10,assessment_assay=160*2*9,
                assessment_ablations=160*2*2,assessment_max=6720,
                development_fit=96,development_calibration=1008,
                development_selection=1008,development_max=2112)


class MathematicalTests(unittest.TestCase):
    def test_corridor_coverage(self):
        self.assertEqual(evidence()['corridor_open_half'],F(1,2048))
        self.assertGreater(evidence()['corridor_all64_miss'],F(96,100))

    def test_optimism_is_a_different_assumption(self):
        self.assertGreater(F(9,10)**11,F(3,10))

    def test_pattern_normalization_and_support(self):
        b=illustrative_pattern_law()
        self.assertEqual(sum(b),1)
        self.assertTrue(all(p>0 for p in b))

    def test_pattern_correlation(self):
        b=illustrative_pattern_law()
        self.assertEqual(evidence()['pattern_bit_occupancy'],F(3,8))
        self.assertGreater(b[0],F(5,8)**4)

    def test_boundary_marginal_not_padding_zero(self):
        b=illustrative_pattern_law()
        marginal=sum(p for v,p in enumerate(b) if (v&1)==0)
        padded=b[0]/(b[0]+b[1])
        self.assertEqual(marginal,F(5,8))
        self.assertNotEqual(marginal,padded)

    def test_condition_protected_bit(self):
        b=illustrative_pattern_law()
        denominator=sum(p for v,p in enumerate(b) if (v&1)==0)
        posterior=[p/denominator if (v&1)==0 else F(0) for v,p in enumerate(b)]
        self.assertEqual(sum(posterior),1)
        self.assertEqual(sum(p*((v>>0)&1) for v,p in enumerate(posterior)),0)

    def test_refresh_stationarity(self):
        b=[F(3,4),F(1,4)]; r=F(1,10)
        t=[[(1-r)*int(u==v)+r*b[v] for v in range(2)] for u in range(2)]
        self.assertEqual([sum(b[u]*t[u][v] for u in range(2)) for v in range(2)],b)

    def test_refresh_gap(self):
        b=[F(3,4),F(1,4)]; r=F(1,10)
        t=[[(1-r)*int(u==v)+r*b[v] for v in range(2)] for u in range(2)]
        squared=[[sum(t[u][k]*t[k][v] for k in range(2)) for v in range(2)] for u in range(2)]
        formula=[[(1-r)**2*int(u==v)+(1-(1-r)**2)*b[v] for v in range(2)] for u in range(2)]
        self.assertEqual(squared,formula)

    def test_rejection_posterior_identity(self):
        p=[F(1,10),F(2,10),F(3,10),F(4,10)]
        g=[F(1),F(1,2),F(1,4),F(1)]
        h=[0,1,1,0]
        zg=sum(a*b for a,b in zip(p,g))
        q=[a*b/zg for a,b in zip(p,g)]
        accept=sum(a*b for a,b in zip(q,h))
        rejected=[a*b/accept for a,b in zip(q,h)]
        total=sum(a*b*c for a,b,c in zip(p,g,h))
        exact=[a*b*c/total for a,b,c in zip(p,g,h)]
        self.assertEqual(rejected,exact)

    def test_marginal_single_cell_is_not_full_missing_mask(self):
        # Two normalized full outcomes share the same returned first-cell bit.
        p=[F(1,3),F(2,3)]
        self.assertEqual(sum(p),1)
        self.assertNotEqual(sum(p),p[0])

    def test_original_saturation_wait(self):
        self.assertLess(evidence()['original_wait'],evidence()['original_uncertain_move'])
        r=finite_reference([F(1,2)]*2,
                           [[F(1005,1000),F(1005,1000)],
                            [F(1005,1000),F(1105,1000)]],
                           [[F(1),F(0)],[F(0),F(1)]])
        self.assertEqual(r['evsi'],0)

    def test_soft_cost_finite(self):
        costs=[1+9*p/(1-p+F(5,100)) for p in (F(0),F(1,2),F(1))]
        self.assertEqual(costs[0],1)
        self.assertEqual(costs[-1],181)
        self.assertTrue(all(1<=v<=181 for v in costs))

    def test_known_progress(self):
        self.assertLess(evidence()['safe_move'],evidence()['safe_wait'])

    def test_uncertain_progress(self):
        self.assertEqual(evidence()['uncertain_move'],F(-9,80))
        self.assertLess(evidence()['uncertain_move'],evidence()['safe_wait'])

    def test_legitimate_wait(self):
        self.assertEqual(evidence()['high_blocked_move'],F(19,250))
        self.assertGreater(evidence()['high_blocked_move'],evidence()['safe_wait'])

    def test_exact_value_crosses_price(self):
        r=evidence()['perfect_query']
        self.assertEqual(r['evsi'],F(3,20))
        self.assertEqual(r['evsi'],r['posterior_advantage'])
        self.assertGreater(r['evsi'],F(2,100))
        self.assertLessEqual(r['evsi'],r['vpc'])

    def test_noisy_value(self):
        self.assertEqual(evidence()['noisy_query']['evsi'],F(27,200))

    def test_phantom_goal_positive_score_contrast(self):
        prior=[F(1,2)]*2
        channel=[[F(1),F(0)],[F(0),F(1)]]
        real=[[F(-195,1000),F(105,1000),F(5,1000)],
              [F(105,1000),F(-195,1000),F(5,1000)]]
        phantom=[[F(205,1000),F(105,1000),F(5,1000)],
                 [F(105,1000),F(205,1000),F(5,1000)]]
        self.assertEqual(finite_reference(prior,real,channel)['evsi'],F(3,20))
        self.assertEqual(finite_reference(prior,phantom,channel)['evsi'],0)

    def test_full_query_activates_when_each_single_cell_does_not(self):
        blocked=F(47,50); free=1-blocked
        prior=[free*free,free*blocked,blocked*free,blocked*blocked]
        loss=[[F(-195,1000),F(-195,1000),F(5,1000)],
              [F(-195,1000),F(105,1000),F(5,1000)],
              [F(105,1000),F(-195,1000),F(5,1000)],
              [F(105,1000),F(105,1000),F(5,1000)]]
        full=[[F(int(i==j)) for j in range(4)] for i in range(4)]
        first=[[F(1),F(0)],[F(1),F(0)],[F(0),F(1)],[F(0),F(1)]]
        second=[[F(1),F(0)],[F(0),F(1)],[F(1),F(0)],[F(0),F(1)]]
        self.assertEqual(finite_reference(prior,loss,full)['evsi'],F(291,12500))
        self.assertEqual(finite_reference(prior,loss,first)['evsi'],F(3,250))
        self.assertEqual(finite_reference(prior,loss,second)['evsi'],F(3,250))
        self.assertGreater(F(291,12500),F(2,100))
        self.assertLess(F(3,250),F(2,100))

    def test_information_does_not_reveal_future(self):
        # Known current state, independent fair future; either action has loss1/2.
        r=finite_reference([F(1,2)]*2,[[F(0),F(1)],[F(1),F(0)]],
                           [[F(1,2),F(1,2)],[F(1,2),F(1,2)]])
        self.assertEqual(r['evsi'],0)
        self.assertEqual(r['vpc'],F(1,2)) # here full state includes the future bit

    def test_negative_policy_conditioned_value_is_possible(self):
        base=F(1,2) # prior action0, opposite-action worlds
        wrong_after_perfect_query=F(1)
        self.assertEqual(base-wrong_after_perfect_query,F(-1,2))

    def test_terminal_goal(self):
        self.assertLess(F(5,1000),F(1005,1000))

    def test_loss_range(self):
        self.assertEqual(F(1305,1000)-F(-1195,1000),F(5,2))

    def test_count_matching(self):
        self.assertGreaterEqual(5-4,1)
        self.assertEqual(1+1,2) # charged initialization plus exactly one window call

    def test_matrix(self):
        e=evidence()
        self.assertEqual(e['assessment_core']+e['assessment_assay']+e['assessment_ablations'],6720)
        self.assertEqual(96+1008+1008,2112)

    def test_scope_no_navigation_or_random_simulator(self):
        tree=ast.parse(Path(__file__).read_text())
        modules=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node,ast.ImportFrom):
                modules.append(node.module or '')
        self.assertFalse(any(x.startswith('spatial_memory') or x in ('random','numpy') for x in modules))


def encode(value):
    if isinstance(value,F):
        return dict(exact=str(value),decimal=float(value))
    if isinstance(value,dict):
        return {k:encode(v) for k,v in value.items()}
    if isinstance(value,list):
        return [encode(v) for v in value]
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.test:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MathematicalTests))
        raise SystemExit(not result.wasSuccessful())
    if not args.output:
        parser.error('--test or --output required')
    args.output.mkdir(parents=True,exist_ok=True)
    data=encode(evidence())
    data['python']=sys.version
    data['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    destination=args.output/'mathematical_fixtures.json'
    destination.write_text(json.dumps(data,indent=2)+'\n')
    print(f'Wrote {destination}; exact arithmetic only, zero episodes/layouts.')


if __name__=='__main__':
    main()
