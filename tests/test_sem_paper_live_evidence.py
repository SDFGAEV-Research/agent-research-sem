from __future__ import annotations

import unittest

from projects.sem_paper.composition.live_evidence import (
    LiveEvidenceReceipt,
    LiveEvidenceStatus,
    LiveEvidenceValidationError,
    decode_live_evidence,
)


class SemPaperLiveEvidenceTests(unittest.TestCase):
    def test_blocked_environment_receipt_is_not_claim_eligible(self) -> None:
        receipt = LiveEvidenceReceipt(
            schema_version="sem-paper-live-evidence.v1",
            evidence_id="attempt-1",
            status=LiveEvidenceStatus.BLOCKED_BY_ENVIRONMENT,
            run_id="run-1",
            source_tree_digest="a" * 64,
            qualified_closure_digest=None,
            t2b_gate_digest=None,
            protocol_digest="b" * 64,
            matrix_profile="paired-conformance",
            repetitions=1,
            claim_eligible=False,
            blockers=("minecraft_server_unavailable",),
        )
        self.assertFalse(receipt.claim_eligible)
        with self.assertRaises(LiveEvidenceValidationError):
            from projects.sem_paper.composition.live_evidence import validate_live_evidence

            validate_live_evidence(receipt, require_claim_eligibility=True)

    def test_pass_requires_core6_and_immutable_digests(self) -> None:
        document = {
            "schema_version": "sem-paper-live-evidence.v1",
            "evidence_id": "run-1",
            "status": "PASS",
            "run_id": "run-1",
            "source_tree_digest": "a" * 64,
            "qualified_closure_digest": "b" * 64,
            "t2b_gate_digest": "c" * 64,
            "protocol_digest": "d" * 64,
            "matrix_profile": "core-6",
            "repetitions": 12,
            "claim_eligible": True,
            "blockers": [],
        }
        receipt = decode_live_evidence(document)
        self.assertEqual(receipt.status, LiveEvidenceStatus.PASS)
        self.assertEqual(len(receipt.digest), 64)


if __name__ == "__main__":
    unittest.main()
