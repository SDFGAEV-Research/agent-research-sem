from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3

from research_platform.data.fact.api import (
    DurableFact,
    DurableFactConflict,
    DurableFactCorruptionError,
    DurableFactNotFound,
    DurableFactReceipt,
    FactCriticality,
)
from research_platform.data._canonical import canonical_digest, canonical_text


class SQLiteDurableFactStore:
    """Append-only durable fact authority with immutable fact identity."""

    def __init__(self, path: str | Path, *, timeout_seconds: float = 30.0) -> None:
        self.path = Path(path).expanduser().resolve()
        self.timeout_seconds = timeout_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS durable_facts(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_id TEXT NOT NULL UNIQUE,
                    fact_type TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    criticality TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    artifact_refs_json TEXT NOT NULL,
                    state_refs_json TEXT NOT NULL,
                    record_sha256 TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_durable_facts_type_sequence
                ON durable_facts(fact_type,sequence);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=self.timeout_seconds, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute(f"PRAGMA busy_timeout={int(self.timeout_seconds * 1000)}")
        return db

    @staticmethod
    def _document(fact: DurableFact) -> dict[str, object]:
        return {
            "fact_id": fact.fact_id,
            "fact_type": fact.fact_type,
            "schema_version": fact.schema_version,
            "criticality": fact.criticality.value,
            "payload": dict(fact.payload),
            "artifact_refs": fact.artifact_refs,
            "state_refs": fact.state_refs,
        }

    @classmethod
    def _digest(cls, fact: DurableFact) -> str:
        return canonical_digest(cls._document(fact))

    @classmethod
    def _encoded(cls, fact: DurableFact) -> tuple[str, str, str]:
        return (
            canonical_text(dict(fact.payload)),
            json.dumps(fact.artifact_refs, ensure_ascii=False, separators=(",", ":")),
            json.dumps(fact.state_refs, ensure_ascii=False, separators=(",", ":")),
        )

    @staticmethod
    def _decode(row: tuple[object, ...]) -> DurableFact:
        try:
            payload = json.loads(str(row[5]))
            artifact_refs = json.loads(str(row[6]))
            state_refs = json.loads(str(row[7]))
            if not isinstance(payload, dict) or not isinstance(artifact_refs, list) or not isinstance(state_refs, list):
                raise TypeError("durable fact JSON fields have invalid shape")
            if any(not isinstance(value, str) for value in artifact_refs):
                raise TypeError("durable fact artifact refs must be strings")
            if any(not isinstance(value, str) for value in state_refs):
                raise TypeError("durable fact state refs must be strings")
            return DurableFact(
                fact_id=str(row[1]),
                fact_type=str(row[2]),
                schema_version=str(row[3]),
                criticality=FactCriticality(str(row[4])),
                payload=payload,
                artifact_refs=tuple(artifact_refs),
                state_refs=tuple(state_refs),
            )
        except (IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DurableFactCorruptionError("durable fact record cannot be decoded") from exc

    def append(self, fact: DurableFact) -> DurableFactReceipt:
        record_sha256 = self._digest(fact)
        payload_json, artifact_refs_json, state_refs_json = self._encoded(fact)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT sequence,fact_id,fact_type,schema_version,criticality,payload_json,"
                    "artifact_refs_json,state_refs_json,record_sha256 FROM durable_facts WHERE fact_id=?",
                    (fact.fact_id,),
                ).fetchone()
                if row is not None:
                    current = self._decode(row)
                    if current != fact or str(row[8]) != record_sha256:
                        raise DurableFactConflict(fact.fact_id)
                    db.execute("COMMIT")
                    return DurableFactReceipt(fact.fact_id, int(row[0]), record_sha256)
                cursor = db.execute(
                    "INSERT INTO durable_facts(fact_id,fact_type,schema_version,criticality,payload_json,"
                    "artifact_refs_json,state_refs_json,record_sha256) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        fact.fact_id,
                        fact.fact_type,
                        fact.schema_version,
                        fact.criticality.value,
                        payload_json,
                        artifact_refs_json,
                        state_refs_json,
                        record_sha256,
                    ),
                )
                sequence = int(cursor.lastrowid)
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return DurableFactReceipt(fact.fact_id, sequence, record_sha256)

    def get(self, fact_id: str) -> DurableFact:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT sequence,fact_id,fact_type,schema_version,criticality,payload_json,"
                "artifact_refs_json,state_refs_json,record_sha256 FROM durable_facts WHERE fact_id=?",
                (fact_id,),
            ).fetchone()
        if row is None:
            raise DurableFactNotFound(fact_id)
        fact = self._decode(row)
        if self._digest(fact) != str(row[8]):
            raise DurableFactCorruptionError(f"durable fact integrity mismatch: {fact_id}")
        return fact

    def count(self) -> int:
        with closing(self._connect()) as db:
            row = db.execute("SELECT COUNT(*) FROM durable_facts").fetchone()
        return int(row[0])


__all__ = ["SQLiteDurableFactStore"]
