import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('apply_backport',ROOT/'scripts/apply_backport.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class BackportSafety(unittest.TestCase):
    def sequence_fixture(self, root):
        (root/'patches').mkdir()
        target=root/'opt/frigate/frigate/video/ffmpeg.py'
        target.parent.mkdir(parents=True)
        target.write_text('synthetic original\n')
        states=['synthetic original\n','synthetic reset fixed\n','synthetic reconnect fixed\n']
        for index,(metadata_name,patch_name) in enumerate(module.BACKPORTS):
            patch_bytes=('synthetic patch '+str(index)).encode()
            (root/'patches'/patch_name).write_bytes(patch_bytes)
            metadata={'source_path':'/opt/frigate/frigate/video/ffmpeg.py',
                'patch_sha256':hashlib.sha256(patch_bytes).hexdigest(),
                'before_sha256':hashlib.sha256(states[index].encode()).hexdigest(),
                'after_sha256':hashlib.sha256(states[index+1].encode()).hexdigest(),
                'replacements':[{'before':states[index],'after':states[index+1]}]}
            (root/'patches'/metadata_name).write_text(json.dumps(metadata))
        return target

    def test_both_backports_apply_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=self.sequence_fixture(root)
            result=module.apply(root,root)
            self.assertEqual(target.read_text(),'synthetic reconnect fixed\n')
            self.assertEqual(len(result['backports']),2)

    def test_rejected_second_backport_preserves_original_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=self.sequence_fixture(root)
            original=target.read_bytes()
            (root/'patches/24002-config-subscriber.patch').write_text('altered second patch')
            with self.assertRaisesRegex(ValueError,'Recorded upstream patch changed'):
                module.apply(root,root)
            self.assertEqual(target.read_bytes(),original)

    def test_unexpected_source_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'opt/frigate/frigate/video/ffmpeg.py';p.parent.mkdir(parents=True)
            p.write_text('synthetic unexpected source\n');original=p.read_bytes()
            with self.assertRaisesRegex(ValueError,'Unsupported upstream source'):
                module.apply(ROOT,root)
            self.assertEqual(p.read_bytes(),original)

    def test_original_patch_reference_is_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'patches').mkdir()
            (root/'patches/watchdog-reset.json').write_bytes((ROOT/'patches/watchdog-reset.json').read_bytes())
            (root/'patches/24663-watchdog-reset.patch').write_text('altered patch')
            with self.assertRaisesRegex(ValueError,'Recorded upstream patch changed'):
                module.apply(root)
