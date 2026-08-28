from __future__ import annotations

import hashlib
import json

import pytest

from research_platform.artifact.catalog.api import ArtifactKind
from research_platform.artifact.catalog.runtime import InMemoryArtifactRegistry
from research_platform.artifact.content.api import ArtifactAcquisitionError, ArtifactAcquisitionRequest
from research_platform.artifact.content.composition import compose_artifact_acquisition
from research_platform.scope.api import PLATFORM_SCOPE


class _Response:
    status = 200

    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        del size
        payload, self._payload = self._payload, b""
        return payload

    def close(self) -> None:
        self.closed = True


def test_generic_artifact_acquisition_atomically_publishes_and_reuses_verified_file(tmp_path) -> None:
    payload = b"runtime-artifact-bytes"
    sha1 = hashlib.sha1(payload).hexdigest()
    calls: list[str] = []

    def opener(request, timeout):
        del timeout
        calls.append(request.full_url)
        return _Response(payload)

    assembly = compose_artifact_acquisition(opener=opener)
    request = ArtifactAcquisitionRequest(
        artifact_id="runtime.artifact.test",
        source_url="https://artifacts.example.invalid/runtime.bin",
        destination=str(tmp_path / "server.jar"),
        scope=PLATFORM_SCOPE,
        kind=ArtifactKind.RUNTIME,
        producer_component_id="test",
        expected_sha1=sha1,
    )
    first = assembly.acquirer.acquire(request)
    second = assembly.acquirer.acquire(request)

    assert first.downloaded is True
    assert second.downloaded is False
    assert first.record.digest == hashlib.sha256(payload).hexdigest()
    assert (tmp_path / "server.jar").read_bytes() == payload
    assert calls == [request.source_url]

    registry = InMemoryArtifactRegistry()
    assert registry.put(first.record) == first.record


def test_generic_artifact_acquisition_fails_closed_on_digest_mismatch(tmp_path) -> None:
    payload = b"not-the-expected-server"

    def opener(request, timeout):
        del request, timeout
        return _Response(payload)

    assembly = compose_artifact_acquisition(opener=opener)
    request = ArtifactAcquisitionRequest(
        artifact_id="runtime.artifact.bad",
        source_url="https://artifacts.example.invalid/runtime.bin",
        destination=str(tmp_path / "server.jar"),
        scope=PLATFORM_SCOPE,
        kind=ArtifactKind.RUNTIME,
        producer_component_id="test",
        expected_sha1="0" * 40,
    )
    with pytest.raises(ArtifactAcquisitionError, match="SHA1_MISMATCH"):
        assembly.acquirer.acquire(request)
    assert not (tmp_path / "server.jar").exists()
