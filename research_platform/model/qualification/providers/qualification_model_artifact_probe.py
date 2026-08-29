"""Model artifact facts for deployment qualification."""

from __future__ import annotations

import json
from pathlib import Path

from research_platform.model.qualification.api import DeploymentQualificationRequest, ModelArtifactFacts


class ModelArtifactProbe:
    """Inspect local model artifacts without loading model weights."""
    @staticmethod
    def _artifact_stats(path: Path) -> tuple[int | None, int | None, int | None]:
        if not path.is_dir():
            return None, None, None
        total = 0
        files = 0
        shards = 0
        try:
            for item in path.rglob("*"):
                if not item.is_file():
                    continue
                files += 1
                total += item.stat().st_size
                if item.suffix.lower() in {".safetensors", ".bin", ".pt", ".pth"}:
                    shards += 1
        except OSError:
            return None, None, None
        return total, files, shards

    @classmethod
    def capture(cls, request: DeploymentQualificationRequest) -> tuple[ModelArtifactFacts, str | None]:
        path = request.model_path
        artifact_bytes, file_count, shard_count = cls._artifact_stats(path)
        config = path / "config.json"
        if not config.is_file():
            return ModelArtifactFacts(
                request.model_id,
                str(path),
                None,
                (),
                None,
                None,
                False,
                "model config.json is missing",
                artifact_bytes,
                file_count,
                shard_count,
                artifact_bytes,
            ), "model config.json is missing"
        try:
            data = json.loads(config.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ModelArtifactFacts(
                request.model_id,
                str(path),
                None,
                (),
                None,
                None,
                False,
                type(exc).__name__,
                artifact_bytes,
                file_count,
                shard_count,
                artifact_bytes,
            ), "model config.json could not be parsed"
        context = next((data.get(key) for key in ("max_position_embeddings", "max_sequence_length", "max_seq_len") if data.get(key) is not None), None)
        return ModelArtifactFacts(
            request.model_id,
            str(path),
            str(data["model_type"]) if data.get("model_type") else None,
            tuple(str(x) for x in data.get("architectures", ())),
            str(data["torch_dtype"]) if data.get("torch_dtype") else None,
            int(context) if context is not None else None,
            True,
            None,
            artifact_bytes,
            file_count,
            shard_count,
            artifact_bytes,
        ), None

__all__ = ["ModelArtifactProbe"]
