from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes, durable_unlink


REGRESSION_STATE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ReleaseRegressionShardResult:
    shard_index: int
    shard_identity_sha256: str
    first_test_file: str
    last_test_file: str
    passed: int
    skipped: int


@dataclass(frozen=True, slots=True)
class ReleaseRegressionState:
    schema_version: int
    source_manifest_digest: str
    test_inventory_sha256: str
    runtime_sha256: str
    tests_collected: int
    shard_size: int
    completed_shards: tuple[ReleaseRegressionShardResult, ...]

    def matches(
        self,
        *,
        source_manifest_digest: str,
        test_inventory_sha256: str,
        runtime_sha256: str,
        tests_collected: int,
        shard_size: int,
    ) -> bool:
        return (
            self.schema_version == REGRESSION_STATE_SCHEMA_VERSION
            and self.source_manifest_digest == source_manifest_digest
            and self.test_inventory_sha256 == test_inventory_sha256
            and self.runtime_sha256 == runtime_sha256
            and self.tests_collected == int(tests_collected)
            and self.shard_size == int(shard_size)
        )

    def result_for(self, shard_index: int, shard_identity_sha256: str) -> ReleaseRegressionShardResult | None:
        for result in self.completed_shards:
            if result.shard_index == shard_index and result.shard_identity_sha256 == shard_identity_sha256:
                return result
        return None

    def with_result(self, result: ReleaseRegressionShardResult) -> "ReleaseRegressionState":
        retained = tuple(item for item in self.completed_shards if item.shard_index != result.shard_index)
        return ReleaseRegressionState(
            schema_version=self.schema_version,
            source_manifest_digest=self.source_manifest_digest,
            test_inventory_sha256=self.test_inventory_sha256,
            runtime_sha256=self.runtime_sha256,
            tests_collected=self.tests_collected,
            shard_size=self.shard_size,
            completed_shards=tuple(sorted((*retained, result), key=lambda item: item.shard_index)),
        )

    def to_json_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def test_inventory_digest(relative_test_files: tuple[str, ...]) -> str:
    raw = "\n".join(relative_test_files).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def shard_identity_digest(relative_test_files: tuple[str, ...]) -> str:
    if not relative_test_files:
        raise ValueError("release regression shard cannot be empty")
    raw = "\n".join(relative_test_files).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def default_regression_state_path(root: Path) -> Path:
    resolved = Path(root).resolve()
    return resolved.parent / f".{resolved.name}.release-regression-state.json"


def decode_regression_state(raw: bytes) -> ReleaseRegressionState:
    try:
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("regression state must be an object")
        shards_raw = payload.pop("completed_shards")
        if not isinstance(shards_raw, list):
            raise TypeError("completed_shards must be a list")
        shards = tuple(ReleaseRegressionShardResult(**item) for item in shards_raw)
        return ReleaseRegressionState(completed_shards=shards, **payload)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("release regression state violates its schema") from exc


def load_regression_state(path: Path) -> ReleaseRegressionState | None:
    path = Path(path)
    if not path.exists():
        return None
    return decode_regression_state(path.read_bytes())


def write_regression_state(path: Path, state: ReleaseRegressionState) -> None:
    atomic_replace_bytes(Path(path), state.to_json_bytes())


def clear_regression_state(path: Path) -> None:
    durable_unlink(Path(path))


__all__ = [
    "REGRESSION_STATE_SCHEMA_VERSION",
    "ReleaseRegressionShardResult",
    "ReleaseRegressionState",
    "clear_regression_state",
    "decode_regression_state",
    "default_regression_state_path",
    "load_regression_state",
    "shard_identity_digest",
    "test_inventory_digest",
    "write_regression_state",
]
