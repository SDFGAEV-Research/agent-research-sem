from pathlib import Path
import tempfile
import unittest
import zipfile

from research_platform.platform.composition.release_quality import build_release_quality_evidence
from research_platform.governance.release.runtime.evidence import build_release_evidence
from research_platform.governance.release.runtime.manifest import build_release_manifest
from research_platform.governance.release.runtime.packager import ReleasePackager
from research_platform.governance.release.runtime.package_verification import verify_release_package


class ReleasePackageSelfVerificationV190Tests(unittest.TestCase):
    def _tree(self, root: Path) -> None:
        (root / "research_platform").mkdir(parents=True)
        (root / "research_platform" / "__init__.py").write_text("", encoding="utf-8")
        (root / "research_platform" / "x.py").write_text("x=1\n", encoding="utf-8")
        (root / "pyproject.toml").write_text(
            '[project]\nname="x"\nversion="1.2.3"\nrequires-python=">=3.11"\n',
            encoding="utf-8",
        )

    def test_official_package_verifies_every_member_against_frozen_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"; root.mkdir(); self._tree(root)
            manifest = build_release_manifest(root)
            evidence = build_release_evidence(
                root,
                quality=build_release_quality_evidence(root),
                regression_tests_collected=1,
                regression_tests_passed=1,
                regression_tests_skipped=0,
                regression_shard_count=1,
                regression_test_inventory_sha256="1" * 64,
                regression_runtime_sha256="2" * 64,
                manifest=manifest,
            )
            package = ReleasePackager().build(root, Path(td) / "release.zip", evidence=evidence)
            report = verify_release_package(Path(package.zip_path))
            self.assertTrue(report.clean, report.errors)
            self.assertEqual(report.manifest_digest, manifest.digest())
            self.assertEqual(report.evidence_digest, evidence.digest())

    def test_tampered_package_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"; root.mkdir(); self._tree(root)
            manifest = build_release_manifest(root)
            evidence = build_release_evidence(
                root,
                quality=build_release_quality_evidence(root),
                regression_tests_collected=1,
                regression_tests_passed=1,
                regression_tests_skipped=0,
                regression_shard_count=1,
                regression_test_inventory_sha256="1" * 64,
                regression_runtime_sha256="2" * 64,
                manifest=manifest,
            )
            path = Path(td) / "release.zip"
            ReleasePackager().build(root, path, evidence=evidence)
            with zipfile.ZipFile(path, "a") as zf:
                zf.writestr("research_platform/x.py", b"x=999\n")
            report = verify_release_package(path)
            self.assertFalse(report.clean)
            self.assertTrue(any("duplicate ZIP member" in row or "package hash drift" in row for row in report.errors))

    def test_legacy_package_snapshot_manifests_are_not_release_authorities(self):
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / "PACKAGE_CONTENTS.sha256").exists())
        self.assertFalse((root / "PACKAGE_METADATA.json").exists())


if __name__ == "__main__":
    unittest.main()
