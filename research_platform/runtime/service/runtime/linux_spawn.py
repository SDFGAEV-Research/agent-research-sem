from __future__ import annotations

from research_platform.runtime.service.api import ServiceLaunchContract, ServiceProcessIdentity
import hashlib
import os
from pathlib import Path
import subprocess

from .capture_paths import ServiceCapturePaths
from .environment import MaterializedServiceEnvironment
from .linux_children import LinuxChildRegistry
from .linux_procfs import LinuxProcfsReader


class LinuxProcessSpawner:
    """The sole local ``subprocess.Popen`` authority for supervised services."""

    def __init__(self, procfs: LinuxProcfsReader, children: LinuxChildRegistry) -> None:
        self._procfs = procfs
        self._children = children

    def start(
        self,
        contract: ServiceLaunchContract,
        environment: MaterializedServiceEnvironment,
        captures: ServiceCapturePaths,
    ) -> tuple[ServiceProcessIdentity, tuple[str, ...]]:
        captures.stdout_path.parent.mkdir(parents=True, exist_ok=True)
        captures.stderr_path.parent.mkdir(parents=True, exist_ok=True)
        with captures.stdout_path.open("ab", buffering=0) as stdout, captures.stderr_path.open(
            "ab", buffering=0
        ) as stderr:
            child = subprocess.Popen(
                contract.argv,
                executable=contract.executable,
                cwd=contract.cwd,
                env=environment.as_dict(),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                close_fds=True,
            )
        try:
            visible_pid = self._procfs.visible_pid(child.pid)
            start_identity = self._procfs.start_identity(visible_pid)
            pgid = os.getpgid(child.pid)
        except BaseException:
            child.kill()
            child.wait(timeout=5)
            raise
        self._children.remember(child)
        control_pid = None if visible_pid == child.pid else child.pid
        process = ServiceProcessIdentity(visible_pid, start_identity, pgid, control_pid)
        launch_payload = f"{contract.digest()}:{visible_pid}:{control_pid}:{start_identity}:{pgid}"
        evidence = "proc-start:" + hashlib.sha256(launch_payload.encode()).hexdigest()
        return process, (evidence,)


__all__ = ["LinuxProcessSpawner"]
