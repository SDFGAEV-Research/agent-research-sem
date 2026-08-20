from __future__ import annotations

from dataclasses import dataclass
import hashlib
import socket
import time

from research_platform.runtime.service.api import (
    ExactServiceRuntimePort,
    ServiceLaunchContract,
    ServiceReadyObservation,
    ServiceReconcileObservation,
    ServiceStartOutcome,
    ServiceStopOutcome,
)
from research_platform.runtime.service.runtime.process_contracts import (
    ExactProcessBackend,
)

from ..api import MinecraftDiagnosticsPort, MinecraftServerSpec


class MinecraftServerServiceError(RuntimeError):
    """MC composition could not bind or operate the generic service port."""


class MinecraftTcpReadinessProbe:
    """Generic service-readiness adapter specialized only by MC TCP semantics."""

    def __init__(self, *, host: str, port: int, poll_interval_s: float = 0.25) -> None:
        if not host.strip() or not 1 <= port <= 65535 or poll_interval_s <= 0:
            raise ValueError("Minecraft TCP readiness configuration is invalid")
        self.host = host
        self.port = port
        self.poll_interval_s = poll_interval_s

    def wait_ready(self, process, contract: ServiceLaunchContract, backend: ExactProcessBackend) -> str:
        deadline = time.monotonic() + contract.readiness_timeout_s
        last_error = "not-probed"
        while time.monotonic() < deadline:
            if not backend.alive(process):
                raise MinecraftServerServiceError(
                    f"Minecraft server process exited before TCP readiness: {self.host}:{self.port}"
                )
            try:
                with socket.create_connection((self.host, self.port), timeout=min(1.0, self.poll_interval_s + 0.5)):
                    payload = f"{contract.digest()}:{process.pid}:{process.start_identity}:{self.host}:{self.port}"
                    return "minecraft-tcp-ready:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
            except OSError as exc:
                last_error = f"{type(exc).__name__}:{exc}"
            time.sleep(self.poll_interval_s)
        raise MinecraftServerServiceError(
            f"Minecraft server TCP readiness timed out for {self.host}:{self.port}: {last_error}"
        )


def build_server_service_contract(
    spec: MinecraftServerSpec,
    *,
    environment_digest: str,
    artifact_digest: str,
    runtime_identity_digest: str,
    generation: str = "minecraft-server-v1",
    readiness_timeout_s: float = 120.0,
    stop_timeout_s: float = 30.0,
    heartbeat_interval_s: float = 5.0,
) -> ServiceLaunchContract:
    return ServiceLaunchContract(
        service_id=f"minecraft.server.{spec.level_name}",
        generation=generation,
        executable=spec.java_executable,
        argv=spec.command(),
        cwd=spec.workdir,
        environment_digest=environment_digest,
        artifact_digest=artifact_digest,
        runtime_identity_digest=runtime_identity_digest,
        readiness_timeout_s=readiness_timeout_s,
        stop_timeout_s=stop_timeout_s,
        heartbeat_interval_s=heartbeat_interval_s,
    )


@dataclass(slots=True)
class MinecraftServerServiceController:
    """MC composition facade over the platform's exact service lifecycle."""

    spec: MinecraftServerSpec
    contract: ServiceLaunchContract
    service_runtime: ExactServiceRuntimePort
    diagnostics: MinecraftDiagnosticsPort | None = None

    def _event(self, event: str, *, level: str = "DEBUG", attributes: dict[str, object] | None = None) -> None:
        if self.diagnostics is None:
            return
        try:
            self.diagnostics.event(
                phase="server_service",
                event=event,
                level=level,
                attributes={"service_id": self.contract.service_id, **(attributes or {})},
                correlation_refs=(self.contract.digest(),),
            )
        except BaseException:
            return

    def _failure(self, code: str, exc: BaseException) -> None:
        if self.diagnostics is None:
            return
        try:
            self.diagnostics.failure(
                phase="server_service",
                code=code,
                message=str(exc),
                exception=exc,
                attributes={"service_id": self.contract.service_id},
                correlation_refs=(self.contract.digest(),),
            )
        except BaseException:
            return

    def reconcile(self) -> ServiceReconcileObservation:
        self._event("MC_SERVER_RECONCILE_START")
        try:
            result = self.service_runtime.reconcile_exact(self.contract)
        except Exception as exc:
            self._failure("MC_SERVER_RECONCILE_FAILED", exc)
            raise
        self._event("MC_SERVER_RECONCILE_END", attributes={"state_present": result.state_present, "has_process": result.process is not None})
        return result

    def start(self) -> ServiceStartOutcome:
        self._event("MC_SERVER_START", level="INFO", attributes={"host": self.spec.host, "port": self.spec.port})
        try:
            result = self.service_runtime.start_exact(self.contract)
        except Exception as exc:
            self._failure("MC_SERVER_START_FAILED", exc)
            raise
        self._event("MC_SERVER_READY", level="INFO", attributes={"pid": result.process.pid, "ready_ref": result.ready_evidence_ref})
        return result

    def verify_ready(self) -> ServiceReadyObservation:
        try:
            return self.service_runtime.verify_ready_exact(self.contract)
        except Exception as exc:
            self._failure("MC_SERVER_READY_VERIFICATION_FAILED", exc)
            raise

    def stop(self) -> ServiceStopOutcome:
        self._event("MC_SERVER_STOP", level="INFO")
        try:
            result = self.service_runtime.stop_exact(self.contract)
        except Exception as exc:
            self._failure("MC_SERVER_STOP_FAILED", exc)
            raise
        self._event("MC_SERVER_STOPPED", level="INFO", attributes={"stopped": result.stopped})
        return result


__all__ = [
    "MinecraftServerServiceController",
    "MinecraftServerServiceError",
    "MinecraftTcpReadinessProbe",
    "build_server_service_contract",
]
