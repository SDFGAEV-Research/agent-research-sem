from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, TypeVar, Generic, runtime_checkable

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RegistrationKey:
    namespace: str
    name: str

    def __post_init__(self) -> None:
        if not self.namespace.strip() or not self.name.strip():
            raise ValueError("registration key fields must be non-empty")


class ScopeDisposed(RuntimeError):
    pass


class RegistrationConflict(RuntimeError):
    pass


@runtime_checkable
class RegistrationHandlePort(Protocol):
    @property
    def key(self) -> RegistrationKey: ...
    def close(self, *, timeout_s: float | None = None) -> None: ...


@runtime_checkable
class RegistrationLeasePort(Protocol, Generic[T]):
    @property
    def value(self) -> T: ...
    def close(self) -> None: ...


@runtime_checkable
class RegistrationScopePort(Protocol):
    @property
    def scope_id(self) -> str: ...
    def child(self, scope_id: str) -> "RegistrationScopePort": ...
    def register(self, key: RegistrationKey, value: object) -> RegistrationHandlePort: ...
    def acquire(self, key: RegistrationKey) -> AbstractContextManager[object]: ...
    def dispose(self, *, timeout_s: float | None = None) -> None: ...


@runtime_checkable
class RegistrationScopeFactoryPort(Protocol):
    def create(self, scope_id: str) -> RegistrationScopePort: ...


__all__ = [
    "RegistrationConflict",
    "RegistrationHandlePort",
    "RegistrationKey",
    "RegistrationLeasePort",
    "RegistrationScopeFactoryPort",
    "RegistrationScopePort",
    "ScopeDisposed",
]
