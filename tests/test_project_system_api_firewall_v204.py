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
from research_platform.scope.api import ScopeIdentity, ScopeKind


class _Sink(LogSinkPort):
    def __init__(self) -> None:
        self.rows: list[LogRecord] = []

    def append(self, record: LogRecord) -> None:
        self.rows.append(record)


def compose_test_logging(store: InMemoryLogStore):
    meta = build_in_memory_platform_meta()
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
        planner=meta.capability_composition,
    ).logging


def test_sem_paper_declares_system_capabilities_not_concrete_providers():
    keys = {row.key for row in PROJECT_DEFINITION.capabilities}
    assert "observability:logging" in keys
    assert "participant:method.runtime" in keys
    assert {row.treatment_id for row in PROJECT_DEFINITION.methods} == {"fixed_memory", "self_evolving"}


def test_sem_paper_can_customize_logging_through_log_sink_port_only():
    downstream = InMemoryLogStore()
    logging = bind_project_logging(compose_test_logging(downstream))
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

    ports = SemPaperCompositionPorts(
        method_system=MethodCompositionPorts(EndpointFactory(), object()),
        logging=compose_test_logging(store),
        evolution_factory=lambda source: object(),
        evolution_provider_id="sem.evolution.project-test.v1",
    )
    bindings = compose_sem_paper(ports)

    assert bindings.definition is PROJECT_DEFINITION
    assert bindings.logging is not ports.logging
    assert len(bound) == 2
    assert bindings.fixed_memory[0].method_id == "self_evolving_memory"
    assert bindings.self_evolving[0].method_id == "self_evolving_memory"
