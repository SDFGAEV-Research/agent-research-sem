from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile
from collections.abc import Mapping

from research_platform.platform.kernel import JsonObject, JsonValue

from .diagnostics import json_default
from ..api.artifacts import RunArtifactKind, RunArtifactStorePort, RunArtifactWriteActorPort


class DirectoryRunArtifactStore(RunArtifactStorePort):
    """Crash-safe directory provider for run artifacts."""

    def __init__(self, root: Path | str, *, writer_actor: RunArtifactWriteActorPort) -> None:
        self.root = Path(root).expanduser().resolve()
        self._writer_actor = writer_actor

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

    def publish_json(self, name: str, payload: JsonValue, *, kind: RunArtifactKind) -> str:
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n"
        return self.publish_text(name, body, kind=kind)

    def publish_text(self, name: str, content: str, *, kind: RunArtifactKind) -> str:
        target = Path(self.path(name, kind=kind))

        def publish_owned() -> str:
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

        return self._writer_actor.call(f"publish:{name}", publish_owned)

    def append_json(
        self,
        name: str,
        payload: JsonObject,
        *,
        kind: RunArtifactKind,
    ) -> str:
        target = Path(self.path(name, kind=kind))
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=json_default) + "\n"

        def append_owned() -> str:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            return str(target)

        return self._writer_actor.call(f"append:{name}", append_owned)



__all__ = ["DirectoryRunArtifactStore"]
