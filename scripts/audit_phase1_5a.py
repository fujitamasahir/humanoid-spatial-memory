"""Finite mathematical checks and synthetic kernels; no navigation/policy imports.

Run --test for the isolated audit tests or --output DIR for measured evidence.
This does not implement a particle filter, sensor, scheduler or topology generator.
"""
import argparse
import array
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import struct
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
NORMAL = statistics.NormalDist()


def finite_information(prior, losses, likelihood):
    """Exhaustive finite decision-table identity, not an online estimator."""
    if not math.isclose(sum(prior), 1):
        raise ValueError('prior must normalize')
    if any(not math.isclose(sum(row), 1) for row in likelihood):
        raise ValueError('each state observation law must normalize')
    actions = len(losses[0])
    risk = min(sum(p * row[a] for p, row in zip(prior, losses))
               for a in range(actions))
    after = 0.0
    support = []
    for y in range(len(likelihood[0])):
        joint = [p * row[y] for p, row in zip(prior, likelihood)]
        mass = sum(joint)
        support.append(mass)
        if mass:
            after += min(sum(w * row[a] for w, row in zip(joint, losses))
                         for a in range(actions))
    perfect = sum(p * min(row) for p, row in zip(prior, losses))
    return {'risk': risk, 'evsi': risk-after, 'vpi': risk-perfect,
            'observation_mass': support}


def paired_power(n, effect, variance):
    if variance <= 0:
        raise ValueError('positive variance required')
    z = NORMAL.inv_cdf(.975)
    shift = effect / math.sqrt(variance/n)
    return 1-NORMAL.cdf(z-shift) + NORMAL.cdf(-z-shift)


def required_clusters(effect, variance, power=.8):
    raw = (NORMAL.inv_cdf(.975)+NORMAL.inv_cdf(power))**2*variance/effect**2
    return 4*math.ceil(raw/4)  # balanced four-mechanism design


def power_tables():
    rows = []
    for q in (.05, .1, .2, .4, .8):
        for effect in (.03, .05, .1):
            if q < effect:
                continue  # impossible paired binary distribution
            variance = q-effect**2
            rows.append(dict(discordance=q, effect=effect, variance=variance,
                             halfwidth160=NORMAL.inv_cdf(.975)*math.sqrt(variance/160),
                             power160=paired_power(160, effect, variance),
                             clusters80=required_clusters(effect, variance),
                             clusters90=required_clusters(effect, variance,.9)))
    cluster_rows = []
    for variance in (.025, .05, .1, .2, .4, .8):
        cluster_rows.append(dict(variance=variance,
                                halfwidth160=NORMAL.inv_cdf(.975)*math.sqrt(variance/160),
                                power160=paired_power(160,.05,variance),
                                clusters80=required_clusters(.05,variance)))
    return rows, cluster_rows


def timing(fn, repeats=21):
    for _ in range(3):
        fn()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        fn()
        samples.append((time.perf_counter_ns()-start)/1e6)
    ordered = sorted(samples)
    return dict(median_ms=statistics.median(samples),
                p95_ms=ordered[math.ceil(.95*len(ordered))-1],
                samples_ms=samples)


