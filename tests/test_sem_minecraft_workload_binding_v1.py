from __future__ import annotations

from types import SimpleNamespace

import pytest

from projects.sem_paper.composition import (
    SemPaperMinecraftWorkloadBindingFactory,
    SemPaperWorkloadBindingError,
    ScriptedMinecraftPlanner,
)
from projects.sem_paper.method.self_evolving_memory.evolution import BranchRole
from projects.sem_paper.composition.minecraft_workload import MinecraftTaskSpec
from research_platform.platform.kernel import ExecutionContext


class MethodSession:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def close(self) -> None:
        self.events.append("method.close")


class MethodEndpoint:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def open_session(self, *, session_id: str, services: object) -> MethodSession:
        self.events.append(f"method.open:{session_id}")
        return MethodSession(self.events)


class ObservationSink:
    def record(self, observation: object) -> None:
        del observation


class EnvironmentSession:
    def close(self) -> None:
        pass


class BranchRuntime:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.implementation = SimpleNamespace(
            identity=SimpleNamespace(artifact_digest="e" * 64)
        )

    def open_session(self, services: object) -> EnvironmentSession:
        del services
        self.events.append("environment.open")
        return EnvironmentSession()

    def close(self) -> None:
        self.events.append("environment.close")


class BranchRuntimeFactory:
    def __init__(self, runtime: BranchRuntime) -> None:
        self.runtime = runtime
        self.opened = 0

    def open(self, request: object) -> BranchRuntime:
        del request
        self.opened += 1
        return self.runtime


class RequestFactory:
    def build(self, *, role: BranchRole, candidate: object, branch: object) -> object:
        return (role, candidate, branch)


class PlannerFactory:
    def create(self, *, role, candidate, task, method):
        del role, candidate, task, method
        return ScriptedMinecraftPlanner(({"tool": "finish", "args": {}},))


class SinkFactory:
    def create(self, *, role: BranchRole, branch: object) -> ObservationSink:
        del role, branch
        return ObservationSink()


def _composition(events: list[str], candidate_materializer: object | None = None):
    return SimpleNamespace(
        bindings=SimpleNamespace(
            fixed_memory=MethodEndpoint(events),
            candidate_method_materializer=candidate_materializer,
        )
    )


def _factory(events: list[str], *, candidate_materializer: object | None = None):
    runtime = BranchRuntime(events)
    return SemPaperMinecraftWorkloadBindingFactory(
        composition=_composition(events, candidate_materializer),
        branch_runtime_factory=BranchRuntimeFactory(runtime),
        request_factory=RequestFactory(),
        planner_factory=PlannerFactory(),
        observation_sink_factory=SinkFactory(),
        tasks=(MinecraftTaskSpec("task-1", "collection", "collect wood"),),
        context=ExecutionContext("run-1", "trace-1", "span-1"),
        workload_id_factory=lambda role, branch: f"paper:{role.value}:{getattr(branch, 'branch_id', 'branch')}",
    )


def test_workload_binding_opens_environment_before_method_and_closes_reverse_order() -> None:
    events: list[str] = []
    factory = _factory(events)
    branch = SimpleNamespace(branch_id="control-a")

    binding = factory.open(role=BranchRole.CONTROL, candidate=None, branch=branch)
    assert binding.environment_generation == "e" * 64
    assert binding.task_manifest_digest
    assert events == ["environment.open", "method.open:control-a:method"]

    binding.close()
    assert events == [
        "environment.open",
        "method.open:control-a:method",
        "method.close",
        "environment.close",
    ]


def test_candidate_binding_fails_without_candidate_materializer_and_does_not_open_runtime() -> None:
    events: list[str] = []
    factory = _factory(events)
    with pytest.raises(SemPaperWorkloadBindingError, match="materializer"):
        factory.open(role=BranchRole.CANDIDATE, candidate=object(), branch=SimpleNamespace(branch_id="candidate-a"))
    assert events == []

