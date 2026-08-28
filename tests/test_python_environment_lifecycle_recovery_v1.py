from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_platform.environment.python.api import (
    EnvironmentCommandResult,
    PythonEnvironmentOwnership,
    PythonEnvironmentSpec,
)
from research_platform.environment.python.runtime import build_python_environment_authorities
from research_platform.environment.python.runtime.lifecycle_transaction import (
    PythonEnvironmentLifecycleTransaction,
    PythonEnvironmentLifecycleTransactionStore,
)
from research_platform.environment.python.runtime.registry import PythonEnvironmentRegistry
from research_platform.resource.directory.api import DirectoryLayout, ManagedDirectoryKind
from research_platform.resource.directory.runtime import build_local_directory_authorities
from research_platform.scope.api import PLATFORM_SCOPE


def _layout(root: Path) -> DirectoryLayout:
    return DirectoryLayout(
        releases=root / "releases",
        runtime=root / "runtime",
        state=root / "state",
        logs=root / "logs",
        model_artifacts=root / "models",
        python_environments=root / "envs",
        cache=root / "cache",
        temp=root / "tmp",
        locks=root / "locks",
        workspaces=root / "workspaces",
    )


class _Runner:
    def run(self, argv, *, cwd=None, environment=None):
        return EnvironmentCommandResult(tuple(argv), 0, "", "")


class _Backend:
    backend_id = "fake"

    def __init__(self, *, fail_after_partial: bool = False) -> None:
        self.fail_after_partial = fail_after_partial

    def create(self, root: Path, spec: PythonEnvironmentSpec) -> Path:
        del spec
        path = self.python_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.fail_after_partial:
            (root / "partial.txt").write_text("partial", encoding="utf-8")
            raise RuntimeError("backend create failed")
        path.write_text("python", encoding="utf-8")
        return path

    def python_path(self, root: Path) -> Path:
        return root / "bin" / "python"

    def install(self, root: Path, requirements: Path, *, extra_args: tuple[str, ...] = ()) -> EnvironmentCommandResult:
        del root, requirements, extra_args
        return EnvironmentCommandResult(("pip",), 0, "", "")


def _directories(root: Path):
    return build_local_directory_authorities(_layout(root))


def _authorities(root: Path, backend: _Backend | None = None):
    directories = _directories(root)
    authorities = build_python_environment_authorities(
        directories.layout,
        (backend or _Backend(),),
        _Runner(),
    )
    return directories, authorities


def _spec(environment_id: str = "managed") -> PythonEnvironmentSpec:
    return PythonEnvironmentSpec(
        environment_id,
        PLATFORM_SCOPE,
        backend="fake",
        description="managed test env",
        tags=("test",),
    )


def _transaction(root: Path, *, operation: str, phase: str, environment_id: str = "managed"):
    directories = _directories(root)
    spec = _spec(environment_id)
    env_root = directories.layout.root(ManagedDirectoryKind.PYTHON_ENVIRONMENTS) / environment_id
    txn = PythonEnvironmentLifecycleTransaction(
        operation,
        phase,
        environment_id,
        spec.scope,
        spec.backend,
        env_root,
        env_root / "bin" / "python",
        PythonEnvironmentOwnership.MANAGED,
        spec.description,
        tuple(sorted(set(spec.tags))),
        spec.specification_digest,
    )
    return directories, spec, txn


def _materialize(txn: PythonEnvironmentLifecycleTransaction, payload: bytes = b"python") -> None:
    txn.python_path.parent.mkdir(parents=True, exist_ok=True)
    txn.python_path.write_bytes(payload)


def test_create_failure_rolls_back_partial_managed_root_and_journal(tmp_path) -> None:
    directories, authorities = _authorities(tmp_path, _Backend(fail_after_partial=True))
    with pytest.raises(RuntimeError, match="backend create failed"):
        authorities.lifecycle.create(_spec())
    env_root = directories.layout.root(ManagedDirectoryKind.PYTHON_ENVIRONMENTS) / "managed"
    assert not env_root.exists()
    with pytest.raises(KeyError):
        authorities.lifecycle.get("managed")
    assert PythonEnvironmentLifecycleTransactionStore(directories.layout).get("managed") is None


def test_constructor_completes_materialized_create_after_crash(tmp_path) -> None:
    directories, _spec_value, txn = _transaction(tmp_path, operation="create", phase="materialized")
    _materialize(txn)
    store = PythonEnvironmentLifecycleTransactionStore(directories.layout)
    store.put(txn)

    _directories_again, authorities = _authorities(tmp_path)

    loaded = authorities.lifecycle.get("managed")
    assert loaded.specification_digest == txn.specification_digest
    assert loaded.root == txn.root
    assert store.get("managed") is None


