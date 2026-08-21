"""Composition adapters for the prompt API; projects must not import these."""

from .binding import FrozenPromptRequestBinding

__all__ = ["FrozenPromptRequestBinding"]
