"""Audit the Paper production boundary before any scientific execution.

This is intentionally a reporting audit, not a bypassable success gate.  It
keeps the remaining architecture/science gaps machine-readable so a future
change cannot hide them behind a green generic architecture gate.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

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
    """Read the current checkout, including uncommitted audit repairs.

    The previous implementation preferred ``git show :path`` and therefore
    audited the index instead of the working tree.  That made the machine
    audit blind to exactly the changes an engineer was trying to validate.
    """

    return path.read_text(encoding="utf-8")


def _python_sources(*roots: Path) -> tuple[Path, ...]:
    return tuple(
        item
        for root in roots
        if root.exists()
        for item in root.rglob("*.py")
        if "__pycache__" not in item.parts
        and not any(part.startswith(".rsync-") for part in item.parts)
    )


def _contains(sources: tuple[Path, ...], needle: str) -> bool:
    return any(needle in _source(item) for item in sources)


def _call_keyword_sets(source: str, function_name: str) -> tuple[frozenset[str], ...]:
    """Return keyword names for each direct call to ``function_name``.

    This intentionally parses Python rather than slicing source around an old
    assignment spelling. Refactors may change tuple unpacking or formatting,
    but the composition authority is the call and its explicit bindings.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ()
    rows: list[frozenset[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name: str | None = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name != function_name:
            continue
        rows.append(
            frozenset(
                keyword.arg
                for keyword in node.keywords
                if keyword.arg is not None
            )
        )
    return tuple(rows)


def _json_document(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_t2b_gate_pass(path: Path) -> bool:
    """Validate the T2B result semantics instead of trusting one status field."""

    payload = _json_document(path)
    if payload is None:
        return False
    if payload.get("status") != "T2B_GATE_PASS" or payload.get("failure_class") != "NONE":
        return False
    if payload.get("same_server_process_for_both_seeds") is not True:
        return False
    gate_digest = payload.get("gate_digest")
    world_digest = payload.get("world_level_dat_sha256")
    if not isinstance(gate_digest, str) or len(gate_digest) != 64:
        return False
    if not isinstance(world_digest, str) or len(world_digest) != 64:
        return False

    server = payload.get("server_identity")
    if not isinstance(server, dict):
        return False
    jar_digest = server.get("jar_sha256")
    if not isinstance(jar_digest, str) or len(jar_digest) != 64:
        return False

    preflight = payload.get("preflight")
    if not isinstance(preflight, dict):
        return False
    probes = preflight.get("probes")
    if not isinstance(probes, list) or not probes:
        return False
    if any(
        not isinstance(probe, dict)
        or probe.get("ok") is not True
        or probe.get("cause_code") != "OK"
        for probe in probes
    ):
        return False

    runs = payload.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        return False
    by_seed: dict[str, dict[str, object]] = {}
    for run in runs:
        if not isinstance(run, dict) or run.get("returncode") != 0:
            return False
        result = run.get("result")
        if not isinstance(result, dict):
            return False
        seed = result.get("seed")
        if seed not in {"C", "X"} or run.get("seed") != seed:
            return False
        if result.get("status") != "PASS" or result.get("spawned") is not True:
            return False
        grounded = result.get("grounded_record_count")
        if not isinstance(grounded, int) or isinstance(grounded, bool) or grounded <= 0:
            return False
        refs = result.get("materialized_source_refs")
        if not isinstance(refs, list) or not refs:
            return False
        if any(not isinstance(ref, str) or not ref.startswith(f"j_mem:{seed}:") for ref in refs):
            return False
        by_seed[str(seed)] = result
    return set(by_seed) == {"C", "X"}


_T2B_NON_RUNTIME_PREFIXES = (
    "artifacts/sem_live_evidence/",
    "docs/",
    "projects/sem_paper/governance/",
    "tests/",
)
_T2B_NON_RUNTIME_EXACT = {"scripts/sem_paper_architecture_audit.py"}


def _t2b_changed_paths_are_non_runtime(paths: tuple[str, ...]) -> bool:
    """Permit evidence-only descendants without letting stale runtime gates survive code changes."""

    for raw in paths:
        path = raw.replace("\\", "/").strip()
        if not path:
            continue
        if path in _T2B_NON_RUNTIME_EXACT:
            continue
        if any(path.startswith(prefix) for prefix in _T2B_NON_RUNTIME_PREFIXES):
            continue
        return False
    return True


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", "-C", str(ROOT), *args),
        capture_output=True,
        text=True,
        check=False,
    )


def _t2b_source_is_current(path: Path) -> bool:
    """Bind one live gate to its tested commit and reject runtime-sensitive drift."""

    provenance = _json_document(path.parent / "PROVENANCE.json")
    if provenance is None:
        return False
    source = provenance.get("source")
    gate = provenance.get("gate")
    bundle = provenance.get("bundle")
    if not isinstance(source, dict) or not isinstance(gate, dict) or not isinstance(bundle, dict):
        return False
    commit = source.get("commit_sha")
    tree = source.get("git_tree")
    expected_gate_sha = gate.get("gate_result_sha256")
    expected_bundle_sha = bundle.get("sha256")
    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        return False
    if not isinstance(tree, str) or re.fullmatch(r"[0-9a-f]{40}", tree) is None:
        return False
    if not isinstance(expected_gate_sha, str) or re.fullmatch(r"[0-9a-f]{64}", expected_gate_sha) is None:
        return False
    if not isinstance(expected_bundle_sha, str) or re.fullmatch(r"[0-9a-f]{64}", expected_bundle_sha) is None:
        return False
    bundle_path = path.parent / "T2B_EVIDENCE.zip"
    try:
        bundle_bytes = bundle_path.read_bytes()
        if hashlib.sha256(bundle_bytes).hexdigest() != expected_bundle_sha:
            return False
        with zipfile.ZipFile(bundle_path) as archive:
            raw_gate = archive.read("T2B_GATE_RESULT.json")
        if hashlib.sha256(raw_gate).hexdigest() != expected_gate_sha:
            return False
        archived_gate = json.loads(raw_gate.decode("utf-8"))
    except (OSError, UnicodeError, ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError):
        return False
    projected_gate = _json_document(path)
    if projected_gate is None or archived_gate != projected_gate:
        return False

    tested_tree = _git("rev-parse", f"{commit}^{{tree}}")
    if tested_tree.returncode != 0 or tested_tree.stdout.strip() != tree:
        return False
    ancestry = _git("merge-base", "--is-ancestor", commit, "HEAD")
    if ancestry.returncode != 0:
        return False
    changed = _git("diff", "--name-only", f"{commit}..HEAD", "--")
    working = _git("diff", "--name-only", "HEAD", "--")
    untracked = _git("ls-files", "--others", "--exclude-standard")
    if changed.returncode != 0 or working.returncode != 0 or untracked.returncode != 0:
        return False
    paths = tuple(
        line
        for output in (changed.stdout, working.stdout, untracked.stdout)
        for line in output.splitlines()
        if line.strip()
    )
    return _t2b_changed_paths_are_non_runtime(paths)


def _t2b_evidence_paths() -> tuple[str, ...]:
    """Discover live-gate evidence only from the project-owned immutable evidence authority."""

    root = ROOT / "artifacts" / "sem_live_evidence"
    if not root.is_dir():
        return ()
    return tuple(
        str(path.relative_to(ROOT))
        for path in root.rglob("T2B_GATE_RESULT.json")
        if path.is_file()
    )

def _is_qualified_model_closure(path: Path) -> bool:
    """Prove that a persisted closure can produce the exact SEM planner binding."""

    document = _json_document(path)
    if document is None or document.get("schema_version") != "qualified-model-deployment-closure.v1":
        return False
    runtime_root_raw = document.get("runtime_qualification_root")
    if not isinstance(runtime_root_raw, str) or not runtime_root_raw.strip():
        return False
    runtime_root = Path(runtime_root_raw)
    if not runtime_root.is_absolute():
        runtime_root = (path.parent / runtime_root).resolve(strict=False)
    if not runtime_root.is_dir():
        return False

    try:
        from research_platform.model.serving.endpoint.composition import (
            PersistedQualifiedModelEndpointBinding,
            load_qualified_model_deployment_closure,
        )
        from research_platform.model.serving.providers.runtime_qualification_storage import (
            DirectoryRuntimeQualificationEvidenceStore,
        )

        closure = load_qualified_model_deployment_closure(
            path,
            runtime_qualification_store_factory=DirectoryRuntimeQualificationEvidenceStore,
        )
        binding = PersistedQualifiedModelEndpointBinding(closure).binding_for(
            role="planner",
            prompt_generation="sem-paper-planner-generation-v1",
        )
    except (OSError, TypeError, ValueError, KeyError, RuntimeError):
        return False
    return (
        binding.role == "planner"
        and binding.prompt_generation == "sem-paper-planner-generation-v1"
        and bool(binding.deployment_id)
        and bool(binding.runtime_qualification_digest)
    )


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
            if item.name != "__init__.py"
            and "__pycache__" not in item.parts
            and not any(part.startswith(".rsync-") for part in item.parts)
        ]
        if not sources:
            # Empty catalog directories are structural placeholders, not
            # declaration-only implementation leaves.
            continue
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
    qualified_binding_artifacts = tuple(
        relative_path
        for relative_path in qualified_closure_artifacts
        if _is_qualified_model_closure(ROOT / relative_path)
    )
    t2b_evidence = _t2b_evidence_paths()
    t2b_pass_evidence = tuple(
        path
        for path in t2b_evidence
        if _is_t2b_gate_pass(ROOT / path) and _t2b_source_is_current(ROOT / path)
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
            "production_runtime_factory_argument": any(
                "evolution_factory" in keywords
                for keywords in _call_keyword_sets(production_source, "build_runtime")
            ),
            "disabled_factory_in_production_entrypoint": "DisabledSessionEvolutionFactory" in production_source,
        },
        "study": {
            "matrix_executor_wired": (
                "StudyMatrixExecutor" in production_source
                or "build_default_experiment_run_application" in production_source
            ),
            "confirmatory_factory_used": "build_sem_paper_confirmatory_protocol" in production_source,
            "conformance_factory_used": "build_sem_paper_conformance_protocol" in production_source,
            "protocol_repetitions_one": "repetitions=1" in production_source,
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
            "qualified_binding_artifacts": qualified_binding_artifacts,
            "t2b_gate_results": t2b_evidence,
            "t2b_pass_results": t2b_pass_evidence,
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
        "scientific_semantics": {
            "fixed_seed_x_endpoint_composed": (
                "fixed_seed_x_deluxe_snapshot_factory" in production_source
                and _contains(paper_sources, "validate_plan_provider_closure")
                and _contains(paper_sources, "fixed_endpoints_by_seed")
            ),
            "cognition_uses_method_session_recall": (
                _contains(paper_sources, "class SemMethodAgentMemoryAdapter")
                and _contains(paper_sources, "memory=SemMethodAgentMemoryAdapter(self.method)")
            ),
            "statistics_use_matched_environment_units": (
                _contains(paper_sources, "incomplete_matched_environment_unit")
                and _contains(paper_sources, "seed_pair_values")
            ),
            "production_uses_confirmatory_core6": (
                "build_sem_paper_confirmatory_protocol" in production_source
                and _contains(paper_sources, "is_confirmatory_protocol")
            ),
            "rulebased_shares_scientific_authorities": (
                _contains(paper_sources, "replace(bindings, proposal=RuleBasedProposalAuthority())")
                and "build_rule_based_evolution_factory(evolution_bindings)" in production_source
            ),
            "operator_evolution_binding_seam": (
                "--evolution-binding-factory" in production_source
                and "_load_evolution_bindings" in production_source
            ),
            "auxiliary_run_finalizer": (
                "_finalize_run_auxiliary_evidence" in production_source
                and _contains(paper_sources, "class DirectoryScientificAuxiliarySampleStore")
                and _contains(paper_sources, "def finalize_scientific_auxiliary_evidence")
            ),
            "auxiliary_estimand_semantics": (
                _contains(paper_sources, 'SCIENTIFIC_AUXILIARY_SCHEMA_VERSION = "sem-scientific-auxiliary.v2"')
                and _contains(paper_sources, '"GAG": (None, None)')
                and _contains(paper_sources, "held_out_positive_edit_fraction")
                and _contains(paper_sources, "gate_to_audit_generalization_gap")
            ),
            "lifetime_estimands_match_frozen_semantics": (
                _contains(paper_sources, "matched_lifetime_deltas")
                and _contains(paper_sources, "sum(1 for delta in matched_lifetime_deltas if delta > 0.0)")
                and _contains(paper_sources, '"LPI", "probability that matched lifetime SelfEvolve utility exceeds FixedSeed"')
            ),
            "legacy_claim_ready_retired": (
                "matrix_profile='claim-ready' is retired" in study_source
                and "build_sem_paper_confirmatory_protocol" in production_source
            ),
        },
    }


def build_findings() -> tuple[AuditFinding, ...]:
    entrypoint = _source(ROOT / "scripts" / "run_sem_minecraft_experiment.py")
    application = _source(ROOT / "scripts" / "sem_paper_minecraft_application.py")
    production_source = entrypoint + "\n" + application
    runtime_keyword_sets = _call_keyword_sets(production_source, "build_runtime")
    runtime_binds_evolution = any(
        "evolution_factory" in keywords and "evolution_bindings" in keywords
        for keywords in runtime_keyword_sets
    )
    runtime_binds_qualified_model = any(
        "qualified_binding" in keywords
        for keywords in runtime_keyword_sets
    )
    evolution_unbound = (
        "DisabledSessionEvolutionFactory" in production_source
        or not runtime_binds_evolution
        or "build_sem_paper_evolution_factory(bound_evolution)" not in production_source
    )
    qualified_model_unbound = (
        not runtime_binds_qualified_model
        or "PersistedQualifiedModelEndpointBinding(closure).binding_for(" not in production_source
        or 'if inputs.mode == "baseline" and qualified_binding is None:' not in production_source
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
    study_open = (
        not surface["study"]["core6_or_rulebased_symbols"]
        or not surface["study"]["confirmatory_factory_used"]
    )
    expected_scientific_metrics = {"LTE_SR", "LPI", "CLU", "TDP", "ELCE", "HPEF", "GAG"}
    metric_open = set(surface["metrics"]["full_lifetime_metric_symbols"]) != expected_scientific_metrics
    checkpoint_open = not surface["checkpoint"]["mc_provider_bound_at_environment_composition"] or not surface["checkpoint"]["resume_operation_composed"]
    live_evidence_gaps = tuple(
        gap
        for gap, present in (
            ("qualified planner deployment closure is missing", bool(surface["live_evidence"]["qualified_binding_artifacts"])),
            ("verified T2B live gate evidence is missing", bool(surface["live_evidence"]["t2b_pass_results"])),
        )
        if not present
    )
    live_evidence_open = bool(live_evidence_gaps)
    topology_authority_open = surface["architecture"]["topology_python_source"] and surface["architecture"]["catalog_json_source"]
    semantic = surface["scientific_semantics"]
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
            "open" if qualified_model_unbound else "closed",
            "production does not prove persisted qualified model binding composition"
            if qualified_model_unbound
            else "runtime composition call supplies the persisted qualified model binding and fails closed when absent",
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
            "SEM_FIXED_SEED_PROVIDER_IDENTITY",
            "blocking",
            "closed" if semantic["fixed_seed_x_endpoint_composed"] else "open",
            "Core-6 Fixed-C/Fixed-X dry-compose through seed-specific endpoints"
            if semantic["fixed_seed_x_endpoint_composed"]
            else "Fixed-C/Fixed-X seed-specific endpoint closure is not enforced",
            "Bind Seed-C and Seed-X to distinct endpoint identities and dry-compose every arm before runtime startup.",
        ),
        AuditFinding(
            "SEM_COGNITION_METHOD_RECALL",
            "blocking",
            "closed" if semantic["cognition_uses_method_session_recall"] else "open",
            "Minecraft cognition recalls through the exact arm MethodSession"
            if semantic["cognition_uses_method_session_recall"]
            else "Minecraft cognition can bypass the bound SEM MethodSession recall authority",
            "Route cognition memory through MethodSession.recall and keep local memory non-authoritative.",
        ),
        AuditFinding(
            "SEM_MATCHED_ENVIRONMENT_STATISTICS",
            "blocking",
            "closed" if semantic["statistics_use_matched_environment_units"] else "open",
            "Seed-C/X deltas are aggregated within repetition before uncertainty estimation"
            if semantic["statistics_use_matched_environment_units"]
            else "Seed rows are not proven to be aggregated into matched environment units",
            "Use repetition/environment unit as N and average the two frozen seed deltas within each unit.",
        ),
        AuditFinding(
            "SEM_CONFIRMATORY_PROTOCOL_AUTHORITY",
            "blocking",
            "closed" if semantic["production_uses_confirmatory_core6"] else "open",
            "production selects frozen full-N Core-6 and closure validates the confirmatory predicate"
            if semantic["production_uses_confirmatory_core6"]
            else "production protocol and scientific closure do not share one Core-6 authority",
            "Use Core-6 for confirmatory full-N execution; keep external/ablation tiers separate.",
        ),
        AuditFinding(
            "SEM_RULEBASED_TREATMENT_IDENTITY",
            "blocking",
            "closed" if semantic["rulebased_shares_scientific_authorities"] else "open",
            "RuleBased replaces only proposal policy and shares evaluator/adoption/reconciliation authorities"
            if semantic["rulebased_shares_scientific_authorities"]
            else "RuleBased is not proven to share the scientific gate authorities with SelfEvolve",
            "Compose RuleBased by replacing only proposal policy on the scientific evolution binding set.",
        ),
        AuditFinding(
            "SEM_EVOLUTION_OPERATOR_INJECTION",
            "blocking",
            "closed" if semantic["operator_evolution_binding_seam"] else "open",
            "CLI exposes a typed trusted factory seam for scientific evolution authorities"
            if semantic["operator_evolution_binding_seam"]
            else "CLI cannot inject the deployment-specific scientific evolution authorities",
            "Expose an outer-composition factory seam and fail closed unless the returned bindings are scientifically ready.",
        ),
        AuditFinding(
            "SEM_AUXILIARY_RUN_FINALIZER",
            "blocking",
            "closed" if semantic["auxiliary_run_finalizer"] else "open",
            "typed run-local auxiliary samples are provenance-checked and finalized automatically"
            if semantic["auxiliary_run_finalizer"]
            else "scientific auxiliary estimands still require a manually assembled final receipt",
            "Finalize typed trajectory/held-out audit samples inside the run and keep missing samples fail-closed.",
        ),
        AuditFinding(
            "SEM_AUXILIARY_ESTIMAND_SEMANTICS",
            "blocking",
            "closed" if semantic["auxiliary_estimand_semantics"] else "open",
            "HPEF/GAG use frozen held-out edit-audit semantics and GAG is a signed gap"
            if semantic["auxiliary_estimand_semantics"]
            else "auxiliary metric field/range semantics do not match the frozen estimands",
            "Use held-out positive edit fraction for HPEF and signed gate-minus-audit effect for GAG.",
        ),
        AuditFinding(
            "SEM_LIFETIME_ESTIMAND_SEMANTICS",
            "blocking",
            "closed" if semantic["lifetime_estimands_match_frozen_semantics"] else "open",
            "LTE/CLU/LPI share matched lifetime units and LPI is empirical P(delta_life > 0)"
            if semantic["lifetime_estimands_match_frozen_semantics"]
            else "lifetime point estimands are not proven to match the frozen matched-unit definitions",
            "Compute LTE/CLU/LPI from identical matched lifetime units; define LPI as P(delta_life > 0).",
        ),
        AuditFinding(
            "SEM_RETIRED_PROTOCOL_FAIL_CLOSED",
            "blocking",
            "closed" if semantic["legacy_claim_ready_retired"] else "open",
            "legacy pre-freeze 12-arm claim-ready profile is rejected and production selects Core-6"
            if semantic["legacy_claim_ready_retired"]
            else "the obsolete 12-arm profile remains executable or production does not select Core-6",
            "Fail closed on the obsolete profile and execute supplementary controls as separate frozen studies.",
        ),
        AuditFinding(
            "LIVE_EXECUTION_EVIDENCE",
            "blocking",
            "open" if live_evidence_open else "closed",
            "; ".join(live_evidence_gaps)
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
