from __future__ import annotations

from research_platform.participant.method.runtime import InMemoryMethodObservationSink

from tests_support import build_self_evolving_memory_method

import unittest

from research_platform.experimentation.evaluation.api import ComparabilityProof
from research_platform.platform.kernel import ExecutionContext
from research_platform.participant.method.api import MethodServices

from projects.sem_paper.method.self_evolving_memory import (
    EvolutionStageFactories,
    PipelineSessionEvolutionFactory,
)
from projects.sem_paper.method.self_evolving_memory.evolution import (
    ArchitectureObservationReport,
    CandidateArchitecture,
    EditKind,
    EvaluationProof,
    EvolutionEligibility,
    PrimitiveEdit,
    PrimitiveEditKind,
    StructuralIntent,
)


class SEMEvolutionStageCompositionV175Tests(unittest.TestCase):
    def test_only_eligibility_and_diagnosis_receive_session_source(self) -> None:
        built: list[str] = []

        class Eligibility:
            def check(self): return EvolutionEligibility(True, "eligible")
        class Diagnosis:
            def diagnose(self): return ArchitectureObservationReport("g0", "neutral", ("e1",))
        class Synthesis:
            def propose(self, aor): return StructuralIntent(EditKind.CREATE, "r", {"node_id": "n"})
        class Compiler:
            def compile(self, intent, base):
                return CandidateArchitecture(
                    base, "candidate", {"nodes": ["n"]}, "d" * 64,
                    (PrimitiveEdit(PrimitiveEditKind.CREATE, "n"),),
                    (object(),),
                )
        class Evaluator:
            def evaluate(self, candidate):
                return EvaluationProof(
                    ComparabilityProof(True, "pair", (), "cp", "w", "e", "t"),
                    {"gain": 1.0},
                )
        class Acceptance:
            def accept(self, intent, proof): return True
        class Adoption:
            def adopt(self, candidate, proof): return "g1"

        def source_factory(name, value):
            def build(source):
                built.append(name)
                self.assertFalse(hasattr(source, "ingest"))
                self.assertTrue(hasattr(source, "snapshot"))
                return value()
            return build

        def isolated_factory(name, value):
            def build():
                built.append(name)
                return value()
            return build

        def adoption_factory(authority):
            built.append("adoption")
            self.assertTrue(callable(getattr(authority, "commit_prepared_adoption", None)))
            self.assertTrue(callable(getattr(authority, "open_evidence_cut", None)))
            self.assertFalse(hasattr(authority, "snapshot"))
            return Adoption()

        stages = EvolutionStageFactories(
            eligibility=source_factory("eligibility", Eligibility),
            diagnosis=source_factory("diagnosis", Diagnosis),
            synthesis=isolated_factory("synthesis", Synthesis),
            compiler=isolated_factory("compiler", Compiler),
            evaluator=isolated_factory("evaluator", Evaluator),
            acceptance=isolated_factory("acceptance", Acceptance),
            adoption=adoption_factory,
        )
        evolution = PipelineSessionEvolutionFactory(stages)
        endpoint = build_self_evolving_memory_method(
            evolution_factory=evolution,
            evolution_provider_id="sem.evolution.pipeline.test.v1",
        )
        session = endpoint.open_session(
            session_id="s",
            services=MethodServices(InMemoryMethodObservationSink()),
        )
        context = ExecutionContext("run", "trace", "span", task_id="task")
        session.task_completed({}, context)
        self.assertEqual(
            built,
            ["eligibility", "diagnosis", "synthesis", "compiler", "evaluator", "acceptance", "adoption"],
        )
        self.assertEqual(session.diagnostics()["generation"], "g1")
        self.assertEqual(
            [record.mutation_type for record in session.mutation_history()],
            ["TASK_COMPLETED", "ADOPTION_COMMIT"],
        )

    def test_self_treatment_cannot_be_constructed_without_explicit_evolution_provider(self) -> None:
        with self.assertRaises(TypeError):
            build_self_evolving_memory_method()  # type: ignore[call-arg]


if __name__ == "__main__":
    unittest.main()
