from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
import re
import time
from typing import Any, Mapping, Protocol

from research_platform.participant.method.api import MethodSession, RecallRequest
from research_platform.platform.kernel import ExecutionContext


@dataclass(frozen=True, slots=True)
class MinecraftSuccessSpec:
    kind: str
    params: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MinecraftTaskSpec:
    task_id: str
    family: str
    goal: str
    context: str = ""
    lineage_id: str = ""
    referenced_anchors: tuple[str, ...] = ()
    depends_on_task_ids: tuple[str, ...] = ()
    retry_of_task_id: str | None = None
    max_steps: int = 12
    max_seconds: float = 180.0
    success: MinecraftSuccessSpec = MinecraftSuccessSpec("planner_finish", {})
    script: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.goal.strip() or not self.family.strip():
            raise ValueError("Minecraft task identity, family and goal are required")
        if self.max_steps <= 0 or self.max_seconds <= 0:
            raise ValueError("Minecraft task limits must be positive")


def task_from_mapping(raw: Mapping[str, object]) -> MinecraftTaskSpec:
    success_raw = raw.get("success", {"kind": "planner_finish"})
    if isinstance(success_raw, str):
        success = MinecraftSuccessSpec(success_raw, {})
    elif isinstance(success_raw, Mapping):
        success = MinecraftSuccessSpec(
            str(success_raw.get("kind", "planner_finish")),
            {key: value for key, value in success_raw.items() if key != "kind"},
        )
    else:
        raise ValueError("Minecraft task success must be a string or mapping")
    raw_script = raw.get("script", ())
    if not isinstance(raw_script, (list, tuple)):
        raise ValueError("Minecraft task script must be a list or tuple")
    script: list[Mapping[str, object]] = []
    for value in raw_script:
        if not isinstance(value, Mapping):
            raise ValueError("Minecraft task script rows must be mappings")
        script.append(dict(value))
    return MinecraftTaskSpec(
        task_id=str(raw["task_id"]),
        family=str(raw.get("family", "mixed")),
        goal=str(raw["goal"]),
        context=str(raw.get("context", "")),
        lineage_id=str(raw.get("lineage_id", raw["task_id"])),
        referenced_anchors=tuple(str(value) for value in raw.get("referenced_anchors", ())),
        depends_on_task_ids=tuple(str(value) for value in raw.get("depends_on_task_ids", ())),
        retry_of_task_id=str(raw["retry_of_task_id"]) if raw.get("retry_of_task_id") else None,
        max_steps=int(raw.get("max_steps", 12)),
        max_seconds=float(raw.get("max_seconds", 180.0)),
        success=success,
        script=tuple(script),
    )


@dataclass(frozen=True, slots=True)
class MinecraftEnvironmentObservation:
    """Project-facing view produced by a composition adapter around MC Observation."""

    observation_id: str
    state: Mapping[str, object]
    payload: object


@dataclass(frozen=True, slots=True)
class MinecraftEnvironmentActionResult:
    accepted: bool
    verified: bool | None
    observation: MinecraftEnvironmentObservation | None
    payload: object = None
    diagnostics: Mapping[str, object] = field(default_factory=dict)


class MinecraftWorkloadEnvironmentPort(Protocol):
    def observe(self, context: ExecutionContext) -> MinecraftEnvironmentObservation: ...

    def act(
        self,
        action_id: str,
        action_type: str,
        payload: Mapping[str, object],
        context: ExecutionContext,
    ) -> MinecraftEnvironmentActionResult: ...


@dataclass(frozen=True, slots=True)
class MinecraftPlannerDecision:
    action_type: str
    payload: Mapping[str, object] = field(default_factory=dict)
    rationale: str = ""


class MinecraftPlannerPort(Protocol):
    def decide(
        self,
        *,
        task: MinecraftTaskSpec,
        context: ExecutionContext,
        state: Mapping[str, object],
        memory_context: str,
        step: int,
        prior_actions: tuple[Mapping[str, object], ...],
    ) -> MinecraftPlannerDecision: ...


class MinecraftEvidencePort(Protocol):
    def ingest_observation(self, observation: object, context: ExecutionContext) -> tuple[str, ...]: ...


class MinecraftWorkloadDiagnosticsPort(Protocol):
    def event(self, event: str, *, attributes: Mapping[str, object] | None = None, level: str = "DEBUG") -> None: ...

    def metric(self, name: str, value: float, *, labels: Mapping[str, str] | None = None) -> None: ...

    def failure(self, code: str, message: str, *, phase: str) -> None: ...


class MinecraftWorkloadFailure(RuntimeError):
    def __init__(self, phase: str, code: str, message: str) -> None:
        super().__init__(f"Minecraft workload phase {phase} failed [{code}]: {message}")
        self.phase = phase
        self.code = code


