from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
from threading import Lock

from research_platform.model.serving.api import RuntimeQualificationEvidenceStorePort
from research_platform.model.serving.endpoint.api import (
    QualifiedModelClosurePublication,
    QualifiedModelClosurePublicationReceipt,
)
from research_platform.platform.kernel import canonical_bytes
from research_platform.platform.kernel.durability import InterprocessFileLock, atomic_replace_bytes

from .qualified_closure_codec import (
    QualifiedClosureCodecError,
    decode_qualified_closure,
    encode_qualified_closure,
)


_LOCAL_LOCKS_GUARD = Lock()
_LOCAL_LOCKS: dict[str, Lock] = {}


class QualifiedModelClosurePublicationError(RuntimeError):
    pass


def _local_lock(path: Path) -> Lock:
    key = os.path.normcase(str(path.resolve(strict=False)))
    with _LOCAL_LOCKS_GUARD:
        lock = _LOCAL_LOCKS.get(key)
        if lock is None:
            lock = Lock()
            _LOCAL_LOCKS[key] = lock
        return lock


def _publication_maps(publication: QualifiedModelClosurePublication):
    deployments = {item.deployment_id: item for item in publication.deployments}
    routes = {item.deployment_id: item for item in publication.routes}
    receipts = {item.deployment_id: item for item in publication.runtime_qualification_receipts}
    if len(deployments) != len(publication.deployments):
        raise QualifiedModelClosurePublicationError("qualified closure has duplicate deployments")
    if len(routes) != len(publication.routes):
        raise QualifiedModelClosurePublicationError("qualified closure has duplicate routes")
    if len(receipts) != len(publication.runtime_qualification_receipts):
        raise QualifiedModelClosurePublicationError("qualified closure has duplicate runtime receipts")
    if set(deployments) != set(routes) or set(deployments) != set(receipts):
        raise QualifiedModelClosurePublicationError(
            "qualified closure deployments, routes, and runtime receipts must align exactly"
        )
    return deployments, routes, receipts


def _validate(publication: QualifiedModelClosurePublication) -> None:
    deployments, routes, receipts = _publication_maps(publication)
    roles_by_deployment: dict[str, set[str]] = {key: set() for key in deployments}
    for assignment in publication.role_manifest.assignments:
        if assignment.deployment_id not in deployments:
            raise QualifiedModelClosurePublicationError(
                f"qualified role references missing deployment: {assignment.role}"
            )
        roles_by_deployment[assignment.deployment_id].add(assignment.role)

    for deployment_id, deployment in deployments.items():
        route = routes[deployment_id]
        receipt = receipts[deployment_id]
        certificate_digest = deployment.certificate.digest()
        if route.deployment_generation != deployment.digest():
            raise QualifiedModelClosurePublicationError(
                f"qualified endpoint route generation drift: {deployment_id}"
            )
        if receipt.stack_digest != deployment.stack.digest():
            raise QualifiedModelClosurePublicationError(
                f"runtime qualification stack drift: {deployment_id}"
            )
        if receipt.qualification_certificate_digest != certificate_digest:
            raise QualifiedModelClosurePublicationError(
                f"runtime qualification certificate drift: {deployment_id}"
            )
        if receipt.heartbeat_qualification_digest != certificate_digest:
            raise QualifiedModelClosurePublicationError(
                f"runtime heartbeat qualification drift: {deployment_id}"
            )
        required_roles = roles_by_deployment[deployment_id]
        if not required_roles or not required_roles.issubset(set(receipt.qualified_roles)):
            raise QualifiedModelClosurePublicationError(
                f"runtime qualification does not cover frozen roles: {deployment_id}"
            )
        if not receipt.evidence_refs:
            raise QualifiedModelClosurePublicationError(
                f"runtime qualification has no evidence refs: {deployment_id}"
            )
        if type(receipt.created_at) is not float or receipt.created_at <= 0:
            raise QualifiedModelClosurePublicationError(
                f"runtime qualification timestamp is invalid: {deployment_id}"
            )


def publish_qualified_model_deployment_closure(
    path: str | Path,
    publication: QualifiedModelClosurePublication,
    *,
    runtime_qualification_store_factory: Callable[
        [Path], RuntimeQualificationEvidenceStorePort
    ],
) -> QualifiedModelClosurePublicationReceipt:
    """Publish exact runtime receipts first, then expose one immutable closure atomically."""

    closure_path = Path(path).expanduser().resolve(strict=False)
    lock_path = closure_path.with_name(closure_path.name + ".publish.lock")
    document = encode_qualified_closure(
        role_manifest=publication.role_manifest,
        deployments=publication.deployments,
        routes=publication.routes,
        runtime_manifest_digest=publication.runtime_manifest_digest,
        runtime_qualification_root=publication.runtime_qualification_root,
    )
    try:
        decoded = decode_qualified_closure(document)
    except QualifiedClosureCodecError as exc:
        raise QualifiedModelClosurePublicationError("qualified closure publication is invalid") from exc

    with _local_lock(lock_path), InterprocessFileLock(lock_path):
        _validate(publication)
        existing_digest: str | None = None
        if closure_path.exists():
            try:
                existing = decode_qualified_closure(
                    json.loads(closure_path.read_text(encoding="utf-8"))
                )
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, QualifiedClosureCodecError) as exc:
                raise QualifiedModelClosurePublicationError(
                    "existing qualified closure is malformed and cannot be overwritten"
                ) from exc
            if existing.closure_digest != decoded.closure_digest:
                raise QualifiedModelClosurePublicationError(
                    "qualified closure already exists with different content"
                )
            existing_digest = existing.closure_digest
        runtime_root = (closure_path.parent / decoded.runtime_qualification_root).resolve(strict=False)
        runtime_store = runtime_qualification_store_factory(runtime_root)
        evidence_paths: list[str] = []
        for receipt in sorted(
            publication.runtime_qualification_receipts,
            key=lambda item: item.deployment_id,
        ):
            try:
                evidence_path = runtime_store.publish(
                    publication.runtime_manifest_digest,
                    receipt,
                )
                loaded = runtime_store.load(
                    publication.runtime_manifest_digest,
                    receipt.deployment_id,
                )
            except Exception as exc:
                raise QualifiedModelClosurePublicationError(
                    f"runtime qualification publication failed: {receipt.deployment_id}"
                ) from exc
            if loaded.digest() != receipt.digest():
                raise QualifiedModelClosurePublicationError(
                    f"runtime qualification readback drift: {receipt.deployment_id}"
                )
            evidence_paths.append(str(evidence_path))

        if existing_digest is not None:
            return QualifiedModelClosurePublicationReceipt(
                closure_path=str(closure_path),
                closure_digest=existing_digest,
                runtime_evidence_paths=tuple(evidence_paths),
            )

        atomic_replace_bytes(closure_path, canonical_bytes(document, indent=2))
        try:
            persisted = decode_qualified_closure(
                json.loads(closure_path.read_text(encoding="utf-8"))
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, QualifiedClosureCodecError) as exc:
            raise QualifiedModelClosurePublicationError(
                "published qualified closure failed readback validation"
            ) from exc
        if persisted.closure_digest != decoded.closure_digest:
            raise QualifiedModelClosurePublicationError(
                "published qualified closure digest changed during readback"
            )
        return QualifiedModelClosurePublicationReceipt(
            closure_path=str(closure_path),
            closure_digest=persisted.closure_digest,
            runtime_evidence_paths=tuple(evidence_paths),
        )


__all__ = [
    "QualifiedModelClosurePublicationError",
    "publish_qualified_model_deployment_closure",
]
