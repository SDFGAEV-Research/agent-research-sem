"""Replaceable model endpoint transports."""

from .openai_compatible import OpenAICompatibleModelEndpoint, UrllibJsonTransport

__all__ = ["OpenAICompatibleModelEndpoint", "UrllibJsonTransport"]
