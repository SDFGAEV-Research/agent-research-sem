from __future__ import annotations

from types import SimpleNamespace

from projects.sem_paper.composition import (
    SemPaperNonMinecraftProductionRoot,
    SemPaperNonMinecraftWorkloadPorts,
    build_sem_paper_study_protocol,
    compose_sem_paper_non_minecraft_production_root,
)
from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from research_platform.environment.api import ActionRequest, ActionResult, Observation
from research_platform.experimentation.experiment.api import ExperimentTaskSpec
from research_platform.experimentation.run.api import ExperimentRunSpec
from research_platform.experimentation.run.composition import build_default_experiment_run_application
from research_platform.participant.method.api import (
    MethodTaskCompletionReceipt,
    RecallResult,
)
from research_platform.platform.kernel import ExecutionContext, canonical_digest


class _Method:
    def recall(self, request):
        return RecallResult("", "method-g0")

    def task_completed(self, result, context):
        return MethodTaskCompletionReceipt(context.task_id or "task", "method-g0")

    def close(self):
        return None


class _Endpoint:
    def __init__(self, name: str):
        self.name = name

    def open_session(self, *, session_id, services):
        del session_id, services
        return _Method()


class _CandidateMaterializer:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.calls = 0

    def materialize(self, candidate):
        assert candidate is not None
        self.calls += 1
        return self.endpoint


class _Environment:
    def observe(self, context):
        return Observation(f"obs:{context.task_id}:initial", "closed-world-g0", {"state": {"done": False}})

    def act(self, request: ActionRequest):
        return ActionResult(
            request.action_id,
            True,
            Observation(f"obs:{request.action_id}", "closed-world-g0", {"state": {"done": True}}),
            None,
            {"verified": True},
        )

    def close(self):
        return None


class _EnvironmentFactory:
    def open(self, *, role, candidate, unit, assignment, context):
        del role, candidate, unit, assignment, context
        return _Environment()


class _Planner:
    def decide(self, *, task, context, state, memory_context, step, prior_actions):
        from research_platform.experimentation.workload import WorkloadDecision

        return WorkloadDecision("advance", {"step": step}, "test")


class _PlannerFactory:
    def create(self, *, role, candidate, unit, assignment, task, method):
        del role, candidate, unit, assignment, task, method
        return _Planner()


class _State:
    def state(self, observation):
        return observation.payload["state"]


class _Completion:
    def is_complete(self, *, task, state, planner_finished, last_action):
        del task, planner_finished, last_action
        return bool(state.get("done"))

    def utility(self, *, task, success, state):
        del task, state
        return 1.0 if success else 0.0


class _Evidence:
    def ingest_observation(self, observation, context):
        del context
        return (observation.observation_id,)


class _EvidenceFactory:
    def create(self, *, role, candidate, unit, assignment, method):
        del role, candidate, unit, assignment
        assert isinstance(method, _Method)
        return _Evidence()


class _ObservationSinkFactory:
    def create(self, *, role, repetition):
        del role, repetition
        return SimpleNamespace(record=lambda observation: None)


class _Artifacts:
    def publish_json(self, name, payload, *, kind):
        del payload, kind
        return name


def test_non_minecraft_root_uses_generic_batch_and_materializes_treatment():
    task = ExperimentTaskSpec("task-1", "closed", "advance")
    protocol = build_sem_paper_study_protocol(
        study_id="study-1",
        workload_id="workload-1",
        task_manifest_digest=canonical_digest((task,)),
        seed_identity="seed",
        fixed_configuration="fixed",
        candidate_configuration="candidate",
    )
    materializer = _CandidateMaterializer(_Endpoint("candidate"))
    composition = SimpleNamespace(
        bindings=SimpleNamespace(
            fixed_memory=_Endpoint("fixed"),
            candidate_method_materializer=materializer,
        )
    )
    run_spec = ExperimentRunSpec(
        run_id="run-1",
        project_id="sem-paper-1",
        experiment_id="sem-paper-non-minecraft",
        study_id=protocol.study_id,
        execution_profile="test",
        task_manifest_digest=protocol.task_manifest_digest,
        seed_schedule_digest=protocol.seed_schedule_digest,
        repetitions=protocol.repetitions,
        artifact_root="C:/runs/run-1",
        environment_identity_digest=canonical_digest("non-minecraft-test"),
    )
    root = compose_sem_paper_non_minecraft_production_root(
        composition=composition,
        run_spec=run_spec,
        ports=SemPaperNonMinecraftWorkloadPorts(
            environment_factory=_EnvironmentFactory(),
            planner_factory=_PlannerFactory(),
            state=_State(),
            completion=_Completion(),
            evidence_factory=_EvidenceFactory(),
            observation_sink_factory=_ObservationSinkFactory(),
        ),
        tasks=(task,),
        study_protocol=protocol,
        context=ExecutionContext("run-1", "trace-1", "span-1", study_id="study-1"),
        run_executor=build_default_experiment_run_application(_Artifacts()),
        candidate=SimpleNamespace(),
    )

    assert isinstance(root, SemPaperNonMinecraftProductionRoot)
    report = root.execute_run().study_report

    assert len(report.observations) == 2
    assert all(dict(observation.metrics)["success_rate"] == 1.0 for observation in report.observations)
    assert materializer.calls == 1
