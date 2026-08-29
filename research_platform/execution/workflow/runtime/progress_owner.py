from __future__ import annotations

from dataclasses import replace
import hashlib
import json

from research_platform.execution.operation.api import OperationId
from research_platform.execution.workflow.api.graph import WorkflowGraph
from research_platform.execution.workflow.api.progress import (
    WorkflowOperationBinding,
    WorkflowProgress,
    WorkflowProgressConflict,
    WorkflowProgressStorePort,
    WorkflowRecoveryDisposition,
    WorkflowRunId,
)


def workflow_graph_digest(graph: WorkflowGraph) -> str:
    payload = [
        [step.step_id, step.operation_type, sorted(step.dependencies), sorted(step.required_capabilities)]
        for step in sorted(graph.steps, key=lambda item: item.step_id)
    ]
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class WorkflowProgressOwner:
    """Single durable owner for workflow progress and step/operation ancestry."""

    def __init__(self, store: WorkflowProgressStorePort) -> None:
        self._store = store

    @property
    def durability(self) -> str:
        return self._store.durability

    def start(self, workflow_run_id: WorkflowRunId, graph: WorkflowGraph) -> WorkflowProgress:
        graph_digest = workflow_graph_digest(graph)
        existing = self._store.load(workflow_run_id)
        if existing is not None:
            if existing.graph_digest != graph_digest:
                raise ValueError("workflow graph differs from durable workflow identity")
            return existing
        candidate = WorkflowProgress(workflow_run_id, graph_digest, 0)
        try:
            return self._store.create(candidate)
        except WorkflowProgressConflict:
            existing = self._store.load(workflow_run_id)
            if existing is None:
                raise
            if existing.graph_digest != graph_digest:
                raise ValueError("workflow graph differs from durable workflow identity")
            return existing

    def require(self, workflow_run_id: WorkflowRunId) -> WorkflowProgress:
        progress = self._store.load(workflow_run_id)
        if progress is None:
            raise KeyError(f"workflow progress not found: {workflow_run_id.value}")
        return progress

    @staticmethod
    def _require_graph(progress: WorkflowProgress, graph: WorkflowGraph) -> None:
        if progress.graph_digest != workflow_graph_digest(graph):
            raise ValueError("workflow graph differs from durable workflow identity")

    def ready_steps(self, workflow_run_id: WorkflowRunId, graph: WorkflowGraph) -> tuple[str, ...]:
        progress = self.require(workflow_run_id)
        self._require_graph(progress, graph)
        if progress.cancellation_requested or progress.failed is not None:
            return ()
        occupied = frozenset(item.step_id for item in (*progress.running, *progress.uncertain))
        return graph.ready_steps(frozenset(progress.completed_steps), occupied)

    def claim(
        self,
        workflow_run_id: WorkflowRunId,
        graph: WorkflowGraph,
        step_id: str,
        operation_id: OperationId,
    ) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        self._require_graph(progress, graph)
        if progress.cancellation_requested or progress.failed is not None:
            raise RuntimeError(f"workflow step is not ready: {step_id}")
        occupied = frozenset(item.step_id for item in (*progress.running, *progress.uncertain))
        ready = graph.ready_steps(frozenset(progress.completed_steps), occupied)
        if step_id not in ready:
            raise RuntimeError(f"workflow step is not ready: {step_id}")
        binding = WorkflowOperationBinding(step_id, operation_id)
        updated = replace(progress, version=progress.version + 1, running=progress.running + (binding,))
        return self._store.compare_and_swap(progress.version, updated)

    @staticmethod
    def _require_binding(
        bindings: tuple[WorkflowOperationBinding, ...], step_id: str, operation_id: OperationId, *, state: str
    ) -> WorkflowOperationBinding:
        matches = tuple(item for item in bindings if item.step_id == step_id)
        if len(matches) != 1:
            raise RuntimeError(f"workflow step is not {state}: {step_id}")
        binding = matches[0]
        if binding.operation_id != operation_id:
            raise RuntimeError(
                f"stale workflow operation completion rejected: step={step_id} "
                f"expected={binding.operation_id.value} actual={operation_id.value}"
            )
        return binding

    def complete(self, workflow_run_id: WorkflowRunId, step_id: str, operation_id: OperationId) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        binding = self._require_binding(progress.running, step_id, operation_id, state="running")
        updated = replace(
            progress,
            version=progress.version + 1,
            running=tuple(item for item in progress.running if item != binding),
            completed=tuple(sorted((*progress.completed, binding), key=lambda item: item.step_id)),
        )
        return self._store.compare_and_swap(progress.version, updated)

    def fail(self, workflow_run_id: WorkflowRunId, step_id: str, operation_id: OperationId) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        if progress.failed is not None:
            if progress.failed.step_id == step_id and progress.failed.operation_id == operation_id:
                return progress
            raise RuntimeError(f"workflow already failed at step: {progress.failed.step_id}")
        active = progress.running + progress.uncertain
        binding = self._require_binding(active, step_id, operation_id, state="active/uncertain")
        updated = replace(
            progress,
            version=progress.version + 1,
            failed=binding,
            running=tuple(item for item in progress.running if item != binding),
            uncertain=tuple(item for item in progress.uncertain if item != binding),
        )
        return self._store.compare_and_swap(progress.version, updated)

    def recover_interrupted(self, workflow_run_id: WorkflowRunId) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        if not progress.running:
            return progress
        updated = replace(
            progress,
            version=progress.version + 1,
            uncertain=tuple(sorted((*progress.uncertain, *progress.running), key=lambda item: item.step_id)),
            running=(),
        )
        return self._store.compare_and_swap(progress.version, updated)

    def reconcile(
        self,
        workflow_run_id: WorkflowRunId,
        step_id: str,
        operation_id: OperationId,
        disposition: WorkflowRecoveryDisposition,
    ) -> WorkflowProgress:
        progress = self.require(workflow_run_id)
        binding = self._require_binding(progress.uncertain, step_id, operation_id, state="uncertain")
        remaining = tuple(item for item in progress.uncertain if item != binding)
        if disposition is WorkflowRecoveryDisposition.COMPLETED:
            updated = replace(
                progress,
                version=progress.version + 1,
                uncertain=remaining,
                completed=tuple(sorted((*progress.completed, binding), key=lambda item: item.step_id)),
            )
        elif disposition is WorkflowRecoveryDisposition.RETRY_NOT_EXECUTED:
            updated = replace(progress, version=progress.version + 1, uncertain=remaining)
        else:
            if progress.failed is not None:
                raise RuntimeError(f"workflow already failed at step: {progress.failed.step_id}")
            updated = replace(progress, version=progress.version + 1, uncertain=remaining, failed=binding)
        return self._store.compare_and_swap(progress.version, updated)

    def request_cancel(
        self, workflow_run_id: WorkflowRunId, reason: str
    ) -> tuple[WorkflowProgress, tuple[OperationId, ...]]:
        if not isinstance(reason, str):
            raise TypeError("workflow cancellation reason must be text")
        reason = reason.strip()
        if not reason:
            raise ValueError("workflow cancellation reason required")
        progress = self.require(workflow_run_id)
        active = (*progress.running, *progress.uncertain)
        if progress.cancellation_requested:
            return progress, tuple(item.operation_id for item in active)
        updated = replace(
            progress,
            version=progress.version + 1,
            cancellation_requested=True,
            cancellation_reason=reason,
        )
        saved = self._store.compare_and_swap(progress.version, updated)
        return saved, tuple(item.operation_id for item in (*saved.running, *saved.uncertain))


__all__ = ["WorkflowProgressOwner", "workflow_graph_digest"]
