from __future__ import annotations

import json
import queue
import subprocess
from typing import Any

import pytest

from research_platform.environment.minecraft.api import (
    MinecraftBridgeEnvelope,
    MinecraftBridgeSpec,
    MinecraftEndpointSpec,
    MinecraftEnvironmentSpec,
    MinecraftObservationEvent,
    MinecraftServerSpec,
)
from research_platform.environment.minecraft.providers.readiness import (
    parse_java_major,
    parse_node_major,
    probe_node,
    probe_node_package,
)
from research_platform.environment.minecraft.providers.jsonl_bridge import JsonlMinecraftBridge
from research_platform.environment.minecraft.providers.server_files import (
    MinecraftServerPreparationError,
    prepare_server_files,
)
from research_platform.environment.minecraft.composition.server_service import (
    MinecraftServerServiceController,
    build_server_service_contract,
)
from research_platform.environment.minecraft.composition.diagnostics import (
    StructuredMinecraftDiagnostics,
)
from research_platform.environment.minecraft.composition.environment import compose_minecraft_environment
from research_platform.environment.minecraft.runtime import MinecraftStateProjection
from research_platform.environment.runtime.api import ActionReconciliationDisposition, ActionRequest
from research_platform.observability.logging.context.api import DiagnosticAddress
from research_platform.observability.logging.record.api import LogRecord
from research_platform.observability.logging.record.runtime import StructuredLogger
from research_platform.platform.kernel import ExecutionContext
from research_platform.runtime.service.api import (
    ServiceProcessIdentity,
    ServiceReadyObservation,
    ServiceReconcileObservation,
    ServiceStartOutcome,
    ServiceStopOutcome,
)
from research_platform.scope.api import ScopeIdentity, ScopeKind


def test_bridge_envelope_is_strict_and_preserves_wire_identity() -> None:
    envelope = MinecraftBridgeEnvelope.from_mapping(
        {
            "type": "event",
            "kind": "self_snapshot",
            "ts_ms": 123,
            "seq": 9,
            "source": "mineflayer",
            "request_id": "request-1",
            "payload": {"username": "bot"},
        }
    )
    event = envelope.as_observation()
    assert event.kind == "self_snapshot"
    assert event.timestamp_ms == 123
    assert event.sequence == 9
    assert event.request_id == "request-1"
    with pytest.raises(ValueError, match="type=event"):
        MinecraftBridgeEnvelope.from_mapping({"type": "ack"})


def test_state_projection_reuses_v034_reduction_invariant_and_is_bounded() -> None:
    state = MinecraftStateProjection(max_entities=1)
    state.ingest(
        MinecraftObservationEvent(
            "self_snapshot",
            {
                "username": "bot",
                "position": {"x": 1, "y": 2, "z": 3},
                "health": 20,
                "food": 18,
                "inventory": [{"name": "oak_log", "count": 3}],
                "dimension": "overworld",
            },
            sequence=1,
        )
    )
    state.ingest(
        MinecraftObservationEvent(
            "entity_observation", {"uuid": "a", "name": "cow"}, sequence=2
        )
    )
    state.ingest(
        MinecraftObservationEvent(
            "entity_observation", {"uuid": "b", "name": "pig"}, sequence=3
        )
    )
    state.ingest(
        MinecraftObservationEvent(
            "action_result",
            {"verified": True, "action": {"tool": "wait"}, "outcome": {"waited_ms": 1}},
            sequence=4,
        )
    )
    assert state.username == "bot"
    assert state.anchor("spawn") == {"x": 1.0, "y": 2.0, "z": 3.0}
    assert tuple(state.entities) == ("b",)
    assert state.last_action_verified is True
    assert state.snapshot_digest() == state.snapshot_digest()

    with pytest.raises(ValueError, match="sequence regressed"):
        state.ingest(MinecraftObservationEvent("health", {"health": 1}, sequence=2))


def test_readiness_parsers_and_probe_codes_are_actionable() -> None:
    assert parse_node_major("v22.1.0") == 22
    assert parse_java_major('openjdk version "21.0.8" 2025-07-15') == 21

    def runner(command, **_kwargs):
        if command[0] == "node" and command[1] == "--version":
            return subprocess.CompletedProcess(command, 0, "v22.1.0\n", "")
        return subprocess.CompletedProcess(command, 1, "", "MODULE_NOT_FOUND")

    assert probe_node(runner=runner).ok is True
    missing = probe_node_package("/bridge", package_name="mineflayer", runner=runner)
    assert missing.ok is False
    assert missing.cause_code == "PACKAGE_NOT_RESOLVABLE"


