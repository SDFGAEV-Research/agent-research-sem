from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import posixpath
import re

from research_platform.runtime.server.identity.api import (
    ServerCommandResult,
    ServerFileTransferResult,
)


class ServerReleaseDeploymentError(RuntimeError):
    """A content-addressed remote release could not be published exactly."""

    def __init__(self, phase: str, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(f"server release deployment failed at {phase}: {message}")
        self.phase = phase
        self.cause = cause


def _require_digest(value: str, *, field: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return value.lower()


@dataclass(frozen=True, slots=True)
class ServerReleaseLayout:
    """Explicit POSIX target layout for immutable server releases."""

    root: str

    def __post_init__(self) -> None:
        if not posixpath.isabs(self.root):
            raise ValueError("server release root must be an absolute POSIX target path")
        normalized = posixpath.normpath(self.root)
        if normalized == "/":
            raise ValueError("server release root must not be the POSIX filesystem root")
        object.__setattr__(self, "root", normalized)

    @property
    def incoming_root(self) -> str:
        return posixpath.join(self.root, "incoming")

    @property
    def releases_root(self) -> str:
        return posixpath.join(self.root, "releases")

    def archive_path(self, release_digest: str) -> str:
        digest = _require_digest(release_digest, field="release_digest")
        return posixpath.join(self.incoming_root, f"{digest}.zip")

    def release_path(self, release_digest: str) -> str:
        digest = _require_digest(release_digest, field="release_digest")
        return posixpath.join(self.releases_root, digest)

    def staging_path(self, release_digest: str) -> str:
        digest = _require_digest(release_digest, field="release_digest")
        return posixpath.join(self.releases_root, f".{digest}.staging")


@dataclass(frozen=True, slots=True)
class ServerReleaseDeploymentRequest:
    release_digest: str
    local_package: Path
    layout: ServerReleaseLayout

    def __post_init__(self) -> None:
        object.__setattr__(self, "release_digest", _require_digest(self.release_digest, field="release_digest"))
        if not self.local_package.is_absolute():
            raise ValueError("local release package must be an absolute path")


@dataclass(frozen=True, slots=True)
class ServerReleaseDeploymentReceipt:
    server_id: str
    release_digest: str
    remote_archive: str
    remote_release_dir: str
    uploaded: bool
    preparation: ServerCommandResult
    transfer: ServerFileTransferResult | None
    finalization: ServerCommandResult | None


__all__ = [
    "ServerReleaseDeploymentError",
    "ServerReleaseDeploymentReceipt",
    "ServerReleaseDeploymentRequest",
    "ServerReleaseLayout",
]
