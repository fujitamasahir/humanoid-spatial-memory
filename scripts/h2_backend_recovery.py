"""Pre-draw native-backend restoration; no generation law/model changes."""
import json,sys,subprocess
from h2_final_common import *
from spatial_memory.phase15_macos_monitored import MonitoredBackend
from spatial_memory.phase15_topology import Graph
PIN=OUT/'backend/pin.json'
def main():
    # Original frozen gate remains mandatory. Restoration itself also committed.
    from run_h2_final import gate
    gate()
    for p in [Path(__file__).resolve(),PIN,ROOT/'docs/h2_backend_recovery_v1_1.md']:
        assert subprocess.check_output(['git','show','HEAD:'+str(p.relative_to(ROOT))],cwd=ROOT)==p.read_bytes()
    pin=json.loads(PIN.read_text());assert all(sha(ROOT/p)==h for p,h in pin['artifact_sha256'].items())
    import h2_generate_maps as gen
    backend=MonitoredBackend(pin_path=PIN);checked=0
    try:
        for p in gen.nav.checkpoints():
            t=p.get('topology',{})
            if 'matrix' not in t or 'exact' not in t:continue
            key=backend.exact_certificate(Graph(tuple(map(tuple,t['matrix']))))
            assert list(key)==t['exact'],p['identity'];checked+=1
        assert checked>=36
    finally:backend.close()
    write(OUT/'backend/compatibility.json',{'status':'PASS_EXACT_ARCHIVED_GRAPH_KEYS','keys_checked':checked,'pin_sha256':sha(PIN),'scope':'Public authorized FIT checkpoints only; no new map drawn during restoration','original_backend_missing':True,'original_native_hash_not_claimed':True})
    manifest(OUT/'backend')
    class Restored(MonitoredBackend):
        def __init__(self):super().__init__(pin_path=PIN)
    gen.MonitoredBackend=Restored
    gen.main()
if __name__=='__main__':main()
