from __future__ import annotations

import hashlib
import json
from pathlib import Path



EXCLUDED_DIRS={"__pycache__",".git",".pytest_cache","build","dist"}
EXCLUDED_SUFFIXES={".pyc",".pyo"}
DERIVED_RELEASE_FILES={"RELEASE_MANIFEST.json","RELEASE_EVIDENCE.json"}

from .project_metadata import load_project_metadata


def hash_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()


from research_platform.governance.release.api import FileDigest, ReleaseManifest, RunLaunchManifest


def _iter_release_files(root:Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file(): continue
        rel=path.relative_to(root)
        if any(p in EXCLUDED_DIRS or p.endswith(".egg-info") for p in rel.parts): continue
        if path.suffix in EXCLUDED_SUFFIXES: continue
        if rel.as_posix() in DERIVED_RELEASE_FILES: continue
        yield path,rel


def build_release_manifest(
    root:Path,
    *,
    platform_code_version:str|None=None,
    python_requires:str|None=None,
)->ReleaseManifest:
    metadata=load_project_metadata(root)
    resolved_version=metadata.version if platform_code_version is None else platform_code_version
    resolved_python=metadata.python_requires if python_requires is None else python_requires
    files=[]
    for path,rel in _iter_release_files(root): files.append(FileDigest(rel.as_posix(),hash_file(path),path.stat().st_size))
    tree_raw="\n".join(f"{x.sha256}  {x.path}  {x.size}" for x in files).encode()
    return ReleaseManifest(1,tuple(files),hashlib.sha256(tree_raw).hexdigest(),resolved_python,resolved_version)


def verify_release_manifest(root:Path,manifest:ReleaseManifest)->tuple[str,...]:
    errors=[]; actual={x.path:x for x in build_release_manifest(root,platform_code_version=manifest.platform_code_version,python_requires=manifest.python_requires).files}; expected={x.path:x for x in manifest.files}
    for path in sorted(expected.keys()-actual.keys()): errors.append(f"missing file: {path}")
    for path in sorted(actual.keys()-expected.keys()): errors.append(f"unexpected file: {path}")
    for path in sorted(expected.keys()&actual.keys()):
        if expected[path].sha256!=actual[path].sha256 or expected[path].size!=actual[path].size: errors.append(f"file drift: {path}")
    if not errors:
        rebuilt=build_release_manifest(root,platform_code_version=manifest.platform_code_version,python_requires=manifest.python_requires)
        if rebuilt.source_tree_sha256!=manifest.source_tree_sha256: errors.append("source tree digest mismatch")
    return tuple(errors)
