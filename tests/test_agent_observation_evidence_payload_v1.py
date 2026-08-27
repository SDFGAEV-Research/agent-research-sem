from __future__ import annotations

from types import SimpleNamespace

from projects.sem_paper.composition.minecraft_agent import SemPaperCognitionEvidenceAdapter
from research_platform.environment.api import Observation
from research_platform.environment.minecraft.composition.agent import MinecraftAgentObservationPort
from research_platform.participant.agent.api import AgentObservation
from research_platform.participant.agent.runtime.vision import (
    VisionFrame,
    VisionInterpretation,
    VisionObservationProjector,
)
from research_platform.platform.kernel import ExecutionContext


class _Session:
    def observe(self, context):
        del context
        return Observation(
            "raw-1",
            "world-g1",
            {"state": {"health": 20}, "events": [{"kind": "spawn", "payload": {}}]},
            ("artifact:world",),
        )


def test_minecraft_agent_observation_preserves_environment_evidence_payload() -> None:
    observation = MinecraftAgentObservationPort(_Session()).observe(object())

    assert observation.state["health"] == 20
    assert observation.evidence_payload["events"][0]["kind"] == "spawn"
    assert observation.artifact_refs == ("artifact:world",)


def test_vision_projection_preserves_nonvisual_evidence_payload() -> None:
    observation = AgentObservation(
        "agent-1",
        "world-g1",
        {"health": 20},
        evidence_payload={"events": [{"kind": "spawn", "payload": {}}]},
    )
    projected = VisionObservationProjector().project(
        observation,
        VisionFrame("frame-1", "world-g1", "artifact:frame", 640, 480),
        VisionInterpretation("frame-1", ("tree",), "tree ahead", 0.9, ("evidence:vision",)),
    )

    assert projected.evidence_payload == observation.evidence_payload


class _Evidence:
    def __init__(self) -> None:
        self.payload = None

    def ingest_observation(self, observation, context):
        del context
        self.payload = observation.payload
        return ()


def test_sem_cognition_adapter_forwards_agent_evidence_payload() -> None:
    evidence = _Evidence()
    adapter = SemPaperCognitionEvidenceAdapter(evidence)
    observation = AgentObservation(
        "agent-2",
        "world-g1",
        {"health": 20},
        evidence_payload={"state": {"health": 20}, "events": [{"kind": "spawn", "payload": {}}]},
    )

    adapter.ingest(observation, ExecutionContext("run", "trace", "span"))

    assert evidence.payload["events"][0]["kind"] == "spawn"

