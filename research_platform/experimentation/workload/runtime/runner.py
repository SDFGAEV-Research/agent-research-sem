from __future__ import annotations

from collections import deque
from collections.abc import Mapping
import time
from dataclasses import replace

from research_platform.environment.runtime.api import (
    ActionRequest,
    ActionResult,
    Observation,
    action_request_digest,
    require_action_result_identity,
)
from research_platform.experimentation.experiment.api import ExperimentTaskSpec, FailureScope
from research_platform.participant.method.api import MethodSession, MethodTaskOutcome, RecallRequest
from research_platform.platform.kernel import ExecutionContext, JsonValue
from research_platform.platform.kernel.errors import describe_exception

from ..api import (
    WorkloadActionAdapterPort,
    WorkloadBoundaryPort,
    WorkloadCompletionPort,
    WorkloadDecision,
    WorkloadDiagnosticsPort,
    WorkloadEnvironmentPort,
    WorkloadEvidencePort,
    WorkloadFailurePolicyPort,
    WorkloadPlannerPort,
    WorkloadStatePort,
    WorkloadTaskResult,
    WorkloadTaskRunError,
)


class _DefaultActionAdapter:
    def action_id(self, task: ExperimentTaskSpec, step: int) -> str:
        return f"{task.task_id}:action:{step}"


