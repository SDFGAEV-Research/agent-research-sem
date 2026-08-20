from __future__ import annotations

from pathlib import Path
import unittest

from research_platform.governance.architecture.runtime_observability_invariants import audit_runtime_observability_invariants


class RuntimeObservabilityArchitectureV183Tests(unittest.TestCase):
    def test_runtime_truth_does_not_import_observability_plane(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(audit_runtime_observability_invariants(root), [])


if __name__ == "__main__":
    unittest.main()