def synthetic_benchmarks():
    rng = random.Random(1505011)
    m, n, k, a, tiles = 64, 625, 29, 5, 169
    probabilities = [[rng.random() for _ in range(16)] for _ in range(m*tiles)]
    sums = [sum(row) for row in probabilities]
    probabilities = [[p/s for p in row] for row, s in zip(probabilities,sums)]
    uniforms = [rng.random() for _ in probabilities]

    def categorical_kernel():
        out = []
        for row, u in zip(probabilities, uniforms):
            total = 0.
            for state, p in enumerate(row):
                total += p
                if u < total:
                    out.append(state)
                    break
        return out

    # Arbitrary short Boolean lists: no geometric rays or real visibility.
    short_lists = [[rng.randrange(2) for _ in range(3)] for _ in range(m*k)]

    def boolean_kernel():
        return [not any(row) for row in short_lists]

    qtable = [[rng.random()*2.105 for _ in range(a)] for _ in range(m)]
    emissions = [[(math.log(.05+rng.random()*.9), math.log(.05+rng.random()*.9))
                  for _ in range(k)] for _ in range(m)]
    results = {'categorical_64x169x16': timing(categorical_kernel),
               'boolean_64x29x3': timing(boolean_kernel), 'dense': []}
    for draws in (64,128,256):
        returns = [[rng.randrange(2) for _ in range(k)] for _ in range(draws)]

        def dense_kernel():
            answer = []
            for y in returns:
                logs = [sum(pair[v] for pair,v in zip(row,y)) for row in emissions]
                peak = max(logs)
                weights = [math.exp(v-peak) for v in logs]
                normalizer = sum(weights)
                answer.append(min(sum(w*row[act] for w,row in zip(weights,qtable))
                                  /normalizer for act in range(a)))
            return answer

        measured = timing(dense_kernel)
        measured.update(J=draws, emission_factors=draws*m*k,
                        action_products=draws*m*a,
                        full_matrix_kernel_cpu_hours=measured['median_ms']*10035200/3.6e6,
                        reduced_matrix_kernel_cpu_hours=measured['median_ms']*537600/3.6e6)
        results['dense'].append(measured)
    return results


