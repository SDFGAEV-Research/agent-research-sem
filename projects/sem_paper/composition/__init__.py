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
    validate_task_manifest,
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
from .non_minecraft_workload import (
    NonMinecraftEnvironmentFactoryPort,
    NonMinecraftEvidencePort,
    NonMinecraftMethodObservationSinkFactoryPort,
    NonMinecraftPlannerFactoryPort,
    NonMinecraftResultSinkPort,
    NonMinecraftStatePort,
    NonMinecraftWorkloadCloseError,
    SemPaperNonMinecraftProductionRoot,
    SemPaperNonMinecraftStudyUnitAdapter,
    SemPaperNonMinecraftWorkloadBinding,
    SemPaperNonMinecraftWorkloadBindingFactory,
    SemPaperNonMinecraftWorkloadPorts,
    compose_sem_paper_non_minecraft_production_root,
    execute_sem_paper_non_minecraft_workload,
)
from .study_execution import SemPaperMinecraftStudyUnitAdapter, SemPaperStudyUnitError
from .model_planner import (
    SemPaperModelPlanner,
    SemPaperModelPlannerBinding,
    SemPaperModelPlannerError,
    SemPaperModelPlannerFactory,
)
from .minecraft_host import SemPaperMinecraftBranchRequestFactory, SemPaperMinecraftHostInputs
from .study import SEM_PAPER_METRIC_NAMES, build_sem_paper_study_protocol

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
    "validate_task_manifest",
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
    "NonMinecraftEnvironmentFactoryPort",
    "NonMinecraftEvidencePort",
    "NonMinecraftMethodObservationSinkFactoryPort",
    "NonMinecraftPlannerFactoryPort",
    "NonMinecraftResultSinkPort",
    "NonMinecraftStatePort",
    "NonMinecraftWorkloadCloseError",
    "SemPaperNonMinecraftProductionRoot",
    "SemPaperNonMinecraftStudyUnitAdapter",
    "SemPaperNonMinecraftWorkloadBinding",
    "SemPaperNonMinecraftWorkloadBindingFactory",
    "SemPaperNonMinecraftWorkloadPorts",
    "compose_sem_paper_non_minecraft_production_root",
    "execute_sem_paper_non_minecraft_workload",
    "SemPaperMinecraftStudyUnitAdapter",
    "SemPaperStudyUnitError",
    "SemPaperModelPlanner",
    "SemPaperModelPlannerBinding",
    "SemPaperModelPlannerError",
    "SemPaperModelPlannerFactory",
    "SemPaperMinecraftBranchRequestFactory",
    "SemPaperMinecraftHostInputs",
    "SEM_PAPER_METRIC_NAMES",
    "build_sem_paper_study_protocol",
]
