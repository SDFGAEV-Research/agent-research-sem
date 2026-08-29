from __future__ import annotations

import hashlib
import json
from pathlib import Path
from threading import Event, Thread
from unittest import mock

import pytest

from research_platform.artifact.catalog.api import ArtifactKind
from research_platform.artifact.catalog.runtime import InMemoryArtifactRegistry
from research_platform.artifact.content.api import ArtifactAcquisitionError, ArtifactAcquisitionRequest
from research_platform.artifact.content.composition import compose_artifact_acquisition
from research_platform.artifact.content.providers import download as download_provider
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


def test_verified_existing_artifact_is_hashed_once_on_reuse(tmp_path) -> None:
    payload = b"large-artifact-simulation"
    assembly = compose_artifact_acquisition(opener=lambda request, timeout: _Response(payload))
    request = ArtifactAcquisitionRequest(
        artifact_id="runtime.artifact.reuse-hash",
        source_url="https://artifacts.example.invalid/runtime.bin",
        destination=str(tmp_path / "runtime.bin"),
        scope=PLATFORM_SCOPE,
        kind=ArtifactKind.RUNTIME,
        producer_component_id="test",
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )
    assembly.acquirer.acquire(request)
    with mock.patch.object(download_provider, "_digests", wraps=download_provider._digests) as digests:
        reused = assembly.acquirer.acquire(request)
    assert reused.downloaded is False
    assert digests.call_count == 1


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


def test_artifact_acquisition_cleanup_failure_is_typed_and_preserves_primary_failure(tmp_path) -> None:
    payload = b"not-the-expected-artifact"
    assembly = compose_artifact_acquisition(opener=lambda request, timeout: _Response(payload))
    request = ArtifactAcquisitionRequest(
        artifact_id="runtime.artifact.cleanup-failure",
        source_url="https://artifacts.example.invalid/runtime.bin",
        destination=str(tmp_path / "runtime.bin"),
        scope=PLATFORM_SCOPE,
        kind=ArtifactKind.RUNTIME,
        producer_component_id="test",
        expected_sha256="0" * 64,
    )
    with mock.patch.object(Path, "unlink", side_effect=PermissionError("cleanup blocked")):
        with pytest.raises(ArtifactAcquisitionError) as caught:
            assembly.acquirer.acquire(request)

    assert caught.value.code == "TEMP_CLEANUP_FAILED"
    assert isinstance(caught.value.__cause__, ArtifactAcquisitionError)
    assert caught.value.__cause__.code == "SHA256_MISMATCH"
    assert "PermissionError: cleanup blocked" in str(caught.value)


def test_artifact_acquisition_cleanup_failure_preserves_wrapped_download_failure(tmp_path) -> None:
    def opener(request, timeout):
        del request, timeout
        raise OSError("network failed")

    assembly = compose_artifact_acquisition(opener=opener)
    request = ArtifactAcquisitionRequest(
        artifact_id="runtime.artifact.cleanup-download-failure",
        source_url="https://artifacts.example.invalid/runtime.bin",
        destination=str(tmp_path / "runtime.bin"),
        scope=PLATFORM_SCOPE,
        kind=ArtifactKind.RUNTIME,
        producer_component_id="test",
        expected_sha256="0" * 64,
    )
    with mock.patch.object(Path, "unlink", side_effect=PermissionError("cleanup blocked")):
        with pytest.raises(ArtifactAcquisitionError) as caught:
            assembly.acquirer.acquire(request)

    assert caught.value.code == "TEMP_CLEANUP_FAILED"
    assert isinstance(caught.value.__cause__, ArtifactAcquisitionError)
    assert caught.value.__cause__.code == "DOWNLOAD_FAILED"
    assert "OSError: network failed" in str(caught.value.__cause__)


def test_artifact_acquisition_cleanup_failure_does_not_mask_base_exception(tmp_path) -> None:
    class AbortAcquisition(BaseException):
        pass

    def opener(request, timeout):
        del request, timeout
        raise AbortAcquisition("stop now")

    assembly = compose_artifact_acquisition(opener=opener)
    request = ArtifactAcquisitionRequest(
        artifact_id="runtime.artifact.cleanup-abort",
        source_url="https://artifacts.example.invalid/runtime.bin",
        destination=str(tmp_path / "runtime.bin"),
        scope=PLATFORM_SCOPE,
        kind=ArtifactKind.RUNTIME,
        producer_component_id="test",
        expected_sha256="0" * 64,
    )
    with mock.patch.object(Path, "unlink", side_effect=PermissionError("cleanup blocked")):
        with pytest.raises(AbortAcquisition) as caught:
            assembly.acquirer.acquire(request)

    assert caught.value.__notes__
    assert "PermissionError: cleanup blocked" in caught.value.__notes__[0]


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
