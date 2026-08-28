from __future__ import annotations

import io
from pathlib import Path
import tarfile
import threading

from research_platform.artifact.content.api import (
    ArchiveMaterializationError,
    ArchiveMaterializationRequest,
)
from research_platform.artifact.content.providers import SafeTarArchiveMaterializer


def _archive(path: Path, payload: bytes = b"verified-java\n") -> None:
    with tarfile.open(path, "w:gz") as archive:
        directory = tarfile.TarInfo("runtime")
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        archive.addfile(directory)
        bin_dir = tarfile.TarInfo("runtime/bin")
        bin_dir.type = tarfile.DIRTYPE
        bin_dir.mode = 0o755
        archive.addfile(bin_dir)
        java = tarfile.TarInfo("runtime/bin/java")
        java.size = len(payload)
        java.mode = 0o755
        archive.addfile(java, io.BytesIO(payload))


def _request(archive: Path, destination: Path) -> ArchiveMaterializationRequest:
    return ArchiveMaterializationRequest(
        archive_path=str(archive.resolve()),
        destination=str(destination.resolve()),
        required_relative_paths=("bin/java",),
    )


def test_materialized_tree_is_reverified_after_atomic_publication(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.tar.gz"
    destination = tmp_path / "runtime-home"
    _archive(archive)
    materializer = SafeTarArchiveMaterializer()

    result = materializer.materialize(_request(archive, destination))
    inspection = materializer.inspect(str(destination))

    assert result.tree_sha256 == inspection.tree_sha256
    assert result.file_count == inspection.file_count == 1
    assert result.expanded_size == inspection.expanded_size == len(b"verified-java\n")
    assert (destination / "bin" / "java").read_bytes() == b"verified-java\n"


def test_concurrent_publication_has_one_winner_and_no_overwrite(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.tar.gz"
    destination = tmp_path / "runtime-home"
    _archive(archive)
    barrier = threading.Barrier(2)
    successes = []
    failures: list[ArchiveMaterializationError] = []

    def publish() -> None:
        barrier.wait()
        try:
            successes.append(SafeTarArchiveMaterializer().materialize(_request(archive, destination)))
        except ArchiveMaterializationError as exc:
            failures.append(exc)

    threads = [threading.Thread(target=publish) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].code in {"DESTINATION_EXISTS", "PUBLICATION_BUSY"}
    final = SafeTarArchiveMaterializer().inspect(str(destination))
    assert final.tree_sha256 == successes[0].tree_sha256
    assert (destination / "bin" / "java").read_bytes() == b"verified-java\n"


def test_tree_digest_changes_when_published_content_changes(tmp_path: Path) -> None:
    archive = tmp_path / "runtime.tar.gz"
    destination = tmp_path / "runtime-home"
    _archive(archive)
    materializer = SafeTarArchiveMaterializer()
    result = materializer.materialize(_request(archive, destination))

    (destination / "bin" / "java").write_bytes(b"tampered\n")
    inspection = materializer.inspect(str(destination))

    assert inspection.tree_sha256 != result.tree_sha256
