from __future__ import annotations

from typing import Protocol

from research_platform.execution.decision.cycle_identity import DecisionCycleIdentity
from research_platform.execution.decision.cycle_result import DecisionCycleResult
from research_platform.experimentation.experiment.api import ExperimentSpec
from research_platform.participant.core.api import ParticipantSessionBinding
from research_platform.participant.core.api.runtime_ports import ParticipantSessionLifecyclePort
from research_platform.platform.kernel import ExecutionContext, OperationResult
from research_platform.experimentation.run.identity.api import RunIdentity

from .contracts import RunCleanupReport


class RunCycleExecutionPort(Protocol):
    """Lifecycle-facing view of one completed run cycle."""

    @property
    def result(self) -> DecisionCycleResult: ...

    @property
    def final_context(self) -> ExecutionContext: ...

    @property
    def checkpoint_id(self) -> str | None: ...


class RunCycleExecutorPort(Protocol):
    """Narrow behavior needed by a lifecycle-owned run session."""

    def execute(
        self,
        *,
        task: object,
        input_kind: str,
        input_payload: object,
        cycle_identity: DecisionCycleIdentity,
        previous_context: ExecutionContext | None,
    ) -> RunCycleExecutionPort: ...


class RunSessionPort(Protocol):
    """Stable lifecycle-owned surface for an open run."""

    @property
    def latest_checkpoint_id(self) -> str | None: ...

    @property
    def requires_recovery(self) -> bool: ...

    def execute(
        self,
        *,
        task: object,
        input_kind: str = "input",
        input_payload: object = None,
        cycle_identity: DecisionCycleIdentity,
    ) -> DecisionCycleResult: ...

    def close(self) -> RunCleanupReport: ...


class RunSessionFactoryPort(Protocol):
    """Parent Run authority asks Lifecycle to create its own session implementation."""

    def create(
        self,
        *,
        spec: ExperimentSpec,
        identity: RunIdentity,
        cycle_executor: RunCycleExecutorPort,
        participant_sessions: tuple[ParticipantSessionBinding, ...],
        participant_lifecycle: ParticipantSessionLifecyclePort,
        open_operations: tuple[OperationResult[object], ...],
        initial_context: ExecutionContext,
    ) -> RunSessionPort: ...


__all__ = [
    "RunCycleExecutionPort",
    "RunCycleExecutorPort",
    "RunSessionFactoryPort",
    "RunSessionPort",
]
