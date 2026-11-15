"""Boot real Frigate images before/after upgrade with persistent synthetic state.

Runs on a disposable Docker runner. GPU passthrough is intentionally not requested:
this checks image startup and data preservation, not GPU acceleration.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
variant = sys.argv[1]
manifest = json.loads((ROOT / variant / 'app.json').read_text())
artifacts=ROOT/'e2e-artifacts'/('upgrade-'+variant);artifacts.mkdir(parents=True,exist_ok=True)
name = 'frigate-upgrade-' + variant


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def wait_api(port):
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/config', timeout=3) as response:
                return json.load(response)
        except Exception:
            time.sleep(2)
    raise AssertionError('Frigate API did not start')


with tempfile.TemporaryDirectory(prefix='frigate-upgrade-') as directory:
    root = Path(directory)
    for sub in ('config', 'media', 'models'):
        (root / sub).mkdir()
    config = root / 'config/config.yml'
    config.write_text('''mqtt:
  enabled: false
auth:
  enabled: false
record:
  enabled: true
  continuous: {days: 1}
  motion: {days: 1}
  alerts: {retain: {days: 7}}
  detections: {retain: {days: 7}}
detect:
  enabled: false
detectors:
  cpu:
    type: cpu
cameras:
  synthetic_preserved:
    enabled: false
    friendly_name: Synthetic preserved camera
    ffmpeg:
      inputs:
        - path: rtsp://192.0.2.10/synthetic
          roles: [detect]
    detect:
      width: 640
      height: 360
  synthetic_live:
    enabled: true
    ffmpeg:
      input_args: [-re, -stream_loop, '-1']
      hwaccel_args: []
      inputs:
        - path: /config/synthetic-input.mp4
          roles: [detect, record]
    detect:
      width: 320
      height: 180
      fps: 5
version: 0.17-0
''')
    marker = root / 'media/synthetic-recording-marker'
    marker.write_bytes(b'synthetic persistent media')
    original_hash = hashlib.sha256(marker.read_bytes()).hexdigest()
    suffix = '-tensorrt' if variant == 'nvidia' else ''
    preserved_recording=None
    results=[]
    try:
        generator="import glob,subprocess; f=sorted(glob.glob('/usr/lib/ffmpeg/*/bin/ffmpeg'))[-1]; subprocess.run([f,'-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=5','-t','4','-c:v','libx264','-pix_fmt','yuv420p','-y','/config/synthetic-input.mp4'],check=True)"
        docker('run','--rm','--entrypoint','python3','-v',f'{root / "config"}:/config',manifest['image'],'-c',generator)
        for index, image in enumerate(('ghcr.io/blakeblackshear/frigate:0.17.0' + suffix, 'ghcr.io/blakeblackshear/frigate:0.18.2' + suffix, manifest['image'])):
            if image != manifest['image']:
                docker('pull', image)
            stage_started=time.time()
            docker('run', '-d', '--name', name, '--shm-size=256m', '-p', '127.0.0.1::5000',
                   '-v', f'{root / "config"}:/config', '-v', f'{root / "media"}:/media/frigate',
                   '-v', f'{root / "models"}:/models', image)
            port = docker('port', name, '5000').rsplit(':', 1)[1]
            current = wait_api(port)
            assert current['cameras']['synthetic_preserved']['friendly_name'] == 'Synthetic preserved camera'
            assert current['cameras']['synthetic_preserved']['detect']['width'] == 640
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/version') as response:
                assert image.split(':')[-1].split('-')[0] in response.read().decode()
            assert hashlib.sha256(marker.read_bytes()).hexdigest() == original_hash
            assert (root / 'config/frigate.db').exists()
            if index == 0:
                docker('exec', name, 'python3', '-c',
                       "import sqlite3; c=sqlite3.connect('/config/frigate.db'); "
                       "c.execute('CREATE TABLE synthetic_upgrade_marker (value TEXT)'); "
                       "c.execute(\"INSERT INTO synthetic_upgrade_marker VALUES ('retained')\"); c.commit()")
            else:
                docker('exec', name, 'python3', '-c',
                       "import sqlite3; c=sqlite3.connect('/config/frigate.db'); "
                       "assert c.execute('SELECT value FROM synthetic_upgrade_marker').fetchone()[0]=='retained'; "
                       "assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'")
            # Require a real saved synthetic video segment at every upgrade stage.
            deadline=time.monotonic()+90
            fresh=None
            while time.monotonic()<deadline:
                probe=f"import sqlite3,json,time; c=sqlite3.connect('/config/frigate.db'); r=c.execute(\"SELECT path,start_time,end_time FROM recordings WHERE camera='synthetic_live' AND start_time>? AND end_time-start_time>=2 ORDER BY start_time DESC LIMIT 1\",({stage_started},)).fetchone(); print(json.dumps(r))"
                fresh=json.loads(docker('exec',name,'python3','-c',probe))
                if fresh:break
                time.sleep(2)
            assert fresh,'Fresh synthetic recording missing after upgrade'
            relative=Path(fresh[0]).relative_to('/media/frigate')
            recorded=root/'media'/relative
            assert recorded.is_file()
            if preserved_recording:
                old_path,old_hash=preserved_recording
                assert old_path.is_file() and hashlib.sha256(old_path.read_bytes()).hexdigest()==old_hash
            else:
                preserved_recording=(recorded,hashlib.sha256(recorded.read_bytes()).hexdigest())
            decode="import glob,subprocess,sys; f=sorted(glob.glob('/usr/lib/ffmpeg/*/bin/ffmpeg'))[-1]; subprocess.run([f,'-v','error','-i',sys.argv[1],'-frames:v','2','-f','null','-'],check=True,timeout=20)"
            docker('exec',name,'python3','-c',decode,fresh[0])
            results.append({'image':image,'config_preserved':True,'database_preserved':True,'media_preserved':True,'fresh_recording_decoded':True})
            (artifacts/'result.json').write_text(json.dumps(results,indent=2))
            (artifacts/f'stage-{index}.log').write_text(docker('logs','--tail','100',name))
            docker('stop', name)
            docker('rm', name)
            print('PASS:', variant, image, 'camera config, database and persistent media preserved', flush=True)
    finally:
        subprocess.run(['docker', 'logs', '--tail', '100', name], check=False)
        subprocess.run(['docker', 'rm', '-f', name], check=False)
        # Frigate creates root-owned directories in this disposable fixture.
        # Return only our generated temporary tree to the test runner for cleanup.
        subprocess.run(['chown', '-R', f'{os.getuid()}:{os.getgid()}', str(root)], check=True)
