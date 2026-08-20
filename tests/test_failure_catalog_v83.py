from __future__ import annotations

from pathlib import Path
import unittest

from research_platform.reliability.failure.api import DEFAULT_FAILURE_CATALOG, FailureCatalog, FailureSpec, RecoveryAction

from research_platform.reliability.forensics.runtime import FailureCatalogSourceAudit
from research_platform.reliability.primitives import CrashClass
from research_platform.platform.composition.service_crash_failure import SERVICE_CRASH_FAILURE_CODES


class FailureCatalogV83Tests(unittest.TestCase):
    def test_all_service_crash_codes_are_registered_with_exact_restart_semantics(self):
        for crash_class,code in SERVICE_CRASH_FAILURE_CODES.items():
            spec=DEFAULT_FAILURE_CATALOG.require("MODEL_SERVING",code,"service_process_exit")
            self.assertEqual(spec.default_recovery,RecoveryAction.RESTART_EXACT_MODEL)

    def test_same_domain_code_cannot_be_redefined_at_different_stage(self):
        c=FailureCatalog((FailureSpec("X","CODE","stage_a",RecoveryAction.MANUAL_DIAGNOSIS),))
        with self.assertRaises(ValueError):
            c.register(FailureSpec("X","CODE","stage_b",RecoveryAction.RETRY_OPERATION))

    def test_current_source_literal_taxonomy_is_registered(self):
        root=Path(__file__).resolve().parents[1]/"research_platform"
        report=FailureCatalogSourceAudit(root,DEFAULT_FAILURE_CATALOG).run()
        self.assertEqual(report.errors,())
        self.assertGreaterEqual(len(DEFAULT_FAILURE_CATALOG.all()), 1)


if __name__=='__main__': unittest.main()
