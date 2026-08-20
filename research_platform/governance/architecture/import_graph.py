from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ImportEdge:
    source_module: str
    target_module: str
    path: str
    line: int


@dataclass(frozen=True, slots=True)
class ImportRule:
    source_prefix: str
    target_prefix: str
    reason: str


@dataclass(frozen=True, slots=True)
class ImportViolation:
    edge: ImportEdge
    reason: str


def module_name(root: Path, path: Path) -> str:
    rel=path.relative_to(root).with_suffix("")
    parts=list(rel.parts)
    if parts and parts[-1]=="__init__": parts.pop()
    return ".".join(parts)


def _resolve_relative(source: str, level: int, module: str | None, *, source_is_package: bool = False) -> str:
    parts=source.split(".")
    # __init__.py represents a package, while ordinary files represent modules.
    package=parts if source_is_package else parts[:-1]
    if level>0:
        keep=max(0,len(package)-(level-1)); base=package[:keep]
    else: base=[]
    if module: base.extend(module.split("."))
    return ".".join(base)


def scan_imports(root: Path, package_roots: tuple[str,...]=( "research_platform", "projects")) -> tuple[ImportEdge,...]:
    edges=[]
    for prefix in package_roots:
        pkg=root/prefix
        if not pkg.exists(): continue
        for path in sorted(pkg.rglob("*.py")):
            src=module_name(root,path)
            tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(package_roots): edges.append(ImportEdge(src,alias.name,path.relative_to(root).as_posix(),node.lineno))
                elif isinstance(node,ast.ImportFrom):
                    target=_resolve_relative(src,node.level,node.module,source_is_package=path.name=="__init__.py") if node.level else (node.module or "")
                    if target.startswith(package_roots): edges.append(ImportEdge(src,target,path.relative_to(root).as_posix(),node.lineno))
    return tuple(edges)


def audit_import_rules(edges: tuple[ImportEdge,...], rules: tuple[ImportRule,...]) -> tuple[ImportViolation,...]:
    out=[]
    for edge in edges:
        for rule in rules:
            if edge.source_module.startswith(rule.source_prefix) and edge.target_module.startswith(rule.target_prefix):
                out.append(ImportViolation(edge,rule.reason))
    return tuple(out)


def package_cycles(edges: tuple[ImportEdge,...], depth: int=2) -> tuple[tuple[str,...],...]:
    def bucket(name: str) -> str:
        # Platform is a hierarchical root.  Its foundational kernel and composition
        # root intentionally sit on opposite sides of every child system: children
        # depend on kernel primitives, while composition depends on children.  If both
        # are collapsed into the same depth-2 ``research_platform.platform`` bucket,
        # every valid parent/child relationship becomes a false cycle.  Keep those two
        # architectural planes distinct while retaining the historical depth argument
        # for all ordinary packages and synthetic tests.
        if depth == 2 and name.startswith("research_platform.platform.kernel"):
            return "research_platform.foundation"
        if depth == 2 and name.startswith("research_platform.platform.composition"):
            return "research_platform.composition"
        return ".".join(name.split(".")[:depth])

    graph: dict[str,set[str]]={}
    for e in edges:
        a,b=bucket(e.source_module),bucket(e.target_module)
        if a!=b: graph.setdefault(a,set()).add(b); graph.setdefault(b,set())
    cycles=set()
    def canonical(cycle:list[str])->tuple[str,...]:
        body=cycle[:-1]; rots=[tuple(body[i:]+body[:i]) for i in range(len(body))]; rev=list(reversed(body)); rots += [tuple(rev[i:]+rev[:i]) for i in range(len(rev))]
        return min(rots)
    for start in sorted(graph):
        stack=[(start,[start])]
        while stack:
            node,path=stack.pop()
            for nxt in graph.get(node,()):
                if nxt==start and len(path)>1: cycles.add(canonical(path+[start]))
                elif nxt not in path and len(path)<len(graph): stack.append((nxt,path+[nxt]))
    return tuple(sorted(cycles))


