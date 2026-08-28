from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from research_platform.artifact.catalog.api import (
    ArtifactKind,
    ArtifactNotFound,
    ArtifactQuery,
    ArtifactRecord,
    ArtifactRegistryConflict,
    ArtifactRegistryCorruptionError,
    ArtifactRetention,
)
from research_platform.artifact._canonical import canonical_digest
from research_platform.scope.api import ScopeIdentity, ScopeKind


class SQLiteArtifactRegistry:
    """Immutable SQLite artifact catalog with record-integrity verification."""

    _COLUMNS = (
        "artifact_id", "kind", "scope_kind", "scope_id", "digest", "location",
        "producer_component_id", "producer_operation_id", "media_type", "lineage_json",
        "declared_retention", "metadata_json", "record_sha256",
    )

    def __init__(self, path: str | Path, *, timeout_seconds: float = 30.0) -> None:
        self.path = Path(path).expanduser().resolve()
        self.timeout_seconds = timeout_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            self._ensure_schema(db)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=self.timeout_seconds, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute(f"PRAGMA busy_timeout={int(self.timeout_seconds * 1000)}")
        return db

    @classmethod
    def _ensure_schema(cls, db: sqlite3.Connection) -> None:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS artifacts(
                artifact_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                scope_kind TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                digest TEXT NOT NULL,
                location TEXT NOT NULL,
                producer_component_id TEXT NOT NULL,
                producer_operation_id TEXT,
                media_type TEXT NOT NULL,
                lineage_json TEXT NOT NULL,
                declared_retention TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_artifacts_scope ON artifacts(scope_kind,scope_id,artifact_id);
            CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind,artifact_id);
            CREATE INDEX IF NOT EXISTS idx_artifacts_producer ON artifacts(producer_component_id,artifact_id);
            """
        )
        columns = tuple(row[1] for row in db.execute("PRAGMA table_info(artifacts)"))
        if columns != cls._COLUMNS:
            raise ArtifactRegistryCorruptionError(
                f"unsupported artifact catalog schema columns: {columns!r}"
            )

    @staticmethod
    def _document(record: ArtifactRecord) -> dict[str, object]:
        return {
            "artifact_id": record.artifact_id,
            "kind": record.kind.value,
            "scope": {"kind": record.scope.kind.value, "scope_id": record.scope.scope_id},
            "digest": record.digest,
            "location": record.location,
            "producer_component_id": record.producer_component_id,
            "producer_operation_id": record.producer_operation_id,
            "media_type": record.media_type,
            "lineage": record.lineage,
            "retention": record.retention.value,
            "metadata": record.metadata,
        }

    @classmethod
    def _record_digest(cls, record: ArtifactRecord) -> str:
        return canonical_digest(cls._document(record))

    @classmethod
    def _encode(cls, record: ArtifactRecord) -> tuple[object, ...]:
        return (
            record.artifact_id,
            record.kind.value,
            record.scope.kind.value,
            record.scope.scope_id,
            record.digest,
            record.location,
            record.producer_component_id,
            record.producer_operation_id,
            record.media_type,
            json.dumps(record.lineage, ensure_ascii=False, separators=(",", ":")),
            record.retention.value,
            json.dumps(record.metadata, ensure_ascii=False, separators=(",", ":")),
            cls._record_digest(record),
        )

    @classmethod
    def _decode(cls, row: tuple[object, ...]) -> ArtifactRecord:
        try:
            lineage = json.loads(str(row[9]))
            metadata = json.loads(str(row[11]))
            if not isinstance(lineage, list) or not isinstance(metadata, list):
                raise TypeError("artifact collection fields have invalid JSON shape")
            if any(not isinstance(value, str) for value in lineage):
                raise TypeError("artifact lineage JSON must contain only strings")
            if any(
                not isinstance(pair, list)
                or len(pair) != 2
                or not isinstance(pair[0], str)
                or not isinstance(pair[1], str)
                for pair in metadata
            ):
                raise TypeError("artifact metadata JSON must contain string pairs")
            record = ArtifactRecord(
                artifact_id=str(row[0]),
                kind=ArtifactKind(str(row[1])),
                scope=ScopeIdentity(ScopeKind(str(row[2])), str(row[3])),
                digest=str(row[4]),
                location=str(row[5]),
                producer_component_id=str(row[6]),
                producer_operation_id=None if row[7] is None else str(row[7]),
                media_type=str(row[8]),
                lineage=tuple(lineage),
                retention=ArtifactRetention(str(row[10])),
                metadata=tuple((pair[0], pair[1]) for pair in metadata),
            )
        except (IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ArtifactRegistryCorruptionError("artifact catalog record cannot be decoded") from exc
        if cls._record_digest(record) != str(row[12]):
            raise ArtifactRegistryCorruptionError(
                f"artifact catalog record integrity mismatch: {record.artifact_id}"
            )
        return record

    @classmethod
    def _select_columns(cls) -> str:
        return ",".join(cls._COLUMNS)

    def put(self, artifact: ArtifactRecord) -> ArtifactRecord:
        encoded = self._encode(artifact)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                current_row = db.execute(
                    f"SELECT {self._select_columns()} FROM artifacts WHERE artifact_id=?",
                    (artifact.artifact_id,),
                ).fetchone()
                if current_row is not None:
                    current = self._decode(current_row)
                    if current != artifact:
                        raise ArtifactRegistryConflict(artifact.artifact_id)
                    db.execute("COMMIT")
                    return current
                db.execute(
                    "INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    encoded,
                )
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return artifact

    def get(self, artifact_id: str) -> ArtifactRecord:
        with closing(self._connect()) as db:
            row = db.execute(
                f"SELECT {self._select_columns()} FROM artifacts WHERE artifact_id=?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise ArtifactNotFound(artifact_id)
        return self._decode(row)

    def query(self, query: ArtifactQuery = ArtifactQuery()) -> tuple[ArtifactRecord, ...]:
        clauses: list[str] = []
        args: list[object] = []
        if query.scope is not None:
            clauses.extend(("scope_kind=?", "scope_id=?"))
            args.extend((query.scope.kind.value, query.scope.scope_id))
        if query.kind is not None:
            clauses.append("kind=?")
            args.append(query.kind.value)
        if query.producer_component_id is not None:
            clauses.append("producer_component_id=?")
            args.append(query.producer_component_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as db:
            rows = db.execute(
                f"SELECT {self._select_columns()} FROM artifacts{where} ORDER BY artifact_id",
                args,
            ).fetchall()
        return tuple(self._decode(row) for row in rows)


__all__ = ["SQLiteArtifactRegistry"]
