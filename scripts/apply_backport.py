"""Apply the recorded upstream backport only to the exact qualified source."""
import hashlib
import json
from pathlib import Path
import sys


def apply(root, source_root=Path('/')):
    metadata = json.loads((root / 'patches/watchdog-reset.json').read_text())
    patch = (root / 'patches/24663-watchdog-reset.patch').read_bytes()
    if hashlib.sha256(patch).hexdigest() != metadata['patch_sha256']:
        raise ValueError('Recorded upstream patch changed')
    target = source_root / metadata['source_path'].lstrip('/')
    original = target.read_bytes()
    if hashlib.sha256(original).hexdigest() != metadata['before_sha256']:
        raise ValueError('Unsupported upstream source; review the backport before rebuilding')
    changed = original.decode()
    for replacement in metadata['replacements']:
        if changed.count(replacement['before']) != 1:
            raise ValueError('Upstream patch context is not unique')
        changed = changed.replace(replacement['before'], replacement['after'])
    if hashlib.sha256(changed.encode()).hexdigest() != metadata['after_sha256']:
        raise ValueError('Patched source does not match qualified output')
    target.write_text(changed)
    return metadata


if __name__ == '__main__':
    print(json.dumps(apply(Path(sys.argv[1]))))