DEFAULT_IMPORT_RULES=(
    ImportRule("research_platform.model.request.api","research_platform.model.request.runtime","Model Request API cannot depend on its runtime implementation"),
    ImportRule("research_platform.model.request.api","research_platform.model.request.prompt.runtime","Model Request API cannot depend on Prompt OS implementation"),
    ImportRule("research_platform.execution.capability.api","research_platform.execution.capability.runtime","Capability API cannot depend on capability runtime implementation"),
    ImportRule("research_platform.data.projection.api","research_platform.data.projection.runtime","Projection API cannot depend on projection runtime implementation"),
    ImportRule("research_platform.data.fact.api","research_platform.data.fact.runtime","Fact API cannot depend on fact runtime implementation"),
    ImportRule("research_platform.participant.capability.api","research_platform.execution.capability.runtime","Participant capability API cannot depend on execution capability runtime implementation"),
    ImportRule("research_platform.data.record.api","research_platform.data.fact.api","Record-plane API cannot depend upward on durable-fact API"),
    ImportRule("research_platform.data.record.api","research_platform.observability.api","Record-plane API cannot depend upward on observability API"),
    ImportRule("research_platform.data.record.api","research_platform.participant.capability.api","Record-plane API cannot depend upward on capability API"),
    ImportRule("research_platform","projects","generic platform must not import a concrete project/application"),
    ImportRule("research_platform.participant.method.api","research_platform.model.serving","Method ABI cannot depend on model-serving implementation"),
    ImportRule("research_platform.participant.method.api","research_platform.model.request.prompt.runtime","Method ABI cannot depend on Prompt OS implementation"),
    ImportRule("research_platform.runtime.service.runtime","research_platform.execution.runtime.manager","Service OS cannot depend upward on Runtime Manager"),
    ImportRule("research_platform.reliability.primitives","research_platform.execution.runtime.manager","Reliability contracts cannot depend on Runtime Manager"),
    ImportRule("research_platform.reliability.primitives","research_platform.runtime.service.runtime","Reliability contracts cannot depend on Service OS"),
    ImportRule("research_platform.platform.kernel","research_platform.platform.composition.runtime_control","Kernel cannot depend upward on bootstrap wiring"),
    ImportRule("research_platform.reliability.forensics","research_platform.platform.composition.runtime_control","Forensics cannot depend upward on bootstrap wiring"),
    ImportRule("research_platform.experimentation.study","research_platform.participant.definition.runtime","Study execution cannot import participant definition factories"),
    ImportRule("research_platform.experimentation.study","research_platform.participant.binding.runtime","Study execution cannot import participant binding runtime"),
    ImportRule("research_platform.experimentation.study","research_platform.participant.session.runtime","Study execution cannot import participant session runtime"),
    ImportRule("research_platform.execution.workflow.implementations","research_platform.participant.definition.runtime","Workflow execution cannot import participant definition factories"),
    ImportRule("research_platform.execution.workflow.implementations","research_platform.participant.binding.runtime","Workflow execution cannot import participant binding runtime"),
    ImportRule("research_platform.execution.workflow.implementations","research_platform.participant.session.runtime","Workflow execution cannot import participant session runtime"),
    ImportRule("research_platform.execution.runtime.manager","research_platform.participant.definition.runtime","Runtime Manager cannot import participant definition runtime"),
    ImportRule("research_platform.execution.runtime.manager","research_platform.participant.binding.runtime","Runtime Manager cannot import participant binding runtime"),
    ImportRule("research_platform.execution.runtime.manager","research_platform.participant.session.runtime","Runtime Manager cannot import participant session runtime"),
    ImportRule("research_platform.runtime.service.runtime","research_platform.participant.definition.runtime","Service OS cannot import participant definition runtime"),
    ImportRule("research_platform.runtime.service.runtime","research_platform.participant.binding.runtime","Service OS cannot import participant binding runtime"),
    ImportRule("research_platform.runtime.service.runtime","research_platform.participant.session.runtime","Service OS cannot import participant session runtime"),
    ImportRule("research_platform.runtime.session.runtime","research_platform.participant.definition.runtime","Server session transport cannot import participant definition runtime"),
    ImportRule("research_platform.runtime.session.runtime","research_platform.participant.binding.runtime","Server session transport cannot import participant binding runtime"),
    ImportRule("research_platform.runtime.session.runtime","research_platform.participant.session.runtime","Server session transport cannot import participant session runtime"),
    ImportRule("research_platform.runtime.session.runtime.","research_platform.execution.runtime.manager","Persistent-session implementation cannot depend upward on Runtime Manager"),
    ImportRule("research_platform.runtime.session.runtime.","research_platform.runtime.service.runtime","Persistent-session implementation cannot own service supervision"),
    ImportRule("research_platform.runtime.session.runtime.","research_platform.model.serving","Persistent-session implementation cannot own model serving"),
    ImportRule("research_platform.runtime.session.runtime.","research_platform.platform.composition.runtime_control","Persistent-session implementation cannot depend upward on bootstrap"),
    ImportRule("research_platform.execution.runtime.manager","research_platform.runtime.session.runtime.","Runtime Manager must depend on persistent-session API, not a concrete backend"),
    ImportRule("research_platform.governance.release.runtime","research_platform.participant.definition.runtime","Release identity layer cannot import participant definition runtime"),
    ImportRule("research_platform.governance.release.runtime","research_platform.participant.binding.runtime","Release identity layer cannot import participant binding runtime"),
    ImportRule("research_platform.governance.release.runtime","research_platform.participant.session.runtime","Release identity layer cannot import participant session runtime"),
    ImportRule("research_platform.experimentation.study","research_platform.platform.composition.runtime_control","Study runtime cannot depend upward on bootstrap wiring"),
    ImportRule("research_platform.reliability.effect.runtime","research_platform.platform.composition.runtime_control","Effect journal cannot depend upward on bootstrap wiring"),
    ImportRule("research_platform.participant.method.api","research_platform.platform.composition.runtime_control","Method ABI cannot depend upward on bootstrap wiring"),
    ImportRule("research_platform.environment.runtime.api","research_platform.platform.composition.runtime_control","Environment ABI cannot depend upward on bootstrap wiring"),
    ImportRule("research_platform.participant.agent.api","research_platform.environment.runtime.api","Agent ABI cannot depend on Environment ABI"),
    ImportRule("research_platform.participant.agent.api","research_platform.participant.method.api","Agent ABI cannot depend on Method ABI"),
    ImportRule("research_platform.participant.agent.api","research_platform.experimentation.study","Agent ABI cannot depend upward on Study runtime"),
    ImportRule("research_platform.participant.capability.api","research_platform.participant.agent.api","Capability ABI cannot depend upward on Agent ABI"),
    ImportRule("research_platform.participant.capability.api","research_platform.environment.runtime.api","Capability ABI cannot depend on Environment ABI"),
    ImportRule("research_platform.participant.capability.api","research_platform.participant.method.api","Capability ABI cannot depend on Method ABI"),
    ImportRule("research_platform.participant.capability.api","research_platform.experimentation.study","Capability ABI cannot depend upward on Study runtime"),
    ImportRule("research_platform.participant.agent.api","research_platform.platform.composition.runtime_control","Agent ABI cannot depend upward on bootstrap wiring"),
    ImportRule("research_platform.participant.capability.api","research_platform.platform.composition.runtime_control","Capability ABI cannot depend upward on bootstrap wiring"),
    ImportRule("research_platform.reliability.effect.api","research_platform.participant.agent.api","Effect ABI cannot depend upward on Agent ABI"),
    ImportRule("research_platform.reliability.effect.api","research_platform.participant.capability.api","Effect ABI cannot depend upward on Capability ABI"),
    ImportRule("research_platform.reliability.effect.api","research_platform.environment.runtime.api","Effect ABI cannot depend on Environment ABI"),
    ImportRule("research_platform.reliability.effect.api","research_platform.participant.method.api","Effect ABI cannot depend on Method ABI"),
    ImportRule("research_platform.reliability.effect.api","research_platform.experimentation.study","Effect ABI cannot depend upward on Study runtime"),
    ImportRule("research_platform.reliability.effect.api","research_platform.platform.composition.runtime_control","Effect ABI cannot depend upward on bootstrap wiring"),
    ImportRule("research_platform.participant.core.api","research_platform.participant.agent.api","Participant ABI cannot depend on Agent ABI"),
    ImportRule("research_platform.participant.core.api","research_platform.participant.capability.api","Participant ABI cannot depend on Capability ABI"),
    ImportRule("research_platform.participant.core.api","research_platform.environment.runtime.api","Participant ABI cannot depend on Environment ABI"),
    ImportRule("research_platform.participant.core.api","research_platform.participant.method.api","Participant ABI cannot depend on Method ABI"),
    ImportRule("research_platform.participant.core.api","research_platform.experimentation.study","Participant ABI cannot depend upward on Study runtime"),
    ImportRule("research_platform.participant.core.api","research_platform.platform.composition.runtime_control","Participant ABI cannot depend upward on bootstrap wiring"),
)


def architecture_import_rules(root: Path) -> tuple[ImportRule, ...]:
    from .extensions import discover_architecture_extensions

    rules = list(DEFAULT_IMPORT_RULES)
    for extension in discover_architecture_extensions(root):
        rules.extend(getattr(extension, "IMPORT_RULES", ()))
    return tuple(rules)
