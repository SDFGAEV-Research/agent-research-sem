from __future__ import annotations

from pathlib import Path

from research_platform.model.serving.endpoint.api import (
    QualifiedModelClosurePublication,
    QualifiedModelClosurePublicationReceipt,
)
from research_platform.model.serving.endpoint.providers.qualified_closure_publication import (
    publish_qualified_model_deployment_closure as _publish_qualified_model_deployment_closure,
)
from research_platform.model.serving.providers.runtime_qualification_storage import (
    DirectoryRuntimeQualificationEvidenceStore,
)


def publish_qualified_model_deployment_closure(
    path: str | Path,
    publication: QualifiedModelClosurePublication,
) -> QualifiedModelClosurePublicationReceipt:
    """Publish one qualified deployment closure through the platform default durable backend."""

    return _publish_qualified_model_deployment_closure(
        path,
        publication,
        runtime_qualification_store_factory=DirectoryRuntimeQualificationEvidenceStore,
    )


__all__ = ["publish_qualified_model_deployment_closure"]
