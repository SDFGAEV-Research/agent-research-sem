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
from .candidate_method import (
    CandidateMethodMaterializationError,
    CandidateMethodMaterializerPort,
    SemPaperCandidateMethodMaterializer,
    build_seed_x_candidate,
)
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
from .minecraft_binding import (
    SemPaperBranchRuntimeRequestFactoryPort,
    SemPaperMethodObservationSinkFactoryPort,
    SemPaperMinecraftWorkloadBinding,
    SemPaperMinecraftWorkloadBindingFactory,
    SemPaperPlannerFactoryPort,
    SemPaperWorkloadBindingError,
)
from .minecraft_production import (
    SemPaperMinecraftProductionRoot,
    compose_sem_paper_minecraft_production_root,
)
from .model_planner import (
    SemPaperModelPlanner,
    SemPaperModelPlannerBinding,
    SemPaperModelPlannerError,
    SemPaperModelPlannerFactory,
)
from .minecraft_host import SemPaperMinecraftBranchRequestFactory, SemPaperMinecraftHostInputs

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
    "CandidateMethodMaterializationError",
    "CandidateMethodMaterializerPort",
    "SemPaperCandidateMethodMaterializer",
    "build_seed_x_candidate",
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
    "SemPaperBranchRuntimeRequestFactoryPort",
    "SemPaperMethodObservationSinkFactoryPort",
    "SemPaperMinecraftWorkloadBinding",
    "SemPaperMinecraftWorkloadBindingFactory",
    "SemPaperPlannerFactoryPort",
    "SemPaperWorkloadBindingError",
    "SemPaperMinecraftProductionRoot",
    "compose_sem_paper_minecraft_production_root",
    "SemPaperModelPlanner",
    "SemPaperModelPlannerBinding",
    "SemPaperModelPlannerError",
    "SemPaperModelPlannerFactory",
    "SemPaperMinecraftBranchRequestFactory",
    "SemPaperMinecraftHostInputs",
]
