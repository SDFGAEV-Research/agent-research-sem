from __future__ import annotations

from dataclasses import dataclass, replace
import time
from typing import Callable

from research_platform.platform.kernel import ExecutionContext
from research_platform.platform.kernel.errors import describe_exception
from research_platform.platform.kernel.errors import redact_text

from ..api.cognition import (
    AgentActionSequence,
    AgentActionStep,
    AgentActionSummary,
    AgentCognitionError,
    AgentGoal,
    AgentLoopCheckpoint,
    AgentLoopResult,
    AgentLoopTerminationReason,
    AgentMemoryContext,
    AgentModeDecision,
    AgentModeDisposition,
    AgentObservation,
    AgentPlanningRequest,
    AgentSafetyDecision,
    AgentSafetyDisposition,
    AgentSkillRecord,
    AgentSkillSelection,
    AgentStepReceipt,
)
from ..api.cognition_ports import (
    AgentActionExecutorPort,
    AgentCompletionPort,
    AgentDiagnosticsPort,
    AgentEvidencePort,
    AgentMemoryPort,
    AgentObservationPort,
    AgentPlannerPort,
    AgentProgressPort,
    AgentReactiveModePort,
    AgentSafetySupervisorPort,
    AgentSkillCatalogPort,
    AgentSkillLibraryPort,
)


@dataclass(frozen=True, slots=True)
class _LoopCounters:
    step: int = 0
    plan_calls: int = 0
    no_progress_steps: int = 0
    same_action_runs: int = 0


