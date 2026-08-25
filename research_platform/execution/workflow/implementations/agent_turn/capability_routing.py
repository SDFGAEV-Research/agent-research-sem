from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from research_platform.participant.capability.api import (
    CapabilityDescriptor,
    CapabilityPort,
    CapabilityPolicySet,
    CapabilityRequest,
    CapabilityResult,
)
from research_platform.execution.capability.api import (
    CapabilityInvocationPipelinePort,
    RegistrationKey,
    RegistrationScopePort,
)
from research_platform.platform.kernel import ComponentIdentity, EffectClass, JsonValue, OperationResult

from .capability_effects import CapabilityEffectExecutor
from .capability_operations import CapabilityOperationAdapter


class CapabilityNotAvailable(LookupError):
    pass


class CapabilityAmbiguous(RuntimeError):
    pass


class UnsafeGenericCapability(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CapabilitySessionBinding:
    """Provider-kind-independent exported capability binding."""

    component: ComponentIdentity
    session: object
    source_role: str
    participant: object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.component, ComponentIdentity):
            raise TypeError("CapabilitySessionBinding.component must be ComponentIdentity")
        if not self.source_role.strip():
            raise ValueError("CapabilitySessionBinding.source_role must be non-empty")


class StudyCapabilityRouter(CapabilityPort):
    """Routes Agent calls by capability identity without exposing provider objects/kinds."""

    def __init__(
        self,
        operations: CapabilityOperationAdapter,
        bindings: tuple[CapabilitySessionBinding, ...],
        *,
        effect_executor: CapabilityEffectExecutor | None = None,
        consumer_component: ComponentIdentity | None = None,
        pipeline: CapabilityInvocationPipelinePort,
        scope: RegistrationScopePort,
    ) -> None:
        self._operations_adapter = operations
        self._bindings = bindings
        self._effect_executor = effect_executor
        self._consumer_component = consumer_component
        self._operations: list[OperationResult[JsonValue]] = []
        self._scope = scope
        self._register_routes(bindings)
        self._pipeline = pipeline
        self._invocation_counts: dict[str, int] = {}
        self._state_lock = RLock()

    def _register_routes(self, bindings: tuple[CapabilitySessionBinding, ...]) -> None:
        seen: set[str] = set()
        for binding in bindings:
            descriptors = tuple(getattr(binding.session, "capabilities"))
            for descriptor in descriptors:
                if not isinstance(descriptor, CapabilityDescriptor):
                    raise TypeError("CapabilityExportSession.capabilities must contain CapabilityDescriptor")
                if descriptor.capability_id in seen:
                    raise CapabilityAmbiguous(
                        f"capability is exported by multiple participants: {descriptor.capability_id}"
                    )
                seen.add(descriptor.capability_id)
                self._scope.register(
                    RegistrationKey("capability", descriptor.capability_id),
                    (binding, descriptor),
                )

    def describe(self, capability_id: str) -> CapabilityDescriptor:
        try:
            with self._scope.acquire(RegistrationKey("capability", capability_id)) as route:
                return route[1]
        except KeyError as exc:
            raise CapabilityNotAvailable(capability_id) from exc

    def _ordinal(self, capability_id: str) -> int:
        with self._state_lock:
            current = self._invocation_counts.get(capability_id, 0)
            self._invocation_counts[capability_id] = current + 1
            return current

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            lease = self._scope.acquire(RegistrationKey("capability", request.capability_id))
            with lease as route:
                binding, descriptor = route
                ordinal = self._ordinal(request.capability_id)
                return self._pipeline.invoke(
                    descriptor=descriptor,
                    request=request,
                    execute=lambda: self._invoke_routed(binding, descriptor, request, ordinal),
                )
        except KeyError as exc:
            raise CapabilityNotAvailable(request.capability_id) from exc

    def _invoke_routed(
        self,
        binding: CapabilitySessionBinding,
        descriptor: CapabilityDescriptor,
        request: CapabilityRequest,
        ordinal: int,
    ) -> CapabilityResult:
        if descriptor.effect_class in (EffectClass.PURE, EffectClass.IDEMPOTENT):
            execution = self._operations_adapter.invoke(
                target=binding.component,
                session=binding.session,
                descriptor=descriptor,
                request=request,
                invocation_ordinal=ordinal,
            )
            with self._state_lock:
                self._operations.append(execution.operation)
            return execution.result
        if self._effect_executor is None or self._consumer_component is None:
            raise UnsafeGenericCapability(
                f"generic capability {descriptor.capability_id} has {descriptor.effect_class.value} effects; "
                "a generic EffectIntentJournal and consumer identity are required"
            )
        execution = self._effect_executor.invoke(
            target=binding.component,
            session=binding.session,
            descriptor=descriptor,
            request=request,
            consumer_component=self._consumer_component,
            invocation_ordinal=ordinal,
        )
        with self._state_lock:
            self._operations.extend(execution.operation_results)
        return execution.result

    def drain_operations(self) -> tuple[OperationResult[JsonValue], ...]:
        with self._state_lock:
            rows = tuple(self._operations)
            self._operations.clear()
            return rows

    def close(self) -> None:
        self._scope.dispose()


__all__ = [
    "CapabilityAmbiguous",
    "CapabilityNotAvailable",
    "CapabilitySessionBinding",
    "StudyCapabilityRouter",
    "UnsafeGenericCapability",
]
