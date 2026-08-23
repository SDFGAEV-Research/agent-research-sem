from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from research_platform.artifact.catalog.api import ArtifactKind, ArtifactRetention
from research_platform.artifact.content.api import (
    ArchiveMaterializationPort,
    ArchiveMaterializationRequest,
    ArtifactAcquisitionPort,
    ArtifactAcquisitionRequest,
    ArtifactHttpOpener,
    ArtifactHttpResponse,
    MaterializedTreeInspectionPort,
)
from research_platform.platform.kernel.durability.durable_file import (
    atomic_replace_bytes,
)
from research_platform.platform.kernel.durability.file_lock import InterprocessFileLock
from research_platform.runtime.toolchain.api import (
    JavaRuntimeProvisioningPort,
    JavaRuntimeProvisioningRequest,
    JavaRuntimeProvisioningResult,
    JavaRuntimeReceipt,
    RuntimeToolchainError,
    parse_java_major,
)

_PROVIDER_ID = "eclipse-adoptium.temurin.v3"
_METADATA_HOST = "api.adoptium.net"
_DOWNLOAD_HOST = "github.com"
_DOWNLOAD_PATH = re.compile(r"^/adoptium/temurin\d+-binaries/releases/download/")
_RECEIPT_SCHEMA = "java-runtime-receipt.v1"
_MAX_METADATA_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class TemurinDownloadInfo:
    feature_version: int
    semantic_version: str
    release_name: str
    metadata_url: str
    source_url: str
    archive_name: str
    sha256: str
    size: int


JavaCommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _default_metadata_opener(
    request: Request, timeout_s: float
) -> ArtifactHttpResponse:
    return urlopen(request, timeout=timeout_s)  # type: ignore[return-value]


def _metadata_url(request: JavaRuntimeProvisioningRequest) -> str:
    query = urlencode(
        {
            "architecture": request.platform.architecture,
            "image_type": "jdk",
            "os": request.platform.operating_system,
            "vendor": "eclipse",
        }
    )
    return f"https://{_METADATA_HOST}/v3/assets/latest/{request.feature_version}/hotspot?{query}"


