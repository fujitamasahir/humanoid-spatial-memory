"""Standalone, bounded macOS RSS probe. It never imports research code.

The full mode tests only whether independently measured RSS above the frozen
512 MiB threshold is rejected. It does not change the Phase 1.5 policy.
"""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import select
import subprocess
import sys
import time

LIMIT = 536_870_912
SAMPLE_SECONDS = 0.010
FULL_ALLOCATIONS = (576, 640, 704)  # MiB; <= 8.6% of an 8 GiB machine
CHILD_TIMEOUT_SECONDS = 20
REAP_TIMEOUT_SECONDS = 2
CHUNK_BYTES = 1024 * 1024

CHILD = r'''import json,mmap,os,resource,select,sys,time
size=int(sys.argv[1]);chunk=1024*1024;area=None
try:
    area=mmap.mmap(-1,size,access=mmap.ACCESS_WRITE)
    for offset in range(0,size,chunk):
        count=min(chunk,size-offset)
        area[offset:offset+count]=os.urandom(count)
    print(json.dumps({'event':'ready','pid':os.getpid(),'allocated_bytes':size,
        'bytes_written':size,'worker_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'peak_unit':'bytes','compressed_memory_bytes':None,
        'compressed_memory_status':'not directly exposed by resource.getrusage'}),flush=True)
    ready,_,_=select.select([sys.stdin],[],[],10)
    if not ready:raise TimeoutError('parent report command timeout')
    if sys.stdin.readline()!='REPORT\n':raise ValueError('invalid parent command')
    print(json.dumps({'event':'report','worker_peak_rss_bytes':
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'peak_unit':'bytes'}),flush=True)
finally:
    if area is not None:area.close()
'''


class ProbeError(RuntimeError):
    pass


class RusageInfo(ctypes.Structure):
    # Darwin rusage_info_v2: 16-byte UUID followed by 18 uint64 values.
    _fields_ = [('uuid', ctypes.c_ubyte * 16), ('values', ctypes.c_uint64 * 18)]


def resident_bytes(pid):
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    lib.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    info = RusageInfo()
    if lib.proc_pid_rusage(pid, 2, ctypes.byref(info)) != 0:
        raise ProbeError(f'libproc proc_pid_rusage failed, errno={ctypes.get_errno()}')
    # ri_resident_size is field 6 of rusage_info_v2, in bytes.
    value = int(info.values[6])
    if value <= 0:
        raise ProbeError('libproc returned invalid current resident RSS')
    return value


def measured_decision(current_samples, lifetime_peak):
    """Mirror the frozen measured-RSS acceptance check; invalid evidence rejects."""
    if (not current_samples or any(type(v) is not int or v <= 0 for v in current_samples)
            or type(lifetime_peak) is not int or lifetime_peak <= 0):
        return 'REJECT_INVALID_OR_MISSING_MEASUREMENT'
    if lifetime_peak < max(current_samples):
        return 'REJECT_CONFLICTING_RSS_MEASUREMENTS'
    if max(current_samples) > LIMIT or lifetime_peak > LIMIT:
        return 'REJECT_RESOURCE_EXCESS'
    return 'MEASUREMENTS_WITHIN_THRESHOLD'


def evidence_self_check():
    invalid = [
        measured_decision([], 1),
        measured_decision([1], None),
        measured_decision([1], -1),
        measured_decision([1], True),
        measured_decision([LIMIT + 1], LIMIT + 1),
    ]
    expected = [
        'REJECT_INVALID_OR_MISSING_MEASUREMENT',
        'REJECT_INVALID_OR_MISSING_MEASUREMENT',
        'REJECT_INVALID_OR_MISSING_MEASUREMENT',
        'REJECT_INVALID_OR_MISSING_MEASUREMENT',
        'REJECT_RESOURCE_EXCESS',
    ]
    if invalid != expected:
        raise ProbeError('synthetic evidence decision self-check failed')
    return dict(cases=len(expected), passed=len(expected), failed=0,
                above_threshold_result=invalid[-1], missing_invalid_results=invalid[:-1])


