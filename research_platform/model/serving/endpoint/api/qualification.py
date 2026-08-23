from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from research_platform.platform.kernel import ImmutableModelIdentity


def _require_digest(value: str, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class QualifiedModelEndpointBinding:
    """Frozen endpoint identity imported from model/deployment qualification.

    Projects may consume this contract, but cannot construct scientific model
    identity from ad-hoc environment variables once the binding is required.
    """

    role: str
    deployment_id: str
    deployment_generation: str
    base_url: str
    model: ImmutableModelIdentity
    model_stack_digest: str
    qualification_certificate_digest: str
    runtime_qualification_digest: str
    host_identity_digest: str
    prompt_generation: str
    completion_path: str = "/v1/chat/completions"
    timeout_s: float = 120.0

    def __post_init__(self) -> None:
        if not self.role.strip() or not self.deployment_id.strip():
            raise ValueError("qualified model binding identity is required")
        if not self.base_url.strip() or not self.prompt_generation.strip():
            raise ValueError("qualified model binding route/prompt identity is required")
        if not self.completion_path.startswith("/"):
            raise ValueError("qualified model binding completion_path must be absolute")
        if self.timeout_s <= 0:
            raise ValueError("qualified model binding timeout_s must be positive")
        for field in (
            "deployment_generation",
            "model_stack_digest",
            "qualification_certificate_digest",
            "runtime_qualification_digest",
            "host_identity_digest",
        ):
            _require_digest(getattr(self, field), field)


class QualifiedModelEndpointBindingPort(Protocol):
    """Provider boundary for selecting one already-qualified model role."""

    def binding_for(self, *, role: str, prompt_generation: str) -> QualifiedModelEndpointBinding:
        ...


__all__ = ["QualifiedModelEndpointBinding", "QualifiedModelEndpointBindingPort"]
