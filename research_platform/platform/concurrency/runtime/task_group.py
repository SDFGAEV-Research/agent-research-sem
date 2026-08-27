from __future__ import annotations

from concurrent.futures import CancelledError
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from threading import Condition, Event, Lock, RLock
import time
from typing import Any, Callable, Generic, Iterator, TypeVar

from research_platform.platform.concurrency.api import (
    SerialMailboxPolicy,
    SerialMailboxRejected,
    Deadline,
    ExecutionLaneKind,
    ExecutionPermitRejected,
    ExecutionSpec,
    ScheduledTaskSpec,
    TaskCancelled,
    TaskDeadlineExceeded,
    TaskFailurePolicy,
    TaskFailureScope,
    TaskGroupTopologySnapshot,
    TaskState,
    SerialActorPort,
    TaskTopologySnapshot,
)
from research_platform.platform.concurrency.api.ports import (
    CancellationTokenPort,
    ExecutionAuthorityProviderPort,
    ScheduledTaskHandlePort,
    SerialExecutionLaneProviderPort,
    TaskContextPort,
    TaskHandlePort,
    TimerSchedulerProviderPort,
)
from .actor import SerialActor

T = TypeVar("T")
_TERMINAL_STATES = frozenset({TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED})


class _DeadlineOwner(Enum):
    NONE = "none"
    GROUP = "group"
    TASK = "task"



class _CancellationState(CancellationTokenPort):
    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._reason: str | None = None
        self._cancelled_monotonic: float | None = None

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        with self._lock:
            return self._reason

    @property
    def cancelled_monotonic(self) -> float | None:
        with self._lock:
            return self._cancelled_monotonic

    def cancel(self, reason: str) -> bool:
        reason = str(reason).strip()
        if not reason:
            raise ValueError("cancellation reason required")
        now = time.monotonic()
        with self._lock:
            if self._event.is_set():
                return False
            self._reason = reason
            self._cancelled_monotonic = now
            self._event.set()
            return True

    def wait(self, timeout: float | None = None) -> bool:
        if timeout is not None and timeout < 0:
            raise ValueError("cancellation wait timeout cannot be negative")
        return self._event.wait(timeout)

    def checkpoint(self) -> None:
        if self._event.is_set():
            raise TaskCancelled(self.reason or "task group cancelled")


@dataclass(frozen=True, slots=True)
class _AnyCancellation(CancellationTokenPort):
    """Cancellation view used only while a provider is admitting a task."""

    first: _CancellationState
    second: _CancellationState

    @property
    def cancelled(self) -> bool:
        return self.first.cancelled or self.second.cancelled

    @property
    def reason(self) -> str | None:
        return self.first.reason or self.second.reason

    def wait(self, timeout: float | None = None) -> bool:
        if timeout is not None and timeout < 0:
            raise ValueError("cancellation wait timeout cannot be negative")
        end = None if timeout is None else time.monotonic() + timeout
        while not self.cancelled:
            if end is not None:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    return False
                self.first.wait(min(0.05, remaining))
            else:
                self.first.wait(0.05)
        return True

    def checkpoint(self) -> None:
        if self.cancelled:
            raise TaskCancelled(self.reason or "task submission cancelled")


@dataclass(frozen=True, slots=True)
class _TaskContext(TaskContextPort):
    _group_id: str
    _task_id: str
    _lane_kind: ExecutionLaneKind
    _group_cancellation: _CancellationState
    _task_cancellation: _CancellationState
    _deadline: Deadline | None
    _deadline_owner: _DeadlineOwner
    _cancel_group: Callable[[str], None]

    @property
    def group_id(self) -> str:
        return self._group_id

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def lane_kind(self) -> ExecutionLaneKind:
        return self._lane_kind

    @property
    def deadline(self) -> Deadline | None:
        return self._deadline

    @property
    def cancelled(self) -> bool:
        return self._task_cancellation.cancelled or self._group_cancellation.cancelled

    @property
    def reason(self) -> str | None:
        return self._task_cancellation.reason or self._group_cancellation.reason

    @property
    def remaining_seconds(self) -> float | None:
        return None if self._deadline is None else self._deadline.remaining_seconds

    def wait(self, timeout: float | None = None) -> bool:
        if timeout is not None and timeout < 0:
            raise ValueError("task wait timeout cannot be negative")
        if self.cancelled:
            return True
        if self._deadline is not None:
            remaining = self._deadline.remaining_seconds
            timeout = remaining if timeout is None else min(timeout, remaining)
        # group.cancel() explicitly cancels every owned task record, so waiting on
        # the task event also wakes for group cancellation without polling.
        return self._task_cancellation.wait(timeout)

    def checkpoint(self) -> None:
        self._group_cancellation.checkpoint()
        self._task_cancellation.checkpoint()
        if self._deadline is not None and self._deadline.expired:
            if self._deadline_owner is _DeadlineOwner.GROUP:
                reason = f"task group deadline exceeded: {self._group_id}"
                self._cancel_group(reason)
                self._group_cancellation.checkpoint()
            raise TaskDeadlineExceeded(
                f"task deadline exceeded: {self._group_id}/{self._task_id}"
            )


@dataclass(slots=True)
class _TaskRecord:
    task_id: str
    lane_kind: ExecutionLaneKind
    lane_id: str | None
    deadline: Deadline | None
    deadline_owner: _DeadlineOwner
    failure_scope: TaskFailureScope
    cancellation: _CancellationState = field(default_factory=_CancellationState)
    state: TaskState = TaskState.PENDING
    failure: BaseException | None = None
    raw_handle: Any | None = None
    deadline_handle: ScheduledTaskHandlePort | None = None


