from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from projects.sem_paper.composition import (
    PRIMARY_TASK_FAMILIES,
    task_from_mapping,
    validate_primary_task_manifest,
)
from projects.sem_paper.composition.scientific_metrics import (
    ScientificMetricComputationError,
    ScientificAuxiliaryEvidenceProducer,
    ScientificAuxiliarySample,
    decode_scientific_auxiliary_evidence,
)
from projects.sem_paper.composition.study import (
    build_sem_paper_study_protocol,
    compile_sem_paper_experiment_plan,
    is_claim_ready_protocol,
)
from research_platform.experimentation.run.runtime.diagnostics import exception_chain
from research_platform.observability.logging.storage.runtime.jsonl import (
    JsonlLogCorruptionError,
    JsonlLogStore,
)
from research_platform.observability.logging.context.api import DiagnosticAddress
from research_platform.observability.logging.record.api import LogLevel, LogRecord
from research_platform.scope.api import PLATFORM_SCOPE


class DeepRepairContractTests(unittest.TestCase):
    def test_primary_manifest_is_exactly_six_families(self) -> None:
        path = Path(__file__).parents[1] / "projects/sem_paper/experiments/manifests/sem_primary_tasks_v1.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        tasks = tuple(task_from_mapping(row) for row in raw["tasks"])
        validated = validate_primary_task_manifest(tasks)
        self.assertEqual({task.family for task in validated}, set(PRIMARY_TASK_FAMILIES))
        self.assertEqual(len(validated), 6)

    def test_auxiliary_probability_and_distance_ranges_are_closed(self) -> None:
        base = {
            "schema_version": "sem-scientific-auxiliary.v1",
            "evidence_id": "e",
            "producer": "test",
            "source_tree_digest": "0" * 64,
            "plan_digest": "1" * 64,
            "protocol_digest": "2" * 64,
            "binding_digest": "3" * 64,
            "values": {"TDP": 0.0, "ELCE": 0.0, "HPEF": 1.0, "GAG": 1.0},
            "evidence_refs": ["test:ref"],
        }
        for name, value in (("TDP", -1.0), ("HPEF", 1.1), ("GAG", -0.1)):
            candidate = dict(base)
            candidate["values"] = dict(base["values"])
            candidate["values"][name] = value
            with self.assertRaises(ScientificMetricComputationError):
                decode_scientific_auxiliary_evidence(candidate)

    def test_exception_chain_contains_only_safe_descriptors(self) -> None:
        try:
            try:
                raise RuntimeError("token=sk-secret-value")
            except RuntimeError as inner:
                raise ValueError("outer password=hunter2") from inner
        except ValueError as exc:
            rows = exception_chain(exc)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("error_digest" in row for row in rows))
        self.assertTrue(all("sk-secret" not in row["message"] for row in rows))
        self.assertEqual(len(rows[0]["error_digest"]), 64)

    def test_jsonl_rejects_corrupt_complete_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text("{not-json}\n", encoding="utf-8")
            with self.assertRaises(JsonlLogCorruptionError):
                JsonlLogStore(path).query()

    def test_claim_ready_matrix_contains_external_and_ablation_arms(self) -> None:
        protocol = build_sem_paper_study_protocol(
            study_id="claim-ready-test",
            workload_id="claim-ready-workload",
            task_manifest_digest="a" * 64,
            seed_identity={"seed": "test"},
            fixed_configuration={},
            candidate_configuration={},
            matrix_profile="claim-ready",
        )
        self.assertTrue(is_claim_ready_protocol(protocol))
        plan = compile_sem_paper_experiment_plan(protocol)
        self.assertEqual(len(plan.bindings), 12)
        self.assertEqual(
            {item.comparator_role for item in plan.bindings},
            {"primary", "external", "ablation"},
        )

    def test_auxiliary_producer_requires_complete_typed_seed_samples(self) -> None:
        protocol = build_sem_paper_study_protocol(
            study_id="aux-test",
            workload_id="aux-workload",
            task_manifest_digest="a" * 64,
            seed_identity={"seed": "test"},
            fixed_configuration={},
            candidate_configuration={},
            matrix_profile="core-6",
        )
        plan = compile_sem_paper_experiment_plan(protocol)
        evidence = ScientificAuxiliaryEvidenceProducer().produce(
            plan=plan,
            source_tree_digest="b" * 64,
            samples=(
                ScientificAuxiliarySample("Seed-C", 0.2, -0.1, 0.8, 0.9),
                ScientificAuxiliarySample("Seed-X", 0.4, 0.3, 0.7, 1.0),
            ),
            evidence_refs=("artifact://aux/seed-c", "artifact://aux/seed-x"),
            producer="typed-runtime-producer.v1",
        )
        self.assertAlmostEqual(dict(evidence.values)["TDP"], 0.3)
        with self.assertRaises(ScientificMetricComputationError):
            ScientificAuxiliaryEvidenceProducer().produce(
                plan=plan,
                source_tree_digest="b" * 64,
                samples=(ScientificAuxiliarySample("Seed-C", 0.2, -0.1, 0.8, 0.9),),
                evidence_refs=("artifact://aux/seed-c",),
                producer="typed-runtime-producer.v1",
            )

    def test_jsonl_rotation_keeps_recent_records_queryable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            store = JsonlLogStore(path, max_bytes=1, max_segments=2)
            for index in range(3):
                store.append(
                    LogRecord(
                        f"log-{index}",
                        float(index),
                        LogLevel.INFO,
                        "test",
                        "event",
                        "safe",
                        DiagnosticAddress((PLATFORM_SCOPE,)),
                    )
                )
            self.assertEqual(store.query(limit=1)[0].log_id, "log-2")
            self.assertGreaterEqual(store.last_query_diagnostics["rotated_segments"], 1)


if __name__ == "__main__":
    unittest.main()
