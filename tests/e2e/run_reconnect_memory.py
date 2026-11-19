"""Reproduce the reconnect leak on the previously released package, then fix it."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
variant = sys.argv[1]
metadata = json.loads((ROOT / 'patches/config-subscriber.json').read_text())
manifest = json.loads((ROOT / variant / 'app.json').read_text())
output = ROOT / 'e2e-artifacts' / ('reconnect-' + variant)
output.mkdir(parents=True, exist_ok=True)
results = []
for mode, image, arm in [
    ('baseline', metadata['baseline_images'][variant], 'idle'),
    ('baseline-periodic-publish', metadata['baseline_images'][variant], 'publish'),
    ('fixed', manifest['image'], 'idle'),
]:
    digest = metadata['after_sha256'] if mode == 'fixed' else metadata['before_sha256']
    name = 'synthetic-reconnect-' + variant + '-' + mode
    try:
        if mode == 'baseline':
            sys.path.insert(0, str(ROOT / 'scripts'))
            from ci_image_retry import pull_image
            pull_image(['docker'], image)
        check = subprocess.run(['docker', 'run', '--rm', '--network=none', '--entrypoint',
                                'python3', image, '-c',
                                "import hashlib; assert hashlib.sha256(open('/opt/frigate/frigate/video/ffmpeg.py','rb').read()).hexdigest()=='" + digest + "'"],
                               capture_output=True, text=True, timeout=60)
        assert check.returncode == 0, check.stderr
        process = subprocess.run([
            'docker', 'run', '--name', name, '--network=none', '--memory=768m',
            '--memory-swap=768m', '--pids-limit=128',
            '-e', 'OPENBLAS_NUM_THREADS=1', '-e', 'OMP_NUM_THREADS=1',
            '-v', f'{ROOT / "tests"}:/tests:ro', '--entrypoint', 'python3',
            image, '/tests/e2e/reconnect_memory_worker.py', arm,
        ], capture_output=True, text=True, timeout=180)
        state = json.loads(subprocess.check_output(
            ['docker', 'inspect', name, '--format', '{{json .State}}'], text=True))
        (output / (mode + '.log')).write_text(process.stdout + process.stderr)
        rows = [json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
        assert rows, 'No completed reconnect measurement: ' + process.stderr[-2000:]
        result = rows[-1]
        assert not state['OOMKilled'], 'Unexpected OOM invalidates the reconnect measurement'
        if mode == 'baseline':
            assert process.returncode != 0 and 'Reconnect publisher grew beyond' in process.stderr
            assert result['publisher_growth_kib'] > 8 * 1024, 'Baseline growth was not reproduced'
        else:
            assert process.returncode == 0, process.stdout + process.stderr
        result.update(mode=mode, image=image, source_sha256=digest,
                      exit_code=process.returncode, oom_killed=state['OOMKilled'])
        results.append(result)
        (output / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
        print(json.dumps(result), flush=True)
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
