"""Post-run independent scalar ledger and cap20 preservation checks, no worlds."""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import write,manifest,verify_manifest,sha
from run_dao_synthetic import gate,OUT
from verify_dao_integrity import verify
from spatial_memory.discovery_reference import footprint_reference,scalar_counts
from spatial_memory.discovery_observation import DiscoveryController


def main():
    gate();target=OUT/'verification';target.mkdir(parents=True,exist_ok=False)
    integrity=verify();verified=0
    for folder in ('prepared','prepared_prefreeze_serialization','retrospective',
                   'retrospective_prefreeze_labels','synthetic','analysis'):
        verified+=verify_manifest(OUT/folder)
    states={s['id']:s for s in json.loads((OUT/'prepared/fixtures.json').read_text())}
    rows=json.loads((OUT/'synthetic/decisions.json').read_text());seen=set()
    for row in rows:
        ident=row['id'];key=(ident,row['mode']);assert key not in seen;seen.add(key)
        s=states[ident];ref=footprint_reference(s['grid'],tuple(s['position']),s['yaw'])
        for name in ('frontier','optimistic'):
            assert row['detail'][name]==scalar_counts(s['grid'],s['last_observed'],s['step'],ref[name],s['route'] or ())
        assert row['detail']['sample_visits']<=4941
    assert len(rows)==len(seen)==432 and len(states)==48
    caps=[]
    for mode in ('dao_veto','dao_trigger','dao_route','dao_combined'):
        initial=np.full((15,15),-1,dtype=np.int8);initial[7,7]=0
        c=DiscoveryController(initial,mode=mode,max_observations=20)
        grants=[]
        for step in range(1,81):
            c.set_navigation_context(goal=(12,7),yaw=0.)
            decision=c.decide(step,(7,7))
            if decision['observation_granted']:
                c.refresh(np.full(initial.shape,-1,dtype=np.int8),step);grants.append(step)
            assert c.used==1+len(grants)<=20 and np.array_equal(c.memory.grid,initial)
        assert c.used==20 and len(grants)==19 and c.denied>0
        try:c.refresh(initial,81)
        except RuntimeError:pass
        else:raise AssertionError('Unauthorized cap20 refresh')
        caps.append({'mode':mode,'initial_inclusive_used':c.used,'noninitial_grants':len(grants),
                     'denied_requests':c.denied,'unchanged_last_write_memory':True})
    binding=json.loads((OUT/'protocol_binding.json').read_text());old=json.loads((OUT/'protocol_binding_v1.json').read_text())
    changed=[p for p,h in old['source_sha256'].items() if binding['source_sha256'].get(p)!=h]
    assert changed==['scripts/run_dao_synthetic.py']
    assert old['fixtures_sha256']==binding['fixtures_sha256']
    # Confirm original DAO bytes also match the initial prospective commit.
    import subprocess,hashlib
    for p in ('src/spatial_memory/discovery_observation.py','src/spatial_memory/discovery_reference.py','scripts/dao_fixtures.py'):
        assert hashlib.sha256(subprocess.check_output(['git','show',f'11e6568:{p}'],cwd=ROOT)).hexdigest()==sha(ROOT/p)
    write(target/'integrity.json',{**integrity,'formal_rows_independently_rechecked':len(rows),
        'stage_manifest_files_checked':verified,'bound_sources':len(binding['source_sha256']),
        'cap20_checks':caps,'serialization_repair_changed_only_harness':True,
        'original_policy_geometry_fixtures_unchanged':True,
        'formal_process_invocations':2,'incomplete_serialization_invocations':1,
        'completed_formal_suites':1,'postprocessing_source_sha256':sha(__file__)})
    manifest(target);print('PASS: 432 scalar ledger checks, four initial-inclusive cap20 contracts, source and original-data integrity.')
if __name__=='__main__':main()
