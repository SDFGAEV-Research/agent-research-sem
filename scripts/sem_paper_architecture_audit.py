"""Audit the Paper production boundary before any scientific execution.

This is intentionally a reporting audit, not a bypassable success gate.  It
keeps the remaining architecture/science gaps machine-readable so a future
change cannot hide them behind a green generic architecture gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_platform.governance.architecture.report import build_architecture_report
from research_platform.governance.system_registry.api import system_catalog


@dataclass(frozen=True, slots=True)
class AuditFinding:
    finding_id: str
    severity: str
    status: str
    evidence: str
    required_repair: str


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _python_sources(*roots: Path) -> tuple[Path, ...]:
    return tuple(
        item
        for root in roots
        if root.exists()
        for item in root.rglob("*.py")
        if "__pycache__" not in item.parts
    )


def _contains(sources: tuple[Path, ...], needle: str) -> bool:
    return any(needle in _source(item) for item in sources)


def _count(sources: tuple[Path, ...], needle: str) -> int:
    return sum(_source(item).count(needle) for item in sources)


def _opaque_api_inventory(sources: tuple[Path, ...]) -> tuple[dict[str, object], ...]:
    """Inventory contract payloads, excluding implementation-only setattr calls."""

    pattern = re.compile(
        r"(?::\s*[^#\n]*\bobject\b|->\s*[^#\n]*\bobject\b|"
        r"Mapping\[str,\s*object\]|OperationResult\[object\])"
    )
    rows: list[dict[str, object]] = []
    for item in sources:
        for line_number, line in enumerate(_source(item).splitlines(), start=1):
            if "object.__setattr__" not in line and pattern.search(line):
                rows.append(
                    {
                        "path": str(item.relative_to(ROOT)),
                        "line": line_number,
                        "source": line.strip(),
                    }
                )
    return tuple(rows)


def _opaque_api_count(sources: tuple[Path, ...]) -> int:
    return len(_opaque_api_inventory(sources))


def _declaration_only_leaf_packages() -> tuple[str, ...]:
    descriptors = tuple(system_catalog())
    package_prefixes = tuple(item.package_prefix for item in descriptors)
    packages: list[str] = []
    for descriptor in descriptors:
        package = ROOT.joinpath(*descriptor.package_prefix.split("."))
        if not package.is_dir():
            continue
        # A catalog node is a leaf only when no deeper catalog node owns a
        # descendant package.  The standard api/runtime/providers/composition
        # directories are implementation layers, not catalog children.
        if any(
            other != descriptor.package_prefix
            and other.startswith(descriptor.package_prefix + ".")
            for other in package_prefixes
        ):
            continue
        sources = [
            item
            for item in package.rglob("*.py")
            if item.name != "__init__.py" and "__pycache__" not in item.parts
        ]
        substantive = any(
            re.search(r"\b(?:class|def)\s+[A-Za-z_]", _source(item))
            for item in sources
        )
        if not substantive:
            packages.append(descriptor.package_prefix)
    return tuple(sorted(packages))


def _declaration_only_leaf_count() -> int:
    return len(_declaration_only_leaf_packages())


def _selected_api_sources() -> tuple[Path, ...]:
    return tuple(
        item
        for base in (
            ROOT / "research_platform" / "environment",
            ROOT / "research_platform" / "experimentation",
            ROOT / "research_platform" / "model" / "serving" / "endpoint",
            ROOT / "research_platform" / "experimentation" / "checkpoint",
        )
        for item in base.rglob("api" + "/*.py")
    )


def _surface_inventory(
    *,
    entrypoint: str,
    production_source: str,
    paper_sources: tuple[Path, ...],
    declaration_only_leaf_count: int,
    opaque_count: int,
) -> dict[str, object]:
    """Return evidence for every current Paper/platform completion surface.

    This intentionally reports absence as evidence instead of inferring
    completion from a directory or an exported protocol.  A protocol-only
    seam is useful, but it is not a runnable implementation.
    """

    platform_sources = _python_sources(ROOT / "research_platform")
    all_sources = platform_sources + paper_sources + _python_sources(ROOT / "scripts")
    non_mc_entrypoints = tuple(
        str(path.relative_to(ROOT))
        for path in (ROOT / "scripts").glob("*non*minecraft*.py")
    )
    qualified_closure_artifacts = tuple(
        str(path.relative_to(ROOT))
        for base in (ROOT / "configs", ROOT / "runs", ROOT / "artifacts")
        if base.exists()
        for path in base.rglob("*.json")
        if "closure" in path.name.lower() or "qualified" in path.name.lower()
    )
    t2b_evidence = tuple(
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("T2B_GATE_RESULT.json")
        if "__pycache__" not in path.parts
    )
    evolution_factory_use = tuple(
        str(path.relative_to(ROOT))
        for path in all_sources
        if "PipelineSessionEvolutionFactory(" in _source(path)
        and "class PipelineSessionEvolutionFactory" not in _source(path)
    )
    study_source = _source(ROOT / "projects" / "sem_paper" / "composition" / "study.py")
    full_metric_symbols = tuple(
        symbol
        for symbol in ("LTE_SR", "LPI", "CLU", "TDP", "ELCE", "HPEF", "GAG")
        if _contains(paper_sources, symbol)
    )
    return {
        "entrypoint": {
            "path": "scripts/run_sem_minecraft_experiment.py",
            "lines": len(entrypoint.splitlines()),
            "functions": entrypoint.count("def "),
            "environment_reads": entrypoint.count("os.environ"),
            "typed_run_spec_symbols": sorted(
                symbol
                for symbol in ("RunSpec", "RunSpecification", "ExperimentRunSpec", "OperatorRunRequest")
                if symbol in production_source
            ),
        },
        "generic_experiment_runtime": {
            "run_spec_used": "ExperimentRunSpec" in production_source,
            "run_application_composed": "build_default_experiment_run_application" in production_source,
            "run_application_bound": "run_executor=" in production_source,
            "unit_adapter_passed": "root.execute_run().study_report" in production_source,
        },
        "generic_non_minecraft": {
            "reusable_protocol_present": _contains(
                paper_sources, "class NonMinecraftEnvironmentFactoryPort"
            ),
            "production_entrypoints": non_mc_entrypoints,
            "concrete_provider_symbols": _count(
                paper_sources, "NonMinecraftEnvironmentFactoryPort("
            ),
        },
        "evolution": {
            "stage_contract_present": _contains(
                paper_sources, "class EvolutionStageFactories"
            ),
            "production_factory_construction": evolution_factory_use,
            "production_runtime_factory_argument": "evolution_factory=" in production_source[production_source.find("root, host, log_store = build_runtime(") :],
            "disabled_factory_in_production_entrypoint": "DisabledSessionEvolutionFactory" in production_source,
        },
        "study": {
            "matrix_executor_wired": (
                "StudyMatrixExecutor" in production_source
                or "build_default_experiment_run_application" in production_source
            ),
            "protocol_repetitions_one": bool(
                re.search(r"repetitions\s*:\s*int\s*=\s*1", study_source)
            ) or "repetitions=1" in production_source,
            "variant_count_literal": "variants=(" in study_source,
            "core6_or_rulebased_symbols": sorted(
                symbol
                for symbol in ("Core-6", "Core6", "RuleBasedEvolver", "FixedSeed", "SelfEvolve")
                if _contains(paper_sources, symbol)
            ),
        },
        "metrics": {
            "declared_metric_names": len(re.findall(
                r'^\s*"[a-zA-Z0-9_.]+",?$',
                _source(ROOT / "projects" / "sem_paper" / "composition" / "study.py"),
                flags=re.MULTILINE,
            )),
            "scientific_claim_gate_present": "_scientific_claim_gate" in production_source,
            "full_lifetime_metric_symbols": sorted(full_metric_symbols),
        },
        "checkpoint": {
            "generic_coordinator_present": _contains(
                platform_sources, "class WorkloadCheckpointCoordinator"
            ),
            "mc_provider_bound_at_environment_composition": "checkpoint=" in production_source,
            "resume_operation_composed": "coordinator.restore" in production_source or "resume_checkpoint" in production_source,
        },
        "live_evidence": {
            "qualified_closure_artifacts": qualified_closure_artifacts,
            "t2b_gate_results": t2b_evidence,
            "live_run_invocation_in_entrypoint": "host.start_source()" in production_source,
        },
        "architecture": {
            "declaration_only_leaf_count": declaration_only_leaf_count,
            "opaque_api_count": opaque_count,
            "topology_python_source": "_SYSTEM_TOPOLOGY" in _source(
                ROOT / "research_platform" / "governance" / "system_registry" / "api" / "topology.py"
            ),
            "catalog_json_source": (ROOT / "research_platform" / "governance" / "system_registry" / "catalog.json").is_file(),
        },
    }


def build_findings() -> tuple[AuditFinding, ...]:
    entrypoint = _source(ROOT / "scripts" / "run_sem_minecraft_experiment.py")
    application = _source(ROOT / "scripts" / "sem_paper_minecraft_application.py")
    production_source = entrypoint + "\n" + application
    evolution_unbound = (
        "DisabledSessionEvolutionFactory" in production_source
        or "evolution_factory=" not in production_source[production_source.find("root, host, log_store = build_runtime(") :]
    )
    runtime_call_start = production_source.find("root, host, log_store = build_runtime(")
    runtime_call = (
        production_source[runtime_call_start : runtime_call_start + 2400]
        if runtime_call_start >= 0
        else ""
    )
    declaration_only_leaf_count = _declaration_only_leaf_count()
    paper_sources = tuple((ROOT / "projects" / "sem_paper").rglob("*.py"))
    api_sources = _selected_api_sources()
    opaque_count = _opaque_api_count(api_sources)
    opaque_inventory = _opaque_api_inventory(api_sources)
    report = build_architecture_report(ROOT)
    surface = _surface_inventory(
        entrypoint=entrypoint,
        production_source=production_source,
        paper_sources=paper_sources,
        declaration_only_leaf_count=declaration_only_leaf_count,
        opaque_count=opaque_count,
    )
    run_spec_open = not surface["entrypoint"]["typed_run_spec_symbols"]
    generic_runtime_open = not all(surface["generic_experiment_runtime"].values())
    non_mc_open = not surface["generic_non_minecraft"]["production_entrypoints"]
    evolution_stage_open = not surface["evolution"]["production_factory_construction"]
    study_open = not surface["study"]["core6_or_rulebased_symbols"] or surface["study"]["protocol_repetitions_one"]
    expected_scientific_metrics = {"LTE_SR", "LPI", "CLU", "TDP", "ELCE", "HPEF", "GAG"}
    metric_open = set(surface["metrics"]["full_lifetime_metric_symbols"]) != expected_scientific_metrics
    checkpoint_open = not surface["checkpoint"]["mc_provider_bound_at_environment_composition"] or not surface["checkpoint"]["resume_operation_composed"]
    live_evidence_open = not surface["live_evidence"]["qualified_closure_artifacts"] or not surface["live_evidence"]["t2b_gate_results"]
    topology_authority_open = surface["architecture"]["topology_python_source"] and surface["architecture"]["catalog_json_source"]
    findings = [
        AuditFinding(
            "PAPER_OPERATOR_ENTRYPOINT",
            "blocking",
            "open" if entrypoint.count("def ") > 12 or entrypoint.count("os.environ") > 8 else "closed",
            f"entrypoint_lines={len(entrypoint.splitlines())}; functions={entrypoint.count('def ')}; env_reads={entrypoint.count('os.environ')}",
            "Move operator input loading and production composition behind typed project/platform run-spec ports.",
        ),
        AuditFinding(
            "PAPER_GENERIC_EXPERIMENT_RUNTIME_BYPASS",
            "blocking",
            "open" if generic_runtime_open else "closed",
            (
                "the Paper entrypoint does not compose the run-layer parent over the "
                "generic Study/Workload children"
                if generic_runtime_open
                else "Paper entrypoint is composed through the generic run-layer parent"
            ),
            "Keep assignment expansion, Study Matrix execution and publication in the run parent; inject only a typed MC/non-MC unit adapter.",
        ),
        AuditFinding(
            "SEM_EVOLUTION_PRODUCTION_BINDING",
            "blocking",
            "open" if evolution_unbound else "closed",
            (
                "production entrypoint still permits no real evolution factory"
                if evolution_unbound
                else "production entrypoint receives an explicitly bound evolution factory"
            ),
            "Compose real stage providers only after one session-scoped adoption/serving authority is shared.",
        ),
        AuditFinding(
            "QUALIFIED_MODEL_CLOSURE_COMPOSITION",
            "blocking",
            "open" if "qualified_binding" not in runtime_call else "closed",
            "provider exists, but the current entrypoint still passes no persisted qualified binding"
            if "qualified_binding" not in runtime_call
            else "runtime composition call supplies a qualified binding",
            "Load the persisted deployment/route/live-qualification closure in platform composition; retain fail-closed behavior until present.",
        ),
        AuditFinding(
            "WORKLOAD_CHECKPOINT_RESUME",
            "blocking",
            "open" if checkpoint_open else "closed",
            (
                "production composition does not bind both a world checkpoint provider and resume operator"
                if checkpoint_open
                else "production composition binds the world checkpoint provider and typed resume operator"
            ),
            "Bind authoritative MC world/session cut capture and restore, then expose a typed resume operation.",
        ),
        AuditFinding(
            "STUDY_MATRIX_ADAPTER",
            "blocking",
            "open"
            if not surface["study"]["matrix_executor_wired"]
            else "closed",
            "platform matrix executor exists but the Paper MC entrypoint still calls one evaluator pair directly"
            if not surface["study"]["matrix_executor_wired"]
            else "Paper MC entrypoint delegates the frozen matrix to a project StudyUnitExecutionPort adapter",
            "Add MC and non-MC StudyUnitExecutionPort adapters and execute every frozen assignment.",
        ),
        AuditFinding(
            "DECLARATION_ONLY_TOPOLOGY_LEAVES",
            "blocking",
            "open" if declaration_only_leaf_count else "closed",
            f"declaration_only_leaf_count={declaration_only_leaf_count}; catalog_nodes={len(system_catalog())}",
            "Migrate real owners to leaf nodes, verify callers, then physically delete retired coarse roots.",
        ),
        AuditFinding(
            "OPAQUE_API_PAYLOADS",
            "blocking",
            "open" if opaque_count else "closed",
            f"opaque_token_count={opaque_count} across selected API surfaces",
            "Replace highest-leverage object payloads with schema/digest/codec-bearing contracts without weakening adapters.",
        ),
        AuditFinding(
            "PAPER_RUN_SPEC_FACADE",
            "blocking",
            "open" if run_spec_open else "closed",
            "no typed run-spec/operator request is present; input parsing and lifecycle remain in the script"
            if run_spec_open
            else "typed ExperimentRunSpec is present and used by the Paper entrypoint",
            "Introduce one immutable generic run specification and a project/operator execution port; keep provider choice at the outer composition root.",
        ),
        AuditFinding(
            "PAPER_NON_MINECRAFT_EXECUTION",
            "blocking",
            "open" if non_mc_open else "closed",
            "generic non-MC protocols and tests exist, but no executable non-MC production entrypoint/provider is present"
            if non_mc_open
            else "non-MC production entrypoint and provider are present",
            "Bind a concrete non-MC environment/planner/evidence adapter and run the same StudyMatrix/Workload interfaces through a real entrypoint.",
        ),
        AuditFinding(
            "SEM_EVOLUTION_STAGE_BINDING",
            "blocking",
            "open" if evolution_stage_open else "closed",
            "EvolutionStageFactories is declared but PipelineSessionEvolutionFactory is not constructed by production code"
            if evolution_stage_open
            else "production code constructs the typed evolution factory",
            "Compose real stage providers and one session-scoped adoption/serving authority; do not substitute the disabled factory or baseline endpoint.",
        ),
        AuditFinding(
            "SEM_SCIENTIFIC_MATRIX_COMPLETENESS",
            "blocking",
            "open" if study_open else "closed",
            "current entrypoint fixes a two-variant, one-repetition development matrix; Core-6/RuleBased/ablation symbols are absent"
            if study_open
            else "Core-6 and required comparator symbols are present in the executable matrix",
            "Implement the pre-registered Core-6 and required comparator/ablation tiers with frozen repetitions, seeds, order and budget accounting.",
        ),
        AuditFinding(
            "SEM_SCIENTIFIC_METRIC_REGISTRY",
            "blocking",
            "open" if metric_open else "closed",
            "workload metrics are declared, but full lifetime/edit/adoption/cost/attribution metric symbols are absent"
            if metric_open
            else "full scientific metric registry is present",
            "Promote the Paper metric registry to a typed contract and publish all pre-registered estimands, provenance and cost/attribution metrics.",
        ),
        AuditFinding(
            "MC_WORLD_CHECKPOINT_RESUME",
            "blocking",
            "open" if checkpoint_open else "closed",
            "generic workload checkpoint coordinator exists, but MC environment composition binds no world provider or typed resume operation"
            if checkpoint_open
            else "MC world checkpoint provider and resume operation are composed",
            "Bind an authoritative MC world/session checkpoint provider and expose a typed resume operation that validates the same source cut, method generation and task cut.",
        ),
        AuditFinding(
            "LIVE_EXECUTION_EVIDENCE",
            "blocking",
            "open" if live_evidence_open else "closed",
            "no qualified deployment-closure artifact or T2B gate result exists in the current checkout"
            if live_evidence_open
            else "qualified deployment and T2B evidence artifacts are present",
            "Complete the qualification and live environment gates, then bind their immutable evidence before any scientific claim.",
        ),
        AuditFinding(
            "TOPOLOGY_SINGLE_AUTHORITY",
            "blocking",
            "open" if topology_authority_open else "closed",
            "runtime topology is declared in topology.py while catalog semantics are also declared in catalog.json"
            if topology_authority_open
            else "topology has one generated declaration authority",
            "Generate the runtime catalog from one authoritative topology source and delete the duplicate declaration surface after drift verification.",
        ),
        AuditFinding(
            "GLOBAL_ARCHITECTURE_BASELINE",
            "informational",
            "closed" if report.clean else "open",
            f"import_edges={report.import_edges}; cycles={len(report.package_cycles)}; import_violations={len(report.import_violations)}; source_authority_violations={len(report.source_authority_violations)}",
            "Keep the generic architecture gate green while Paper-specific findings remain explicit.",
        ),
    ]
    return tuple(findings)


def main() -> int:
    findings = build_findings()
    opaque_inventory = _opaque_api_inventory(_selected_api_sources())
    entrypoint = _source(ROOT / "scripts" / "run_sem_minecraft_experiment.py")
    application = _source(ROOT / "scripts" / "sem_paper_minecraft_application.py")
    surface = _surface_inventory(
        entrypoint=entrypoint,
        production_source=entrypoint + "\n" + application,
        paper_sources=tuple((ROOT / "projects" / "sem_paper").rglob("*.py")),
        declaration_only_leaf_count=_declaration_only_leaf_count(),
        opaque_count=len(opaque_inventory),
    )
    payload = {
        "project": "sem_paper",
        "source_root": str(ROOT),
        "findings": [asdict(item) for item in findings],
        "blocking_open": sum(item.severity == "blocking" and item.status == "open" for item in findings),
        "declaration_only_leaves": list(_declaration_only_leaf_packages()),
        "opaque_api_inventory": list(opaque_inventory),
        "surface_inventory": surface,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