@dataclass(frozen=True, slots=True)
class MinecraftTaskRunResult:
    task_id: str
    family: str
    success: bool
    utility: float
    steps: int
    duration_s: float
    failure_reason: str = ""
    memory_queries: int = 0
    planner_actions: tuple[Mapping[str, object], ...] = ()
    decision_cycles: tuple[Mapping[str, object], ...] = ()
    completion_receipt: object | None = None
    diagnostics: Mapping[str, object] = field(default_factory=dict)


def _item_match(name: str, query: str) -> bool:
    if query.startswith("re:"):
        return re.search(query[3:], name) is not None
    return name == query or query in name


def evaluate_success(
    task: MinecraftTaskSpec,
    state: Mapping[str, object],
    *,
    planner_finished: bool,
) -> bool:
    kind = task.success.kind
    params = dict(task.success.params)
    if kind == "always":
        return True
    if kind == "planner_finish":
        return planner_finished and state.get("last_action_verified") is not False
    if kind == "last_action_verified":
        return state.get("last_action_verified") is True
    if kind == "inventory_min":
        inventory = state.get("inventory", {})
        if not isinstance(inventory, Mapping):
            return False
        query = str(params["item"])
        required = int(params.get("count", 1))
        return sum(int(value) for key, value in inventory.items() if _item_match(str(key), query)) >= required
    if kind == "near_anchor":
        anchors = state.get("anchors", {})
        position = state.get("position")
        anchor = anchors.get(str(params["anchor"])) if isinstance(anchors, Mapping) else None
        if not isinstance(anchor, Mapping) or not isinstance(position, Mapping):
            return False
        try:
            distance = math.sqrt(sum((float(position[key]) - float(anchor[key])) ** 2 for key in ("x", "y", "z")))
        except (KeyError, TypeError, ValueError):
            return False
        return distance <= float(params.get("radius", 3))
    if kind == "health_positive":
        try:
            return float(state["health"]) > 0
        except (KeyError, TypeError, ValueError):
            return False
    if kind == "observed_entity":
        entities = state.get("nearby_entities", ())
        if not isinstance(entities, (list, tuple)):
            return False
        query = str(params.get("entity", "")).lower()
        return any(
            query in " ".join(str(row.get(key, "")).lower() for key in ("name", "mob_type", "type", "username"))
            for row in entities
            if isinstance(row, Mapping)
        )
    raise ValueError(f"unknown Minecraft success kind: {kind}")


class ScriptedMinecraftPlanner:
    """Project workload adapter for deterministic baseline/smoke scripts."""

    def __init__(self, script: tuple[Mapping[str, object], ...]) -> None:
        self._script = script

    def decide(
        self,
        *,
        task: MinecraftTaskSpec,
        context: ExecutionContext,
        state: Mapping[str, object],
        memory_context: str,
        step: int,
        prior_actions: tuple[Mapping[str, object], ...],
    ) -> MinecraftPlannerDecision:
        del task, context, state, memory_context, prior_actions
        if step >= len(self._script):
            return MinecraftPlannerDecision("finish", {"reason": "script_exhausted"}, "scripted")
        row = self._script[step]
        action_type = str(row["tool"])
        payload = row.get("args", {})
        if not isinstance(payload, Mapping):
            raise ValueError("scripted Minecraft planner args must be a mapping")
        return MinecraftPlannerDecision(action_type, dict(payload), "scripted")


