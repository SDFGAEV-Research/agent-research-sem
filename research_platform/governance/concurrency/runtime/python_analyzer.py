from __future__ import annotations

import ast
from dataclasses import replace

from research_platform.governance.concurrency.api import (
    ConcurrencyDocument,
    ConcurrencyFileAnalysis,
    ConcurrencyFinding,
    ConcurrencyHotspot,
    ConcurrencyLanguage,
    ConcurrencyMetrics,
    ConcurrencyPriority,
)

_ALLOWED_THREAD_PREFIXES = (
    "research_platform/platform/concurrency/providers/",
    "research_platform/platform/kernel/process/",
)
_ALLOWED_EXECUTOR_PREFIXES = (
    "research_platform/platform/concurrency/providers/",
)
_ALLOWED_TASK_PREFIXES = (
    "research_platform/platform/concurrency/providers/",
)
_BLOCKING_ASYNC_EXACT = {
    "time.sleep",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "os.system",
}
_BLOCKING_ASYNC_LEAVES = {
    "read_bytes", "read_text", "write_bytes", "write_text", "open", "execute", "executemany", "wait",
}
_SLOW_UNDER_LOCK = {
    "open", "read_bytes", "read_text", "write_bytes", "write_text",
    "execute", "executemany", "executescript", "connect", "send", "recv", "request", "urlopen",
    "run", "Popen", "wait", "join", "sleep", "fsync",
}
_SLOW_EXACT = {
    "os.open", "os.close", "os.read", "os.write", "os.pread", "os.pwrite",
    "os.fsync", "os.fdatasync", "os.stat", "os.fstat", "os.replace", "os.rename",
}
_LOCK_NAMES = {"Lock", "RLock", "Condition", "Semaphore", "BoundedSemaphore"}
_QUEUE_NAMES = {"Queue", "LifoQueue", "PriorityQueue"}
_THREAD_NAMES = {"Thread"}
_THREAD_POOL_NAMES = {"ThreadPoolExecutor"}
_PROCESS_POOL_NAMES = {"ProcessPoolExecutor"}
_TASK_NAMES = {"create_task", "ensure_future"}
_SUBPROCESS_NAMES = {"Popen", "run", "call", "check_call", "check_output"}

_OWNED_WAIT_POLICY = "OWNED_CONDITION_WAIT"
_BOUNDED_FANOUT_POLICY = "BOUNDED_TASK_FANOUT"
_CONCURRENCY_POLICIES = {_OWNED_WAIT_POLICY, _BOUNDED_FANOUT_POLICY}


def _concurrency_contract(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str | None, str | None]:
    doc = ast.get_docstring(node, clean=False) or ""
    policy = None
    rationale = None
    for raw_line in doc.splitlines():
        line = raw_line.strip()
        if line.startswith("Concurrency-Policy:"):
            candidate = line.split(":", 1)[1].strip()
            if candidate in _CONCURRENCY_POLICIES:
                policy = candidate
        elif line.startswith("Concurrency-Rationale:"):
            candidate = line.split(":", 1)[1].strip()
            if len(candidate) >= 20:
                rationale = candidate
    if policy is None or rationale is None:
        return None, None
    return policy, rationale


def _call_name(node: ast.Call) -> str:
    value = node.func
    parts: list[str] = []
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _queue_is_bounded(node: ast.Call) -> bool:
    if node.args:
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, int):
            return first.value > 0
        return True
    for keyword in node.keywords:
        if keyword.arg == "maxsize":
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, int):
                return keyword.value.value > 0
            return True
    return False


def _has_timeout(node: ast.Call) -> bool:
    if len(node.args) >= 1:
        return True
    return any(k.arg in {"timeout", "timeout_seconds"} for k in node.keywords)


class _FunctionSummaryVisitor(ast.NodeVisitor):
    """Collect direct slow calls and local helper calls without descending into nested definitions."""

    def __init__(self) -> None:
        self.direct_slow = False
        self.calls: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        leaf = name.rsplit(".", 1)[-1]
        literal_join = (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Constant)
            and isinstance(node.func.value.value, (str, bytes))
        )
        lifecycle_join = leaf == "join" and not literal_join
        if name in _SLOW_EXACT or (leaf in _SLOW_UNDER_LOCK and (leaf != "join" or lifecycle_join)):
            self.direct_slow = True
        if name:
            self.calls.append(name)
        self.generic_visit(node)


