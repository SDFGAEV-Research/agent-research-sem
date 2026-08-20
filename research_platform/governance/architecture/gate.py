from __future__ import annotations

from pathlib import Path

from research_platform.platform.kernel.project_root import discover_project_root

from .import_graph import architecture_import_rules, audit_import_rules, package_cycles, scan_imports
from .platform_policy import build_platform_audit
from .source_authority import audit_source_authorities
from .source_invariants import audit_source_invariants


def main() -> int:
    root = discover_project_root(__file__)
    failed = False
    for violation in build_platform_audit().run():
        failed = True
        print(f"FAIL {violation.kind} {violation.component_id}: {violation.detail}")
    edges = scan_imports(root)
    for violation in audit_import_rules(edges, architecture_import_rules(root)):
        failed = True
        print(
            f"FAIL forbidden_import {violation.edge.source_module}:{violation.edge.line} "
            f"-> {violation.edge.target_module}: {violation.reason}"
        )
    for cycle in package_cycles(edges):
        failed = True
        print(f"FAIL package_cycle {' -> '.join(cycle)}")
    for violation in audit_source_invariants(root):
        failed = True
        print(f"FAIL {violation.invariant} {violation.path}:{violation.line}: {violation.detail}")
    for violation in audit_source_authorities(root):
        failed = True
        print(
            f"FAIL source_authority {violation.authority} "
            f"{violation.path}:{violation.line}: {violation.detail}"
        )
    if failed:
        return 1
    print("ARCHITECTURE_GATE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
