from __future__ import annotations

from research_platform.platform.kernel.errors import SafeExceptionDescriptor, describe_exception


class KernelExceptionDescriptor:
    """Platform adapter that exposes safe kernel exception semantics."""

    def describe(self, exc: BaseException) -> SafeExceptionDescriptor:
        return describe_exception(exc)


__all__ = ["KernelExceptionDescriptor"]
