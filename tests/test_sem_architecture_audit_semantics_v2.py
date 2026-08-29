from __future__ import annotations

from pathlib import Path

from scripts.sem_paper_architecture_audit import (
    _call_keyword_sets,
    _public_opaque_inventory,
)


def test_build_runtime_keyword_audit_is_independent_of_tuple_unpacking() -> None:
    source = """
root, host, log_store, concurrency = build_runtime(
    inputs,
    evolution_factory=factory,
    evolution_bindings=bindings,
    qualified_binding=qualified,
)
"""
    rows = _call_keyword_sets(source, "build_runtime")
    assert rows == (
        frozenset({"evolution_factory", "evolution_bindings", "qualified_binding"}),
    )


def test_build_runtime_keyword_audit_ignores_comments_and_strings() -> None:
    source = '# build_runtime(evolution_factory=fake)\ntext = "qualified_binding=not-a-call"\n'
    assert _call_keyword_sets(source, "build_runtime") == ()


def test_current_production_call_binds_scientific_runtime_authorities() -> None:
    source = Path("scripts/sem_paper_minecraft_application.py").read_text(encoding="utf-8")
    calls = _call_keyword_sets(source, "build_runtime")
    assert any(
        {"evolution_factory", "evolution_bindings", "qualified_binding"} <= set(keywords)
        for keywords in calls
    )
    assert "build_sem_paper_evolution_factory(bound_evolution)" in source
    assert "PersistedQualifiedModelEndpointBinding(closure).binding_for(" in source
    assert 'if inputs.mode == "baseline" and qualified_binding is None:' in source


def test_private_runtime_validator_object_input_is_not_public_api() -> None:
    source = "def _require_value(value: object) -> str:\n    return str(value)\n"
    path = Path(__file__).resolve().parents[1] / ".local" / "synthetic_contracts.py"
    assert _public_opaque_inventory(path, source) == ()


def test_public_opaque_annotation_remains_visible_to_audit() -> None:
    source = "def publish(value: object) -> str:\n    return str(value)\n"
    path = Path(__file__).resolve().parents[1] / ".local" / "synthetic_contracts.py"
    rows = _public_opaque_inventory(path, source)
    assert len(rows) == 1
    assert rows[0]["symbol"] == "publish"
