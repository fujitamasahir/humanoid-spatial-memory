"""Child-only resource diagnostics. No registered RNG or graph generation."""
import importlib.util
import json
import platform
from pathlib import Path
import resource
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
pytestmark=pytest.mark.skipif(sys.platform!='darwin' or platform.machine()!='arm64',reason='Target macOS ARM64 diagnosis')
spec=importlib.util.spec_from_file_location('memory_diagnosis',ROOT/'scripts/diagnose_phase15_macos_memory.py')
diag=importlib.util.module_from_spec(spec);spec.loader.exec_module(diag)


@pytest.fixture(scope='session')
def probe(tmp_path_factory):
    binary=tmp_path_factory.mktemp('minimal-macos-vm')/'probe'
    subprocess.run(['/usr/bin/clang','-arch','arm64','-O2','-Wall','-Wextra','-Werror',
                    str(ROOT/'scripts/native/phase15_macos_vm_probe.c'),'-o',str(binary)],check=True,capture_output=True)
    return binary


@pytest.mark.parametrize('mode',['python','libc','soft-only','limited-c3'])
def test_kernel_rejects_below_existing_vm_not_bad_limit_order(mode):
    parent=resource.getrlimit(resource.RLIMIT_AS)
    r=diag.run_child(mode)
    assert r['initial_python']==r['initial_libc']==[resource.RLIM_INFINITY if resource.RLIM_INFINITY>=0 else 2**63-1]*2
    assert r['requested'][0]==536870912 and r['soft_le_hard'] and r['inherited_hard_allows_request']
    assert r['mach_virtual_bytes']>536870912>r['mach_rss_bytes']
    assert r['libc_return']==-1 and r['errno']==22 and r['after']==r['initial_python']
    if mode in ('python','limited-c3'):
        assert not r['python_success'] and 'current limit exceeds maximum limit' in r['python_error']
    if mode=='limited-c3':assert r['native_c3_executed'] is False
    assert resource.getrlimit(resource.RLIMIT_AS)==parent


def test_larger_vm_limit_succeeds_in_same_execution_environment():
    r=diag.run_child('large-control')
    assert r['requested']==[r['mach_virtual_bytes']+64*1024*1024]*2
    assert r['libc_return']==r['errno']==0 and r['after']==r['requested']
    assert r['requested'][0]>536870912  # absolutely NOT a 512-MiB RSS cap


@pytest.mark.parametrize('mode',['python-touched','native-touched','mmap-touched'])
def test_bounded_touched_allocations_do_not_claim_enforcement(mode):
    r=diag.run_child(mode)
    assert r['libc_return']==-1 and r['errno']==22
    assert r['allocation_has_enforced_512_mib_cap'] is False
    assert r['allocated_touched_bytes']==64*1024*1024
    assert r['rss_after_bytes']-r['rss_before_bytes']>32*1024*1024


def test_footprint_api_denied_without_elevated_privileges():
    r=diag.run_child('footprint-api')
    assert r['requested_mib']==512 and r['mach_return']==8
    assert r['old_limit']==-999 and 'no access' in r['mach_message']


@pytest.mark.parametrize('mode',['absolute','slack'])
def test_minimal_native_vm_worker_rules_out_python_startup_overhead(probe,mode):
    r=json.loads(subprocess.check_output([str(probe),mode],text=True,timeout=10))
    assert r['virtual_bytes']>536870912>r['rss_bytes']
    if mode=='absolute':
        assert r['requested']==[536870912]*2 and r['setrlimit_result']==-1 and r['errno']==22
        assert r['after']==r['before']
    else:
        assert r['setrlimit_result']==r['errno']==0 and r['requested']==r['after']
        assert r['requested'][0]==r['virtual_bytes']+64*1024*1024
        assert not r['extra_128_mib_mapping_succeeded'] and r['mapping_errno']==12


def test_production_gate_remains_closed_and_previous_certificate_pin_unchanged():
    import hashlib
    from spatial_memory.phase15_nauty_macos import MacBackend
    from spatial_memory.phase15_nauty import BackendFailure
    from spatial_memory.phase15_bprime_coordinator import PRODUCTION_GENERATION_ENABLED
    assert PRODUCTION_GENERATION_ENABLED is False
    with pytest.raises(BackendFailure,match='BLOCKED'):MacBackend()
    pin=json.loads((ROOT/'configs/phase15_nauty_macos_validation.json').read_text())
    for path,expected in pin['artifact_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected
