"""Explicit composition of the logging system from its typed leaf seams."""

from __future__ import annotations

from dataclasses import dataclass

from research_platform.governance.system_registry.api import SystemIdentity
from research_platform.observability.logging.query.api import LogQueryPort
from research_platform.observability.logging.record.api import (
    ExceptionDescriptorPort,
    LoggingSystemPort,
)
from research_platform.observability.logging.record.providers.exception_descriptor import (
    KernelExceptionDescriptor,
)
from research_platform.observability.logging.record.runtime import StructuredLoggingSystem
from research_platform.observability.logging.sink.api import LogSinkPort
from research_platform.governance.architecture.composition.capabilities import (
    EXCEPTION_DESCRIPTOR_V1,
    LOG_QUERY_V1,
    LOG_SINK_V1,
    LOGGING_SYSTEM_V1,
)
from research_platform.governance.architecture.composition.capability_graph import (
    BindingPlan,
    CapabilityCompositionPlanner,
    CapabilityOffer,
    CapabilityRequirement,
    CompositionIdentity,
    RequirementAddress,
    SystemCompositionContract,
    interface_contract_digest,
)
from research_platform.platform.kernel import canonical_digest
from research_platform.scope.api import PLATFORM_SCOPE, ScopeIdentity


_LOGGING_SYSTEM = SystemIdentity("observability", ("logging",))
_LOGGING_RECORD_SYSTEM = SystemIdentity("observability", ("logging", "record"))
_LOGGING_STORAGE_SYSTEM = SystemIdentity("observability", ("logging", "storage"))


@dataclass(frozen=True, slots=True)
class LogSinkBinding:
    """One concrete sink selected by a composition root, with evidence."""

    sink: LogSinkPort
    provider_identity: str
    configuration_digest: str


@dataclass(frozen=True, slots=True)
class LogQueryBinding:
    """One concrete query adapter selected by a composition root, with evidence."""

    query: LogQueryPort
    provider_identity: str
    configuration_digest: str


@dataclass(frozen=True, slots=True)
class ExceptionDescriptorBinding:
    """Optional record-policy provider selected by a composition root."""

    descriptor: ExceptionDescriptorPort
    provider_identity: str
    configuration_digest: str


@dataclass(frozen=True, slots=True)
class LoggingComposition:
    """Logging port plus the frozen leaf-to-system binding plan."""

    logging: LoggingSystemPort
    plan: BindingPlan
    logging_offer: CapabilityOffer


def compose_logging_system(
    *,
    sink: LogSinkBinding,
    query: LogQueryBinding,
    planner: CapabilityCompositionPlanner,
    scope: ScopeIdentity = PLATFORM_SCOPE,
    exception_descriptor: ExceptionDescriptorBinding | None = None,
    parent_plan_digest: str | None = None,
) -> LoggingComposition:
    """Compose logging without a container or a hidden default runtime dependency.

    The storage and exception providers are selected here, recorded as offers,
    then injected directly into the structured logging implementation.
    """

    descriptor_binding = exception_descriptor or ExceptionDescriptorBinding(
        descriptor=KernelExceptionDescriptor(),
        provider_identity="platform.kernel.safe-exception-descriptor.v1",
        configuration_digest=canonical_digest({"policy": "platform.kernel.safe-exception.v1"}),
    )
    sink_offer = CapabilityOffer(
        offer_id="observability.logging.sink-provider",
        owner=_LOGGING_STORAGE_SYSTEM,
        scope=scope,
        capability=LOG_SINK_V1,
        interface_digest=interface_contract_digest(LogSinkPort),
        provider_identity=sink.provider_identity,
        configuration_digest=sink.configuration_digest,
    )
    query_offer = CapabilityOffer(
        offer_id="observability.logging.query-provider",
        owner=_LOGGING_STORAGE_SYSTEM,
        scope=scope,
        capability=LOG_QUERY_V1,
        interface_digest=interface_contract_digest(LogQueryPort),
        provider_identity=query.provider_identity,
        configuration_digest=query.configuration_digest,
    )
    descriptor_offer = CapabilityOffer(
        offer_id="observability.logging.exception-descriptor-provider",
        owner=_LOGGING_RECORD_SYSTEM,
        scope=scope,
        capability=EXCEPTION_DESCRIPTOR_V1,
        interface_digest=interface_contract_digest(ExceptionDescriptorPort),
        provider_identity=descriptor_binding.provider_identity,
        configuration_digest=descriptor_binding.configuration_digest,
    )
    sink_requirement = CapabilityRequirement(
        RequirementAddress(_LOGGING_SYSTEM, "sink"),
        scope,
        LOG_SINK_V1,
        interface_contract_digest(LogSinkPort),
    )
    query_requirement = CapabilityRequirement(
        RequirementAddress(_LOGGING_SYSTEM, "query"),
        scope,
        LOG_QUERY_V1,
        interface_contract_digest(LogQueryPort),
    )
    descriptor_requirement = CapabilityRequirement(
        RequirementAddress(_LOGGING_SYSTEM, "exception-descriptor"),
        scope,
        EXCEPTION_DESCRIPTOR_V1,
        interface_contract_digest(ExceptionDescriptorPort),
    )
    logging_offer = CapabilityOffer(
        offer_id="observability.logging.structured-logging-system",
        owner=_LOGGING_SYSTEM,
        scope=scope,
        capability=LOGGING_SYSTEM_V1,
        interface_digest=interface_contract_digest(LoggingSystemPort),
        provider_identity="observability.logging.structured-system.v1",
        configuration_digest=canonical_digest(
            {
                "sink_offer": sink_offer.offer_id,
                "query_offer": query_offer.offer_id,
                "descriptor_offer": descriptor_offer.offer_id,
            }
        ),
    )
    plan = planner.freeze(
        CompositionIdentity(
            "observability.logging",
            scope,
            owner_system=_LOGGING_SYSTEM,
            parent_plan_digest=parent_plan_digest,
        ),
        (
            SystemCompositionContract(
                _LOGGING_SYSTEM,
                scope,
                offers=(logging_offer,),
                requirements=(sink_requirement, query_requirement, descriptor_requirement),
            ),
            SystemCompositionContract(
                _LOGGING_RECORD_SYSTEM,
                scope,
                offers=(descriptor_offer,),
            ),
            SystemCompositionContract(
                _LOGGING_STORAGE_SYSTEM,
                scope,
                offers=(sink_offer, query_offer),
            ),
        ),
    )
    return LoggingComposition(
        logging=StructuredLoggingSystem(
            sink.sink,
            query.query,
            exception_descriptor=descriptor_binding.descriptor,
        ),
        plan=plan,
        logging_offer=logging_offer,
    )


__all__ = [
    "ExceptionDescriptorBinding",
    "LogQueryBinding",
    "LogSinkBinding",
    "LoggingComposition",
    "compose_logging_system",
]
