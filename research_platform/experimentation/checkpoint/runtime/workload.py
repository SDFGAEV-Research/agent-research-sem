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
    WorkloadCheckpointRestoreError,
    WorkloadCheckpointStore,
    WorkloadExecutionCut,
    WorkloadRestoreStateCertainty,
    build_workload_checkpoint_manifest,
)


class WorkloadCheckpointIdentityMismatch(RuntimeError):
    """The requested binding is not the binding that created a checkpoint."""


class WorkloadCheckpointCoordinator:
    """Capture and recover one environment-method-workload checkpoint."""

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
        components = tuple(binding.checkpoint_components())
        ids = tuple(component.component_id for component in components)
        if not ids or len(ids) != len(set(ids)):
            raise WorkloadCheckpointIntegrityError(
                "workload checkpoint requires unique non-empty component providers"
            )
        payloads: list[WorkloadCheckpointPayload] = []
        for component in components:
            payload = component.capture()
            if not isinstance(payload, bytes):
                raise TypeError(
                    f"checkpoint component returned non-bytes payload: {component.component_id}"
                )
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

        component_rows = tuple(binding.checkpoint_components())
        component_ids = tuple(item.component_id for item in component_rows)
        if not component_ids or len(component_ids) != len(set(component_ids)):
            raise WorkloadCheckpointIdentityMismatch(
                "workload checkpoint binding component topology is not unique"
            )
        components = {item.component_id: item for item in component_rows}
        manifest_ids = tuple(item.component_id for item in manifest.component_refs)
        if set(component_ids) != set(manifest_ids):
            raise WorkloadCheckpointIdentityMismatch("workload checkpoint component topology mismatch")
        payload_ids = tuple(item.ref.component_id for item in bundle.payloads)
        if len(payload_ids) != len(set(payload_ids)) or set(payload_ids) != set(manifest_ids):
            raise WorkloadCheckpointIdentityMismatch(
                "workload checkpoint payload topology mismatch"
            )
        payloads = {item.ref.component_id: item for item in bundle.payloads}
        manifest_refs = {item.component_id: item for item in manifest.component_refs}
        for component_id in manifest_ids:
            component = components[component_id]
            ref = manifest_refs[component_id]
            payload = payloads[component_id]
            if payload.ref != ref:
                raise WorkloadCheckpointIdentityMismatch(
                    f"workload checkpoint payload reference drift: {component_id}"
                )
            if (component.codec_id, component.schema_version) != (
                ref.codec_id,
                ref.schema_version,
            ):
                raise WorkloadCheckpointIdentityMismatch(
                    f"workload checkpoint codec drift: {component_id}"
                )

        preimages: dict[str, bytes] = {}
        for component_id in manifest_ids:
            component = components[component_id]
            try:
                preimage = component.capture()
                if not isinstance(preimage, bytes):
                    raise TypeError("checkpoint component preimage must be bytes")
            except BaseException as exc:
                raise WorkloadCheckpointRestoreError(
                    phase="preimage_capture",
                    component_id=component_id,
                    primary=exc,
                    state_certainty=WorkloadRestoreStateCertainty.UNCHANGED,
                ) from exc
            preimages[component_id] = preimage

        attempted: list[str] = []
        try:
            for component_id in manifest_ids:
                attempted.append(component_id)
                components[component_id].restore(payloads[component_id].payload)
        except BaseException as primary:
            rollback_errors: list[tuple[str, BaseException]] = []
            for component_id in reversed(attempted):
                try:
                    components[component_id].restore(preimages[component_id])
                except BaseException as rollback_exc:
                    rollback_errors.append((component_id, rollback_exc))
            certainty = (
                WorkloadRestoreStateCertainty.UNKNOWN
                if rollback_errors
                else WorkloadRestoreStateCertainty.ROLLED_BACK
            )
            raise WorkloadCheckpointRestoreError(
                phase="apply",
                component_id=attempted[-1],
                primary=primary,
                state_certainty=certainty,
                rollback_errors=tuple(rollback_errors),
            ) from primary
        return bundle


__all__ = [
    "WorkloadCheckpointCoordinator",
    "WorkloadCheckpointIdentityMismatch",
    "WorkloadCheckpointRestoreError",
    "WorkloadRestoreStateCertainty",
]
