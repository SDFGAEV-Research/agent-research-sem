"""Executable scientific estimands for the SEM study.

The workload matrix emits observations. This module is the only project-owned
place that turns those observations into the seven pre-registered scientific
estimands. Missing evidence stays missing; it is never replaced by a zero or
by a workload-level proxy.

The four estimands that cannot be derived from the generic workload receipt
(``TDP``, ``ELCE``, ``HPEF`` and ``GAG``) cross a typed auxiliary-evidence
port. The port is digest-bound to the compiled plan and source tree, so a
claim cannot accidentally consume a metric file from another run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
from typing import Mapping

from research_platform.platform.kernel import JsonDocument, canonical_digest
from research_platform.experimentation.study.api import ExperimentPlan, StudyMatrixExecutionReport

from .metrics import SEM_PAPER_SCIENTIFIC_METRIC_NAMES


SCIENTIFIC_AUXILIARY_SCHEMA_VERSION = "sem-scientific-auxiliary.v2"
SCIENTIFIC_AUXILIARY_SAMPLE_SCHEMA_VERSION = "sem-scientific-auxiliary-sample.v1"
SCIENTIFIC_AUXILIARY_METRIC_NAMES = ("TDP", "ELCE", "HPEF", "GAG")
_SCIENTIFIC_AUXILIARY_RANGES: dict[str, tuple[float | None, float | None]] = {
    "TDP": (0.0, None),
    "ELCE": (None, None),
    "HPEF": (0.0, 1.0),
    # Gate-to-Audit Generalization Gap is a signed effect difference, not a
    # probability. Negative values are valid when held-out effect exceeds the
    # gate estimate.
    "GAG": (None, None),
}


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScientificMetricComputationError(f"{field} must be a non-empty string")
    return value.strip()


def _required_digest(value: object, field: str) -> str:
    text = _required_text(value, field)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ScientificMetricComputationError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScientificMetricComputationError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ScientificMetricComputationError(f"{field} must be a finite number")
    return number


def _validated_auxiliary_value(name: str, value: object) -> float:
    number = _finite_number(value, f"auxiliary metric {name}")
    lower, upper = _SCIENTIFIC_AUXILIARY_RANGES[name]
    if lower is not None and number < lower:
        raise ScientificMetricComputationError(f"auxiliary metric {name} must be >= {lower}")
    if upper is not None and number > upper:
        raise ScientificMetricComputationError(f"auxiliary metric {name} must be <= {upper}")
    return number


@dataclass(frozen=True, slots=True)
class ScientificAuxiliaryEvidence:
    """Typed evidence for estimands not derivable from workload aggregates."""

    schema_version: str
    evidence_id: str
    producer: str
    source_tree_digest: str
    plan_digest: str
    protocol_digest: str
    binding_digest: str
    values: tuple[tuple[str, float], ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != SCIENTIFIC_AUXILIARY_SCHEMA_VERSION:
            raise ScientificMetricComputationError(
                f"unsupported scientific auxiliary schema: {self.schema_version}"
            )
        _required_text(self.evidence_id, "evidence_id")
        _required_text(self.producer, "producer")
        for field in ("source_tree_digest", "plan_digest", "protocol_digest", "binding_digest"):
            _required_digest(getattr(self, field), field)
        names = tuple(name for name, _ in self.values)
        if names != tuple(sorted(SCIENTIFIC_AUXILIARY_METRIC_NAMES)):
            raise ScientificMetricComputationError(
                "scientific auxiliary values must contain exactly the four declared metrics"
            )
        for name, value in self.values:
            _required_text(name, "auxiliary metric name")
            _validated_auxiliary_value(name, value)
        if not self.evidence_refs or any(not ref.strip() for ref in self.evidence_refs):
            raise ScientificMetricComputationError("scientific auxiliary evidence refs are required")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ScientificMetricComputationError("scientific auxiliary evidence refs must be unique")

    @property
    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True, slots=True)
class ScientificAuxiliarySample:
    """One typed producer observation for the four non-aggregate estimands."""

    seed_id: str
    trajectory_divergence: float
    held_out_causal_effect: float
    held_out_positive_edit_fraction: float
    gate_to_audit_generalization_gap: float

    def __post_init__(self) -> None:
        if not self.seed_id.strip():
            raise ScientificMetricComputationError("auxiliary sample seed_id is required")
        _validated_auxiliary_value("TDP", self.trajectory_divergence)
        _validated_auxiliary_value("ELCE", self.held_out_causal_effect)
        _validated_auxiliary_value("HPEF", self.held_out_positive_edit_fraction)
        _validated_auxiliary_value("GAG", self.gate_to_audit_generalization_gap)


@dataclass(frozen=True, slots=True)
class ScientificAuxiliarySampleEvidence:
    """One immutable run-produced seed sample before cross-seed finalization."""

    schema_version: str
    sample_id: str
    run_id: str
    seed_id: str
    source_tree_digest: str
    plan_digest: str
    trajectory_divergence: float
    held_out_causal_effect: float
    held_out_positive_edit_fraction: float
    gate_to_audit_generalization_gap: float
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != SCIENTIFIC_AUXILIARY_SAMPLE_SCHEMA_VERSION:
            raise ScientificMetricComputationError(
                f"unsupported scientific auxiliary sample schema: {self.schema_version}"
            )
        _required_text(self.sample_id, "sample_id")
        _required_text(self.run_id, "run_id")
        _required_text(self.seed_id, "seed_id")
        _required_digest(self.source_tree_digest, "source_tree_digest")
        _required_digest(self.plan_digest, "plan_digest")
        _validated_auxiliary_value("TDP", self.trajectory_divergence)
        _validated_auxiliary_value("ELCE", self.held_out_causal_effect)
        _validated_auxiliary_value("HPEF", self.held_out_positive_edit_fraction)
        _validated_auxiliary_value("GAG", self.gate_to_audit_generalization_gap)
        if not self.evidence_refs or any(not ref.strip() for ref in self.evidence_refs):
            raise ScientificMetricComputationError(
                "scientific auxiliary sample evidence refs are required"
            )
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ScientificMetricComputationError(
                "scientific auxiliary sample evidence refs must be unique"
            )

    @property
    def digest(self) -> str:
        return canonical_digest(self)

    def sample(self) -> ScientificAuxiliarySample:
        return ScientificAuxiliarySample(
            seed_id=self.seed_id,
            trajectory_divergence=self.trajectory_divergence,
            held_out_causal_effect=self.held_out_causal_effect,
            held_out_positive_edit_fraction=self.held_out_positive_edit_fraction,
            gate_to_audit_generalization_gap=self.gate_to_audit_generalization_gap,
        )


def decode_scientific_auxiliary_sample_evidence(
    document: JsonDocument,
) -> ScientificAuxiliarySampleEvidence:
    if not isinstance(document, Mapping):
        raise ScientificMetricComputationError(
            "scientific auxiliary sample evidence must be an object"
        )
    expected = {
        "schema_version",
        "sample_id",
        "run_id",
        "seed_id",
        "source_tree_digest",
        "plan_digest",
        "trajectory_divergence",
        "held_out_causal_effect",
        "held_out_positive_edit_fraction",
        "gate_to_audit_generalization_gap",
        "evidence_refs",
    }
    if set(document) != expected:
        raise ScientificMetricComputationError(
            "scientific auxiliary sample evidence fields are not exact"
        )
    raw_refs = document["evidence_refs"]
    if not isinstance(raw_refs, list) or any(not isinstance(item, str) for item in raw_refs):
        raise ScientificMetricComputationError(
            "scientific auxiliary sample evidence refs must be a string list"
        )
    return ScientificAuxiliarySampleEvidence(
        schema_version=_required_text(document["schema_version"], "schema_version"),
        sample_id=_required_text(document["sample_id"], "sample_id"),
        run_id=_required_text(document["run_id"], "run_id"),
        seed_id=_required_text(document["seed_id"], "seed_id"),
        source_tree_digest=_required_digest(document["source_tree_digest"], "source_tree_digest"),
        plan_digest=_required_digest(document["plan_digest"], "plan_digest"),
        trajectory_divergence=_validated_auxiliary_value("TDP", document["trajectory_divergence"]),
        held_out_causal_effect=_validated_auxiliary_value("ELCE", document["held_out_causal_effect"]),
        held_out_positive_edit_fraction=_validated_auxiliary_value("HPEF", document["held_out_positive_edit_fraction"]),
        gate_to_audit_generalization_gap=_validated_auxiliary_value("GAG", document["gate_to_audit_generalization_gap"]),
        evidence_refs=tuple(raw_refs),
    )


def load_scientific_auxiliary_sample_evidence(
    path: str | Path,
) -> ScientificAuxiliarySampleEvidence:
    target = Path(path).expanduser().resolve(strict=False)
    if not target.is_file():
        raise ScientificMetricComputationError(
            f"scientific auxiliary sample evidence is missing: {target}"
        )
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScientificMetricComputationError(
            f"scientific auxiliary sample evidence cannot be read: {target}"
        ) from exc
    return decode_scientific_auxiliary_sample_evidence(document)


class DirectoryScientificAuxiliarySampleStore:
    """Typed append-by-seed store for evaluator/audit-produced estimand samples."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve(strict=False)

    def publish(self, sample: ScientificAuxiliarySampleEvidence) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{sample.seed_id}.json"
        payload = asdict(sample)
        payload["evidence_refs"] = list(sample.evidence_refs)
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(raw, encoding="utf-8")
        temporary.replace(target)
        return target

    def load_all(self) -> tuple[ScientificAuxiliarySampleEvidence, ...]:
        if not self.root.is_dir():
            return ()
        return tuple(
            load_scientific_auxiliary_sample_evidence(path)
            for path in sorted(self.root.glob("*.json"))
            if path.is_file()
        )


