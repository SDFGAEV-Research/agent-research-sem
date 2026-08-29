from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen

from research_platform.artifact.catalog.api import ArtifactRecord
from research_platform.artifact.content.api.acquisition import (
    ArtifactAcquisitionError,
    ArtifactHttpOpener,
    ArtifactHttpResponse,
    ArtifactAcquisitionPort,
    ArtifactAcquisitionRequest,
    ArtifactAcquisitionResult,
)
from ._publication import (
    PublicationLock,
    PublicationLockBusy,
    PublicationLockUnavailable,
    fsync_directory,
)


HttpOpener = ArtifactHttpOpener


def _default_opener(request: Request, timeout_s: float) -> ArtifactHttpResponse:
    return urlopen(request, timeout=timeout_s)  # type: ignore[return-value]


def _digests(path: Path) -> tuple[str, str, int]:
    sha256 = hashlib.sha256()
    sha1 = hashlib.sha1()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(block)
            sha1.update(block)
            size += len(block)
    return sha256.hexdigest(), sha1.hexdigest(), size


class HttpArtifactAcquirer(ArtifactAcquisitionPort):
    """Streaming HTTP artifact provider with atomic publication and digest proof."""

    def __init__(self, *, opener: HttpOpener | None = None, user_agent: str = "research-platform-artifact/1") -> None:
        if not user_agent.strip():
            raise ValueError("artifact user agent must be non-empty")
        self._opener = opener or _default_opener
        self._user_agent = user_agent

    def acquire(self, request: ArtifactAcquisitionRequest) -> ArtifactAcquisitionResult:
        destination = Path(request.destination).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        guard = destination.with_name(f".{destination.name}.acquire.lock")
        try:
            with PublicationLock(guard):
                return self._acquire_owned(request, destination)
        except PublicationLockBusy as exc:
            raise ArtifactAcquisitionError(
                "PUBLICATION_BUSY",
                f"another acquisition owns the destination transaction: {destination}",
            ) from exc
        except PublicationLockUnavailable as exc:
            raise ArtifactAcquisitionError(
                "PUBLICATION_LOCK_UNAVAILABLE",
                f"artifact acquisition lock is unavailable: {destination}",
            ) from exc

    def _acquire_owned(
        self,
        request: ArtifactAcquisitionRequest,
        destination: Path,
    ) -> ArtifactAcquisitionResult:
        if destination.exists():
            existing = self._verify_existing(destination, request)
            if existing is not None:
                return existing
            if not request.replace_existing:
                raise ArtifactAcquisitionError(
                    "EXISTING_ARTIFACT_MISMATCH",
                    f"existing artifact does not match expected digest: {destination}",
                )

        temporary_path: Path | None = None
        try:
            fd, raw_path = tempfile.mkstemp(
                prefix=f".{destination.name}.", dir=str(destination.parent)
            )
            temporary_path = Path(raw_path)
            sha256_hasher = hashlib.sha256()
            sha1_hasher = hashlib.sha1()
            size = 0
            with os.fdopen(fd, "wb") as output:
                response = self._opener(
                    Request(request.source_url, headers={"User-Agent": self._user_agent}),
                    request.timeout_s,
                )
                try:
                    status = int(getattr(response, "status", 200))
                    if status >= 400:
                        raise ArtifactAcquisitionError("HTTP_STATUS", f"HTTP status {status}")
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        sha256_hasher.update(block)
                        sha1_hasher.update(block)
                        size += len(block)
                finally:
                    response.close()
                output.flush()
                os.fsync(output.fileno())

            sha256 = sha256_hasher.hexdigest()
            sha1 = sha1_hasher.hexdigest()
            self._verify_digests(request, sha256, sha1, size)
            temporary_path.replace(destination)
            fsync_directory(destination.parent)
            temporary_path = None
            return ArtifactAcquisitionResult(
                self._record(request, destination, sha256),
                True,
                sha256,
                sha1,
                size,
            )
        except ArtifactAcquisitionError:
            raise
        except Exception as exc:
            raise ArtifactAcquisitionError(
                "DOWNLOAD_FAILED",
                f"{type(exc).__name__}: {exc}",
            ) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _verify_existing(
        path: Path,
        request: ArtifactAcquisitionRequest,
    ) -> ArtifactAcquisitionResult | None:
        sha256, sha1, size = _digests(path)
        try:
            HttpArtifactAcquirer._verify_digests(request, sha256, sha1, size)
        except ArtifactAcquisitionError:
            return None
        return ArtifactAcquisitionResult(
            HttpArtifactAcquirer._record(request, path, sha256),
            False,
            sha256,
            sha1,
            size,
        )

    @staticmethod
    def _verify_digests(request: ArtifactAcquisitionRequest, sha256: str, sha1: str, size: int) -> None:
        if request.expected_sha256 is not None and sha256.lower() != request.expected_sha256.lower():
            raise ArtifactAcquisitionError(
                "SHA256_MISMATCH",
                f"expected {request.expected_sha256}, got {sha256}",
            )
        if request.expected_sha1 is not None and sha1.lower() != request.expected_sha1.lower():
            raise ArtifactAcquisitionError(
                "SHA1_MISMATCH",
                f"expected {request.expected_sha1}, got {sha1}",
            )
        if request.expected_size is not None and size != request.expected_size:
            raise ArtifactAcquisitionError(
                "SIZE_MISMATCH",
                f"expected {request.expected_size}, got {size}",
            )

    @staticmethod
    def _record(request: ArtifactAcquisitionRequest, path: Path, sha256: str) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=request.artifact_id,
            kind=request.kind,
            scope=request.scope,
            digest=sha256,
            location=str(path),
            producer_component_id=request.producer_component_id,
            producer_operation_id=request.producer_operation_id,
            media_type=request.media_type,
            retention=request.retention,
            metadata=(
                ("source_url", request.source_url),
                *( (("expected_sha1", request.expected_sha1),) if request.expected_sha1 else () ),
                *( (("expected_sha256", request.expected_sha256),) if request.expected_sha256 else () ),
            ),
        )


__all__ = ["ArtifactHttpResponse", "HttpArtifactAcquirer", "HttpOpener"]