class _OwnedTaskHandle(Generic[T], TaskHandlePort[T]):
    def __init__(self, group: "StructuredTaskGroup", record: _TaskRecord) -> None:
        self._group = group
        self._record = record

    @property
    def task_id(self) -> str:
        return self._record.task_id

    @property
    def lane_kind(self) -> ExecutionLaneKind:
        return self._record.lane_kind

    @property
    def state(self) -> TaskState:
        return self._group._task_state(self._record.task_id)

    def done(self) -> bool:
        # Logical outcome and physical execution are intentionally distinct.  A
        # non-preemptive CPU child can be deadline-failed while its worker is still
        # running; callers that need structured convergence must use wait/close.
        raw = self._record.raw_handle
        return self.state in _TERMINAL_STATES if raw is None else bool(raw.done())

    def cancel(self) -> bool:
        return self._group._cancel_task(self._record.task_id)

    def result(self, timeout: float | None = None) -> T:
        raw = self._record.raw_handle
        if raw is None:
            failure = self._group._task_failure(self._record.task_id)
            if failure is not None:
                raise failure
            raise RuntimeError(f"task was not submitted: {self._record.task_id}")

        # A deadline is a logical outcome even when a CPU child cannot be
        # preempted.  Surface that outcome immediately; scope close still joins the
        # underlying worker before claiming clean structured convergence.
        failure = self._group._task_failure(self._record.task_id)
        if isinstance(failure, TaskDeadlineExceeded):
            if self._record.deadline_owner is _DeadlineOwner.GROUP:
                reason = f"task group deadline exceeded: {self._group.group_id}"
                self._group.cancel(reason)
                raise TaskCancelled(self._group.cancellation.reason or reason) from failure
            raise failure

        resolved_timeout = self._group._bounded_wait_timeout(self._record.deadline, timeout)
        try:
            value = raw.result(timeout=resolved_timeout)
        except CancelledError as exc:
            self._group._sync_terminal_from_raw(self._record.task_id)
            failure = self._group._task_failure(self._record.task_id)
            if isinstance(failure, TaskDeadlineExceeded):
                raise failure from exc
            raise TaskCancelled(
                self._record.cancellation.reason
                or self._group.cancellation.reason
                or f"task cancelled: {self._record.task_id}"
            ) from exc
        except TimeoutError as exc:
            if self._record.deadline is not None and self._record.deadline.expired:
                if self._record.deadline_owner is _DeadlineOwner.GROUP:
                    self._group.cancel(f"task group deadline exceeded: {self._group.group_id}")
                    raise TaskCancelled(
                        self._group.cancellation.reason or "task group deadline exceeded"
                    ) from exc
                failure = self._group._expire_task(self._record.task_id)
                raise failure from exc
            raise
        except BaseException as exc:
            self._group._sync_terminal_from_raw(self._record.task_id)
            failure = self._group._task_failure(self._record.task_id)
            if failure is not None and failure is not exc:
                raise failure from exc
            raise

        self._group._sync_terminal_from_raw(self._record.task_id)
        state = self._group._task_state(self._record.task_id)
        failure = self._group._task_failure(self._record.task_id)
        if state is TaskState.FAILED and failure is not None:
            raise failure
        if state is TaskState.CANCELLED:
            raise TaskCancelled(
                self._record.cancellation.reason
                or self._group.cancellation.reason
                or f"task cancelled: {self._record.task_id}"
            )
        return value


@dataclass(slots=True)
class _RecurringRecord:
    task_id: str
    lane_id: str
    deadline: Deadline | None
    deadline_owner: _DeadlineOwner
    cancellation: _CancellationState = field(default_factory=_CancellationState)
    state: TaskState = TaskState.PENDING
    failure: BaseException | None = None
    current: Any | None = None
    cancelled: bool = False
    deadline_handle: ScheduledTaskHandlePort | None = None


class _OwnedScheduledHandle(ScheduledTaskHandlePort):
    def __init__(
        self,
        group: "StructuredTaskGroup",
        record: _RecurringRecord,
        timer_handle: ScheduledTaskHandlePort,
    ) -> None:
        self._group = group
        self._record = record
        self._timer_handle = timer_handle

    @property
    def task_id(self) -> str:
        return self._record.task_id

    def cancel(self) -> None:
        self._group._cancel_recurring(self._record.task_id)
        self._timer_handle.cancel()

    def assert_healthy(self) -> None:
        self._timer_handle.assert_healthy()
        failure = self._group._recurring_failure(self._record.task_id)
        if failure is not None:
            raise RuntimeError(
                f"scheduled task failed: {self._group.group_id}/{self._record.task_id}: "
                f"{type(failure).__name__}: {failure}"
            ) from failure


