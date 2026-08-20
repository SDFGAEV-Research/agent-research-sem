from pathlib import Path
from dataclasses import replace

from projects.sem_paper import PROJECT_DEFINITION
from projects.sem_paper.composition import (
    SemPaperCompositionPorts,
    SemPaperMethodResolver,
    compose_sem_paper,
)
from projects.sem_paper.composition.logging import bind_project_logging
from research_platform.governance.architecture.source_invariants import audit_source_invariants
from research_platform.observability.logging.api import (
    DiagnosticAddress,
    LogLevel,
    LogRecord,
    LogSinkPort,
)
from research_platform.participant.method.api import MethodCompositionPorts
from research_platform.participant.method.runtime import DefaultMethodEndpointFactory
from research_platform.platform.composition.participants.method import method_participant_adapter
from research_platform.scope.api import ScopeIdentity


class _Sink(LogSinkPort):
    def __init__(self) -> None:
        self.rows: list[LogRecord] = []

    def append(self, record: LogRecord) -> None:
        self.rows.append(record)


def test_sem_paper_declares_system_capabilities_not_concrete_providers():
    keys = {row.key for row in PROJECT_DEFINITION.capabilities}
    assert "observability:logging" in keys
    assert "participant:method.runtime" in keys
    assert {row.treatment_id for row in PROJECT_DEFINITION.methods} == {"fixed_memory", "self_evolving"}


def test_sem_paper_can_customize_logging_through_log_sink_port_only():
    downstream = _Sink()
    sink = bind_project_logging(downstream)
    record = LogRecord(
        log_id="log-1",
        created_at=1.0,
        level=LogLevel.INFO,
        logger="test",
        event="paper.event",
        message="ok",
        address=DiagnosticAddress((ScopeIdentity("project", "sem-paper-1"),)),
    )
    sink.append(record)
    attrs = dict(downstream.rows[0].attributes)
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
            return DefaultMethodEndpointFactory().bind(implementation, runtime)

    class Sink(LogSinkPort):
        def append(self, record: LogRecord) -> None:
            del record

    ports = SemPaperCompositionPorts(
        method_system=MethodCompositionPorts(EndpointFactory(), object()),
        log_sink=Sink(),
        evolution_factory=lambda source: object(),
        evolution_provider_id="sem.evolution.project-test.v1",
    )
    bindings = compose_sem_paper(ports)

    assert bindings.definition is PROJECT_DEFINITION
    assert bindings.logging is not ports.log_sink
    assert len(bound) == 2
    assert bindings.fixed_memory.identity.method_id == "self_evolving_memory"
    assert bindings.self_evolving.identity.method_id == "self_evolving_memory"
    adapter = method_participant_adapter(bindings.method_resolver)
    for variant in bindings.method_variants:
        participant = adapter.resolve(variant.binding)
        adapter.validate(variant.binding, participant)
        assert participant.endpoint.identity.method_id == "self_evolving_memory"


def test_project_method_projection_fails_closed_on_unknown_or_colliding_identity():
    class EndpointFactory:
        def bind(self, implementation, runtime):
            return DefaultMethodEndpointFactory().bind(implementation, runtime)

    class Sink(LogSinkPort):
        def append(self, record: LogRecord) -> None:
            del record

    bindings = compose_sem_paper(
        SemPaperCompositionPorts(
            method_system=MethodCompositionPorts(EndpointFactory(), object()),
            log_sink=Sink(),
            evolution_factory=lambda source: object(),
            evolution_provider_id="sem.evolution.project-test.v1",
        )
    )
    variant = bindings.method_variants[0]
    unknown = replace(
        variant.binding,
        implementation=replace(variant.binding.implementation, participant_id="unknown"),
    )
    try:
        bindings.method_resolver.resolve(unknown)
    except KeyError:
        pass
    else:
        raise AssertionError("unknown Paper-1 method identity must fail closed")

    try:
        SemPaperMethodResolver(
            (("one", bindings.fixed_memory), ("two", bindings.fixed_memory))
        )
    except ValueError:
        pass
    else:
        raise AssertionError("colliding Paper-1 method projections must fail closed")
