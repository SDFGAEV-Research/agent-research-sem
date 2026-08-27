from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, TypeAlias

from research_platform.platform.kernel import ExecutionContext, canonical_digest


JsonValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)
JsonObject: TypeAlias = dict[str, JsonValue]


def _mapping(value: Mapping[str, JsonValue] | None = None) -> Mapping[str, JsonValue]:
    return dict(value or {})


class AgentLoopTerminationReason(StrEnum):
    COMPLETED = "completed"
    MAX_STEPS = "max_steps"
    TIMEOUT = "timeout"
    STALLED = "stalled"
    INTERRUPTED = "interrupted"
    SAFETY_ABORT = "safety_abort"
    PLANNER_FAILURE = "planner_failure"
    SKILL_FAILURE = "skill_failure"
    ACTION_FAILURE = "action_failure"
    INVALID_PLAN = "invalid_plan"


class AgentCognitionError(RuntimeError):
    """A cognition-loop phase failed with an explicit, stable phase/code."""

    def __init__(self, phase: str, code: str, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        if not phase.strip() or not code.strip():
            raise ValueError("agent cognition errors require non-empty phase and code")
        self.phase = phase
        self.code = code
        self.cause = cause


class AgentSafetyDisposition(StrEnum):
    ALLOW = "allow"
    PREEMPT = "preempt"
    REPLAN = "replan"
    ABORT = "abort"


class AgentModeDisposition(StrEnum):
    """Disposition emitted by a reactive mode controller."""

    CONTINUE = "continue"
    PREEMPT = "preempt"
    REPLAN = "replan"
    ABORT = "abort"


@dataclass(frozen=True, slots=True)
class AgentGoal:
    """Bounded autonomous objective; it carries no environment semantics."""

    goal_id: str
    objective: str
    context: Mapping[str, JsonValue] = field(default_factory=dict)
    max_steps: int = 32
    max_seconds: float = 300.0
    max_replans: int = 32
    no_progress_limit: int = 4
    same_action_limit: int = 3

    def __post_init__(self) -> None:
        if not self.goal_id.strip() or not self.objective.strip():
            raise ValueError("agent goal identity and objective are required")
        if not isinstance(self.context, Mapping):
            raise TypeError("agent goal context must be a mapping")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in (self.max_steps, self.max_replans, self.no_progress_limit, self.same_action_limit)
        ):
            raise ValueError("agent goal integer limits must be positive")
        if isinstance(self.max_seconds, bool) or self.max_seconds <= 0:
            raise ValueError("agent goal max_seconds must be positive")

    @property
    def digest(self) -> str:
        return canonical_digest(
            {
                "goal_id": self.goal_id,
                "objective": self.objective,
                "context": dict(self.context),
                "max_steps": self.max_steps,
                "max_seconds": self.max_seconds,
                "max_replans": self.max_replans,
                "no_progress_limit": self.no_progress_limit,
                "same_action_limit": self.same_action_limit,
            }
        )


@dataclass(frozen=True, slots=True)
class AgentObservation:
    observation_id: str
    generation: str
    state: Mapping[str, JsonValue]
    modality: str = "world"
    artifact_refs: tuple[str, ...] = ()
    state_digest: str = ""
    evidence_payload: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observation_id.strip() or not self.generation.strip():
            raise ValueError("agent observation identity is required")
        if not self.modality.strip() or not isinstance(self.state, Mapping):
            raise ValueError("agent observation modality/state is invalid")
        if not isinstance(self.evidence_payload, Mapping):
            raise ValueError("agent observation evidence payload must be a mapping")
        computed = canonical_digest(dict(self.state))
        if self.state_digest and self.state_digest != computed:
            raise ValueError("agent observation state digest mismatch")
        if not self.state_digest:
            object.__setattr__(self, "state_digest", computed)


@dataclass(frozen=True, slots=True)
class AgentMemoryContext:
    context_text: str
    generation: str
    artifacts: tuple[str, ...] = ()
    query_id: str = ""

    def __post_init__(self) -> None:
        if not self.generation.strip():
            raise ValueError("agent memory generation is required")


