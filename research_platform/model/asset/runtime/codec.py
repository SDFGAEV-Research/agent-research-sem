from __future__ import annotations
import json
from pathlib import Path
from research_platform.model.asset.api import ManagedModelAsset, ModelAssetMode, ModelAssetOrigin
from research_platform.scope.api import scope_from_data, scope_to_data

def encode_model_asset(value: ManagedModelAsset) -> bytes:
    return json.dumps({
        "model_id": value.model_id, "scope": scope_to_data(value.scope), "path": str(value.path),
        "mode": value.mode.value, "family": value.family, "notes": value.notes, "tags": list(value.tags),
        "storage_pool": value.storage_pool,
        "origin": None if value.origin is None else {"backend": value.origin.backend, "source": value.origin.source, "revision": value.origin.revision},
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def decode_model_asset(data: dict[str, object]) -> ManagedModelAsset:
    origin_data = data.get("origin")
    origin = None if origin_data is None else ModelAssetOrigin(
        backend=str(origin_data["backend"]), source=str(origin_data["source"]),
        revision=(str(origin_data["revision"]) if origin_data.get("revision") is not None else None),
    )
    return ManagedModelAsset(
        model_id=str(data["model_id"]), scope=scope_from_data(data["scope"]), path=Path(str(data["path"])),
        mode=ModelAssetMode(str(data["mode"])), family=str(data.get("family", "")), notes=str(data.get("notes", "")),
        origin=origin, tags=tuple(str(item) for item in data.get("tags", ())),
        storage_pool=(str(data["storage_pool"]) if data.get("storage_pool") is not None else None),
    )

__all__ = ["decode_model_asset", "encode_model_asset"]
