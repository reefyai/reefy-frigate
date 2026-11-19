"""Baseline/fixed process-boundary regression, with real resource limits."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from ci_process import run_container
variant=sys.argv[1]
lock=json.loads((ROOT/'upstream-lock.json').read_text())[variant]
manifest=json.loads((ROOT/variant/'app.json').read_text())
metadata=json.loads((ROOT/'patches/watchdog-reset.json').read_text())
output=ROOT/'e2e-artifacts'/('reset-'+variant);output.mkdir(parents=True,exist_ok=True)
results=[]
for mode,image in [('baseline',lock['image']+'@'+lock['digest']),('fixed',manifest['image'])]:
    digest=(metadata['before_sha256'] if mode=='baseline' else
            json.loads((ROOT/'patches/config-subscriber.json').read_text())['after_sha256'])
    check=subprocess.run(['docker','run','--rm','--network=none','--entrypoint','python3',image,'-c',
        "import hashlib; assert hashlib.sha256(open('/opt/frigate/frigate/video/ffmpeg.py','rb').read()).hexdigest()=='"+digest+"'"],capture_output=True,text=True)
    assert check.returncode==0,check.stderr
    unit=subprocess.run(['docker','run','--rm','--network=none','--memory=512m','--pids-limit=64',
        '-v',f'{ROOT / "tests"}:/tests:ro','--entrypoint','python3',image,'/tests/watchdog_contract.py','-v'],capture_output=True,text=True,timeout=60)
    (output/(mode+'-contract.log')).write_text(unit.stdout+unit.stderr)
    if mode=='baseline':
        assert unit.returncode!=0 and 'FAILED (failures=2)' in unit.stderr,'Baseline did not reproduce the two upstream contract failures'
    else:
        assert unit.returncode==0,unit.stderr
    name='synthetic-reset-'+variant+'-'+mode
    try:
        process,state=run_container(['docker','run','--name',name,'--network=none','--memory=768m','--memory-swap=768m','--pids-limit=64',
            '-v',f'{ROOT / "tests"}:/tests:ro','--entrypoint','python3',image,'/tests/e2e/reset_memory_worker.py',mode],name,output/(mode+'-memory'),timeout=60)
        (output/(mode+'-memory.log')).write_text(process.stdout+process.stderr)
        rows=[json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
        evidence=rows[-1] if rows else {}
        reproduced=(state['OOMKilled'] or (process.returncode!=0 and 'Watchdog buffered raw video' in process.stderr))
        if mode=='baseline':assert reproduced,'Baseline must fail specifically from raw-video buffering or its OOM'
        else:assert process.returncode==0 and not state['OOMKilled'],process.stdout+process.stderr
        results.append({'mode':mode,'image':image,'source_sha256':digest,'exit_code':process.returncode,
                        'oom_killed':state['OOMKilled'],'expected_failure_reproduced':reproduced,**evidence})
        (output/'result.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps(results[-1]),flush=True)
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True)
