from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import Any, Callable, Mapping, Protocol, Sequence, TextIO
from uuid import uuid4

from research_platform.environment.runtime.api import (
    ActionReconciliationDisposition,
    ActionRequest,
    Observation,
    action_request_digest,
)
from research_platform.platform.concurrency.api import (
    Deadline,
    ExecutionLaneKind,
    ExecutionSpec,
    SerialActorPort,
    TaskContextPort,
    TaskFailureScope,
    TaskGroupPort,
    TaskHandlePort,
)
from research_platform.platform.kernel import ExecutionContext, JsonValue
from research_platform.platform.kernel.errors import describe_exception
from research_platform.runtime.host.api import OperatingSystemRoute
from research_platform.runtime.process.supervision.composition import build_process_supervisor

from ..api import (
    MINECRAFT_ACTION_TYPES,
    MinecraftBridgeCommandResult,
    MinecraftBridgeEnvelope,
    MinecraftBridgePort,
    MinecraftBridgeSpec,
    MinecraftAgentSpec,
    MinecraftDiagnosticsPort,
    MinecraftEndpointSpec,
    MinecraftObservationEvent,
    MinecraftReconciliation,
)


_STDOUT_EOF = object()


def _safe_exception_message(exc: BaseException) -> str:
    descriptor = describe_exception(exc)
    return f"{descriptor.error_type}[{descriptor.error_digest[:16]}]"


class MinecraftBridgeError(RuntimeError):
    """Transport failure with a stable phase/cause code for diagnosis."""

    def __init__(self, phase: str, cause_code: str, message: str) -> None:
        super().__init__(f"Minecraft bridge {phase} failed [{cause_code}]: {message}")
        self.phase = phase
        self.cause_code = cause_code


class JsonlProcess(Protocol):
    stdin: TextIO | None
    stdout: TextIO | None
    stderr: TextIO | None
    pid: int

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...


ProcessFactory = Callable[..., JsonlProcess]
ProcessTerminator = Callable[[JsonlProcess, bool], None]


@dataclass(frozen=True, slots=True)
class _BridgeMessage:
    kind: str
    value: Mapping[str, Any]


