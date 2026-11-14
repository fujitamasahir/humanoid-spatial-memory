"""Read-only migration audit of existing FIT-only stores and frozen evidence."""
from __future__ import annotations
import gzip,hashlib,importlib.metadata,json,platform,subprocess,sys
from pathlib import Path
from c_v21_common import ROOT,OUT,BASE_COMMIT,write,sha,canonical,manifest,verify_manifest,commit
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
import phase2_mujoco_navigation as nav
import evaluate_c_v2_candidate_coverage_fit72 as frozen
from spatial_memory.phase15_bprime_protocol import digest


def main():
    target=OUT/'environment';target.mkdir(parents=True,exist_ok=False)
    pins={line.split('==')[0]:line.split('==')[1] for line in (ROOT/'requirements.txt').read_text().splitlines() if '==' in line}
    versions={n:importlib.metadata.version(n) for n in pins}
    if versions!=pins or sys.version_info[:2]!=(3,12):raise RuntimeError('Python/dependency pins mismatch')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    if branch!='phase2/mujoco-proxy-pilot' or Path(sys.prefix).resolve()!=(ROOT/'.venv').resolve():raise RuntimeError('Wrong branch/venv')
    integrity=frozen.verify_original_data_integrity()
    stores=[];all_ids=set()
    for s in integrity['stores']:
        directory=ROOT/s['path'];records={}
        for p in sorted((directory/'records').glob('*.json.gz')):
            body=json.loads(gzip.decompress(p.read_bytes()));ident=body['identity'];payload=body['payload']
            if payload.get('partition')!='fit':raise RuntimeError('Unexpected non-FIT material; stop')
            if ident in records or ident in all_ids or p.name!=hashlib.sha256(ident.encode()).hexdigest()+'.json.gz' or body['payload_sha256']!=digest(payload):raise RuntimeError('Checkpoint identity/hash failure')
            if payload['identity']!=ident:raise RuntimeError('Payload identity mismatch')
            records[ident]=payload;all_ids.add(ident)
        seen=set();seqs=set()
        receipts=sorted((directory/'recovered').glob('attempt-*.json'))
        for p in receipts:
            receipt=json.loads(p.read_text());job=receipt['job'];ident=job['identity'];seq=job['sequence']
            if ident in seen or seq in seqs or ident not in records or receipt['run_id']!=s['run_id'] or p.name!=f'attempt-{seq+1}.json':raise RuntimeError('Receipt identity/run/sequence failure')
            if any(records[ident].get(k)!=job.get(k) for k in ('index','mechanism','partition')):raise RuntimeError('Receipt/payload mismatch')
            seen.add(ident);seqs.add(seq)
        if seen!=set(records) or len(records)!=s['records'] or len(receipts)!=s['receipts']:raise RuntimeError('Receipt pairing mismatch')
        stores.append(s)
    if len(all_ids)!=2907:raise RuntimeError('Expected exactly 2,907 original pairs')
    assets=[]
    for p in sorted((ROOT/'third_party/unitree_g1').rglob('*')):
        if p.is_file() and p.suffix.lower() in ('.xml','.stl'):
            rel=p.relative_to(ROOT).as_posix();old=subprocess.check_output(['git','show',BASE_COMMIT+':'+rel],cwd=ROOT)
            if hashlib.sha256(old).hexdigest()!=sha(p):raise RuntimeError('G1 asset changed')
            assets.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha(p)})
    dirs=[frozen.FIT,ROOT/'results/phase2_mujoco/c_v2d_topology_v1',ROOT/'results/phase2_mujoco/c_v2d_topology_v1/fit72_descriptive_screen']
    evidence=[{'directory':str(d.relative_to(ROOT)),'files_verified':verify_manifest(d)} for d in dirs]
    write(target/'verification.json',{'status':'PASS','source_commit':commit(),'branch':branch,'platform':platform.platform(),'machine':platform.machine(),'python':sys.version,'executable':sys.executable,'venv':sys.prefix,'dependencies':versions,'hardware':{'model':'Mac13,1','chip':'Apple M1 Max','memory_bytes':34359738368,'physical_cpus':10,'logical_cpus':10,'source':'sysctl -n hw.model hw.memsize hw.ncpu hw.physicalcpu hw.logicalcpu machdep.cpu.brand_string (outside sandbox)'},'os':subprocess.check_output(['sw_vers'],text=True),'original_checkpoint_receipt_pairs':len(all_ids),'stores':stores,'protected_phase15':nav.verify_preserved_prefix(),'admitted_fit_worlds':len(nav.admitted_worlds()),'g1_assets':assets,'frozen_evidence':evidence,'access_scope':'Only existing fit directories; no generation or reserved reads','baseline_replay':'PENDING_SEPARATE_SAME_MACHINE_REPLAY'})
    manifest(target);print('PASS: 2907 pairs, 836 protected files, pins, G1 assets, FIT evidence')
if __name__=='__main__':main()
