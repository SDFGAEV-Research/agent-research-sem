from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from research_platform.runtime.session.api import (
    PersistentSessionReport,
    PersistentSessionRuntimePort,
    PersistentSessionSpec,
)

from .contracts import FrozenRuntimeManifest

_SLUG = re.compile(r"[^A-Za-z0-9_.-]+")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeControllerCommand:
    argv: tuple[str, ...]
    cwd: str
    environment: tuple[tuple[str, str], ...] = ()
    launcher_binary_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.argv:
            raise ValueError("runtime controller argv required")
        if not Path(self.cwd).is_absolute():
            raise ValueError("runtime controller cwd must be absolute")
        launcher = Path(self.argv[0])
        if not launcher.is_absolute():
            raise ValueError("runtime controller launcher must be an absolute path")
        keys = [key for key, _ in self.environment]
        if tuple(sorted(self.environment)) != self.environment:
            raise ValueError("runtime controller environment must be sorted canonically")
        if len(keys) != len(set(keys)) or any(not key or "=" in key or "\0" in key for key in keys):
            raise ValueError("runtime controller environment keys must be unique safe names")
        if any("\0" in value for _, value in self.environment):
            raise ValueError("runtime controller environment values cannot contain NUL")
        digest = self.launcher_binary_sha256
        if not digest:
            if not launcher.is_file():
                raise FileNotFoundError(f"runtime controller launcher missing: {launcher}")
            digest = _sha256_file(launcher)
            object.__setattr__(self, "launcher_binary_sha256", digest)
        if len(digest) != 64:
            raise ValueError("runtime controller launcher identity must be SHA-256")

    def digest(self) -> str:
        raw = json.dumps(
            {
                "argv": self.argv,
                "cwd": self.cwd,
                "launcher_binary_sha256": self.launcher_binary_sha256,
                "environment": self.environment,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class RuntimePersistentSessionHost:
    """Maps frozen runtime-controller identity to a generic persistent session."""

    def __init__(self, sessions: PersistentSessionRuntimePort) -> None:
        self.sessions = sessions

    @property
    def transport_backend_id(self) -> str:
        return self.sessions.backend_id

    @property
    def transport_identity_digest(self) -> str:
        return self.sessions.transport_identity_digest

    @property
    def transport_identity_verified(self) -> bool:
        return self.sessions.transport_identity_verified

    @staticmethod
    def session_name(control_id: str, manifest_digest: str) -> str:
        slug = _SLUG.sub("-", control_id).strip("-._")[:32] or "runtime"
        control_hash = hashlib.sha256(control_id.encode("utf-8")).hexdigest()[:8]
        return f"rp-{slug}-{control_hash}-{manifest_digest[:12]}"

    def spec(
        self,
        manifest: FrozenRuntimeManifest,
        *,
        control_id: str,
        command: RuntimeControllerCommand,
    ) -> PersistentSessionSpec:
        digest = manifest.digest()
        return PersistentSessionSpec(
            self.session_name(control_id, digest),
            command.argv,
            command.cwd,
            control_id,
            digest,
            command.digest(),
            command.environment,
        )

    def ensure(
        self,
        manifest: FrozenRuntimeManifest,
        *,
        control_id: str,
        command: RuntimeControllerCommand,
    ) -> PersistentSessionReport:
        return self.sessions.ensure(self.spec(manifest, control_id=control_id, command=command))


__all__ = ["RuntimeControllerCommand", "RuntimePersistentSessionHost"]