class GenericWorkloadTaskRunner:
    """Reusable task loop for any environment implementing the platform seam.

    This runner owns sequencing and failure attribution only. State projection,
    action validation, completion predicates, and planner policy are injected
    adapters, so different environment backends share the same execution
    and evidence path.
    """

    def __init__(
        self,
        *,
        environment: WorkloadEnvironmentPort,
        method: MethodSession,
        evidence: WorkloadEvidencePort,
        planner: WorkloadPlannerPort,
        state: WorkloadStatePort,
        completion: WorkloadCompletionPort,
        failure_policy: WorkloadFailurePolicyPort,
        diagnostics: WorkloadDiagnosticsPort | None = None,
        boundary: WorkloadBoundaryPort | None = None,
        action_adapter: WorkloadActionAdapterPort | None = None,
        max_diagnostic_errors: int = 64,
        event_prefix: str = "WORKLOAD",
        metric_prefix: str = "workload",
    ) -> None:
        if max_diagnostic_errors <= 0:
            raise ValueError("max_diagnostic_errors must be positive")
        if not event_prefix.strip() or not metric_prefix.strip():
            raise ValueError("workload diagnostic prefixes must be non-empty")
        self.environment = environment
        self.method = method
        self.evidence = evidence
        self.planner = planner
        self.state = state
        self.completion = completion
        self.failure_policy = failure_policy
        self.diagnostics = diagnostics
        self.boundary = boundary
        self.action_adapter = action_adapter or _DefaultActionAdapter()
        self.event_prefix = event_prefix
        self.metric_prefix = metric_prefix
        self._diagnostic_errors: deque[str] = deque(maxlen=max_diagnostic_errors)

    @property
    def diagnostic_errors(self) -> tuple[str, ...]:
        return tuple(self._diagnostic_errors)

    def _record_diagnostic_error(self, operation: str, exc: BaseException) -> None:
        descriptor = describe_exception(exc)
        self._diagnostic_errors.append(
            f"{operation}:{descriptor.qualified_type}:{descriptor.safe_message}:{descriptor.error_digest}"
        )

    def _event(self, suffix: str, *, level: str = "DEBUG", **attributes: object) -> None:
        if self.diagnostics is None:
            return
        try:
            self.diagnostics.event(f"{self.event_prefix}_{suffix}", level=level, attributes=attributes)
        except Exception as exc:
            self._record_diagnostic_error("event", exc)

    def _metric(self, suffix: str, value: float, *, labels: Mapping[str, str] | None = None) -> None:
        if self.diagnostics is None:
            return
        try:
            self.diagnostics.metric(f"{self.metric_prefix}.{suffix}", value, labels=labels)
        except Exception as exc:
            self._record_diagnostic_error("metric", exc)

    def _failure(self, phase: str, code: str, exc: BaseException) -> None:
        if self.diagnostics is None:
            return
        try:
            self.diagnostics.failure(
                code,
                describe_exception(exc).safe_message,
                phase=phase,
                exception=exc,
            )
        except Exception as diagnostic_exc:
            self._record_diagnostic_error("failure", diagnostic_exc)

    def _raise(self, phase: str, code: str, exc: BaseException, *, scope: FailureScope) -> None:
        self._failure(phase, code, exc)
        raise WorkloadTaskRunError(
            phase,
            code,
            describe_exception(exc).safe_message,
            scope=scope,
        ) from exc

    def _raise_classified(self, phase: str, code: str, exc: BaseException) -> None:
        scope = self.failure_policy.scope(phase, exc)
        if not isinstance(scope, FailureScope):
            raise TypeError("workload failure policy returned an invalid FailureScope")
        self._raise(phase, code, exc, scope=scope)

    def _observation(self, observation: Observation, context: ExecutionContext) -> Mapping[str, JsonValue]:
        self.evidence.ingest_observation(observation, context)
        return dict(self.state.state(observation))

    def run(self, task: ExperimentTaskSpec, context: ExecutionContext) -> WorkloadTaskResult:
        self._diagnostic_errors.clear()
        started = time.monotonic()
        task_context = replace(context, task_id=task.task_id, decision_cycle_id=None)
        state: Mapping[str, JsonValue] = {}
        actions: list[Mapping[str, JsonValue]] = []
        cycles: list[Mapping[str, JsonValue]] = []
        memory_queries = 0
        planner_finished = False
        failure_reason = ""
        last_action: ActionResult | None = None
        metadata = {
            "task_id": task.task_id,
            "family": task.family,
            "objective": task.objective,
            "context": task.context,
            "lineage_id": task.lineage_id,
            "status": "STARTED",
        }
        self._event("TASK_START", level="INFO", task_id=task.task_id, family=task.family)

        try:
            task_event = None if self.boundary is None else self.boundary.begin(metadata, task_context)
            if task_event is not None:
                state = self._observation(task_event, task_context)
            initial = self.environment.observe(task_context)
            state = self._observation(initial, task_context)
        except Exception as exc:
            self._raise_classified("initial_observe", "WORKLOAD_INITIAL_OBSERVE_FAILED", exc)

        for step in range(task.max_steps):
            if self.completion.is_complete(
                task=task,
                state=state,
                planner_finished=planner_finished,
                last_action=last_action,
            ):
                break
            if time.monotonic() - started > task.max_seconds:
                failure_reason = "task_timeout"
                break
            cycle_id = f"{task.task_id}:cycle:{step}"
            cycle_context = replace(
                task_context,
                span_id=f"{task.task_id}:span:{step}",
                parent_span_id=task_context.span_id,
                decision_cycle_id=cycle_id,
            )
            cycle_started = time.monotonic()
            try:
                recalled = self.method.recall(RecallRequest(task.objective, cycle_context, limit=8))
                memory_queries += 1
                decision = self.planner.decide(
                    task=task,
                    context=cycle_context,
                    state=state,
                    memory_context=recalled.context_text,
                    step=step,
                    prior_actions=tuple(actions),
                )
                if not isinstance(decision, WorkloadDecision):
                    raise TypeError("workload planner returned an invalid decision")
            except Exception as exc:
                self._raise_classified("decision", "WORKLOAD_DECISION_FAILED", exc)

            if decision.completion_claim or decision.action_type == "finish":
                planner_finished = True
                actions.append({
                    "action_type": decision.action_type,
                    "payload": dict(decision.payload),
                    "rationale": decision.rationale,
                    "completion_claim": decision.completion_claim,
                    "decision_cycle_id": cycle_id,
                })
                cycles.append({
                    "decision_cycle_id": cycle_id,
                    "step": step,
                    "action_type": decision.action_type,
                    "cycle_duration_s": time.monotonic() - cycle_started,
                })
                break

            action_started = time.monotonic()
            action_id = self.action_adapter.action_id(task, step)
            request = ActionRequest(action_id, decision.action_type, dict(decision.payload), cycle_context)
            request_digest = action_request_digest(request)
            self._event(
                "ACTION_STARTED",
                task_id=task.task_id,
                step=step,
                action_id=action_id,
                action_type=decision.action_type,
                action_request_digest=request_digest,
                decision_cycle_id=cycle_id,
            )
            try:
                result = require_action_result_identity(
                    request,
                    self.environment.act(request),
                    source="workload environment",
                )
                last_action = result
                if result.observation is not None:
                    state = self._observation(result.observation, cycle_context)
            except Exception as exc:
                self._event(
                    "ACTION_FINISHED",
                    level="ERROR",
                    task_id=task.task_id,
                    step=step,
                    action_id=action_id,
                    action_type=decision.action_type,
                    action_request_digest=request_digest,
                    decision_cycle_id=cycle_id,
                    accepted=False,
                    verified=None,
                    duration_s=time.monotonic() - action_started,
                    observation_id=None,
                    observation_generation=None,
                    effect_id=None,
                    failure_type=type(exc).__name__,
                )
                self._raise_classified("action", "WORKLOAD_ACTION_FAILED", exc)
            action_duration = time.monotonic() - action_started
            verified = result.diagnostics.get("verified") if isinstance(result.diagnostics, Mapping) else None
            self._event(
                "ACTION_FINISHED",
                level="INFO" if result.accepted else "WARNING",
                task_id=task.task_id,
                step=step,
                action_id=action_id,
                action_type=decision.action_type,
                action_request_digest=request_digest,
                decision_cycle_id=cycle_id,
                accepted=result.accepted,
                verified=verified if isinstance(verified, bool) else None,
                duration_s=action_duration,
                observation_id=None if result.observation is None else result.observation.observation_id,
                observation_generation=None if result.observation is None else result.observation.generation,
                effect_id=None if result.effect is None else result.effect.effect_id,
            )
            actions.append({
                "action_id": action_id,
                "action_type": decision.action_type,
                "payload": dict(decision.payload),
                "accepted": result.accepted,
                "verified": verified if isinstance(verified, bool) else None,
                "rationale": decision.rationale,
                "decision_cycle_id": cycle_id,
            })
            cycles.append({
                "decision_cycle_id": cycle_id,
                "step": step,
                "action_type": decision.action_type,
                "accepted": result.accepted,
                "verified": verified if isinstance(verified, bool) else None,
                "action_duration_s": action_duration,
                "cycle_duration_s": time.monotonic() - cycle_started,
                "action_request_digest": request_digest,
            })
            self._metric(
                "action_latency_s",
                action_duration,
                labels={"family": task.family, "action": decision.action_type},
            )
            self._event("TASK_ACTION", task_id=task.task_id, step=step, action_type=decision.action_type, verified=verified)

        if time.monotonic() - started >= task.max_seconds:
            failure_reason = failure_reason or "task_timeout"
        success = self.completion.is_complete(
            task=task,
            state=state,
            planner_finished=planner_finished,
            last_action=last_action,
        ) if not failure_reason else False
        if not success and not failure_reason:
            failure_reason = "completion_predicate_not_satisfied"

        utility = self.completion.utility(task=task, success=success, state=state)
        try:
            completion = self.method.task_completed(
                MethodTaskOutcome(
                    task_id=task.task_id,
                    family=task.family,
                    lineage_id=task.lineage_id,
                    success=success,
                    utility=utility,
                    steps=len(actions),
                    failure_reason=failure_reason,
                    memory_queries=memory_queries,
                ),
                task_context,
            )
        except Exception as exc:
            self._raise_classified("task_completion", "WORKLOAD_TASK_COMPLETION_FAILED", exc)

        try:
            end_event = None if self.boundary is None else self.boundary.end(
                {**metadata, "status": "SUCCEEDED" if success else "FAILED", "failure_reason": failure_reason},
                task_context,
            )
            if end_event is not None:
                self.evidence.ingest_observation(end_event, task_context)
        except Exception as exc:
            self._raise_classified("task_end", "WORKLOAD_TASK_END_FAILED", exc)

        duration = time.monotonic() - started
        self._metric("duration_s", duration, labels={"family": task.family, "result": "success" if success else "failure"})
        self._event(
            "TASK_END",
            level="INFO" if success else "WARNING",
            task_id=task.task_id,
            success=success,
            steps=len(actions),
            failure_reason=failure_reason,
        )
        return WorkloadTaskResult(
            task_id=task.task_id,
            family=task.family,
            lineage_id=task.lineage_id,
            success=success,
            utility=utility,
            steps=len(actions),
            duration_s=duration,
            failure_reason=failure_reason,
            memory_queries=memory_queries,
            planner_actions=tuple(actions),
            decision_cycles=tuple(cycles),
            completion_receipt=completion,
            failure_scope=FailureScope.TASK.value,
            diagnostics={"diagnostic_sink_errors": self.diagnostic_errors} if self.diagnostic_errors else {},
        )


__all__ = ["GenericWorkloadTaskRunner"]
