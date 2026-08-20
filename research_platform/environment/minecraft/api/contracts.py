from __future__ import annotations

from dataclasses import dataclass
import ntpath
from pathlib import Path
import posixpath
from typing import Any, Mapping


def _is_absolute_target_path(value: str) -> bool:
    """Recognize both Windows and POSIX target paths on any controller OS."""

    return Path(value).is_absolute() or ntpath.isabs(value) or posixpath.isabs(value)


MINECRAFT_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "goto",
        "collect_block",
        "craft_item",
        "place_block",
        "attack_nearest",
        "wait",
        "chat",
        "observe_entities",
        "registry_search",
    }
)


@dataclass(frozen=True, slots=True)
class MinecraftEndpointSpec:
    """Frozen network and agent identity used by one MC environment instance."""

    host: str = "127.0.0.1"
    port: int = 25565
    username: str = "ResearchPlatformBot"
    auth: str = "offline"
    version: str = ""

    def __post_init__(self) -> None:
        if not self.host.strip() or not self.username.strip() or not self.auth.strip():
            raise ValueError("Minecraft endpoint host, username and auth are required")
        if not 1 <= self.port <= 65535:
            raise ValueError("Minecraft endpoint port must be between 1 and 65535")


@dataclass(frozen=True, slots=True)
class MinecraftBridgeSpec:
    """Frozen bridge process contract; server lifecycle is owned elsewhere."""

    command: tuple[str, ...]
    cwd: str
    stderr_log_path: str | None = None
    connect_timeout_s: float = 45.0
    command_timeout_s: float = 45.0

    def __post_init__(self) -> None:
        if not self.command or any(not item.strip() for item in self.command):
            raise ValueError("Minecraft bridge command must be non-empty")
        if not self.cwd.strip():
            raise ValueError("Minecraft bridge cwd must be non-empty")
        if min(self.connect_timeout_s, self.command_timeout_s) <= 0:
            raise ValueError("Minecraft bridge timeouts must be positive")


@dataclass(frozen=True, slots=True)
class MinecraftEnvironmentSpec:
    """One immutable MC environment selection without runtime state."""

    endpoint: MinecraftEndpointSpec
    bridge: MinecraftBridgeSpec
    implementation_version: str = "1"
    abi_version: str = "1"
    schema_version: str = "1"
    provider_id: str = "minecraft.mineflayer.jsonl.v1"
    max_entities: int = 256

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (
                self.implementation_version,
                self.abi_version,
                self.schema_version,
                self.provider_id,
            )
        ):
            raise ValueError("Minecraft environment identity fields must be non-empty")
        if self.max_entities < 1:
            raise ValueError("Minecraft environment max_entities must be positive")


@dataclass(frozen=True, slots=True)
class MinecraftSessionRuntimeIdentity:
    """MC-owned session runtime identity exposed before participant binding."""

    runtime_id: str
    runtime_version: str
    abi_version: str
    artifact_digest: str

    def __post_init__(self) -> None:
        if any(
            not value.strip()
            for value in (self.runtime_id, self.runtime_version, self.abi_version, self.artifact_digest)
        ):
            raise ValueError("Minecraft session runtime identity fields must be non-empty")


@dataclass(frozen=True, slots=True)
class MinecraftServerSpec:
    """Immutable vanilla-server configuration; it owns no process lifecycle."""

    jar_path: str
    workdir: str
    java_executable: str
    host: str = "127.0.0.1"
    port: int = 25565
    level_name: str = "research-world"
    level_seed: str = "RESEARCH_PLATFORM_FIXED_WORLD_V1"
    online_mode: bool = False
    xms: str = "512M"
    xmx: str = "2G"

    def __post_init__(self) -> None:
        for name, value in (
            ("jar_path", self.jar_path),
            ("workdir", self.workdir),
            ("java_executable", self.java_executable),
        ):
            if not value.strip() or not _is_absolute_target_path(value):
                raise ValueError(f"Minecraft server {name} must be an absolute path")
        if not self.host.strip() or not 1 <= self.port <= 65535:
            raise ValueError("Minecraft server host/port is invalid")
        if (
            not self.level_name.strip()
            or "/" in self.level_name
            or "\\" in self.level_name
            or not self.level_seed.strip()
        ):
            raise ValueError("Minecraft server level identity is invalid")
        if not self.xms.strip() or not self.xmx.strip():
            raise ValueError("Minecraft server heap sizes must be non-empty")

    def command(self) -> tuple[str, ...]:
        return (
            self.java_executable,
            f"-Xms{self.xms}",
            f"-Xmx{self.xmx}",
            "-jar",
            str(Path(self.jar_path)),
            "nogui",
        )


@dataclass(frozen=True, slots=True)
class MinecraftServerPreparedFiles:
    """Prepared server configuration facts, not a server process identity."""

    eula_path: str
    properties_path: str
    eula_accepted: bool
    properties_digest: str

    def __post_init__(self) -> None:
        if not self.eula_path or not self.properties_path or not self.properties_digest:
            raise ValueError("Minecraft prepared-file identity is incomplete")


@dataclass(frozen=True, slots=True)
class MinecraftObservationEvent:
    """Architecture-neutral event decoded from one bridge envelope."""

    kind: str
    payload: Mapping[str, object]
    sequence: int = 0
    timestamp_ms: int = 0
    source: str = "mineflayer"
    request_id: str | None = None

    def __post_init__(self) -> None:
        if not self.kind.strip() or self.sequence < 0 or self.timestamp_ms < 0:
            raise ValueError("Minecraft observation event identity is invalid")
        if not self.source.strip():
            raise ValueError("Minecraft observation event source is required")
        if self.request_id is not None and not self.request_id.strip():
            raise ValueError("Minecraft observation event request_id must be non-empty")


@dataclass(frozen=True, slots=True)
class MinecraftBridgeEnvelope:
    """Validated wire envelope emitted by a Minecraft bridge.

    This is the direct, architecture-neutral extraction of v034's
    ``BridgeEnvelope``. It deliberately contains no task, memory, benchmark or
    evolution fields; those remain payload data owned by the composing project.
    """

    kind: str
    timestamp_ms: int
    payload: Mapping[str, Any]
    source: str = "mineflayer"
    sequence: int = 0
    request_id: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MinecraftBridgeEnvelope":
        if value.get("type") != "event":
            raise ValueError("Minecraft bridge envelope must have type=event")
        kind = str(value.get("kind", ""))
        if not kind.strip():
            raise ValueError("Minecraft bridge event kind is required")
        payload = value.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ValueError("Minecraft bridge event payload must be a mapping")
        timestamp_ms = int(value.get("ts_ms", 0))
        sequence = int(value.get("seq", 0))
        source = str(value.get("source", "mineflayer"))
        request_id_value = value.get("request_id")
        request_id = None if request_id_value is None else str(request_id_value)
        return cls(
            kind=kind,
            timestamp_ms=timestamp_ms,
            payload=dict(payload),
            source=source,
            sequence=sequence,
            request_id=request_id,
        )

    def as_observation(self) -> MinecraftObservationEvent:
        return MinecraftObservationEvent(
            kind=self.kind,
            payload=dict(self.payload),
            sequence=self.sequence,
            timestamp_ms=self.timestamp_ms,
            source=self.source,
            request_id=self.request_id,
        )
