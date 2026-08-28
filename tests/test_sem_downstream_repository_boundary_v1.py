from pathlib import Path
import subprocess


def test_downstream_does_not_override_upstream_platform_tree():
    root = Path(__file__).resolve().parents[1]
    if not (root / ".git").exists():
        return
    result = subprocess.run(
        ["git", "diff", "--name-only", "upstream/master..HEAD", "--", "research_platform"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert not result.stdout.strip(), result.stdout


def test_platform_source_never_imports_sem_project():
    root = Path(__file__).resolve().parents[1]
    offenders = []
    for path in (root / "research_platform").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "projects.sem_paper" in text or "from projects" in text:
            offenders.append(path.relative_to(root).as_posix())
    assert not offenders, offenders
