import copy
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


import sys
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_release import validate


class ReleaseTests(unittest.TestCase):
    def test_no_downgrade_from_main(self):
        for variant in ('intel', 'nvidia'):
            previous = json.loads(subprocess.check_output(['git', 'show', f'origin/main:{variant}/app.json'], cwd=ROOT))
            current = json.loads((ROOT / variant / 'app.json').read_text())
            def upstream(image):
                return tuple(map(int, re.search(r':(\d+)\.(\d+)\.(\d+)', image).groups()))
            self.assertGreaterEqual(upstream(current['upstream_image']), upstream(previous.get('upstream_image', previous['image'])))

    def test_both_manifests_and_upgrade_contract(self):
        for variant in ('intel', 'nvidia'):
            validate(json.loads((ROOT / variant / 'app.json').read_text()), variant)

    def test_rejects_original_downgrade_and_ambiguous_version(self):
        for variant in ('intel', 'nvidia'):
            good = json.loads((ROOT / variant / 'app.json').read_text())
            bad = copy.deepcopy(good)
            suffix = '-tensorrt' if variant == 'nvidia' else ''
            bad['image'] = 'ghcr.io/blakeblackshear/frigate:0.17.0' + suffix
            bad['version'] = '0.17.0-reefy.2026-01-01-00'
            with self.assertRaises(AssertionError): validate(bad, variant)
            bad = copy.deepcopy(good)
            bad['version'] = '2026.01.01-00'
            with self.assertRaises(AssertionError): validate(bad, variant)


if __name__ == '__main__':
    unittest.main()
