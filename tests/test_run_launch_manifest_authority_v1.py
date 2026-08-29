from __future__ import annotations

from dataclasses import replace
import unittest

import pytest

from research_platform.experimentation.run.manifest.api import CompositionPlanReference
from research_platform.execution.runtime.manager import RunLaunchIdentity
from tests_support import frozen_runtime_manifest


class RunLaunchManifestAuthorityV1Tests(unittest.TestCase):
    def test_only_the_run_manifest_system_owns_launch_identity(self):
        from research_platform.execution.runtime import manager
        from research_platform.governance.release import api as release_api

        self.assertFalse(hasattr(manager, "FrozenRuntimeManifest"))
        self.assertFalse(hasattr(release_api, "RunLaunchManifest"))

    def test_composition_plan_is_required_and_changes_run_process_generation(self):
        manifest = frozen_runtime_manifest()
        with self.assertRaisesRegex(ValueError, "requires at least one composition plan"):
            replace(manifest, composition_plans=())

        changed = replace(
            manifest,
            composition_plans=(
                CompositionPlanReference(
                    "tests.runtime.composition.v1",
                    "system:tests-runtime",
                    "platform:platform",
                    "b" * 64,
                ),
            ),
        )
        self.assertNotEqual(manifest.digest(), changed.digest())
        self.assertNotEqual(
            RunLaunchIdentity.from_manifest(manifest),
            RunLaunchIdentity.from_manifest(changed),
        )
        self.assertEqual(RunLaunchIdentity.from_manifest(manifest).digest(), manifest.digest())


if __name__ == "__main__":
    unittest.main()


def test_run_launch_manifest_rejects_non_string_identity_values() -> None:
    manifest = frozen_runtime_manifest()
    with pytest.raises(ValueError):
        replace(manifest, release_digest=7)
    with pytest.raises(ValueError):
        replace(manifest, command_argv=("run", False))
    with pytest.raises(ValueError):
        replace(manifest, qualified_deployment_digests=(False,))
    with pytest.raises(ValueError):
        replace(manifest, config_digests=(("config", False),))


def test_composition_plan_reference_rejects_non_string_fields() -> None:
    with pytest.raises(ValueError):
        CompositionPlanReference(
            "tests.runtime.composition.v1",
            False,
            "platform:platform",
            "a" * 64,
        )
