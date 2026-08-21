from __future__ import annotations

import struct

import pytest

from research_platform.environment.minecraft.api import (
    MinecraftConsoleCommandResult,
    MinecraftRconEndpoint,
    MinecraftServerSpec,
)
from research_platform.environment.minecraft.providers.rcon import (
    MinecraftRconConsole,
    MinecraftRconError,
)
from research_platform.environment.minecraft.providers.world_cut import (
    FilesystemMinecraftWorldCutProvider,
)
from research_platform.environment.minecraft.providers.world_quiescence import (
    MinecraftSaveQuiescenceProvider,
    MinecraftWorldQuiescenceError,
)
from research_platform.environment.minecraft.providers.server_files import (
    MinecraftServerPreparationError,
    prepare_server_files,
)


class _ConsoleDouble:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.fail_command: str | None = None

    def execute(self, command: str, *, timeout_s: float) -> MinecraftConsoleCommandResult:
        assert timeout_s > 0
        self.commands.append(command)
        if command == self.fail_command:
            raise RuntimeError(f"command failed: {command}")
        return MinecraftConsoleCommandResult(command, "ok", f"evidence:{command}")


class _IdentityFeed:
    def __init__(self, *values: str) -> None:
        self.values = list(values)
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self.values[min(self.calls - 1, len(self.values) - 1)]


def _quiescence_provider(tmp_path, console: _ConsoleDouble, identity: _IdentityFeed):
    return MinecraftSaveQuiescenceProvider(
        console=console,
        source_workdir=str(tmp_path / "server"),
        level_name="research-world",
        server_contract_digest="c" * 64,
        process_identity_digest=identity,
    )


def test_save_quiescence_holds_and_releases_the_server_save_barrier(tmp_path) -> None:
    console = _ConsoleDouble()
    provider = _quiescence_provider(tmp_path, console, _IdentityFeed("a" * 64))

    cut = provider.save_and_quiesce(session_id="capture-1", context=None)

    assert console.commands == ["save-off", "save-all flush"]
    assert cut.process_identity_digest == "a" * 64
    provider.resume(cut, session_id="capture-1", context=None)
    assert console.commands == ["save-off", "save-all flush", "save-on"]


def test_quiescence_and_world_cut_compose_without_a_second_server_owner(tmp_path) -> None:
    source = tmp_path / "server"
    level = source / "research-world"
    level.mkdir(parents=True)
    (source / "server.properties").write_text("level-name=research-world\n", encoding="utf-8")
    (level / "level.dat").write_bytes(b"level")
    console = _ConsoleDouble()
    quiescence = _quiescence_provider(tmp_path, console, _IdentityFeed("a" * 64))
    cuts = FilesystemMinecraftWorldCutProvider(
        quiescence=quiescence,
        snapshot_root=tmp_path / "cuts",
        branch_root=tmp_path / "branches",
    )

    cut = cuts.capture(session_id="capture-1", context=None)

    assert cut.process_identity_digest == "a" * 64
    assert console.commands == ["save-off", "save-all flush", "save-on"]


def test_server_preparation_configures_rcon_only_with_explicit_secret(tmp_path) -> None:
    jar = tmp_path / "server.jar"
    jar.write_bytes(b"server")
    spec = MinecraftServerSpec(
        jar_path=str(jar),
        workdir=str(tmp_path / "server"),
        java_executable="/usr/bin/java",
        rcon_endpoint=MinecraftRconEndpoint(port=25585),
    )

    with pytest.raises(MinecraftServerPreparationError, match="RCON_PASSWORD_REQUIRED"):
        prepare_server_files(spec, accept_eula=True)
    assert not (tmp_path / "server" / "eula.txt").exists()
    prepare_server_files(spec, accept_eula=True, rcon_password="server-secret")
    properties = (tmp_path / "server" / "server.properties").read_text(encoding="utf-8")
    assert "enable-rcon=true" in properties
    assert "rcon.port=25585" in properties
    assert "rcon.password=server-secret" in properties


