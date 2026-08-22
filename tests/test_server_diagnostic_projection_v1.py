from __future__ import annotations

from research_platform.runtime.server.api import (
    ServerOperationEffect,
    ServerOperationKind,
    ServerOperationStarted,
)
from research_platform.runtime.server.health.api import (
    ServerDiagnosticStatus,
    ServerHealthReport,
    ServerSessionDiagnostic,
)
from research_platform.runtime.server.health.runtime import ServerDiagnosticProjector
from research_platform.runtime.server.identity.api import ServerCommandResult


def _health(*, server_id: str = "sem-ubuntu", ready: bool = True) -> ServerHealthReport:
    return ServerHealthReport(
        server_id=server_id,
        reachable=ready,
        host_name="remote",
        python_version="3.10",
        git_version=None,
        tmux_version=None,
        raw=ServerCommandResult(server_id, "health", 0 if ready else 255, "", ""),
        platform_ready=ready,
        checks=() if ready else (("python_binary_identity", "mismatch"),),
        issues=() if ready else ("python_binary_identity",),
    )


def _pending(*, profile_digest: str) -> object:
    return ServerOperationStarted(
        "op-uncertain",
        "sem-ubuntu",
        ServerOperationKind.FILE_UPLOAD,
        "request-digest",
        1.0,
        False,
        profile_digest,
        ServerOperationEffect.MUTATION,
    )


def test_diagnostic_marks_old_profile_uncertainty_as_actionable() -> None:
    from research_platform.runtime.server.api import ServerOperationRecord

    record = ServerOperationRecord(_pending(profile_digest="old-profile"))
    report = ServerDiagnosticProjector().project(
        server_id="sem-ubuntu",
        profile_digest="current-profile",
        operation_log="/tmp/server-operations.jsonl",
        health=_health(),
        pending_operations=(record,),
        recent_operations=(record,),
    )

    assert report.status == ServerDiagnosticStatus.RECONCILIATION_REQUIRED
    assert not report.ready_for_mutation
    assert report.issues[0].code == "operation_profile_reconciliation_required"


def test_diagnostic_joins_exact_health_and_session_without_command_side_effects() -> None:
    session = ServerSessionDiagnostic(
        "research-platform-shell",
        "drift",
        "controller command differs",
        reason_code="controller_command_drift",
        evidence_refs=("session-binding:abc",),
    )
    report = ServerDiagnosticProjector().project(
        server_id="sem-ubuntu",
        profile_digest="current-profile",
        operation_log="/tmp/server-operations.jsonl",
        health=_health(),
        pending_operations=(),
        recent_operations=(),
        session=session,
    )

    assert report.status == ServerDiagnosticStatus.READY
    assert report.ready_for_mutation
    assert report.session == session
    assert report.issues[0].code == "session:drift"