class ScientificAuxiliaryEvidenceProducer:
    """Produce digest-bound auxiliary evidence from typed runtime samples.

    This is the production boundary for TDP/ELCE/HPEF/GAG.  It deliberately
    accepts no untyped JSON mapping and never fills a missing sample with a
    default.  A caller must provide one complete sample per declared seed.
    """

    def produce(
        self,
        *,
        plan: ExperimentPlan,
        source_tree_digest: str,
        samples: tuple[ScientificAuxiliarySample, ...],
        evidence_refs: tuple[str, ...],
        producer: str,
    ) -> ScientificAuxiliaryEvidence:
        plan.assert_consistent()
        if len(source_tree_digest) != 64 or any(
            char not in "0123456789abcdef" for char in source_tree_digest
        ):
            raise ScientificMetricComputationError("auxiliary producer source_tree_digest is invalid")
        if not samples:
            raise ScientificMetricComputationError("auxiliary producer requires runtime samples")
        expected_seeds = {
            binding.seed_id
            for binding in plan.bindings
            if binding.variant.kind.value in {"control", "treatment"}
        }
        actual_seeds = {sample.seed_id for sample in samples}
        if actual_seeds != expected_seeds:
            raise ScientificMetricComputationError(
                "auxiliary producer samples must cover exactly the primary study seeds"
            )
        if len(samples) != len(actual_seeds):
            raise ScientificMetricComputationError("auxiliary producer samples must be unique by seed")
        count = float(len(samples))
        values = (
            ("ELCE", sum(item.held_out_causal_effect for item in samples) / count),
            ("GAG", sum(item.gate_to_audit_generalization_gap for item in samples) / count),
            ("HPEF", sum(item.held_out_positive_edit_fraction for item in samples) / count),
            ("TDP", sum(item.trajectory_divergence for item in samples) / count),
        )
        return ScientificAuxiliaryEvidence(
            schema_version=SCIENTIFIC_AUXILIARY_SCHEMA_VERSION,
            evidence_id="aux_" + canonical_digest(
                {"plan": plan.plan_digest, "source": source_tree_digest, "values": values}
            )[:32],
            producer=_required_text(producer, "producer"),
            source_tree_digest=source_tree_digest,
            plan_digest=plan.plan_digest,
            protocol_digest=plan.protocol_digest,
            binding_digest=plan.binding_digest,
            values=values,
            evidence_refs=tuple(evidence_refs),
        )



