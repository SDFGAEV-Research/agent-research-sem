from pathlib import Path
import tempfile
import unittest

from research_platform.governance.architecture import ImportRule, analyze_hotspots, audit_import_rules, build_architecture_report, package_cycles, scan_imports


class ArchitectureAnalyzerTests(unittest.TestCase):
    def test_current_tree_has_no_forbidden_imports_or_cycles(self):
        root=Path(__file__).resolve().parents[1]; report=build_architecture_report(root)
        self.assertEqual(report.import_violations,()); self.assertEqual(report.package_cycles,()); self.assertEqual(report.declared_authority_violations,()); self.assertEqual(len(report.report_sha256),64)

    def test_rule_reports_exact_source_line(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"research_platform"/"x").mkdir(parents=True); (root/"projects"/"m").mkdir(parents=True)
            (root/"research_platform"/"__init__.py").write_text(""); (root/"projects"/"__init__.py").write_text("")
            p=root/"research_platform"/"x"/"a.py"; p.write_text("from projects.m import y\n")
            edges=scan_imports(root); v=audit_import_rules(edges,(ImportRule("research_platform","projects","no"),))
            self.assertEqual(v[0].edge.line,1); self.assertIn("a.py",v[0].edge.path)

    def test_cycle_detection_is_physical(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"research_platform"/"a").mkdir(parents=True); (root/"research_platform"/"b").mkdir(parents=True)
            for p in (root/"research_platform"/"__init__.py",root/"research_platform"/"a"/"__init__.py",root/"research_platform"/"b"/"__init__.py"): p.write_text("")
            (root/"research_platform"/"a"/"x.py").write_text("from research_platform.b import y\n")
            (root/"research_platform"/"b"/"y.py").write_text("from research_platform.a import x\n")
            self.assertTrue(package_cycles(scan_imports(root),depth=2))

    def test_hotspot_analysis_surfaces_large_branchy_module(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/"projects").mkdir(); (root/"projects"/"__init__.py").write_text(""); (root/"projects"/"x.py").write_text("def f(x):\n"+"    if x: x+=1\n"*30+"    return x\n")
            rows=analyze_hotspots(root); self.assertGreater(rows[0].branches,20); self.assertGreater(rows[0].score,rows[0].physical_lines)

if __name__=='__main__': unittest.main()
