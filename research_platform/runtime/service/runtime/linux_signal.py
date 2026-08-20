from __future__ import annotations

from research_platform.runtime.service.api import ServiceLaunchContract, ServiceProcessIdentity
import os
import signal
import time

from .linux_children import LinuxChildRegistry
from .linux_procfs import LinuxProcfsReader
from .process_contracts import ServiceProcessDrift


class LinuxProcessSignaler:
    """The sole process-group signal authority for supervised local services."""

    def __init__(self, procfs: LinuxProcfsReader, children: LinuxChildRegistry) -> None:
        self._procfs = procfs
        self._children = children

    def alive(self, process: ServiceProcessIdentity) -> bool:
        if not self._procfs.alive_pid(process.pid):
            return False
        try:
            return self._procfs.start_identity(process.pid) == process.start_identity
        except (FileNotFoundError, ProcessLookupError):
            return False

    def stop(
        self,
        process: ServiceProcessIdentity,
        contract: ServiceLaunchContract,
    ) -> tuple[str, ...]:
        if not self.alive(process):
            self._children.reap(process.pid)
            return (f"proc-already-exited:{process.pid}",)
        pgid = process.process_group_id
        if pgid is None:
            raise ServiceProcessDrift(
                "cannot safely stop process without frozen process-group identity"
            )
        if os.getpgid(process.pid) != pgid:
            raise ServiceProcessDrift(
                "process group drift; refusing to signal unrelated process"
            )
        os.killpg(pgid, signal.SIGTERM)
        if self._wait_for_exit(process, contract.stop_timeout_s):
            return (f"proc-stopped:{process.pid}",)
        if self.alive(process):
            os.killpg(pgid, signal.SIGKILL)
        self._children.reap(process.pid)
        return (f"proc-killed:{process.pid}",)

    def _wait_for_exit(self, process: ServiceProcessIdentity, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self._children.poll(process.pid)
            if not self.alive(process):
                self._children.reap(process.pid)
                return True
            time.sleep(0.05)
        return False


__all__ = ["LinuxProcessSignaler"]
