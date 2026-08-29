from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from research_platform.platform.kernel import canonical_digest

from .platform_policy import build_platform_audit
from .hotspots import ModuleHotspot, analyze_hotspots
from .optimization import analyze_optimization_risks
from .import_graph import ImportViolation, architecture_import_rules, audit_import_rules, audit_layer_dag, package_cycles, scan_imports
from .source_invariants import audit_source_invariants
from .source_authority import architecture_source_authority_rules
from .seam_graphs import SeamEdge, declared_capability_graph, partition_seam_graphs, scan_seam_graphs
from .system_graphs import SubsystemGraphEdge, SystemGraphEdge, declared_subsystem_graph, declared_system_graph
from .source_index import architecture_source_index
from .source_profile import scan_architecture_source_profile


@dataclass(frozen=True, slots=True)
class ArchitectureReport:
    source_root: str
    import_edges: int
    import_violations: tuple[dict[str,object],...]
    layer_violations: tuple[dict[str,object],...]
    package_cycles: tuple[tuple[str,...],...]
    declared_authority_violations: tuple[dict[str,object],...]
    source_invariant_violations: tuple[dict[str,object],...]
    source_authority_violations: tuple[dict[str,object],...]
    top_hotspots: tuple[dict[str,object],...]
    top_optimization_risks: tuple[dict[str,object],...]
    capability_graph: tuple[SeamEdge, ...]
    operation_graph: tuple[SeamEdge, ...]
    event_graph: tuple[SeamEdge, ...]
    system_graph: tuple[SystemGraphEdge, ...]
    subsystem_graph: tuple[SubsystemGraphEdge, ...]
    report_sha256: str

    @property
    def clean(self)->bool:
        return not self.import_violations and not self.layer_violations and not self.package_cycles and not self.declared_authority_violations and not self.source_invariant_violations and not self.source_authority_violations


def build_architecture_report(root:Path,*,hotspot_limit:int=20)->ArchitectureReport:
    root = Path(root).resolve()
    authority_rules = architecture_source_authority_rules(root)
    # Repository-wide facts are extracted in one streaming AST pass.  Only
    # focused invariant audits use the bounded AST cache below.
    profile = scan_architecture_source_profile(root, authority_rules=authority_rules)
    with architecture_source_index(root, max_entries=128) as source_index:
        source_index.seed_imports(
            (root / fact.path, fact.imports) for fact in profile.import_facts
        )
        source_index.seed_import_edges(("research_platform", "projects"), profile.import_edges)
        source_index.seed_import_edges(
            ("research_platform",),
            (edge for edge in profile.import_edges if edge.source_module.startswith("research_platform")),
        )
        sv = audit_source_invariants(root)
    edges = profile.import_edges
    iv = audit_import_rules(edges, architecture_import_rules(root))
    lv = audit_layer_dag(root, edges)
    cycles = package_cycles(edges)
    av = build_platform_audit().run()
    hotspots = profile.hotspots[:hotspot_limit]
    risks = profile.optimization_risks[:hotspot_limit]
    seams = profile.seam_edges
    sav = profile.authority_violations
    declared_audit=build_platform_audit(); capability_graph,operation_graph,event_graph=partition_seam_graphs(seams,declared_capabilities=declared_capability_graph(declared_audit))
    system_graph=declared_system_graph(); subsystem_graph=declared_subsystem_graph()
    base={"source_root":str(root.resolve()),"import_edges":len(edges),"import_violations":[{"source":x.edge.source_module,"target":x.edge.target_module,"path":x.edge.path,"line":x.edge.line,"reason":x.reason} for x in iv],"layer_violations":[{"source":x.edge.source_module,"target":x.edge.target_module,"path":x.edge.path,"line":x.edge.line,"source_layer":x.source_layer,"target_layer":x.target_layer,"reason":x.reason} for x in lv],"package_cycles":[list(x) for x in cycles],"declared_authority_violations":[asdict(x) for x in av],"source_invariant_violations":[asdict(x) for x in sv],"source_authority_violations":[asdict(x) for x in sav],"top_hotspots":[asdict(x) for x in hotspots],"top_optimization_risks":[asdict(x) for x in risks],"capability_graph":[asdict(x) for x in capability_graph],"operation_graph":[asdict(x) for x in operation_graph],"event_graph":[asdict(x) for x in event_graph],"system_graph":[asdict(x) for x in system_graph],"subsystem_graph":[asdict(x) for x in subsystem_graph]}
    identity={key:value for key,value in base.items() if key != "source_root"}
    digest=canonical_digest(identity)
    return ArchitectureReport(
        source_root=base["source_root"], import_edges=base["import_edges"],
        import_violations=tuple(base["import_violations"]), layer_violations=tuple(base["layer_violations"]), package_cycles=tuple(tuple(x) for x in base["package_cycles"]),
        declared_authority_violations=tuple(base["declared_authority_violations"]), source_invariant_violations=tuple(base["source_invariant_violations"]),
        source_authority_violations=tuple(base["source_authority_violations"]), top_hotspots=tuple(base["top_hotspots"]),
        top_optimization_risks=tuple(base["top_optimization_risks"]), capability_graph=capability_graph,
        operation_graph=operation_graph, event_graph=event_graph, system_graph=system_graph,
        subsystem_graph=subsystem_graph, report_sha256=digest,
    )
