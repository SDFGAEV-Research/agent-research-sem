from __future__ import annotations

import pytest

from research_platform.environment.minecraft.api import (
    MinecraftBridgeSpec,
    MinecraftEndpointSpec,
    MinecraftEnvironmentSpec,
    MinecraftReconciliation,
)
from research_platform.environment.minecraft.runtime.action_coordinator import MinecraftActionCoordinator
from research_platform.environment.minecraft.runtime.checkpoint import MinecraftActionVerification
from research_platform.environment.runtime.api import (
    ActionIdentityViolation,
    ActionReconciliationDisposition,
    ActionRequest,
    action_request_digest,
)
from research_platform.platform.kernel import ExecutionContext


class _Bridge:
    def __init__(self, disposition: ActionReconciliationDisposition = ActionReconciliationDisposition.UNKNOWN) -> None:
        self.disposition = disposition
        self.commands = 0
        self.reconciliations: list[tuple[str, str | None]] = []

    def command(self, command, payload, *, timeout_s):
        self.commands += 1
        raise AssertionError(f"unexpected command: {command}")

    def reconcile_action(self, action_id, *, request, context, request_digest=None):
        self.reconciliations.append((action_id, request_digest))
        return MinecraftReconciliation(action_id, self.disposition, {"source": "unit"})


def _coordinator(bridge: _Bridge) -> MinecraftActionCoordinator:
    spec = MinecraftEnvironmentSpec(
        endpoint=MinecraftEndpointSpec(),
        bridge=MinecraftBridgeSpec(command=("fake-node",), cwd="."),
    )
    return MinecraftActionCoordinator(
        session_id="session",
        generation="a" * 64,
        provider_instance_id="minecraft:session",
        spec=spec,
        bridge=bridge,
        event_log=lambda *args, **kwargs: None,
        failure_log=lambda *args, **kwargs: None,
        ingest_events=lambda *args, **kwargs: None,
        observation=lambda **kwargs: None,
        state_payload=lambda: {},
        last_observation=lambda: None,
    )


def _request(action_id: str = "action-1") -> ActionRequest:
    return ActionRequest(
        action_id,
        "wait",
        {"ms": 1},
        ExecutionContext("run", "trace", "span", task_id="task"),
    )


def test_replace_restores_ledger_identity_without_touching_bridge() -> None:
    bridge = _Bridge()
    coordinator = _coordinator(bridge)
    request = _request()
    coordinator.replace({
        request.action_id: MinecraftActionVerification(
            request_digest=action_request_digest(request), accepted=True, verified=True
        )
    })

    with pytest.raises(ActionIdentityViolation, match="already executed"):
        coordinator.act(request)

    assert bridge.commands == 0
    assert len(coordinator) == 1


def test_snapshot_is_defensive_and_replace_owns_new_ledger() -> None:
    coordinator = _coordinator(_Bridge())
    request = _request()
    verification = MinecraftActionVerification(
        request_digest=action_request_digest(request), accepted=False, verified=None
    )
    coordinator.replace({request.action_id: verification})

    snapshot = coordinator.snapshot()
    snapshot.clear()

    assert len(coordinator) == 1
    assert coordinator.snapshot()[request.action_id] == verification


def test_prepared_unknown_reconciliation_returns_no_action_result() -> None:
    bridge = _Bridge(ActionReconciliationDisposition.UNKNOWN)
    coordinator = _coordinator(bridge)
    request = _request("prepared-1")
    handle = coordinator.prepare_action_recovery(request, request.context)

    result = coordinator.reconcile_prepared_action(handle, request.context)

    assert result.disposition is ActionReconciliationDisposition.UNKNOWN
    assert result.result is None
    assert bridge.reconciliations == [(request.action_id, handle.request_digest)]
