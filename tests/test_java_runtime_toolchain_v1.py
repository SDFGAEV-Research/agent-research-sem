from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
from io import BytesIO
from pathlib import Path

import pytest

from research_platform.artifact.content.api import (
    ArchiveMaterializationError,
    ArchiveMaterializationRequest,
)
from research_platform.artifact.content.composition import compose_artifact_acquisition
from research_platform.artifact.content.providers import SafeTarArchiveMaterializer
from research_platform.runtime.toolchain.api import (
    JavaRuntimePlatform,
    JavaRuntimeProvisioningRequest,
    RuntimeToolchainError,
)
from research_platform.runtime.toolchain.composition import (
    compose_eclipse_adoptium_java_runtime,
)
from research_platform.scope.api import PLATFORM_SCOPE


class _Response:
    status = 200

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, size: int = -1) -> bytes:
        del size
        payload, self._payload = self._payload, b""
        return payload

    def close(self) -> None:
        pass


def _tar_payload(
    *,
    unsafe_member: str | None = None,
    unsafe_link: str | None = None,
) -> bytes:
    output = BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name in ("jdk-21.0.8", "jdk-21.0.8/bin"):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            archive.addfile(info)
        java = b"verified-java-placeholder\n"
        info = tarfile.TarInfo("jdk-21.0.8/bin/java")
        info.size = len(java)
        info.mode = 0o755
        archive.addfile(info, BytesIO(java))
        if unsafe_member is not None:
            data = b"escape"
            info = tarfile.TarInfo(unsafe_member)
            info.size = len(data)
            info.mode = 0o644
            archive.addfile(info, BytesIO(data))
        if unsafe_link is not None:
            info = tarfile.TarInfo("jdk-21.0.8/escape-link")
            info.type = tarfile.SYMTYPE
            info.linkname = unsafe_link
            info.mode = 0o777
            archive.addfile(info)
    return output.getvalue()


def _request(tmp_path: Path) -> JavaRuntimeProvisioningRequest:
    root = tmp_path / "cache"
    return JavaRuntimeProvisioningRequest(
        feature_version=21,
        platform=JavaRuntimePlatform("linux", "x64"),
        archive_path=str((root / "temurin.tar.gz").resolve()),
        destination=str((root / "home").resolve()),
        receipt_path=str((root / "receipt.json").resolve()),
        scope=PLATFORM_SCOPE,
        producer_operation_id="test-operation",
    )


def test_temurin_runtime_is_verified_materialized_and_reused_without_metadata_network(
    tmp_path: Path,
) -> None:
    payload = _tar_payload()
    checksum = hashlib.sha256(payload).hexdigest()
    source_url = (
        "https://github.com/adoptium/temurin21-binaries/releases/download/"
        "jdk-21.0.8%2B9/OpenJDK21U-jdk_x64_linux_hotspot_21.0.8_9.tar.gz"
    )
    metadata = [
        {
            "vendor": "eclipse",
            "release_name": "jdk-21.0.8+9",
            "version": {"major": 21, "semver": "21.0.8+9"},
            "binary": {
                "architecture": "x64",
                "image_type": "jdk",
                "jvm_impl": "hotspot",
                "os": "linux",
                "package": {
                    "name": "OpenJDK21U-jdk_x64_linux_hotspot_21.0.8_9.tar.gz",
                    "link": source_url,
                    "checksum": checksum,
                    "size": len(payload),
                },
            },
        }
    ]
    metadata_calls: list[str] = []
    artifact_calls: list[str] = []
    command_calls: list[tuple[str, ...]] = []

    def metadata_opener(request, timeout):
        del timeout
        metadata_calls.append(request.full_url)
        return _Response(json.dumps(metadata).encode("utf-8"))

    def artifact_opener(request, timeout):
        del timeout
        artifact_calls.append(request.full_url)
        return _Response(payload)

    def runner(command, **kwargs):
        del kwargs
        command_calls.append(tuple(command))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="",
            stderr='openjdk version "21.0.8" 2025-07-15\nEclipse Temurin',
        )

    acquisition = compose_artifact_acquisition(opener=artifact_opener)
    materializer = SafeTarArchiveMaterializer()
    assembly = compose_eclipse_adoptium_java_runtime(
        acquisition=acquisition.acquirer,
        materialization=materializer,
        tree_inspection=materializer,
        metadata_opener=metadata_opener,
        command_runner=runner,
    )
    request = _request(tmp_path)

    first = assembly.provisioner.provision(request)
    second = assembly.provisioner.provision(request)

    assert first.archive_downloaded is True
    assert first.materialized is True
    assert second.archive_downloaded is False
    assert second.materialized is False
    assert first.receipt.digest() == second.receipt.digest()
    assert (
        Path(first.receipt.java_executable).read_bytes()
        == b"verified-java-placeholder\n"
    )
    assert Path(request.receipt_path).is_file()
    assert len(metadata_calls) == 1
    assert artifact_calls == [source_url]
    assert len(command_calls) == 2

    Path(first.receipt.java_executable).write_bytes(b"tampered-java\n")
    with pytest.raises(RuntimeToolchainError, match="JAVA_EXECUTABLE_DRIFT"):
        assembly.provisioner.provision(request)


def test_safe_tar_materializer_rejects_path_traversal_without_publication(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    archive_path.write_bytes(_tar_payload(unsafe_member="../escape"))
    destination = tmp_path / "home"

    with pytest.raises(ArchiveMaterializationError, match="UNSAFE_MEMBER_PATH"):
        SafeTarArchiveMaterializer().materialize(
            ArchiveMaterializationRequest(
                archive_path=str(archive_path.resolve()),
                destination=str(destination.resolve()),
                required_relative_paths=("bin/java",),
            )
        )

    assert not destination.exists()
    assert not (tmp_path / "escape").exists()


def test_safe_tar_materializer_rejects_symlink_escaping_single_archive_root(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "unsafe-link.tar.gz"
    archive_path.write_bytes(_tar_payload(unsafe_link="../outside"))
    destination = tmp_path / "home"

    with pytest.raises(ArchiveMaterializationError, match="UNSAFE_LINK_TARGET"):
        SafeTarArchiveMaterializer().materialize(
            ArchiveMaterializationRequest(
                archive_path=str(archive_path.resolve()),
                destination=str(destination.resolve()),
                required_relative_paths=("bin/java",),
            )
        )

    assert not destination.exists()
