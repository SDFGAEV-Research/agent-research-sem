from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .source_index import source_nodes, source_text, source_tree


@dataclass(frozen=True, slots=True)
class ModuleHotspot:
    module: str
    path: str
    physical_lines: int
    functions: int
    classes: int
    imports: int
    branches: int
    exception_handlers: int
    max_function_lines: int
    score: int


def analyze_hotspots(root: Path, package_roots: tuple[str,...]=( "research_platform","projects")) -> tuple[ModuleHotspot,...]:
    rows=[]
    for pkg in package_roots:
        base=root/pkg
        if not base.exists(): continue
        for path in sorted(base.rglob("*.py")):
            text=source_text(path); tree=source_tree(path); nodes=source_nodes(path); funcs=[n for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
            branches=sum(isinstance(n,(ast.If,ast.For,ast.AsyncFor,ast.While,ast.Try,ast.Match,ast.IfExp)) for n in nodes)
            imports=sum(isinstance(n,(ast.Import,ast.ImportFrom)) for n in nodes); classes=sum(isinstance(n,ast.ClassDef) for n in nodes); handlers=sum(isinstance(n,ast.ExceptHandler) for n in nodes)
            max_fn=max((getattr(n,"end_lineno",n.lineno)-n.lineno+1 for n in funcs),default=0)
            lines=len(text.splitlines()); module=".".join(path.relative_to(root).with_suffix("").parts).replace(".__init__","")
            score=lines + branches*8 + imports*3 + handlers*10 + max(0,max_fn-50)*2
            rows.append(ModuleHotspot(module,path.relative_to(root).as_posix(),lines,len(funcs),classes,imports,branches,handlers,max_fn,score))
    return tuple(sorted(rows,key=lambda x:(-x.score,x.module)))
