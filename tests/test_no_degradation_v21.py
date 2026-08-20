from pathlib import Path
import tempfile
import unittest
from research_platform.governance.quality import scan_no_degradation

class NoDegradationV21Tests(unittest.TestCase):
    def test_detects_explicit_runtime_degradation_api(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'bad.py').write_text('fallback_model = "small"\n')
            findings=scan_no_degradation(root); self.assertEqual(findings[0].identifier,'fallback_model')
    def test_does_not_match_comments_or_descriptive_fallback_word(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'ok.py').write_text('# no fallback should exist\nreason = "fallback is forbidden"\n')
            self.assertEqual(scan_no_degradation(root),())
if __name__=='__main__': unittest.main()
