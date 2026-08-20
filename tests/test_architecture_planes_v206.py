from pathlib import Path
import tempfile
import unittest

from research_platform.governance.architecture.planes import is_composition_module
from research_platform.governance.architecture.system_dependency_invariants import audit_system_dependency_invariants


class ArchitecturePlaneTests(unittest.TestCase):
    def test_composition_module_is_explicit_architecture_plane(self):
        self.assertTrue(is_composition_module("research_platform.platform.composition.experiment_runtime"))
        self.assertTrue(is_composition_module("research_platform.model.composition.runtime"))
        self.assertFalse(is_composition_module("research_platform.model.runtime.serving"))

    def test_composition_edges_do_not_pollute_authoritative_system_dag(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "research_platform/platform/composition/sample.py"
            path.parent.mkdir(parents=True)
            path.write_text("from research_platform.model.runtime import anything\n", encoding="utf-8")
            self.assertEqual(audit_system_dependency_invariants(root), [])


if __name__ == "__main__":
    unittest.main()