@dataclass(frozen=True, slots=True)
class AgentActionSummary:
    action_id: str
    action_type: str
    skill_id: str
    accepted: bool
    verified: bool | None
    observation_digest: str = ""
    rationale: str = ""
    payload: Mapping[str, JsonValue] = field(default_factory=dict)


def action_summary_payload(summary: AgentActionSummary) -> dict[str, JsonValue]:
    """Return the canonical, slot-safe representation used by checkpoints."""

    return {
        "action_id": summary.action_id,
        "action_type": summary.action_type,
        "skill_id": summary.skill_id,
        "accepted": summary.accepted,
        "verified": summary.verified,
        "observation_digest": summary.observation_digest,
        "rationale": summary.rationale,
        "payload": dict(summary.payload),
    }


@dataclass(frozen=True, slots=True)
class AgentPlanningRequest:
    goal: AgentGoal
    observation: AgentObservation
    memory: AgentMemoryContext
    step: int
    plan_call: int
    prior_actions: tuple[AgentActionSummary, ...]
    context: ExecutionContext
    available_skills: tuple[AgentSkillDescription, ...] = ()
    retrieved_skills: tuple[AgentSkillRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentSkillDescription:
    skill_id: str
    category: str
    description: str
    argument_contract: str
    mutates_world: bool
    supports_sequences: bool = True
    safety_class: str = "ordinary"

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.skill_id, self.category, self.description, self.argument_contract, self.safety_class)):
            raise ValueError("agent skill description text is required")


@dataclass(frozen=True, slots=True)
class AgentSkillSelection:
    skill_id: str
    arguments: Mapping[str, JsonValue] = field(default_factory=dict)
    completion_claim: bool = False
    rationale: str = ""
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.skill_id.strip() or not isinstance(self.arguments, Mapping):
            raise ValueError("agent skill selection is invalid")


@dataclass(frozen=True, slots=True)
class AgentSkillRecord:
    """Reusable typed skill recipe with provenance, never executable source."""

    skill_id: str
    version: str
    summary: str
    tags: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    recipe: tuple[tuple[str, Mapping[str, JsonValue]], ...] = ()
    success_count: int = 0
    failure_count: int = 0

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.skill_id, self.version, self.summary)):
            raise ValueError("agent skill record identity and summary are required")
        if min(self.success_count, self.failure_count) < 0:
            raise ValueError("agent skill record counters cannot be negative")
        if any(not action_type.strip() or not isinstance(payload, Mapping) for action_type, payload in self.recipe):
            raise ValueError("agent skill record recipe is invalid")


@dataclass(frozen=True, slots=True)
class AgentActionStep:
    action_id: str
    action_type: str
    payload: Mapping[str, JsonValue]
    skill_id: str
    sequence_id: str
    sequence_index: int
    interruptible: bool = True
    rationale: str = ""

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.action_id, self.action_type, self.skill_id, self.sequence_id)):
            raise ValueError("agent action step identity is required")
        if not isinstance(self.payload, Mapping) or self.sequence_index < 0:
            raise ValueError("agent action step payload/index is invalid")


@dataclass(frozen=True, slots=True)
class AgentActionSequence:
    sequence_id: str
    skill_id: str
    steps: tuple[AgentActionStep, ...]
    completion_claim: bool = False

    def __post_init__(self) -> None:
        if not self.sequence_id.strip() or not self.skill_id.strip():
            raise ValueError("agent action sequence identity is required")
        if not self.completion_claim and not self.steps:
            raise ValueError("non-completion skill sequence must contain an action")
        if any(step.sequence_id != self.sequence_id or step.skill_id != self.skill_id for step in self.steps):
            raise ValueError("agent action sequence step identity mismatch")
        if tuple(step.sequence_index for step in self.steps) != tuple(range(len(self.steps))):
            raise ValueError("agent action sequence indices must be contiguous")


