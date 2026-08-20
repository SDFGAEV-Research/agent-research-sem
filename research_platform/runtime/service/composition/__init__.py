"""Composition of platform-owned service lifecycle modules."""

from .local_runtime import LocalServiceRuntimeComposer
from .supervisor import build_service_supervisor

__all__ = ["LocalServiceRuntimeComposer", "build_service_supervisor"]
