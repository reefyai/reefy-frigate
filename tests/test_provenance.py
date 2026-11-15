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

class PlatformProvenance(unittest.TestCase):
    def test_selects_qualified_image_and_preserves_attestation_index(self):
        from registry import amd64_image
        image={'digest':'sha256:'+'c'*64,'platform':{'architecture':'amd64','os':'linux'}}
        attestation={'digest':'sha256:'+'d'*64,'platform':{'architecture':'unknown','os':'unknown'}}
        self.assertEqual(amd64_image({'manifests':[image,attestation]}),image)
        for entries in [[attestation],[image,image],[{'digest':'sha256:'+'e'*64,'platform':{'architecture':'arm64','os':'linux'}}]]:
            with self.assertRaises(ValueError):amd64_image({'manifests':entries})
