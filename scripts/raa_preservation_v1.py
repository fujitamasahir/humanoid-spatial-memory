"""Read-only prior Phase2 evidence manifests plus original admitted FIT integrity."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from c_v21_common import sha
from verify_dao_integrity import verify


def verify_prior():
    base=verify();cache={};checked=0;manifests=[];issues=[];opaque=[]
    for p in sorted((ROOT/'results/phase2_mujoco').rglob('artifact_manifest.json')):
        if any(part.startswith('raa_') for part in p.relative_to(ROOT).parts):continue
        doc=json.loads(p.read_text());items=doc if isinstance(doc,list) else doc.get('files',[]) if isinstance(doc,dict) else []
        if not isinstance(items,list) or not items or not all(isinstance(v,dict) and {'path','sha256'}<=v.keys() for v in items):
            opaque.append(str(p.relative_to(ROOT)));continue
        manifests.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
        for item in items:
            rel=Path(item['path'])
            if rel.is_absolute() or '..' in rel.parts:issues.append({'manifest':str(p.relative_to(ROOT)),'path':str(rel),'error':'unsafe_record_not_opened'});continue
            target=p.parent/rel
            try:
                if target not in cache:cache[target]=(target.stat().st_size,sha(target))
                size,h=cache[target]
                assert h==item['sha256'] and ('bytes' not in item or size==item['bytes'])
                checked+=1
            except (FileNotFoundError,AssertionError):issues.append({'manifest':str(p.relative_to(ROOT)),'path':str(rel),'error':'preexisting_manifest_mismatch_or_missing'})
    base.update(prior_manifest_records_checked=checked,unique_prior_files_hashed=len(cache),
        prior_manifests=manifests,nonstandard_manifests_preserved=opaque,prior_manifest_issues=issues)
    return base
if __name__=='__main__':
    value=verify_prior();print(json.dumps({k:v for k,v in value.items() if k!='prior_manifests'},indent=2))
