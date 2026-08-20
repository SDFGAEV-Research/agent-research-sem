import ast
import unittest
from pathlib import Path

from methods.self_evolving_memory.evidence_audit import AuditEvidenceStore
from methods.self_evolving_memory.evidence_eval import EvalEvidenceStore
from methods.self_evolving_memory.evidence_memory import InMemoryEvidenceStore
from methods.self_evolving_memory.evidence_memory import InMemoryEvidenceSnapshotSource


class SEMEvidencePhysicalFirewallV104Tests(unittest.TestCase):
    def test_three_evidence_domains_remain_physically_separate(self):
        self.assertIsNotNone(InMemoryEvidenceStore())
        self.assertIsNotNone(AuditEvidenceStore())
        self.assertIsNotNone(EvalEvidenceStore())

    def test_materialization_imports_only_jmem_physical_module(self):
        root=Path(__file__).resolve().parents[1]
        path=root/'methods/self_evolving_memory/materialization.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        imports=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom): imports.append(node.module or '')
        self.assertIn('research_platform.platform.kernel', imports)
        self.assertIn('evidence_api', imports)
        self.assertNotIn('evidence_memory',imports)
        self.assertNotIn('evidence',imports)
        self.assertNotIn('evidence_audit',imports)
        self.assertNotIn('evidence_eval',imports)

    def test_jmem_view_exposes_snapshot_only(self):
        view=InMemoryEvidenceSnapshotSource(InMemoryEvidenceStore())
        self.assertTrue(hasattr(view,'snapshot'))
        self.assertFalse(hasattr(view,'append'))


if __name__ == '__main__':
    unittest.main()
