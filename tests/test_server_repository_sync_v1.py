from __future__ import annotations

from research_platform.runtime.server.identity.api import (
    ServerCommandResult,
    ServerTransportFailureKind,
)
from research_platform.runtime.server.lifecycle.api import (
    ServerRepositorySyncError,
    ServerRepositorySyncRequest,
)
from research_platform.runtime.server.lifecycle.providers import SSHGitRepositorySynchronizer


REVISION = "a" * 40
URL = "https://github.com/SDFGAEV/agent-research-platform-system.git"


def test_repository_request_requires_exact_github_revision() -> None:
    request = ServerRepositorySyncRequest(URL, "agent-research-platform-system", REVISION)
    assert request.revision == REVISION


def test_repository_request_rejects_unsafe_source_and_revision() -> None:
    import pytest

    with pytest.raises(ValueError, match="GitHub"):
        ServerRepositorySyncRequest("https://example.com/repo.git", "repo", REVISION)
    with pytest.raises(ValueError, match="revision"):
        ServerRepositorySyncRequest(URL, "repo", "not-a-commit")
    with pytest.raises(ValueError, match="repository_name"):
        ServerRepositorySyncRequest(URL, "../repo", REVISION)


def test_repository_sync_uses_profile_owned_root_and_pinned_checkout() -> None:
    captured: list[tuple[str, bool, object]] = []

    class Connection:
        profile = type("Profile", (), {"server_id": "sem-ubuntu"})()

        def execute(self, command: str, *, interactive: bool = False, effect=None):
            captured.append((command, interactive, effect))
            return ServerCommandResult("sem-ubuntu", command, 0, "", "")

    synchronizer = SSHGitRepositorySynchronizer(
        Connection(),
        repository_root="/data/research-platform",
        profile_digest="p" * 64,
    )
    receipt = synchronizer.sync(
        ServerRepositorySyncRequest(URL, "agent-research-platform-system", REVISION),
        interactive=True,
    )
    command, interactive, effect = captured[0]
    assert interactive is True
    assert str(effect) == "mutation"
    assert "git clone --branch master --single-branch" in command
    assert "checkout --detach" in command
    assert REVISION in command
    assert receipt.target_path == "/data/research-platform/agent-research-platform-system"
    assert receipt.profile_digest == "p" * 64


def test_repository_status_reads_only_the_profile_owned_checkout() -> None:
    captured: list[tuple[str, bool, object]] = []

    class Connection:
        profile = type("Profile", (), {"server_id": "sem-ubuntu"})()

        def execute(self, command: str, *, interactive: bool = False, effect=None):
            captured.append((command, interactive, effect))
            return ServerCommandResult(
                "sem-ubuntu",
                command,
                0,
                "target_kind=git\nexists=1\nhead="
                + REVISION
                + "\norigin="
                + URL
                + "\ndirty=0\nstaging_kind=absent\nstaging=0\ntarget_children=\n",
                "",
            )

    synchronizer = SSHGitRepositorySynchronizer(
        Connection(), repository_root="/data/research-platform"
    )
    status = synchronizer.inspect("agent-research-platform-system", staging_revision=REVISION)
    assert status.exists is True
    assert status.head == REVISION
    assert status.dirty is False
    assert status.staging_exists is False
    assert status.target_kind == "git"
    assert status.staging_kind == "absent"
    assert status.target_children == ()
    assert captured[0][2].value == "observation"


def test_repository_status_distinguishes_a_non_git_target_directory() -> None:
    class Connection:
        profile = type("Profile", (), {"server_id": "sem-ubuntu"})()

        def execute(self, command: str, *, interactive: bool = False, effect=None):
            return ServerCommandResult(
                "sem-ubuntu",
                command,
                0,
                "target_kind=directory\nexists=0\nhead=\norigin=\n"
                "dirty=\nstaging_kind=absent\nstaging=0\n"
                "target_children=envs,models,runs\n",
                "",
            )

    status = SSHGitRepositorySynchronizer(
        Connection(), repository_root="/data/research-platform/repositories"
    ).inspect("agent-research-platform-system", staging_revision=REVISION)
    assert status.exists is False
    assert status.target_kind == "directory"
    assert status.target_children == ("envs", "models", "runs")
    assert status.staging_kind == "absent"


def test_repository_sync_preserves_structured_transport_failure() -> None:
    class Connection:
        profile = type("Profile", (), {"server_id": "sem-ubuntu"})()

        def execute(self, command: str, *, interactive: bool = False, effect=None):
            return ServerCommandResult(
                "sem-ubuntu",
                command,
                255,
                "",
                "connection closed",
                ServerTransportFailureKind.NETWORK,
            )

    synchronizer = SSHGitRepositorySynchronizer(
        Connection(), repository_root="/data/research-platform"
    )
    import pytest

    with pytest.raises(ServerRepositorySyncError, match="network"):
        synchronizer.sync(ServerRepositorySyncRequest(URL, "repo", REVISION))
