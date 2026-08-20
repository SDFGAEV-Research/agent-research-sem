from __future__ import annotations

from research_platform.runtime.service.api import ServiceLaunchContract, ServiceProcessIdentity
from research_platform.platform.kernel import canonical_digest
import os
from pathlib import Path
import time

from .environment import MaterializedServiceEnvironment
from .linux_procfs import LinuxProcfsReader
from .process_contracts import ProcessReconcileResult, ProcessReconcileStatus


class LinuxExactProcessVerifier:
    """Read-only Linux process identity authority shared by local launch backends.

    This component never spawns or signals processes.  It only proves whether a
    PID/start-identity still represents the exact frozen executable/argv/cwd/env.
    Keeping this verification independent prevents the direct-Popen and tmux
    launch transports from developing subtly different process identity rules.
    """

    def __init__(self, procfs: LinuxProcfsReader) -> None:
        self._procfs = procfs

    @staticmethod
    def _evidence_ref(
        *,
        process: ServiceProcessIdentity,
        status: ProcessReconcileStatus,
        facts: dict[str, object],
    ) -> str:
        payload = {
            "pid": process.pid,
            "start_identity": process.start_identity,
            "status": status.value,
            "facts": facts,
        }
        digest = canonical_digest(payload)
        return f"proc-reconcile:{digest}"

    @staticmethod
    def _missing(process: ServiceProcessIdentity, prefix: str) -> ProcessReconcileResult:
        return ProcessReconcileResult(
            ProcessReconcileStatus.MISSING,
            (f"{prefix}:{process.pid}",),
        )

    def identity(self, pid: int) -> ServiceProcessIdentity:
        return ServiceProcessIdentity(
            pid,
            self._procfs.start_identity(pid),
            os.getpgid(pid),
        )

    def reconcile(
        self,
        process: ServiceProcessIdentity,
        contract: ServiceLaunchContract,
        environment: MaterializedServiceEnvironment,
    ) -> ProcessReconcileResult:
        if not self._procfs.alive_pid(process.pid):
            return self._missing(process, "proc-missing")
        try:
            facts = self._procfs.facts(process.pid)
        except FileNotFoundError:
            return self._missing(process, "proc-missing")
        if facts.start_identity != process.start_identity:
            return self._missing(process, "proc-pid-reused")
        expected_exe = str(Path(contract.executable).resolve())
        evidence_facts = {
            "exe": facts.executable,
            "argv": facts.argv,
            "cwd": facts.cwd,
            "pgid": facts.process_group_id,
            "environment_digest": environment.digest,
        }
        exact = (
            facts.executable == expected_exe
            and facts.argv == contract.argv
            and facts.cwd == str(Path(contract.cwd).resolve())
            and facts.environment == environment.as_dict()
            and (
                process.process_group_id is None
                or facts.process_group_id == process.process_group_id
            )
        )
        status = ProcessReconcileStatus.EXACT if exact else ProcessReconcileStatus.DRIFT
        return ProcessReconcileResult(
            status,
            (self._evidence_ref(process=process, status=status, facts=evidence_facts),),
            None if exact else "live process identity differs from frozen launch contract",
        )

    def wait_exact(
        self,
        pid: int,
        contract: ServiceLaunchContract,
        environment: MaterializedServiceEnvironment,
        *,
        timeout_s: float,
        poll_interval_s: float = 0.02,
    ) -> tuple[ServiceProcessIdentity, ProcessReconcileResult]:
        deadline = time.monotonic() + timeout_s
        last: ProcessReconcileResult | None = None
        while time.monotonic() < deadline:
            if not self._procfs.alive_pid(pid):
                time.sleep(poll_interval_s)
                continue
            try:
                process = self.identity(pid)
            except (FileNotFoundError, ProcessLookupError):
                time.sleep(poll_interval_s)
                continue
            last = self.reconcile(process, contract, environment)
            if last.status is ProcessReconcileStatus.EXACT:
                return process, last
            if last.status is ProcessReconcileStatus.MISSING:
                time.sleep(poll_interval_s)
                continue
            # A live process with the right start identity but wrong exact facts
            # is drift, not a transient readiness condition.
            break
        detail = last.reason if last is not None else "process never became observable"
        raise RuntimeError(f"process failed exact launch verification: {detail}")


__all__ = ["LinuxExactProcessVerifier"]
