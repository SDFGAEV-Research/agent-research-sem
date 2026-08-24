"""Verify one SEM live-evidence receipt before any scientific claim."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from projects.sem_paper.composition.live_evidence import (
    LiveEvidenceValidationError,
    load_live_evidence,
    validate_live_evidence,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--source-tree-digest")
    parser.add_argument("--require-claim-eligibility", action="store_true")
    args = parser.parse_args(argv)
    try:
        receipt = validate_live_evidence(
            load_live_evidence(args.receipt),
            expected_source_tree_digest=args.source_tree_digest,
            require_claim_eligibility=args.require_claim_eligibility,
        )
    except LiveEvidenceValidationError as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "status": receipt.status.value,
                "evidence_id": receipt.evidence_id,
                "receipt_digest": receipt.digest,
                "claim_eligible": receipt.claim_eligible,
                "blockers": list(receipt.blockers),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