def test_save_flush_failure_attempts_save_on_and_preserves_primary_cause(tmp_path) -> None:
    console = _ConsoleDouble()
    console.fail_command = "save-all flush"
    provider = _quiescence_provider(tmp_path, console, _IdentityFeed("a" * 64))

    with pytest.raises(MinecraftWorldQuiescenceError, match="CONSOLE_SAVE_ALL_FLUSH_FAILED") as raised:
        provider.save_and_quiesce(session_id="capture-1", context=None)

    assert raised.value.code == "CONSOLE_SAVE_ALL_FLUSH_FAILED"
    assert console.commands == ["save-off", "save-all flush", "save-on"]


def test_save_off_command_failure_also_attempts_recovery_save_on(tmp_path) -> None:
    console = _ConsoleDouble()
    console.fail_command = "save-off"
    provider = _quiescence_provider(tmp_path, console, _IdentityFeed("a" * 64))

    with pytest.raises(MinecraftWorldQuiescenceError, match="CONSOLE_SAVE_OFF_FAILED"):
        provider.save_and_quiesce(session_id="capture-1", context=None)

    assert console.commands == ["save-off", "save-on"]


def test_changed_process_identity_prevents_recovery_command_to_a_new_server(tmp_path) -> None:
    console = _ConsoleDouble()
    provider = _quiescence_provider(tmp_path, console, _IdentityFeed("a" * 64, "b" * 64))

    with pytest.raises(MinecraftWorldQuiescenceError, match="SAVE_BARRIER_RECOVERY_FAILED") as raised:
        provider.save_and_quiesce(session_id="capture-1", context=None)

    assert raised.value.code == "SAVE_BARRIER_RECOVERY_FAILED"
    assert "PROCESS_IDENTITY_CHANGED" in str(raised.value)
    assert console.commands == ["save-off", "save-all flush"]


def _rcon_packet(request_id: int, packet_type: int, payload: str) -> bytes:
    body = struct.pack("<ii", request_id, packet_type) + payload.encode() + b"\x00\x00"
    return struct.pack("<i", len(body)) + body


class _RconSocket:
    def __init__(self, *, auth_failure: bool = False, expected_timeout: float = 3.0) -> None:
        self.incoming = bytearray()
        self.payloads: list[tuple[int, str]] = []
        self.closed = False
        self.auth_failure = auth_failure
        self.expected_timeout = expected_timeout

    def settimeout(self, value: float | None) -> None:
        assert value == self.expected_timeout

    def connect(self, address: tuple[str, int]) -> None:
        assert address == ("127.0.0.1", 25575)

    def sendall(self, data: bytes) -> None:
        (length,) = struct.unpack("<i", data[:4])
        body = data[4 : 4 + length]
        request_id, packet_type = struct.unpack("<ii", body[:8])
        payload = body[8:-2].decode()
        self.payloads.append((packet_type, payload))
        response_id = -1 if self.auth_failure and packet_type == 3 else request_id
        response_type = 2 if packet_type == 3 else 0
        self.incoming.extend(_rcon_packet(response_id, response_type, "executed"))

    def recv(self, size: int) -> bytes:
        if not self.incoming:
            raise AssertionError("fake RCON server had no response")
        chunk = bytes(self.incoming[:size])
        del self.incoming[:size]
        return chunk

    def close(self) -> None:
        self.closed = True


def test_rcon_console_authenticates_and_returns_non_secret_command_evidence() -> None:
    sock = _RconSocket()
    console = MinecraftRconConsole(
        MinecraftRconEndpoint(command_timeout_s=3.0),
        secret_provider=lambda: "super-secret",
        socket_factory=lambda: sock,
    )

    result = console.execute("save-all flush", timeout_s=3.0)

    assert result.command == "save-all flush"
    assert result.response == "executed"
    assert "super-secret" not in result.evidence_ref
    assert sock.payloads == [(3, "super-secret"), (2, "save-all flush")]
    assert sock.closed is True


def test_rcon_authentication_failure_has_stable_code_and_closes_socket() -> None:
    sock = _RconSocket(auth_failure=True, expected_timeout=1.0)
    console = MinecraftRconConsole(
        MinecraftRconEndpoint(),
        secret_provider=lambda: "wrong-secret",
        socket_factory=lambda: sock,
    )

    with pytest.raises(MinecraftRconError, match="RCON_AUTH_FAILED") as raised:
        console.execute("save-all flush", timeout_s=1.0)

    assert raised.value.code == "RCON_AUTH_FAILED"
    assert "wrong-secret" not in str(raised.value)
    assert sock.closed is True
