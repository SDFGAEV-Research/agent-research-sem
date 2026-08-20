from pathlib import Path
import re
import unittest


class ReleaseDocsSingleTruthV128Tests(unittest.TestCase):
    def test_documents_do_not_claim_a_manual_current_test_baseline(self):
        root = Path(__file__).resolve().parents[1]
        integration = (root / "docs" / "INTEGRATION_PLAN.md").read_text(encoding="utf-8")
        self.assertNotRegex(integration, r"Current\s+\d+[ -]Test Baseline")
        self.assertIn("RELEASE_EVIDENCE.json", integration)

    def test_readme_marks_round_count_as_historical(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("Round 98 — Historical Verified Runtime Baseline", readme)
        self.assertIn("Current release truth", readme)
        self.assertIn("RELEASE_EVIDENCE.json", readme)

    def test_release_docs_define_one_frozen_truth_and_no_legacy_package_manifest(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        integration = (root / "docs" / "INTEGRATION_PLAN.md").read_text(encoding="utf-8")
        for text in (readme, integration):
            self.assertIn("RELEASE_MANIFEST.json", text)
            self.assertIn("RELEASE_EVIDENCE.json", text)
            self.assertIn("verify_release_package.py", text)
        self.assertFalse((root / "PACKAGE_CONTENTS.sha256").exists())
        self.assertFalse((root / "PACKAGE_METADATA.json").exists())

    def test_version_literal_has_single_project_authority(self):
        root = Path(__file__).resolve().parents[1]
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        version = match.group(1)
        hits = []
        for base in (root / "research_platform", root / "projects"):
            for path in base.rglob("*.py"):
                if version in path.read_text(encoding="utf-8"):
                    hits.append(path.relative_to(root).as_posix())
        self.assertEqual(hits, [], f"project version duplicated in source: {hits}")


if __name__ == "__main__":
    unittest.main()
