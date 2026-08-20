from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from research_platform.reliability.failure.api import FailureCatalog


@dataclass(frozen=True, slots=True)
class FailureCatalogAuditReport:
    literal_build_failures: tuple[tuple[str,str,str,str], ...]
    literal_catalog_requires: tuple[tuple[str,str,str,str], ...]
    free_form_builder_calls: tuple[str, ...]
    errors: tuple[str, ...]


class FailureCatalogSourceAudit:
    """Checks literal failure taxonomy usage in production source against the central catalog."""

    def __init__(self, source_root: Path, catalog: FailureCatalog) -> None:
        self.source_root=source_root
        self.catalog=catalog

    @staticmethod
    def _kw_literal(call:ast.Call,name:str)->str|None:
        for kw in call.keywords:
            if kw.arg==name and isinstance(kw.value,ast.Constant) and isinstance(kw.value.value,str):
                return kw.value.value
        return None

    def run(self)->FailureCatalogAuditReport:
        builds=[]; requires=[]; free_form=[]; errors=[]
        for path in self.source_root.rglob('*.py'):
            if '__pycache__' in path.parts or 'tests' in path.parts:
                continue
            try: tree=ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
            except (SyntaxError,UnicodeDecodeError): continue
            rel=str(path.relative_to(self.source_root))
            for node in ast.walk(tree):
                if not isinstance(node,ast.Call): continue
                func=node.func
                if isinstance(func,ast.Name) and func.id=='build_failure':
                    d=self._kw_literal(node,'failure_domain'); c=self._kw_literal(node,'failure_code'); s=self._kw_literal(node,'stage')
                    if d and c and s:
                        builds.append((d,c,s,rel))
                        try:self.catalog.require(d,c,s)
                        except KeyError:errors.append(f'unregistered literal build_failure taxonomy: {(d,c,s)} at {rel}:{node.lineno}')
                    if rel != 'reliability/failure/api/factory.py':
                        where=f'{rel}:{node.lineno}'
                        free_form.append(where)
                        errors.append(f'free-form build_failure bypasses FailureSpec authority at {where}')
                if isinstance(func,ast.Attribute) and func.attr=='require' and len(node.args)>=3:
                    vals=[]
                    for arg in node.args[:3]:
                        vals.append(arg.value if isinstance(arg,ast.Constant) and isinstance(arg.value,str) else None)
                    if all(vals):
                        d,c,s=vals
                        requires.append((d,c,s,rel))
                        try:self.catalog.require(d,c,s)
                        except KeyError:errors.append(f'unregistered catalog require taxonomy: {(d,c,s)} at {rel}:{node.lineno}')
        return FailureCatalogAuditReport(
            tuple(sorted(builds)),
            tuple(sorted(requires)),
            tuple(sorted(free_form)),
            tuple(sorted(errors)),
        )
