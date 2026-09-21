"""Boot real Frigate images before/after upgrade with persistent synthetic state.

Runs on a disposable Docker runner. GPU passthrough is intentionally not requested:
this checks image startup and data preservation, not GPU acceleration.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
variant = sys.argv[1]
manifest = json.loads((ROOT / variant / 'app.json').read_text())
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
  enabled: false
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
version: 0.17-0
''')
    marker = root / 'media/synthetic-recording-marker'
    marker.write_bytes(b'synthetic persistent media')
    original_hash = hashlib.sha256(marker.read_bytes()).hexdigest()
    suffix = '-tensorrt' if variant == 'nvidia' else ''
    try:
        for index, image in enumerate(('ghcr.io/blakeblackshear/frigate:0.17.0' + suffix, manifest['image'])):
            docker('pull', image)
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
            docker('stop', name)
            docker('rm', name)
            print('PASS:', variant, image, 'camera config, database and persistent media preserved', flush=True)
    finally:
        subprocess.run(['docker', 'logs', '--tail', '100', name], check=False)
        subprocess.run(['docker', 'rm', '-f', name], check=False)
