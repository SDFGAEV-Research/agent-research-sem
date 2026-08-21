from __future__ import annotations

from pathlib import Path

import pytest

from research_platform.runtime.server.identity.providers import (
    ServerProfileFileError,
    load_server_profile_environment,
)


def test_profile_file_replaces_inherited_server_bindings_and_preserves_other_environment(tmp_path: Path) -> None:
    profile = tmp_path / "sem.env"
    profile.write_text(
        "# one authority\nRP_SERVER_SEM_UBUNTU_HOST=research.example\n"
        "RP_SERVER_SEM_UBUNTU_PORT=60320\n",
        encoding="utf-8",
    )
    values = load_server_profile_environment(
        profile,
        base={
            "PATH": "/usr/bin",
            "RP_SERVER_SEM_UBUNTU_HOST": "stale.example",
            "RP_SERVER_OTHER_HOST": "stale-other.example",
        },
    )
    assert values["PATH"] == "/usr/bin"
    assert values["RP_SERVER_SEM_UBUNTU_HOST"] == "research.example"
    assert "RP_SERVER_OTHER_HOST" not in values


def test_profile_file_supports_export_and_fully_quoted_values(tmp_path: Path) -> None:
    profile = tmp_path / "sem.env"
    profile.write_text(
        "export RP_SERVER_SEM_UBUNTU_USER='ubuntu'\n"
        'RP_SERVER_SEM_UBUNTU_TERM="xterm-256color"\n',
        encoding="utf-8",
    )
    values = load_server_profile_environment(profile, base={})
    assert values["RP_SERVER_SEM_UBUNTU_USER"] == "ubuntu"
    assert values["RP_SERVER_SEM_UBUNTU_TERM"] == "xterm-256color"


@pytest.mark.parametrize(
    "content",
    (
        "RP_SERVER_SEM_UBUNTU_HOST\n",
        "RP_SERVER_SEM_UBUNTU_HOST=one\nRP_SERVER_SEM_UBUNTU_HOST=two\n",
        "RP_SERVER_SEM_UBUNTU_HOST=two words\n",
        "RP_SERVER_SEM_UBUNTU_HOST='unterminated\n",
    ),
)
def test_profile_file_rejects_ambiguous_or_unsafe_records(tmp_path: Path, content: str) -> None:
    profile = tmp_path / "bad.env"
    profile.write_text(content, encoding="utf-8")
    with pytest.raises(ServerProfileFileError):
        load_server_profile_environment(profile, base={})


def test_connection_profile_materializes_control_path_and_persist_seconds(tmp_path: Path) -> None:
    from research_platform.runtime.host.providers import LocalOperatingSystemRoute
    from research_platform.runtime.server.identity.providers import EnvironmentSSHServerConnectionFactory

    control_path = Path("/tmp/rp-ssh-%C")
    profile = EnvironmentSSHServerConnectionFactory(LocalOperatingSystemRoute()).from_environment(
        "sem-ubuntu",
        environ={
            "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
            "RP_SERVER_SEM_UBUNTU_PORT": "60320",
            "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
            "RP_SERVER_SEM_UBUNTU_SSH_CONTROL_PATH": str(control_path),
            "RP_SERVER_SEM_UBUNTU_SSH_CONTROL_PERSIST_SECONDS": "900",
        },
    ).profile
    assert profile.control_path == control_path
    assert profile.control_persist_seconds == 900


def test_connection_profile_rejects_an_oversized_control_socket_template(tmp_path: Path) -> None:
    from research_platform.runtime.host.providers import LocalOperatingSystemRoute
    from research_platform.runtime.server.identity.api import ServerIdentityConfigurationError
    from research_platform.runtime.server.identity.providers import EnvironmentSSHServerConnectionFactory

    with pytest.raises(ServerIdentityConfigurationError, match="108"):
        EnvironmentSSHServerConnectionFactory(LocalOperatingSystemRoute()).from_environment(
            "sem-ubuntu",
            environ={
                "RP_SERVER_SEM_UBUNTU_HOST": "research.example",
                "RP_SERVER_SEM_UBUNTU_PORT": "60320",
                "RP_SERVER_SEM_UBUNTU_USER": "ubuntu",
                "RP_SERVER_SEM_UBUNTU_SSH_CONTROL_PATH": str(tmp_path / ("x" * 100)) + "%C",
            },
        )
