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
)
from research_platform.platform.kernel import ExecutionContext
from research_platform.runtime.host.api import OperatingSystemRoute

from ..api import (
    MinecraftBridgeCommandResult,
    MinecraftBridgeEnvelope,
    MinecraftBridgePort,
    MinecraftBridgeSpec,
    MinecraftDiagnosticsPort,
    MinecraftEndpointSpec,
    MinecraftObservationEvent,
    MinecraftReconciliation,
)


_STDOUT_EOF = object()


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
        operating_system: OperatingSystemRoute,
        process_factory: ProcessFactory | None = None,
        process_terminator: ProcessTerminator | None = None,
        diagnostics: MinecraftDiagnosticsPort | None = None,
        stderr_tail_lines: int = 300,
    ) -> None:
        self.endpoint = endpoint
        self.spec = spec
        self._process_factory = process_factory or subprocess.Popen
        self._process_terminator = process_terminator
        self._operating_system = operating_system
        self._diagnostics = diagnostics
        self._diagnostic_errors: deque[str] = deque(maxlen=20)
        self._stderr_tail: deque[str] = deque(maxlen=max(20, stderr_tail_lines))
        self._stdout_queue: queue.Queue[str | object] = queue.Queue()
        self._process: JsonlProcess | None = None
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._stderr_handle: TextIO | None = None
        self._request_counter = 0
        self._action_proofs: dict[str, bool] = {}
        self._lock = threading.RLock()

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr_tail)

    @property
    def process_id(self) -> int | None:
        return self._process.pid if self._process is not None else None

    def _event_log(
        self,
        *,
        phase: str,
        event: str,
        attributes: Mapping[str, object] | None = None,
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
        attributes: Mapping[str, object] | None = None,
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

    def _drain_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            for line in iter(process.stdout.readline, ""):
                self._stdout_queue.put(line)
        finally:
            self._stdout_queue.put(_STDOUT_EOF)

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

    def _next_request_id(self, command: str, payload: Mapping[str, object]) -> str:
        candidate = payload.get("request_id") or payload.get("action_id")
        if candidate is not None and str(candidate).strip():
            return str(candidate)
        self._request_counter += 1
        return f"mc-{command}-{self._request_counter}-{uuid4().hex[:8]}"

    def _send(self, command: str, payload: Mapping[str, object], *, request_id: str) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise MinecraftBridgeError("transport", "BRIDGE_NOT_STARTED", "bridge process is not running")
        message = {"cmd": command, "request_id": request_id, **dict(payload)}
        try:
            process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except Exception as exc:
            self._failure_log(phase="send", code="BRIDGE_STDIN_WRITE_FAILED", message=str(exc), exception=exc)
            raise MinecraftBridgeError("send", "BRIDGE_STDIN_WRITE_FAILED", str(exc)) from exc

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
            self._failure_log(phase="decode", code="BRIDGE_INVALID_JSON", message=line[:512], exception=exc)
            raise MinecraftBridgeError("decode", "BRIDGE_INVALID_JSON", line[:512]) from exc
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
            raise MinecraftBridgeError("decode", "BRIDGE_INVALID_EVENT", str(exc)) from exc

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
                    if action_id is not None and "verified" in event.payload:
                        self._action_proofs[str(action_id)] = bool(event.payload["verified"])
                continue
            if message.kind != "ack":
                continue
            if str(message.value.get("cmd", "")) != command:
                continue
            observed_request_id = message.value.get("request_id")
            if observed_request_id is not None and str(observed_request_id) != request_id:
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
        if verified is not None:
            verified = bool(verified)
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

    def start(self) -> None:
        with self._lock:
            if self._process is not None:
                raise MinecraftBridgeError("start", "BRIDGE_ALREADY_STARTED", "bridge already started")
            self._stdout_queue = queue.Queue()
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
                self._stdout_thread = threading.Thread(
                    target=self._drain_stdout, name="minecraft-bridge-stdout", daemon=True
                )
                self._stderr_thread = threading.Thread(
                    target=self._drain_stderr, name="minecraft-bridge-stderr", daemon=True
                )
                self._stdout_thread.start()
                self._stderr_thread.start()
                request_id = "minecraft-connect"
                self._send(
                    "connect",
                    {
                        "host": self.endpoint.host,
                        "port": self.endpoint.port,
                        "username": self.endpoint.username,
                        "auth": self.endpoint.auth,
                        **({"version": self.endpoint.version} if self.endpoint.version else {}),
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
                        if self.endpoint.version and observed_version and observed_version != self.endpoint.version:
                            self._failure_log(
                                phase="handshake",
                                code="MINECRAFT_VERSION_DRIFT",
                                message=f"expected={self.endpoint.version!r}; observed={observed_version!r}",
                            )
                            raise MinecraftBridgeError(
                                "handshake", "MINECRAFT_VERSION_DRIFT", f"expected={self.endpoint.version!r}; observed={observed_version!r}"
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
                self.close()
                raise

    def command(
        self,
        command: str,
        payload: Mapping[str, object],
        *,
        timeout_s: float,
    ) -> MinecraftBridgeCommandResult:
        if not command.strip():
            raise ValueError("Minecraft bridge command must be non-empty")
        if timeout_s <= 0:
            raise ValueError("Minecraft bridge command timeout must be positive")
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

    def reconcile_action(
        self,
        action_id: str,
        *,
        request: ActionRequest,
        context: ExecutionContext,
    ) -> MinecraftReconciliation:
        del request, context
        if not action_id.strip():
            raise ValueError("Minecraft action_id must be non-empty")
        verified = self._action_proofs.get(action_id)
        if verified is True:
            disposition = ActionReconciliationDisposition.APPLIED
        elif verified is False:
            disposition = ActionReconciliationDisposition.NOT_APPLIED
        else:
            disposition = ActionReconciliationDisposition.UNKNOWN
        return MinecraftReconciliation(
            action_id=action_id,
            disposition=disposition,
            diagnostics={
                "proof_source": "action_result_event" if verified is not None else "none",
                "known_action_proof": verified,
            },
        )

    def close(self) -> None:
        with self._lock:
            process = self._process
            if process is None:
                return
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
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self._terminate_process(process)
            finally:
                if process.poll() is None:
                    self._terminate_process(process)
                for thread in (self._stdout_thread, self._stderr_thread):
                    if thread is not None:
                        thread.join(timeout=1)
                if self._stderr_handle is not None:
                    self._stderr_handle.close()
                    self._stderr_handle = None
                self._stdout_thread = None
                self._stderr_thread = None
                self._process = None

    def _terminate_process(self, process: JsonlProcess) -> None:
        if self._process_terminator is not None:
            try:
                self._process_terminator(process, False)
                return
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            process.terminate()
            process.wait(timeout=2)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
        if self._process_terminator is not None:
            try:
                self._process_terminator(process, True)
                return
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            process.kill()
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            pass


__all__ = ["JsonlMinecraftBridge", "JsonlProcess", "MinecraftBridgeError", "ProcessTerminator"]
