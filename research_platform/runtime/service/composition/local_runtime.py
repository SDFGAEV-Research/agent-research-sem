from __future__ import annotations

from pathlib import Path

from research_platform.runtime.service.api import ExactServiceRuntimePort, ServiceContractDrift, ServiceLaunchContract
from research_platform.platform.concurrency.api import TaskGroupPort
from research_platform.runtime.host.api import OperatingSystemFamily, OperatingSystemRoute
from research_platform.scope.path.api import is_absolute_target_path
from research_platform.runtime.service.runtime.capture_paths import DirectoryCapturePathProvider
from research_platform.runtime.service.runtime.environment import MaterializedServiceEnvironment, StaticServiceEnvironmentProvider
from research_platform.runtime.service.runtime.linux_backend import LinuxProcessBackend
from research_platform.runtime.service.runtime.process_adapter import LocalServiceProcessAdapter
from research_platform.runtime.service.runtime.process_contracts import ExactProcessBackend, ServiceReadinessProbe
from research_platform.runtime.service.runtime.runtime_endpoint import ExactServiceRuntimeEndpoint
from research_platform.runtime.service.runtime.start_intent_store import DirectoryServiceStartIntentStore
from research_platform.runtime.service.runtime.state_storage import FileServiceStateStore

from .supervisor import build_service_supervisor


class UnsupportedHostProcessBackend(RuntimeError):
    """The host route has no exact process provider for the selected OS."""


def compose_local_process_backend(
    operating_system: OperatingSystemRoute,
    *,
    task_group: TaskGroupPort,
) -> ExactProcessBackend:
    """Route local process supervision to the host-specific provider.

    Linux is the currently complete provider because the deployment target is
    Ubuntu. Windows must get a native exact-process provider before it is used;
    silently selecting the Linux /proc implementation would corrupt identity
    and recovery semantics.
    """

    if operating_system.identity.family is OperatingSystemFamily.LINUX:
        return LinuxProcessBackend(task_group)
    raise UnsupportedHostProcessBackend(
        "no exact local service process provider for host OS "
        f"{operating_system.identity.family.value}"
    )


class LocalServiceRuntimeComposer:
    """Compose the platform-owned local service lifecycle for any executable service.

    The caller supplies the complete environment and readiness semantics. This
    module owns only the reusable local state, capture, process and supervisor
    assembly; it does not know whether the service is a domain runtime, a model, or a
    future project runtime.
    """

    def __init__(
        self,
        *,
        state_root: Path,
        intent_root: Path,
        capture_root: Path,
        operating_system: OperatingSystemRoute,
        task_group: TaskGroupPort,
        process_backend: ExactProcessBackend | None = None,
    ) -> None:
        self.state_root = state_root.resolve()
        self.intent_root = intent_root.resolve()
        self.capture_root = capture_root.resolve()
        if any(not is_absolute_target_path(root) for root in (self.state_root, self.intent_root, self.capture_root)):
            raise ValueError("local service runtime roots must be absolute")
        self._operating_system = operating_system
        self._task_group = task_group
        self._process_backend = process_backend

    @staticmethod
    def _safe(value: str) -> str:
        return value.replace("/", "_").replace("\\", "_")

    def open(
        self,
        contract: ServiceLaunchContract,
        *,
        environment: MaterializedServiceEnvironment,
        readiness: ServiceReadinessProbe,
    ) -> ExactServiceRuntimePort:
        if environment.digest != contract.environment_digest:
            raise ServiceContractDrift(
                "materialized service environment does not match the launch contract"
            )
        service_key = self._safe(contract.service_id)
        contract_key = contract.digest()
        provider = StaticServiceEnvironmentProvider((environment,))
        backend = self._process_backend or compose_local_process_backend(
            self._operating_system,
            task_group=self._task_group,
        )
        adapter = LocalServiceProcessAdapter(
            provider,
            DirectoryCapturePathProvider(self.capture_root),
            backend,
            readiness,
        )
        state = FileServiceStateStore(self.state_root / service_key / contract_key / "state.json")
        intents = DirectoryServiceStartIntentStore(self.intent_root / service_key / contract_key)
        return ExactServiceRuntimeEndpoint(build_service_supervisor(state, intents, adapter))


__all__ = [
    "LocalServiceRuntimeComposer",
    "UnsupportedHostProcessBackend",
    "compose_local_process_backend",
]
