"""Wait for a private Docker fixture without coupling exit to its attach stream."""
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace


def run_container(command, name, output, timeout):
    output = Path(output)
    # Detached startup avoids a completed worker being held by the CLI's attach
    # stream. The original payload deadline and its own readiness bounds remain.
    started = subprocess.run(command[:2] + ['-d'] + command[2:],
                             capture_output=True, text=True, timeout=60)
    assert started.returncode == 0, started.stdout + started.stderr
    timed_out = False
    try:
        waited = subprocess.run(['docker', 'wait', name], capture_output=True,
                                text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        waited = None
    state = json.loads(subprocess.check_output(
        ['docker', 'inspect', name, '--format', '{{json .State}}'],
        text=True, timeout=30))
    logs = subprocess.run(['docker', 'logs', name], capture_output=True,
                          text=True, timeout=30)
    output.with_suffix('.log').write_text(logs.stdout + logs.stderr)
    output.with_suffix('.state.json').write_text(json.dumps(state, indent=2))
    assert not timed_out, 'Container payload exceeded its unchanged deadline: ' + name
    assert waited.returncode == 0 and logs.returncode == 0, waited.stderr + logs.stderr
    return SimpleNamespace(returncode=int(waited.stdout.strip()),
                           stdout=logs.stdout, stderr=logs.stderr), state
