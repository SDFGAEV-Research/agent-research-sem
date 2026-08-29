"""Strict durable reader for one platform-published qualified model closure."""

from collections.abc import Callable
import json
from pathlib import Path

from research_platform.model.serving.api import RuntimeQualificationEvidenceStorePort

from .qualified_binding import QualifiedModelDeploymentClosure
from .qualified_closure_codec import QualifiedClosureCodecError, decode_qualified_closure


class QualifiedModelClosureReadError(ValueError):
    """The persisted closure is absent, malformed, altered, or internally inconsistent."""


def load_qualified_model_deployment_closure(
    path: str | Path,
    *,
    runtime_qualification_store_factory: Callable[
        [Path], RuntimeQualificationEvidenceStorePort
    ],
) -> QualifiedModelDeploymentClosure:
    """Load only the strict platform-published closure schema."""

    closure_path = Path(path).expanduser().resolve(strict=False)
    if not closure_path.is_file():
        raise QualifiedModelClosureReadError(
            f"qualified model closure is missing: {closure_path}"
        )
    try:
        document = json.loads(closure_path.read_text(encoding="utf-8"))
        decoded = decode_qualified_closure(document)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, QualifiedClosureCodecError) as exc:
        raise QualifiedModelClosureReadError(
            f"qualified model closure cannot be decoded: {closure_path}"
        ) from exc

    runtime_root = (
        closure_path.parent / decoded.runtime_qualification_root
    ).resolve(strict=False)
    try:
        runtime_store = runtime_qualification_store_factory(runtime_root)
    except Exception as exc:
        raise QualifiedModelClosureReadError(
            "runtime qualification store factory failed"
        ) from exc
    if not callable(getattr(runtime_store, "load", None)) or not callable(
        getattr(runtime_store, "publish", None)
    ):
        raise QualifiedModelClosureReadError(
            "runtime qualification store factory returned an invalid port"
        )

    return QualifiedModelDeploymentClosure(
        role_manifest=decoded.role_manifest,
        deployments=decoded.deployments,
        routes=decoded.routes,
        runtime_manifest_digest=decoded.runtime_manifest_digest,
        runtime_qualifications=runtime_store,
    )


__all__ = [
    "QualifiedModelClosureReadError",
    "load_qualified_model_deployment_closure",
]
