from __future__ import annotations

import inspect
from pathlib import Path


class SemPaperModelQualificationError(ValueError):
    """The platform model-qualification handoff is not claim-eligible for SEM."""


_CANARY_REQUEST_IDENTITY_FIELDS = frozenset({"probe_digest", "request_body_digest"})
_CANARY_BINDING_IDENTITY_FIELDS = (
    "runtime_canary_evidence_digests",
    "runtime_canary_digest",
    "canary_evidence_digests",
    "canary_closure_digest",
)


def platform_canary_provenance_contract_ready() -> bool:
    """Return whether the installed platform exposes reconstructable canary provenance."""

    try:
        from research_platform.model.serving.api import RuntimeCanaryEvidence
        from research_platform.model.serving.endpoint.api import QualifiedModelEndpointBinding
    except (ImportError, AttributeError):
        return False
    canary_fields = set(getattr(RuntimeCanaryEvidence, "__dataclass_fields__", {}))
    binding_fields = set(getattr(QualifiedModelEndpointBinding, "__dataclass_fields__", {}))
    return bool(_CANARY_REQUEST_IDENTITY_FIELDS & canary_fields) and bool(
        set(_CANARY_BINDING_IDENTITY_FIELDS) & binding_fields
    )


def _require_digest(value: object, field: str) -> str:
    if type(value) is not str or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise SemPaperModelQualificationError(f"{field} must be a lowercase SHA-256 digest")
    return value


def qualified_binding_canary_evidence_digests(binding: object) -> tuple[str, ...]:
    """Extract the content-derived canary authority carried by one platform binding."""

    for field in _CANARY_BINDING_IDENTITY_FIELDS:
        value = getattr(binding, field, None)
        if value is None:
            continue
        if isinstance(value, str):
            raw = (value,)
        elif isinstance(value, (tuple, list)):
            raw = tuple(value)
        else:
            raise SemPaperModelQualificationError(
                f"qualified model binding {field} has an invalid type"
            )
        if not raw:
            continue
        digests = tuple(sorted(_require_digest(item, field) for item in raw))
        if len(digests) != len(set(digests)):
            raise SemPaperModelQualificationError(
                "qualified model binding contains duplicate runtime canary identities"
            )
        return digests
    raise SemPaperModelQualificationError(
        "qualified model binding does not carry runtime canary evidence identity"
    )



def sem_planner_runtime_canary_probe(model_id: str):
    """Return the frozen SEM planner canary executed by platform qualification."""

    from research_platform.model.serving.api import RuntimeCanaryContract, RuntimeCanaryProbe
    from research_platform.platform.kernel import canonical_digest

    if type(model_id) is not str or not model_id.strip():
        raise SemPaperModelQualificationError("SEM planner canary model_id must be non-empty")
    suite_digest = canonical_digest({
        "schema": "sem-planner-runtime-canary-suite.v1",
        "prompt_generation": "sem-paper-planner-generation-v1",
        "response_contract": "non-thinking-json-object",
    })
    contract = RuntimeCanaryContract(
        contract_id="sem-planner-nonthinking-json-v1",
        require_json_object=True,
        required_json_keys=("status",),
        allowed_finish_reasons=("stop",),
        expected_json_digest=canonical_digest({"status": "ok"}),
    )
    return RuntimeCanaryProbe(
        canary_id="sem-planner-nonthinking-json-v1",
        role="planner",
        suite_digest=suite_digest,
        request_body={
            "model": model_id,
            "messages": [{"role": "user", "content": 'Return exactly {"status":"ok"} as JSON.'}],
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 32,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_object"},
        },
        contract=contract,
    )


def verify_sem_planner_canary_authority(closure: object, binding: object) -> tuple[str, ...]:
    """Prove that the binding was authorized by the exact SEM-owned planner probe."""

    model = getattr(binding, "model", None)
    model_id = getattr(model, "model_id", None)
    expected = sem_planner_runtime_canary_probe(model_id)
    binding_digests = qualified_binding_canary_evidence_digests(binding)
    evidence = getattr(closure, "runtime_canary_evidence", None)
    if type(evidence) is not tuple or not evidence:
        raise SemPaperModelQualificationError("qualified closure exposes no runtime canary evidence")
    selected = tuple(item for item in evidence if getattr(item, "evidence_digest", None) in binding_digests)
    if tuple(sorted(getattr(item, "evidence_digest", "") for item in selected)) != binding_digests:
        raise SemPaperModelQualificationError("qualified binding canary identities do not match loaded evidence")
    matches = tuple(
        item for item in selected
        if getattr(item, "role", None) == "planner"
        and getattr(item, "canary_id", None) == expected.canary_id
        and getattr(item, "suite_digest", None) == expected.suite_digest
        and getattr(item, "probe_digest", None) == expected.digest()
        and getattr(item, "contract_digest", None) == expected.contract.digest()
        and getattr(item, "passed", None) is True
    )
    if not matches:
        raise SemPaperModelQualificationError(
            "qualified planner binding was not authorized by the exact SEM non-thinking canary"
        )
    return tuple(sorted(item.evidence_digest for item in matches))

def load_sem_qualified_model_closure(path: str | Path):
    """Load through the installed platform authority without duplicating its schema."""

    from research_platform.model.serving.endpoint.composition import (
        load_qualified_model_deployment_closure,
    )
    from research_platform.model.serving.providers.runtime_qualification_storage import (
        DirectoryRuntimeQualificationEvidenceStore,
    )

    kwargs: dict[str, object] = {
        "runtime_qualification_store_factory": DirectoryRuntimeQualificationEvidenceStore,
    }
    parameters = inspect.signature(load_qualified_model_deployment_closure).parameters
    if "runtime_canary_store_factory" in parameters:
        try:
            from research_platform.model.serving.providers.runtime_canary_storage import (
                DirectoryRuntimeCanaryEvidenceStore,
            )
        except (ImportError, AttributeError) as exc:
            raise SemPaperModelQualificationError(
                "platform closure loader requires runtime canary storage but exposes no provider"
            ) from exc
        kwargs["runtime_canary_store_factory"] = DirectoryRuntimeCanaryEvidenceStore
    return load_qualified_model_deployment_closure(path, **kwargs)


__all__ = [
    "SemPaperModelQualificationError",
    "load_sem_qualified_model_closure",
    "platform_canary_provenance_contract_ready",
    "qualified_binding_canary_evidence_digests",
    "sem_planner_runtime_canary_probe",
    "verify_sem_planner_canary_authority",
]
