"""Real uncooperative raw-video child through the installed watchdog method."""
from collections import deque
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from types import SimpleNamespace
sys.path.insert(0,'/tests')
from watchdog_contract import reset_method, watchdog

# This fixture keeps producing after SIGTERM, matching a stalled decoder that
# flushes duplicate frames during reset. No camera data or fleet services used.
CHILD='''import os,signal,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
os.write(2,b"READY\\n")
block=b"x"*65536
for i in range(4096):os.write(1,block)
while True:
 os.write(1,block)
 time.sleep(0.04)
'''

def rss_kib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

mode=sys.argv[1]
process=subprocess.Popen([sys.executable,'-u','-c',CHILD],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
assert process.stderr.readline()==b'READY\n'
fixture=watchdog(process)
fixture.capture_thread=None
restarted=[]
replacement=None

def restart():
    global replacement
    assert process.poll() is not None,'Previous decoder must be reaped before replacement'
    replacement=subprocess.Popen([sys.executable,'-c','import sys;sys.stdout.buffer.write(b"healthy-frame")'],stdout=subprocess.PIPE)
    assert replacement.communicate(timeout=5)[0]==b'healthy-frame'
    restarted.append(True)
fixture.start_ffmpeg_detect=restart
before=rss_kib();started=time.monotonic()
try:
    reset_method('/opt/frigate/frigate/video/ffmpeg.py')(fixture)
    growth=rss_kib()-before
    result={'mode':mode,'rss_growth_kib':growth,'elapsed_seconds':round(time.monotonic()-started,2),
            'old_child_reaped':process.poll() is not None,'replacement_frame_verified':bool(restarted)}
    print(json.dumps(result),flush=True)
    assert process.poll() is not None and restarted
    assert 29<=result['elapsed_seconds']<=45,'Keep the original 30-second termination bound'
    assert growth<32*1024,'Watchdog buffered raw video during decoder termination'
finally:
    if process.poll() is None:
        process.kill();process.wait(timeout=5)
    process.stdout.close();process.stderr.close()
