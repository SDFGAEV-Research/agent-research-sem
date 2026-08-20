from __future__ import annotations

import shutil
import subprocess

from research_platform.resource.compute.api import (
    GpuDeviceStatus,
    GpuProcessStatus,
    GpuRuntimeSnapshot,
)


class NvidiaSmiGpuRuntimeObserver:
    """Best-effort operational GPU view; it never acts as an admission gate."""

    def __init__(self, executable: str = "nvidia-smi") -> None:
        self._executable = executable

    def snapshot(self) -> GpuRuntimeSnapshot:
        executable = shutil.which(self._executable)
        if executable is None:
            return GpuRuntimeSnapshot(False, detail="nvidia-smi-unavailable")
        devices = self._devices(executable)
        if devices is None:
            return GpuRuntimeSnapshot(False, detail="nvidia-smi-query-failed")
        processes = self._processes(executable)
        return GpuRuntimeSnapshot(True, devices=devices, processes=processes)

    @staticmethod
    def _devices(executable: str) -> tuple[GpuDeviceStatus, ...] | None:
        try:
            result = subprocess.run(
                (
                    executable,
                    "--query-gpu=index,uuid,name,memory.total,memory.used,memory.free,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        values: list[GpuDeviceStatus] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            row = [item.strip() for item in line.split(",", 6)]
            if len(row) != 7:
                continue
            try:
                values.append(GpuDeviceStatus(row[0], row[1], row[2], int(row[3]), int(row[4]), int(row[5]), int(row[6])))
            except ValueError:
                continue
        return tuple(values)

    @staticmethod
    def _processes(executable: str) -> tuple[GpuProcessStatus, ...]:
        try:
            result = subprocess.run(
                (
                    executable,
                    "--query-compute-apps=pid,gpu_uuid,used_gpu_memory,process_name",
                    "--format=csv,noheader,nounits",
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5.0,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ()
        if result.returncode != 0:
            return ()
        values: list[GpuProcessStatus] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            row = [item.strip() for item in line.split(",", 3)]
            if len(row) != 4:
                continue
            try:
                values.append(GpuProcessStatus(int(row[0]), row[1], int(row[2]), row[3]))
            except ValueError:
                continue
        return tuple(values)


__all__ = ["NvidiaSmiGpuRuntimeObserver"]