class _LocalBlockingCatalog:
    """Small intrafile call graph used to catch lock -> helper -> blocking I/O chains."""

    def __init__(self, tree: ast.Module) -> None:
        self._nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self._calls: dict[str, tuple[str, ...]] = {}
        self._blocking: set[str] = set()
        self._collect(tree.body)
        self._summarize()

    def _collect(self, body: list[ast.stmt], prefix: tuple[str, ...] = ()) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = ".".join((*prefix, node.name))
                self._nodes[q] = node
                self._collect(node.body, (*prefix, node.name))
            elif isinstance(node, ast.ClassDef):
                self._collect(node.body, (*prefix, node.name))

    def _resolve(self, caller: str, call_name: str) -> str | None:
        parts = call_name.split(".") if call_name else []
        leaf = parts[-1] if parts else ""
        parent = caller.rsplit(".", 1)[0] if "." in caller else ""
        # Only an exact ``self.method()``/``cls.method()`` call denotes another
        # method on the same class.  ``self._executor.submit()`` and
        # ``self._handle.close()`` target injected objects and must not be
        # rebound to this class merely because the leaf name matches.
        if len(parts) == 2 and parts[0] in {"self", "cls"} and parent:
            candidate = f"{parent}.{leaf}"
            return candidate if candidate in self._nodes else None
        # Bare local calls can resolve to a module/nested function.  Attribute
        # calls on arbitrary receivers are deliberately opaque in this small
        # intrafile graph.
        if len(parts) == 1:
            if call_name in self._nodes:
                return call_name
            same_parent = f"{parent}.{leaf}" if parent else leaf
            if same_parent in self._nodes:
                return same_parent
            matches = [q for q in self._nodes if q.rsplit(".", 1)[-1] == leaf]
            if len(matches) == 1:
                return matches[0]
        return None

    def _summarize(self) -> None:
        for q, node in self._nodes.items():
            visitor = _FunctionSummaryVisitor()
            for stmt in node.body:
                if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visitor.visit(stmt)
            self._calls[q] = tuple(visitor.calls)
            if visitor.direct_slow:
                self._blocking.add(q)
        changed = True
        while changed:
            changed = False
            for caller, calls in self._calls.items():
                if caller in self._blocking:
                    continue
                if any((resolved := self._resolve(caller, name)) in self._blocking for name in calls):
                    self._blocking.add(caller)
                    changed = True

    def is_blocking_helper(self, caller: str, call_name: str) -> bool:
        resolved = self._resolve(caller, call_name)
        return resolved is not None and resolved in self._blocking


