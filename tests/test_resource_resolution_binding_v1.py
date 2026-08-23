from __future__ import annotations

from pathlib import Path
import sys

from research_platform.resource.resolution import ResourceResolutionRequest
from research_platform.resource.resolution.composition import build_local_resource_resolver


def test_named_resource_binding_resolves_paths_and_executables_without_project_path_logic(tmp_path: Path):
    binding = build_local_resource_resolver().resolve(
        ResourceResolutionRequest(
            "run-1",
            str(tmp_path),
            paths=(("artifacts", "artifacts"), ("input", str(tmp_path / "input.json"))),
            executables=(("python", sys.executable),),
        )
    )

    assert binding.path("artifacts") == str((tmp_path / "artifacts").resolve())
    assert binding.path("input") == str((tmp_path / "input.json").resolve())
    assert Path(binding.executable("python")).is_file()
    assert len(binding.resolution_digest) == 64
