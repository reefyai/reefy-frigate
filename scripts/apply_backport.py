"""Apply the recorded upstream backport only to the exact qualified source."""
import hashlib
import json
from pathlib import Path
import sys


BACKPORTS = (
    ('watchdog-reset.json', '24663-watchdog-reset.patch'),
    ('config-subscriber.json', '24002-config-subscriber.patch'),
)


def apply(root, source_root=Path('/')):
    staged = {}
    applied = []
    for metadata_name, patch_name in BACKPORTS:
        metadata = json.loads((root / 'patches' / metadata_name).read_text())
        patch = (root / 'patches' / patch_name).read_bytes()
        if hashlib.sha256(patch).hexdigest() != metadata['patch_sha256']:
            raise ValueError('Recorded upstream patch changed')
        target = source_root / metadata['source_path'].lstrip('/')
        original = staged.get(target)
        if original is None:
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
        staged[target] = changed.encode()
        applied.append(metadata)
    # Validate the complete sequence before changing an upstream file.
    for target, changed in staged.items():
        target.write_bytes(changed)
    return {'backports': applied}


if __name__ == '__main__':
    print(json.dumps(apply(Path(sys.argv[1]))))
