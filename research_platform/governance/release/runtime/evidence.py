from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from research_platform.governance.release.api import ReleaseManifest, ReleaseQualityEvidence
from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes
from .manifest import build_release_manifest


RELEASE_EVIDENCE_FILENAME = "RELEASE_EVIDENCE.json"


class ReleaseEvidenceMismatch(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseEvidence:
    """Location-independent evidence for one immutable source release.

    The evidence file is deliberately excluded from the source-tree manifest, otherwise the
    evidence would recursively hash itself.  It binds the source manifest, architecture result,
    regression count and static quality gates into one deterministic identity.
    """

    schema_version: int
    platform_code_version: str
    python_requires: str
    release_manifest_digest: str
    source_tree_sha256: str
    release_file_count: int
    regression_tests_collected: int
    regression_tests_passed: int
    regression_tests_skipped: int
    regression_shard_count: int
    regression_test_inventory_sha256: str
    regression_runtime_sha256: str
    architecture_report_sha256: str
    architecture_clean: bool
    no_degradation_findings: int
    silent_failure_findings: int

    @property
    def clean(self) -> bool:
        return (
            self.architecture_clean
            and self.no_degradation_findings == 0
            and self.silent_failure_findings == 0
            and self.regression_tests_collected > 0
            and self.regression_tests_passed > 0
            and self.regression_tests_passed + self.regression_tests_skipped == self.regression_tests_collected
            and self.regression_shard_count > 0
            and len(self.regression_test_inventory_sha256) == 64
            and len(self.regression_runtime_sha256) == 64
        )

    def digest(self) -> str:
        raw = json.dumps(
            asdict(self),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            asdict(self),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8") + b"\n"



def build_release_evidence(
    root: Path,
    *,
    quality: ReleaseQualityEvidence,
    regression_tests_collected: int,
    regression_tests_passed: int,
    regression_tests_skipped: int,
    regression_shard_count: int,
    regression_test_inventory_sha256: str,
    regression_runtime_sha256: str,
    manifest: ReleaseManifest | None = None,
) -> ReleaseEvidence:
    root = Path(root).resolve()
    resolved_manifest = manifest or build_release_manifest(root)
    return ReleaseEvidence(
        schema_version=2,
        platform_code_version=resolved_manifest.platform_code_version,
        python_requires=resolved_manifest.python_requires,
        release_manifest_digest=resolved_manifest.digest(),
        source_tree_sha256=resolved_manifest.source_tree_sha256,
        release_file_count=len(resolved_manifest.files),
        regression_tests_collected=int(regression_tests_collected),
        regression_tests_passed=int(regression_tests_passed),
        regression_tests_skipped=int(regression_tests_skipped),
        regression_shard_count=int(regression_shard_count),
        regression_test_inventory_sha256=str(regression_test_inventory_sha256),
        regression_runtime_sha256=str(regression_runtime_sha256),
        architecture_report_sha256=quality.architecture_report_sha256,
        architecture_clean=quality.architecture_clean,
        no_degradation_findings=quality.no_degradation_findings,
        silent_failure_findings=quality.silent_failure_findings,
    )


def decode_release_evidence(raw: bytes) -> ReleaseEvidence:
    try:
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("release evidence must be an object")
        return ReleaseEvidence(**payload)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ReleaseEvidenceMismatch("release evidence violates the evidence contract") from exc


def load_release_evidence(path: Path) -> ReleaseEvidence:
    return decode_release_evidence(Path(path).read_bytes())


def write_release_evidence(path: Path, evidence: ReleaseEvidence) -> None:
    atomic_replace_bytes(Path(path), evidence.to_json_bytes())


def verify_release_evidence(
    root: Path,
    evidence: ReleaseEvidence,
    *,
    quality: ReleaseQualityEvidence,
    observed_tests_collected: int | None = None,
    observed_tests_passed: int | None = None,
    observed_tests_skipped: int | None = None,
    observed_shard_count: int | None = None,
    observed_test_inventory_sha256: str | None = None,
    observed_runtime_sha256: str | None = None,
) -> tuple[str, ...]:
    root = Path(root).resolve()
    current = build_release_evidence(
        root,
        quality=quality,
        regression_tests_collected=evidence.regression_tests_collected if observed_tests_collected is None else observed_tests_collected,
        regression_tests_passed=evidence.regression_tests_passed if observed_tests_passed is None else observed_tests_passed,
        regression_tests_skipped=evidence.regression_tests_skipped if observed_tests_skipped is None else observed_tests_skipped,
        regression_shard_count=evidence.regression_shard_count if observed_shard_count is None else observed_shard_count,
        regression_test_inventory_sha256=evidence.regression_test_inventory_sha256 if observed_test_inventory_sha256 is None else observed_test_inventory_sha256,
        regression_runtime_sha256=evidence.regression_runtime_sha256 if observed_runtime_sha256 is None else observed_runtime_sha256,
    )
    errors: list[str] = []
    static_fields = (
        "platform_code_version",
        "python_requires",
        "release_manifest_digest",
        "source_tree_sha256",
        "release_file_count",
        "architecture_report_sha256",
        "architecture_clean",
        "no_degradation_findings",
        "silent_failure_findings",
    )
    for field in static_fields:
        if getattr(current, field) != getattr(evidence, field):
            errors.append(f"release evidence drift: {field}")
    observed_fields = (
        ("regression_tests_collected", observed_tests_collected),
        ("regression_tests_passed", observed_tests_passed),
        ("regression_tests_skipped", observed_tests_skipped),
        ("regression_shard_count", observed_shard_count),
        ("regression_test_inventory_sha256", observed_test_inventory_sha256),
        ("regression_runtime_sha256", observed_runtime_sha256),
    )
    for field, observed in observed_fields:
        if observed is not None and getattr(current, field) != getattr(evidence, field):
            errors.append(f"release evidence drift: {field}")
    if not evidence.clean:
        errors.append("release evidence is not clean")
    return tuple(errors)
