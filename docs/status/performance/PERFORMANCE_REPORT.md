# Performance Governance Report

- Source digest: `621eb0a1e15a4c9001f529cb1255d2db6a2459553ce60d665d5d229ffe3baba1`
- Hotspots: **104**
- Findings: **125**
- P0/P1 blockers: **0**

## Coverage

| Language | Files | Hotspots | Parse errors |
|---|---:|---:|---:|
| javascript | 203 | 1 | 0 |
| python | 2602 | 98 | 0 |
| shell | 19 | 5 | 0 |

## Debt by system

| System | Hotspots |
|---|---:|
| governance | 20 |
| projects | 19 |
| runtime | 10 |
| scripts | 9 |
| environment | 9 |
| reliability | 8 |
| model | 6 |
| observability | 6 |
| experimentation | 5 |
| .server-state | 3 |
| artifact | 3 |
| deploy | 2 |
| resource | 2 |
| execution | 2 |

## Top 104 hotspots

| Score | Hotspot | Findings |
|---:|---|---|
| 55 | `deploy/container-entrypoint.sh` | sync-io-density |
| 44 | `scripts/compile_mindcraft_task_manifest.py::_iter_sources` | io-in-loop, serialization-in-loop |
| 35 | `.server-state/upstream-mc/mineflayer-4.37.1/.github/helper/updator.js` | sync-io-density |
| 35 | `projects/sem_paper/method/self_evolving_memory/typed_materialization.py::TypedMemoryMaterializer._validate_records` | serialization-in-loop, allocation-in-loop |
| 30 | `deploy/install_workspace_docker_engine.sh` | io-in-loop, sync-io-density |
| 30 | `projects/sem_paper/method/self_evolving_memory/governance/architecture/evolution.py::_explicit_composition` | whole-file-read, allocation-in-loop |
| 30 | `research_platform/model/serving/runtime/durable_recovery.py::DurableExactRecoveryRunner.run` | io-in-loop |
| 28 | `research_platform/artifact/content/providers/tar_archive.py::digest_materialized_tree` | serialization-in-loop |
| 28 | `research_platform/model/request/prompt/runtime/rendering.py::PromptRenderer.render` | serialization-in-loop |
| 28 | `research_platform/observability/capture/providers/file_persistence.py::FileRawObservationPersistence.verify` | serialization-in-loop |
| 27 | `research_platform/governance/quality/degradation_config_scan.py::scan_config_degradation` | io-in-loop, serialization-in-loop |
| 27 | `scripts/t2b_verify_evidence.py::main` | io-in-loop, serialization-in-loop |
| 20 | `projects/sem_paper/composition/scientific_closure.py::source_tree_digest` | io-in-loop, serialization-in-loop |
| 20 | `research_platform/artifact/content/providers/download.py::HttpArtifactAcquirer.acquire` | io-in-loop |
| 20 | `research_platform/governance/algorithm/providers/filesystem.py::RepositorySourceInventory.documents` | io-in-loop, serialization-in-loop |
| 20 | `research_platform/governance/concurrency/providers/filesystem.py::RepositoryConcurrencySourceInventory.documents` | io-in-loop, serialization-in-loop |
| 20 | `research_platform/governance/performance/providers/filesystem.py::RepositoryPerformanceSourceInventory.documents` | io-in-loop, serialization-in-loop |
| 20 | `research_platform/governance/release/runtime/active_pin_store.py::ActiveReleasePinStore.all` | io-in-loop, serialization-in-loop |
| 20 | `research_platform/governance/release/runtime/packager.py::ReleasePackager._stream_member` | io-in-loop |
| 20 | `research_platform/resource/directory/runtime/workspaces.py::LocalWorkspaceManager.list_workspaces` | io-in-loop, serialization-in-loop |
| 20 | `research_platform/runtime/process/capture/storage.py::CaptureStorage.scan_segments` | io-in-loop |
| 20 | `scripts/sem_paper_minecraft_application.py::_tree_digest` | io-in-loop, serialization-in-loop |
| 20 | `scripts/t2b_install_bridge_deps.sh` | sync-io-density |
| 20 | `scripts/t2b_local_gate.py::run` | io-in-loop, serialization-in-loop |
| 18 | `projects/sem_paper/method/self_evolving_memory/architecture/validation.py::ArchitectureValidator.report` | allocation-in-loop |
| 17 | `research_platform/execution/runtime/manager/runtime_history_integrity.py::verify_runtime_history_lines` | serialization-in-loop |
| 17 | `research_platform/observability/capture/providers/segment_recovery.py::recover_raw_segment` | serialization-in-loop |
| 17 | `research_platform/observability/logging/storage/runtime/jsonl.py::JsonlLogStore.query` | serialization-in-loop |
| 17 | `research_platform/reliability/forensics/providers/segment_verifier.py::scan_segment_chain` | io-in-loop, serialization-in-loop |
| 17 | `research_platform/reliability/forensics/providers/segment_verifier.py::scan_segment_chain_payloads` | io-in-loop, serialization-in-loop |
| 17 | `research_platform/runtime/service/runtime/linux_procfs.py::LinuxProcfsReader.environment` | serialization-in-loop |
| 16 | `research_platform/experimentation/checkpoint/providers/directory_store.py::DirectoryRunCheckpointStore.load` | io-in-loop, whole-file-read |
| 16 | `research_platform/experimentation/checkpoint/providers/workload_store.py::DirectoryWorkloadCheckpointStore.load` | io-in-loop, whole-file-read |
| 15 | `scripts/t2b_export_evidence.py::main` | io-in-loop |
| 14 | `research_platform/governance/algorithm/runtime/scanner.py::AlgorithmScanner.scan` | serialization-in-loop |
| 14 | `research_platform/governance/concurrency/runtime/scanner.py::ConcurrencyScanner.scan` | serialization-in-loop |
| 14 | `research_platform/governance/performance/runtime/scanner.py::PerformanceScanner.scan` | serialization-in-loop |
| 14 | `research_platform/model/request/prompt/runtime/generation_codec.py::decode_generation` | serialization-in-loop |
| 14 | `research_platform/runtime/server/runtime/operation_journal.py::JsonlServerOperationJournal._read_records` | serialization-in-loop |
| 13 | `projects/sem_paper/governance/architecture/__init__.py::audit_source_invariants` | io-in-loop |
| 13 | `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py::AutomaticSliceDiscovery.discover` | serialization-in-loop, allocation-in-loop |
| 13 | `projects/sem_paper/method/self_evolving_memory/grounded_transform.py::GroundedSemanticTransformer._procedure_reduce` | serialization-in-loop, allocation-in-loop |
| 13 | `research_platform/governance/architecture/concurrency_boundary_invariants.py::_audit_concurrency_policy_ownership` | io-in-loop |
| 13 | `research_platform/governance/architecture/concurrency_boundary_invariants.py::_audit_legacy_execution_seams` | io-in-loop |
| 13 | `research_platform/governance/architecture/source_profile.py::scan_architecture_source_profile` | io-in-loop |
| 13 | `research_platform/governance/quality/degradation_python_scan.py::scan_python_degradation` | io-in-loop |
| 13 | `research_platform/governance/quality/silent_failure.py::scan_silent_failures` | io-in-loop |
| 13 | `research_platform/observability/telemetry/metric/providers/query.py::SQLiteTelemetryReader.query` | serialization-in-loop, allocation-in-loop |
| 13 | `research_platform/reliability/forensics/runtime/catalog_audit.py::FailureCatalogSourceAudit.run` | io-in-loop |
| 13 | `research_platform/runtime/service/runtime/linux_procfs.py::LinuxProcfsReader._process_directory` | io-in-loop |
| 12 | `research_platform/environment/minecraft/composition/branch_runtime.py::MinecraftBranchRuntimeBinding._release_allocations` | lock-in-loop |
| 12 | `research_platform/environment/minecraft/composition/branch_runtime.py::MinecraftBranchRuntimeFactory.open` | lock-in-loop |
| 12 | `research_platform/resource/allocation/runtime/endpoint_allocator.py::InMemoryEndpointAllocator.allocate` | lock-in-loop |
| 10 | `.server-state/remote_probe.sh` | sync-io-density |
| 10 | `.server-state/remote_runtime_probe.sh` | sync-io-density |
| 10 | `projects/sem_paper/composition/non_minecraft_workload.py::SemPaperNonMinecraftStudyUnitAdapter.execute_bound` | io-in-loop |
| 10 | `projects/sem_paper/composition/session_state_storage.py::FileSEMSessionStateStore._read_wal` | serialization-in-loop |
| 10 | `projects/sem_paper/method/self_evolving_memory/grounded_transform.py::GroundedSemanticTransformer._pattern_reduce` | serialization-in-loop |
| 10 | `research_platform/artifact/content/providers/tar_archive.py::SafeTarArchiveMaterializer.materialize` | io-in-loop |
| 10 | `research_platform/environment/minecraft/providers/jsonl_bridge.py::JsonlMinecraftBridge._drain_stderr` | io-in-loop |
| 10 | `research_platform/environment/minecraft/providers/rcon.py::_read_exact` | io-in-loop |
| 10 | `research_platform/execution/runtime/manager/model_ports.py::HeartbeatRuntimeQualificationVerifier.verify` | io-in-loop |
| 10 | `research_platform/governance/release/runtime/package_verification.py::_stream_member_digest` | io-in-loop |
| 10 | `research_platform/model/deployment/runtime/controller.py::ModelDesiredStateController.run` | io-in-loop |
| 10 | `research_platform/observability/capture/providers/segment_writer.py::RawSegmentWriter._write_all` | io-in-loop |
| 10 | `research_platform/observability/logging/storage/runtime/jsonl.py::JsonlLogStore._iter_frozen_lines` | io-in-loop |
| 10 | `research_platform/reliability/forensics/providers/directory_change_signal.py::DirectoryChangeSignal._drain_events` | io-in-loop |
| 10 | `research_platform/runtime/process/capture/fd.py::CaptureFD.write_all` | io-in-loop |
| 10 | `research_platform/runtime/process/capture/storage.py::CaptureStorage.read_range_unverified` | io-in-loop |
| 10 | `research_platform/runtime/process/supervision/runtime/command_runner.py::_BoundedPipeCollector.drain` | io-in-loop |
| 9 | `projects/sem_paper/method/self_evolving_memory/evolution/diagnostics.py::StructuralProbeEngine._facts` | allocation-in-loop |
| 9 | `research_platform/experimentation/workload/runtime/runner.py::GenericWorkloadTaskRunner.run` | allocation-in-loop |
| 9 | `research_platform/governance/system_registry/api/topology.py::_load_catalog_semantics` | allocation-in-loop |
| 9 | `scripts/compile_mindcraft_task_manifest.py::compile_manifest` | allocation-in-loop |
| 9 | `scripts/release_regression.py::_run_parallel_plans` | allocation-in-loop |
| 7 | `projects/sem_paper/composition/minecraft_binding.py::SemPaperMinecraftWorkloadBinding._export_evidence` | serialization-in-loop |
| 7 | `projects/sem_paper/method/self_evolving_memory/grounded_transform.py::GroundedSemanticTransformer._knowledge_reduce` | serialization-in-loop |
| 7 | `research_platform/environment/minecraft/composition/server_service.py::MinecraftServerReadinessProbe.wait_ready` | serialization-in-loop |
| 7 | `research_platform/environment/minecraft/composition/server_service.py::MinecraftTcpReadinessProbe._wait_ready_async` | serialization-in-loop |
| 7 | `research_platform/model/serving/endpoint/providers/openai_compatible.py::AsyncioJsonTransport._read_headers` | serialization-in-loop |
| 7 | `research_platform/reliability/forensics/composition/rebuild.py::_hash_payloads` | serialization-in-loop |
| 7 | `research_platform/reliability/forensics/providers/hashlog_lookup.py::find_payload_in_hashlog` | serialization-in-loop |
| 7 | `research_platform/reliability/forensics/providers/hashlog_scanner.py::scan_hash_chain` | serialization-in-loop |
| 7 | `research_platform/reliability/forensics/providers/hashlog_scanner.py::scan_hash_chain_payloads` | serialization-in-loop |
| 7 | `research_platform/runtime/service/runtime/readiness.py::HttpEndpointReadinessProbe._wait_ready_async` | serialization-in-loop |
| 7 | `research_platform/runtime/service/runtime/readiness.py::ProcessAliveReadinessProbe._wait_ready_async` | serialization-in-loop |
| 6 | `projects/sem_paper/composition/minecraft_workload.py::task_from_mapping` | allocation-in-loop |
| 6 | `projects/sem_paper/composition/scientific_metrics.py::SemPaperScientificMetricProvider.compute` | allocation-in-loop |
| 6 | `projects/sem_paper/composition/scientific_metrics.py::SemPaperScientificMetricProvider.compute_statistics` | allocation-in-loop |
| 6 | `projects/sem_paper/method/self_evolving_memory/architecture/serialization.py::architecture_to_dict.transform_to_dict` | allocation-in-loop |
| 6 | `projects/sem_paper/method/self_evolving_memory/deluxe/runtime/lineage.py::MemoryLineageGraph.add_record` | allocation-in-loop |
| 6 | `projects/sem_paper/method/self_evolving_memory/evolution/identifiability.py::_behavior_facts` | allocation-in-loop |
| 6 | `research_platform/environment/minecraft/providers/jsonl_bridge.py::JsonlMinecraftBridge._start_owned` | allocation-in-loop |
| 6 | `research_platform/environment/minecraft/runtime/tasks.py::MinecraftTaskSpec.from_mapping` | allocation-in-loop |
| 6 | `research_platform/experimentation/checkpoint/providers/codec.py::RunCheckpointManifestCodec.decode` | allocation-in-loop |
| 6 | `research_platform/experimentation/run/manifest/runtime/evidence.py::decode_evidence_bundle_manifest` | allocation-in-loop |
| 6 | `research_platform/governance/algorithm/runtime/diff.py::diff_snapshots` | allocation-in-loop |
| 6 | `research_platform/governance/architecture/import_graph.py::package_cycles` | allocation-in-loop |
| 6 | `research_platform/governance/architecture/optimization.py::analyze_optimization_risks` | allocation-in-loop |
| 6 | `research_platform/governance/architecture/system_dependency_invariants.py::audit_system_dependency_invariants` | allocation-in-loop |
| 6 | `research_platform/runtime/service/runtime/linux_procfs.py::LinuxProcfsReader.start_identity` | whole-file-read |
| 6 | `scripts/sem_paper_minecraft_application.py::_write_manifest` | whole-file-read |
| 5 | `research_platform/environment/minecraft/providers/world_cut.py::FilesystemMinecraftWorldCopier.copy` | deep-copy |
| 5 | `research_platform/model/asset/runtime/storage.py::LocalModelAssetStorage.materialize` | deep-copy |
