from __future__ import annotations

from research_platform.reliability.diagnostics.runtime.status_projection import ForensicStatusProbe
from research_platform.platform.concurrency.api import TaskGroupPort
from research_platform.reliability.diagnostics.api import DiagnosticEvidencePort
from .runtime_status_contracts import RuntimeStatusLayout
from research_platform.observability.status.runtime import PlatformStatusService
from research_platform.execution.runtime.manager.heartbeat_storage import FileServiceHeartbeatStore
from research_platform.reliability.recovery.providers.lease_store import RecoveryLeaseStore
from research_platform.execution.runtime.manager.history import RuntimeHistory
from research_platform.execution.runtime.manager.runtime_history_storage import FileRuntimeHistoryStorage
from research_platform.execution.runtime.manager.runtime_state_storage import FileRuntimeControlStateStore
from research_platform.execution.runtime.manager.model_deployment_status import ModelDeploymentStatusProbe
from research_platform.reliability.recovery.composition import compose_recovery_lease_status_probe
from research_platform.execution.runtime.manager.runtime_transaction_status import RuntimeTransactionStatusProbe
from research_platform.execution.runtime.manager.status_readers import (
    RuntimeControlStatusReader,
    ServiceHeartbeatStatusReader,
)
from research_platform.runtime.session.runtime import default_persistent_session_backend_registry
from research_platform.runtime.session.runtime.health_projection import PersistentSessionHealthProbe
from research_platform.runtime.service.runtime.state_storage import FileServiceStateStore
from research_platform.runtime.service.runtime.start_intent_store import DirectoryServiceStartIntentStore
from research_platform.runtime.service.runtime.status_projection import ServiceOperationalStatusProbe
from research_platform.runtime.service.runtime.status_reader import ServiceOperationalStatusReader


def build_runtime_status_service(
    layout: RuntimeStatusLayout,
    forensic_evidence: DiagnosticEvidencePort,
    *,
    task_group: TaskGroupPort,
) -> PlatformStatusService:
    """Concrete IO assembly for otherwise independent read-only subsystem probes."""

    runtime_reader = RuntimeControlStatusReader(
        FileRuntimeControlStateStore(layout.runtime_state),
        RuntimeHistory(FileRuntimeHistoryStorage(layout.runtime_history)),
    )
    heartbeat_reader = ServiceHeartbeatStatusReader(FileServiceHeartbeatStore(layout.heartbeat_root))
    probes = [
        RuntimeTransactionStatusProbe(runtime_reader),
        compose_recovery_lease_status_probe(RecoveryLeaseStore(layout.recovery_lease)),
    ]

    registry = default_persistent_session_backend_registry(task_group)
    if layout.server_session is not None:
        probes.insert(
            0,
            PersistentSessionHealthProbe(registry.build_status_probe(layout.server_session)),
        )

    probes.extend(
        ModelDeploymentStatusProbe(
            deployment,
            heartbeat_reader,
            heartbeat_max_age_seconds=layout.heartbeat_max_age_seconds,
        )
        for deployment in sorted(layout.deployments, key=lambda item: item.deployment_id)
    )
    probes.extend(
        ServiceOperationalStatusProbe(
            binding.service_id,
            ServiceOperationalStatusReader(
                FileServiceStateStore(binding.state_path),
                DirectoryServiceStartIntentStore(binding.start_intent_root),
            ),
        )
        for binding in sorted(layout.services, key=lambda item: item.service_id)
    )
    probes.append(ForensicStatusProbe(forensic_evidence))
    return PlatformStatusService(probes)


__all__ = ["build_runtime_status_service"]
