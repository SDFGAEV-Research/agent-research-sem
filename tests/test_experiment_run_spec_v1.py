from __future__ import annotations

import unittest

from research_platform.experimentation.run.api import ExperimentRunSpec


class ExperimentRunSpecTests(unittest.TestCase):
    def test_identity_is_environment_neutral_and_digestable(self) -> None:
        spec = ExperimentRunSpec(
            run_id="run-1",
            project_id="project-1",
            experiment_id="experiment-1",
            study_id="study-1",
            execution_profile="baseline",
            task_manifest_digest="tasks",
            seed_schedule_digest="seeds",
            repetitions=2,
            artifact_root="runs/project-1/run-1",
            environment_identity_digest="environment",
            model_binding_digest="model-binding",
            prompt_generation="prompt-v1",
        )

        self.assertEqual(len(spec.identity_digest()), 64)
        self.assertEqual(spec.repetitions, 2)

    def test_empty_provider_identity_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ExperimentRunSpec(
                run_id="run-1",
                project_id="project-1",
                experiment_id="experiment-1",
                study_id="study-1",
                execution_profile="baseline",
                task_manifest_digest="tasks",
                seed_schedule_digest="seeds",
                repetitions=1,
                artifact_root="runs/project-1/run-1",
                environment_identity_digest="",
            )


if __name__ == "__main__":
    unittest.main()
