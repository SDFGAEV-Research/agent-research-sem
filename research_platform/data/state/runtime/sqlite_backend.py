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

    def read_many(self, aggregate_ids: tuple[str, ...]) -> tuple[EncodedAggregate, ...]:
        """Read a request set without N/SQLite-variable-limit round trips.

        The common path uses one indexed ``IN`` query.  Extremely large request
        sets are materialized once into a connection-local TEMP relation and
        joined in one query, avoiding the previous Python chunk loop that made
        database round trips scale with request cardinality.
        """

        if not aggregate_ids:
            return ()
        variable_limit = max(1, self.conn.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER))
        if len(aggregate_ids) <= variable_limit:
            placeholders = ",".join(["?"] * len(aggregate_ids))
            found = self.conn.execute(
                "SELECT aggregate_id,version,generation,digest,payload,payload_sha256 "
                f"FROM aggregates WHERE aggregate_id IN ({placeholders})",
                aggregate_ids,
            ).fetchall()
            return tuple(self.backend.decode_row(row) for row in found)

        self.conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS state_read_many_ids("
            "aggregate_id TEXT PRIMARY KEY) WITHOUT ROWID"
        )
        self.conn.execute("DELETE FROM state_read_many_ids")
        self.conn.executemany(
            "INSERT INTO state_read_many_ids(aggregate_id) VALUES(?)",
            tuple((aggregate_id,) for aggregate_id in aggregate_ids),
        )
        found = self.conn.execute(
            "SELECT a.aggregate_id,a.version,a.generation,a.digest,a.payload,a.payload_sha256 "
            "FROM aggregates AS a "
            "JOIN state_read_many_ids AS requested USING(aggregate_id)"
        ).fetchall()
        return tuple(self.backend.decode_row(row) for row in found)

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

    def update_many(
        self,
        rows: tuple[tuple[EncodedAggregate, int, str], ...],
    ) -> bool:
        if not rows:
            return True
        cursor = self.conn.executemany(
            """
            UPDATE aggregates
            SET version=?,generation=?,digest=?,payload=?,payload_sha256=?
            WHERE aggregate_id=? AND version=? AND generation=?
            """,
            (
                (
                    value.version,
                    value.generation,
                    value.digest,
                    value.payload,
                    value.payload_sha256,
                    value.aggregate_id,
                    expected_version,
                    expected_generation,
                )
                for value, expected_version, expected_generation in rows
            ),
        )
        return cursor.rowcount == len(rows)

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
