# Algorithm Governance Report

- Source digest: `621eb0a1e15a4c9001f529cb1255d2db6a2459553ce60d665d5d229ffe3baba1`
- Analyzer revision: `javascript:javascript-structural-v2|python:python-ast-v4|shell:shell-structural-v2`
- Symbols: **7483**
- Optimization candidates: **631**

## Coverage

| Language | Files | Symbols | Parse errors |
|---|---:|---:|---:|
| javascript | 203 | 815 | 0 |
| python | 2602 | 6656 | 0 |
| shell | 19 | 12 | 0 |

## Candidate debt by system

| System | Candidates |
|---|---:|
| .server-state | 186 |
| governance | 133 |
| projects | 77 |
| environment | 50 |
| model | 32 |
| scripts | 32 |
| runtime | 21 |
| platform | 19 |
| reliability | 19 |
| experimentation | 16 |
| participant | 11 |
| observability | 11 |
| execution | 9 |
| resource | 7 |
| artifact | 4 |
| operator | 2 |
| deploy | 1 |
| tests_support.py | 1 |

## Top 100 hotspots

| Score | Complexity | Symbol | Findings |
|---:|---|---|---|
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/blocks.js::inject` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/chat.js::inject` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/craft.js::craftOnce` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/craft.js::inject` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/craft.js::startClicking` | deep-nested-loop |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/craft.js::unusedRecipeSlots` | deep-nested-loop |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/digging.js::dig` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/digging.js::inject` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/entities.js::inject` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/inventory.js::inject` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/physics.js::inject` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/test/externalTest.js::describe` | deep-nested-loop, io-in-loop |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/test/externalTests/plugins/testCommon.js::inject` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/test/internalTest.js::describe` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/index.js::inject` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/lib/movements.js::updateCollisionIndex` | deep-nested-loop |
| 100 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/test/internalTest.js::describe` | deep-nested-loop, large-control-surface |
| 100 | O(N^3+) | `projects/sem_paper/composition/scientific_metrics.py::SemPaperScientificMetricProvider.compute_statistics` | deep-nested-loop, large-control-surface |
| 98 | O(N^3+) | `research_platform/environment/minecraft/providers/assets/mineflayer_bridge/resources.js::craftItem` | deep-nested-loop |
| 93 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/team.js::inject` | deep-nested-loop |
| 88 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/lib/movements.js::getMoveJumpUp` | deep-nested-loop |
| 85 | O(N^2) | `.server-state/upstream-mc/mineflayer-4.37.1/.github/helper/updator.js::main` | nested-loop, io-in-loop |
| 85 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/inventory.js::clickWindow` | deep-nested-loop |
| 84 | O(N^3+) | `research_platform/model/qualification/providers/qualification_evidence.py::FileDeploymentQualificationEvidenceStore._record` | deep-nested-loop, large-control-surface |
| 83 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/blocks.js::waitForChunksToLoad` | deep-nested-loop |
| 81 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/team.js::teamHandler` | deep-nested-loop |
| 81 | recursive+iterative | `research_platform/platform/kernel/canonical.py::_normalize` | recursion-plus-loop |
| 80 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/typed_materialization.py::TypedMemoryMaterializer._validate_records` | deep-nested-loop |
| 79 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/bed.js::inject` | deep-nested-loop, large-control-surface |
| 79 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/scoreboard.js::inject` | deep-nested-loop |
| 79 | O(N^3+) | `research_platform/governance/architecture/optimization.py::analyze_optimization_risks` | deep-nested-loop |
| 79 | O(N) | `research_platform/governance/architecture/source_profile.py::scan_architecture_source_profile` | complexity-contract, io-in-loop, large-control-surface |
| 79 | O(N^2) | `scripts/sem_paper_architecture_audit.py::_surface_inventory` | nested-loop, large-control-surface |
| 78 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py::StructuralProbeEngine._facts` | deep-nested-loop |
| 77 | O(N^2) | `projects/sem_paper/composition/scientific_metrics.py::SemPaperScientificMetricProvider.compute` | nested-loop, large-control-surface |
| 77 | O(N^2) | `scripts/t2b_verify_evidence.py::main` | nested-loop, io-in-loop, serialization-in-loop, large-control-surface |
| 76 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/test/internalTest.js::describe` | deep-nested-loop |
| 76 | O(N^3+) | `research_platform/governance/architecture/effect_dependency_invariants.py::audit_effect_dependency_invariants` | deep-nested-loop |
| 76 | O(N^3+) | `research_platform/reliability/forensics/runtime/catalog_audit.py::FailureCatalogSourceAudit.run` | deep-nested-loop, io-in-loop |
| 74 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/examples/trader.js::trade` | deep-nested-loop |
| 74 | O(N^2) | `research_platform/model/qualification/providers/qualification_probe.py::LocalDeploymentCapabilityProbe._simple_index_snapshot` | nested-loop, large-control-surface |
| 73 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/simple_inventory.js::inject` | deep-nested-loop |
| 73 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/villager.js::inject` | deep-nested-loop, large-control-surface |
| 73 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/architecture/validation.py::ArchitectureValidator.report` | deep-nested-loop, large-control-surface |
| 73 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py::TelemetryBook.record_query` | nested-loop, large-control-surface |
| 72 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/index.js::monitorMovement` | deep-nested-loop, large-control-surface |
| 72 | O(N^2) | `research_platform/model/serving/runtime/capacity.py::ExactCapacityPlanner.plan` | nested-loop |
| 71 | O(N^2) | `research_platform/participant/agent/runtime/cognition_loop.py::AgentCognitionLoop.run` | nested-loop, database-in-loop, large-control-surface |
| 71 | O(N) | `scripts/t2b_local_gate.py::run` | subprocess-in-loop, io-in-loop, serialization-in-loop |
| 70 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/architecture/canonical.py::canonical_architecture_dict` | deep-nested-loop |
| 70 | O(N) | `research_platform/model/serving/runtime/durable_recovery.py::DurableExactRecoveryRunner.run` | database-in-loop, io-in-loop |
| 70 | O(N^2) | `research_platform/observability/logging/storage/runtime/jsonl.py::JsonlLogStore.query` | nested-loop, serialization-in-loop |
| 69 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/deluxe/runtime/serving.py::DeluxeMemoryServingService.recall` | nested-loop |
| 69 | O(N^3+) | `research_platform/governance/architecture/failure_dependency_invariants.py::audit_failure_dependency_invariants` | deep-nested-loop |
| 69 | O(N^3+) | `research_platform/operator/maintenance/runtime/management/deployments.py::dispatch` | deep-nested-loop, large-control-surface |
| 68 | O(N^2) | `projects/sem_paper/composition/evolution.py::RuleBasedProposalAuthority.propose` | nested-loop |
| 68 | O(N^3+) | `research_platform/environment/minecraft/providers/assets/mineflayer_bridge/combat.js::attackTarget` | deep-nested-loop |
| 67 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/entities.js::handlePlayerInfoBitfield` | deep-nested-loop |
| 67 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/explosion.js::calcExposure` | deep-nested-loop |
| 67 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/place_entity.js::inject` | deep-nested-loop |
| 67 | O(N^2) | `research_platform/artifact/content/providers/tar_archive.py::digest_materialized_tree` | nested-loop, serialization-in-loop |
| 67 | O(N^3+) | `research_platform/governance/architecture/observability_dependency_invariants.py::audit_observability_logging_leaf_invariants` | deep-nested-loop |
| 67 | O(N log N) | `scripts/compile_mindcraft_task_manifest.py::_iter_sources` | io-in-loop, serialization-in-loop |
| 66 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/test/externalTests/crafting.js::findCraftingTable` | deep-nested-loop |
| 66 | O(N^3+) | `research_platform/governance/architecture/participant_dependency_invariants.py::audit_participant_dependency_invariants` | deep-nested-loop |
| 65 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/anvil.js::inject` | deep-nested-loop |
| 65 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/governance/architecture/authority.py::audit_sem_authority_invariants` | deep-nested-loop |
| 65 | O(N^3+) | `research_platform/governance/architecture/participant_lifecycle_invariants.py::audit_participant_lifecycle_invariants` | deep-nested-loop |
| 64 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/evolution/deluxe_candidate.py::DeluxeCandidatePolicy.audit` | nested-loop |
| 64 | O(N^3+) | `research_platform/governance/architecture/hotspots.py::analyze_hotspots` | deep-nested-loop |
| 64 | O(N^3+) | `research_platform/governance/architecture/service_runtime_invariants.py::audit_service_runtime_invariants` | deep-nested-loop |
| 63 | O(N^2) | `research_platform/runtime/server/identity/providers/catalog.py::build_server_profile_catalog` | nested-loop |
| 62 | O(N log N) | `research_platform/artifact/content/providers/tar_archive.py::SafeTarArchiveMaterializer.materialize` | io-in-loop, large-control-surface |
| 62 | O(N^2) | `research_platform/experimentation/study/runtime/protocol.py::BasicStudyMetricAggregator.aggregate` | nested-loop |
| 61 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/craft.js::updateOutShape` | deep-nested-loop |
| 61 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/test/internalTest.js::it` | deep-nested-loop |
| 61 | O(N^2) | `research_platform/experimentation/workload/runtime/batch.py::GenericWorkloadBatchExecutor.execute` | nested-loop |
| 61 | O(N log N) | `research_platform/governance/release/runtime/package_verification.py::verify_release_package` | complexity-review |
| 61 | O(N^3+) | `scripts/sem_paper_architecture_audit.py::_declaration_only_leaf_packages` | deep-nested-loop |
| 61 | O(N log N) | `scripts/sem_paper_minecraft_application.py::run` | large-control-surface |
| 60 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/block_actions.js::inject` | deep-nested-loop |
| 60 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/index.js::moveToEdge` | deep-nested-loop |
| 60 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/architecture/deluxe_compiler.py::DeluxeArchitectureCompiler.compile_advanced_edit` | nested-loop |
| 60 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/governance/architecture/evidence.py::audit_sem_evidence_invariants` | nested-loop |
| 60 | O(N^3+) | `projects/sem_paper/method/self_evolving_memory/governance/architecture/evolution.py::_explicit_composition` | deep-nested-loop |
| 60 | O(N^2) | `research_platform/experimentation/experiment/api/tasks.py::validate_task_graph` | nested-loop |
| 60 | O(N^2) | `research_platform/platform/composition/execution_observability.py::build_execution_capacity_facts` | nested-loop |
| 59 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/lib/movements.js::constructor` | deep-nested-loop |
| 59 | O(N^3+) | `.server-state/upstream-mc/mineflayer-pathfinder-2.4.5/lib/movements.js::getMoveParkourForward` | deep-nested-loop |
| 59 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/deluxe/runtime/grounding.py::audit_deluxe_grounding` | nested-loop |
| 59 | O(N^2) | `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py::AutomaticSliceDiscovery.discover` | nested-loop, serialization-in-loop |
| 59 | O(N^2) | `research_platform/governance/algorithm/runtime/diff.py::diff_snapshots` | nested-loop |
| 59 | O(N^3+) | `research_platform/governance/architecture/capability_composition_invariants.py::audit_capability_composition_boundaries` | deep-nested-loop |
| 59 | O(N^3+) | `research_platform/governance/architecture/import_graph.py::scan_imports` | deep-nested-loop |
| 58 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/inventory.js::transfer` | deep-nested-loop |
| 58 | O(N^3+) | `research_platform/governance/architecture/audit.py::ArchitectureAudit.run` | deep-nested-loop |
| 58 | O(N^2) | `research_platform/model/qualification/runtime/qualification.py::DeploymentQualificationResolver._append_native_cuda_runtime` | nested-loop |
| 57 | O(N^3+) | `.server-state/upstream-mc/mineflayer-4.37.1/lib/plugins/bed.js::sleep` | deep-nested-loop |
| 56 | O(N^2) | `research_platform/experimentation/run/manifest/api/contracts.py::RunLaunchManifest.__post_init__` | nested-loop |
| 56 | O(N^2) | `research_platform/governance/architecture/participant_binding_invariants.py::audit_participant_binding_invariants` | nested-loop |
