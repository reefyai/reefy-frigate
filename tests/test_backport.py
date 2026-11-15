import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('apply_backport',ROOT/'scripts/apply_backport.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class BackportSafety(unittest.TestCase):
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
