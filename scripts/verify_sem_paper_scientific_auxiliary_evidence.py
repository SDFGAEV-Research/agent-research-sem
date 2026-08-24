"""Verify the typed auxiliary SEM estimand receipt against a compiled run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from projects.sem_paper.composition.scientific_metrics import (
    ScientificMetricComputationError,
    load_scientific_auxiliary_evidence,
    validate_scientific_auxiliary_evidence,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--source-tree-digest", required=True)
    parser.add_argument("--plan-digest", required=True)
    parser.add_argument("--protocol-digest", required=True)
    parser.add_argument("--binding-digest", required=True)
    args = parser.parse_args(argv)
    try:
        evidence = validate_scientific_auxiliary_evidence(
            load_scientific_auxiliary_evidence(args.evidence),
            expected_source_tree_digest=args.source_tree_digest,
            expected_plan_digest=args.plan_digest,
            expected_protocol_digest=args.protocol_digest,
            expected_binding_digest=args.binding_digest,
        )
    except ScientificMetricComputationError as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "status": "VALID",
                "evidence_id": evidence.evidence_id,
                "evidence_digest": evidence.digest,
                "values": dict(evidence.values),
                "evidence_refs": list(evidence.evidence_refs),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