def test_mc_spec_is_independent_of_old_runtime_package() -> None:
    spec = MinecraftEnvironmentSpec(
        endpoint=MinecraftEndpointSpec(),
        bridge=MinecraftBridgeSpec(command=("node", "bridge.js"), cwd="/bridge"),
    )
    assert spec.provider_id == "minecraft.mineflayer.jsonl.v1"
    assert spec.endpoint.port == 25565


class _QueueReader:
    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._closed = False

    def put(self, value: str) -> None:
        self._queue.put(value)

    def readline(self) -> str:
        if self._closed and self._queue.empty():
            return ""
        return self._queue.get()

    def close(self) -> None:
        self._closed = True
        self._queue.put("")


class _FakeProcess:
    _next_pid = 1000

    def __init__(self) -> None:
        self.pid = _FakeProcess._next_pid
        _FakeProcess._next_pid += 1
        self.stdout = _QueueReader()
        self.stderr = _QueueReader()
        self.stdin = self
        self.returncode: int | None = None

    def write(self, line: str) -> int:
        message = json.loads(line)
        command = str(message["cmd"])
        request_id = message.get("request_id")
        if command == "connect":
            self._event("bridge_status", {"status": "spawned", "version": "1.21.6"}, request_id)
            self._ack(command, request_id)
        elif command == "wait":
            self._event(
                "action_result",
                {
                    "action_id": message.get("action_id"),
                    "verified": True,
                    "action": {"tool": "wait"},
                    "outcome": {"waited_ms": 1},
                },
                request_id,
            )
            self._ack(command, request_id, verified=True)
        elif command == "quit":
            self._ack(command, request_id)
            self.returncode = 0
            self.stdout.close()
            self.stderr.close()
        return len(line)

    def flush(self) -> None:
        return None

    def _event(self, kind: str, payload: dict[str, Any], request_id: str | None) -> None:
        value = {"type": "event", "kind": kind, "seq": 1, "ts_ms": 1, "payload": payload}
        if request_id:
            value["request_id"] = request_id
        self.stdout.put(json.dumps(value) + "\n")

    def _ack(self, command: str, request_id: str | None, **payload: Any) -> None:
        value = {"type": "ack", "cmd": command, **payload}
        if request_id:
            value["request_id"] = request_id
        self.stdout.put(json.dumps(value) + "\n")

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15
        self.stdout.close()
        self.stderr.close()

    def kill(self) -> None:
        self.returncode = -9
        self.stdout.close()
        self.stderr.close()


class _Diagnostics:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.failures: list[str] = []
        self.metrics: list[str] = []

    def event(self, *, phase, event, attributes=None, level="DEBUG", correlation_refs=()):
        del attributes, level, correlation_refs
        self.events.append((phase, event))

    def failure(self, *, phase, code, message, exception=None, attributes=None, correlation_refs=()):
        del phase, message, exception, attributes, correlation_refs
        self.failures.append(code)

    def metric(self, *, name, value, labels=None):
        del value, labels
        self.metrics.append(name)


class _LogSink:
    def __init__(self) -> None:
        self.records: list[LogRecord] = []

    def append(self, record: LogRecord) -> None:
        self.records.append(record)


class _MetricSink:
    def __init__(self) -> None:
        self.rows: list[tuple[ExecutionContext, str, float, dict[str, str]]] = []

    def observe(self, context, name, value, **dimensions):
        self.rows.append((context, name, value, dimensions))


class _FailureLedger:
    def __init__(self) -> None:
        self.failures: list[object] = []

    def append_failure_once(self, failure):
        self.failures.append(failure)
        return True, "failure-ref"


def test_jsonl_bridge_preserves_action_identity_and_reconciliation_proof() -> None:
    endpoint = MinecraftEndpointSpec(version="1.21.6")
    spec = MinecraftBridgeSpec(command=("fake-node",), cwd=".", command_timeout_s=1, connect_timeout_s=1)
    diagnostics = _Diagnostics()
    bridge = JsonlMinecraftBridge(
        endpoint=endpoint,
        spec=spec,
        process_factory=lambda _command, **_kwargs: _FakeProcess(),
        diagnostics=diagnostics,
    )
    bridge.start()
    result = bridge.command("wait", {"action_id": "action-1", "ms": 1}, timeout_s=1)
    assert result.acknowledged is True
    assert result.verified is True
    assert result.events[0].request_id == "action-1"
    assert ("start", "BRIDGE_PROCESS_READY") in diagnostics.events
    assert ("command", "BRIDGE_COMMAND_START") in diagnostics.events
    assert "minecraft.bridge.command_latency_s" in diagnostics.metrics

    context = ExecutionContext("run", "trace", "span", task_id="task")
    request = ActionRequest("action-1", "wait", {"ms": 1}, context)
    proof = bridge.reconcile_action("action-1", request=request, context=context)
    assert proof.disposition is ActionReconciliationDisposition.APPLIED
    bridge.close()


