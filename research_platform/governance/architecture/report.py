from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from research_platform.platform.kernel import canonical_digest

from .platform_policy import build_platform_audit
from .hotspots import ModuleHotspot, analyze_hotspots
from .optimization import analyze_optimization_risks
from .import_graph import ImportViolation, architecture_import_rules, audit_import_rules, package_cycles, scan_imports
from .source_invariants import audit_source_invariants
from .source_authority import audit_source_authorities
from .seam_graphs import declared_capability_graph, partition_seam_graphs, scan_seam_graphs
from .system_graphs import declared_subsystem_graph, declared_system_graph


@dataclass(frozen=True, slots=True)
class ArchitectureReport:
    source_root: str
    import_edges: int
    import_violations: tuple[dict[str,object],...]
    package_cycles: tuple[tuple[str,...],...]
    declared_authority_violations: tuple[dict[str,object],...]
    source_invariant_violations: tuple[dict[str,object],...]
    source_authority_violations: tuple[dict[str,object],...]
    top_hotspots: tuple[dict[str,object],...]
    top_optimization_risks: tuple[dict[str,object],...]
    capability_graph: tuple[dict[str,object],...]
    operation_graph: tuple[dict[str,object],...]
    event_graph: tuple[dict[str,object],...]
    system_graph: tuple[dict[str,object],...]
    subsystem_graph: tuple[dict[str,object],...]
    report_sha256: str

    @property
    def clean(self)->bool:
        return not self.import_violations and not self.package_cycles and not self.declared_authority_violations and not self.source_invariant_violations and not self.source_authority_violations


def build_architecture_report(root:Path,*,hotspot_limit:int=20)->ArchitectureReport:
    edges=scan_imports(root); iv=audit_import_rules(edges, architecture_import_rules(root)); cycles=package_cycles(edges); av=build_platform_audit().run(); sv=audit_source_invariants(root); sav=audit_source_authorities(root); hotspots=analyze_hotspots(root)[:hotspot_limit]; risks=analyze_optimization_risks(root)[:hotspot_limit]
    seams=scan_seam_graphs(root); declared_audit=build_platform_audit(); capability_graph,operation_graph,event_graph=partition_seam_graphs(seams,declared_capabilities=declared_capability_graph(declared_audit))
    system_graph=declared_system_graph(); subsystem_graph=declared_subsystem_graph()
    base={"source_root":str(root.resolve()),"import_edges":len(edges),"import_violations":[{"source":x.edge.source_module,"target":x.edge.target_module,"path":x.edge.path,"line":x.edge.line,"reason":x.reason} for x in iv],"package_cycles":[list(x) for x in cycles],"declared_authority_violations":[asdict(x) for x in av],"source_invariant_violations":[asdict(x) for x in sv],"source_authority_violations":[asdict(x) for x in sav],"top_hotspots":[asdict(x) for x in hotspots],"top_optimization_risks":[asdict(x) for x in risks],"capability_graph":list(capability_graph),"operation_graph":list(operation_graph),"event_graph":list(event_graph),"system_graph":list(system_graph),"subsystem_graph":list(subsystem_graph)}
    identity={key:value for key,value in base.items() if key != "source_root"}
    digest=canonical_digest(identity)
    return ArchitectureReport(
        source_root=base["source_root"], import_edges=base["import_edges"],
        import_violations=tuple(base["import_violations"]), package_cycles=tuple(tuple(x) for x in base["package_cycles"]),
        declared_authority_violations=tuple(base["declared_authority_violations"]), source_invariant_violations=tuple(base["source_invariant_violations"]),
        source_authority_violations=tuple(base["source_authority_violations"]), top_hotspots=tuple(base["top_hotspots"]),
        top_optimization_risks=tuple(base["top_optimization_risks"]), capability_graph=tuple(base["capability_graph"]),
        operation_graph=tuple(base["operation_graph"]), event_graph=tuple(base["event_graph"]), system_graph=tuple(base["system_graph"]),
        subsystem_graph=tuple(base["subsystem_graph"]), report_sha256=digest,
    )
