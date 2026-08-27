# Algorithm Governance Report

- Source digest: `874fb8f972beaab9b8e001099419ef25866ae94fadb5025fff247be1702b523a`
- Analyzer revision: `javascript:javascript-structural-v2|python:python-ast-v3|shell:shell-structural-v2`
- Symbols: **6008**
- Optimization candidates: **379**

## Coverage

| Language | Files | Symbols | Parse errors |
|---|---:|---:|---:|
| javascript | 8 | 86 | 0 |
| python | 2506 | 5915 | 0 |
| shell | 3 | 7 | 0 |

## Candidate debt by system

| System | Candidates |
|---|---:|
| governance | 104 |
| projects | 76 |
| environment | 47 |
| model | 28 |
| scripts | 24 |
| runtime | 20 |
| reliability | 19 |
| experimentation | 17 |
| participant | 10 |
| observability | 9 |
| execution | 7 |
| resource | 7 |
| artifact | 4 |
| platform | 2 |
| operator | 2 |
| deploy | 1 |
| tests_support.py | 1 |
| data | 1 |

## Top 100 hotspots

| Score | Complexity | Symbol | Findings |
|---:|---|---|---|
| 100 | O(N^3+) | `projects/sem_paper/composition/scientific_metrics.py::SemPaperScientificMetricProvider.compute_statistics` | deep-nested-loop, large-control-surface |
| 98 | O(N^3+) | `research_platform/environment/minecraft/providers/assets/mineflayer_bridge/resources.js::craftItem` | deep-nested-loop |
| 95 | O(N^3+) | `research_platform/governance/architecture/participant_lifecycle_invariants.py::audit_participant_lifecycle_invariants` | deep-nested-loop, io-in-loop |
| 88 | O(N^3+) | `research_platform/governance/architecture/optimization.py::analyze_optimization_risks` | deep-nested-loop, io-in-loop |
| 84 | O(N^3+) | `research_platform/governance/architecture/effect_dependency_invariants.py::audit_effect_dependency_invariants` | deep-nested-loop, io-in-loop |
| 84 | O(N^3+) | `research_platform/governance/architecture/service_runtime_invariants.py::audit_service_runtime_invariants` | deep-nested-loop, io-in-loop |
| 84 | O(N^3+) | `research_platform/model/qualification/providers/qualification_evidence.py::FileDeploymentQualificationEvidenceStore._record` | deep-nested-loop, large-control-surface |
| 80 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/typed_materialization.py::TypedMemoryMaterializer._validate_records` | deep-nested-loop |
| 80 | recursive+iterative | `research_platform/platform/kernel/canonical.py::_normalize` | recursion-plus-loop |
| 79 | O(N^2) | `scripts/sem_paper_architecture_audit.py::_surface_inventory` | nested-loop, large-control-surface |
| 78 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py::StructuralProbeEngine._facts` | deep-nested-loop |
| 77 | O(N^2) | `projects/sem_paper/composition/scientific_metrics.py::SemPaperScientificMetricProvider.compute` | nested-loop, large-control-surface |
| 77 | O(N^2) | `scripts/t2b_verify_evidence.py::main` | nested-loop, io-in-loop, serialization-in-loop, large-control-surface |
| 76 | O(N^3+) | `research_platform/reliability/forensics/runtime/catalog_audit.py::FailureCatalogSourceAudit.run` | deep-nested-loop, io-in-loop |
| 74 | O(N^2) | `research_platform/model/qualification/providers/qualification_probe.py::LocalDeploymentCapabilityProbe._simple_index_snapshot` | nested-loop, large-control-surface |
| 73 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/architecture/validation.py::ArchitectureValidator.report` | deep-nested-loop, large-control-surface |
| 73 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py::TelemetryBook.record_query` | nested-loop, large-control-surface |
| 73 | O(N^3+) | `research_platform/governance/architecture/hotspots.py::analyze_hotspots` | deep-nested-loop, io-in-loop |
| 72 | O(N^2) | `research_platform/observability/logging/storage/runtime/jsonl.py::JsonlLogStore.query` | nested-loop, io-in-loop, serialization-in-loop |
| 71 | O(N^2) | `research_platform/participant/agent/runtime/cognition_loop.py::AgentCognitionLoop.run` | nested-loop, database-in-loop, large-control-surface |
| 71 | O(N) | `scripts/t2b_local_gate.py::run` | subprocess-in-loop, io-in-loop, serialization-in-loop |
| 70 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/architecture/canonical.py::canonical_architecture_dict` | deep-nested-loop |
| 70 | O(N) | `research_platform/model/serving/runtime/durable_recovery.py::DurableExactRecoveryRunner.run` | database-in-loop, io-in-loop |
| 69 | O(N^3+) | `research_platform/governance/architecture/failure_dependency_invariants.py::audit_failure_dependency_invariants` | deep-nested-loop |
| 69 | O(N^3+) | `research_platform/operator/maintenance/runtime/management/deployments.py::dispatch` | deep-nested-loop, large-control-surface |
| 68 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/deluxe/runtime/serving.py::DeluxeMemoryServingService.recall` | nested-loop |
| 68 | O(N^3+) | `research_platform/environment/minecraft/providers/assets/mineflayer_bridge/combat.js::attackTarget` | deep-nested-loop |
| 68 | O(N^3+) | `research_platform/governance/architecture/import_graph.py::scan_imports` | deep-nested-loop, io-in-loop |
| 67 | O(N^2) | `projects/sem_paper/composition/evolution.py::RuleBasedProposalAuthority.propose` | nested-loop |
| 67 | O(N^2) | `research_platform/artifact/content/providers/tar_archive.py::digest_materialized_tree` | nested-loop, serialization-in-loop |
| 67 | O(N^3+) | `research_platform/governance/architecture/observability_dependency_invariants.py::audit_observability_logging_leaf_invariants` | deep-nested-loop |
| 67 | O(N log N) | `scripts/compile_mindcraft_task_manifest.py::_iter_sources` | io-in-loop, serialization-in-loop |
| 66 | O(N^3+) | `research_platform/governance/architecture/capability_composition_invariants.py::audit_capability_composition_boundaries` | deep-nested-loop, io-in-loop |
| 66 | O(N^3+) | `research_platform/governance/architecture/participant_dependency_invariants.py::audit_participant_dependency_invariants` | deep-nested-loop |
| 66 | O(N^2) | `research_platform/governance/architecture/prompt_api_invariants.py::audit_prompt_api_invariants` | nested-loop, io-in-loop |
| 64 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/governance/architecture/authority.py::audit_sem_authority_invariants` | deep-nested-loop |
| 62 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/evolution/deluxe_candidate.py::DeluxeCandidatePolicy.audit` | nested-loop |
| 62 | O(N log N) | `research_platform/artifact/content/providers/tar_archive.py::SafeTarArchiveMaterializer.materialize` | io-in-loop, large-control-surface |
| 62 | O(N^2) | `research_platform/experimentation/study/runtime/protocol.py::BasicStudyMetricAggregator.aggregate` | nested-loop |
| 62 | O(N^2) | `research_platform/model/serving/runtime/capacity.py::ExactCapacityPlanner.plan` | nested-loop |
| 61 | O(N^2) | `research_platform/experimentation/workload/runtime/batch.py::GenericWorkloadBatchExecutor.execute` | nested-loop |
| 61 | O(N^3+) | `research_platform/governance/architecture/composition_root_invariants.py::audit_composition_root_imports` | deep-nested-loop, io-in-loop |
| 61 | O(N^2) | `research_platform/governance/architecture/model_dependency_invariants.py::audit_model_dependency_invariants` | nested-loop, io-in-loop |
| 61 | O(N log N) | `research_platform/governance/release/runtime/package_verification.py::verify_release_package` | io-in-loop |
| 61 | O(N log N) | `scripts/sem_paper_minecraft_application.py::run` | large-control-surface |
| 60 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/architecture/deluxe_compiler.py::DeluxeArchitectureCompiler.compile_advanced_edit` | nested-loop |
| 60 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/governance/architecture/evidence.py::audit_sem_evidence_invariants` | nested-loop |
| 60 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/governance/architecture/evolution.py::_explicit_composition` | deep-nested-loop |
| 60 | O(N^3+) | `research_platform/governance/architecture/composition_participant_invariants.py::audit_generic_participant_signatures` | deep-nested-loop, io-in-loop |
| 60 | O(N^2) | `research_platform/runtime/server/identity/providers/catalog.py::build_server_profile_catalog` | nested-loop |
| 60 | O(N^3+) | `scripts/sem_paper_architecture_audit.py::_declaration_only_leaf_packages` | deep-nested-loop |
| 59 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py::AutomaticSliceDiscovery.discover` | nested-loop, serialization-in-loop |
| 58 | O(N^3+) | `research_platform/governance/architecture/audit.py::ArchitectureAudit.run` | deep-nested-loop |
| 58 | O(N^3+) | `research_platform/governance/architecture/document_integrity_invariants.py::audit_document_integrity_invariants` | deep-nested-loop, io-in-loop |
| 57 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/deluxe/runtime/grounding.py::audit_deluxe_grounding` | nested-loop |
| 56 | O(N^2) | `research_platform/experimentation/experiment/api/tasks.py::validate_task_graph` | nested-loop |
| 56 | O(N^2) | `research_platform/experimentation/run/manifest/api/contracts.py::RunLaunchManifest.__post_init__` | nested-loop |
| 56 | O(N^2) | `research_platform/experimentation/study/runtime/matrix.py::StudyMatrixExecutor.execute` | nested-loop, database-in-loop |
| 56 | O(N^2) | `research_platform/governance/architecture/runtime_state_invariants.py::audit_runtime_state_invariants` | nested-loop, io-in-loop |
| 56 | O(N log N) | `research_platform/governance/quality/degradation_config_scan.py::scan_config_degradation` | io-in-loop, serialization-in-loop |
| 56 | O(N^2) | `research_platform/model/qualification/runtime/qualification.py::DeploymentQualificationResolver._append_native_cuda_runtime` | nested-loop |
| 55 | O(N^2) | `research_platform/experimentation/run/manifest/runtime/evidence.py::decode_evidence_bundle_manifest` | nested-loop |
| 55 | O(N^3+) | `research_platform/governance/architecture/service_api_invariants.py::audit_service_api_invariants` | deep-nested-loop |
| 55 | O(N^2) | `research_platform/governance/architecture/service_supervisor_invariants.py::audit_service_supervisor_invariants` | nested-loop, io-in-loop |
| 54 | O(N^2) | `projects/sem_paper/composition/scientific_closure.py::source_tree_digest` | nested-loop, io-in-loop, serialization-in-loop |
| 54 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/architecture/contracts.py::MemoryArchitectureSpec.topological_order` | nested-loop |
| 54 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/session_snapshot_document.py::payload_from_document` | nested-loop |
| 54 | O(N) | `research_platform/execution/capability/runtime/scoped_registry.py::ScopedRegistrationRuntime.dispose` | lock-in-loop |
| 54 | O(N^3+) | `research_platform/governance/architecture/composition_workflow_invariants.py::audit_workflow_family_firewall` | deep-nested-loop |
| 54 | O(N^2) | `research_platform/governance/architecture/participant_binding_invariants.py::audit_participant_binding_invariants` | nested-loop |
| 54 | O(N^3+) | `research_platform/governance/architecture/source_authority_engine.py::audit_authority_rules` | deep-nested-loop, io-in-loop |
| 54 | O(N^3+) | `research_platform/governance/architecture/workflow_invariants.py::_audit_dispatch_authority` | deep-nested-loop, io-in-loop |
| 54 | O(N^2) | `scripts/compile_mindcraft_task_manifest.py::compile_manifest` | nested-loop |
| 53 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/architecture/compiler.py::ArchitectureCompiler.compile_edit` | nested-loop |
| 53 | O(N^2) | `research_platform/reliability/forensics/providers/segment_verifier.py::scan_segment_chain_payloads` | nested-loop, io-in-loop, serialization-in-loop |
| 52 | O(N log N) | `research_platform/environment/minecraft/runtime/state.py::MinecraftStateProjection.from_compact` | large-control-surface |
| 52 | O(N^2) | `research_platform/environment/runtime/runtime/state_machine.py::StateMachineEnvironmentSession.restore` | nested-loop, large-control-surface |
| 52 | O(N^3+) | `research_platform/experimentation/experiment/runtime/participant_topology.py::ExperimentParticipantTopology.ordered` | deep-nested-loop |
| 52 | O(N^2) | `research_platform/governance/algorithm/providers/filesystem.py::RepositorySourceInventory.documents` | nested-loop, io-in-loop, serialization-in-loop |
| 52 | O(N^3+) | `research_platform/governance/architecture/status_invariants.py::audit_status_invariants` | deep-nested-loop |
| 52 | O(N) | `research_platform/runtime/server/runtime/operation_journal.py::JsonlServerOperationJournal._read_records` | serialization-in-loop |
| 51 | O(N^2) | `research_platform/environment/minecraft/providers/jsonl_bridge.py::JsonlMinecraftBridge.start` | nested-loop |
| 51 | O(N^2) | `research_platform/execution/lifecycle/manager.py::LifecycleManager._topological_order` | nested-loop |
| 51 | O(N^2) | `research_platform/governance/algorithm/runtime/diff.py::diff_snapshots` | nested-loop |
| 51 | O(N^3+) | `research_platform/governance/architecture/composition_family_invariants.py::audit_composition_family_firewall` | deep-nested-loop |
| 51 | O(N) | `research_platform/runtime/server/health/runtime/diagnostics.py::ServerDiagnosticProjector.project` | complexity-review |
| 50 | O(N^3+) | `projects/sem_paper/composition/study.py::build_sem_paper_study_protocol` | deep-nested-loop |
| 50 | O(N^2) | `research_platform/environment/catalog/runtime/catalog.py::ExecutionEnvironmentCatalog.resolve` | nested-loop |
| 50 | O(N^3+) | `research_platform/governance/architecture/import_graph.py::package_cycles` | deep-nested-loop |
| 50 | O(N^3+) | `research_platform/governance/architecture/workflow_invariants.py::_literal_operation_types` | deep-nested-loop, io-in-loop |
| 50 | O(N) | `research_platform/model/qualification/providers/qualification_probe.py::LocalDeploymentCapabilityProbe._index` | complexity-review |
| 50 | O(N^2) | `research_platform/runtime/session/runtime/environment.py::load_controller_environment` | nested-loop |
| 49 | O(N^2) | `projects/sem_paper/composition/minecraft_workload.py::evaluate_success` | nested-loop |
| 49 | O(N^2) | `projects/sem_paper/composition/non_minecraft_workload.py::SemPaperNonMinecraftStudyUnitAdapter.execute_bound` | nested-loop, io-in-loop |
| 49 | O(N^3+) | `research_platform/governance/architecture/operator_route_invariants.py::audit_operator_route_invariants` | deep-nested-loop |
| 49 | O(N^3+) | `research_platform/governance/architecture/study_invariants.py::_literal_operation_types` | deep-nested-loop, io-in-loop |
| 49 | O(N^2) | `research_platform/observability/logging/storage/runtime/jsonl.py::_decode_record` | nested-loop |
| 49 | O(N) | `scripts/sem_paper_minecraft_application.py::_write_manifest` | complexity-review |
| 48 | O(N^3+) | `research_platform/environment/minecraft/providers/assets/mineflayer_bridge/resources.js::smeltItem` | deep-nested-loop |
| 48 | O(N^2) | `research_platform/environment/minecraft/runtime/tasks.py::MinecraftTaskSpec.from_mapping` | nested-loop |
