"""Paper-1 composition over injected platform APIs and the SEM method package."""

from .logging import bind_project_logging
from .minecraft_evidence import (
    MinecraftEvidenceAdapter,
    MinecraftEvidenceAdmissionError,
    MinecraftObservationView,
    SEMMinecraftEvidenceIngestor,
)
from .minecraft_workload import (
    MinecraftEnvironmentActionResult,
    MinecraftEnvironmentObservation,
    MinecraftPlannerDecision,
    MinecraftSuccessSpec,
    MinecraftTaskRunResult,
    MinecraftTaskSpec,
    MinecraftWorkloadFailure,
    MinecraftWorkloadRunner,
    ScriptedMinecraftPlanner,
    evaluate_success,
    task_from_mapping,
)
from .method import build_fixed_memory_treatment, build_self_evolving_treatment
from .project import (
    SemPaperBindings,
    SemPaperCompositionPorts,
    SemPaperProjectComposition,
    compose_sem_paper,
)
from .minecraft_branch import (
    MinecraftBranchExecutionError,
    MinecraftBranchExecutionResult,
    MinecraftBranchExecutorPort,
    MinecraftPairedBranchRunner,
)
from .minecraft_runtime_adapter import (
    MinecraftWorkloadEnvironmentAdapter,
    MinecraftWorkloadEnvironmentAdapterError,
)
from .minecraft_workload_executor import (
    MinecraftWorkloadBatchResult,
    MinecraftWorkloadBindingCloseError,
    MinecraftWorkloadBindingFactoryPort,
    MinecraftWorkloadBindingPort,
    MinecraftWorkloadBranchExecutor,
)

__all__ = [
    "SemPaperBindings",
    "SemPaperCompositionPorts",
    "SemPaperProjectComposition",
    "bind_project_logging",
    "MinecraftEvidenceAdapter",
    "MinecraftEvidenceAdmissionError",
    "MinecraftObservationView",
    "SEMMinecraftEvidenceIngestor",
    "MinecraftEnvironmentActionResult",
    "MinecraftEnvironmentObservation",
    "MinecraftPlannerDecision",
    "MinecraftSuccessSpec",
    "MinecraftTaskRunResult",
    "MinecraftTaskSpec",
    "MinecraftWorkloadFailure",
    "MinecraftWorkloadRunner",
    "ScriptedMinecraftPlanner",
    "evaluate_success",
    "task_from_mapping",
    "build_fixed_memory_treatment",
    "build_self_evolving_treatment",
    "compose_sem_paper",
    "MinecraftBranchExecutionError",
    "MinecraftBranchExecutionResult",
    "MinecraftBranchExecutorPort",
    "MinecraftPairedBranchRunner",
    "MinecraftWorkloadEnvironmentAdapter",
    "MinecraftWorkloadEnvironmentAdapterError",
    "MinecraftWorkloadBatchResult",
    "MinecraftWorkloadBindingCloseError",
    "MinecraftWorkloadBindingFactoryPort",
    "MinecraftWorkloadBindingPort",
    "MinecraftWorkloadBranchExecutor",
]
