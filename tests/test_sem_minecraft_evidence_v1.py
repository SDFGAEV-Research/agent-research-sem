from __future__ import annotations

from dataclasses import dataclass

import pytest

from projects.sem_paper.composition.minecraft_evidence import (
    MinecraftEvidenceAdapter,
    MinecraftEvidenceAdmissionError,
    MinecraftEvidenceChannel,
    SEMMinecraftEvidenceIngestor,
)
from projects.sem_paper.method.self_evolving_memory.evidence_audit import AuditEvidence
from research_platform.environment.minecraft.api import MinecraftObservationEvent
from research_platform.environment.runtime.api import Observation
from research_platform.platform.kernel import ExecutionContext


@dataclass
class _Method:
    rows: list[tuple[object, ExecutionContext]]

    def ingest(self, evidence: object, context: ExecutionContext) -> None:
        self.rows.append((evidence, context))


@dataclass
class _Audit:
    rows: list[AuditEvidence]

    def append(self, row: AuditEvidence) -> None:
        self.rows.append(row)


def test_mc_adapter_preserves_grounded_state_and_stable_identity() -> None:
    event = MinecraftObservationEvent(
        "self_snapshot",
        {
            "username": "bot",
            "position": {"x": 1, "y": 2, "z": 3},
            "health": 20,
            "inventory": [{"name": "oak_log", "count": 2}],
        },
        sequence=7,
        timestamp_ms=100,
    )
    first = MinecraftEvidenceAdapter().admit(event)[0]
    second = MinecraftEvidenceAdapter().admit(event)[0]

    assert first.channel is MinecraftEvidenceChannel.MEMORY
    assert first.event_type == "WORLD_OBSERVATION"
    assert first.evidence_id == second.evidence_id
    assert first.payload["entity"] == "player:bot"
    assert first.payload["position"] == {"x": 1.0, "y": 2.0, "z": 3.0}
    assert "oak_log" in str(first.payload["state_text"])


def test_unverified_action_is_audit_only_and_verified_action_enters_memory() -> None:
    adapter = MinecraftEvidenceAdapter()
    failed = adapter.admit(
        MinecraftObservationEvent(
            "action_result",
            {"action": {"tool": "goto"}, "outcome": {"error": "blocked"}, "verified": False},
            sequence=1,
        )
    )[0]
    succeeded = adapter.admit(
        MinecraftObservationEvent(
            "action_result",
            {"action": {"tool": "wait"}, "outcome": {"waited_ms": 1}, "verified": True},
            sequence=2,
        )
    )[0]

    assert failed.channel is MinecraftEvidenceChannel.AUDIT
    assert succeeded.channel is MinecraftEvidenceChannel.MEMORY
    assert failed.payload["verified"] is False
    assert succeeded.payload["verified"] is True


def test_sem_ingestor_routes_observation_events_to_injected_authorities() -> None:
    method = _Method([])
    audit = _Audit([])
    ingestor = SEMMinecraftEvidenceIngestor(method, audit, MinecraftEvidenceAdapter())
    context = ExecutionContext("run", "trace", "span", task_id="task")
    observation = Observation(
        "minecraft:observation:1",
        "generation-1",
        {
            "events": [
                {
                    "kind": "self_snapshot",
                    "sequence": 1,
                    "timestamp_ms": 10,
                    "payload": {"username": "bot", "position": {"x": 0, "y": 0, "z": 0}},
                },
                {
                    "kind": "action_result",
                    "sequence": 2,
                    "timestamp_ms": 11,
                    "payload": {"verified": False, "action": "wait", "outcome": "timeout"},
                },
            ]
        },
    )

    memory_ids = ingestor.ingest_observation(observation, context)

    assert len(memory_ids) == 1
    assert len(method.rows) == 1
    assert method.rows[0][0]["event_type"] == "WORLD_OBSERVATION"
    assert len(audit.rows) == 1
    assert audit.rows[0].payload["event_type"] == "ACTION_RESULT"


def test_sem_ingestor_rejects_malformed_observation_events() -> None:
    ingestor = SEMMinecraftEvidenceIngestor(_Method([]), _Audit([]), MinecraftEvidenceAdapter())
    context = ExecutionContext("run", "trace", "span")
    observation = Observation("id", "generation", {"events": [{"kind": ""}]})

    with pytest.raises(MinecraftEvidenceAdmissionError, match="OBSERVATION_EVENT_INVALID"):
        ingestor.ingest_observation(observation, context)
