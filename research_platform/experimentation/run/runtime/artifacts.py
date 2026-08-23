from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile
from collections.abc import Mapping

from .diagnostics import json_default
from ..api.artifacts import RunArtifactKind, RunArtifactStorePort


class DirectoryRunArtifactStore(RunArtifactStorePort):
    """Crash-safe directory provider for run artifacts."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()
        self._appenders: dict[str, object] = {}

    def path(self, name: str, *, kind: RunArtifactKind) -> str:
        del kind
        if not name.strip() or Path(name).is_absolute():
            raise ValueError("run artifact name must be a non-empty relative path")
        relative = Path(name)
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("run artifact name contains an unsafe path component")
        target = (self.root / relative).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("run artifact path escapes the run root") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        return str(target)

    def directory(self, name: str, *, kind: RunArtifactKind) -> str:
        del kind
        if not name.strip() or Path(name).is_absolute():
            raise ValueError("run artifact directory must be a non-empty relative path")
        relative = Path(name)
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise ValueError("run artifact directory contains an unsafe path component")
        target = (self.root / relative).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("run artifact directory escapes the run root") from exc
        target.mkdir(parents=True, exist_ok=True)
        return str(target)

    def publish_json(self, name: str, payload: object, *, kind: RunArtifactKind) -> str:
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n"
        return self.publish_text(name, body, kind=kind)

    def publish_text(self, name: str, content: str, *, kind: RunArtifactKind) -> str:
        target = Path(self.path(name, kind=kind))
        descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            Path(temporary).replace(target)
            return str(target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def append_json(
        self,
        name: str,
        payload: Mapping[str, object],
        *,
        kind: RunArtifactKind,
    ) -> str:
        from .diagnostics import JsonlAppender

        target = self.path(name, kind=kind)
        appender = self._appenders.get(target)
        if appender is None:
            appender = JsonlAppender(Path(target))
            self._appenders[target] = appender
        if not isinstance(appender, JsonlAppender):
            raise TypeError("run artifact append authority has an invalid provider")
        appender.append(payload)
        return target


__all__ = ["DirectoryRunArtifactStore"]