class MinecraftWorkloadRunner:
    """Paper workload loop over injected environment, method, evidence and planner ports."""

    def __init__(
        self,
        *,
        environment: MinecraftWorkloadEnvironmentPort,
        method: MethodSession,
        evidence: MinecraftEvidencePort,
        planner: MinecraftPlannerPort,
        diagnostics: MinecraftWorkloadDiagnosticsPort | None = None,
    ) -> None:
        self.environment = environment
        self.method = method
        self.evidence = evidence
        self.planner = planner
        self.diagnostics = diagnostics

    def _event(self, event: str, *, level: str = "DEBUG", **attributes: object) -> None:
        if self.diagnostics is None:
            return
        try:
            self.diagnostics.event(event, level=level, attributes=attributes)
        except Exception:
            return

    def _metric(self, name: str, value: float, *, labels: Mapping[str, str] | None = None) -> None:
        if self.diagnostics is None:
            return
        try:
            self.diagnostics.metric(name, value, labels=labels)
        except Exception:
            return

    def _failure(self, phase: str, code: str, exc: BaseException) -> None:
        if self.diagnostics is None:
            return
        try:
            self.diagnostics.failure(code, str(exc), phase=phase)
        except Exception:
            return

    def run(self, task: MinecraftTaskSpec, context: ExecutionContext) -> MinecraftTaskRunResult:
        started = time.monotonic()
        task_context = replace(context, task_id=task.task_id, decision_cycle_id=None)
        state: Mapping[str, object] = {}
        actions: list[Mapping[str, object]] = []
        cycles: list[Mapping[str, object]] = []
        memory_queries = 0
        planner_finished = False
        failure_reason = ""
        self._event("MC_TASK_START", level="INFO", task_id=task.task_id, family=task.family)

        try:
            initial = self.environment.observe(task_context)
            state = dict(initial.state)
            self.evidence.ingest_observation(initial, task_context)
        except Exception as exc:
            self._failure("initial_observe", "MC_WORKLOAD_INITIAL_OBSERVE_FAILED", exc)
            raise MinecraftWorkloadFailure("initial_observe", "MC_WORKLOAD_INITIAL_OBSERVE_FAILED", str(exc)) from exc

        for step in range(task.max_steps):
            if evaluate_success(task, state, planner_finished=planner_finished):
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
                memory_result = self.method.recall(RecallRequest(task.goal, cycle_context, limit=8))
                memory_queries += 1
                memory_context = memory_result.context_text
                decision = self.planner.decide(
                    task=task,
                    context=cycle_context,
                    state=state,
                    memory_context=memory_context,
                    step=step,
                    prior_actions=tuple(actions),
                )
            except Exception as exc:
                self._failure("decision", "MC_WORKLOAD_DECISION_FAILED", exc)
                raise MinecraftWorkloadFailure("decision", "MC_WORKLOAD_DECISION_FAILED", str(exc)) from exc

            if decision.action_type == "finish":
                planner_finished = True
                actions.append({"action_type": "finish", "payload": dict(decision.payload), "rationale": decision.rationale, "decision_cycle_id": cycle_id})
                cycles.append({"decision_cycle_id": cycle_id, "step": step, "action_type": "finish", "cycle_duration_s": time.monotonic() - cycle_started})
                break

            action_started = time.monotonic()
            action_id = f"{task.task_id}:action:{step}"
            try:
                result = self.environment.act(action_id, decision.action_type, dict(decision.payload), cycle_context)
                if result.observation is not None:
                    state = dict(result.observation.state)
                    self.evidence.ingest_observation(result.observation, cycle_context)
            except Exception as exc:
                self._failure("action", "MC_WORKLOAD_ACTION_FAILED", exc)
                raise MinecraftWorkloadFailure("action", "MC_WORKLOAD_ACTION_FAILED", str(exc)) from exc
            action_duration = time.monotonic() - action_started
            action_record = {
                "action_id": action_id,
                "action_type": decision.action_type,
                "payload": dict(decision.payload),
                "accepted": result.accepted,
                "verified": result.verified,
                "rationale": decision.rationale,
                "decision_cycle_id": cycle_id,
            }
            actions.append(action_record)
            cycles.append(
                {
                    "decision_cycle_id": cycle_id,
                    "step": step,
                    "action_type": decision.action_type,
                    "accepted": result.accepted,
                    "verified": result.verified,
                    "action_duration_s": action_duration,
                    "cycle_duration_s": time.monotonic() - cycle_started,
                }
            )
            self._metric("minecraft.task.action_latency_s", action_duration, labels={"family": task.family, "action": decision.action_type})
            self._event("MC_TASK_ACTION", task_id=task.task_id, step=step, action_type=decision.action_type, verified=result.verified)

        success = evaluate_success(task, state, planner_finished=planner_finished)
        if not success and not failure_reason:
            failure_reason = "success_predicate_not_satisfied"
        completion = None
        try:
            completion = self.method.task_completed(
                {"task_id": task.task_id, "family": task.family, "success": success, "failure_reason": failure_reason},
                task_context,
            )
        except Exception as exc:
            self._failure("task_completion", "MC_WORKLOAD_TASK_COMPLETION_FAILED", exc)
            raise MinecraftWorkloadFailure("task_completion", "MC_WORKLOAD_TASK_COMPLETION_FAILED", str(exc)) from exc

        duration = time.monotonic() - started
        self._metric("minecraft.task.duration_s", duration, labels={"family": task.family, "result": "success" if success else "failure"})
        self._event("MC_TASK_END", level="INFO" if success else "WARNING", task_id=task.task_id, success=success, steps=len(actions), failure_reason=failure_reason)
        return MinecraftTaskRunResult(
            task_id=task.task_id,
            family=task.family,
            success=success,
            utility=1.0 if success else 0.0,
            steps=len(actions),
            duration_s=duration,
            failure_reason=failure_reason,
            memory_queries=memory_queries,
            planner_actions=tuple(actions),
            decision_cycles=tuple(cycles),
            completion_receipt=completion,
        )


__all__ = [
    "MinecraftEnvironmentActionResult",
    "MinecraftEnvironmentObservation",
    "MinecraftEvidencePort",
    "MinecraftPlannerDecision",
    "MinecraftPlannerPort",
    "MinecraftSuccessSpec",
    "MinecraftTaskRunResult",
    "MinecraftTaskSpec",
    "MinecraftWorkloadDiagnosticsPort",
    "MinecraftWorkloadEnvironmentPort",
    "MinecraftWorkloadFailure",
    "MinecraftWorkloadRunner",
    "ScriptedMinecraftPlanner",
    "evaluate_success",
    "task_from_mapping",
]
