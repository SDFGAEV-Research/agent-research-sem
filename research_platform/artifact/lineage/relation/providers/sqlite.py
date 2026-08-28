from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from research_platform.artifact.lineage.relation.api import (
    ArtifactLineageConflict,
    ArtifactLineageCorruptionError,
    ArtifactLineageCycle,
    ArtifactLineageEdge,
)


class SQLiteArtifactLineageStore:
    """Append-only DAG of artifact provenance edges."""

    def __init__(self, path: str | Path, *, timeout_seconds: float = 30.0) -> None:
        self.path = Path(path).expanduser().resolve()
        self.timeout_seconds = timeout_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS artifact_lineage_edges(
                    edge_id TEXT PRIMARY KEY,
                    parent_artifact_id TEXT NOT NULL,
                    child_artifact_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_lineage_parent
                    ON artifact_lineage_edges(parent_artifact_id,child_artifact_id,edge_id);
                CREATE INDEX IF NOT EXISTS idx_lineage_child
                    ON artifact_lineage_edges(child_artifact_id,parent_artifact_id,edge_id);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=self.timeout_seconds, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute(f"PRAGMA busy_timeout={int(self.timeout_seconds * 1000)}")
        return db

    @staticmethod
    def _decode(row: tuple[object, ...]) -> ArtifactLineageEdge:
        try:
            refs = json.loads(str(row[4]))
            if not isinstance(refs, list):
                raise TypeError("evidence_refs_json must decode to a list")
            if any(not isinstance(value, str) for value in refs):
                raise TypeError("lineage evidence refs must be strings")
            edge = ArtifactLineageEdge(
                parent_artifact_id=str(row[1]),
                child_artifact_id=str(row[2]),
                relation_type=str(row[3]),
                evidence_refs=tuple(refs),
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ArtifactLineageCorruptionError("stored lineage edge cannot be decoded") from exc
        if edge.edge_id != str(row[0]):
            raise ArtifactLineageCorruptionError(
                f"stored lineage edge identity mismatch: {row[0]}"
            )
        return edge

    @staticmethod
    def _would_cycle(db: sqlite3.Connection, edge: ArtifactLineageEdge) -> bool:
        row = db.execute(
            """
            WITH RECURSIVE descendants(artifact_id) AS (
                SELECT child_artifact_id FROM artifact_lineage_edges WHERE parent_artifact_id=?
                UNION
                SELECT e.child_artifact_id
                FROM artifact_lineage_edges e
                JOIN descendants d ON e.parent_artifact_id=d.artifact_id
            )
            SELECT 1 FROM descendants WHERE artifact_id=? LIMIT 1
            """,
            (edge.child_artifact_id, edge.parent_artifact_id),
        ).fetchone()
        return row is not None

    def add(self, edge: ArtifactLineageEdge) -> ArtifactLineageEdge:
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT edge_id,parent_artifact_id,child_artifact_id,relation_type,evidence_refs_json "
                    "FROM artifact_lineage_edges WHERE edge_id=?",
                    (edge.edge_id,),
                ).fetchone()
                if row is not None:
                    current = self._decode(row)
                    if current != edge:
                        raise ArtifactLineageConflict(edge.edge_id)
                    db.execute("COMMIT")
                    return current
                if self._would_cycle(db, edge):
                    raise ArtifactLineageCycle(
                        f"lineage edge would create a cycle: {edge.parent_artifact_id} -> {edge.child_artifact_id}"
                    )
                db.execute(
                    "INSERT INTO artifact_lineage_edges VALUES(?,?,?,?,?)",
                    (
                        edge.edge_id,
                        edge.parent_artifact_id,
                        edge.child_artifact_id,
                        edge.relation_type,
                        json.dumps(edge.evidence_refs, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return edge

    def _query(self, column: str, value: str) -> tuple[ArtifactLineageEdge, ...]:
        if not value.strip():
            raise ValueError("artifact lineage lookup identity must be non-empty")
        if column not in {"parent_artifact_id", "child_artifact_id"}:
            raise ValueError("invalid lineage query column")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT edge_id,parent_artifact_id,child_artifact_id,relation_type,evidence_refs_json "
                f"FROM artifact_lineage_edges WHERE {column}=? ORDER BY edge_id",
                (value,),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def parents(self, child_artifact_id: str) -> tuple[ArtifactLineageEdge, ...]:
        return self._query("child_artifact_id", child_artifact_id)

    def children(self, parent_artifact_id: str) -> tuple[ArtifactLineageEdge, ...]:
        return self._query("parent_artifact_id", parent_artifact_id)


__all__ = ["SQLiteArtifactLineageStore"]
