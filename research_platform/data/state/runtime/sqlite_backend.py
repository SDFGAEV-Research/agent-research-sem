from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True, slots=True)
class EncodedAggregate:
    aggregate_id: str
    version: int
    generation: str
    digest: str
    payload: bytes
    payload_sha256: str


class SQLiteStateWriteSession(AbstractContextManager["SQLiteStateWriteSession"]):
    def __init__(self, backend: "SQLiteStateBackend") -> None:
        self.backend = backend
        self.conn = backend.connect()
        self.conn.execute("BEGIN IMMEDIATE")
        self._complete = False

    def read(self, aggregate_id: str) -> EncodedAggregate | None:
        row = self.conn.execute(
            "SELECT aggregate_id,version,generation,digest,payload,payload_sha256 "
            "FROM aggregates WHERE aggregate_id=?",
            (aggregate_id,),
        ).fetchone()
        return self.backend.decode_row(row) if row is not None else None

    def update(
        self,
        value: EncodedAggregate,
        *,
        expected_version: int,
        expected_generation: str,
    ) -> bool:
        cursor = self.conn.execute(
            """
            UPDATE aggregates
            SET version=?,generation=?,digest=?,payload=?,payload_sha256=?
            WHERE aggregate_id=? AND version=? AND generation=?
            """,
            (
                value.version,
                value.generation,
                value.digest,
                value.payload,
                value.payload_sha256,
                value.aggregate_id,
                expected_version,
                expected_generation,
            ),
        )
        return cursor.rowcount == 1

    def commit(self) -> None:
        self.conn.commit()
        self._complete = True

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is not None or not self._complete:
                self.conn.rollback()
        finally:
            self.conn.close()
        return False


class SQLiteStateBackend:
    """SQLite mechanics only; knows nothing about scientific payload schemas or CAS policy."""

    SCHEMA_VERSION = 1

    def __init__(self, path: Path, *, timeout_seconds: float = 30.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=self.timeout_seconds, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def connection(self):
        """Own and close every state connection, including initialization/read paths."""

        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def decode_row(row: tuple[object, ...]) -> EncodedAggregate:
        return EncodedAggregate(
            str(row[0]), int(row[1]), str(row[2]), str(row[3]), bytes(row[4]), str(row[5])
        )

    def initialize(self, initial: tuple[EncodedAggregate, ...]) -> None:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._ensure_schema(conn)
                for value in initial:
                    self._insert_if_absent(conn, value)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE IF NOT EXISTS state_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS aggregates (
                aggregate_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                generation TEXT NOT NULL,
                digest TEXT NOT NULL,
                payload BLOB NOT NULL,
                payload_sha256 TEXT NOT NULL
            )
            """
        )
        row = conn.execute("SELECT value FROM state_meta WHERE key='schema_version'").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO state_meta(key,value) VALUES('schema_version',?)",
                (str(self.SCHEMA_VERSION),),
            )
        elif int(row[0]) != self.SCHEMA_VERSION:
            raise RuntimeError("unsupported SQLiteAtomicStateStore schema")

    @staticmethod
    def _insert_if_absent(conn: sqlite3.Connection, value: EncodedAggregate) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO aggregates(
                aggregate_id,version,generation,digest,payload,payload_sha256
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                value.aggregate_id,
                value.version,
                value.generation,
                value.digest,
                value.payload,
                value.payload_sha256,
            ),
        )

    def read(self, aggregate_id: str) -> EncodedAggregate | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT aggregate_id,version,generation,digest,payload,payload_sha256 "
                "FROM aggregates WHERE aggregate_id=?",
                (aggregate_id,),
            ).fetchone()
        return self.decode_row(row) if row is not None else None

    def write_session(self) -> SQLiteStateWriteSession:
        return SQLiteStateWriteSession(self)