def run_child(allocation_mib):
    allocation = allocation_mib * 1024 * 1024
    process = subprocess.Popen(
        [sys.executable, '-I', '-c', CHILD, str(allocation)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    samples = []
    child_events = []
    started = time.monotonic()
    ready = None
    report = None
    cleanup = dict(kill_sent=False, reaped=False, returncode=None)
    failure = None
    result = None
    try:
        deadline = started + CHILD_TIMEOUT_SECONDS
        while time.monotonic() < deadline and ready is None:
            if process.poll() is not None:
                raise ProbeError(f'child exited before ready; rc={process.returncode}')
            samples.append(resident_bytes(process.pid))
            readable, _, _ = select.select([process.stdout], [], [], SAMPLE_SECONDS)
            if readable:
                line = process.stdout.readline()
                if not line:
                    raise ProbeError('child closed stdout before ready')
                event = json.loads(line)
                child_events.append(event)
                if event.get('event') != 'ready':
                    raise ProbeError('unexpected child event before ready')
                ready = event
        if ready is None:
            raise ProbeError('child ready timeout')

        # Keep sampling while the allocation is held; then request its peak.
        process.stdin.write('REPORT\n')
        process.stdin.flush()
        while time.monotonic() < deadline and report is None:
            samples.append(resident_bytes(process.pid))
            readable, _, _ = select.select([process.stdout], [], [], SAMPLE_SECONDS)
            if readable:
                line = process.stdout.readline()
                if not line:
                    raise ProbeError('child closed stdout before report')
                event = json.loads(line)
                child_events.append(event)
                if event.get('event') == 'report':
                    report = event
                else:
                    raise ProbeError('unexpected child report event')
        if report is None:
            raise ProbeError('child report timeout')
        process.wait(timeout=REAP_TIMEOUT_SECONDS)
        cleanup.update(reaped=True, returncode=process.returncode, kill_sent=False)
        peak = report.get('worker_peak_rss_bytes')
        if report.get('peak_unit') != 'bytes':
            peak = None
        decision = measured_decision(samples, peak)
        if (ready.get('pid') != process.pid or ready.get('allocated_bytes') != allocation
                or ready.get('bytes_written') != allocation):
            decision = 'REJECT_INVALID_OR_MISSING_MEASUREMENT'
        if (type(ready.get('worker_peak_rss_bytes')) is not int
                or report.get('worker_peak_rss_bytes', 0) < ready.get('worker_peak_rss_bytes', 0)):
            decision = 'REJECT_CONFLICTING_RSS_MEASUREMENTS'
        if cleanup['returncode'] != 0:
            decision = 'REJECT_CHILD_EXIT_FAILURE'
        result = dict(allocation_limit_mib=allocation_mib,
                    allocated_bytes=ready.get('allocated_bytes'),
                    bytes_written=ready.get('bytes_written'),
                    parent_current_rss_samples_bytes=samples,
                    parent_current_rss_peak_bytes=max(samples, default=None),
                    worker_lifetime_peak_rss_bytes=peak,
                    worker_peak_unit=report.get('peak_unit'),
                    compressed_memory_bytes=None,
                    compressed_memory_status=ready.get('compressed_memory_status'),
                    decision=decision, child_events=child_events,
                    elapsed_seconds=time.monotonic()-started, cleanup=cleanup)
    except Exception as error:
        failure = f'{type(error).__name__}: {error}'
    finally:
        if process.poll() is None:
            cleanup['kill_sent'] = True
            process.kill()
            try:
                process.wait(timeout=REAP_TIMEOUT_SECONDS)
                cleanup.update(reaped=True, returncode=process.returncode)
            except subprocess.TimeoutExpired as error:
                failure = f'cleanup timeout after kill: {error}'
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
    if failure is not None:
        return dict(allocation_limit_mib=allocation_mib,
                    allocated_bytes=ready.get('allocated_bytes') if ready else None,
                    bytes_written=ready.get('bytes_written') if ready else None,
                    parent_current_rss_samples_bytes=samples,
                    parent_current_rss_peak_bytes=max(samples, default=None),
                    worker_lifetime_peak_rss_bytes=None,
                    compressed_memory_bytes=None,
                    decision='REJECT_PROBE_OR_EVIDENCE_FAILURE', error=failure,
                    child_events=child_events, elapsed_seconds=time.monotonic()-started,
                    cleanup=cleanup)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--self-test', action='store_true', help='run mechanics only with 16 MiB')
    group.add_argument('--full', action='store_true', help='run bounded 576/640/704 MiB RSS ladder')
    parser.add_argument('--output', type=Path, required=True, help='new JSON report path')
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists():
        parser.error(f'report already exists; preserve existing evidence: {output}')
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        parser.error('macOS arm64 is required')

    lock_path = Path('/tmp') / f'phase15-live-rss-{os.getuid()}.lock'
    lock = lock_path.open('a+')
    try:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('another live RSS probe is already running')

        checks = evidence_self_check()
        trials = []
        sizes = (16,) if args.self_test else FULL_ALLOCATIONS
        for mib in sizes:
            trial = run_child(mib)
            trials.append(trial)
            if args.full and trial['decision'] == 'REJECT_RESOURCE_EXCESS':
                break
            if trial['decision'] not in ('MEASUREMENTS_WITHIN_THRESHOLD', 'REJECT_RESOURCE_EXCESS'):
                break
        observed = any(t['decision'] == 'REJECT_RESOURCE_EXCESS' for t in trials)
        clean = all(t['cleanup']['reaped'] and t['cleanup']['returncode'] == 0 for t in trials)
        if args.self_test:
            status = 'PASS_MECHANICS_ONLY' if clean and trials[0]['decision']=='MEASUREMENTS_WITHIN_THRESHOLD' else 'FAIL'
        elif observed and clean:
            status = 'PASS_ABOVE_THRESHOLD_REJECTED'
        elif not clean or any(t['decision'] not in ('MEASUREMENTS_WITHIN_THRESHOLD','REJECT_RESOURCE_EXCESS') for t in trials):
            status = 'FAIL_EVIDENCE_OR_CLEANUP'
        else:
            status = 'NOT_DEMONSTRATED_WITHIN_SAFE_MAXIMUM'
        script_path = Path(__file__).resolve()
        report = dict(schema=1, status=status,
            mode='self-test' if args.self_test else 'full-live-rss',
            created_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            host=dict(platform=platform.platform(), architecture=platform.machine(), python=sys.version),
            policy=dict(threshold_bytes=LIMIT, production_deadline_seconds=5,
                diagnostic_child_timeout_seconds=CHILD_TIMEOUT_SECONDS,
                sample_interval_seconds=SAMPLE_SECONDS,
                production_deadline_and_policy_unchanged=True),
            safe_bounds=dict(start_mib=16 if args.self_test else FULL_ALLOCATIONS[0],
                ladder_mib=list(sizes), maximum_mib=max(sizes),
                maximum_fraction_of_8gib=max(sizes)/(8*1024),
                one_child_at_a_time=True, random_chunk_bytes=CHUNK_BYTES,
                memory_compression='reported as not directly measured; never inferred from allocation minus RSS'),
            evidence_self_check=checks, trials=trials,
            success_criteria=dict(actual_parent_or_worker_rss_above_limit=observed,
                above_threshold_decision='REJECT_RESOURCE_EXCESS',
                all_children_reaped=clean,
                full_pass_requires_all=not args.self_test),
            script=dict(path=str(script_path), sha256=hashlib.sha256(script_path.read_bytes()).hexdigest()),
            child_source_sha256=hashlib.sha256(CHILD.encode()).hexdigest(),
            report_path=str(output))
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x') as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write('\n')
        print(json.dumps(dict(status=status, report=str(output), trials=len(trials),
                              script_sha256=report['script']['sha256']), indent=2))
        return 0 if status.startswith('PASS_') else 2
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


if __name__ == '__main__':
    raise SystemExit(main())
