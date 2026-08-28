from __future__ import annotations

import json

import pytest

from tests_support import frozen_runtime_manifest
from research_platform.experimentation.run.manifest.runtime import (
    RunLaunchManifestDecodeError,
    decode_run_launch_manifest,
    encode_run_launch_manifest,
)


def test_run_launch_manifest_codec_round_trips_the_frozen_identity() -> None:
    manifest = frozen_runtime_manifest(
        release_digest="r",
        command_argv=("/opt/example/envs/project/bin/python", "-m", "runner"),
    )
    decoded = decode_run_launch_manifest(encode_run_launch_manifest(manifest))
    assert decoded == manifest
    assert decoded.digest() == manifest.digest()


def test_run_launch_manifest_codec_rejects_unknown_or_missing_fields() -> None:
    raw = json.loads(encode_run_launch_manifest(frozen_runtime_manifest()))
    raw["unexpected"] = "drift"
    with pytest.raises(RunLaunchManifestDecodeError):
        decode_run_launch_manifest(json.dumps(raw).encode())