class StructuredTaskGroup:
    """Owned task scope with explicit submission, cancellation and deadline authority.

    Blocking-I/O and serial tasks receive ``TaskContextPort`` as their first
    argument. CPU tasks are process-isolated pure functions and deliberately do
    not receive a context: running process work is non-preemptive.  Logical task
    outcome can therefore become FAILED/CANCELLED before physical execution ends;
    ``TaskTopologySnapshot.execution_done`` and ``wait/close`` make that distinction
    explicit rather than pretending a timed-out process disappeared.
    """

    def __init__(
        self,
        *,
        group_id: str,
        execution: ExecutionAuthorityProviderPort,
        timers: TimerSchedulerProviderPort,
        default_queue_capacity: int,
        deadline: Deadline | None = None,
        failure_policy: TaskFailurePolicy = TaskFailurePolicy.FAIL_FAST,
        shutdown_timeout_seconds: float = 30.0,
        on_close: Callable[[str, Deadline], None] | None = None,
    ) -> None:
        group_id = str(group_id).strip()
        if not group_id:
            raise ValueError("task group id required")
        if shutdown_timeout_seconds <= 0:
            raise ValueError("task group shutdown timeout must be positive")
        self._group_id = group_id
        self._execution = execution
        self._timers = timers
        self._default_queue_capacity = int(default_queue_capacity)
        self._deadline = deadline
        self._failure_policy = failure_policy
        self._shutdown_timeout_seconds = float(shutdown_timeout_seconds)
        self._on_close = on_close
        self._cancellation = _CancellationState()
        self._submission_cancellation = _CancellationState()
        self._provider_submission_cancellation = _AnyCancellation(
            self._cancellation,
            self._submission_cancellation,
        )
        self._lock = RLock()
        self._condition = Condition(self._lock)
        self._tasks: dict[str, _TaskRecord] = {}
        self._recurring: dict[str, _RecurringRecord] = {}
        self._scheduled_handles: dict[str, _OwnedScheduledHandle] = {}
        self._active_submissions = 0
        self._closing = False
        self._closed = False
        self._converged = False
        self._close_complete = Event()
        self._close_failure: BaseException | None = None
        self._group_deadline_handle: ScheduledTaskHandlePort | None = None
        if deadline is not None:
            if deadline.expired:
                raise TaskDeadlineExceeded(f"task group deadline already expired: {group_id}")
            self._group_deadline_handle = self._timers.schedule_once(
                f"task-group-deadline:{group_id}",
                deadline.remaining_seconds,
                lambda: self.cancel(f"task group deadline exceeded: {group_id}"),
            )

    @property
    def group_id(self) -> str:
        return self._group_id

    @property
    def cancellation(self) -> CancellationTokenPort:
        return self._cancellation

    def open_serial_actor(
        self,
        actor_id: str,
        *,
        lane_id: str | None = None,
        capacity: int | None = None,
    ) -> SerialActorPort:
        resolved_actor_id = str(actor_id).strip()
        if not resolved_actor_id:
            raise ValueError("serial actor id required")
        resolved_lane_id = resolved_actor_id if lane_id is None else str(lane_id).strip()
        # Resolve immediately so actor ownership/capacity conflicts are detected at
        # composition time rather than on the first mutation.
        self._execution.ensure_serial_lane(self._group_id, resolved_lane_id, capacity)
        return SerialActor(
            self,
            resolved_actor_id,
            lane_id=resolved_lane_id,
            capacity=capacity,
        )

    @contextmanager
    def _submission_scope(self) -> Iterator[None]:
        with self._condition:
            if self._closing or self._closed:
                raise RuntimeError(f"task group closed: {self._group_id}")
            if self._cancellation.cancelled:
                raise TaskCancelled(self._cancellation.reason or "task group cancelled")
            self._active_submissions += 1
        try:
            yield
        finally:
            with self._condition:
                self._active_submissions -= 1
                if self._active_submissions < 0:
                    raise RuntimeError("task group submission accounting underflow")
                self._condition.notify_all()

    def _effective_deadline(
        self, child: Deadline | None
    ) -> tuple[Deadline | None, _DeadlineOwner]:
        """Resolve exactly one deadline owner for a child.

        The group deadline is enforced once by the group timer. Children inheriting
        it never register their own timer. A stricter child deadline is task-owned
        and receives one independent timer. This prevents duplicate deadline
        authorities from racing to choose incompatible terminal causes.
        """

        if self._deadline is None:
            return (child, _DeadlineOwner.TASK) if child is not None else (None, _DeadlineOwner.NONE)
        if child is None or self._deadline.monotonic_deadline <= child.monotonic_deadline:
            return self._deadline, _DeadlineOwner.GROUP
        return child, _DeadlineOwner.TASK

    def _reserve_task(
        self,
        task_id: str,
        lane_kind: ExecutionLaneKind,
        lane_id: str | None,
        deadline: Deadline | None,
        failure_scope: TaskFailureScope,
    ) -> _TaskRecord:
        task_id = str(task_id).strip()
        if not task_id:
            raise ValueError("task id required")
        effective, deadline_owner = self._effective_deadline(deadline)
        with self._lock:
            if task_id in self._tasks or task_id in self._recurring:
                raise ValueError(f"task id already owned by group: {self._group_id}/{task_id}")
            record = _TaskRecord(task_id, lane_kind, lane_id, effective, deadline_owner, failure_scope)
            self._tasks[task_id] = record
        if effective is not None and effective.expired:
            if deadline_owner is _DeadlineOwner.GROUP:
                reason = f"task group deadline exceeded: {self._group_id}"
                self.cancel(reason)
                failure = TaskCancelled(self._cancellation.reason or reason)
                self._mark_cancelled(task_id, failure)
                raise failure
            failure = TaskDeadlineExceeded(
                f"task deadline already expired: {self._group_id}/{task_id}"
            )
            self._mark_failed(task_id, failure)
            raise failure
        return record

    def _submit_contextual(
        self,
        *,
        spec: ExecutionSpec,
        record: _TaskRecord,
        fn: Callable[..., T],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> TaskHandlePort[T]:
        context = _TaskContext(
            self._group_id,
            record.task_id,
            record.lane_kind,
            self._cancellation,
            record.cancellation,
            record.deadline,
            record.deadline_owner,
            self.cancel,
        )

        def invoke() -> T:
            self._mark_running(record.task_id)
            context.checkpoint()
            value = fn(context, *args, **kwargs)
            context.checkpoint()
            return value

        try:
            raw = self._execution.submit(
                self._group_id,
                spec,
                invoke,
                deadline=record.deadline,
                cancellation=self._provider_submission_cancellation,
            )
        except TaskCancelled as exc:
            self._mark_cancelled(record.task_id, exc)
            raise
        except ExecutionPermitRejected:
            self._mark_cancelled(
                record.task_id,
                TaskCancelled(f"execution permit rejected: {self._group_id}/{record.task_id}"),
            )
            raise
        except SerialMailboxRejected:
            self._mark_cancelled(
                record.task_id,
                TaskCancelled(f"execution permit rejected: {self._group_id}/{record.task_id}"),
            )
            raise
        except BaseException as exc:
            failure = self._normalize_submission_failure(record, exc)
            if isinstance(failure, TaskCancelled):
                self._mark_cancelled(record.task_id, failure)
            else:
                self._mark_failed(record.task_id, failure)
            if failure is exc:
                raise
            raise failure from exc
        with self._lock:
            record.raw_handle = raw
        if hasattr(raw, "add_done_callback"):
            raw.add_done_callback(lambda _handle: self._sync_terminal_from_raw(record.task_id))
        self._arm_task_deadline(record)
        if self._cancellation.cancelled or self._submission_cancellation.cancelled:
            self._cancel_task(
                record.task_id,
                reason=self._cancellation.reason or "task group closing",
            )
        return _OwnedTaskHandle(self, record)

    def submit(
        self,
        spec: ExecutionSpec,
        fn: Callable[..., T],
        /,
        *args: Any,
        deadline: Deadline | None = None,
        **kwargs: Any,
    ) -> TaskHandlePort[T]:
        """Submit through the single owner-aware execution port.

        Blocking-I/O and SERIAL callables receive ``TaskContextPort`` as their
        first argument. CPU callables remain pure process-callable functions and
        receive only the explicit arguments. The execution class is therefore a
        property of the request, not a different executor API.
        """

        if spec.lane_kind is ExecutionLaneKind.BLOCKING_IO:
            return self._submit_blocking(spec, fn, *args, deadline=deadline, **kwargs)
        if spec.lane_kind is ExecutionLaneKind.ASYNC_IO:
            return self._submit_async_io(spec, fn, *args, deadline=deadline, **kwargs)
        if spec.lane_kind is ExecutionLaneKind.CPU:
            return self._submit_cpu(spec, fn, *args, deadline=deadline, **kwargs)
        if spec.lane_kind is ExecutionLaneKind.SERIAL:
            return self._submit_serial(spec, fn, *args, deadline=deadline, **kwargs)
        raise ValueError(f"unsupported execution lane: {spec.lane_kind}")

    def _submit_blocking(
        self,
        spec: ExecutionSpec,
        fn: Callable[..., T],
        /,
        *args: Any,
        deadline: Deadline | None = None,
        **kwargs: Any,
    ) -> TaskHandlePort[T]:
        with self._submission_scope():
            record = self._reserve_task(spec.task_id, ExecutionLaneKind.BLOCKING_IO, None, deadline, spec.failure_scope)
            return self._submit_contextual(
                spec=spec,
                record=record,
                fn=fn,
                args=args,
                kwargs=kwargs,
            )

    def _submit_async_io(
        self,
        spec: ExecutionSpec,
        fn: Callable[..., T],
        /,
        *args: Any,
        deadline: Deadline | None = None,
        **kwargs: Any,
    ) -> TaskHandlePort[T]:
        with self._submission_scope():
            record = self._reserve_task(spec.task_id, ExecutionLaneKind.ASYNC_IO, None, deadline, spec.failure_scope)
            context = _TaskContext(
                self._group_id,
                record.task_id,
                record.lane_kind,
                self._cancellation,
                record.cancellation,
                record.deadline,
                record.deadline_owner,
                self.cancel,
            )

            async def invoke() -> T:
                context.checkpoint()
                value = fn(context, *args, **kwargs)
                import inspect
                if not inspect.isawaitable(value):
                    raise TypeError("ASYNC_IO task callable must return an awaitable")
                result = await value
                context.checkpoint()
                return result

            try:
                raw = self._execution.submit(
                    self._group_id,
                    spec,
                    invoke,
                    deadline=record.deadline,
                    cancellation=self._provider_submission_cancellation,
                )
            except TaskCancelled as exc:
                self._mark_cancelled(record.task_id, exc)
                raise
            except ExecutionPermitRejected:
                self._mark_cancelled(
                    record.task_id,
                    TaskCancelled(f"execution permit rejected: {self._group_id}/{record.task_id}"),
                )
                raise
            except BaseException as exc:
                failure = self._normalize_submission_failure(record, exc)
                if isinstance(failure, TaskCancelled):
                    self._mark_cancelled(record.task_id, failure)
                else:
                    self._mark_failed(record.task_id, failure)
                if failure is exc:
                    raise
                raise failure from exc
            with self._lock:
                record.raw_handle = raw
            if hasattr(raw, "add_done_callback"):
                raw.add_done_callback(lambda _handle: self._sync_terminal_from_raw(record.task_id))
            self._arm_task_deadline(record)
            if self._cancellation.cancelled or self._submission_cancellation.cancelled:
                self._cancel_task(
                    record.task_id,
                    reason=self._cancellation.reason or "task group closing",
                )
            return _OwnedTaskHandle(self, record)

    def _submit_serial(
        self,
        spec: ExecutionSpec,
        fn: Callable[..., T],
        /,
        *args: Any,
        deadline: Deadline | None = None,
        **kwargs: Any,
    ) -> TaskHandlePort[T]:
        with self._submission_scope():
            lane = self._execution.ensure_serial_lane(self._group_id, spec.lane_id or "", spec.capacity)
            record = self._reserve_task(spec.task_id, ExecutionLaneKind.SERIAL, lane.lane_id, deadline, spec.failure_scope)
            return self._submit_contextual(
                spec=spec,
                record=record,
                fn=fn,
                args=args,
                kwargs=kwargs,
            )

    def _submit_cpu(
        self,
        spec: ExecutionSpec,
        fn: Callable[..., T],
        /,
        *args: Any,
        deadline: Deadline | None = None,
        **kwargs: Any,
    ) -> TaskHandlePort[T]:
        with self._submission_scope():
            record = self._reserve_task(spec.task_id, ExecutionLaneKind.CPU, None, deadline, spec.failure_scope)
            try:
                raw = self._execution.submit(
                    self._group_id,
                    spec,
                    fn,
                    *args,
                    deadline=record.deadline,
                    cancellation=self._provider_submission_cancellation,
                    **kwargs,
                )
            except TaskCancelled as exc:
                self._mark_cancelled(record.task_id, exc)
                raise
            except ExecutionPermitRejected:
                self._mark_cancelled(
                    record.task_id,
                    TaskCancelled(f"execution permit rejected: {self._group_id}/{record.task_id}"),
                )
                raise
            except BaseException as exc:
                failure = self._normalize_submission_failure(record, exc)
                if isinstance(failure, TaskCancelled):
                    self._mark_cancelled(record.task_id, failure)
                else:
                    self._mark_failed(record.task_id, failure)
                if failure is exc:
                    raise
                raise failure from exc
            with self._lock:
                record.raw_handle = raw
                if record.state is TaskState.PENDING:
                    # CPU work is considered in-flight after process-pool submission;
                    # physical completion is separately observable.
                    record.state = TaskState.RUNNING
            if hasattr(raw, "add_done_callback"):
                raw.add_done_callback(lambda _handle: self._sync_terminal_from_raw(record.task_id))
            self._arm_task_deadline(record)
            if self._cancellation.cancelled or self._submission_cancellation.cancelled:
                self._cancel_task(
                    record.task_id,
                    reason=self._cancellation.reason or "task group closing",
                )
            return _OwnedTaskHandle(self, record)

    def _schedule_serial_fixed_delay(
        self,
        lane_id: str,
        spec: ScheduledTaskSpec,
        fn: Callable[..., Any],
        /,
        *args: Any,
        deadline: Deadline | None = None,
        capacity: int | None = None,
        **kwargs: Any,
    ) -> ScheduledTaskHandlePort:
        with self._submission_scope():
            lane = self._execution.ensure_serial_lane(self._group_id, lane_id, capacity)
            effective, deadline_owner = self._effective_deadline(deadline)
            with self._lock:
                if spec.task_id in self._tasks or spec.task_id in self._recurring:
                    raise ValueError(f"task id already owned by group: {self._group_id}/{spec.task_id}")
                record = _RecurringRecord(spec.task_id, lane.lane_id, effective, deadline_owner)
                self._recurring[spec.task_id] = record

            if effective is not None and effective.expired:
                if deadline_owner is _DeadlineOwner.GROUP:
                    reason = f"task group deadline exceeded: {self._group_id}"
                    self.cancel(reason)
                    # Registration has reserved identity but has not installed its
                    # scheduled handle yet, so group.cancel() cannot discover it.
                    # Publish the recurring child as a normal cancelled terminal.
                    self._cancel_recurring(record.task_id)
                    raise TaskCancelled(self._cancellation.reason or reason)
                self._expire_recurring(record.task_id)
                raise TaskDeadlineExceeded(
                    f"scheduled task deadline already expired: {self._group_id}/{record.task_id}"
                )

            def tick() -> None:
                with self._lock:
                    if self._closing or self._closed or record.cancelled or self._cancellation.cancelled:
                        return
                    if record.current is not None and not record.current.done():
                        return
                    if record.failure is not None:
                        return
                    expired = record.deadline is not None and record.deadline.expired
                if expired:
                    if record.deadline_owner is _DeadlineOwner.GROUP:
                        self.cancel(f"task group deadline exceeded: {self._group_id}")
                    else:
                        self._expire_recurring(record.task_id)
                    return
                context = _TaskContext(
                    self._group_id,
                    record.task_id,
                    ExecutionLaneKind.SERIAL,
                    self._cancellation,
                    record.cancellation,
                    record.deadline,
                    record.deadline_owner,
                    self.cancel,
                )

                def invoke() -> Any:
                    context.checkpoint()
                    value = fn(context, *args, **kwargs)
                    context.checkpoint()
                    return value

                try:
                    current = self._execution.submit(
                        self._group_id,
                        ExecutionSpec(
                            task_id=f"heartbeat-tick:{record.task_id}",
                            lane_kind=ExecutionLaneKind.SERIAL,
                            lane_id=record.lane_id,
                            capacity=capacity,
                            mailbox_policy=SerialMailboxPolicy.REJECT,
                        ),
                        invoke,
                        deadline=record.deadline,
                        cancellation=context,
                    )
                except SerialMailboxRejected:
                    # Recurring work uses REJECT as its non-blocking coalescing
                    # policy. Pressure is not a heartbeat failure and must never
                    # stall the shared timer authority.
                    return
                except TaskCancelled:
                    with self._lock:
                        if record.state is not TaskState.FAILED:
                            record.state = TaskState.CANCELLED
                    return
                except BaseException as exc:
                    with self._lock:
                        if record.state not in {TaskState.FAILED, TaskState.CANCELLED}:
                            record.failure = exc
                            record.state = TaskState.FAILED
                            first_failure = True
                        else:
                            first_failure = False
                    if first_failure and self._failure_policy is TaskFailurePolicy.FAIL_FAST:
                        self.cancel(f"scheduled task submission failed: {record.task_id}")
                    return

                def on_done(_handle: Any) -> None:
                    try:
                        _handle.result(timeout=0)
                    except TaskCancelled:
                        with self._lock:
                            if record.state is not TaskState.FAILED:
                                record.state = TaskState.CANCELLED
                    except BaseException as exc:
                        with self._lock:
                            if record.state not in {TaskState.FAILED, TaskState.CANCELLED}:
                                record.failure = exc
                                record.state = TaskState.FAILED
                                first_failure = True
                            else:
                                first_failure = False
                        if first_failure and self._failure_policy is TaskFailurePolicy.FAIL_FAST:
                            self.cancel(f"scheduled task failed: {record.task_id}")

                if hasattr(current, "add_done_callback"):
                    current.add_done_callback(on_done)
                with self._lock:
                    record.current = current

            try:
                provider_spec = ScheduledTaskSpec(
                    task_id=f"{self._group_id}/{spec.task_id}",
                    interval_seconds=spec.interval_seconds,
                    initial_delay_seconds=spec.initial_delay_seconds,
                )
                timer_handle = self._timers.schedule_fixed_delay(provider_spec, tick)
            except BaseException as exc:
                with self._lock:
                    record.failure = exc
                    record.state = TaskState.FAILED
                if self._failure_policy is TaskFailurePolicy.FAIL_FAST:
                    self.cancel(f"scheduled task registration failed: {record.task_id}")
                raise
            owned = _OwnedScheduledHandle(self, record, timer_handle)
            with self._lock:
                self._scheduled_handles[spec.task_id] = owned
                record.state = TaskState.RUNNING
                cancel_immediately = self._cancellation.cancelled or self._submission_cancellation.cancelled
            self._arm_recurring_deadline(record)
            if cancel_immediately:
                owned.cancel()
            return owned

    def _normalize_submission_failure(self, record: _TaskRecord, failure: BaseException) -> BaseException:
        if isinstance(failure, TimeoutError) and record.deadline is not None and record.deadline.expired:
            if record.deadline_owner is _DeadlineOwner.GROUP:
                self.cancel(f"task group deadline exceeded: {self._group_id}")
                return TaskCancelled(self._cancellation.reason or "task group deadline exceeded")
            return TaskDeadlineExceeded(f"task deadline exceeded during submission: {record.task_id}")
        return failure

    @staticmethod
    def _raw_completed_monotonic(raw: Any | None) -> float | None:
        if raw is None:
            return None
        value = getattr(raw, "completed_monotonic", None)
        return None if value is None else float(value)

    def _arm_task_deadline(self, record: _TaskRecord) -> None:
        if record.deadline is None or record.deadline_owner is not _DeadlineOwner.TASK:
            return
        self._sync_terminal_from_raw(record.task_id)
        with self._lock:
            if record.state in _TERMINAL_STATES:
                return
        remaining = record.deadline.remaining_seconds
        if remaining <= 0:
            self._expire_task(record.task_id)
            return
        try:
            handle = self._timers.schedule_once(
                f"task-deadline:{self._group_id}/{record.task_id}",
                remaining,
                lambda: self._expire_task(record.task_id),
            )
        except BaseException as exc:
            self._mark_failed(record.task_id, exc)
            raise
        with self._lock:
            if record.state in _TERMINAL_STATES:
                cancel_immediately = True
            else:
                record.deadline_handle = handle
                cancel_immediately = False
        if cancel_immediately:
            handle.cancel()

    def _arm_recurring_deadline(self, record: _RecurringRecord) -> None:
        if record.deadline is None or record.deadline_owner is not _DeadlineOwner.TASK:
            return
        remaining = record.deadline.remaining_seconds
        if remaining <= 0:
            self._expire_recurring(record.task_id)
            return
        try:
            handle = self._timers.schedule_once(
                f"scheduled-task-deadline:{self._group_id}/{record.task_id}",
                remaining,
                lambda: self._expire_recurring(record.task_id),
            )
        except BaseException as exc:
            with self._lock:
                record.failure = exc
                record.state = TaskState.FAILED
            if self._failure_policy is TaskFailurePolicy.FAIL_FAST:
                self.cancel(f"scheduled task deadline registration failed: {record.task_id}")
            raise
        with self._lock:
            if record.state in {TaskState.FAILED, TaskState.CANCELLED}:
                cancel_immediately = True
            else:
                record.deadline_handle = handle
                cancel_immediately = False
        if cancel_immediately:
            handle.cancel()

    @staticmethod
    def _cancel_deadline_handle(handle: ScheduledTaskHandlePort | None) -> None:
        if handle is not None:
            handle.cancel()

    def _retire_group_deadline(self) -> None:
        """Disarm the one group-owned deadline after structural convergence.

        A close request seals submissions, but it does not end the scope's deadline
        authority while accepted children are still executing. Keeping the timer
        armed lets the group deadline cancel cooperative children during close.
        """

        with self._lock:
            handle = self._group_deadline_handle
            self._group_deadline_handle = None
        self._cancel_deadline_handle(handle)

    def _mark_running(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks[task_id]
            if record.state is TaskState.PENDING:
                record.state = TaskState.RUNNING

    def _mark_succeeded(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks[task_id]
            if record.state in _TERMINAL_STATES:
                return
            record.state = TaskState.SUCCEEDED
            deadline_handle = record.deadline_handle
            record.deadline_handle = None
        self._cancel_deadline_handle(deadline_handle)

    def _mark_cancelled(self, task_id: str, failure: BaseException | None = None) -> None:
        with self._lock:
            record = self._tasks[task_id]
            if record.state in _TERMINAL_STATES:
                return
            record.state = TaskState.CANCELLED
            if failure is not None and record.failure is None:
                record.failure = failure
            deadline_handle = record.deadline_handle
            record.deadline_handle = None
        self._cancel_deadline_handle(deadline_handle)

    def _mark_failed(self, task_id: str, failure: BaseException) -> None:
        should_cancel = False
        with self._lock:
            record = self._tasks[task_id]
            if record.state in _TERMINAL_STATES:
                return
            record.state = TaskState.FAILED
            record.failure = failure
            deadline_handle = record.deadline_handle
            record.deadline_handle = None
            should_cancel = (
                record.failure_scope is TaskFailureScope.GROUP
                and self._failure_policy is TaskFailurePolicy.FAIL_FAST
            )
        self._cancel_deadline_handle(deadline_handle)
        if should_cancel:
            self.cancel(f"task failed: {task_id}")

    def _expire_task(self, task_id: str) -> TaskDeadlineExceeded:
        failure = TaskDeadlineExceeded(f"task deadline exceeded: {self._group_id}/{task_id}")
        with self._lock:
            record = self._tasks[task_id]
            raw = record.raw_handle
            completed = self._raw_completed_monotonic(raw)
            if record.state in _TERMINAL_STATES:
                return record.failure if isinstance(record.failure, TaskDeadlineExceeded) else failure
            # Timer callbacks can run late. Completion at or before the deadline is
            # authoritative and must never be reclassified as a timeout.
            if (
                completed is not None
                and record.deadline is not None
                and completed <= record.deadline.monotonic_deadline
            ):
                should_sync = True
            else:
                should_sync = False
                record.failure = failure
                record.state = TaskState.FAILED
                record.deadline_handle = None
                lane_kind = record.lane_kind
                should_cancel_group = (
                    record.failure_scope is TaskFailureScope.GROUP
                    and self._failure_policy is TaskFailurePolicy.FAIL_FAST
                )
        if should_sync:
            self._sync_terminal_from_raw(task_id)
            return failure
        if lane_kind is not ExecutionLaneKind.CPU:
            record.cancellation.cancel(f"task deadline exceeded: {task_id}")
        if raw is not None:
            raw.cancel()
        if should_cancel_group:
            self.cancel(f"task deadline exceeded: {task_id}")
        return failure

    def _expire_recurring(self, task_id: str) -> None:
        failure = TaskDeadlineExceeded(
            f"scheduled task deadline exceeded: {self._group_id}/{task_id}"
        )
        with self._lock:
            record = self._recurring.get(task_id)
            if record is None or record.state in {TaskState.FAILED, TaskState.CANCELLED}:
                return
            record.failure = failure
            record.state = TaskState.FAILED
            record.deadline_handle = None
            current = record.current
            scheduled = self._scheduled_handles.get(task_id)
            should_cancel_group = self._failure_policy is TaskFailurePolicy.FAIL_FAST
        record.cancellation.cancel(f"scheduled task deadline exceeded: {task_id}")
        if current is not None:
            current.cancel()
        if scheduled is not None:
            scheduled._timer_handle.cancel()
        if should_cancel_group:
            self.cancel(f"scheduled task deadline exceeded: {task_id}")

    def _sync_terminal_from_raw(self, task_id: str) -> None:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None or record.raw_handle is None:
                return
            raw = record.raw_handle
            if not raw.done():
                if record.state is TaskState.PENDING and hasattr(raw, "running") and raw.running():
                    record.state = TaskState.RUNNING
                return
            completed = self._raw_completed_monotonic(raw) or time.monotonic()
            deadline = record.deadline
            deadline_missed = (
                deadline is not None
                and record.deadline_owner is _DeadlineOwner.TASK
                and completed > deadline.monotonic_deadline
            )
            already_terminal = record.state in _TERMINAL_STATES
            predetermined_failure = record.failure
        if already_terminal:
            return
        if deadline_missed:
            self._mark_failed(
                task_id,
                predetermined_failure
                if isinstance(predetermined_failure, TaskDeadlineExceeded)
                else TaskDeadlineExceeded(f"task deadline exceeded: {self._group_id}/{task_id}"),
            )
            return
        try:
            raw.result(timeout=0)
        except CancelledError as exc:
            if isinstance(predetermined_failure, TaskDeadlineExceeded):
                self._mark_failed(task_id, predetermined_failure)
            else:
                self._mark_cancelled(task_id, exc)
        except TaskCancelled as exc:
            self._mark_cancelled(task_id, exc)
        except TaskDeadlineExceeded as exc:
            if record.deadline_owner is _DeadlineOwner.GROUP:
                reason = f"task group deadline exceeded: {self._group_id}"
                self.cancel(reason)
                self._mark_cancelled(task_id, TaskCancelled(self._cancellation.reason or reason))
            else:
                self._mark_failed(task_id, exc)
        except BaseException as exc:
            self._mark_failed(task_id, exc)
        else:
            if predetermined_failure is not None:
                self._mark_failed(task_id, predetermined_failure)
                return
            cancellation_times = tuple(
                value
                for value in (
                    record.cancellation.cancelled_monotonic,
                    self._cancellation.cancelled_monotonic,
                )
                if value is not None
            )
            if cancellation_times and min(cancellation_times) <= completed:
                self._mark_cancelled(task_id)
            else:
                self._mark_succeeded(task_id)

    def _task_state(self, task_id: str) -> TaskState:
        self._sync_terminal_from_raw(task_id)
        with self._lock:
            return self._tasks[task_id].state

    def _task_failure(self, task_id: str) -> BaseException | None:
        self._sync_terminal_from_raw(task_id)
        with self._lock:
            return self._tasks[task_id].failure

    def _cancel_task(self, task_id: str, *, reason: str = "task cancelled") -> bool:
        with self._lock:
            record = self._tasks[task_id]
            raw = record.raw_handle
            terminal = record.state in _TERMINAL_STATES
        if terminal:
            return False
        cooperative = record.cancellation.cancel(reason)
        raw_cancelled = False if raw is None else bool(raw.cancel())
        self._mark_cancelled(task_id)
        return cooperative or raw_cancelled

    @staticmethod
    def _bounded_wait_timeout(deadline: Deadline | None, timeout: float | None) -> float | None:
        if timeout is not None and timeout < 0:
            raise ValueError("wait timeout cannot be negative")
        if deadline is None:
            return timeout
        remaining = deadline.remaining_seconds
        if timeout is None:
            return remaining
        return min(timeout, remaining)

    def _cancel_recurring(self, task_id: str) -> None:
        with self._lock:
            record = self._recurring.get(task_id)
            if record is None:
                return
            record.cancelled = True
            record.cancellation.cancel(f"scheduled task cancelled: {task_id}")
            if record.state is not TaskState.FAILED:
                record.state = TaskState.CANCELLED
            current = record.current
            deadline_handle = record.deadline_handle
            record.deadline_handle = None
        self._cancel_deadline_handle(deadline_handle)
        if current is not None:
            current.cancel()

    def _recurring_failure(self, task_id: str) -> BaseException | None:
        with self._lock:
            record = self._recurring.get(task_id)
            return None if record is None else record.failure

    def cancel(self, reason: str) -> None:
        self._cancellation.cancel(reason)
        with self._lock:
            task_ids = tuple(self._tasks)
            scheduled = tuple(self._scheduled_handles.values())
            group_deadline_handle = self._group_deadline_handle
            self._group_deadline_handle = None
        self._cancel_deadline_handle(group_deadline_handle)
        for handle in scheduled:
            handle.cancel()
        for task_id in task_ids:
            self._cancel_task(task_id, reason=reason)

    def wait(self, *, timeout: float | None = None) -> None:
        """Join every physically submitted child before surfacing logical failures."""

        if timeout is not None and timeout < 0:
            raise ValueError("wait timeout cannot be negative")
        end = None if timeout is None else time.monotonic() + timeout
        with self._lock:
            records = tuple(self._tasks.values())
            recurring = tuple(self._recurring.values())
            scheduled = tuple(self._scheduled_handles.values())
        errors: list[BaseException] = []
        for scheduled_handle in scheduled:
            try:
                scheduled_handle.assert_healthy()
            except BaseException as exc:
                errors.append(exc)
        for record in records:
            raw = record.raw_handle
            if raw is None:
                if (
                    record.failure is not None
                    and record.state is TaskState.FAILED
                    and record.failure_scope is TaskFailureScope.GROUP
                ):
                    errors.append(record.failure)
                continue
            remaining = None if end is None else max(0.0, end - time.monotonic())
            observed_failure: BaseException | None = None
            try:
                raw.result(timeout=remaining)
            except TimeoutError as exc:
                errors.append(exc)
                continue
            except BaseException as exc:
                # The owned record is the authority for whether this failure
                # belongs to the group or to the caller.  Keep the raw defect
                # until that ownership decision is observed; never discard it.
                observed_failure = exc
            self._sync_terminal_from_raw(record.task_id)
            with self._lock:
                state = record.state
                failure = record.failure
            if state is TaskState.FAILED and record.failure_scope is TaskFailureScope.GROUP:
                if failure is not None:
                    errors.append(failure)
                elif observed_failure is not None:
                    errors.append(observed_failure)
                else:
                    errors.append(RuntimeError(f"failed task has no failure evidence: {record.task_id}"))
        for record in recurring:
            current = record.current
            if current is not None and not current.done():
                remaining = None if end is None else max(0.0, end - time.monotonic())
                observed_failure: BaseException | None = None
                try:
                    current.result(timeout=remaining)
                except TimeoutError as exc:
                    errors.append(exc)
                except BaseException as exc:
                    observed_failure = exc
            else:
                observed_failure = None
            if record.state is TaskState.FAILED:
                if record.failure is not None:
                    errors.append(record.failure)
                elif observed_failure is not None:
                    errors.append(observed_failure)
                else:
                    errors.append(RuntimeError(f"failed recurring task has no failure evidence: {record.task_id}"))
        if errors:
            raise ExceptionGroup(f"task group failed: {self._group_id}", errors)

    def assert_healthy(self) -> None:
        with self._lock:
            task_ids = tuple(self._tasks)
        for task_id in task_ids:
            self._sync_terminal_from_raw(task_id)
        with self._lock:
            failures = [
                record.failure
                for record in (*self._tasks.values(), *self._recurring.values())
                if (
                    record.failure is not None
                    and record.state is TaskState.FAILED
                    and getattr(record, "failure_scope", TaskFailureScope.GROUP) is TaskFailureScope.GROUP
                )
            ]
        if failures:
            raise ExceptionGroup(f"task group unhealthy: {self._group_id}", failures)

    @staticmethod
    def _execution_done(record: _TaskRecord) -> bool:
        raw = record.raw_handle
        if raw is None:
            return record.state in _TERMINAL_STATES
        return bool(raw.done())

    def snapshot(self) -> TaskGroupTopologySnapshot:
        with self._lock:
            records = tuple(self._tasks.values())
        for record in records:
            self._sync_terminal_from_raw(record.task_id)
        with self._lock:
            tasks = [
                TaskTopologySnapshot(
                    group_id=self._group_id,
                    task_id=record.task_id,
                    lane_kind=record.lane_kind,
                    lane_id=record.lane_id,
                    state=record.state,
                    execution_done=self._execution_done(record),
                    deadline_monotonic=None if record.deadline is None else record.deadline.monotonic_deadline,
                    failure_type=None if record.failure is None else type(record.failure).__name__,
                    failure_scope=record.failure_scope,
                )
                for record in self._tasks.values()
            ]
            tasks.extend(
                TaskTopologySnapshot(
                    group_id=self._group_id,
                    task_id=record.task_id,
                    lane_kind=ExecutionLaneKind.SERIAL,
                    lane_id=record.lane_id,
                    state=record.state,
                    execution_done=(
                        record.state in _TERMINAL_STATES
                        and (record.current is None or bool(record.current.done()))
                    ),
                    deadline_monotonic=None if record.deadline is None else record.deadline.monotonic_deadline,
                    failure_type=None if record.failure is None else type(record.failure).__name__,
                )
                for record in self._recurring.values()
            )
            return TaskGroupTopologySnapshot(
                group_id=self._group_id,
                failure_policy=self._failure_policy,
                deadline_monotonic=None if self._deadline is None else self._deadline.monotonic_deadline,
                cancelled=self._cancellation.cancelled,
                closing=self._closing,
                closed=self._closed,
                converged=self._converged,
                cancellation_reason=self._cancellation.reason,
                tasks=tuple(sorted(tasks, key=lambda item: item.task_id)),
            )

    def _all_execution_done(self) -> bool:
        with self._lock:
            tasks = tuple(self._tasks.values())
            recurring = tuple(self._recurring.values())
        return all(self._execution_done(record) for record in tasks) and all(
            record.current is None or bool(record.current.done()) for record in recurring
        )

    def _wait_for_submissions(self, deadline: Deadline) -> None:
        with self._condition:
            while self._active_submissions:
                remaining = deadline.remaining_seconds
                if remaining <= 0:
                    raise TimeoutError(
                        f"task group submissions did not quiesce before deadline: {self._group_id}"
                    )
                self._condition.wait(remaining)

    def close(
        self,
        *,
        cancel_pending: bool = False,
        deadline: Deadline | None = None,
    ) -> None:
        effective = deadline or Deadline.after(self._shutdown_timeout_seconds)
        with self._condition:
            if self._closed and self._converged:
                failure = self._close_failure
                if failure is not None:
                    raise failure
                return
            if self._closing:
                wait_for_existing_close = True
            else:
                self._closing = True
                self._closed = True  # sealed: no future submissions, even if convergence later fails
                self._close_failure = None
                self._close_complete.clear()
                self._submission_cancellation.cancel("task group closing submissions")
                wait_for_existing_close = False

        if wait_for_existing_close:
            if not self._close_complete.wait(effective.remaining_seconds):
                raise TimeoutError(f"task group close did not converge: {self._group_id}")
            with self._lock:
                failure = self._close_failure
            if failure is not None:
                raise failure
            return

        errors: list[BaseException] = []
        submissions_quiesced = False
        on_close_succeeded = self._on_close is None
        try:
            if cancel_pending:
                self.cancel("task group closing")
            try:
                self._wait_for_submissions(effective)
            except BaseException as exc:
                errors.append(exc)
            else:
                submissions_quiesced = True

            with self._lock:
                scheduled = tuple(self._scheduled_handles.values())
            for handle in scheduled:
                handle.cancel()

            # Do not disarm the group deadline before joining accepted children.
            # The deadline remains the scope's logical cancellation authority even
            # after close() seals future submissions.
            try:
                self.wait(timeout=effective.remaining_seconds)
            except BaseException as exc:
                errors.append(exc)
            if self._on_close is not None:
                try:
                    self._on_close(self._group_id, effective)
                except BaseException as exc:
                    errors.append(exc)
                else:
                    on_close_succeeded = True
        finally:
            failure: BaseException | None = None
            if errors:
                failure = errors[0] if len(errors) == 1 else ExceptionGroup(
                    f"task group close failed: {self._group_id}",
                    errors,
                )
            converged = submissions_quiesced and self._all_execution_done() and on_close_succeeded
            if converged:
                self._retire_group_deadline()
            with self._condition:
                self._close_failure = failure
                self._converged = converged
                self._closing = False
                self._condition.notify_all()
            self._close_complete.set()

        if failure is not None:
            raise failure

    def __enter__(self) -> "StructuredTaskGroup":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc is not None:
            self.cancel(f"task group scope failed: {type(exc).__name__}")
        self.close(cancel_pending=exc is not None)
        return False


__all__ = ["StructuredTaskGroup"]