class _BodyAnalyzer(ast.NodeVisitor):
    def __init__(
        self,
        *,
        relative_path: str,
        qualified_name: str,
        async_function: bool,
        concurrency_policy: str | None,
        local_blocking: _LocalBlockingCatalog,
    ) -> None:
        self.relative_path = relative_path
        self.qualified_name = qualified_name
        self.async_function = async_function
        self.concurrency_policy = concurrency_policy
        self.local_blocking = local_blocking
        self.loop_depth = 0
        self.lock_depth = 0
        self.await_depth = 0
        self.values = {name: 0 for name in ConcurrencyMetrics.__dataclass_fields__}
        self.values["async_functions"] = int(async_function)
        self.findings: list[ConcurrencyFinding] = []

    def _add(self, priority: ConcurrencyPriority, code: str, detail: str, line: int) -> None:
        self.findings.append(ConcurrencyFinding(priority, code, detail, line))

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.target); self.visit(node.iter)
        self.loop_depth += 1
        for stmt in node.body: self.visit(stmt)
        self.loop_depth -= 1
        for stmt in node.orelse: self.visit(stmt)
    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While) -> None:
        self.visit(node.test); self.loop_depth += 1
        for stmt in node.body: self.visit(stmt)
        self.loop_depth -= 1
        for stmt in node.orelse: self.visit(stmt)

    def visit_With(self, node: ast.With) -> None:
        lock_scope = any(self._looks_lock_context(item.context_expr) for item in node.items)
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars: self.visit(item.optional_vars)
        if lock_scope:
            self.values["lock_scopes"] += 1
            self.lock_depth += 1
        for stmt in node.body: self.visit(stmt)
        if lock_scope: self.lock_depth -= 1
    visit_AsyncWith = visit_With

    @staticmethod
    def _looks_lock_context(node: ast.expr) -> bool:
        if isinstance(node, ast.Name):
            return "lock" in node.id.lower() or "condition" in node.id.lower()
        if isinstance(node, ast.Attribute):
            return "lock" in node.attr.lower() or "condition" in node.attr.lower()
        return False

    def visit_Await(self, node: ast.Await) -> None:
        self.values["await_calls"] += 1
        self.await_depth += 1
        try:
            self.visit(node.value)
        finally:
            self.await_depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        leaf = name.rsplit(".", 1)[-1]
        line = getattr(node, "lineno", 0)
        if leaf in _THREAD_NAMES:
            self.values["thread_constructors"] += 1
            daemon = any(k.arg == "daemon" and isinstance(k.value, ast.Constant) and bool(k.value.value) for k in node.keywords)
            if daemon:
                self.values["daemon_threads"] += 1
                if not self.relative_path.startswith(_ALLOWED_THREAD_PREFIXES):
                    self._add(ConcurrencyPriority.P1, "daemon-thread-lifecycle", "daemon thread is not owned by the platform concurrency provider", line)
            if not self.relative_path.startswith(_ALLOWED_THREAD_PREFIXES):
                self._add(ConcurrencyPriority.P1, "unmanaged-thread", "thread construction bypasses platform.concurrency", line)
        if leaf in _THREAD_POOL_NAMES:
            self.values["thread_pool_constructors"] += 1
            if not self.relative_path.startswith(_ALLOWED_EXECUTOR_PREFIXES):
                self._add(ConcurrencyPriority.P1, "unmanaged-thread-pool", "ThreadPoolExecutor bypasses platform.concurrency", line)
        if leaf in _PROCESS_POOL_NAMES:
            self.values["process_pool_constructors"] += 1
            if not self.relative_path.startswith(_ALLOWED_EXECUTOR_PREFIXES):
                self._add(ConcurrencyPriority.P1, "unmanaged-process-pool", "ProcessPoolExecutor bypasses platform.concurrency", line)
        if leaf in _TASK_NAMES:
            self.values["task_creations"] += 1
            if self.loop_depth:
                self.values["fanout_in_loops"] += 1
                self._add(ConcurrencyPriority.P1, "unbounded-task-fanout", "async task creation occurs inside a loop without visible admission bound", line)
            if not self.relative_path.startswith(_ALLOWED_TASK_PREFIXES):
                self._add(ConcurrencyPriority.P1, "unmanaged-async-task", "async task creation bypasses structured concurrency ownership", line)
        if leaf in _QUEUE_NAMES:
            self.values["queue_constructors"] += 1
            if not _queue_is_bounded(node):
                self.values["unbounded_queues"] += 1
                self._add(ConcurrencyPriority.P0, "unbounded-queue", "queue has no explicit positive capacity/backpressure", line)
        if leaf in _LOCK_NAMES:
            self.values["lock_constructors"] += 1
        if leaf in _SUBPROCESS_NAMES and (name.startswith("subprocess.") or leaf == "Popen"):
            self.values["subprocess_constructors"] += 1
        literal_join = (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Constant)
            and isinstance(node.func.value.value, (str, bytes))
        )
        lifecycle_join = leaf == "join" and not literal_join
        if lifecycle_join:
            self.values["lifecycle_join_calls"] += 1
        awaited_wait = leaf == "wait" and self.await_depth > 0
        wait_like = (leaf in {"wait", "result"} or lifecycle_join) and not awaited_wait
        condition_wait = leaf == "wait" and "condition" in name.lower()
        if wait_like and not _has_timeout(node):
            self.values["timeoutless_waits"] += 1
            owned_receive = condition_wait and self.concurrency_policy == _OWNED_WAIT_POLICY
            if not owned_receive:
                self._add(ConcurrencyPriority.P2, "timeoutless-wait", "blocking wait has no explicit deadline/timeout", line)
        blocking_async = (
            name in _BLOCKING_ASYNC_EXACT
            or (leaf in _BLOCKING_ASYNC_LEAVES and not awaited_wait)
            or lifecycle_join
        )
        if self.async_function and blocking_async:
            self.values["blocking_calls_in_async"] += 1
            self._add(ConcurrencyPriority.P0, "blocking-in-async", f"blocking call in async function: {name or leaf}", line)
        slow_leaf = name in _SLOW_EXACT or (leaf in _SLOW_UNDER_LOCK and (leaf != "join" or lifecycle_join))
        indirect_slow = self.local_blocking.is_blocking_helper(self.qualified_name, name)
        if self.lock_depth and (slow_leaf or indirect_slow) and not condition_wait:
            self.values["blocking_calls_under_lock"] += 1
            code = "blocking-helper-under-lock" if indirect_slow and not slow_leaf else "blocking-under-lock"
            detail = (
                f"call while lock is held reaches a local helper with blocking I/O: {name or leaf}"
                if code == "blocking-helper-under-lock"
                else f"potentially slow/blocking call while lock is held: {name or leaf}"
            )
            self._add(ConcurrencyPriority.P1, code, detail, line)
        if self.loop_depth and leaf in {"submit", "map"}:
            self.values["fanout_in_loops"] += 1
            if self.concurrency_policy != _BOUNDED_FANOUT_POLICY:
                self._add(ConcurrencyPriority.P2, "executor-fanout-in-loop", "executor fanout occurs in a loop without a reviewed bounded-fanout contract", line)
        self.generic_visit(node)

    def metrics(self) -> ConcurrencyMetrics:
        return ConcurrencyMetrics(**self.values)


