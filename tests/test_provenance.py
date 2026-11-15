import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from registry import verify_labels

class ReleaseProvenance(unittest.TestCase):
    def test_rejects_other_source_or_base_before_promotion(self):
        source='a'*40;manifest={'version':'1.2.3-reefy.2000-01-01-00'};base={'image':'registry.example/synthetic:1.2.3','digest':'sha256:'+'b'*64}
        labels={'org.opencontainers.image.revision':source,'org.opencontainers.image.version':manifest['version'],
                'org.opencontainers.image.base.name':base['image'],'org.opencontainers.image.base.digest':base['digest']}
        verify_labels(labels,source,manifest,base)
        for key in labels:
            wrong=copy.deepcopy(labels);wrong[key]='different'
            with self.assertRaises(ValueError):verify_labels(wrong,source,manifest,base)
