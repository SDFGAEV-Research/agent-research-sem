from __future__ import annotations

from research_platform.runtime.server.identity.api import ServerCommandResult
from research_platform.runtime.server.lifecycle.api import ServerRepositoryCommandRequest
from research_platform.runtime.server.lifecycle.providers import SSHGitRepositoryCommandRunner


REVISION = "b" * 40


def test_repository_command_request_is_pinned_and_confined() -> None:
    request = ServerRepositoryCommandRequest(
        "agent-research-platform-system",
        REVISION.upper(),
        ("python", "-m", "compileall", "-q", "."),
        "projects/sem_paper",
    )
    assert request.revision == REVISION
    assert request.relative_cwd == "projects/sem_paper"


def test_repository_command_request_rejects_escape_and_empty_argv() -> None:
    import pytest

    with pytest.raises(ValueError, match="relative_cwd"):
        ServerRepositoryCommandRequest("repo", REVISION, ("python",), "../outside")
    with pytest.raises(ValueError, match="command_argv"):
        ServerRepositoryCommandRequest("repo", REVISION, ())


def test_repository_command_uses_exact_checkout_and_mutation_observation() -> None:
    captured: list[tuple[str, bool, object]] = []

    class Connection:
        profile = type("Profile", (), {"server_id": "sem-ubuntu", "repository_timeout_seconds": 1800.0})()

        def execute(self, command: str, *, interactive: bool = False, effect=None, timeout_seconds=None):
            del timeout_seconds
            captured.append((command, interactive, effect))
            return ServerCommandResult("sem-ubuntu", command, 0, "ok\n", "")

    runner = SSHGitRepositoryCommandRunner(
        Connection(),
        repository_root="/data/research-platform",
        profile_digest="p" * 64,
    )
    receipt = runner.run(
        ServerRepositoryCommandRequest(
            "agent-research-platform-system",
            REVISION,
            ("python", "-m", "compileall", "-q", "."),
            "projects/sem_paper",
        ),
        interactive=True,
    )
    command, interactive, effect = captured[0]
    assert interactive is True
    assert str(effect) == "mutation"
    assert f"expected={REVISION}" in command
    assert "cd \"$cwd\"" in command
    assert receipt.target_path == "/data/research-platform/agent-research-platform-system"
    assert receipt.working_directory == (
        "/data/research-platform/agent-research-platform-system/projects/sem_paper"
    )
    assert receipt.succeeded is True
    assert receipt.profile_digest == "p" * 64
