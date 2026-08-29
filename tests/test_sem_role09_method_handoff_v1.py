from pathlib import Path

from projects.sem_paper.composition import evolution as composition_evolution
from projects.sem_paper.method.self_evolving_memory.evolution.slicing import (
    AutomaticSliceDiscovery,
)


ROOT = Path(__file__).resolve().parents[1]
_HISTORICAL_IMPORT = (
    "projects.sem_paper.method.self_evolving_memory.evolution.diagnostics"
)


def test_role10_composition_binds_role09_slice_authority_directly() -> None:
    assert composition_evolution.AutomaticSliceDiscovery is AutomaticSliceDiscovery
    assert AutomaticSliceDiscovery.__module__.endswith(".evolution.slicing")


def test_role10_production_has_no_historical_role09_diagnostics_import() -> None:
    paths = tuple((ROOT / "projects" / "sem_paper" / "composition").rglob("*.py"))
    paths += tuple((ROOT / "scripts").glob("sem_paper*.py"))
    offenders = [str(path.relative_to(ROOT)) for path in paths if _HISTORICAL_IMPORT in path.read_text(encoding="utf-8")]
    assert offenders == []
