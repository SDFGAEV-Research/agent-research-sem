from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4


class DurableFileWriteError(RuntimeError):
    """Raised when a durable filesystem publication cannot be completed."""


def fsync_directory(path: Path) -> None:
    """Persist directory-entry updates for *path*.

    File fsync alone does not make a rename durable across power loss.  The
    directory containing the replaced entry must also be fsynced.  This helper
    deliberately knows nothing about document formats or domain state.
    """

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_replace_bytes(path: Path, payload: bytes) -> None:
    """Durably publish *payload* at *path* using same-directory atomic replace.

    The protocol is intentionally minimal and domain-agnostic:

        write unique temp -> fsync(temp) -> replace -> fsync(parent)

    A unique temp name avoids concurrent writers corrupting one another's temp
    file.  Higher layers remain responsible for single-writer/CAS semantics and
    document schemas/checksums.
    """

    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = parent / f".{path.name}.tmp.{os.getpid()}.{uuid4().hex}"
    published = False
    try:
        with tmp.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        published = True
        fsync_directory(parent)
    except BaseException as exc:
        if not published:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise DurableFileWriteError(f"durable atomic publication failed for {path}") from exc


def durable_replace_file(source: Path, target: Path) -> None:
    """Durably replace *target* with an already materialized file *source*.

    This variant is intended for large generated artifacts such as rebuilt
    SQLite databases where re-reading the whole source into memory merely to
    call :func:`atomic_replace_bytes` would be wasteful.  The source file is
    fsynced before rename and the target directory is fsynced afterwards.
    """

    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(source, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.replace(source, target)
        fsync_directory(target.parent)
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise DurableFileWriteError(
            f"durable file replacement failed: {source} -> {target}"
        ) from exc


def durable_unlink(path: Path) -> None:
    """Remove *path* and persist the directory-entry deletion."""

    if not path.exists():
        return
    path.unlink()
    fsync_directory(path.parent)


__all__ = [
    "DurableFileWriteError",
    "atomic_replace_bytes",
    "durable_replace_file",
    "durable_unlink",
    "fsync_directory",
]
