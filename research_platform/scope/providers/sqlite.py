from __future__ import annotations

import sqlite3

from research_platform.platform.kernel.retry import retry_until_deadline
from contextlib import contextmanager
from pathlib import Path

from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity, ScopeKind
from research_platform.scope.runtime import ScopeNotRegistered, ScopeRegistryConflict


class SQLiteScopeRegistry:
    """Crash-durable scope hierarchy with one SQLite authority.

    Scope registration is idempotent for the same parent and immutable for a
    different parent.  Every operation opens and closes its own connection so
    a process restart cannot retain a locked handle.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path, *, timeout_seconds: float = 30.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds
        with self._connection() as conn:
            self._ensure_schema(conn)
            conn.execute(
                "INSERT OR IGNORE INTO scopes(scope_key,kind,scope_id,parent_key) VALUES(?,?,?,NULL)",
                (PLATFORM_SCOPE.key, PLATFORM_SCOPE.kind.value, PLATFORM_SCOPE.scope_id),
            )

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.path, timeout=self.timeout_seconds, isolation_level=None)
        try:
            conn.execute(f"PRAGMA busy_timeout={max(1, int(self.timeout_seconds * 1000))}")
            retry_until_deadline(
                lambda: conn.execute("PRAGMA journal_mode=WAL"),
                should_retry=lambda exc: isinstance(exc, sqlite3.OperationalError)
                and "locked" in str(exc).lower(),
                timeout_seconds=self.timeout_seconds,
            )
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE IF NOT EXISTS scope_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scopes(
                scope_key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                parent_key TEXT REFERENCES scopes(scope_key),
                UNIQUE(kind, scope_id)
            )
            """
        )
        row = conn.execute("SELECT value FROM scope_meta WHERE key='schema_version'").fetchone()
        if row is None:
            conn.execute("INSERT INTO scope_meta(key,value) VALUES('schema_version',?)", (str(self.SCHEMA_VERSION),))
        elif int(row[0]) != self.SCHEMA_VERSION:
            raise RuntimeError("unsupported SQLiteScopeRegistry schema")

    @staticmethod
    def _decode(row: tuple[object, ...]) -> tuple[ScopeIdentity, ScopeIdentity | None]:
        scope = ScopeIdentity(ScopeKind(str(row[1])), str(row[2]))
        parent_key = row[3]
        if parent_key is None:
            return scope, None
        parent_kind, parent_id = str(parent_key).split(":", 1)
        return scope, ScopeIdentity(ScopeKind(parent_kind), parent_id)

    def register(self, scope: ScopeIdentity, parent: ScopeIdentity | None) -> None:
        if scope.kind is ScopeKind.PLATFORM:
            if scope != PLATFORM_SCOPE or parent is not None:
                raise ScopeRegistryConflict("platform scope has one fixed root identity")
        elif parent is None:
            raise ScopeRegistryConflict("non-platform scope requires explicit parent")
        elif parent.kind is not scope.expected_parent_kind:
            raise ScopeRegistryConflict(
                f"invalid scope parent: {scope.kind.value} requires {scope.expected_parent_kind.value}"
            )
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._ensure_schema(conn)
            if parent is not None:
                parent_row = conn.execute("SELECT 1 FROM scopes WHERE scope_key=?", (parent.key,)).fetchone()
                if parent_row is None:
                    conn.rollback()
                    raise ScopeNotRegistered(parent.key)
            row = conn.execute(
                "SELECT kind,scope_id,parent_key FROM scopes WHERE scope_key=?", (scope.key,)
            ).fetchone()
            parent_key = None if parent is None else parent.key
            if row is not None:
                existing_parent = row[2]
                if existing_parent != parent_key:
                    conn.rollback()
                    raise ScopeRegistryConflict(f"scope parent already fixed: {scope.key}")
                conn.commit()
                return
            conn.execute(
                "INSERT INTO scopes(scope_key,kind,scope_id,parent_key) VALUES(?,?,?,?)",
                (scope.key, scope.kind.value, scope.scope_id, parent_key),
            )
            conn.commit()

    def parent(self, scope: ScopeIdentity) -> ScopeIdentity | None:
        with self._connection() as conn:
            row = conn.execute("SELECT kind,scope_id,parent_key FROM scopes WHERE scope_key=?", (scope.key,)).fetchone()
        if row is None:
            raise ScopeNotRegistered(scope.key)
        return self._decode((scope.key, *row))[1]

    def ancestry(self, scope: ScopeIdentity) -> tuple[ScopeIdentity, ...]:
        """Resolve leaf-to-root ancestry in one SQLite round-trip.

        The recursive CTE keeps cycle detection inside the same consistent read
        snapshot. This avoids opening one WAL connection per hierarchy level and
        prevents ancestry from observing a mixed hierarchy across concurrent writes.
        """

        with self._connection() as conn:
            rows = conn.execute(
                """
                WITH RECURSIVE ancestry(
                    scope_key, kind, scope_id, parent_key, depth, path, cycle
                ) AS (
                    SELECT scope_key, kind, scope_id, parent_key, 0,
                           '|' || scope_key || '|', 0
                    FROM scopes WHERE scope_key=?
                    UNION ALL
                    SELECT s.scope_key, s.kind, s.scope_id, s.parent_key, a.depth + 1,
                           a.path || s.scope_key || '|',
                           CASE WHEN instr(a.path, '|' || s.scope_key || '|') > 0 THEN 1 ELSE 0 END
                    FROM scopes AS s
                    JOIN ancestry AS a ON s.scope_key = a.parent_key
                    WHERE a.cycle = 0
                )
                SELECT scope_key, kind, scope_id, parent_key, depth, cycle
                FROM ancestry
                ORDER BY depth ASC
                """,
                (scope.key,),
            ).fetchall()
        if not rows:
            raise ScopeNotRegistered(scope.key)
        if any(int(row[5]) for row in rows):
            repeated = next(str(row[0]) for row in rows if int(row[5]))
            raise ScopeRegistryConflict(f"scope cycle detected at {repeated}")
        last_parent = rows[-1][3]
        if last_parent is not None:
            raise ScopeNotRegistered(str(last_parent))
        return tuple(
            ScopeIdentity(ScopeKind(str(row[1])), str(row[2]))
            for row in rows
        )

    def children(self, scope: ScopeIdentity) -> tuple[ScopeIdentity, ...]:
        if not self.contains(scope):
            raise ScopeNotRegistered(scope.key)
        with self._connection() as conn:
            rows = conn.execute("SELECT kind,scope_id FROM scopes WHERE parent_key=?", (scope.key,)).fetchall()
        return tuple(sorted((ScopeIdentity(ScopeKind(str(row[0])), str(row[1])) for row in rows), key=lambda item: item.key))

    def contains(self, scope: ScopeIdentity) -> bool:
        with self._connection() as conn:
            return conn.execute("SELECT 1 FROM scopes WHERE scope_key=?", (scope.key,)).fetchone() is not None


__all__ = ["SQLiteScopeRegistry"]
