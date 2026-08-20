from research_platform.platform.composition.experiment_runtime import build_experiment_runtime
from tests_support import FakeParticipantResolver
from tests_support import EmptyWorkflowSurfaceFactory, context_action_spec
import unittest

from research_platform.experimentation.experiment.runtime import ExperimentRuntime
from research_platform.experimentation.experiment.api import ExperimentWorkflowIdentityMismatch
from research_platform.experimentation.experiment.api import ExperimentSpec


class AlternateWorkflow:
    workflow_id = "alternate.v1"
    surface_id = "empty.operations.v1"
    configuration_digest = "cfg-123"

    def run(self, operations, context, *, task, input_kind, input_payload):
        raise AssertionError("identity mismatch must fail before workflow execution")


class ExperimentWorkflowIdentityV127Tests(unittest.TestCase):
    def test_workflow_changes_study_identity(self):
        default = context_action_spec(study_id="s", method_id="m", environment_id="e", model_stack_digest="model", prompt_generation="prompt", workload_digest="work", seed_digest="seed", repetitions=1)
        from dataclasses import replace
        alternate = replace(
            default, scientific_workflow_id="alternate.v1",
            scientific_workflow_configuration_digest="cfg-123",
        )
        self.assertNotEqual(default.identity_digest(), alternate.identity_digest())

    def test_runtime_rejects_workflow_drift_before_plugin_construction(self):
        runtime = build_experiment_runtime(participant_adapters=(), scientific_workflow=AlternateWorkflow(), workflow_surface_factories=(EmptyWorkflowSurfaceFactory(),))
        frozen_default = context_action_spec(study_id="s", method_id="missing-method", environment_id="missing-env", model_stack_digest="model", prompt_generation="prompt", workload_digest="work", seed_digest="seed", repetitions=1)
        with self.assertRaises(ExperimentWorkflowIdentityMismatch):
            runtime.execute_cycle(
                frozen_default,
                task="x",
                input_kind="noop",
                input_payload=None,
            )

    def test_custom_workflow_requires_stable_id(self):
        class Anonymous:
            surface_id = "empty.operations.v1"
            configuration_digest = ""
            def run(self, operations, context, *, task, input_kind, input_payload):
                return None
        with self.assertRaises(ValueError):
            build_experiment_runtime(participant_adapters=(), scientific_workflow=Anonymous(), workflow_surface_factories=(EmptyWorkflowSurfaceFactory(),))


if __name__ == "__main__":
    unittest.main()
