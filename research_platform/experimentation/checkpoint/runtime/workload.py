from __future__ import annotations

import hashlib

from research_platform.platform.kernel import ExecutionContext

from .capture import load_workload_checkpoint, publish_workload_checkpoint

from ..api import (
    RunCheckpointIntegrityError,
    WorkloadCheckpointBindingPort,
    WorkloadCheckpointBundle,
    WorkloadCheckpointComponentRef,
    WorkloadCheckpointManifest,
    WorkloadCheckpointPayload,
    WorkloadCheckpointStore,
    WorkloadExecutionCut,
    build_workload_checkpoint_manifest,
)


class WorkloadCheckpointIdentityMismatch(RuntimeError):
    """The requested binding is not the binding that created a checkpoint."""


class WorkloadCheckpointCoordinator:
    """Capture/restore one atomic environment-method-workload checkpoint."""

    def __init__(self, store: WorkloadCheckpointStore) -> None:
        self._store = store

    @staticmethod
    def _require_context(context: ExecutionContext) -> tuple[str, str, str]:
        if not context.run_id.strip() or not context.study_id or not context.study_id.strip():
            raise WorkloadCheckpointIdentityMismatch(
                "workload checkpoint requires run_id and study_id in ExecutionContext"
            )
        if not context.branch_id or not context.branch_id.strip():
            raise WorkloadCheckpointIdentityMismatch(
                "workload checkpoint requires branch_id in ExecutionContext"
            )
        return context.run_id, context.study_id, context.branch_id

    def capture(
        self,
        *,
        binding: WorkloadCheckpointBindingPort,
        context: ExecutionContext,
        execution_cut: WorkloadExecutionCut,
    ) -> WorkloadCheckpointManifest:
        run_id, study_id, branch_id = self._require_context(context)
        if binding.run_id != run_id or binding.study_id != study_id or binding.branch_id != branch_id:
            raise WorkloadCheckpointIdentityMismatch("checkpoint context does not match workload binding")
        components = binding.checkpoint_components()
        ids = [component.component_id for component in components]
        if len(ids) != len(set(ids)) or not ids:
            raise WorkloadCheckpointIntegrityError(
                "workload checkpoint requires unique non-empty component providers"
            )
        payloads: list[WorkloadCheckpointPayload] = []
        for component in components:
            payload = component.capture()
            if not isinstance(payload, bytes):
                raise TypeError(f"checkpoint component returned non-bytes payload: {component.component_id}")
            ref = WorkloadCheckpointComponentRef(
                component_id=component.component_id,
                codec_id=component.codec_id,
                schema_version=component.schema_version,
                payload_sha256=hashlib.sha256(payload).hexdigest(),
                payload_size=len(payload),
            )
            payloads.append(WorkloadCheckpointPayload(ref, payload))
        manifest = build_workload_checkpoint_manifest(
            run_id=run_id,
            study_id=study_id,
            workload_id=binding.workload_id,
            branch_id=branch_id,
            source_cut_id=binding.source_cut_id,
            environment_generation=binding.environment_generation,
            method_generation=binding.method_generation,
            task_manifest_digest=binding.task_manifest_digest,
            execution_cut=execution_cut,
            component_refs=tuple(item.ref for item in payloads),
        )
        return publish_workload_checkpoint(self._store, manifest, tuple(payloads))

    def restore(
        self,
        checkpoint_id: str,
        *,
        binding: WorkloadCheckpointBindingPort,
        context: ExecutionContext,
    ) -> WorkloadCheckpointBundle:
        run_id, study_id, branch_id = self._require_context(context)
        bundle = load_workload_checkpoint(self._store, checkpoint_id)
        manifest = bundle.manifest
        expected = {
            "run_id": run_id,
            "study_id": study_id,
            "workload_id": binding.workload_id,
            "branch_id": branch_id,
            "source_cut_id": binding.source_cut_id,
            "environment_generation": binding.environment_generation,
            "method_generation": binding.method_generation,
            "task_manifest_digest": binding.task_manifest_digest,
        }
        actual = {key: getattr(manifest, key) for key in expected}
        if actual != expected:
            raise WorkloadCheckpointIdentityMismatch(
                f"workload checkpoint identity mismatch: expected={expected!r} actual={actual!r}"
            )
        components = {item.component_id: item for item in binding.checkpoint_components()}
        if set(components) != {item.component_id for item in manifest.component_refs}:
            raise WorkloadCheckpointIdentityMismatch("workload checkpoint component topology mismatch")
        payloads = {item.ref.component_id: item for item in bundle.payloads}
        for ref in manifest.component_refs:
            component = components[ref.component_id]
            if (component.codec_id, component.schema_version) != (ref.codec_id, ref.schema_version):
                raise WorkloadCheckpointIdentityMismatch(
                    f"workload checkpoint codec drift: {ref.component_id}"
                )
            component.restore(payloads[ref.component_id].payload)
        return bundle


__all__ = ["WorkloadCheckpointCoordinator", "WorkloadCheckpointIdentityMismatch"]