@dataclass(frozen=True, slots=True)
class AgentSafetyDecision:
    disposition: AgentSafetyDisposition
    reason: str
    controller_id: str
    replacement: AgentActionSequence | None = None

    def __post_init__(self) -> None:
        if not self.reason.strip() or not self.controller_id.strip():
            raise ValueError("agent safety decision must identify reason/controller")
        if self.disposition is AgentSafetyDisposition.PREEMPT and self.replacement is None:
            raise ValueError("preempting safety decision requires a replacement sequence")


@dataclass(frozen=True, slots=True)
class AgentModeDecision:
    """Typed result of a higher-priority reactive mode review.

    A mode may interrupt a selected skill, but it may only replace it with an
    already-typed action sequence.  This preserves the useful part of a mode
    controller without allowing code injection or an action-ABI bypass.
    """

    mode_id: str
    disposition: AgentModeDisposition
    reason: str
    replacement: AgentActionSequence | None = None

    def __post_init__(self) -> None:
        if not self.mode_id.strip() or not self.reason.strip():
            raise ValueError("agent mode decision must identify mode and reason")
        if self.disposition is AgentModeDisposition.PREEMPT and self.replacement is None:
            raise ValueError("preempting mode decision requires a replacement sequence")


@dataclass(frozen=True, slots=True)
class AgentStepReceipt:
    action_id: str
    action_type: str
    skill_id: str
    sequence_id: str
    accepted: bool
    verified: bool | None
    observation: AgentObservation | None = None
    effect_id: str | None = None
    effect_certainty: str = "unknown"
    diagnostics: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.action_id, self.action_type, self.skill_id, self.sequence_id)):
            raise ValueError("agent step receipt identity is required")
        if self.effect_certainty not in {"confirmed", "rejected", "possible", "unknown"}:
            raise ValueError("agent step receipt effect certainty is invalid")


@dataclass(frozen=True, slots=True)
class AgentLoopCheckpoint:
    schema_version: str
    session_id: str
    goal_digest: str
    step: int
    plan_calls: int
    no_progress_steps: int
    same_action_runs: int
    last_observation_digest: str
    action_summaries: tuple[AgentActionSummary, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != "agent-cognition-checkpoint.v1":
            raise ValueError("unsupported agent cognition checkpoint schema")
        if not self.session_id.strip() or len(self.goal_digest) != 64:
            raise ValueError("agent cognition checkpoint identity is invalid")
        if min(self.step, self.plan_calls, self.no_progress_steps, self.same_action_runs) < 0:
            raise ValueError("agent cognition checkpoint counters cannot be negative")

    @property
    def digest(self) -> str:
        return canonical_digest({
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "goal_digest": self.goal_digest,
            "step": self.step,
            "plan_calls": self.plan_calls,
            "no_progress_steps": self.no_progress_steps,
            "same_action_runs": self.same_action_runs,
            "last_observation_digest": self.last_observation_digest,
            "action_summaries": [action_summary_payload(summary) for summary in self.action_summaries],
        })


@dataclass(frozen=True, slots=True)
class AgentLoopResult:
    success: bool
    termination: AgentLoopTerminationReason
    steps: int
    plan_calls: int
    memory_queries: int
    selected_skills: tuple[str, ...]
    action_receipts: tuple[AgentStepReceipt, ...]
    final_observation: AgentObservation
    checkpoint: AgentLoopCheckpoint
    failure_code: str = ""
    diagnostics: Mapping[str, JsonValue] = field(default_factory=dict)


__all__ = [
    "AgentActionSequence",
    "AgentActionStep",
    "AgentActionSummary",
    "AgentCognitionError",
    "AgentGoal",
    "AgentLoopCheckpoint",
    "AgentLoopResult",
    "AgentLoopTerminationReason",
    "AgentMemoryContext",
    "AgentModeDecision",
    "AgentModeDisposition",
    "AgentObservation",
    "AgentPlanningRequest",
    "AgentSafetyDecision",
    "AgentSafetyDisposition",
    "AgentSkillDescription",
    "AgentSkillRecord",
    "AgentSkillSelection",
    "AgentStepReceipt",
    "action_summary_payload",
    "JsonObject",
    "JsonValue",
]
