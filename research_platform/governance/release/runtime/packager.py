from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import tempfile
import zipfile

from research_platform.governance.release.api import ReleaseManifest
from research_platform.platform.kernel import canonical_bytes
from .manifest import build_release_manifest
from .evidence import RELEASE_EVIDENCE_FILENAME, ReleaseEvidence, ReleaseEvidenceMismatch, load_release_evidence


@dataclass(frozen=True, slots=True)
class ReleasePackage:
    zip_path: str
    sha256: str
    manifest_digest: str
    file_count: int
    evidence_digest: str | None = None


class ReleasePackager:
    """Deterministic source/document package: sorted entries, normalized timestamps and permissions."""
    NORMALIZED_DT=(2026,1,1,0,0,0)
    def build(
        self,
        root:Path,
        zip_path:Path,
        *,
        version:str|None=None,
        evidence:ReleaseEvidence|None=None,
    )->ReleasePackage:
        manifest=build_release_manifest(root,platform_code_version=version)
        resolved_evidence=evidence
        evidence_path=root/RELEASE_EVIDENCE_FILENAME
        if resolved_evidence is None and evidence_path.exists():
            resolved_evidence=load_release_evidence(evidence_path)
        if resolved_evidence is not None:
            if not resolved_evidence.clean:
                raise ReleaseEvidenceMismatch("release evidence is not clean")
            if resolved_evidence.release_manifest_digest != manifest.digest():
                raise ReleaseEvidenceMismatch("release evidence does not bind the package manifest")
        manifest_bytes=canonical_bytes(manifest, indent=2)
        zip_path.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(zip_path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zf:
            for fd in manifest.files:
                data=(root/fd.path).read_bytes(); info=zipfile.ZipInfo(fd.path,self.NORMALIZED_DT); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=(0o644 & 0xFFFF)<<16; zf.writestr(info,data)
            info=zipfile.ZipInfo("RELEASE_MANIFEST.json",self.NORMALIZED_DT); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=(0o644 & 0xFFFF)<<16; zf.writestr(info,manifest_bytes)
            if resolved_evidence is not None:
                info=zipfile.ZipInfo(RELEASE_EVIDENCE_FILENAME,self.NORMALIZED_DT); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=(0o644 & 0xFFFF)<<16; zf.writestr(info,resolved_evidence.to_json_bytes())
        h=hashlib.sha256(zip_path.read_bytes()).hexdigest()
        return ReleasePackage(str(zip_path),h,manifest.digest(),len(manifest.files),resolved_evidence.digest() if resolved_evidence is not None else None)
