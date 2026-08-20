from __future__ import annotations

from research_platform.experimentation.experiment.api import ExperimentSpec
from research_platform.experimentation.run.identity.api import RunIdentity
from research_platform.participant.core.api import ParticipantSessionBinding
from research_platform.participant.core.api.runtime_ports import ParticipantSessionLifecyclePort
from research_platform.platform.kernel import ExecutionContext, OperationResult

from ..api import RunCycleExecutorPort, RunSessionPort
from .closer import RunCloser
from .session import RunSession


class DefaultRunSessionFactory:
    """Default Lifecycle implementation for constructing an open run session."""

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
    ) -> RunSessionPort:
        closer = RunCloser(
            spec=spec,
            identity=identity,
            participant_sessions=participant_sessions,
            lifecycle=participant_lifecycle,
        )
        return RunSession(
            spec=spec,
            identity=identity,
            cycle_executor=cycle_executor,
            closer=closer,
            open_operations=open_operations,
            initial_context=initial_context,
        )


__all__ = ["DefaultRunSessionFactory"]
