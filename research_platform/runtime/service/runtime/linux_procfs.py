from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LinuxProcessFacts:
    start_identity: str
    executable: str
    argv: tuple[str, ...]
    cwd: str
    environment: dict[str, str]
    process_group_id: int


class LinuxProcfsReader:
    """Read-only /proc view. Signal/spawn authority deliberately lives elsewhere."""

    def __init__(self, root: Path = Path("/proc")) -> None:
        self.root = root

    def path(self, pid: int, name: str = "") -> Path:
        return self.root / str(pid) / name

    @staticmethod
    def alive_pid(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def start_identity(self, pid: int) -> str:
        stat = self.path(pid, "stat").read_text(encoding="utf-8")
        close = stat.rfind(")")
        if close < 0:
            raise RuntimeError("invalid /proc stat format")
        fields = stat[close + 2 :].split()
        if len(fields) <= 19:
            raise RuntimeError("/proc stat missing starttime")
        start_ticks = fields[19]
        boot_id_path = self.root / "sys/kernel/random/boot_id"
        boot_id = boot_id_path.read_text(encoding="utf-8").strip() if boot_id_path.exists() else "unknown-boot"
        return f"linux-proc:{boot_id}:{start_ticks}"

    def cmdline(self, pid: int) -> tuple[str, ...]:
        raw = self.path(pid, "cmdline").read_bytes()
        return tuple(part.decode("utf-8", errors="surrogateescape") for part in raw.split(b"\x00") if part)

    def environment(self, pid: int) -> dict[str, str]:
        raw = self.path(pid, "environ").read_bytes()
        result: dict[str, str] = {}
        for item in raw.split(b"\x00"):
            if not item:
                continue
            key, sep, value = item.partition(b"=")
            if not sep:
                continue
            result[key.decode("utf-8", errors="surrogateescape")] = value.decode("utf-8", errors="surrogateescape")
        return result

    def facts(self, pid: int) -> LinuxProcessFacts:
        return LinuxProcessFacts(
            start_identity=self.start_identity(pid),
            executable=str(self.path(pid, "exe").resolve()),
            argv=self.cmdline(pid),
            cwd=str(self.path(pid, "cwd").resolve()),
            environment=self.environment(pid),
            process_group_id=os.getpgid(pid),
        )


__all__ = ["LinuxProcessFacts", "LinuxProcfsReader"]
