"""Paper-1 composition over injected platform APIs and the SEM method package."""

from .logging import bind_project_logging
from .method import build_fixed_memory_treatment, build_self_evolving_treatment
from .participant import (
    SemPaperMethodParticipantEndpoint,
    SemPaperMethodParticipantVariant,
    SemPaperMethodResolver,
)
from .project import SemPaperBindings, SemPaperCompositionPorts, compose_sem_paper

__all__ = [
    "SemPaperBindings",
    "SemPaperCompositionPorts",
    "SemPaperMethodParticipantEndpoint",
    "SemPaperMethodParticipantVariant",
    "SemPaperMethodResolver",
    "bind_project_logging",
    "build_fixed_memory_treatment",
    "build_self_evolving_treatment",
    "compose_sem_paper",
]
