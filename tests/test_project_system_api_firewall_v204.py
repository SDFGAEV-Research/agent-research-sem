from pathlib import Path

from projects.sem_paper import PROJECT_DEFINITION
from projects.sem_paper.composition import (
    SemPaperCompositionPorts,
    compose_sem_paper,
)
from projects.sem_paper.composition.logging import bind_project_logging
from research_platform.governance.architecture.source_invariants import audit_source_invariants
from research_platform.observability.logging.composition import (
    LogQueryBinding,
    LogSinkBinding,
    compose_logging_system,
)
from research_platform.observability.logging.context.api import DiagnosticAddress
from research_platform.observability.logging.record.api import LogLevel, LogRecord
from research_platform.observability.logging.sink.api import LogSinkPort
from research_platform.observability.logging.storage.runtime import InMemoryLogStore
from research_platform.participant.method.api import MethodCompositionPorts
from research_platform.platform.composition.platform_meta import build_in_memory_platform_meta
from research_platform.platform.kernel import canonical_digest
from research_platform.participant.method.composition import (
    MethodSystemProviders,
    compose_method_system,
)
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind
from projects.sem_paper.method.self_evolving_memory.serving_providers import build_deluxe_session_serving


class _Sink(LogSinkPort):
    def __init__(self) -> None:
        self.rows: list[LogRecord] = []

    def append(self, record: LogRecord) -> None:
        self.rows.append(record)


def compose_test_logging(store: InMemoryLogStore, *, planner=None):
    meta = build_in_memory_platform_meta() if planner is None else None
    return compose_logging_system(
        sink=LogSinkBinding(
            store,
            "tests.in-memory-log-store.v1",
            canonical_digest({"store": "in-memory"}),
        ),
        query=LogQueryBinding(
            store,
            "tests.in-memory-log-store.v1",
            canonical_digest({"store": "in-memory"}),
        ),
        planner=meta.capability_composition if meta is not None else planner,
    )


def sem_project_scope(meta) -> ScopeIdentity:
    workspace = ScopeIdentity(ScopeKind.WORKSPACE, "tests")
    program = ScopeIdentity(ScopeKind.PROGRAM, "papers")
    project = ScopeIdentity(ScopeKind.PROJECT, "sem-paper-1")
    meta.scopes.register(workspace, PLATFORM_SCOPE)
    meta.scopes.register(program, workspace)
    meta.scopes.register(project, program)
    return project


def test_sem_paper_declares_system_capabilities_not_concrete_providers():
    keys = {row.key for row in PROJECT_DEFINITION.capabilities}
    assert "observability:logging" in keys
    assert "participant:method.runtime" in keys
    assert {row.treatment_id for row in PROJECT_DEFINITION.methods} == {"fixed_memory", "self_evolving"}


def test_sem_paper_can_customize_logging_through_log_sink_port_only():
    downstream = InMemoryLogStore()
    logging = bind_project_logging(compose_test_logging(downstream).logging)
    writer = logging.bind(
        logger="test",
        address=DiagnosticAddress((ScopeIdentity(ScopeKind.PROJECT, "sem-paper-1"),)),
    )
    writer.log(LogLevel.INFO, event="paper.event", message="ok")
    attrs = dict(downstream.query(event="paper.event")[0].attributes)
    assert attrs["project_id"] == "sem-paper-1"
    assert attrs["paper_method"] == "self_evolving_memory"


def test_repository_project_obeys_system_api_firewall():
    root = Path(__file__).resolve().parents[1]
    violations = [v for v in audit_source_invariants(root) if v.invariant == "project_system_api_firewall"]
    assert violations == []


def test_paper_method_is_project_owned_and_historical_methods_root_is_retired():
    root = Path(__file__).resolve().parents[1]
    method_root = root / "projects" / "sem_paper" / "method" / "self_evolving_memory"
    assert method_root.is_dir()
    assert (method_root / "composition.py").is_file()
    assert not (root / "methods").exists()


def test_project_root_binds_both_paper_treatments_through_injected_method_ports():
    bound: list[tuple[object, object]] = []

    class EndpointFactory:
        def bind(self, implementation, runtime):
            bound.append((implementation, runtime))
            return (implementation.identity, runtime.runtime_identity)

    store = InMemoryLogStore()
    meta = build_in_memory_platform_meta()
    project_scope = sem_project_scope(meta)
    ports = SemPaperCompositionPorts(
        method_system=compose_method_system(
            providers=MethodSystemProviders(
                EndpointFactory(),
                object(),
                "tests.method-system.v1",
                canonical_digest({"provider": "tests.method-system"}),
            ),
            planner=meta.capability_composition,
        ),
        logging=compose_test_logging(store, planner=meta.capability_composition),
        planner=meta.capability_composition,
        scope=project_scope,
        evolution_factory=lambda source: object(),
        evolution_provider_id="sem.evolution.project-test.v1",
    )
    composition = compose_sem_paper(ports)
    bindings = composition.bindings

    assert bindings.definition is PROJECT_DEFINITION
    assert bindings.logging is not ports.logging.logging
    assert len(bound) == 2
    assert bindings.fixed_memory[0].method_id == "self_evolving_memory"
    assert bindings.self_evolving[0].method_id == "self_evolving_memory"
    assert {edge.requirement.requirement_id for edge in composition.plan.edges} == {
        "logging-system",
        "method-composition-ports",
    }


def test_project_root_keeps_fixed_and_self_evolving_serving_projections_separate():
    bound: list[object] = []

    class EndpointFactory:
        def bind(self, implementation, runtime):
            bound.append(implementation)
            return (implementation.identity, runtime.runtime_identity)

    store = InMemoryLogStore()
    meta = build_in_memory_platform_meta()
    project_scope = sem_project_scope(meta)
    fixed_snapshot_factory = object()
    evolving_snapshot_factory = object()
    ports = SemPaperCompositionPorts(
        method_system=compose_method_system(
            providers=MethodSystemProviders(
                EndpointFactory(),
                object(),
                "tests.method-system.deluxe.v1",
                canonical_digest({"provider": "tests.method-system.deluxe"}),
            ),
            planner=meta.capability_composition,
        ),
        logging=compose_test_logging(store, planner=meta.capability_composition),
        planner=meta.capability_composition,
        scope=project_scope,
        evolution_factory=lambda source: object(),
        evolution_provider_id="sem.evolution.project-deluxe-test.v1",
        serving_factory=build_deluxe_session_serving,
        serving_provider_id="sem.serving.deluxe.project-test.v1",
        fixed_deluxe_snapshot_factory=fixed_snapshot_factory,
        self_evolving_serving_factory=build_deluxe_session_serving,
        self_evolving_deluxe_snapshot_factory=evolving_snapshot_factory,
    )

    compose_sem_paper(ports)

    assert len(bound) == 2
    assert all(item.serving_provider_id == "sem.serving.deluxe.project-test.v1" for item in bound)
    assert bound[0].deluxe_snapshot_factory is fixed_snapshot_factory
    assert bound[1].deluxe_snapshot_factory is evolving_snapshot_factory
