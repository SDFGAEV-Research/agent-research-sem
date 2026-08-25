from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from research_platform.observability.logging.context.api import DiagnosticAddress
from research_platform.observability.logging.record.api import LogLevel, LogRecord
from research_platform.observability.logging.storage.runtime.jsonl import JsonlLogStore
from research_platform.scope.api import PLATFORM_SCOPE
from projects.sem_paper.composition.evolution import (
    EvolutionBindingError,
    build_sem_paper_evolution_factory,
)


class FinalReliabilityBoundaryTests(unittest.TestCase):
    def test_jsonl_log_store_round_trip_survives_new_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            record = LogRecord(
                "log-1",
                1.0,
                LogLevel.ERROR,
                "test",
                "failure",
                "safe message",
                DiagnosticAddress((PLATFORM_SCOPE,)),
            )
            JsonlLogStore(path).append(record)
            self.assertEqual(JsonlLogStore(path).query(limit=1), (record,))

    def test_scientific_evolution_rejects_placeholder_bindings(self) -> None:
        with self.assertRaises(EvolutionBindingError):
            build_sem_paper_evolution_factory()


if __name__ == "__main__":
    unittest.main()
