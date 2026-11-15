import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ci_image_retry import transient_download_failure
class TransferPolicy(unittest.TestCase):
    def test_retries_known_interrupted_transfers(self):
        for error in ['tls: bad record MAC','unexpected EOF','connection reset by peer']:
            self.assertTrue(transient_download_failure(error))
    def test_never_retries_security_or_permanent_failures(self):
        for error in ['certificate verify failed','unauthorized','manifest unknown','no space left on device','404 not found']:
            self.assertFalse(transient_download_failure(error))