def synthetic_storage():
    rows = []
    for draws in (64,128,256):
        for mode in ('sticky_1pct', 'independent'):
            rng = random.Random(1505012)
            state = bytearray(rng.randbytes(64*79*2))
            frames = []
            for step in range(80):
                if mode == 'independent':
                    state[:] = rng.randbytes(len(state))
                else:
                    for _ in range(math.ceil(len(state)*8*.01)):
                        bit = rng.randrange(len(state)*8)
                        state[bit//8] ^= 1 << (bit%8)
                floats = array.array('d', [rng.random() for _ in range(64+64*5+draws)])
                if sys.byteorder != 'little':
                    floats.byteswap()
                # fixed 2 KiB metadata/public-return placeholder, no evaluator trace
                frames.append(struct.pack('<I',step)+state+floats.tobytes()+bytes(2048))
            raw = b''.join(frames)
            packed = gzip.compress(raw,compresslevel=6,mtime=0)
            rows.append(dict(J=draws,pattern=mode,raw_episode_bytes=len(raw),
                             gzip_episode_bytes=len(packed),
                             full_matrix_decimal_GB=len(packed)*125440/1e9,
                             reduced_matrix_decimal_GB=len(packed)*6720/1e9,
                             sha256=hashlib.sha256(packed).hexdigest()))
    return rows


class AuditTests(unittest.TestCase):
    def test_perfect_binary(self):
        r=finite_information([.5,.5],[[0,1],[1,0]],[[1,0],[0,1]])
        self.assertAlmostEqual(r['evsi'],.5)
        self.assertAlmostEqual(r['vpi'],.5)

    def test_uninformative(self):
        r=finite_information([.5,.5],[[0,1],[1,0]],[[.3,.7],[.3,.7]])
        self.assertAlmostEqual(r['evsi'],0)

    def test_common_optimum(self):
        r=finite_information([.5,.5],[[0,1],[0,2]],[[1,0],[0,1]])
        self.assertEqual(r['evsi'],0)

    def test_noisy_binary(self):
        r=finite_information([.5,.5],[[0,1],[1,0]],[[.95,.05],[.05,.95]])
        self.assertAlmostEqual(r['evsi'],.45)

    def test_parity(self):
        costs=[[0,1],[1,0],[1,0],[0,1]]
        single=[[1,0],[1,0],[0,1],[0,1]]
        joint=[[int(i==j) for j in range(4)] for i in range(4)]
        self.assertAlmostEqual(finite_information([.25]*4,costs,single)['evsi'],0)
        self.assertAlmostEqual(finite_information([.25]*4,costs,joint)['evsi'],.5)

    def test_missingness_informative(self):
        r=finite_information([.5,.5],[[0,1],[1,0]],[[1,0],[0,1]])
        self.assertEqual(r['observation_mass'],[.5,.5])
        self.assertAlmostEqual(r['evsi'],.5) # y=0 can mean missing, not occupied

    def test_impossible_observation(self):
        r=finite_information([.5,.5],[[0,1],[1,0]],[[1,0,0],[0,1,0]])
        self.assertEqual(r['observation_mass'][2],0)

    def test_invalid_law(self):
        with self.assertRaises(ValueError):
            finite_information([.5,.5],[[0,1],[1,0]],[[.2,.3],[.4,.6]])

    def test_random_finite_bounds(self):
        rng=random.Random(1505013)
        for _ in range(200):
            prior=[rng.random() for _ in range(4)]
            prior=[v/sum(prior) for v in prior]
            costs=[[rng.random()*2.105 for _ in range(3)] for _ in prior]
            law=[[rng.random() for _ in range(3)] for _ in prior]
            law=[[v/sum(row) for v in row] for row in law]
            r=finite_information(prior,costs,law)
            self.assertGreaterEqual(r['evsi'],-1e-12)
            self.assertLessEqual(r['evsi'],r['vpi']+1e-12)
            self.assertLessEqual(r['vpi'],2.105)

    def test_scaling(self):
        prior=[.5,.5]; law=[[.9,.1],[.1,.9]]
        base=finite_information(prior,[[0,1],[1,0]],law)['evsi']
        other=finite_information(prior,[[0,7],[7,0]],law)['evsi']
        self.assertAlmostEqual(other,7*base)

    def test_zero_sample_se_trap(self):
        # Informative event probability .001: no such event is likely in J=64.
        self.assertGreater((1-.001)**64,.93)

    def test_bootstrap_support_failure(self):
        self.assertGreater((1-2**-29)**64,.9999998)

    def test_power_monotonic(self):
        self.assertLess(paired_power(160,.05,.2),paired_power(640,.05,.2))

    def test_variance_pairing(self):
        q=.2; d=.05
        plus=(q+d)/2; minus=(q-d)/2
        self.assertAlmostEqual(plus+minus-(plus-minus)**2,.1975)

    def test_required_balanced(self):
        self.assertEqual(required_clusters(.05,.1975),624)

    def test_repeat_variance(self):
        self.assertAlmostEqual(.2*(1+.5)/2,.15)

    def test_matrix_arithmetic(self):
        self.assertEqual(160*2*(5+5),3200)
        self.assertEqual(160*2*9,2880)
        self.assertEqual(3200+2880+160*2*2,6720)

    def test_scope_no_navigation_imports(self):
        import ast
        tree=ast.parse(Path(__file__).read_text())
        modules=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                modules.extend(x.name for x in node.names)
            if isinstance(node,ast.ImportFrom):
                modules.append(node.module or '')
        self.assertFalse(any(x.startswith('spatial_memory') for x in modules))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.test:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AuditTests))
        raise SystemExit(not result.wasSuccessful())
    if not args.output:
        parser.error('--test or --output is required')
    args.output.mkdir(parents=True,exist_ok=True)
    paired,clusters=power_tables()
    cpu='unknown'
    for line in Path('/proc/cpuinfo').read_text().splitlines():
        if line.startswith('model name'):
            cpu=line.split(':',1)[1].strip(); break
    evidence=dict(scope='synthetic mathematical workloads only; zero navigation episodes',
                  python=sys.version, platform=platform.platform(),cpu=cpu,
                  logical_cpus=os.cpu_count(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  paired_power=paired,cluster_power=clusters,
                  kernels=synthetic_benchmarks(),storage=synthetic_storage())
    evidence['process_peak_rss_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    evidence['frozen_sha256']={str(p):hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                              (Path('results/phase1_4b/parameter_lock.json'),Path('results/phase1_4a/manifests/assessment.json'))}
    destination=args.output/'mathematical_audit.json'
    destination.write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({key:evidence[key] for key in ('cpu','python','process_peak_rss_KiB')}))
    print(f'Wrote {destination}; no navigation code imported or episodes run.')


if __name__=='__main__':
    main()
