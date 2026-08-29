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

    def checkpoint(self):
        return SimpleNamespace(method_runtime_binding_digest="m" * 64)


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

    @property
    def environment_generation(self) -> str:
        return "e" * 64

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


def _factory(
    events: list[str],
    *,
    candidate_materializer: object | None = None,
    cognition_factory: object | None = None,
):
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
        cognition_factory=cognition_factory,
    )


def test_workload_binding_opens_environment_before_method_and_closes_reverse_order() -> None:
    events: list[str] = []
    factory = _factory(events)
    branch = SimpleNamespace(branch_id="control-a", cut_id="cut-a")

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

def test_cognition_binding_adds_cognition_ancestry_to_workload_checkpoint_topology() -> None:
    events: list[str] = []
    factory = _factory(events, cognition_factory=object())
    binding = factory.open(
        role=BranchRole.CONTROL,
        candidate=None,
        branch=SimpleNamespace(branch_id="control-cognition", cut_id="cut-cognition"),
    )
    try:
        assert [component.component_id for component in binding.checkpoint_components()] == [
            "environment.session",
            "method.session",
            "evidence.audit",
            "evidence.eval",
            "participant.agent.cognition",
        ]
        assert binding.cognition_checkpoints is not None
    finally:
        binding.close()


class _ArtifactCapture:
    def __init__(self) -> None:
        self.texts: dict[str, str] = {}
        self.jsons: dict[str, dict] = {}

    def publish_text(self, name, content, *, kind):
        del kind
        self.texts[name] = content
        return name

    def publish_json(self, name, payload, *, kind):
        del kind
        self.jsons[name] = dict(payload)
        return name


class _FailOnceMethodClose:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.calls = 0

    def close(self) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("method close unavailable")
        self.inner.close()


def test_evidence_manifest_binds_exported_content_digests() -> None:
    import hashlib

    events: list[str] = []
    binding = _factory(events).open(
        role=BranchRole.CONTROL,
        candidate=None,
        branch=SimpleNamespace(branch_id="control-evidence", cut_id="cut-evidence"),
    )
    artifacts = _ArtifactCapture()
    binding.artifact_store = artifacts
    binding.evidence_artifact_prefix = "evidence/control-evidence"

    binding.close()

    manifest = artifacts.jsons["evidence/control-evidence/evidence_manifest.json"]
    assert manifest["schema_version"] == "sem-paper.minecraft-evidence-manifest.v2"
    assert manifest["branch_id"] == "control-evidence"
    assert manifest["source_cut_id"] == "cut-evidence"
    for name in ("j_audit.jsonl", "j_eval.jsonl"):
        body = artifacts.texts[f"evidence/control-evidence/{name}"].encode("utf-8")
        row = manifest["artifacts"][name]
        assert row["sha256"] == hashlib.sha256(body).hexdigest()
        assert row["size_bytes"] == len(body)


def test_close_retry_does_not_repeat_already_completed_cleanup_phases() -> None:
    events: list[str] = []
    binding = _factory(events).open(
        role=BranchRole.CONTROL,
        candidate=None,
        branch=SimpleNamespace(branch_id="control-retry", cut_id="cut-retry"),
    )
    original_method = binding.method
    failing_method = _FailOnceMethodClose(original_method)
    binding.method = failing_method

    with pytest.raises(SemPaperWorkloadBindingError, match="close failed"):
        binding.close()
    assert events.count("environment.close") == 1
    assert events.count("method.close") == 0

    binding.close()
    assert failing_method.calls == 2
    assert events.count("environment.close") == 1
    assert events.count("method.close") == 1
