from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from research_platform.platform.kernel import ExecutionContext

from ..api.cognition import (
    AgentActionStep,
    AgentActionSummary,
    AgentCognitionError,
    AgentObservation,
    AgentStepReceipt,
)
from ..api.cognition_ports import (
    AgentActionExecutorPort,
    AgentEvidencePort,
    AgentMemoryPort,
    AgentObservationPort,
)


EventSink = Callable[..., None]
FailureSink = Callable[..., None]


@dataclass(frozen=True, slots=True)
class ActionPhaseResult:
    receipt: AgentStepReceipt
    observation: AgentObservation
    summary: AgentActionSummary


class CognitionActionPhase:
    """Own one action attempt from typed step to observed receipt."""

    def __init__(
        self,
        *,
        executor: AgentActionExecutorPort,
        observation: AgentObservationPort,
        evidence: AgentEvidencePort,
        memory: AgentMemoryPort,
        event: EventSink,
        failure: FailureSink,
    ) -> None:
        self._executor = executor
        self._observation = observation
        self._evidence = evidence
        self._memory = memory
        self._event = event
        self._failure = failure

    @staticmethod
    def _validate_receipt(step: AgentActionStep, receipt: AgentStepReceipt) -> None:
        if not isinstance(receipt, AgentStepReceipt):
            raise TypeError("agent action executor returned an invalid receipt")
        expected = (step.action_id, step.action_type, step.skill_id, step.sequence_id)
        actual = (receipt.action_id, receipt.action_type, receipt.skill_id, receipt.sequence_id)
        if actual != expected:
            raise ValueError("agent action receipt identity mismatch")

    def _observe_after_action(self, context: ExecutionContext) -> AgentObservation:
        try:
            value = self._observation.observe(context)
            if not isinstance(value, AgentObservation):
                raise TypeError("agent observation port returned an invalid observation")
            self._evidence.ingest(value, context)
            self._event(
                "AGENT_OBSERVATION",
                phase="post_action_observe",
                observation_id=value.observation_id,
                state_digest=value.state_digest,
                modality=value.modality,
            )
            return value
        except AgentCognitionError:
            raise
        except BaseException as exc:
            self._failure("AGENT_OBSERVATION_FAILED", str(exc), phase="post_action_observe")
            raise AgentCognitionError(
                "post_action_observe",
                "AGENT_OBSERVATION_FAILED",
                str(exc),
                cause=exc,
            ) from exc

    @staticmethod
    def _summary(step: AgentActionStep, receipt: AgentStepReceipt) -> AgentActionSummary:
        return AgentActionSummary(
            action_id=step.action_id,
            action_type=step.action_type,
            skill_id=step.skill_id,
            accepted=receipt.accepted,
            verified=receipt.verified,
            observation_digest="" if receipt.observation is None else receipt.observation.state_digest,
            rationale=step.rationale,
            payload=dict(step.payload),
        )

    def execute(
        self,
        step: AgentActionStep,
        context: ExecutionContext,
        *,
        completed_step: int,
    ) -> ActionPhaseResult:
        try:
            receipt = self._executor.execute(step, context)
            self._validate_receipt(step, receipt)
            if receipt.observation is not None:
                observation = receipt.observation
                self._evidence.ingest(observation, context)
            else:
                observation = self._observe_after_action(context)
            self._memory.record(receipt, context)
        except AgentCognitionError:
            raise
        except BaseException as exc:
            self._failure("AGENT_ACTION_FAILED", str(exc), phase="action")
            raise AgentCognitionError(
                "action", "AGENT_ACTION_FAILED", str(exc), cause=exc
            ) from exc

        self._event(
            "AGENT_ACTION_RECEIPT",
            level="INFO" if receipt.accepted else "WARNING",
            action_id=step.action_id,
            action_type=step.action_type,
            skill_id=step.skill_id,
            accepted=receipt.accepted,
            verified=receipt.verified,
            step=completed_step,
            observation_digest=observation.state_digest,
        )
        return ActionPhaseResult(
            receipt=receipt,
            observation=observation,
            summary=self._summary(step, receipt),
        )


__all__ = ["ActionPhaseResult", "CognitionActionPhase"]
