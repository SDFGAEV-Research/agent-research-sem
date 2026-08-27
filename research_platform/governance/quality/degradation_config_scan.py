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
from .degradation_paths import iter_audited_files

_TRUE_TOKENS = {"true", "yes", "on", "1"}
_EMPTY_TOKENS = {"", "null", "none", "[]", "{}", "''", '\"\"'}
_YAML_KEY_RE = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*(?P<value>.*?)\s*(?:#.*)?$")

_FORBIDDEN_CONFIG_KEY_RE = re.compile(
    "|".join(
        re.escape(key)
        for key in sorted(FORBIDDEN_ENABLED_CONFIG_KEYS | FORBIDDEN_NONEMPTY_CONFIG_KEYS)
    ),
    re.IGNORECASE,
)


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
    suffixes = frozenset({".yaml", ".yml", ".json", ".toml"})
    for path in iter_audited_files(root, suffixes=suffixes):
        rel = path.relative_to(root)
        suffix = path.suffix.lower()
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _FORBIDDEN_CONFIG_KEY_RE.search(raw) is None:
            continue
        if suffix in {".yaml", ".yml"}:
            # Reuse the strict YAML line scanner only after the exact-safe prefilter.
            yield from _scan_yaml(path, rel)
        elif suffix == ".json":
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            yield from _walk_config(payload, path=rel.as_posix())
        elif suffix == ".toml":
            try:
                payload = tomllib.loads(raw)
            except tomllib.TOMLDecodeError:
                continue
            yield from _walk_config(payload, path=rel.as_posix())


__all__ = ["scan_config_degradation"]
