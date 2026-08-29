from __future__ import annotations

import hashlib
import json
from threading import Event, Thread

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


def test_concurrent_artifact_publication_has_one_destination_owner(tmp_path) -> None:
    payload = b"one-immutable-runtime-artifact"
    sha256 = hashlib.sha256(payload).hexdigest()
    first_opened = Event()
    release_first = Event()
    first_results = []
    first_errors = []

    def opener(request, timeout):
        del request, timeout
        if not first_opened.is_set():
            first_opened.set()
            assert release_first.wait(5)
        return _Response(payload)

    assembly = compose_artifact_acquisition(opener=opener)
    request = ArtifactAcquisitionRequest(
        artifact_id="runtime.artifact.concurrent",
        source_url="https://artifacts.example.invalid/runtime.bin",
        destination=str(tmp_path / "server.jar"),
        scope=PLATFORM_SCOPE,
        kind=ArtifactKind.RUNTIME,
        producer_component_id="test",
        expected_sha256=sha256,
    )

    def first_acquire() -> None:
        try:
            first_results.append(assembly.acquirer.acquire(request))
        except BaseException as exc:
            first_errors.append(exc)

    thread = Thread(target=first_acquire)
    thread.start()
    assert first_opened.wait(5)
    try:
        with pytest.raises(ArtifactAcquisitionError) as caught:
            assembly.acquirer.acquire(request)
        assert caught.value.code == "PUBLICATION_BUSY"
    finally:
        release_first.set()
        thread.join(5)

    assert not thread.is_alive()
    assert first_errors == []
    assert len(first_results) == 1
    assert first_results[0].downloaded is True
    assert (tmp_path / "server.jar").read_bytes() == payload
