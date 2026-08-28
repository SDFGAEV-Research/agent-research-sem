from __future__ import annotations

import json
from pathlib import Path

from research_platform.governance.repository_boundary import audit_repository_boundary


def _minimal_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "research_platform" / "governance" / "system_registry").mkdir(parents=True)
    (root / "research_platform" / "core").mkdir(parents=True)
    (root / "deploy").mkdir()
    (root / "research_platform" / "core" / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "research_platform" / "governance" / "system_registry" / "catalog.json").write_text(
        json.dumps({"governance": {"package_prefix": "research_platform.governance"}}), encoding="utf-8"
    )
    (root / "pyproject.toml").write_text('[tool.setuptools.packages.find]\ninclude = ["research_platform*"]\n', encoding="utf-8")
    (root / "deploy" / "Dockerfile").write_text("COPY research_platform ./research_platform\n", encoding="utf-8")
    return root


def test_clean_upstream_repository_passes(tmp_path: Path) -> None:
    report = audit_repository_boundary(_minimal_root(tmp_path))
    assert report.passed
    assert report.violations == ()


def test_downstream_directory_and_core_import_fail_closed(tmp_path: Path) -> None:
    root = _minimal_root(tmp_path)
    (root / "projects" / "demo").mkdir(parents=True)
    (root / "research_platform" / "core" / "bad.py").write_text("from projects.demo import app\n", encoding="utf-8")
    report = audit_repository_boundary(root)
    codes = {row.code for row in report.violations}
    assert "DOWNSTREAM_PATH_IN_UPSTREAM" in codes
    assert "CORE_IMPORTS_DOWNSTREAM" in codes


def test_packaging_and_image_cannot_embed_downstream(tmp_path: Path) -> None:
    root = _minimal_root(tmp_path)
    (root / "pyproject.toml").write_text('include = ["research_platform*", "projects*"]\n', encoding="utf-8")
    (root / "deploy" / "Dockerfile").write_text("COPY projects ./projects\n", encoding="utf-8")
    codes = {row.code for row in audit_repository_boundary(root).violations}
    assert "PACKAGE_INCLUDES_DOWNSTREAM" in codes
    assert "IMAGE_COPIES_DOWNSTREAM" in codes


def test_release_manifest_cannot_publish_downstream_paths(tmp_path: Path) -> None:
    root = _minimal_root(tmp_path)
    (root / "RELEASE_MANIFEST.json").write_text(
        json.dumps({"files": [{"path": "projects/demo/app.py"}]}), encoding="utf-8"
    )
    report = audit_repository_boundary(root)
    assert any(row.code == "RELEASE_INCLUDES_DOWNSTREAM" for row in report.violations)


def test_current_repository_boundary_passes() -> None:
    root = Path(__file__).resolve().parents[1]
    report = audit_repository_boundary(root, include_release_manifest=False)
    assert report.passed, report.violations
