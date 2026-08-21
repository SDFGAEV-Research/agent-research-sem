from __future__ import annotations

from typing import Protocol

from .contracts import (
    ServerReleaseDeploymentReceipt,
    ServerReleaseDeploymentRequest,
)


class ServerReleaseDeploymentPort(Protocol):
    def publish(
        self,
        request: ServerReleaseDeploymentRequest,
        *,
        interactive: bool = False,
    ) -> ServerReleaseDeploymentReceipt: ...


__all__ = ["ServerReleaseDeploymentPort"]
