import copy
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def validate(manifest, variant):
    suffix = '-tensorrt' if variant == 'nvidia' else ''
    image = re.fullmatch(r'ghcr.io/blakeblackshear/frigate:(\d+)\.(\d+)\.(\d+)' + suffix, manifest['image'])
    assert image, 'Unexpected image or hardware variant'
    upstream = tuple(map(int, image.groups()))
    assert upstream >= (0, 17, 2), 'Upstream downgrade below previously shipped 0.17.2'
    version = '.'.join(image.groups())
    assert re.fullmatch(r'v' + re.escape(version) + r'-reefy\.\d{4}-\d{2}-\d{2}-\d{2}', manifest['version']), 'Version must identify upstream and Reefy release'
    for volume, storage in [('config', 'state'), ('models', 'state'), ('media', 'bulk')]:
        spec = manifest['volumes'][volume]
        assert spec['storage_class'] == storage
        assert spec['mount'] == ('/media/frigate' if volume == 'media' else '/' + volume)


class ReleaseTests(unittest.TestCase):
    def test_both_manifests_and_upgrade_contract(self):
        for variant in ('intel', 'nvidia'):
            validate(json.loads((ROOT / variant / 'app.json').read_text()), variant)

    def test_rejects_original_downgrade_and_ambiguous_version(self):
        for variant in ('intel', 'nvidia'):
            good = json.loads((ROOT / variant / 'app.json').read_text())
            bad = copy.deepcopy(good)
            bad['image'] = bad['image'].replace('0.17.2', '0.17.0')
            bad['version'] = '2026.09.13-00'
            with self.assertRaises(AssertionError): validate(bad, variant)
            bad = copy.deepcopy(good)
            bad['version'] = '2026.01.01-00'
            with self.assertRaises(AssertionError): validate(bad, variant)


if __name__ == '__main__':
    unittest.main()
