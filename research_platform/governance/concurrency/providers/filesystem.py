from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Iterable

from research_platform.governance.concurrency.api import (
    ConcurrencyBaseline, ConcurrencyDocument, ConcurrencyLanguage, ConcurrencySnapshot,
)
from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes

_LANG={'.py':ConcurrencyLanguage.PYTHON,'.js':ConcurrencyLanguage.JAVASCRIPT,'.mjs':ConcurrencyLanguage.JAVASCRIPT,'.cjs':ConcurrencyLanguage.JAVASCRIPT,'.sh':ConcurrencyLanguage.SHELL,'.bash':ConcurrencyLanguage.SHELL}
_EXCLUDE={'.git','.venv','venv','node_modules','__pycache__','.pytest_cache','.local','dist','build'}


class RepositoryConcurrencySourceInventory:
    def __init__(self, root:Path, *, include_tests:bool=False): self._root=Path(root).resolve(); self._include_tests=include_tests
    def documents(self)->Iterable[ConcurrencyDocument]:
        for path in sorted(self._root.rglob('*')):
            if not path.is_file(): continue
            rel=path.relative_to(self._root)
            if any(x in _EXCLUDE for x in rel.parts) or (not self._include_tests and rel.parts and rel.parts[0]=='tests'): continue
            lang=_LANG.get(path.suffix.lower())
            if lang is None: continue
            try: raw=path.read_bytes(); text=raw.decode('utf-8')
            except (OSError,UnicodeDecodeError): continue
            yield ConcurrencyDocument(rel.as_posix(),lang,hashlib.sha256(raw).hexdigest(),text)


class FilesystemConcurrencySnapshotStore:
    def __init__(self, state_root:Path, *, baseline_path:Path):
        self._root=Path(state_root); self._root.mkdir(parents=True,exist_ok=True); self._history=self._root/'history'; self._baseline=Path(baseline_path)
    @staticmethod
    def _bytes(value): return json.dumps(asdict(value),sort_keys=True,separators=(',',':')).encode()+b'\n'
    def publish_current(self,snapshot:ConcurrencySnapshot)->None: atomic_replace_bytes(self._root/'CONCURRENCY_CURRENT.json',self._bytes(snapshot))
    def append_history(self,snapshot:ConcurrencySnapshot)->None:
        self._history.mkdir(parents=True,exist_ok=True)
        latest=sorted(self._history.glob('*.json'))
        if latest:
            try:
                data=json.loads(latest[-1].read_text())
                if data.get('source_digest')==snapshot.source_digest and data.get('analyzer_revision')==snapshot.analyzer_revision:return
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass
        atomic_replace_bytes(self._history/f'{snapshot.generated_unix_ns}-{snapshot.source_digest[:12]}.json',self._bytes(snapshot))
    def load_baseline(self)->ConcurrencyBaseline|None:
        if not self._baseline.exists(): return None
        data=json.loads(self._baseline.read_text())
        return ConcurrencyBaseline(
            schema_version=str(data['schema_version']), analyzer_revision=str(data['analyzer_revision']),
            blocker_fingerprints=tuple(str(x) for x in data.get('blocker_fingerprints',())),
        )
    def publish_baseline(self,baseline:ConcurrencyBaseline)->None:
        self._baseline.parent.mkdir(parents=True,exist_ok=True)
        atomic_replace_bytes(self._baseline,self._bytes(baseline))
