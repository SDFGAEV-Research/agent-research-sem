from __future__ import annotations

import posixpath
import re
import shlex

from research_platform.runtime.server.api import ServerOperationEffect
from research_platform.runtime.server.identity.api import ServerConnectionPort

from ..api import (
    ServerRepositorySyncError,
    ServerRepositorySyncReceipt,
    ServerRepositorySyncRequest,
    ServerRepositorySyncPort,
    ServerRepositoryStatus,
)


_REPOSITORY_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")


def _shell(value: str) -> str:
    return shlex.quote(value)


class SSHGitRepositorySynchronizer(ServerRepositorySyncPort):
    """Synchronize one exact GitHub revision through the managed SSH port.

    The operator cwd is the only remote repository-root authority. Existing
    checkouts must be clean and must point at the requested origin; the
    synchronizer never resets or overwrites a dirty worktree.
    """

    def __init__(
        self,
        connection: ServerConnectionPort,
        *,
        repository_root: str,
        profile_digest: str = "",
    ) -> None:
        if not repository_root.startswith("/") or repository_root == "/":
            raise ValueError("repository_root must be a non-root absolute POSIX path")
        self._connection = connection
        self._repository_root = posixpath.normpath(repository_root)
        self._profile_digest = profile_digest

    def sync(
        self,
        request: ServerRepositorySyncRequest,
        *,
        interactive: bool = False,
    ) -> ServerRepositorySyncReceipt:
        target = posixpath.join(self._repository_root, request.repository_name)
        staging = target + ".staging-" + request.revision[:12]
        url = _shell(request.repository_url)
        target_q = _shell(target)
        staging_q = _shell(staging)
        revision_q = _shell(request.revision)
        command = (
            "set -eu; "
            f"root={_shell(self._repository_root)}; target={target_q}; staging={staging_q}; "
            "mkdir -p -- \"$root\"; "
            "if [ -e \"$target\" ] && [ ! -d \"$target/.git\" ]; then "
            "printf 'target-not-git\\n' >&2; exit 21; fi; "
            "if [ -d \"$target/.git\" ]; then "
            "test -z \"$(git -C \"$target\" status --porcelain)\"; "
            f"test \"$(git -C \"$target\" remote get-url origin)\" = {url}; "
            "git -C \"$target\" fetch --prune origin master; "
            f"git -C \"$target\" rev-parse --verify {revision_q}^{{commit}} >/dev/null; "
            f"git -C \"$target\" checkout --detach {revision_q}; "
            "else "
            f"test ! -e \"$staging\"; git clone --branch master --single-branch {url} \"$staging\"; "
            f"git -C \"$staging\" rev-parse --verify {revision_q}^{{commit}} >/dev/null; "
            f"git -C \"$staging\" checkout --detach {revision_q}; "
            "mv -- \"$staging\" \"$target\"; fi; "
            f"test \"$(git -C \"$target\" rev-parse HEAD)\" = {revision_q}; "
            "test -z \"$(git -C \"$target\" status --porcelain)\"; "
            "printf 'repository=%s\\nrevision=%s\\ntarget=%s\\n' "
            "\"$(git -C \"$target\" remote get-url origin)\" "
            "\"$(git -C \"$target\" rev-parse HEAD)\" \"$target\""
        )
        result = self._connection.execute(
            command,
            interactive=interactive,
            effect=ServerOperationEffect.MUTATION,
        )
        if not result.succeeded:
            raise ServerRepositorySyncError(
                "sync",
                f"remote command failed rc={result.return_code} failure={result.failure_kind}",
            )
        return ServerRepositorySyncReceipt(
            self._connection.profile.server_id,
            request.repository_url,
            request.repository_name,
            request.revision,
            target,
            result.return_code,
            self._profile_digest,
        )

    def inspect(
        self,
        repository_name: str,
        *,
        staging_revision: str | None = None,
        interactive: bool = False,
    ) -> ServerRepositoryStatus:
        if _REPOSITORY_NAME_RE.fullmatch(repository_name) is None:
            raise ValueError("repository_name contains unsafe or unsupported characters")
        target = posixpath.join(self._repository_root, repository_name)
        staging = target + (".staging-" + staging_revision[:12] if staging_revision else "")
        target_q = _shell(target)
        staging_q = _shell(staging)
        command = (
            "set -eu; "
            f"target={target_q}; staging={staging_q}; "
            "if [ -d \"$target/.git\" ]; then "
            "printf 'exists=1\\nhead=%s\\norigin=%s\\ndirty=%s\\n' "
            "\"$(git -C \"$target\" rev-parse HEAD)\" "
            "\"$(git -C \"$target\" remote get-url origin)\" "
            "\"$(if [ -n \"$(git -C \"$target\" status --porcelain)\" ]; then printf 1; else printf 0; fi)\"; "
            "else printf 'exists=0\\nhead=\\norigin=\\ndirty=\\n'; fi; "
            "if [ -e \"$staging\" ]; then printf 'staging=1\\n'; else printf 'staging=0\\n'; fi"
        )
        result = self._connection.execute(
            command,
            interactive=interactive,
            effect=ServerOperationEffect.OBSERVATION,
        )
        if not result.succeeded:
            raise ServerRepositorySyncError(
                "inspect",
                f"remote command failed rc={result.return_code} failure={result.failure_kind}",
            )
        values: dict[str, str] = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value
        required = {"exists", "head", "origin", "dirty", "staging"}
        if set(values) != required:
            raise ServerRepositorySyncError("inspect", "remote status violated the repository status contract")
        exists = values["exists"] == "1"
        dirty = None if not exists else values["dirty"] == "1"
        return ServerRepositoryStatus(
            self._connection.profile.server_id,
            repository_name,
            target,
            exists,
            values["head"] or None,
            values["origin"] or None,
            dirty,
            values["staging"] == "1",
        )


__all__ = ["SSHGitRepositorySynchronizer"]