class JsonlMinecraftBridge(MinecraftBridgePort):
    """Mineflayer-independent JSONL transport extracted from v034.

    The class owns only the short-lived bridge transport. A Minecraft Java
    server is not started, stopped or inferred here. A process factory is
    injectable so the protocol can be tested without Node or Minecraft.
    """

    def __init__(
        self,
        *,
        endpoint: MinecraftEndpointSpec,
        spec: MinecraftBridgeSpec,
        agent: MinecraftAgentSpec,
        operating_system: OperatingSystemRoute,
        process_factory: ProcessFactory | None = None,
        process_terminator: ProcessTerminator | None = None,
        diagnostics: MinecraftDiagnosticsPort | None = None,
        task_group: TaskGroupPort,
        stderr_tail_lines: int = 300,
    ) -> None:
        self.endpoint = endpoint
        self.spec = spec
        self.agent = agent
        self._process_factory = process_factory or subprocess.Popen
        self._process_terminator = process_terminator
        self._operating_system = operating_system
        self._diagnostics = diagnostics
        self._diagnostic_errors: deque[str] = deque(maxlen=20)
        self._stderr_tail: deque[str] = deque(maxlen=max(20, stderr_tail_lines))
        self._stdout_queue: queue.Queue[str | object] = queue.Queue(maxsize=self.spec.stdout_queue_capacity)
        self._stdout_stop = threading.Event()
        self._process: JsonlProcess | None = None
        self._stdout_task: TaskHandlePort[None] | None = None
        self._stderr_task: TaskHandlePort[None] | None = None
        self._stderr_handle: TextIO | None = None
        self._request_counter = 0
        self._action_proofs: dict[str, ActionReconciliationDisposition] = {}
        actor_identity = hashlib.sha256(
            f"{endpoint.host}:{endpoint.port}:{agent.username}".encode("utf-8")
        ).hexdigest()[:20]
        self._task_group = task_group
        self._bridge_identity = actor_identity
        self._action_recovery_root = (
            Path(self.spec.action_recovery_root)
            if self.spec.action_recovery_root is not None
            else None
        )
        self._action_recovery_dir: Path | None = None
        self._process_supervisor = build_process_supervisor(
            task_group,
            termination_hook=process_terminator,
        )
        self._actor: SerialActorPort = task_group.open_serial_actor(
            f"minecraft-bridge:{actor_identity}:{uuid4().hex}",
            lane_id=f"minecraft-bridge:{actor_identity}",
        )
        self._closing = False

    @property
    def action_recovery_durability(self) -> str:
        return "crash_durable" if self._action_recovery_root is not None else "process_local"

    def configure_action_recovery(self, namespace: str) -> None:
        if not namespace.strip():
            raise ValueError("Minecraft action recovery namespace must be non-empty")
        if self._process is not None:
            raise MinecraftBridgeError(
                "recovery", "BRIDGE_ALREADY_STARTED", "action recovery must be bound before start"
            )
        if self._action_recovery_root is None:
            self._action_recovery_dir = None
            return
        digest = hashlib.sha256(namespace.encode("utf-8")).hexdigest()
        self._action_recovery_dir = self._action_recovery_root / digest

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr_tail)

    @property
    def process_id(self) -> int | None:
        return self._process.pid if self._process is not None else None

    def supports_command(self, command: str) -> bool:
        return command in MINECRAFT_ACTION_TYPES | {
            "snapshot",
            "task_event",
            "quit",
            "reconcile_action",
        }

    def _event_log(
        self,
        *,
        phase: str,
        event: str,
        attributes: Mapping[str, JsonValue] | None = None,
        level: str = "DEBUG",
        correlation_refs: tuple[str, ...] = (),
    ) -> None:
        if self._diagnostics is None:
            return
        try:
            self._diagnostics.event(
                phase=phase,
                event=event,
                attributes=attributes or {},
                level=level,
                correlation_refs=correlation_refs,
            )
        except BaseException as exc:
            self._diagnostic_errors.append(f"event:{type(exc).__name__}:{exc}")

    def _failure_log(
        self,
        *,
        phase: str,
        code: str,
        message: str,
        exception: BaseException | None = None,
        attributes: Mapping[str, JsonValue] | None = None,
        correlation_refs: tuple[str, ...] = (),
    ) -> None:
        if self._diagnostics is None:
            return
        try:
            self._diagnostics.failure(
                phase=phase,
                code=code,
                message=message,
                exception=exception,
                attributes=attributes or {},
                correlation_refs=correlation_refs,
            )
        except BaseException as exc:
            self._diagnostic_errors.append(f"failure:{type(exc).__name__}:{exc}")

    def _metric(self, *, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        if self._diagnostics is None:
            return
        try:
            self._diagnostics.metric(name=name, value=value, labels=labels or {})
        except BaseException as exc:
            self._diagnostic_errors.append(f"metric:{type(exc).__name__}:{exc}")

    def _put_stdout(self, item: str | object) -> bool:
        while not self._stdout_stop.is_set():
            try:
                self._stdout_queue.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def _drain_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            for line in iter(process.stdout.readline, ""):
                if not self._put_stdout(line):
                    return
        finally:
            self._put_stdout(_STDOUT_EOF)

    def _drain_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        try:
            if self.spec.stderr_log_path:
                path = Path(self.spec.stderr_log_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                self._stderr_handle = path.open("a", encoding="utf-8", buffering=1)
            for line in iter(process.stderr.readline, ""):
                text = line.rstrip("\r\n")
                self._stderr_tail.append(text)
                if self._stderr_handle is not None:
                    self._stderr_handle.write(line)
        finally:
            if self._stderr_handle is not None:
                self._stderr_handle.close()
                self._stderr_handle = None

    def _drain_stdout_task(self, context: TaskContextPort) -> None:
        context.checkpoint()
        self._drain_stdout()
        context.checkpoint()

    def _drain_stderr_task(self, context: TaskContextPort) -> None:
        context.checkpoint()
        self._drain_stderr()
        context.checkpoint()

    def _next_request_id(self, command: str, payload: Mapping[str, JsonValue]) -> str:
        candidate = payload.get("request_id") or payload.get("action_id")
        if candidate is not None and str(candidate).strip():
            return str(candidate)
        self._request_counter += 1
        return f"mc-{command}-{self._request_counter}-{uuid4().hex[:8]}"

    def _send(self, command: str, payload: Mapping[str, JsonValue], *, request_id: str) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise MinecraftBridgeError("transport", "BRIDGE_NOT_STARTED", "bridge process is not running")
        message = {"cmd": command, "request_id": request_id, **dict(payload)}
        try:
            process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except Exception as exc:
            message = _safe_exception_message(exc)
            self._failure_log(phase="send", code="BRIDGE_STDIN_WRITE_FAILED", message=message, exception=exc)
            raise MinecraftBridgeError("send", "BRIDGE_STDIN_WRITE_FAILED", message) from exc

    def _read(self, *, timeout_s: float) -> _BridgeMessage:
        process = self._process
        if process is None:
            raise MinecraftBridgeError("read", "BRIDGE_NOT_STARTED", "bridge process is not running")
        try:
            item = self._stdout_queue.get(timeout=timeout_s)
        except queue.Empty as exc:
            code = process.poll()
            if code is not None:
                self._failure_log(
                    phase="read",
                    code="BRIDGE_EXITED",
                    message=f"exit_code={code}",
                    attributes={"stderr_tail": self._stderr_tail_text()},
                )
                raise MinecraftBridgeError(
                    "read",
                    "BRIDGE_EXITED",
                    f"exit_code={code}; stderr_tail={self._stderr_tail_text()}",
                ) from exc
            raise MinecraftBridgeError(
                "read", "BRIDGE_READ_TIMEOUT", f"no complete JSONL message within {timeout_s:.3f}s"
            ) from exc
        if item is _STDOUT_EOF:
            self._failure_log(
                phase="read",
                code="BRIDGE_STDOUT_EOF",
                message=f"exit_code={process.poll()}",
                attributes={"stderr_tail": self._stderr_tail_text()},
            )
            raise MinecraftBridgeError(
                "read", "BRIDGE_STDOUT_EOF", f"exit_code={process.poll()}; stderr_tail={self._stderr_tail_text()}"
            )
        line = str(item).strip()
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            message = f"invalid-json[{_safe_exception_message(exc)}]"
            self._failure_log(phase="decode", code="BRIDGE_INVALID_JSON", message=message, exception=exc)
            raise MinecraftBridgeError("decode", "BRIDGE_INVALID_JSON", message) from exc
        if not isinstance(value, Mapping):
            self._failure_log(phase="decode", code="BRIDGE_MESSAGE_NOT_OBJECT", message=line[:512])
            raise MinecraftBridgeError("decode", "BRIDGE_MESSAGE_NOT_OBJECT", line[:512])
        return _BridgeMessage(str(value.get("type", "")), dict(value))

    def _stderr_tail_text(self) -> str:
        return " | ".join(self._stderr_tail[-20:])[-6000:]

    @staticmethod
    def _event(message: _BridgeMessage) -> MinecraftObservationEvent:
        if message.kind != "event":
            raise MinecraftBridgeError("decode", "BRIDGE_UNEXPECTED_MESSAGE", message.kind)
        try:
            return MinecraftBridgeEnvelope.from_mapping(message.value).as_observation()
        except (TypeError, ValueError) as exc:
            raise MinecraftBridgeError("decode", "BRIDGE_INVALID_EVENT", _safe_exception_message(exc)) from exc

    def _observe_until_ack(
        self,
        *,
        command: str,
        request_id: str,
        timeout_s: float,
        require_ack: bool = True,
    ) -> MinecraftBridgeCommandResult:
        deadline = time.monotonic() + timeout_s
        events: list[MinecraftObservationEvent] = []
        ack: Mapping[str, Any] | None = None
        while time.monotonic() < deadline:
            message = self._read(timeout_s=max(0.001, deadline - time.monotonic()))
            if message.kind == "event":
                event = self._event(message)
                events.append(event)
                if event.kind == "action_result":
                    action_id = event.payload.get("action_id")
                    outcome = event.payload.get("outcome")
                    status = outcome.get("status") if isinstance(outcome, Mapping) else None
                    if action_id is not None and event.payload.get("verified") is True:
                        self._action_proofs[str(action_id)] = ActionReconciliationDisposition.APPLIED
                    elif action_id is not None and status == "rejected":
                        self._action_proofs[str(action_id)] = ActionReconciliationDisposition.NOT_APPLIED
                    elif action_id is not None:
                        self._action_proofs[str(action_id)] = ActionReconciliationDisposition.UNKNOWN
                continue
            if message.kind != "ack":
                continue
            if str(message.value.get("cmd", "")) != command:
                continue
            observed_request_id = message.value.get("request_id")
            if not isinstance(observed_request_id, str) or observed_request_id != request_id:
                continue
            ack = message.value
            break

        if require_ack and ack is None:
            self._failure_log(
                phase="command",
                code="BRIDGE_COMMAND_TIMEOUT",
                message=f"command={command}; request_id={request_id}",
                attributes={"stderr_tail": self._stderr_tail_text()},
                correlation_refs=(request_id,),
            )
            raise MinecraftBridgeError(
                "command",
                "BRIDGE_COMMAND_TIMEOUT",
                f"command={command}; request_id={request_id}; stderr_tail={self._stderr_tail_text()}",
            )
        ack_value = dict(ack or {})
        verified = ack_value.get("verified")
        if verified is not None and not isinstance(verified, bool):
            raise MinecraftBridgeError(
                "decode", "BRIDGE_INVALID_ACK", "ack verified must be boolean"
            )
        rejected = ack_value.get("rejected")
        if rejected is not None and not isinstance(rejected, bool):
            raise MinecraftBridgeError(
                "decode", "BRIDGE_INVALID_ACK", "ack rejected must be boolean"
            )
        diagnostics = {
            "request_id": request_id,
            "event_count": len(events),
            "ack": ack_value,
            "stderr_tail": self.stderr_tail,
            "process_id": self.process_id,
            "error": ack_value.get("error"),
            "diagnostic_errors": tuple(self._diagnostic_errors),
        }
        self._event_log(
            phase="command",
            event="BRIDGE_COMMAND_END",
            level="ERROR" if ack_value.get("error") else "DEBUG",
            attributes={
                "command": command,
                "request_id": request_id,
                "event_count": len(events),
                "verified": verified,
                "acknowledged": ack is not None and not bool(ack_value.get("error")),
            },
            correlation_refs=(request_id,),
        )
        self._metric(
            name="minecraft.bridge.command_events",
            value=float(len(events)),
            labels={"command": command, "verified": str(verified).lower()},
        )
        return MinecraftBridgeCommandResult(
            command=command,
            acknowledged=ack is not None and not bool(ack_value.get("error")),
            verified=verified,
            events=tuple(events),
            diagnostics=diagnostics,
        )

    def _start_owned(self) -> None:
        """Start and handshake the bridge on its actor-owned lifecycle lane.

        Algorithm-Complexity: O(N)
        Algorithm-Rationale: N is the number of handshake events consumed plus the declared action capabilities inspected; the capability validation pass and event-consumption loop are sequential phases, not a Cartesian product.
        """
        if self._closing:
            raise MinecraftBridgeError("start", "BRIDGE_CLOSING", "bridge close is in progress")
        if self._process is not None:
            raise MinecraftBridgeError("start", "BRIDGE_ALREADY_STARTED", "bridge already started")
        self._stdout_stop.clear()
        self._stdout_queue = queue.Queue(maxsize=self.spec.stdout_queue_capacity)
        started_at = time.monotonic()
        self._event_log(
            phase="start",
            event="BRIDGE_PROCESS_START",
            attributes={
                "command": self.spec.command,
                "cwd": self.spec.cwd,
                "host": self.endpoint.host,
                "port": self.endpoint.port,
            },
        )
        try:
            process_options = {
                "cwd": self.spec.cwd,
                "stdin": subprocess.PIPE,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "bufsize": 1,
                "start_new_session": self._operating_system.is_posix,
            }
            if self._operating_system.is_windows:
                process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            self._process = self._process_factory(list(self.spec.command), **process_options)
            self._stdout_task = self._task_group.submit(
                ExecutionSpec(
                    task_id=f"minecraft-bridge:{self._bridge_identity}:stdout:{uuid4().hex}",
                    lane_kind=ExecutionLaneKind.BLOCKING_IO,
                    failure_scope=TaskFailureScope.CALLER,
                ),
                self._drain_stdout_task,
            )
            self._stderr_task = self._task_group.submit(
                ExecutionSpec(
                    task_id=f"minecraft-bridge:{self._bridge_identity}:stderr:{uuid4().hex}",
                    lane_kind=ExecutionLaneKind.BLOCKING_IO,
                    failure_scope=TaskFailureScope.CALLER,
                ),
                self._drain_stderr_task,
            )
            request_id = "minecraft-connect"
            self._send(
                "connect",
                {
                    "host": self.endpoint.host,
                    "port": self.endpoint.port,
                    "username": self.agent.username,
                    "auth": self.agent.auth,
                    **({"version": self.agent.version} if self.agent.version else {}),
                    **(
                        {"action_recovery_dir": str(self._action_recovery_dir)}
                        if self._action_recovery_dir is not None
                        else {}
                    ),
                },
                request_id=request_id,
            )
            deadline = time.monotonic() + self.spec.connect_timeout_s
            spawned = False
            while time.monotonic() < deadline:
                message = self._read(timeout_s=max(0.001, deadline - time.monotonic()))
                if message.kind != "event":
                    continue
                event = self._event(message)
                if event.kind == "bridge_status" and event.payload.get("status") == "spawned":
                    observed_version = str(event.payload.get("version") or "")
                    if self.agent.version and observed_version and observed_version != self.agent.version:
                        self._failure_log(
                            phase="handshake",
                            code="MINECRAFT_VERSION_DRIFT",
                            message=f"expected={self.agent.version!r}; observed={observed_version!r}",
                        )
                        raise MinecraftBridgeError(
                            "handshake", "MINECRAFT_VERSION_DRIFT", f"expected={self.agent.version!r}; observed={observed_version!r}"
                        )
                    observed_actions = event.payload.get("action_types")
                    if not isinstance(observed_actions, list) or any(
                        not isinstance(value, str) for value in observed_actions
                    ):
                        raise MinecraftBridgeError(
                            "handshake",
                            "MINECRAFT_CAPABILITY_MANIFEST_MISSING",
                            "bridge did not declare a string action_types manifest",
                        )
                    observed_action_set = frozenset(observed_actions)
                    if (
                        len(observed_action_set) != len(observed_actions)
                        or observed_action_set != MINECRAFT_ACTION_TYPES
                    ):
                        missing = sorted(MINECRAFT_ACTION_TYPES - observed_action_set)
                        extra = sorted(observed_action_set - MINECRAFT_ACTION_TYPES)
                        raise MinecraftBridgeError(
                            "handshake",
                            "MINECRAFT_CAPABILITY_DRIFT",
                            f"missing={missing}; extra={extra}",
                        )
                    spawned = True
                    break
                if event.kind in {"error", "kicked", "end"}:
                    self._failure_log(
                        phase="handshake",
                        code="MINECRAFT_SPAWN_FAILED",
                        message=f"event={event.kind}",
                        attributes={"payload": dict(event.payload)},
                    )
                    raise MinecraftBridgeError(
                        "handshake", "MINECRAFT_SPAWN_FAILED", f"event={event.kind}; payload={dict(event.payload)}"
                    )
            if not spawned:
                self._failure_log(
                    phase="handshake",
                    code="MINECRAFT_SPAWN_TIMEOUT",
                    message="bridge did not emit spawned",
                )
                raise MinecraftBridgeError("handshake", "MINECRAFT_SPAWN_TIMEOUT", "bridge did not emit spawned")
            self._event_log(
                phase="start",
                event="BRIDGE_PROCESS_READY",
                level="INFO",
                attributes={"duration_s": time.monotonic() - started_at, "process_id": self.process_id},
            )
        except Exception:
            self._close_owned()
            raise

    def start(self) -> None:
        self._actor.call("start", self._start_owned)

    def _command_owned(
        self,
        command: str,
        payload: Mapping[str, JsonValue],
        timeout_s: float,
    ) -> MinecraftBridgeCommandResult:
        if self._closing:
            raise MinecraftBridgeError("command", "BRIDGE_CLOSING", "bridge close is in progress")
        request_id = self._next_request_id(command, payload)
        started_at = time.monotonic()
        self._event_log(
            phase="command",
            event="BRIDGE_COMMAND_START",
            attributes={
                "command": command,
                "request_id": request_id,
                "payload_keys": tuple(sorted(str(key) for key in payload)),
                "payload_digest": hashlib.sha256(
                    json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, default=repr).encode("utf-8")
                ).hexdigest(),
            },
            correlation_refs=(request_id,),
        )
        self._send(command, payload, request_id=request_id)
        result = self._observe_until_ack(
            command=command,
            request_id=request_id,
            timeout_s=timeout_s,
        )
        self._metric(
            name="minecraft.bridge.command_latency_s",
            value=time.monotonic() - started_at,
            labels={"command": command, "result": "error" if result.diagnostics.get("error") else "ok"},
        )
        return result

    def command(
        self,
        command: str,
        payload: Mapping[str, JsonValue],
        *,
        timeout_s: float,
    ) -> MinecraftBridgeCommandResult:
        if not command.strip():
            raise ValueError("Minecraft bridge command must be non-empty")
        if timeout_s <= 0:
            raise ValueError("Minecraft bridge command timeout must be positive")
        return self._actor.call("command", self._command_owned, command, payload, timeout_s)

    def _reconcile_action_owned(
        self, action_id: str, request_digest: str
    ) -> MinecraftReconciliation:
        local = self._action_proofs.get(action_id)
        if local in {
            ActionReconciliationDisposition.APPLIED,
            ActionReconciliationDisposition.NOT_APPLIED,
        }:
            return MinecraftReconciliation(
                action_id=action_id,
                disposition=local,
                diagnostics={
                    "proof_source": "action_result_event",
                    "known_action_proof": local.value,
                    "durability": self.action_recovery_durability,
                },
            )
        request_id = f"reconcile-{hashlib.sha256(action_id.encode('utf-8')).hexdigest()[:16]}-{self._request_counter + 1}"
        self._request_counter += 1
        self._send(
            "reconcile_action",
            {"action_id": action_id, "request_digest": request_digest},
            request_id=request_id,
        )
        response = self._observe_until_ack(
            command="reconcile_action",
            request_id=request_id,
            timeout_s=self.spec.command_timeout_s,
        )
        ack = response.diagnostics.get("ack")
        raw = ack.get("disposition") if isinstance(ack, Mapping) else None
        try:
            disposition = ActionReconciliationDisposition(str(raw))
        except ValueError as exc:
            raise MinecraftBridgeError(
                "reconcile", "BRIDGE_INVALID_RECONCILIATION", f"disposition={raw!r}"
            ) from exc
        if disposition is not ActionReconciliationDisposition.UNKNOWN:
            self._action_proofs[action_id] = disposition
        return MinecraftReconciliation(
            action_id=action_id,
            disposition=disposition,
            diagnostics={
                "proof_source": "durable_action_journal"
                if self._action_recovery_dir is not None
                else "process_action_journal",
                "known_action_proof": disposition.value,
                "durability": self.action_recovery_durability,
            },
        )

    def reconcile_action(
        self,
        action_id: str,
        *,
        request: ActionRequest,
        context: ExecutionContext,
        request_digest: str | None = None,
    ) -> MinecraftReconciliation:
        del context
        if not action_id.strip():
            raise ValueError("Minecraft action_id must be non-empty")
        digest = request_digest or action_request_digest(request)
        return self._actor.call(
            "reconcile-action", self._reconcile_action_owned, action_id, digest
        )

    def _close_owned(self) -> None:
        process = self._process
        if process is None or self._closing:
            return
        self._closing = True
        stdout_task = self._stdout_task
        stderr_task = self._stderr_task
        self._event_log(
            phase="close",
            event="BRIDGE_PROCESS_CLOSE",
            attributes={"process_id": process.pid},
            level="INFO",
        )
        try:
            if process.poll() is None and process.stdin is not None:
                try:
                    self._send("quit", {}, request_id="minecraft-close")
                except MinecraftBridgeError:
                    pass
            try:
                if process.poll() is None:
                    try:
                        self._process_supervisor.await_exit(
                            f"minecraft-bridge:{self._bridge_identity}:graceful-close",
                            process,
                            deadline=Deadline.after(3.0),
                        ).result(timeout=4.0)
                    except TimeoutError:
                        self._terminate_process(process)
            finally:
                if process.poll() is None:
                    self._terminate_process(process)
                self._stdout_stop.set()
                # Closing the parent pipe endpoints makes any blocked readline
                # converge before we join the task-group-owned drain tasks.
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        try:
                            stream.close()
                        except OSError:
                            pass
                drain_errors: list[BaseException] = []
                for handle in (stdout_task, stderr_task):
                    if handle is None:
                        continue
                    try:
                        handle.result(timeout=2.0)
                    except BaseException as exc:
                        drain_errors.append(exc)
                if drain_errors:
                    raise ExceptionGroup("minecraft bridge drain tasks failed to converge", drain_errors)
        finally:
            self._stdout_task = None
            self._stderr_task = None
            self._process = None
            self._closing = False

    def close(self) -> None:
        self._actor.call("close", self._close_owned)

    def _terminate_process(self, process: JsonlProcess) -> None:
        if process.poll() is not None:
            return
        self._process_supervisor.terminate(
            f"minecraft-bridge:{self._bridge_identity}:terminate",
            process,
            deadline=Deadline.after(6.0),
        ).result(timeout=7.0)



__all__ = ["JsonlMinecraftBridge", "JsonlProcess", "MinecraftBridgeError", "ProcessTerminator"]
