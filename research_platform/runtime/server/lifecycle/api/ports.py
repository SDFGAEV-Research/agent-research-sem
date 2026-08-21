from __future__ import annotations

from typing import Protocol

from .contracts import (
    ServerReleaseDeploymentReceipt,
    ServerReleaseDeploymentRequest,
)


class ServerRuntimeLaunchManifestPort(Protocol):
    release_digest: str
    command_argv: tuple[str, ...]
    launcher_binary_sha256: str
    command_environment_digest: str
    config_digests: tuple[tuple[str, str], ...]

    def digest(self) -> str: ...


class ServerReleaseDeploymentPort(Protocol):
    def publish(
        self,
        request: ServerReleaseDeploymentRequest,
        *,
        interactive: bool = False,
    ) -> ServerReleaseDeploymentReceipt: ...


__all__ = ["ServerReleaseDeploymentPort", "ServerRuntimeLaunchManifestPort"]
