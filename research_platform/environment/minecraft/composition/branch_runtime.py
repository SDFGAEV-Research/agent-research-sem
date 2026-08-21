from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from research_platform.resource.allocation.api import EndpointAllocation, EndpointAllocationPort

from ..api import (
    MinecraftBranchRuntimeFactoryPort,
    MinecraftBranchRuntimePort,
    MinecraftBranchRuntimeRequest,
    MinecraftBranchServerFactoryPort,
    MinecraftEnvironmentSpec,
    MinecraftServerLifecyclePort,
)
from .environment import MinecraftEnvironmentAssembly
from ..runtime import MinecraftEnvironmentImplementation


class MinecraftBranchRuntimeError(RuntimeError):
    """A branch runtime failed and its cleanup may also require inspection."""

    def __init__(
        self,
        message: str,
        *,
        phase: str,
        cause: BaseException | None = None,
        cleanup_errors: tuple[BaseException, ...] = (),
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.cause = cause
        self.cleanup_errors = cleanup_errors


class MinecraftBranchEnvironmentFactoryPort(Protocol):
    def compose(self, spec: MinecraftEnvironmentSpec) -> MinecraftEnvironmentAssembly: ...


class MinecraftBranchRuntimeBinding(MinecraftBranchRuntimePort):
    """Own one branch's server/session/endpoint lifecycle in reverse order."""

    def __init__(
        self,
        *,
        allocation: EndpointAllocation,
        implementation: MinecraftEnvironmentImplementation,
        environment_runtime: object,
        server: MinecraftServerLifecyclePort,
        session_id: str,
        endpoint_allocations: EndpointAllocationPort,
    ) -> None:
        self.allocation = allocation
        self.implementation = implementation
        self._environment_runtime = environment_runtime
        self._server = server
        self._session_id = session_id
        self._endpoint_allocations = endpoint_allocations
        self._session: object | None = None
        self._closed = False

    def open_session(self, services: object) -> object:
        if self._closed:
            raise MinecraftBranchRuntimeError("branch runtime is closed")
        if self._session is not None:
            return self._session
        try:
            self._server.start()
            self._server.verify_ready()
            self._session = self._environment_runtime.open_session(
                self.implementation,
                session_id=self._session_id,
                services=services,
            )
            return self._session
        except BaseException as exc:
            cleanup_errors: list[BaseException] = []
            try:
                self._server.stop()
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
            try:
                self._endpoint_allocations.release(self.allocation.allocation_id)
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
            if cleanup_errors:
                raise MinecraftBranchRuntimeError(
                    "branch runtime start failed and cleanup failed",
                    phase="start",
                    cause=exc,
                    cleanup_errors=tuple(cleanup_errors),
                ) from exc
            raise MinecraftBranchRuntimeError(
                "branch runtime start failed",
                phase="start",
                cause=exc,
            ) from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        errors: list[BaseException] = []
        if self._session is not None:
            try:
                self._session.close()
            except BaseException as exc:
                errors.append(exc)
        try:
            self._server.stop()
        except BaseException as exc:
            errors.append(exc)
        try:
            self._endpoint_allocations.release(self.allocation.allocation_id)
        except BaseException as exc:
            errors.append(exc)
        if errors:
            raise MinecraftBranchRuntimeError(
                f"branch runtime close failed ({len(errors)} cleanup errors)",
                phase="close",
                cleanup_errors=tuple(errors),
            ) from errors[0]


class MinecraftBranchRuntimeFactory(MinecraftBranchRuntimeFactoryPort):
    """Environment-owned branch binder over explicit resource/service seams."""

    def __init__(
        self,
        *,
        endpoint_allocations: EndpointAllocationPort,
        environment_factory: MinecraftBranchEnvironmentFactoryPort,
        server_factory: MinecraftBranchServerFactoryPort,
    ) -> None:
        self._endpoint_allocations = endpoint_allocations
        self._environment_factory = environment_factory
        self._server_factory = server_factory

    def open(self, request: MinecraftBranchRuntimeRequest) -> MinecraftBranchRuntimeBinding:
        allocation = self._endpoint_allocations.allocate(request.endpoint_allocation)
        try:
            endpoint = allocation.endpoint
            environment_spec = replace(request.environment_template, endpoint=replace(
                request.environment_template.endpoint,
                host=endpoint.host,
                port=endpoint.port,
            ))
            server_spec = replace(
                request.server_template,
                host=endpoint.host,
                port=endpoint.port,
                workdir=request.branch.workdir,
                level_name=request.branch.level_name,
            )
            environment = self._environment_factory.compose(environment_spec)
            server = self._server_factory.create(
                server_spec,
                environment_generation=environment.implementation.identity.artifact_digest,
            )
            return MinecraftBranchRuntimeBinding(
                allocation=allocation,
                implementation=environment.implementation,
                environment_runtime=environment.runtime,
                server=server,
                session_id=request.session_id,
                endpoint_allocations=self._endpoint_allocations,
            )
        except BaseException:
            self._endpoint_allocations.release(allocation.allocation_id)
            raise


__all__ = [
    "MinecraftBranchEnvironmentFactoryPort",
    "MinecraftBranchRuntimeBinding",
    "MinecraftBranchRuntimeError",
    "MinecraftBranchRuntimeFactory",
]
