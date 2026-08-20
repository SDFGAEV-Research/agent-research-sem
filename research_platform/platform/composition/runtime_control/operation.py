from __future__ import annotations

from research_platform.platform.kernel import (
    OperationAuxiliaryFailureSink,
    OperationExecutor,
    OperationFailureSink,
    OperationObserver,
)
from research_platform.observability.api import (
    EventSink,
    OperationAuxiliaryFailureEventSink,
    OperationLifecycleObserver,
)


def build_operation_executor(
    *,
    failure_sink: OperationFailureSink | None = None,
    event_sink: EventSink | None = None,
    observers: tuple[OperationObserver, ...] = (),
    auxiliary_failure_sink: OperationAuxiliaryFailureSink | None = None,
) -> OperationExecutor:
    """Compose a storage-neutral operation boundary from explicit ports.

    Event persistence and failure persistence are independently replaceable.  When an
    event sink is supplied, standard lifecycle and auxiliary-failure projections are
    installed automatically; callers may add unrelated observers without coupling them
    to the storage backend.
    """

    lifecycle_observers: tuple[OperationObserver, ...] = (
        (OperationLifecycleObserver(event_sink),) if event_sink is not None else ()
    )
    auxiliary = auxiliary_failure_sink
    if auxiliary is None and event_sink is not None:
        auxiliary = OperationAuxiliaryFailureEventSink(event_sink)
    return OperationExecutor(
        failure_sink,
        observers=lifecycle_observers + tuple(observers),
        auxiliary_failure_sink=auxiliary,
    )


__all__ = ["build_operation_executor"]
