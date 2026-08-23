from __future__ import annotations

from dataclasses import dataclass

import pytest

from research_platform.experimentation.checkpoint.providers import DirectoryWorkloadCheckpointStore
from research_platform.experimentation.checkpoint.runtime import (
    CheckpointedWorkloadBatchExecutor,
    WorkloadCheckpointCoordinator,
)
from research_platform.experimentation.experiment.api import (
    ExperimentTaskSpec,
    ExperimentWorkloadFailure,
    FailureScope,
)
from research_platform.experimentation.workload import WorkloadTaskResult
from research_platform.platform.kernel import ExecutionContext


@dataclass
class _StateComponent:
    component_id: str = "test.session"
    codec_id: str = "test.session.bytes"
    schema_version: str = "1"
    value: bytes = b"initial"

    def capture(self) -> bytes:
        return self.value

    def restore(self, payload: bytes) -> None:
        self.value = payload


class _CheckpointBinding:
    run_id = "run-1"
    study_id = "study-1"
    workload_id = "workload-1"
    branch_id = "branch-1"
    source_cut_id = "cut-1"
    environment_generation = "env-1"
    method_generation = "method-1"
    task_manifest_digest = "tasks-1"

    def __init__(self, component: _StateComponent) -> None:
        self.component = component

    def checkpoint_components(self):
        return (self.component,)


class _Runner:
    def __init__(self, task_id: str, calls: list[str], *, abort: bool = False) -> None:
        self.task_id = task_id
        self.calls = calls
        self.abort = abort

    def run(self, task: ExperimentTaskSpec, context: ExecutionContext) -> WorkloadTaskResult:
        del context
        self.calls.append(task.task_id)
        if self.abort:
            raise ExperimentWorkloadFailure(
                "execute",
                "TEST_BRANCH_ABORT",
                "simulated interruption after the committed prefix",
                scope=FailureScope.BRANCH,
            )
        return WorkloadTaskResult(
            task_id=task.task_id,
            family=task.family,
            success=True,
            utility=1.0,
            steps=1,
            duration_s=0.01,
            lineage_id=task.lineage_id,
            planner_actions=({"tool": "finish"},),
            diagnostics={"receipt": task.task_id},
        )


class _BatchBinding:
    def __init__(
        self,
        component: _StateComponent,
        calls: list[str],
        *,
        abort_second: bool = False,
    ) -> None:
        self.context = ExecutionContext(
            "run-1",
            "trace-1",
            "span-1",
            study_id="study-1",
            branch_id="branch-1",
        )
        self.tasks = (
            ExperimentTaskSpec("task-1", "family", "first"),
            ExperimentTaskSpec("task-2", "family", "second", depends_on_task_ids=("task-1",)),
        )
        self.component = component
        self.calls = calls
        self.abort_second = abort_second
        self.closed = False
        self.recorded: list[str] = []

    def runner_for(self, task: ExperimentTaskSpec) -> _Runner:
        return _Runner(
            task.task_id,
            self.calls,
            abort=self.abort_second and task.task_id == "task-2",
        )

    def record_result(self, *, task, result, context) -> None:
        del context
        self.recorded.append(task.task_id)
        self.component.value = task.task_id.encode("utf-8")

    def close(self) -> None:
        self.closed = True


class _RecordingCoordinator:
    def __init__(self, inner: WorkloadCheckpointCoordinator) -> None:
        self.inner = inner
        self.captured = []

    def capture(self, **kwargs):
        manifest = self.inner.capture(**kwargs)
        self.captured.append(manifest)
        return manifest

    def restore(self, checkpoint_id, **kwargs):
        return self.inner.restore(checkpoint_id, **kwargs)


class _CheckpointPublication:
    def __init__(self) -> None:
        self.manifests = []

    def published(self, manifest) -> None:
        self.manifests.append(manifest)


def test_checkpointed_batch_resumes_exact_committed_prefix(tmp_path) -> None:
    recorder = _RecordingCoordinator(
        WorkloadCheckpointCoordinator(DirectoryWorkloadCheckpointStore(tmp_path / "cp"))
    )

    publication = _CheckpointPublication()
    first_state = _StateComponent()
    first_calls: list[str] = []
    first_batch = _BatchBinding(first_state, first_calls, abort_second=True)
    with pytest.raises(ExperimentWorkloadFailure):
        CheckpointedWorkloadBatchExecutor(recorder, publication=publication).execute(
            first_batch,
            checkpoint_binding=_CheckpointBinding(first_state),
        )

    assert first_calls == ["task-1", "task-2"]
    assert first_batch.recorded == ["task-1"]
    assert first_batch.closed is True
    assert len(recorder.captured) == 1
    assert publication.manifests == recorder.captured
    checkpoint_id = recorder.captured[0].checkpoint_id
    assert recorder.captured[0].execution_cut.completed_task_ids == ("task-1",)

    resumed_state = _StateComponent(value=b"fresh")
    resumed_calls: list[str] = []
    resumed_batch = _BatchBinding(resumed_state, resumed_calls)
    outcome = CheckpointedWorkloadBatchExecutor(
        recorder,
        publication=publication,
    ).execute(
        resumed_batch,
        checkpoint_binding=_CheckpointBinding(resumed_state),
        resume_checkpoint_id=checkpoint_id,
    )

    assert resumed_calls == ["task-2"]
    assert resumed_batch.recorded == ["task-2"]
    assert tuple(item.task_id for item in outcome.batch.task_results) == ("task-1", "task-2")
    assert outcome.resumed_from_checkpoint_id == checkpoint_id
    assert outcome.latest_checkpoint_id is not None
    assert publication.manifests == recorder.captured
    assert resumed_batch.closed is True
    # Restore first proves the component snapshot was task-1; task-2 then advances it.
    assert resumed_state.value == b"task-2"
