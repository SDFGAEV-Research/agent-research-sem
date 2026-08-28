from pathlib import Path
import tomllib


def test_downstream_package_installs_sem_project_and_manifests():
    root = Path(__file__).resolve().parents[1]
    payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    package_find = payload["tool"]["setuptools"]["packages"]["find"]
    assert "research_platform*" in package_find["include"]
    assert "projects*" in package_find["include"]

    package_data = payload["tool"]["setuptools"]["package-data"]
    assert "experiments/manifests/*.json" in package_data["projects.sem_paper"]

    manifest_root = root / "projects" / "sem_paper" / "experiments" / "manifests"
    assert (manifest_root / "sem_primary_tasks_v1.json").is_file()
    assert (manifest_root / "mindcraft_tasks_v1.json").is_file()
