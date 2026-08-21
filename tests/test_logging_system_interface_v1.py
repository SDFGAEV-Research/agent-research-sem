from __future__ import annotations

from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.observability.logging.composition import build_logging_system
from research_platform.observability.logging.context.api import DiagnosticAddress
from research_platform.observability.logging.record.api import ExceptionDescriptorPort, LogLevel
from research_platform.observability.logging.storage.runtime import InMemoryLogStore
from research_platform.scope.api import PLATFORM_SCOPE


class MarkerExceptionDescriptor(ExceptionDescriptorPort):
    def describe(self, exc: BaseException):
        from research_platform.platform.kernel.errors import SafeExceptionDescriptor

        return SafeExceptionDescriptor(
            error_type="custom",
            qualified_type="custom.Error",
            safe_message="custom-safe",
            error_digest="d" * 64,
        )


def address() -> DiagnosticAddress:
    return DiagnosticAddress(
        scope_path=(PLATFORM_SCOPE,),
        system_path=(SystemIdentity("platform"),),
        component_id="test.component",
        trace_id="trace-1",
    )


def test_logging_system_binds_internal_writer_and_unified_query() -> None:
    store = InMemoryLogStore()
    logging = build_logging_system(store, store)
    writer = logging.bind(logger="platform.test", address=address())
    writer.child(component_id="child").failure(
        event="FAILURE_OBSERVED",
        message="failure reference",
        failure_id="failure-1",
    )

    rows = logging.query(trace_id="trace-1")
    assert len(rows) == 1
    assert rows[0].failure_refs == ("failure-1",)
    assert dict(rows[0].attributes) == {}


def test_exception_policy_is_injected_at_logging_composition() -> None:
    store = InMemoryLogStore()
    logging = build_logging_system(
        store,
        store,
        exception_descriptor=MarkerExceptionDescriptor(),
    )
    writer = logging.bind(logger="platform.test", address=address())
    writer.exception(event="BROKEN", message="broken", exc=RuntimeError("raw"))
    row = store.query(event="BROKEN")[0]
    assert row.exception is not None
    assert row.exception.safe_message == "custom-safe"
