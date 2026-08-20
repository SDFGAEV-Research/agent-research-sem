from __future__ import annotations

from research_platform.runtime.service.api import ServiceLaunchContract, ServiceProcessIdentity
import hashlib
import time
from urllib.request import Request, urlopen

from .process_contracts import ExactProcessBackend


class ProcessAliveReadinessProbe:
    """Generic worker readiness; deliberately not a model qualification probe."""

    def __init__(self, *, poll_interval_s: float = 0.05) -> None:
        if poll_interval_s <= 0:
            raise ValueError("poll interval must be positive")
        self.poll_interval_s = poll_interval_s

    def wait_ready(
        self,
        process: ServiceProcessIdentity,
        contract: ServiceLaunchContract,
        backend: ExactProcessBackend,
    ) -> str:
        deadline = time.monotonic() + contract.readiness_timeout_s
        while time.monotonic() < deadline:
            if backend.alive(process):
                payload = f"{contract.digest()}:{process.pid}:{process.start_identity}:alive"
                return "process-alive:" + hashlib.sha256(payload.encode()).hexdigest()
            time.sleep(self.poll_interval_s)
        raise TimeoutError(f"service {contract.service_id} did not remain alive before readiness timeout")


class HttpEndpointReadinessProbe:
    """Operational HTTP readiness for managed services; not scientific qualification."""

    def __init__(self, url: str, *, poll_interval_s: float = 0.25, request_timeout_s: float = 2.0) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("readiness URL must use http or https")
        if poll_interval_s <= 0 or request_timeout_s <= 0:
            raise ValueError("readiness polling values must be positive")
        self.url = url
        self.poll_interval_s = poll_interval_s
        self.request_timeout_s = request_timeout_s

    def wait_ready(
        self,
        process: ServiceProcessIdentity,
        contract: ServiceLaunchContract,
        backend: ExactProcessBackend,
    ) -> str:
        deadline = time.monotonic() + contract.readiness_timeout_s
        last_error = "not-ready"
        while time.monotonic() < deadline:
            if not backend.alive(process):
                raise RuntimeError(f"service {contract.service_id} exited before HTTP readiness")
            try:
                with urlopen(Request(self.url, method="GET"), timeout=self.request_timeout_s) as response:
                    status = int(getattr(response, "status", 200))
                    if 200 <= status < 400:
                        payload = f"{contract.digest()}:{process.pid}:{self.url}:{status}"
                        return "http-ready:" + hashlib.sha256(payload.encode()).hexdigest()
                    last_error = f"http-{status}"
            except OSError as exc:
                last_error = type(exc).__name__
            time.sleep(self.poll_interval_s)
        raise TimeoutError(f"service {contract.service_id} readiness timed out ({last_error})")


__all__ = ["HttpEndpointReadinessProbe", "ProcessAliveReadinessProbe"]
