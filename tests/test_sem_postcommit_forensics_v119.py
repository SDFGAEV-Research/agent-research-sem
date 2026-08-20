from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from research_platform.execution.workflow.implementations.context_action.failure_classifier import ContextActionFailureClassifier
from research_platform.reliability.failure.api import RecoveryAction
from research_platform.platform.kernel import ComponentIdentity, ExecutionContext, OperationRequest, canonical_digest
from methods.self_evolving_memory.session import SEMEvolutionPostCommitError
from methods.self_evolving_memory.evolution import EvolutionStage, EvolutionStageFailure
from research_platform.execution.workflow.implementations.context_action.forensic_refs import StudyOperationFailureReferenceProjector


class SEMPostcommitForensicsV119Tests(unittest.TestCase):
    def test_classifier_detects_postcommit_semantics_without_importing_concrete_method(self):
        caller=ComponentIdentity("study","study","1","1","g")
        target=ComponentIdentity("method.sem","sem","1","7","cfg")
        ctx=ExecutionContext("r","t","s",task_id="task",operation_id="op")
        payload={"result":"x"}
        request=OperationRequest("op","invocation:test-sem-postcommit","method.task_completed",ctx,caller,target,payload,"v1",canonical_digest(payload))
        exc=SEMEvolutionPostCommitError("operation:op",RuntimeError("cut"))
        classified=ContextActionFailureClassifier().classify(request,exc)
        self.assertEqual(classified.spec.code,"EVOLUTION_POST_COMMIT_UNCERTAIN")
        self.assertEqual(classified.spec.default_recovery,RecoveryAction.RECONCILE_METHOD_STATE)

    def test_stage_identity_projects_to_generic_failure_correlation_without_platform_importing_sem(self):
        caller=ComponentIdentity("study","study","1","1","g")
        target=ComponentIdentity("method.sem","sem","1","8","cfg")
        ctx=ExecutionContext("r","t","s",task_id="task",operation_id="op")
        payload={"result":"x"}
        request=OperationRequest("op","invocation:test-sem-stage","method.task_completed",ctx,caller,target,payload,"v1",canonical_digest(payload))
        stage=EvolutionStageFailure(EvolutionStage.EVALUATION, RuntimeError("provider secret"))
        exc=SEMEvolutionPostCommitError("operation:op",stage)
        stage.__cause__=RuntimeError("provider secret")
        exc.__cause__=stage
        refs=StudyOperationFailureReferenceProjector().project(request,exc)
        self.assertIn("evolution-stage:evaluation", refs.correlation_refs)
        self.assertFalse(any("provider secret" in ref for ref in refs.correlation_refs))


if __name__ == "__main__": unittest.main()
