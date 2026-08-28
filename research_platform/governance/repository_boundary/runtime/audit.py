from __future__ import annotations

import ast
import json
from pathlib import Path

from ..api import RepositoryBoundaryReport, RepositoryBoundaryViolation


_SCHEMA = "platform-repository-boundary.v1"
_FORBIDDEN_ROOTS = (
    "projects",
    "docs/projects",
    "docs/research",
)

_FRAMEWORK_ENVIRONMENT_DIRS = frozenset({"api", "binding", "catalog", "composition", "instance", "providers", "python", "resolution", "runtime", "specification"})
_BUNDLED_ENVIRONMENT_PROVIDERS = frozenset({"minecraft"})
_ALLOWED_ENVIRONMENT_SYSTEMS = frozenset({
    "environment", "environment/binding", "environment/catalog", "environment/instance",
    "environment/instance/identity", "environment/instance/readiness", "environment/minecraft",
    "environment/python", "environment/resolution", "environment/runtime", "environment/specification",
    "environment/specification/digest", "environment/specification/schema",
})


def _violation(code: str, path: str, detail: str) -> RepositoryBoundaryViolation:
    return RepositoryBoundaryViolation(code, path.replace("\\", "/"), detail)


def _audit_forbidden_roots(root: Path) -> list[RepositoryBoundaryViolation]:
    rows: list[RepositoryBoundaryViolation] = []
    for relative in _FORBIDDEN_ROOTS:
        if (root / relative).exists():
            rows.append(_violation("DOWNSTREAM_PATH_IN_UPSTREAM", relative, "downstream-owned path exists in upstream"))
    return rows


def _audit_core_imports(root: Path) -> list[RepositoryBoundaryViolation]:
    rows: list[RepositoryBoundaryViolation] = []
    package_root = root / "research_platform"
    for path in package_root.rglob("*.py") if package_root.exists() else ():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as exc:
            rows.append(_violation("SOURCE_PARSE_FAILED", str(path.relative_to(root)), str(exc)))
            continue
        for node in ast.walk(tree):
            names: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                names = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = (node.module,)
            if any(name == "projects" or name.startswith("projects.") for name in names):
                rows.append(_violation(
                    "CORE_IMPORTS_DOWNSTREAM",
                    str(path.relative_to(root)),
                    f"line {getattr(node, 'lineno', 0)} imports downstream namespace",
                ))
    return rows


def _audit_environment_ownership(root: Path) -> list[RepositoryBoundaryViolation]:
    rows: list[RepositoryBoundaryViolation] = []
    environment_root = root / "research_platform" / "environment"
    allowed_dirs = _FRAMEWORK_ENVIRONMENT_DIRS | _BUNDLED_ENVIRONMENT_PROVIDERS
    if environment_root.is_dir():
        for child in sorted(environment_root.iterdir(), key=lambda path: path.name):
            if child.is_dir() and not child.name.startswith("__") and child.name not in allowed_dirs:
                rows.append(_violation("CONCRETE_ENVIRONMENT_IN_UPSTREAM", str(child.relative_to(root)), "environment provider is not an approved bundled upstream provider"))
    catalog = root / "research_platform" / "governance" / "system_registry" / "catalog.json"
    if catalog.is_file():
        try:
            payload = json.loads(catalog.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            rows.append(_violation("SYSTEM_CATALOG_INVALID", str(catalog.relative_to(root)), str(exc)))
            return rows
        if isinstance(payload, dict):
            for key in payload:
                if (key == "environment" or key.startswith("environment/")) and key not in _ALLOWED_ENVIRONMENT_SYSTEMS:
                    rows.append(_violation("REGISTRY_OWNS_DOWNSTREAM_ENVIRONMENT", str(catalog.relative_to(root)), f"unapproved environment system: {key}"))
    return rows


def _audit_metadata(root: Path) -> list[RepositoryBoundaryViolation]:
    rows: list[RepositoryBoundaryViolation] = []
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        if 'projects*' in text or 'projects.' in text:
            rows.append(_violation("PACKAGE_INCLUDES_DOWNSTREAM", "pyproject.toml", "package discovery includes downstream code"))

    dockerfile = root / "deploy" / "Dockerfile"
    if dockerfile.is_file():
        text = dockerfile.read_text(encoding="utf-8").lower()
        if "copy projects" in text:
            rows.append(_violation("IMAGE_COPIES_DOWNSTREAM", "deploy/Dockerfile", "generic image copies downstream project source"))
    return rows


def _audit_release_manifest(root: Path) -> list[RepositoryBoundaryViolation]:
    manifest = root / "RELEASE_MANIFEST.json"
    if not manifest.is_file():
        return []
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [_violation("RELEASE_MANIFEST_INVALID", "RELEASE_MANIFEST.json", str(exc))]
    text = json.dumps(payload, sort_keys=True)
    forbidden = ("projects/", "docs/projects/", "docs/research/")
    if any(token in text for token in forbidden):
        return [_violation("RELEASE_INCLUDES_DOWNSTREAM", "RELEASE_MANIFEST.json", "release inventory contains downstream-owned paths")]
    return []


def audit_repository_boundary(root: Path, *, include_release_manifest: bool = True) -> RepositoryBoundaryReport:
    resolved = Path(root).resolve()
    violations = (
        _audit_forbidden_roots(resolved)
        + _audit_core_imports(resolved)
        + _audit_environment_ownership(resolved)
        + _audit_metadata(resolved)
        + (_audit_release_manifest(resolved) if include_release_manifest else [])
    )
    ordered = tuple(sorted(violations, key=lambda row: (row.code, row.path, row.detail)))
    return RepositoryBoundaryReport(_SCHEMA, ordered)


__all__ = ["audit_repository_boundary"]
