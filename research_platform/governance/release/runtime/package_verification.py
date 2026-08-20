from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import zipfile

from .evidence import RELEASE_EVIDENCE_FILENAME, decode_release_evidence
from .manifest_io import decode_release_manifest


@dataclass(frozen=True, slots=True)
class ReleasePackageVerificationReport:
    clean: bool
    manifest_digest: str | None
    evidence_digest: str | None
    source_tree_sha256: str | None
    file_count: int
    errors: tuple[str, ...]


def verify_release_package(zip_path: Path) -> ReleasePackageVerificationReport:
    """Independently verify a frozen release ZIP using only bytes inside the package."""

    errors: list[str] = []
    manifest_digest: str | None = None
    evidence_digest: str | None = None
    source_tree_sha256: str | None = None
    file_count = 0
    try:
        with zipfile.ZipFile(Path(zip_path), "r") as zf:
            names = zf.namelist()
            if len(names) != len(set(names)):
                errors.append("duplicate ZIP member")
            required = {"RELEASE_MANIFEST.json", RELEASE_EVIDENCE_FILENAME}
            missing_required = sorted(required - set(names))
            for name in missing_required:
                errors.append(f"missing package metadata: {name}")
            if errors:
                return ReleasePackageVerificationReport(False, None, None, None, 0, tuple(errors))

            manifest = decode_release_manifest(zf.read("RELEASE_MANIFEST.json"))
            evidence = decode_release_evidence(zf.read(RELEASE_EVIDENCE_FILENAME))
            manifest_digest = manifest.digest()
            evidence_digest = evidence.digest()
            source_tree_sha256 = manifest.source_tree_sha256
            file_count = len(manifest.files)

            expected_members = {row.path for row in manifest.files} | required
            for name in sorted(expected_members - set(names)):
                errors.append(f"missing package file: {name}")
            for name in sorted(set(names) - expected_members):
                errors.append(f"unexpected package file: {name}")

            for row in manifest.files:
                if row.path not in names:
                    continue
                data = zf.read(row.path)
                if len(data) != row.size:
                    errors.append(f"package size drift: {row.path}")
                    continue
                if hashlib.sha256(data).hexdigest() != row.sha256:
                    errors.append(f"package hash drift: {row.path}")

            tree_raw = "\n".join(
                f"{row.sha256}  {row.path}  {row.size}" for row in manifest.files
            ).encode()
            if hashlib.sha256(tree_raw).hexdigest() != manifest.source_tree_sha256:
                errors.append("package source-tree digest mismatch")
            if evidence.release_manifest_digest != manifest_digest:
                errors.append("package evidence does not bind package manifest")
            if evidence.source_tree_sha256 != manifest.source_tree_sha256:
                errors.append("package evidence source-tree digest mismatch")
            if evidence.release_file_count != len(manifest.files):
                errors.append("package evidence file-count mismatch")
            if evidence.platform_code_version != manifest.platform_code_version:
                errors.append("package evidence version mismatch")
            if evidence.python_requires != manifest.python_requires:
                errors.append("package evidence python requirement mismatch")
            if not evidence.clean:
                errors.append("package evidence is not clean")
    except (OSError, zipfile.BadZipFile, KeyError, ValueError, TypeError) as exc:
        errors.append(f"package decode failed: {type(exc).__qualname__}")

    return ReleasePackageVerificationReport(
        clean=not errors,
        manifest_digest=manifest_digest,
        evidence_digest=evidence_digest,
        source_tree_sha256=source_tree_sha256,
        file_count=file_count,
        errors=tuple(errors),
    )


__all__ = ["ReleasePackageVerificationReport", "verify_release_package"]
