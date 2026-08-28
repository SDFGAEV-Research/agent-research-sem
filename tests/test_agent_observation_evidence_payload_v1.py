import pytest

from research_platform.participant.agent.api import AgentObservation


def test_agent_observation_preserves_evidence_payload_without_mixing_it_into_state():
    state = {"position": [1, 2, 3], "ready": True}
    evidence = {"events": [{"kind": "observation", "sequence": 1}]}
    observation = AgentObservation(
        observation_id="obs-1",
        generation="env-1",
        state=state,
        evidence_payload=evidence,
    )

    assert observation.state == state
    assert observation.evidence_payload == evidence
    assert "events" not in observation.state
    assert observation.state_digest


def test_agent_observation_rejects_non_mapping_evidence_payload():
    with pytest.raises(ValueError, match="evidence payload must be a mapping"):
        AgentObservation(
            observation_id="obs-1",
            generation="env-1",
            state={},
            evidence_payload=["invalid"],  # type: ignore[arg-type]
        )
