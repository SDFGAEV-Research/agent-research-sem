from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class ProjectMetadata:
    name: str
    version: str
    python_requires: str
    source: str


def load_project_metadata(root: Path, *, allow_unversioned: bool = True) -> ProjectMetadata:
    """Resolve release identity from one project authority.

    Source trees use pyproject.toml. Installed deployments may fall back to package
    metadata. Synthetic test trees are explicitly marked unversioned rather than
    inheriting a stale hard-coded release number.
    """

    root = Path(root)
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = data.get("project", {})
        name = str(project.get("name") or "")
        version = str(project.get("version") or "")
        python_requires = str(project.get("requires-python") or "")
        if not name or not version or not python_requires:
            raise ValueError("pyproject.toml must define project.name, project.version, and project.requires-python")
        return ProjectMetadata(name, version, python_requires, "pyproject.toml")

    try:
        version = importlib_metadata.version("research-platform")
    except importlib_metadata.PackageNotFoundError:
        if not allow_unversioned:
            raise RuntimeError("project version authority not found")
        return ProjectMetadata("unversioned", "unversioned", ">=3.11", "synthetic")
    return ProjectMetadata("research-platform", version, ">=3.11", "installed-metadata")