def test_minecraft_diagnostics_composition_unifies_log_metric_and_failure_ports() -> None:
    log_sink = _LogSink()
    logger = StructuredLogger(
        log_sink,
        logger="environment.minecraft",
        address=DiagnosticAddress((ScopeIdentity(ScopeKind.PROJECT, "paper"),)),
    )
    context = ExecutionContext("run", "trace", "span", task_id="task")
    metric_sink = _MetricSink()
    failure_ledger = _FailureLedger()
    materialized: list[dict[str, object]] = []

    def materializer(**kwargs):
        materialized.append(kwargs)
        return {"failure_code": kwargs["code"], "phase": kwargs["phase"]}

    diagnostics = StructuredMinecraftDiagnostics(
        logger=logger,
        context=lambda: context,
        metrics=metric_sink,
        failure_ledger=failure_ledger,
        failure_materializer=materializer,
    )
    diagnostics.event(
        phase="command",
        event="MC_COMMAND_END",
        level="INFO",
        attributes={"action_id": "action-1"},
        correlation_refs=("action-1",),
    )
    diagnostics.metric(name="minecraft.command_latency_s", value=0.25, labels={"command": "wait"})
    diagnostics.failure(
        phase="read",
        code="BRIDGE_STDOUT_EOF",
        message="bridge ended",
        exception=RuntimeError("bridge ended"),
        correlation_refs=("action-1",),
    )

    assert [record.event for record in log_sink.records] == ["MC_COMMAND_END", "MC_FAILURE"]
    assert metric_sink.rows[0][1:] == ("minecraft.command_latency_s", 0.25, {"command": "wait"})
    assert len(failure_ledger.failures) == 1
    assert materialized[0]["code"] == "BRIDGE_STDOUT_EOF"
    assert diagnostics.diagnostic_errors == ()


def test_server_files_require_explicit_eula_policy(tmp_path) -> None:
    jar = tmp_path / "server.jar"
    jar.write_bytes(b"server-artifact")
    spec = MinecraftServerSpec(
        jar_path=str(jar),
        workdir=str(tmp_path / "world"),
        java_executable="/usr/bin/java",
    )
    with pytest.raises(MinecraftServerPreparationError, match="EULA_ACCEPTANCE_REQUIRED"):
        prepare_server_files(spec, accept_eula=False)
    prepared = prepare_server_files(spec, accept_eula=True)
    assert prepared.eula_accepted is True
    assert "eula=true" in (tmp_path / "world" / "eula.txt").read_text()
    properties = (tmp_path / "world" / "server.properties").read_text()
    assert "level-name=research-world" in properties
    assert "server-port=25565" in properties


class _FakeServiceRuntime:
    def __init__(self) -> None:
        self.process = ServiceProcessIdentity(42, "start-42", 42)
        self.calls: list[str] = []

    def reconcile_exact(self, contract):
        self.calls.append("reconcile")
        return ServiceReconcileObservation(True, self.process, (contract.digest(),))

    def start_exact(self, contract):
        self.calls.append("start")
        return ServiceStartOutcome(contract.digest(), self.process, "ready-ref", ("start-ref",))

    def verify_ready_exact(self, contract):
        self.calls.append("verify")
        return ServiceReadyObservation(contract.digest(), self.process, "ready-ref", ("ready-ref",))

    def stop_exact(self, contract):
        self.calls.append("stop")
        return ServiceStopOutcome(contract.digest(), True, ("stop-ref",))


def test_server_controller_uses_generic_service_port_only() -> None:
    spec = MinecraftServerSpec(
        jar_path="/srv/minecraft/server.jar",
        workdir="/srv/minecraft/world",
        java_executable="/usr/bin/java",
    )
    contract = build_server_service_contract(
        spec,
        environment_digest="a" * 64,
        artifact_digest="b" * 64,
        runtime_identity_digest="c" * 64,
    )
    runtime = _FakeServiceRuntime()
    controller = MinecraftServerServiceController(spec, contract, runtime)
    assert controller.reconcile().process is not None
    assert controller.start().ready_evidence_ref == "ready-ref"
    assert controller.verify_ready().process.pid == 42
    assert controller.stop().stopped is True
    assert runtime.calls == ["reconcile", "start", "verify", "stop"]


def test_minecraft_composition_binds_provider_once() -> None:
    spec = MinecraftEnvironmentSpec(
        endpoint=MinecraftEndpointSpec(),
        bridge=MinecraftBridgeSpec(command=("node", "bridge.js"), cwd="/srv/minecraft/bridge"),
    )
    assembly = compose_minecraft_environment(spec)
    assert assembly.implementation.identity.environment_id == "minecraft"
    assert assembly.runtime.runtime_identity.runtime_id == "minecraft.environment.session"
