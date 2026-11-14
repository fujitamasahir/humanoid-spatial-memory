"""Record immutable source and robot-model fingerprints for the showcase."""
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FILES=(
 'src/spatial_memory/scheduling.py','src/spatial_memory/evaluation.py',
 'src/spatial_memory/simulation.py','src/spatial_memory/navigation.py',
 'src/spatial_memory/mujoco_navigation.py','src/spatial_memory/mujoco_perception.py',
 'src/spatial_memory/emergency_safety.py','src/spatial_memory/pedestrian_tracking.py',
 'scripts/phase2_mujoco_navigation.py',
 'scripts/evaluate_phase2_61ray_emergency_safety_full_288.py')
def digest(b): return hashlib.sha256(b).hexdigest()
def main():
 assets=sorted(p for p in (ROOT/'third_party/unitree_g1').rglob('*') if p.is_file())
 binding={'schema':'ai-day-2026-frozen-runtime-v1',
  'research_base_commit':'b6cb1fa233fbcd30b7ea26e88b865a69db96b91e',
  'algorithm_policies':['periodic','age','uncertainty'],
  'frozen_source_files':{name:digest((ROOT/name).read_bytes()) for name in FILES},
  'unitree_g1_upstream_commit':(ROOT/'third_party/unitree_g1.UPSTREAM_COMMIT').read_text().strip(),
  'unitree_g1_files':{p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in assets}}
 out=Path(__file__).resolve().parent/'data'/'runtime_binding.json'
 out.write_text(json.dumps(binding,sort_keys=True,indent=2)+'\n')
 print(json.dumps({'path':str(out.relative_to(ROOT)),'source_files':len(FILES),'g1_files':len(assets),'sha256':digest(out.read_bytes())},indent=2))
if __name__=='__main__':main()