def _official_download_url(value: str, feature_version: int) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != _DOWNLOAD_HOST
        or _DOWNLOAD_PATH.match(parsed.path) is None
        or not parsed.path.startswith(
            f"/adoptium/temurin{feature_version}-binaries/releases/download/"
        )
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or bool(parsed.query)
        or bool(parsed.fragment)
    ):
        raise RuntimeToolchainError(
            "UNTRUSTED_DOWNLOAD_URL",
            f"Temurin package URL is not an official Adoptium release asset: {value}",
        )
    return value


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _receipt_document(receipt: JavaRuntimeReceipt) -> bytes:
    body = {"schema": _RECEIPT_SCHEMA, "payload": asdict(receipt)}
    canonical = json.dumps(
        body,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    document = {**body, "sha256": hashlib.sha256(canonical).hexdigest()}
    return (
        json.dumps(
            document,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _load_receipt(path: Path) -> JavaRuntimeReceipt:
    try:
        document = json.loads(path.read_bytes())
        body = {"schema": document["schema"], "payload": document["payload"]}
        canonical = json.dumps(
            body,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if body["schema"] != _RECEIPT_SCHEMA:
            raise ValueError("schema mismatch")
        if hashlib.sha256(canonical).hexdigest() != document.get("sha256"):
            raise ValueError("document checksum mismatch")
        if not isinstance(body["payload"], Mapping):
            raise TypeError("receipt payload is not an object")
        return JavaRuntimeReceipt(**dict(body["payload"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeToolchainError(
            "RECEIPT_INVALID",
            f"Java runtime receipt cannot be trusted: {type(exc).__name__}: {exc}",
        ) from exc


class EclipseAdoptiumTemurinProvider(JavaRuntimeProvisioningPort):
    """Official Temurin adapter over generic acquisition and tar materialization."""

    def __init__(
        self,
        acquisition: ArtifactAcquisitionPort,
        materialization: ArchiveMaterializationPort,
        tree_inspection: MaterializedTreeInspectionPort,
        *,
        metadata_opener: ArtifactHttpOpener | None = None,
        command_runner: JavaCommandRunner = subprocess.run,
        user_agent: str = "research-platform-java-toolchain/1",
    ) -> None:
        if not user_agent.strip():
            raise ValueError("Java runtime user agent must be non-empty")
        self._acquisition = acquisition
        self._materialization = materialization
        self._tree_inspection = tree_inspection
        self._metadata_opener = metadata_opener or _default_metadata_opener
        self._command_runner = command_runner
        self._user_agent = user_agent

    def resolve(self, request: JavaRuntimeProvisioningRequest) -> TemurinDownloadInfo:
        metadata_url = _metadata_url(request)
        try:
            response = self._metadata_opener(
                Request(metadata_url, headers={"User-Agent": self._user_agent}),
                min(request.timeout_s, 30.0),
            )
            try:
                status = int(getattr(response, "status", 200))
                if status >= 400:
                    raise RuntimeToolchainError(
                        "METADATA_HTTP_STATUS",
                        f"HTTP status {status} from {metadata_url}",
                    )
                raw = response.read(_MAX_METADATA_BYTES + 1)
                if len(raw) > _MAX_METADATA_BYTES:
                    raise RuntimeToolchainError(
                        "METADATA_SIZE_LIMIT",
                        f"Temurin metadata exceeds {_MAX_METADATA_BYTES} bytes",
                    )
                payload = json.loads(raw.decode("utf-8"))
            finally:
                response.close()
        except RuntimeToolchainError:
            raise
        except Exception as exc:
            raise RuntimeToolchainError(
                "METADATA_FETCH_FAILED",
                f"{type(exc).__name__}: {exc}",
            ) from exc
        if (
            not isinstance(payload, list)
            or len(payload) != 1
            or not isinstance(payload[0], Mapping)
        ):
            raise RuntimeToolchainError(
                "METADATA_SHAPE_INVALID",
                "Temurin latest-assets response must contain exactly one release object",
            )
        asset = payload[0]
        binary = asset.get("binary")
        # Adoptium's v3 response renamed ``version_data`` to ``version``.
        # Accept the legacy name for recorded fixtures, while validating the
        # current response shape and identity below.
        version_data = asset.get("version")
        if version_data is None:
            version_data = asset.get("version_data")
        package = binary.get("package") if isinstance(binary, Mapping) else None
        if (
            not isinstance(binary, Mapping)
            or not isinstance(version_data, Mapping)
            or not isinstance(package, Mapping)
        ):
            raise RuntimeToolchainError(
                "METADATA_SHAPE_INVALID",
                "Temurin release metadata has no binary, version, or package object",
            )
        if asset.get("vendor") != "eclipse":
            raise RuntimeToolchainError(
                "METADATA_IDENTITY_MISMATCH",
                f"Temurin asset vendor={asset.get('vendor')!r}; expected 'eclipse'",
            )
        expected_fields = {
            "architecture": request.platform.architecture,
            "image_type": "jdk",
            "jvm_impl": "hotspot",
            "os": request.platform.operating_system,
        }
        for name, expected in expected_fields.items():
            if binary.get(name) != expected:
                raise RuntimeToolchainError(
                    "METADATA_IDENTITY_MISMATCH",
                    f"Temurin binary {name}={binary.get(name)!r}; expected {expected!r}",
                )
        semantic_version = str(version_data.get("semver", "")).strip()
        declared_major = version_data.get("major")
        if declared_major is not None:
            try:
                if int(declared_major) != request.feature_version:
                    raise RuntimeToolchainError(
                        "RELEASE_IDENTITY_MISMATCH",
                        f"Temurin declared major {declared_major!r} does not match feature {request.feature_version}",
                    )
            except (TypeError, ValueError) as exc:
                raise RuntimeToolchainError(
                    "RELEASE_IDENTITY_INVALID",
                    "Temurin declared major version is invalid",
                ) from exc
        release_name = str(asset.get("release_name", "")).strip()
        archive_name = str(package.get("name", "")).strip()
        source_url = _official_download_url(
            str(package.get("link", "")).strip(),
            request.feature_version,
        )
        checksum = str(package.get("checksum", "")).lower().strip()
        try:
            size = int(package["size"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeToolchainError(
                "PACKAGE_SIZE_INVALID", "Temurin package size is invalid"
            ) from exc
        if (
            not semantic_version
            or not release_name
            or len(semantic_version) > 128
            or len(release_name) > 256
        ):
            raise RuntimeToolchainError(
                "RELEASE_IDENTITY_INVALID",
                "Temurin release identity is missing or unbounded",
            )
        try:
            semantic_major = int(semantic_version.split(".", 1)[0])
        except ValueError as exc:
            raise RuntimeToolchainError(
                "RELEASE_IDENTITY_INVALID", "Temurin semantic version is invalid"
            ) from exc
        if semantic_major != request.feature_version:
            raise RuntimeToolchainError(
                "RELEASE_IDENTITY_MISMATCH",
                f"Temurin semantic version {semantic_version} does not match feature {request.feature_version}",
            )
        if (
            not archive_name
            or archive_name != Path(archive_name).name
            or not archive_name.endswith(".tar.gz")
            or len(archive_name) > 255
        ):
            raise RuntimeToolchainError(
                "PACKAGE_NAME_INVALID",
                "Temurin package name must be a bounded tar.gz basename",
            )
        if unquote(Path(urlparse(source_url).path).name) != archive_name:
            raise RuntimeToolchainError(
                "PACKAGE_IDENTITY_MISMATCH",
                "Temurin package name does not match the official release asset URL",
            )
        if len(checksum) != 64 or any(
            character not in "0123456789abcdef" for character in checksum
        ):
            raise RuntimeToolchainError(
                "PACKAGE_CHECKSUM_INVALID", "Temurin package SHA-256 is invalid"
            )
        if size <= 0:
            raise RuntimeToolchainError(
                "PACKAGE_SIZE_INVALID", "Temurin package size must be positive"
            )
        return TemurinDownloadInfo(
            request.feature_version,
            semantic_version,
            release_name,
            metadata_url,
            source_url,
            archive_name,
            checksum,
            size,
        )

    def _verify_java(
        self, java_executable: Path, feature_version: int
    ) -> tuple[int, str]:
        if (
            not java_executable.is_file()
            or java_executable.is_symlink()
            or not os.access(java_executable, os.X_OK)
        ):
            raise RuntimeToolchainError(
                "JAVA_EXECUTABLE_INVALID",
                f"materialized Java executable is missing, linked, or not executable: {java_executable}",
            )
        try:
            result = self._command_runner(
                [str(java_executable), "-version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except Exception as exc:
            raise RuntimeToolchainError(
                "JAVA_COMMAND_FAILED",
                f"{type(exc).__name__}: {exc}",
            ) from exc
        output = (result.stderr or result.stdout or "").strip()
        if result.returncode != 0:
            raise RuntimeToolchainError(
                "JAVA_COMMAND_FAILED",
                f"java -version returned {result.returncode}: {output}",
            )
        major = parse_java_major(output)
        if major != feature_version:
            raise RuntimeToolchainError(
                "JAVA_VERSION_MISMATCH",
                f"materialized Java major is {major}; expected exactly {feature_version}",
            )
        return major, output

    def _reuse(
        self,
        request: JavaRuntimeProvisioningRequest,
        destination: Path,
        archive_path: Path,
        receipt_path: Path,
    ) -> JavaRuntimeProvisioningResult:
        if receipt_path.is_symlink():
            raise RuntimeToolchainError(
                "RECEIPT_INVALID",
                f"Java runtime receipt must not be a symlink: {receipt_path}",
            )
        receipt = _load_receipt(receipt_path)
        _official_download_url(receipt.source_url, request.feature_version)
        expected_metadata_url = _metadata_url(request)
        expected_java = destination / "bin" / "java"
        expected = (
            _PROVIDER_ID,
            request.feature_version,
            request.platform.operating_system,
            request.platform.architecture,
            expected_metadata_url,
            str(archive_path),
            str(destination),
            str(expected_java),
        )
        actual = (
            receipt.provider_id,
            receipt.feature_version,
            receipt.operating_system,
            receipt.architecture,
            receipt.metadata_url,
            receipt.archive_path,
            receipt.java_home,
            receipt.java_executable,
        )
        if actual != expected:
            raise RuntimeToolchainError(
                "RECEIPT_IDENTITY_MISMATCH",
                "cached Java runtime receipt does not match the requested platform or paths",
            )
        if not archive_path.is_file() or archive_path.is_symlink():
            raise RuntimeToolchainError(
                "ARCHIVE_MISSING", f"cached Java archive is missing: {archive_path}"
            )
        archive_sha256, archive_size = _sha256_file(archive_path)
        if (archive_sha256, archive_size) != (
            receipt.archive_sha256,
            receipt.archive_size,
        ):
            raise RuntimeToolchainError(
                "ARCHIVE_DRIFT", "cached Java archive digest or size changed"
            )
        executable_sha256, _ = _sha256_file(expected_java)
        if executable_sha256 != receipt.java_executable_sha256:
            raise RuntimeToolchainError(
                "JAVA_EXECUTABLE_DRIFT", "cached Java executable changed"
            )
        java_major, version_output = self._verify_java(
            expected_java, request.feature_version
        )
        if (
            java_major != receipt.java_major
            or hashlib.sha256(version_output.encode("utf-8")).hexdigest()
            != receipt.java_version_output_sha256
        ):
            raise RuntimeToolchainError(
                "JAVA_VERSION_DRIFT", "cached Java version output changed"
            )
        # Some official JDK distributions perform a one-time, in-place
        # runtime initialization during the first ``java -version`` call.
        # Verify the final tree after that probe so this initialization is
        # captured in the receipt while subsequent reuse remains fail-closed.
        tree = self._tree_inspection.inspect(str(destination))
        if (
            tree.tree_sha256,
            tree.file_count,
            tree.expanded_size,
        ) != (
            receipt.materialized_tree_sha256,
            receipt.materialized_file_count,
            receipt.materialized_size,
        ):
            raise RuntimeToolchainError(
                "RUNTIME_TREE_DRIFT", "cached Java runtime tree changed"
            )
        return JavaRuntimeProvisioningResult(receipt, False, False)

    def provision(
        self,
        request: JavaRuntimeProvisioningRequest,
    ) -> JavaRuntimeProvisioningResult:
        destination = Path(request.destination).resolve()
        archive_path = Path(request.archive_path).resolve()
        receipt_path = Path(request.receipt_path).resolve()
        if len({destination, archive_path, receipt_path}) != 3:
            raise RuntimeToolchainError(
                "CACHE_LAYOUT_INVALID",
                "Java runtime archive, destination, and receipt paths must be distinct",
            )
        if destination in archive_path.parents or destination in receipt_path.parents:
            raise RuntimeToolchainError(
                "CACHE_LAYOUT_INVALID",
                "Java runtime archive and receipt must be outside the materialized tree",
            )
        lock_path = receipt_path.with_name(receipt_path.name + ".lock")
        with InterprocessFileLock(lock_path):
            return self._provision_locked(
                request,
                destination,
                archive_path,
                receipt_path,
            )

    def _provision_locked(
        self,
        request: JavaRuntimeProvisioningRequest,
        destination: Path,
        archive_path: Path,
        receipt_path: Path,
    ) -> JavaRuntimeProvisioningResult:
        present = tuple(
            path.exists() or path.is_symlink()
            for path in (destination, archive_path, receipt_path)
        )
        if any(present):
            if not all(present):
                raise RuntimeToolchainError(
                    "CACHE_STATE_INCOMPLETE",
                    "Java runtime cache must contain the archive, materialized tree, and receipt together",
                )
            return self._reuse(request, destination, archive_path, receipt_path)

        info = self.resolve(request)
        acquisition = self._acquisition.acquire(
            ArtifactAcquisitionRequest(
                artifact_id=(
                    f"java.temurin.{info.semantic_version}."
                    f"{request.platform.operating_system}.{request.platform.architecture}"
                ),
                source_url=info.source_url,
                destination=str(archive_path),
                scope=request.scope,
                kind=ArtifactKind.RUNTIME,
                producer_component_id="runtime.toolchain.java.temurin",
                producer_operation_id=request.producer_operation_id,
                media_type="application/gzip",
                retention=ArtifactRetention.PROJECT,
                expected_sha256=info.sha256,
                expected_size=info.size,
                timeout_s=request.timeout_s,
            )
        )
        materialized = self._materialization.materialize(
            ArchiveMaterializationRequest(
                archive_path=str(archive_path),
                destination=str(destination),
                required_relative_paths=("bin/java",),
            )
        )
        java_executable = destination / "bin" / "java"
        java_major, version_output = self._verify_java(
            java_executable, request.feature_version
        )
        # The probe above may perform a distribution-specific one-time
        # initialization. Persist the digest of the final executable tree,
        # not only the bytes that were present immediately after extraction.
        materialized = self._tree_inspection.inspect(str(destination))
        executable_sha256, _ = _sha256_file(java_executable)
        receipt = JavaRuntimeReceipt(
            provider_id=_PROVIDER_ID,
            feature_version=request.feature_version,
            semantic_version=info.semantic_version,
            release_name=info.release_name,
            operating_system=request.platform.operating_system,
            architecture=request.platform.architecture,
            metadata_url=info.metadata_url,
            source_url=info.source_url,
            archive_path=str(archive_path),
            archive_sha256=acquisition.sha256,
            archive_size=acquisition.size,
            java_home=str(destination),
            java_executable=str(java_executable),
            java_executable_sha256=executable_sha256,
            materialized_tree_sha256=materialized.tree_sha256,
            materialized_file_count=materialized.file_count,
            materialized_size=materialized.expanded_size,
            java_major=java_major,
            java_version_output_sha256=hashlib.sha256(
                version_output.encode("utf-8")
            ).hexdigest(),
        )
        atomic_replace_bytes(receipt_path, _receipt_document(receipt))
        return JavaRuntimeProvisioningResult(
            receipt,
            acquisition.downloaded,
            True,
        )


__all__ = ["EclipseAdoptiumTemurinProvider", "JavaCommandRunner", "TemurinDownloadInfo"]
