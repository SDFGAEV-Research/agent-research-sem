"""Paper-1 composition over injected platform APIs and the SEM method package."""

from .logging import bind_project_logging
from .method import build_fixed_memory_treatment, build_self_evolving_treatment

__all__ = ["bind_project_logging", "build_fixed_memory_treatment", "build_self_evolving_treatment"]
