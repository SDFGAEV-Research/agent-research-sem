from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from research_platform.data.dataset.api import (
    DatasetIdentity,
    DatasetNotFound,
    DatasetQuery,
    DatasetRegistryConflict,
    DatasetRegistryCorruptionError,
    DatasetVersion,
)
from research_platform.data._canonical import canonical_digest
from research_platform.data._sqlite_types import require_optional_text, require_text
from research_platform.scope.api import ScopeIdentity, ScopeKind


class SQLiteDatasetRegistry:
    """Immutable SQLite dataset-version registry with verified base records."""

    _COLUMNS = (
        "dataset_key", "dataset_id", "version", "scope_kind", "scope_id", "digest",
        "location", "schema_ref", "parents_json", "tags_json", "metadata_json", "record_sha256",
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
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @classmethod
    def _ensure_schema(cls, db: sqlite3.Connection) -> None:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS datasets(
                dataset_key TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                version TEXT NOT NULL,
                scope_kind TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                digest TEXT NOT NULL,
                location TEXT NOT NULL,
                schema_ref TEXT,
                parents_json TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_datasets_identity ON datasets(dataset_id,version);
            CREATE INDEX IF NOT EXISTS idx_datasets_scope ON datasets(scope_kind,scope_id,dataset_key);
            CREATE TABLE IF NOT EXISTS dataset_tags(
                dataset_key TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY(dataset_key,tag),
                FOREIGN KEY(dataset_key) REFERENCES datasets(dataset_key) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_dataset_tags_tag ON dataset_tags(tag,dataset_key);
            """
        )
        columns = tuple(row[1] for row in db.execute("PRAGMA table_info(datasets)"))
        if columns != cls._COLUMNS:
            raise DatasetRegistryCorruptionError(
                f"unsupported dataset registry schema columns: {columns!r}"
            )

    @staticmethod
    def _document(dataset: DatasetVersion) -> dict[str, object]:
        return {
            "identity": {"dataset_id": dataset.identity.dataset_id, "version": dataset.identity.version},
            "scope": {"kind": dataset.scope.kind.value, "scope_id": dataset.scope.scope_id},
            "digest": dataset.digest,
            "location": dataset.location,
            "schema_ref": dataset.schema_ref,
            "parent_versions": dataset.parent_versions,
            "tags": dataset.tags,
            "metadata": dataset.metadata,
        }

    @classmethod
    def _record_digest(cls, dataset: DatasetVersion) -> str:
        return canonical_digest(cls._document(dataset))

    @classmethod
    def _encode(cls, dataset: DatasetVersion) -> tuple[object, ...]:
        return (
            dataset.identity.key,
            dataset.identity.dataset_id,
            dataset.identity.version,
            dataset.scope.kind.value,
            dataset.scope.scope_id,
            dataset.digest,
            dataset.location,
            dataset.schema_ref,
            json.dumps(dataset.parent_versions, ensure_ascii=False, separators=(",", ":")),
            json.dumps(dataset.tags, ensure_ascii=False, separators=(",", ":")),
            json.dumps(dataset.metadata, ensure_ascii=False, separators=(",", ":")),
            cls._record_digest(dataset),
        )

    @classmethod
    def _decode(cls, row: tuple[object, ...]) -> DatasetVersion:
        try:
            parents = json.loads(require_text(row[8], label="dataset parents_json"))
            tags = json.loads(require_text(row[9], label="dataset tags_json"))
            metadata = json.loads(require_text(row[10], label="dataset metadata_json"))
            if not isinstance(parents, list) or not isinstance(tags, list) or not isinstance(metadata, list):
                raise TypeError("dataset collection fields have invalid JSON shape")
            if any(not isinstance(value, str) for value in parents):
                raise TypeError("dataset parents JSON must contain only strings")
            if any(not isinstance(value, str) for value in tags):
                raise TypeError("dataset tags JSON must contain only strings")
            if any(
                not isinstance(pair, list)
                or len(pair) != 2
                or not isinstance(pair[0], str)
                or not isinstance(pair[1], str)
                for pair in metadata
            ):
                raise TypeError("dataset metadata JSON must contain string pairs")
            dataset = DatasetVersion(
                identity=DatasetIdentity(
                    require_text(row[1], label="dataset_id"),
                    require_text(row[2], label="dataset version"),
                ),
                scope=ScopeIdentity(
                    ScopeKind(require_text(row[3], label="dataset scope_kind")),
                    require_text(row[4], label="dataset scope_id"),
                ),
                digest=require_text(row[5], label="dataset digest"),
                location=require_text(row[6], label="dataset location"),
                schema_ref=require_optional_text(row[7], label="dataset schema_ref"),
                parent_versions=tuple(parents),
                tags=tuple(tags),
                metadata=tuple((pair[0], pair[1]) for pair in metadata),
            )
            dataset_key = require_text(row[0], label="dataset_key")
            record_sha256 = require_text(row[11], label="dataset record_sha256")
        except (IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DatasetRegistryCorruptionError("dataset registry record cannot be decoded") from exc
        if dataset.identity.key != dataset_key:
            raise DatasetRegistryCorruptionError(
                f"dataset key does not match identity: {row[0]!r}"
            )
        if cls._record_digest(dataset) != record_sha256:
            raise DatasetRegistryCorruptionError(
                f"dataset registry record integrity mismatch: {dataset.identity.key}"
            )
        return dataset

    @classmethod
    def _select_columns(cls) -> str:
        return ",".join(cls._COLUMNS)

    def register(self, dataset: DatasetVersion) -> DatasetVersion:
        encoded = self._encode(dataset)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    f"SELECT {self._select_columns()} FROM datasets WHERE dataset_key=?",
                    (dataset.identity.key,),
                ).fetchone()
                if row is not None:
                    current = self._decode(row)
                    if current != dataset:
                        raise DatasetRegistryConflict(dataset.identity.key)
                    db.execute("COMMIT")
                    return current
                db.execute("INSERT INTO datasets VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", encoded)
                db.executemany(
                    "INSERT INTO dataset_tags(dataset_key,tag) VALUES(?,?)",
                    ((dataset.identity.key, tag) for tag in dataset.tags),
                )
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return dataset

    def get(self, identity: DatasetIdentity) -> DatasetVersion:
        with closing(self._connect()) as db:
            row = db.execute(
                f"SELECT {self._select_columns()} FROM datasets WHERE dataset_key=?",
                (identity.key,),
            ).fetchone()
        if row is None:
            raise DatasetNotFound(identity.key)
        return self._decode(row)

    def query(self, query: DatasetQuery = DatasetQuery()) -> tuple[DatasetVersion, ...]:
        clauses: list[str] = []
        args: list[object] = []
        join = ""
        if query.tag is not None:
            join = " JOIN dataset_tags t ON t.dataset_key=d.dataset_key"
            clauses.append("t.tag=?")
            args.append(query.tag)
        if query.dataset_id is not None:
            clauses.append("d.dataset_id=?")
            args.append(query.dataset_id)
        if query.scope is not None:
            clauses.extend(("d.scope_kind=?", "d.scope_id=?"))
            args.extend((query.scope.kind.value, query.scope.scope_id))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        columns = ",".join(f"d.{column}" for column in self._COLUMNS)
        with closing(self._connect()) as db:
            rows = db.execute(
                f"SELECT {columns} FROM datasets d{join}{where} ORDER BY d.dataset_key",
                args,
            ).fetchall()
        decoded = tuple(self._decode(row) for row in rows)
        if query.tag is not None and any(query.tag not in row.tags for row in decoded):
            raise DatasetRegistryCorruptionError("dataset tag index disagrees with authoritative record")
        return decoded


__all__ = ["SQLiteDatasetRegistry"]
