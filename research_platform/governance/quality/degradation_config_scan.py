from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib
from typing import Any, Iterable

from .degradation_contracts import (
    DegradationFinding,
    FORBIDDEN_ENABLED_CONFIG_KEYS,
    FORBIDDEN_NONEMPTY_CONFIG_KEYS,
)
from .degradation_paths import is_excluded_path

_TRUE_TOKENS = {"true", "yes", "on", "1"}
_EMPTY_TOKENS = {"", "null", "none", "[]", "{}", "''", '\"\"'}
_YAML_KEY_RE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*(?P<value>.*?)\s*(?:#.*)?$")


def _enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_TOKENS
    return False


def _nonempty(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in _EMPTY_TOKENS
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _walk_config(value: Any, *, path: str, line: int = 1, prefix: str = "") -> Iterable[DegradationFinding]:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key)
            fq = f"{prefix}.{key}" if prefix else key
            normalized = key.lower()
            if normalized in FORBIDDEN_ENABLED_CONFIG_KEYS and _enabled(child):
                yield DegradationFinding(path, line, fq, "config_enabled")
            if normalized in FORBIDDEN_NONEMPTY_CONFIG_KEYS and _nonempty(child):
                yield DegradationFinding(path, line, fq, "config_fallback_target")
            yield from _walk_config(child, path=path, line=line, prefix=fq)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_config(child, path=path, line=line, prefix=f"{prefix}[{index}]")


def _scan_yaml(path: Path, rel: Path) -> Iterable[DegradationFinding]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return
    for lineno, raw in enumerate(lines, start=1):
        match = _YAML_KEY_RE.match(raw)
        if not match:
            continue
        key = match.group("key").lower()
        value = match.group("value").strip()
        scalar = value.strip("'\"").lower()
        if key in FORBIDDEN_ENABLED_CONFIG_KEYS and scalar in _TRUE_TOKENS:
            yield DegradationFinding(rel.as_posix(), lineno, key, "config_enabled")
        if key in FORBIDDEN_NONEMPTY_CONFIG_KEYS and scalar not in _EMPTY_TOKENS:
            yield DegradationFinding(rel.as_posix(), lineno, key, "config_fallback_target")


def scan_config_degradation(root: Path) -> Iterable[DegradationFinding]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if is_excluded_path(rel):
            continue
        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            yield from _scan_yaml(path, rel)
        elif suffix == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            yield from _walk_config(payload, path=rel.as_posix())
        elif suffix == ".toml":
            try:
                with path.open("rb") as handle:
                    payload = tomllib.load(handle)
            except (OSError, tomllib.TOMLDecodeError):
                continue
            yield from _walk_config(payload, path=rel.as_posix())


__all__ = ["scan_config_degradation"]
