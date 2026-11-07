"""Evaluator-only development manifests, disjoint by realized environment.

Generation never executes a policy. Assessment records are not runnable in 1.4A.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from .simulation import Scenario
from .scenarios import generate_scenario
from .robustness import FAMILIES, generate_robustness, truth_audit


def canonical_environment(scenario):
    data=asdict(scenario)
    for field in ('name','split'):
        data.pop(field)
    # Static sets have no order; paths and same-time event order are meaningful.
    data['walls']=sorted(set(map(tuple,data['walls'])))
    data['obstacles']=sorted(set(map(tuple,data['obstacles'])))
    return data


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def environment_hash(scenario):
    return digest(canonical_environment(scenario))


def layout_hash(scenario):
    data=canonical_environment(scenario)
    return digest({key:data[key] for key in ('width','height','walls','start','goal')})


def historical_exclusions(root):
    """Read development-only historical records; no held-out configuration access."""
    hashes,seeds=set(),set()
    for phase in ('phase1_1','phase1_2','phase1_3','representative'):
        directory=Path(root)/'results'/phase
        for path in sorted(directory.rglob('results.json')):
            payload=json.loads(path.read_text(encoding='utf-8-sig'))
            seeds.update(r['seed'] for r in payload.get('episodes',[]))
            for record in payload.get('realized_scenarios',[]):
                scenario=Scenario.from_dict(record['scenario'])
                if scenario.split != 'development':
                    raise ValueError('Historical exclusion input must be development only')
                hashes.add(environment_hash(scenario))
    # Phase 1.0 may have configuration-only truth rather than realized records.
    for name in ('development.json','development_phase1_1.json','development_phase1_2.json'):
        config=json.loads((Path(root)/'configs'/name).read_text(encoding='utf-8-sig'))
        for seed in config['seeds']:
            seeds.add(seed)
            for template in config['scenarios']:
                hashes.add(environment_hash(generate_scenario(template,seed)))
    return hashes,seeds


def build_manifests(excluded_hashes=(), excluded_seeds=(), *, families=FAMILIES):
    """Frozen 35/70 split; optional family subset is for unit tests only."""
    if not families or len(set(families))!=len(families) or any(f not in FAMILIES for f in families):
        raise ValueError('Invalid development families')
    seen=set(excluded_hashes)
    prior_seeds=set(excluded_seeds)
    manifests={}
    for partition,start,count in (('tuning',10000,5),('assessment',20000,10)):
        accepted,rejected=[],[]
        for family in families:
            found=0
            for seed in range(start,start+10000):
                if seed in prior_seeds:
                    rejected.append(dict(family=family,seed=seed,reason='historical_seed'))
                    continue
                scenario=generate_robustness(family,seed)
                fingerprint=environment_hash(scenario)
                if fingerprint in seen:
                    rejected.append(dict(family=family,seed=seed,reason='duplicate_environment'))
                    continue
                try:
                    audit=truth_audit(scenario,40)
                except ValueError as error:
                    rejected.append(dict(family=family,seed=seed,reason='topology',detail=str(error)))
                    continue
                seen.add(fingerprint)
                accepted.append(dict(partition=partition,family=family,seed=seed,
                    environment_sha256=fingerprint,layout_sha256=layout_hash(scenario),
                    scenario=asdict(scenario),topology=audit))
                found+=1
                if found==count:
                    break
            if found!=count:
                raise ValueError('Candidate limit exhausted; protocol amendment required')
        manifests[partition]=dict(partition=partition,split='development',horizon=40,
            records=accepted,rejections=rejected,outcomes_generated=False,
            excluded_environment_hashes=sorted(set(excluded_hashes)),excluded_seeds=sorted(prior_seeds))
    return manifests


def validate_manifest(manifest):
    if manifest['split']!='development' or manifest['partition'] not in {'tuning','assessment'}:
        raise ValueError('Invalid development partition')
    seen=set()
    for record in manifest['records']:
        scenario=Scenario.from_dict(record['scenario'])
        fingerprint=environment_hash(scenario)
        if (scenario.split!='development' or record['partition']!=manifest['partition']
            or record['environment_sha256']!=fingerprint or fingerprint in seen
            or record['layout_sha256']!=layout_hash(scenario)):
            raise ValueError('Manifest hash/uniqueness/partition violation')
        if fingerprint in manifest.get('excluded_environment_hashes',[]) or record['seed'] in manifest.get('excluded_seeds',[]):
            raise ValueError('Excluded historical realization')
        if not (10000 <= record['seed'] < 20000 if manifest['partition']=='tuning' else 20000 <= record['seed'] < 30000):
            raise ValueError('Invalid seed namespace')
        regenerated=generate_robustness(record['family'],record['seed'])
        if environment_hash(regenerated)!=fingerprint:
            raise ValueError('Scenario/seed reproduction mismatch')
        seen.add(fingerprint)
        if truth_audit(scenario,manifest['horizon'])!=record['topology']:
            raise ValueError('Manifest topology mismatch')
    return seen


def require_smoke_record(record):
    if record.get('partition')!='smoke':
        raise ValueError('Tuning and assessment execution are not authorized in Phase 1.4A')
    scenario=Scenario.from_dict(record['scenario'])
    if scenario.split!='development':
        raise ValueError('Held-out execution is reserved')
    return scenario