def finalize_scientific_auxiliary_evidence(
    *,
    plan: ExperimentPlan,
    source_tree_digest: str,
    run_id: str,
    sample_store: DirectoryScientificAuxiliarySampleStore,
    output_path: str | Path,
    producer: str = "sem-paper.scientific-auxiliary-finalizer.v1",
) -> ScientificAuxiliaryEvidence:
    """Finalize run-local typed seed samples into the claim-gate receipt.

    No estimator is synthesized here.  The four values must already have been
    produced by the trajectory / held-out audit / governance authorities and
    published as typed seed samples.  This function only validates provenance,
    exact seed coverage and plan/source identity before deterministic aggregation.
    """

    samples = sample_store.load_all()
    if not samples:
        raise ScientificMetricComputationError(
            "no run-local scientific auxiliary samples were published"
        )
    for item in samples:
        if item.run_id != run_id:
            raise ScientificMetricComputationError(
                f"auxiliary sample {item.sample_id!r} belongs to another run"
            )
        if item.source_tree_digest != source_tree_digest:
            raise ScientificMetricComputationError(
                f"auxiliary sample {item.sample_id!r} source digest does not match the run"
            )
        if item.plan_digest != plan.plan_digest:
            raise ScientificMetricComputationError(
                f"auxiliary sample {item.sample_id!r} plan digest does not match the run"
            )
    refs = tuple(
        dict.fromkeys(
            ref
            for item in sorted(samples, key=lambda row: row.seed_id)
            for ref in item.evidence_refs
        )
    )
    evidence = ScientificAuxiliaryEvidenceProducer().produce(
        plan=plan,
        source_tree_digest=source_tree_digest,
        samples=tuple(item.sample() for item in samples),
        evidence_refs=refs,
        producer=producer,
    )
    target = Path(output_path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": evidence.schema_version,
        "evidence_id": evidence.evidence_id,
        "producer": evidence.producer,
        "source_tree_digest": evidence.source_tree_digest,
        "plan_digest": evidence.plan_digest,
        "protocol_digest": evidence.protocol_digest,
        "binding_digest": evidence.binding_digest,
        "values": dict(evidence.values),
        "evidence_refs": list(evidence.evidence_refs),
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return evidence

def decode_scientific_auxiliary_evidence(document: JsonDocument) -> ScientificAuxiliaryEvidence:
    """Decode an exact JSON evidence document without accepting extra fields."""

    if not isinstance(document, Mapping):
        raise ScientificMetricComputationError("scientific auxiliary evidence must be an object")
    expected = {
        "schema_version",
        "evidence_id",
        "producer",
        "source_tree_digest",
        "plan_digest",
        "protocol_digest",
        "binding_digest",
        "values",
        "evidence_refs",
    }
    if set(document) != expected:
        raise ScientificMetricComputationError("scientific auxiliary evidence fields are not exact")
    raw_values = document["values"]
    if not isinstance(raw_values, Mapping) or set(raw_values) != set(SCIENTIFIC_AUXILIARY_METRIC_NAMES):
        raise ScientificMetricComputationError(
            "scientific auxiliary evidence values must contain exactly TDP, ELCE, HPEF and GAG"
        )
    raw_refs = document["evidence_refs"]
    if not isinstance(raw_refs, list) or any(not isinstance(item, str) for item in raw_refs):
        raise ScientificMetricComputationError("scientific auxiliary evidence refs must be a string list")
    return ScientificAuxiliaryEvidence(
        schema_version=_required_text(document["schema_version"], "schema_version"),
        evidence_id=_required_text(document["evidence_id"], "evidence_id"),
        producer=_required_text(document["producer"], "producer"),
        source_tree_digest=_required_digest(document["source_tree_digest"], "source_tree_digest"),
        plan_digest=_required_digest(document["plan_digest"], "plan_digest"),
        protocol_digest=_required_digest(document["protocol_digest"], "protocol_digest"),
        binding_digest=_required_digest(document["binding_digest"], "binding_digest"),
        values=tuple(
            (name, _validated_auxiliary_value(name, raw_values[name]))
            for name in sorted(SCIENTIFIC_AUXILIARY_METRIC_NAMES)
        ),
        evidence_refs=tuple(raw_refs),
    )


def load_scientific_auxiliary_evidence(path: str | Path) -> ScientificAuxiliaryEvidence:
    target = Path(path).expanduser().resolve(strict=False)
    if not target.is_file():
        raise ScientificMetricComputationError(f"scientific auxiliary evidence is missing: {target}")
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScientificMetricComputationError(
            f"scientific auxiliary evidence cannot be read: {target}"
        ) from exc
    return decode_scientific_auxiliary_evidence(document)


def validate_scientific_auxiliary_evidence(
    evidence: ScientificAuxiliaryEvidence,
    *,
    expected_source_tree_digest: str | None = None,
    expected_plan_digest: str | None = None,
    expected_protocol_digest: str | None = None,
    expected_binding_digest: str | None = None,
) -> ScientificAuxiliaryEvidence:
    for label, expected, actual in (
        ("source tree", expected_source_tree_digest, evidence.source_tree_digest),
        ("plan", expected_plan_digest, evidence.plan_digest),
        ("protocol", expected_protocol_digest, evidence.protocol_digest),
        ("binding", expected_binding_digest, evidence.binding_digest),
    ):
        if expected is not None and actual != expected:
            raise ScientificMetricComputationError(
                f"scientific auxiliary evidence {label} digest does not match the run"
            )
    return evidence


@dataclass(frozen=True, slots=True)
class ScientificMetricReport:
    plan_digest: str
    protocol_digest: str
    metric_manifest_digest: str
    values: tuple[tuple[str, float], ...]
    missing: tuple[str, ...]
    blockers: tuple[str, ...]
    auxiliary_evidence_digest: str | None = None

    @property
    def eligible(self) -> bool:
        return not self.missing and not self.blockers

    @property
    def digest(self) -> str:
        return canonical_digest(self)


class ScientificMetricComputationError(ValueError):
    """The report cannot be interpreted under the frozen estimand contract."""


@dataclass(frozen=True, slots=True)
class StatisticalComparison:
    comparison_id: str
    treatment_provider: str
    reference_provider: str
    estimate: float
    sample_count: int
    standard_error: float
    ci_lower: float
    ci_upper: float
    raw_p_value: float
    adjusted_p_value: float
    correction_method: str


@dataclass(frozen=True, slots=True)
class ScientificStatisticalReport:
    """Paired effects, uncertainty, and multiplicity metadata for the plan."""

    plan_digest: str
    effects: tuple[tuple[str, float, int, float, float, float], ...]
    missing: tuple[str, ...]
    blockers: tuple[str, ...]
    comparisons: tuple[StatisticalComparison, ...] = ()
    missingness_policy: str = "complete_case_paired_observations"
    blocked_task_policy: str = "blocked_tasks_invalidate_scientific_claim"

    @property
    def eligible(self) -> bool:
        return not self.missing and not self.blockers

    @property
    def digest(self) -> str:
        return canonical_digest(self)


def _implementation(provider_id: str) -> str:
    value = provider_id.rsplit(".", 1)[-1]
    return {
        "fixed-memory": "FixedSeed",
        "candidate-memory": "RuleBasedEvolver",
    }.get(value, value)


class SemPaperScientificMetricProvider:
    """Compute the project estimands from a complete compiled study report."""

    def compute(
        self,
        *,
        plan: ExperimentPlan,
        report: StudyMatrixExecutionReport,
        auxiliary_evidence: ScientificAuxiliaryEvidence | None = None,
    ) -> ScientificMetricReport:
        plan.assert_consistent()
        if report.plan_digest != plan.plan_digest:
            raise ScientificMetricComputationError("scientific metric report is not bound to the experiment plan")
        if report.protocol_digest != plan.protocol_digest:
            raise ScientificMetricComputationError("scientific metric report protocol digest mismatches the plan")

        bindings = {item.variant.variant_id: item for item in plan.bindings}
        seed_groups: dict[str, dict[str, str]] = {}
        for variant_id, binding in bindings.items():
            implementation = _implementation(binding.provider_id)
            if implementation not in {"FixedSeed", "SelfEvolve"}:
                continue
            seed_groups.setdefault(binding.seed_id, {})[implementation] = variant_id

        blockers: list[str] = []
        expected_seeds: set[str] = set()
        for seed_id, implementations in sorted(seed_groups.items()):
            if {"FixedSeed", "SelfEvolve"}.issubset(implementations):
                expected_seeds.add(seed_id)
            else:
                blockers.append(f"incomplete_fixed_self_pair:{seed_id}")

        # Build estimands from the same matched environment units used by the
        # inferential statistics.  Seed-C / Seed-X are matched architecture
        # factors inside each repetition, not independent lifetime units.
        observation_metrics: dict[tuple[str, int], dict[str, float]] = {}
        for observation in report.observations:
            key = (observation.assignment.variant_id, observation.assignment.repetition)
            if key in observation_metrics:
                blockers.append(
                    f"duplicate_metric_observation:{observation.assignment.variant_id}:"
                    f"{observation.assignment.repetition}"
                )
                continue
            observation_metrics[key] = dict(observation.metrics)

        matched_lifetime_deltas: list[float] = []
        matched_self_utilities: list[float] = []
        for repetition in range(plan.protocol.repetitions):
            seed_deltas: dict[str, float] = {}
            seed_self_utilities: dict[str, float] = {}
            for seed_id in sorted(expected_seeds):
                implementations = seed_groups[seed_id]
                fixed_metrics = observation_metrics.get((implementations["FixedSeed"], repetition))
                self_metrics = observation_metrics.get((implementations["SelfEvolve"], repetition))
                fixed = fixed_metrics.get("utility_mean") if fixed_metrics else None
                self_value = self_metrics.get("utility_mean") if self_metrics else None
                if fixed is None or self_value is None:
                    blockers.append(f"missing_utility_mean:{seed_id}:{repetition}")
                    continue
                if (
                    float(fixed_metrics.get("task_blocked_total", 0.0)) > 0
                    or float(self_metrics.get("task_blocked_total", 0.0)) > 0
                ):
                    blockers.append(f"blocked_fixed_self_pair:{seed_id}:{repetition}")
                    continue
                seed_deltas[seed_id] = float(self_value) - float(fixed)
                seed_self_utilities[seed_id] = float(self_value)

            if set(seed_deltas) != expected_seeds:
                blockers.append(
                    "incomplete_matched_environment_unit:FixedSeed:SelfEvolve:"
                    f"{repetition}:expected={','.join(sorted(expected_seeds))}:"
                    f"actual={','.join(sorted(seed_deltas))}"
                )
                continue
            if not expected_seeds:
                continue
            matched_lifetime_deltas.append(
                sum(seed_deltas[seed_id] for seed_id in sorted(expected_seeds))
                / len(expected_seeds)
            )
            matched_self_utilities.append(
                sum(seed_self_utilities[seed_id] for seed_id in sorted(expected_seeds))
                / len(expected_seeds)
            )

        values: dict[str, float] = {}
        if matched_lifetime_deltas:
            values["LTE_SR"] = sum(matched_lifetime_deltas) / len(matched_lifetime_deltas)
            values["CLU"] = sum(matched_self_utilities) / len(matched_self_utilities)
            # Frozen v0.16 definition: LPI = P(Delta_life > 0), not a mean
            # relative effect.  The empirical probability is over independent
            # pre-registered lifetime/environment units.
            values["LPI"] = (
                sum(1 for delta in matched_lifetime_deltas if delta > 0.0)
                / len(matched_lifetime_deltas)
            )

        if auxiliary_evidence is not None:
            if auxiliary_evidence.plan_digest != plan.plan_digest:
                blockers.append("auxiliary_evidence_plan_digest_mismatch")
            if auxiliary_evidence.protocol_digest != plan.protocol_digest:
                blockers.append("auxiliary_evidence_protocol_digest_mismatch")
            if auxiliary_evidence.binding_digest != plan.binding_digest:
                blockers.append("auxiliary_evidence_binding_digest_mismatch")
            for name, value in auxiliary_evidence.values:
                if not math.isfinite(float(value)):
                    blockers.append(f"non_finite_auxiliary_metric:{name}")
                else:
                    values[name] = float(value)

        missing = tuple(name for name in SEM_PAPER_SCIENTIFIC_METRIC_NAMES if name not in values)
        auxiliary_digest = auxiliary_evidence.digest if auxiliary_evidence is not None else None
        manifest_digest = canonical_digest(
            {
                "plan_digest": plan.plan_digest,
                "protocol_digest": plan.protocol_digest,
                "binding_digest": plan.binding_digest,
                "auxiliary_evidence_digest": auxiliary_digest,
                "values": tuple(sorted(values.items())),
                "missing": missing,
                "blockers": tuple(blockers),
            }
        )
        return ScientificMetricReport(
            plan_digest=plan.plan_digest,
            protocol_digest=plan.protocol_digest,
            metric_manifest_digest=manifest_digest,
            values=tuple(sorted(values.items())),
            missing=missing,
            blockers=tuple(blockers),
            auxiliary_evidence_digest=auxiliary_digest,
        )

    def compute_statistics(
        self,
        *,
        plan: ExperimentPlan,
        report: StudyMatrixExecutionReport,
    ) -> ScientificStatisticalReport:
        """Compute complete-case paired effects for every declared Core-6 arm pair.

        Primary LTE_SR remains the Self-vs-Fixed comparison. Rule-based arms are
        retained as explicit secondary comparisons and all pairwise p-values
        receive Holm adjustment; no arm is collapsed by ``VariantKind``.
        """

        plan.assert_consistent()
        if report.plan_digest != plan.plan_digest:
            raise ScientificMetricComputationError("statistical report is not bound to the experiment plan")
        if report.protocol_digest != plan.protocol_digest:
            raise ScientificMetricComputationError("statistical report protocol digest mismatches the plan")
        bindings = {item.variant.variant_id: item for item in plan.bindings}
        groups: dict[str, dict[str, str]] = {}
        for variant_id, binding in bindings.items():
            implementation = _implementation(binding.provider_id)
            if implementation in {"FixedSeed", "RuleBasedEvolver", "SelfEvolve"}:
                groups.setdefault(binding.seed_id, {})[implementation] = variant_id
        observations = {
            (item.assignment.variant_id, item.assignment.repetition): dict(item.metrics)
            for item in report.observations
        }
        # Repetition/environment-unit is the independent statistical unit.
        # Seed-C and Seed-X are matched factors *within* that unit and must be
        # averaged before variance/SE/CI/p-value estimation.  Pooling the two
        # seed deltas would pseudoreplicate N (e.g. 12 repetitions -> 24).
        seed_pair_values: dict[
            tuple[str, str], dict[int, dict[str, float]]
        ] = {}
        blockers: list[str] = []
        for seed_id, variants in sorted(groups.items()):
            implementations = tuple(
                name for name in ("FixedSeed", "RuleBasedEvolver", "SelfEvolve") if name in variants
            )
            for reference_index, reference in enumerate(implementations):
                for treatment in implementations[reference_index + 1 :]:
                    by_repetition = seed_pair_values.setdefault(
                        (treatment, reference), {}
                    )
                    for repetition in range(plan.protocol.repetitions):
                        reference_metrics = observations.get((variants[reference], repetition))
                        treatment_metrics = observations.get((variants[treatment], repetition))
                        reference_utility = reference_metrics.get("utility_mean") if reference_metrics else None
                        treatment_utility = treatment_metrics.get("utility_mean") if treatment_metrics else None
                        if reference_utility is None or treatment_utility is None:
                            blockers.append(f"missing_paired_observation:{seed_id}:{reference}:{treatment}:{repetition}")
                            continue
                        if (
                            float(reference_metrics.get("task_blocked_total", 0.0)) > 0
                            or float(treatment_metrics.get("task_blocked_total", 0.0)) > 0
                        ):
                            blockers.append(f"blocked_paired_observation:{seed_id}:{reference}:{treatment}:{repetition}")
                            continue
                        by_repetition.setdefault(repetition, {})[seed_id] = (
                            float(treatment_utility) - float(reference_utility)
                        )

        pair_values: dict[tuple[str, str], list[float]] = {}
        for pair, by_repetition in sorted(seed_pair_values.items()):
            treatment, reference = pair
            expected_seeds = {
                seed_id
                for seed_id, variants in groups.items()
                if treatment in variants and reference in variants
            }
            unit_values: list[float] = []
            for repetition in range(plan.protocol.repetitions):
                seed_values = by_repetition.get(repetition, {})
                if set(seed_values) != expected_seeds:
                    blockers.append(
                        "incomplete_matched_environment_unit:"
                        f"{reference}:{treatment}:{repetition}:"
                        f"expected={','.join(sorted(expected_seeds))}:"
                        f"actual={','.join(sorted(seed_values))}"
                    )
                    continue
                unit_values.append(
                    sum(seed_values[seed_id] for seed_id in sorted(expected_seeds))
                    / len(expected_seeds)
                )
            pair_values[pair] = unit_values

        missing: list[str] = []
        if not pair_values or not pair_values.get(("SelfEvolve", "FixedSeed")):
            missing.extend(("paired_effect", "paired_effect_ci"))

        raw_comparisons: list[StatisticalComparison] = []
        for (treatment, reference), values in sorted(pair_values.items()):
            if not values:
                continue
            count = len(values)
            estimate = sum(values) / count
            variance = sum((value - estimate) ** 2 for value in values) / (count - 1) if count > 1 else 0.0
            standard_error = math.sqrt(variance / count)
            margin = 1.96 * standard_error
            if standard_error <= 1e-12:
                raw_p = 0.0 if abs(estimate) > 1e-12 else 1.0
            else:
                raw_p = math.erfc(abs(estimate / standard_error) / math.sqrt(2.0))
            raw_comparisons.append(
                StatisticalComparison(
                    comparison_id=f"{treatment}_vs_{reference}",
                    treatment_provider=treatment,
                    reference_provider=reference,
                    estimate=estimate,
                    sample_count=count,
                    standard_error=standard_error,
                    ci_lower=estimate - margin,
                    ci_upper=estimate + margin,
                    raw_p_value=min(1.0, max(0.0, raw_p)),
                    adjusted_p_value=0.0,
                    correction_method="holm_bonferroni",
                )
            )

        ordered = sorted(enumerate(raw_comparisons), key=lambda item: item[1].raw_p_value)
        adjusted: dict[int, float] = {}
        previous = 0.0
        count_comparisons = len(ordered)
        for rank, (index, comparison) in enumerate(ordered):
            value = min(1.0, comparison.raw_p_value * (count_comparisons - rank))
            previous = max(previous, value)
            adjusted[index] = previous
        comparisons = tuple(
            replace(comparison, adjusted_p_value=adjusted[index])
            for index, comparison in enumerate(raw_comparisons)
        )
        rows = tuple(
            (
                "LTE_SR" if item.comparison_id == "SelfEvolve_vs_FixedSeed" else item.comparison_id,
                item.estimate,
                item.sample_count,
                item.standard_error,
                item.ci_lower,
                item.ci_upper,
            )
            for item in comparisons
        )
        return ScientificStatisticalReport(
            plan_digest=plan.plan_digest,
            effects=rows,
            missing=tuple(missing),
            blockers=tuple(dict.fromkeys(blockers)),
            comparisons=comparisons,
        )


__all__ = [
    "SCIENTIFIC_AUXILIARY_METRIC_NAMES",
    "SCIENTIFIC_AUXILIARY_SCHEMA_VERSION",
    "SCIENTIFIC_AUXILIARY_SAMPLE_SCHEMA_VERSION",
    "ScientificAuxiliaryEvidence",
    "ScientificAuxiliarySample",
    "ScientificAuxiliarySampleEvidence",
    "DirectoryScientificAuxiliarySampleStore",
    "ScientificAuxiliaryEvidenceProducer",
    "ScientificMetricComputationError",
    "ScientificMetricReport",
    "ScientificStatisticalReport",
    "StatisticalComparison",
    "SemPaperScientificMetricProvider",
    "decode_scientific_auxiliary_evidence",
    "decode_scientific_auxiliary_sample_evidence",
    "load_scientific_auxiliary_evidence",
    "load_scientific_auxiliary_sample_evidence",
    "finalize_scientific_auxiliary_evidence",
    "validate_scientific_auxiliary_evidence",
]
