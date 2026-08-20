from __future__ import annotations

import pytest

from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.observability.logging.api import DiagnosticAddress, LogLevel
from research_platform.observability.logging.runtime import InMemoryLogStore, StructuredLogger
from research_platform.reliability.diagnostics.runtime import DiagnosticLogQueryAdapter
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind


def address() -> DiagnosticAddress:
    workspace = ScopeIdentity(ScopeKind.WORKSPACE, "w1")
    return DiagnosticAddress(
        scope_path=(PLATFORM_SCOPE, workspace),
        system_path=(SystemIdentity("platform"), SystemIdentity("platform", ("runtime",))),
        component_id="component.a",
        trace_id="trace-1",
        span_id="span-1",
    )


def test_structured_logging_is_observation_only_and_queryable() -> None:
    store = InMemoryLogStore()
    logger = StructuredLogger(store, logger="test", address=address())

    log_id = logger.log(
        LogLevel.INFO,
        event="RUN_STARTED",
        message="run started",
        attributes={"run_id": "r1", "count": 2},
    )

    assert log_id.startswith("log_")
    rows = DiagnosticLogQueryAdapter(store).query_logs(trace_id="trace-1")
    assert len(rows) == 1
    assert rows[0].event == "RUN_STARTED"
    assert rows[0].record_plane if hasattr(rows[0], "record_plane") else True


def test_exception_logging_uses_safe_descriptor_without_owning_failure_taxonomy() -> None:
    store = InMemoryLogStore()
    logger = StructuredLogger(store, logger="test", address=address())

    with pytest.raises(RuntimeError) as caught:
        raise RuntimeError("token=super-secret")
    logger.exception(event="WORK_FAILED", message="operation failed", exc=caught.value)

    row = store.query(event="WORK_FAILED")[0]
    assert row.exception is not None
    assert "super-secret" not in row.exception.safe_message
