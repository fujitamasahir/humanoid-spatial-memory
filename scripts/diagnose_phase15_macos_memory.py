"""Bounded disposable-process diagnostics; never relaxes production admission.

Only child-local limits are changed. The 64-MiB slack example demonstrates VM
allocation rejection, not a 512-MiB RSS limit. No historical graph is loaded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
LIMIT=536870912
CHILD=r'''
import ctypes,json,mmap,os,resource,sys
lib=ctypes.CDLL(None,use_errno=True)
class Limits(ctypes.Structure):_fields_=[('soft',ctypes.c_uint64),('hard',ctypes.c_uint64)]
class Info(ctypes.Structure):_fields_=[('virtual_bytes',ctypes.c_uint64),('rss_bytes',ctypes.c_uint64),('peak_bytes',ctypes.c_uint64),('tail',ctypes.c_int*6)]
lib.getrlimit.argtypes=[ctypes.c_int,ctypes.POINTER(Limits)]
lib.setrlimit.argtypes=[ctypes.c_int,ctypes.POINTER(Limits)]
lib.task_info.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint)]
actual=Limits();assert lib.getrlimit(resource.RLIMIT_AS,ctypes.byref(actual))==0
info=Info();count=ctypes.c_uint(ctypes.sizeof(info)//4)
task=ctypes.c_uint.in_dll(lib,'mach_task_self_').value
assert lib.task_info(task,20,ctypes.byref(info),ctypes.byref(count))==0
mode=sys.argv[1];limit=536870912
soft=info.virtual_bytes+64*1024*1024 if mode=='large-control' else limit
hard=actual.hard if mode=='soft-only' else soft
result=dict(mode=mode,uid=os.getuid(),initial_python=list(resource.getrlimit(resource.RLIMIT_AS)),
 initial_libc=[actual.soft,actual.hard],requested=[soft,hard],soft_le_hard=soft<=hard,
 inherited_hard_allows_request=hard<=actual.hard,mach_virtual_bytes=info.virtual_bytes,
 mach_rss_bytes=info.rss_bytes,rlimit_as_equals_rss=resource.RLIMIT_AS==resource.RLIMIT_RSS)
if mode=='footprint-api':
 f=lib.task_set_phys_footprint_limit
 f.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.POINTER(ctypes.c_int)];f.restype=ctypes.c_int
 old=ctypes.c_int(-999);code=f(task,512,ctypes.byref(old))
 lib.mach_error_string.argtypes=[ctypes.c_int];lib.mach_error_string.restype=ctypes.c_char_p
 result.update(api='task_set_phys_footprint_limit',requested_mib=512,mach_return=code,
               mach_message=lib.mach_error_string(code).decode(),old_limit=old.value)
else:
 # First Python then direct libc in the same disposable child. If Python fails
 # and libc fails identically, Python's local argument validation is not cause.
 if mode in ('python','limited-c3'):
  try:resource.setrlimit(resource.RLIMIT_AS,(soft,hard));result['python_success']=True
  except Exception as error:result.update(python_success=False,python_error=repr(error))
 ctypes.set_errno(0)
 rc=lib.setrlimit(resource.RLIMIT_AS,ctypes.byref(Limits(soft,hard)))
 result.update(libc_return=rc,errno=ctypes.get_errno(),errno_text=os.strerror(ctypes.get_errno()))
 result['after']=list(resource.getrlimit(resource.RLIMIT_AS))
 if mode=='limited-c3':
  # On this host the worker cannot establish its cap, so never import the native
  # code under an unlimited profile and describe it as a capped success.
  result['native_c3_executed']=False
  result['native_c3_under_512_mib']='BLOCKED' if rc else 'NEEDS_SEPARATE_REVALIDATION'
 if mode in ('python-touched','native-touched','mmap-touched'):
  size=64*1024*1024;result['allocation_has_enforced_512_mib_cap']=(rc==0)
  before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
  try:
   if mode=='python-touched':
    block=bytearray(size)
    for i in range(0,size,4096):block[i]=1
   elif mode=='native-touched':
    lib.malloc.argtypes=[ctypes.c_size_t];lib.malloc.restype=ctypes.c_void_p
    ptr=lib.malloc(size)
    if not ptr:raise MemoryError('malloc refused')
    ctypes.memset(ptr,1,size)
   else:
    block=mmap.mmap(-1,size)
    for i in range(0,size,4096):block[i]=1
   result['allocated_touched_bytes']=size
  except (MemoryError,OSError) as error:result['allocation_error']=repr(error)
  result.update(rss_before_bytes=before,rss_after_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
print(json.dumps(result),flush=True)
'''
MODES=('python','libc','soft-only','large-control','limited-c3','python-touched',
       'native-touched','mmap-touched','footprint-api')


def run_child(mode):
    if mode not in MODES:raise ValueError('Unknown isolated probe')
    completed=subprocess.run([sys.executable,'-I','-c',CHILD,mode],
        capture_output=True,text=True,timeout=15,check=True)
    return json.loads(completed.stdout)


def collect(native_probe):
    if sys.platform!='darwin' or platform.machine()!='arm64':raise ValueError('macOS ARM64 only')
    before_parent=__import__('resource').getrlimit(__import__('resource').RLIMIT_AS)
    rows=[run_child(mode) for mode in MODES]
    native=[]
    for mode in ('absolute','slack'):
        native.append(json.loads(subprocess.check_output([str(native_probe.resolve()),mode],text=True,timeout=10)))
    after_parent=__import__('resource').getrlimit(__import__('resource').RLIMIT_AS)
    if before_parent!=after_parent:raise ValueError('Parent limits changed')
    return dict(platform=platform.platform(),python=sys.version,parent_limits_unchanged=True,
        probes=rows,minimal_native_probes=native,native_probe_sha256=hashlib.sha256(native_probe.read_bytes()).hexdigest(),
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (Path(__file__),ROOT/'scripts/native/phase15_macos_vm_probe.c')},
        hard_512_mib_gate='BLOCKED',production_enabled=False,
        scope='Same unprivileged sandbox only; no unsandboxed baseline, no elevated privilege, no host-wide limit changes',
        interpretation='Kernel EINVAL for a below-existing-VM RLIMIT_AS, not invalid soft/hard ordering. Larger limit succeeds; RSS and VM are distinct.',
        caveat='The diagnostic does not itself authorize a new resource policy or native API entitlement')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-probe',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Preserve previous memory evidence')
    result=collect(args.native_probe)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as handle:json.dump(result,handle,indent=2,sort_keys=True);handle.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
