from __future__ import annotations

from research_platform.experimentation.experiment.api import (
    ExperimentScientificWorkflow,
    ExperimentSpec,
    ExperimentWorkflowIdentity,
    ExperimentWorkflowIdentityMismatch,
)


def workflow_identity(workflow: ExperimentScientificWorkflow) -> ExperimentWorkflowIdentity:
    workflow_id = getattr(workflow, "workflow_id", None)
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise ValueError("ExperimentScientificWorkflow must expose a stable non-empty workflow_id")
    configuration_digest = getattr(workflow, "configuration_digest", "")
    if not isinstance(configuration_digest, str):
        raise ValueError("ExperimentScientificWorkflow.configuration_digest must be a string")
    return ExperimentWorkflowIdentity(workflow_id, configuration_digest)


def verify_workflow_identity(spec: ExperimentSpec, identity: ExperimentWorkflowIdentity) -> None:
    expected = (spec.scientific_workflow_id, spec.scientific_workflow_configuration_digest)
    actual = (identity.workflow_id, identity.configuration_digest)
    if expected != actual:
        raise ExperimentWorkflowIdentityMismatch(
            "frozen Experiment workflow identity mismatch: "
            f"expected id={expected[0]!r} config={expected[1]!r}, "
            f"actual id={actual[0]!r} config={actual[1]!r}"
        )


__all__ = ["verify_workflow_identity", "workflow_identity"]
