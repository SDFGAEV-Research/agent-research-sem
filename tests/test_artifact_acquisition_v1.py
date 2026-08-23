from __future__ import annotations

import hashlib
import json

import pytest

from research_platform.artifact.catalog.api import ArtifactKind
from research_platform.artifact.catalog.runtime import InMemoryArtifactRegistry
from research_platform.artifact.content.api import ArtifactAcquisitionError, ArtifactAcquisitionRequest
from research_platform.artifact.content.composition import compose_artifact_acquisition
from research_platform.environment.minecraft.providers.server_artifact import (
    OfficialMinecraftServerArtifactProvider,
)
from research_platform.environment.minecraft.composition import (
    compose_official_minecraft_server_artifacts,
)
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
    payload = b"minecraft-server-bytes"
    sha1 = hashlib.sha1(payload).hexdigest()
    calls: list[str] = []

    def opener(request, timeout):
        del timeout
        calls.append(request.full_url)
        return _Response(payload)

    assembly = compose_artifact_acquisition(opener=opener)
    request = ArtifactAcquisitionRequest(
        artifact_id="minecraft.server.test",
        source_url="https://piston-data.mojang.com/server.jar",
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
        artifact_id="minecraft.server.bad",
        source_url="https://piston-data.mojang.com/server.jar",
        destination=str(tmp_path / "server.jar"),
        scope=PLATFORM_SCOPE,
        kind=ArtifactKind.RUNTIME,
        producer_component_id="test",
        expected_sha1="0" * 40,
    )
    with pytest.raises(ArtifactAcquisitionError, match="SHA1_MISMATCH"):
        assembly.acquirer.acquire(request)
    assert not (tmp_path / "server.jar").exists()


def test_official_minecraft_adapter_resolves_manifest_and_uses_generic_acquirer(tmp_path) -> None:
    payload = b"official-server"
    sha1 = hashlib.sha1(payload).hexdigest()
    detail_url = "https://piston-meta.mojang.com/v1/packages/detail.json"
    server_url = "https://piston-data.mojang.com/v1/objects/server.jar"
    responses = {
        "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json": {
            "versions": [{"id": "1.21.6", "type": "release", "url": detail_url}],
        },
        detail_url: {"downloads": {"server": {"url": server_url, "sha1": sha1, "size": len(payload)}}},
    }
    metadata_calls: list[str] = []

    def metadata_opener(request, timeout):
        del timeout
        metadata_calls.append(request.full_url)
        return _Response(json.dumps(responses[request.full_url]).encode("utf-8"))

    def artifact_opener(request, timeout):
        del timeout
        assert request.full_url == server_url
        return _Response(payload)

    assembly = compose_artifact_acquisition(opener=artifact_opener)
    provider = OfficialMinecraftServerArtifactProvider(
        assembly.acquirer,
        metadata_opener=metadata_opener,
    )
    result = provider.acquire(
        "1.21.6",
        destination=str(tmp_path / "server.jar"),
        scope=PLATFORM_SCOPE,
        producer_operation_id="test-op",
    )

    assert result.downloaded is True
    assert result.record.artifact_id == "minecraft.server.1.21.6"
    assert result.record.producer_operation_id == "test-op"
    assert metadata_calls == [
        "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json",
        detail_url,
    ]


def test_official_minecraft_artifact_composition_binds_metadata_and_content_openers(tmp_path) -> None:
    payload = b"composed-official-server"
    sha1 = hashlib.sha1(payload).hexdigest()
    detail_url = "https://piston-meta.mojang.com/v1/packages/composed.json"
    server_url = "https://piston-data.mojang.com/v1/objects/composed-server.jar"

    def metadata_opener(request, timeout):
        del timeout
        value = (
            {"versions": [{"id": "1.21.8", "type": "release", "url": detail_url}]}
            if request.full_url.endswith("version_manifest_v2.json")
            else {"downloads": {"server": {"url": server_url, "sha1": sha1, "size": len(payload)}}}
        )
        return _Response(json.dumps(value).encode("utf-8"))

    def artifact_opener(request, timeout):
        del timeout
        assert request.full_url == server_url
        return _Response(payload)

    assembly = compose_official_minecraft_server_artifacts(
        metadata_opener=metadata_opener,
        artifact_opener=artifact_opener,
    )
    result = assembly.provider.acquire(
        "1.21.8",
        destination=str(tmp_path / "server.jar"),
        scope=PLATFORM_SCOPE,
    )

    assert result.downloaded is True
    assert result.sha1 == sha1