class AgentCognitionLoop:
    """Durable, environment-neutral cognition loop.

    The loop deliberately owns only cognition sequencing.  It does not know
    environment actions, model providers, storage backends, or experiment
    semantics.  Those concerns enter through the typed ports and therefore
    remain replaceable while every decision, action, observation, and
    checkpoint is still attributable to one goal and one execution context.
    """

    def __init__(
        self,
        *,
        observation: AgentObservationPort,
        planner: AgentPlannerPort,
        skills: AgentSkillCatalogPort,
        executor: AgentActionExecutorPort,
        memory: AgentMemoryPort,
        safety: AgentSafetySupervisorPort,
        completion: AgentCompletionPort,
        evidence: AgentEvidencePort,
        progress: AgentProgressPort,
        skill_library: AgentSkillLibraryPort | None = None,
        reactive_modes: AgentReactiveModePort | None = None,
        diagnostics: AgentDiagnosticsPort | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.observation = observation
        self.planner = planner
        self.skills = skills
        self.executor = executor
        self.memory = memory
        self.safety = safety
        self.completion = completion
        self.evidence = evidence
        self.progress = progress
        self.skill_library = skill_library
        self.reactive_modes = reactive_modes
        self.diagnostics = diagnostics
        self.clock = clock
        self._diagnostic_failures: list[dict[str, object]] = []
        descriptions = self.skills.describe()
        if not descriptions:
            raise ValueError("agent cognition loop requires a non-empty skill catalog")
        ids = [description.skill_id for description in descriptions]
        if len(ids) != len(set(ids)):
            raise ValueError("agent cognition skill ids must be unique")

    def _event(self, name: str, *, level: str = "DEBUG", **attributes: object) -> None:
        if self.diagnostics is None:
            return
        normalized = {
            key: value
            for key, value in attributes.items()
            if value is None or isinstance(value, (str, int, float, bool))
        }
        try:
            self.diagnostics.event(name, level=level, attributes=normalized)
        except Exception as exc:
            # A diagnostic sink must never mask an environment or planner
            # result, but its failure is itself observable forensic evidence.
            self._record_diagnostic_failure("event", name, exc)
            return

    def _failure(self, code: str, message: str, *, phase: str) -> None:
        if self.diagnostics is None:
            return
        try:
            self.diagnostics.failure(code, redact_text(message), phase=phase)
        except Exception as exc:
            self._record_diagnostic_failure("failure", code, exc, phase=phase)
            return

    def _record_diagnostic_failure(
        self,
        operation: str,
        code: str,
        error: Exception,
        *,
        phase: str | None = None,
    ) -> None:
        self._diagnostic_failures.append(
            {
                "operation": operation,
                "code": code,
                "phase": phase,
                "error_type": type(error).__name__,
                "error_message": describe_exception(error).safe_message,
            }
        )

    def diagnostic_failures(self) -> tuple[dict[str, object], ...]:
        """Return auxiliary diagnostic-sink failures without masking primary work."""

        return tuple(dict(item) for item in self._diagnostic_failures)

    @staticmethod
    def _context(context: ExecutionContext, goal: AgentGoal, suffix: str) -> ExecutionContext:
        return replace(
            context,
            task_id=goal.goal_id,
            decision_cycle_id=f"{goal.goal_id}:{suffix}",
            component_id="participant.agent.cognition",
        )

    def _observe(self, context: ExecutionContext, *, phase: str) -> AgentObservation:
        try:
            value = self.observation.observe(context)
            if not isinstance(value, AgentObservation):
                raise TypeError("agent observation port returned an invalid observation")
            self.evidence.ingest(value, context)
            self._event(
                "AGENT_OBSERVATION",
                phase=phase,
                observation_id=value.observation_id,
                state_digest=value.state_digest,
                modality=value.modality,
            )
            return value
        except AgentCognitionError:
            raise
        except BaseException as exc:
            self._failure("AGENT_OBSERVATION_FAILED", str(exc), phase=phase)
            raise AgentCognitionError(phase, "AGENT_OBSERVATION_FAILED", str(exc), cause=exc) from exc

    @staticmethod
    def _summary(
        step: AgentActionStep,
        receipt: AgentStepReceipt,
    ) -> AgentActionSummary:
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

    def _checkpoint(
        self,
        *,
        goal: AgentGoal,
        session_id: str,
        counters: _LoopCounters,
        observation: AgentObservation,
        summaries: tuple[AgentActionSummary, ...],
        context: ExecutionContext,
    ) -> AgentLoopCheckpoint:
        checkpoint = AgentLoopCheckpoint(
            schema_version="agent-cognition-checkpoint.v1",
            session_id=session_id,
            goal_digest=goal.digest,
            step=counters.step,
            plan_calls=counters.plan_calls,
            no_progress_steps=counters.no_progress_steps,
            same_action_runs=counters.same_action_runs,
            last_observation_digest=observation.state_digest,
            action_summaries=summaries,
        )
        try:
            self.progress.persist(checkpoint, context)
        except BaseException as exc:
            self._failure("AGENT_CHECKPOINT_FAILED", str(exc), phase="checkpoint")
            raise AgentCognitionError("checkpoint", "AGENT_CHECKPOINT_FAILED", str(exc), cause=exc) from exc
        return checkpoint

    def _result(
        self,
        *,
        success: bool,
        termination: AgentLoopTerminationReason,
        counters: _LoopCounters,
        memory_queries: int,
        selected_skills: tuple[str, ...],
        receipts: tuple[AgentStepReceipt, ...],
        observation: AgentObservation,
        checkpoint: AgentLoopCheckpoint,
        failure_code: str = "",
        diagnostics: dict[str, object] | None = None,
    ) -> AgentLoopResult:
        combined_diagnostics: dict[str, object] = {
            "checkpoint_digest": checkpoint.digest,
            "last_observation_digest": observation.state_digest,
            "plan_calls": counters.plan_calls,
        }
        if diagnostics:
            combined_diagnostics.update(diagnostics)
        return AgentLoopResult(
            success=success,
            termination=termination,
            steps=counters.step,
            plan_calls=counters.plan_calls,
            memory_queries=memory_queries,
            selected_skills=selected_skills,
            action_receipts=receipts,
            final_observation=observation,
            checkpoint=checkpoint,
            failure_code=failure_code,
            diagnostics=combined_diagnostics,
        )

    def _record_skill(
        self,
        sequence: AgentActionSequence,
        receipts: tuple[AgentStepReceipt, ...],
        *,
        success: bool,
        context: ExecutionContext,
    ) -> None:
        if self.skill_library is None:
            return
        try:
            self.skill_library.record(sequence, receipts, success=success, context=context)
        except BaseException as exc:
            self._failure("AGENT_SKILL_LIBRARY_FAILED", str(exc), phase="memory")
            raise AgentCognitionError(
                "memory", "AGENT_SKILL_LIBRARY_FAILED", str(exc), cause=exc
            ) from exc

    def run(
        self,
        goal: AgentGoal,
        context: ExecutionContext,
        *,
        session_id: str | None = None,
        checkpoint: AgentLoopCheckpoint | None = None,
    ) -> AgentLoopResult:
        run_session_id = session_id or f"{context.run_id}:{goal.goal_id}"
        if checkpoint is not None and checkpoint.goal_digest != goal.digest:
            raise ValueError("agent cognition checkpoint belongs to another goal")
        if checkpoint is not None and checkpoint.session_id != run_session_id:
            raise ValueError("agent cognition checkpoint belongs to another session")
        counters = _LoopCounters(
            step=checkpoint.step if checkpoint is not None else 0,
            plan_calls=checkpoint.plan_calls if checkpoint is not None else 0,
            no_progress_steps=checkpoint.no_progress_steps if checkpoint is not None else 0,
            same_action_runs=checkpoint.same_action_runs if checkpoint is not None else 0,
        )
        summaries = list(checkpoint.action_summaries if checkpoint is not None else ())
        receipts: list[AgentStepReceipt] = []
        selected_skills: list[str] = [summary.skill_id for summary in summaries]
        memory_queries = 0
        invalid_completion_claims = 0
        started = self.clock()
        loop_context = self._context(context, goal, "observe:initial")
        observation = self._observe(loop_context, phase="initial_observe")
        last_action_type = summaries[-1].action_type if summaries else ""
        last_receipt: AgentStepReceipt | None = None

        while counters.step < goal.max_steps:
            if self.clock() - started > goal.max_seconds:
                checkpoint_value = self._checkpoint(
                    goal=goal, session_id=run_session_id, counters=counters,
                    observation=observation, summaries=tuple(summaries), context=loop_context,
                )
                return self._result(
                    success=False, termination=AgentLoopTerminationReason.TIMEOUT,
                    counters=counters, memory_queries=memory_queries,
                    selected_skills=tuple(selected_skills), receipts=tuple(receipts),
                    observation=observation, checkpoint=checkpoint_value,
                    failure_code="AGENT_LOOP_TIMEOUT",
                )

            try:
                if self.completion.is_complete(
                    goal, observation, planner_finished=False, last_receipt=last_receipt
                ):
                    checkpoint_value = self._checkpoint(
                        goal=goal, session_id=run_session_id, counters=counters,
                        observation=observation, summaries=tuple(summaries), context=loop_context,
                    )
                    return self._result(
                        success=True, termination=AgentLoopTerminationReason.COMPLETED,
                        counters=counters, memory_queries=memory_queries,
                        selected_skills=tuple(selected_skills), receipts=tuple(receipts),
                        observation=observation, checkpoint=checkpoint_value,
                    )
                memory = self.memory.recall(goal, observation, loop_context)
                memory_queries += 1
                if not isinstance(memory, AgentMemoryContext):
                    raise TypeError("agent memory port returned an invalid context")
                plan_context = self._context(context, goal, f"plan:{counters.plan_calls}")
                retrieved_skills: tuple[AgentSkillRecord, ...] = ()
                if self.skill_library is not None:
                    retrieved_skills = self.skill_library.search(
                        goal, observation, limit=8, context=plan_context
                    )
                    if not isinstance(retrieved_skills, tuple):
                        raise TypeError("agent skill library returned a non-tuple result")
                request = AgentPlanningRequest(
                    goal=goal,
                    observation=observation,
                    memory=memory,
                    step=counters.step,
                    plan_call=counters.plan_calls,
                    prior_actions=tuple(summaries),
                    context=plan_context,
                    available_skills=self.skills.describe(),
                    retrieved_skills=retrieved_skills,
                )
                selection = self.planner.plan(request)
                if not isinstance(selection, AgentSkillSelection):
                    raise TypeError("agent planner returned an invalid skill selection")
                sequence = self.skills.expand(
                    selection,
                    observation=observation,
                    context=plan_context,
                    sequence_id=f"{goal.goal_id}:sequence:{counters.plan_calls}",
                )
                if not isinstance(sequence, AgentActionSequence):
                    raise TypeError("agent skill catalog returned an invalid action sequence")
                decision = self.safety.review(
                    goal, observation, selection, sequence, plan_context
                )
                if not isinstance(decision, AgentSafetyDecision):
                    raise TypeError("agent safety supervisor returned an invalid decision")
                counters = replace(counters, plan_calls=counters.plan_calls + 1)
                self._event(
                    "AGENT_PLAN_SELECTED", level="INFO",
                    goal_id=goal.goal_id, skill_id=selection.skill_id,
                    sequence_id=sequence.sequence_id, plan_call=counters.plan_calls,
                    disposition=decision.disposition.value,
                )
                if counters.plan_calls > goal.max_replans + goal.max_steps:
                    raise AgentCognitionError(
                        "planning", "AGENT_REPLAN_LIMIT", "agent planner exceeded replan limit"
                    )
                if decision.disposition is AgentSafetyDisposition.ABORT:
                    checkpoint_value = self._checkpoint(
                        goal=goal, session_id=run_session_id, counters=counters,
                        observation=observation, summaries=tuple(summaries), context=plan_context,
                    )
                    return self._result(
                        success=False, termination=AgentLoopTerminationReason.SAFETY_ABORT,
                        counters=counters, memory_queries=memory_queries,
                        selected_skills=tuple(selected_skills), receipts=tuple(receipts),
                        observation=observation, checkpoint=checkpoint_value,
                        failure_code="AGENT_SAFETY_ABORT",
                    )
                if decision.disposition is AgentSafetyDisposition.REPLAN:
                    continue
                if decision.disposition is AgentSafetyDisposition.PREEMPT:
                    if decision.replacement is None:
                        raise AgentCognitionError("safety", "AGENT_INVALID_PREEMPT", "preempt decision has no replacement")
                    sequence = decision.replacement
                if self.reactive_modes is not None:
                    mode_decision = self.reactive_modes.review(
                        goal, observation, selection, sequence, plan_context
                    )
                    if not isinstance(mode_decision, (AgentModeDecision, type(None))):
                        raise TypeError("agent reactive mode port returned an invalid decision")
                    if mode_decision is not None:
                        self._event(
                            "AGENT_MODE_REVIEW",
                            level="INFO" if mode_decision.disposition is AgentModeDisposition.CONTINUE else "WARNING",
                            mode_id=mode_decision.mode_id,
                            disposition=mode_decision.disposition.value,
                        )
                        if mode_decision.disposition is AgentModeDisposition.ABORT:
                            checkpoint_value = self._checkpoint(
                                goal=goal, session_id=run_session_id, counters=counters,
                                observation=observation, summaries=tuple(summaries), context=plan_context,
                            )
                            return self._result(
                                success=False, termination=AgentLoopTerminationReason.INTERRUPTED,
                                counters=counters, memory_queries=memory_queries,
                                selected_skills=tuple(selected_skills), receipts=tuple(receipts),
                                observation=observation, checkpoint=checkpoint_value,
                                failure_code="AGENT_MODE_ABORT",
                            )
                        if mode_decision.disposition is AgentModeDisposition.REPLAN:
                            continue
                        if mode_decision.disposition is AgentModeDisposition.PREEMPT:
                            if mode_decision.replacement is None:
                                raise AgentCognitionError(
                                    "mode", "AGENT_INVALID_MODE_PREEMPT",
                                    "preempting mode decision has no replacement",
                                )
                            sequence = mode_decision.replacement
                if selection.completion_claim or sequence.completion_claim:
                    if self.completion.is_complete(
                        goal, observation, planner_finished=True, last_receipt=last_receipt
                    ):
                        checkpoint_value = self._checkpoint(
                            goal=goal, session_id=run_session_id, counters=counters,
                            observation=observation, summaries=tuple(summaries), context=plan_context,
                        )
                        return self._result(
                            success=True, termination=AgentLoopTerminationReason.COMPLETED,
                            counters=counters, memory_queries=memory_queries,
                            selected_skills=tuple(selected_skills), receipts=tuple(receipts),
                            observation=observation, checkpoint=checkpoint_value,
                        )
                    # A completion claim that is not grounded in the observed
                    # state is a replan signal, never a success.
                    invalid_completion_claims += 1
                    if invalid_completion_claims > goal.max_replans:
                        checkpoint_value = self._checkpoint(
                            goal=goal, session_id=run_session_id, counters=counters,
                            observation=observation, summaries=tuple(summaries), context=plan_context,
                        )
                        return self._result(
                            success=False, termination=AgentLoopTerminationReason.INVALID_PLAN,
                            counters=counters, memory_queries=memory_queries,
                            selected_skills=tuple(selected_skills), receipts=tuple(receipts),
                            observation=observation, checkpoint=checkpoint_value,
                            failure_code="AGENT_UNGROUNDED_COMPLETION_CLAIM",
                        )
                    continue
            except AgentCognitionError:
                raise
            except BaseException as exc:
                self._failure("AGENT_PLANNING_FAILED", str(exc), phase="planning")
                raise AgentCognitionError("planning", "AGENT_PLANNING_FAILED", str(exc), cause=exc) from exc

            if not sequence.steps:
                raise AgentCognitionError("planning", "AGENT_EMPTY_SEQUENCE", "non-completion sequence is empty")
            sequence_failed = False
            sequence_receipts: list[AgentStepReceipt] = []
            for step in sequence.steps:
                if counters.step >= goal.max_steps:
                    break
                action_context = self._context(context, goal, f"cycle:{counters.step}")
                previous_digest = observation.state_digest
                try:
                    receipt = self.executor.execute(step, action_context)
                    if not isinstance(receipt, AgentStepReceipt):
                        raise TypeError("agent action executor returned an invalid receipt")
                    if receipt.action_id != step.action_id or receipt.action_type != step.action_type:
                        raise ValueError("agent action receipt identity does not match the request")
                    if receipt.observation is not None:
                        observation = receipt.observation
                        self.evidence.ingest(observation, action_context)
                    else:
                        observation = self._observe(action_context, phase="post_action_observe")
                    self.memory.record(receipt, action_context)
                except AgentCognitionError:
                    raise
                except BaseException as exc:
                    self._failure("AGENT_ACTION_FAILED", str(exc), phase="action")
                    raise AgentCognitionError("action", "AGENT_ACTION_FAILED", str(exc), cause=exc) from exc
                receipts.append(receipt)
                sequence_receipts.append(receipt)
                summaries.append(self._summary(step, receipt))
                selected_skills.append(step.skill_id)
                counters = replace(counters, step=counters.step + 1)
                if receipt.observation is None or observation.state_digest == previous_digest:
                    next_no_progress = counters.no_progress_steps + 1
                else:
                    next_no_progress = 0
                next_same = counters.same_action_runs + 1 if step.action_type == last_action_type else 1
                counters = replace(counters, no_progress_steps=next_no_progress, same_action_runs=next_same)
                last_action_type = step.action_type
                last_receipt = receipt
                self._event(
                    "AGENT_ACTION_RECEIPT",
                    level="INFO" if receipt.accepted else "WARNING",
                    action_id=step.action_id, action_type=step.action_type,
                    skill_id=step.skill_id, accepted=receipt.accepted,
                    verified=receipt.verified, step=counters.step,
                    observation_digest=observation.state_digest,
                )
                checkpoint_value = self._checkpoint(
                    goal=goal, session_id=run_session_id, counters=counters,
                    observation=observation, summaries=tuple(summaries), context=action_context,
                )
                if self.completion.is_complete(
                    goal, observation, planner_finished=False, last_receipt=last_receipt
                ):
                    self._record_skill(
                        sequence, tuple(sequence_receipts), success=True, context=action_context
                    )
                    return self._result(
                        success=True, termination=AgentLoopTerminationReason.COMPLETED,
                        counters=counters, memory_queries=memory_queries,
                        selected_skills=tuple(selected_skills), receipts=tuple(receipts),
                        observation=observation, checkpoint=checkpoint_value,
                    )
                if not receipt.accepted:
                    sequence_failed = True
                    break
                if counters.no_progress_steps >= goal.no_progress_limit:
                    self._record_skill(
                        sequence, tuple(sequence_receipts), success=False, context=action_context
                    )
                    return self._result(
                        success=False, termination=AgentLoopTerminationReason.STALLED,
                        counters=counters, memory_queries=memory_queries,
                        selected_skills=tuple(selected_skills), receipts=tuple(receipts),
                        observation=observation, checkpoint=checkpoint_value,
                        failure_code="AGENT_NO_PROGRESS",
                    )
                if counters.same_action_runs >= goal.same_action_limit:
                    self._record_skill(
                        sequence, tuple(sequence_receipts), success=False, context=action_context
                    )
                    return self._result(
                        success=False, termination=AgentLoopTerminationReason.STALLED,
                        counters=counters, memory_queries=memory_queries,
                        selected_skills=tuple(selected_skills), receipts=tuple(receipts),
                        observation=observation, checkpoint=checkpoint_value,
                        failure_code="AGENT_REPEATED_ACTION",
                    )
            self._record_skill(
                sequence,
                tuple(sequence_receipts),
                success=not sequence_failed and self.completion.is_complete(
                    goal, observation, planner_finished=False, last_receipt=last_receipt
                ),
                context=loop_context,
            )
            if sequence_failed:
                # The failed receipt remains in the trajectory; the next plan
                # receives it through prior_actions and may choose recovery.
                continue

        checkpoint_value = self._checkpoint(
            goal=goal, session_id=run_session_id, counters=counters,
            observation=observation, summaries=tuple(summaries), context=loop_context,
        )
        return self._result(
            success=False, termination=AgentLoopTerminationReason.MAX_STEPS,
            counters=counters, memory_queries=memory_queries,
            selected_skills=tuple(selected_skills), receipts=tuple(receipts),
            observation=observation, checkpoint=checkpoint_value,
            failure_code="AGENT_MAX_STEPS",
        )


__all__ = ["AgentCognitionLoop"]
