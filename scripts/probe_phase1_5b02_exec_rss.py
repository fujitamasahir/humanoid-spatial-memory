"""Standalone memory-accounting diagnostic, no graph or world execution."""
import json
from pathlib import Path
import resource
import subprocess
import sys

held=bytearray(550*1024*1024)
code='''import resource,json
resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))
print(json.dumps(dict(peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,status=open('/proc/self/status').read())))
'''
completed=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,check=True)
child=json.loads(completed.stdout)
report=dict(parent_peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,child=child)
target=Path(__file__).resolve().parents[1]/'results/runs/phase1_5b02_exec_rss_probe.json'
target.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(parent_peak=report['parent_peak'],child_peak=child['peak'],
    current=[line for line in child['status'].splitlines() if line.startswith(('VmRSS:','VmSize:','VmHWM:'))])))