def test_constructor_finishes_create_when_registry_was_published_before_phase_commit(tmp_path) -> None:
    directories, _spec_value, txn = _transaction(tmp_path, operation="create", phase="materialized")
    _materialize(txn)
    store = PythonEnvironmentLifecycleTransactionStore(directories.layout)
    store.put(txn)
    PythonEnvironmentRegistry(directories.layout).put(txn.environment())

    _directories_again, authorities = _authorities(tmp_path)

    assert authorities.lifecycle.get("managed").identity_digest == txn.environment().identity_digest
    assert store.get("managed") is None


def test_prepared_create_crash_rolls_back_partial_root_on_constructor(tmp_path) -> None:
    directories, _spec_value, txn = _transaction(tmp_path, operation="create", phase="prepared")
    _materialize(txn, b"partial")
    store = PythonEnvironmentLifecycleTransactionStore(directories.layout)
    store.put(txn)

    _authorities(tmp_path)

    assert not txn.root.exists()
    assert store.get("managed") is None


def test_remove_crash_after_registry_delete_continues_root_cleanup(tmp_path) -> None:
    directories, authorities = _authorities(tmp_path)
    created = authorities.lifecycle.create(_spec())
    store = PythonEnvironmentLifecycleTransactionStore(directories.layout)
    txn = PythonEnvironmentLifecycleTransaction(
        "remove", "prepared", created.environment_id, created.scope, created.backend,
        created.root, created.python_path, created.ownership, created.description,
        created.tags, created.specification_digest,
    )
    store.put(txn)
    PythonEnvironmentRegistry(directories.layout).remove("managed")

    _authorities(tmp_path)

    assert not created.root.exists()
    assert store.get("managed") is None


def test_remove_crash_after_root_delete_clears_unregistered_transaction(tmp_path) -> None:
    directories, authorities = _authorities(tmp_path)
    created = authorities.lifecycle.create(_spec())
    store = PythonEnvironmentLifecycleTransactionStore(directories.layout)
    txn = PythonEnvironmentLifecycleTransaction(
        "remove", "unregistered", created.environment_id, created.scope, created.backend,
        created.root, created.python_path, created.ownership, created.description,
        created.tags, created.specification_digest,
    )
    store.put(txn)
    PythonEnvironmentRegistry(directories.layout).remove("managed")
    import shutil
    shutil.rmtree(created.root)

    _authorities(tmp_path)

    assert store.get("managed") is None


def test_transaction_digest_tampering_fails_closed_before_mutation(tmp_path) -> None:
    directories, _spec_value, txn = _transaction(tmp_path, operation="create", phase="prepared")
    _materialize(txn, b"partial")
    store = PythonEnvironmentLifecycleTransactionStore(directories.layout)
    store.put(txn)
    path = directories.layout.root(ManagedDirectoryKind.STATE) / "python-environment-lifecycle" / "managed.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["phase"] = "committed"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RuntimeError, match="digest mismatch"):
        _authorities(tmp_path)

    assert txn.root.exists()
    assert path.exists()


def test_committed_create_missing_root_fails_closed_and_preserves_journal(tmp_path) -> None:
    directories, _spec_value, txn = _transaction(tmp_path, operation="create", phase="committed")
    store = PythonEnvironmentLifecycleTransactionStore(directories.layout)
    store.put(txn)

    with pytest.raises(RuntimeError, match="Committed Python environment is missing"):
        _authorities(tmp_path)

    assert store.get("managed") is not None


def test_create_is_idempotent_only_for_same_managed_specification(tmp_path) -> None:
    _directories_value, authorities = _authorities(tmp_path)
    first = authorities.lifecycle.create(_spec())
    second = authorities.lifecycle.create(_spec())
    assert second.identity_digest == first.identity_digest

    changed = PythonEnvironmentSpec("managed", PLATFORM_SCOPE, backend="fake", description="changed")
    with pytest.raises(FileExistsError, match="already registered"):
        authorities.lifecycle.create(changed)


class _CountingBackend(_Backend):
    def __init__(self) -> None:
        super().__init__()
        self.create_count = 0

    def create(self, root: Path, spec: PythonEnvironmentSpec) -> Path:
        import time
        self.create_count += 1
        time.sleep(0.05)
        return super().create(root, spec)


def test_concurrent_same_spec_create_materializes_backend_once(tmp_path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    backend = _CountingBackend()
    _directories_value, authorities = _authorities(tmp_path, backend)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(lambda _item: authorities.lifecycle.create(_spec()), range(2)))

    assert backend.create_count == 1
    assert results[0].identity_digest == results[1].identity_digest


def test_same_spec_create_does_not_hide_missing_registered_interpreter(tmp_path) -> None:
    _directories_value, authorities = _authorities(tmp_path)
    created = authorities.lifecycle.create(_spec())
    created.python_path.unlink()

    with pytest.raises(FileExistsError, match="already registered"):
        authorities.lifecycle.create(_spec())

    assert authorities.lifecycle.get("managed").state.value == "missing"
