from __future__ import annotations

from pathlib import Path

from scripts.sem_paper_architecture_audit import _call_keyword_sets, _opaque_api_inventory, _production_confirmatory_core6_semantics, _selected_api_sources


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


def test_confirmatory_core6_audit_requires_real_ast_call_chain() -> None:
    production = """
def _study_protocol_factory_for_mode(mode):
    return build_sem_paper_conformance_protocol if mode == 'scripted-smoke' else build_sem_paper_confirmatory_protocol

def run(inputs):
    protocol_factory = _study_protocol_factory_for_mode(inputs.mode)
    study_protocol = protocol_factory(study_id='s')
    return compile_sem_paper_experiment_plan(study_protocol)
"""
    closure = """
def gate(plan):
    return is_confirmatory_protocol(plan.protocol)
"""
    assert _production_confirmatory_core6_semantics(production, closure)


def test_confirmatory_core6_audit_rejects_symbol_co_presence_without_call_chain() -> None:
    production = "build_sem_paper_confirmatory_protocol = object()\nis_confirmatory_protocol = object()\n"
    closure = "text = 'is_confirmatory_protocol(plan.protocol)'\n"
    assert not _production_confirmatory_core6_semantics(production, closure)


def test_current_production_confirmatory_core6_call_chain_is_semantic() -> None:
    production = Path('scripts/sem_paper_minecraft_application.py').read_text(encoding='utf-8')
    closure = Path('projects/sem_paper/composition/scientific_closure.py').read_text(encoding='utf-8')
    assert _production_confirmatory_core6_semantics(production, closure)


def test_opaque_api_audit_distinguishes_private_decoder_from_public_contract(tmp_path, monkeypatch) -> None:
    import scripts.sem_paper_architecture_audit as audit
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    private = tmp_path / "private_api.py"
    private.write_text("def _require(value: object) -> str:\n    return str(value)\n", encoding="utf-8")
    assert audit._opaque_api_inventory((private,)) == ()
    public = tmp_path / "public_api.py"
    public.write_text("def publish(payload: object) -> str:\n    return str(payload)\n", encoding="utf-8")
    rows = audit._opaque_api_inventory((public,))
    assert len(rows) == 1
    assert rows[0]["line"] == 1


def test_current_selected_platform_api_surfaces_have_no_opaque_public_contracts() -> None:
    assert _opaque_api_inventory(_selected_api_sources()) == ()