class PythonConcurrencyAnalyzer:
    language = ConcurrencyLanguage.PYTHON
    revision = "python-concurrency-ast-v10"

    def analyze(self, document: ConcurrencyDocument) -> ConcurrencyFileAnalysis:
        try:
            tree = ast.parse(document.text, filename=document.relative_path)
        except SyntaxError:
            return ConcurrencyFileAnalysis(document.relative_path, document.language, document.sha256, self.revision, (), 1)
        hotspots: list[ConcurrencyHotspot] = []
        local_blocking = _LocalBlockingCatalog(tree)

        def walk(body: list[ast.stmt], prefix: tuple[str, ...] = ()) -> None:
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    q = ".".join((*prefix, node.name))
                    concurrency_policy, _rationale = _concurrency_contract(node)
                    analyzer = _BodyAnalyzer(
                        relative_path=document.relative_path,
                        qualified_name=q,
                        async_function=isinstance(node, ast.AsyncFunctionDef),
                        concurrency_policy=concurrency_policy,
                        local_blocking=local_blocking,
                    )
                    for stmt in node.body:
                        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            analyzer.visit(stmt)
                    metrics = analyzer.metrics()
                    findings = tuple(analyzer.findings)
                    has_primitives = any(getattr(metrics, field) for field in ConcurrencyMetrics.__dataclass_fields__)
                    if findings or has_primitives:
                        hotspots.append(ConcurrencyHotspot(
                            hotspot_id=f"{document.relative_path}::{q}",
                            relative_path=document.relative_path,
                            language=document.language,
                            qualified_name=q,
                            line_start=node.lineno,
                            line_end=getattr(node, "end_lineno", node.lineno),
                            metrics=metrics,
                            findings=findings,
                        ))
                    walk(node.body, (*prefix, node.name))
                elif isinstance(node, ast.ClassDef):
                    walk(node.body, (*prefix, node.name))
        walk(tree.body)
        return ConcurrencyFileAnalysis(
            document.relative_path, document.language, document.sha256, self.revision,
            tuple(hotspots), 0,
        )
