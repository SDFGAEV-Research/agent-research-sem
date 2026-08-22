"""Pure deployment-plan interpretation over captured capability facts."""

from __future__ import annotations

from research_platform.model.qualification.api import (
    BackendCandidatePlan,
    CandidateDecision,
    DeploymentCapabilityFacts,
    DeploymentQualificationPlan,
    DeploymentQualificationRequest,
    InstallPackage,
)


PYPI_SIMPLE = "https://pypi.org/simple"


class DeploymentQualificationResolver:
    """Turn immutable facts into an explainable, installable candidate plan.

    This implementation intentionally does not install packages or start a
    process.  It selects at most one *plan candidate* for this composition
    request; runtime fallback is not part of this module.
    """

    def resolve(
        self,
        request: DeploymentQualificationRequest,
        facts: DeploymentCapabilityFacts,
    ) -> DeploymentQualificationPlan:
        candidates = tuple(self._candidate(backend, request, facts) for backend in request.backends)
        selected = next(
            (item.backend for item in candidates if item.decision is CandidateDecision.ACCEPTED),
            None,
        )
        return DeploymentQualificationPlan(
            request_digest=request.digest(),
            facts_digest=facts.digest(),
            candidates=candidates,
            selected_backend=selected,
        )

    def _candidate(
        self,
        backend: str,
        request: DeploymentQualificationRequest,
        facts: DeploymentCapabilityFacts,
    ) -> BackendCandidatePlan:
        normalized = backend.strip().lower()
        reasons: list[str] = []
        evidence: list[str] = [f"facts:{facts.digest()}"]
        packages: list[InstallPackage] = []

        if not facts.gpus:
            reasons.append("no NVIDIA GPU was observed")
        elif len(facts.gpus) < request.tensor_parallel:
            reasons.append(
                f"tensor_parallel={request.tensor_parallel} requires at least that many GPUs; "
                f"only {len(facts.gpus)} were observed"
            )
        if facts.model.error or not facts.model.config_present:
            reasons.append("model config.json was not captured; model identity is incomplete")
        if not facts.python.pip_version:
            reasons.append("selected Python interpreter has no usable pip")
        if not facts.python.ensurepip_available:
            reasons.append(
                "selected Python interpreter cannot bootstrap ensurepip; "
                "environment creation must use a managed interpreter with venv support"
            )

        if normalized not in {"sglang", "vllm"}:
            reasons.append(f"no compatibility rule is registered for backend {backend!r}")
            return BackendCandidatePlan(
                backend=backend,
                decision=CandidateDecision.REJECTED,
                version=None,
                packages=(),
                reasons=tuple(reasons),
                evidence_refs=tuple(evidence),
            )

        framework = self._latest(facts, normalized, PYPI_SIMPLE)
        if framework is None:
            reasons.append(f"package index has no usable {normalized} release")
        else:
            packages.append(InstallPackage(normalized, framework, PYPI_SIMPLE))
            evidence.append(f"package-index:{normalized}:{PYPI_SIMPLE}:{framework}")

        if normalized == "sglang":
            kernel = self._latest_kernel(facts)
            if kernel is None:
                reasons.append(
                    "no CUDA-specific sglang-kernel package was found in the official channel set"
                )
            else:
                kernel_version, kernel_index = kernel
                packages.append(InstallPackage("sglang-kernel", kernel_version, kernel_index))
                evidence.append(f"package-index:sglang-kernel:{kernel_index}:{kernel_version}")
                self._check_observed_kernel_architecture(facts, reasons, evidence)

        if facts.cuda.driver_version is None:
            reasons.append("NVIDIA driver version was not observed")
        if facts.cuda.driver_cuda_version is None and facts.cuda.toolkit_version is None:
            reasons.append("neither driver CUDA API nor toolkit version was observed")

        decision = CandidateDecision.REJECTED if reasons else CandidateDecision.ACCEPTED
        return BackendCandidatePlan(
            backend=backend,
            decision=decision,
            version=packages[0].version if packages else None,
            packages=tuple(packages),
            reasons=tuple(reasons),
            evidence_refs=tuple(evidence),
        )

    @staticmethod
    def _latest(
        facts: DeploymentCapabilityFacts,
        package: str,
        index_url: str,
    ) -> str | None:
        item = facts.package_index(package, index_url)
        return item.latest if item is not None else None

    @staticmethod
    def _latest_kernel(
        facts: DeploymentCapabilityFacts,
    ) -> tuple[str, str] | None:
        rows = [
            item
            for item in facts.package_indexes
            if item.package == "sglang-kernel" and item.latest is not None
        ]
        if not rows:
            return None
        # Probe order is the compatibility order; the first usable channel is
        # the one whose exact index is recorded in the plan.
        item = rows[0]
        return item.latest or "", item.index_url

    @staticmethod
    def _check_observed_kernel_architecture(
        facts: DeploymentCapabilityFacts,
        reasons: list[str],
        evidence: list[str],
    ) -> None:
        observed = facts.python.kernel_architectures
        if not observed:
            evidence.append("sglang-kernel-architecture:not-observed")
            reasons.append(
                "architecture-specific sglang-kernel support is not observable yet; "
                "wheel/import qualification is required before materialization"
            )
            return
        evidence.append("sglang-kernel-architecture:" + ",".join(observed))
        required = {
            f"sm{gpu.compute_capability.replace('.', '')}"
            for gpu in facts.gpus
            if gpu.compute_capability
        }
        if required and not required.issubset(set(observed)):
            reasons.append(
                "observed sglang-kernel architectures "
                f"{','.join(observed)} do not cover required GPU architectures "
                f"{','.join(sorted(required))}"
            )


__all__ = ["DeploymentQualificationResolver", "PYPI_SIMPLE"]
