from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from research_platform.platform.kernel.durability.durable_file import atomic_replace_bytes

from research_platform.runtime.process.api import ByteSegment, CaptureIntegrityError, CaptureManifest


class CaptureStorage:
    """Pure filesystem projection for segmented process capture."""

    def __init__(self,root:Path,stream:str)->None:
        self.root=root; self.stream=stream; root.mkdir(parents=True,exist_ok=True)
        self.manifest_path=root/f"{stream}.manifest.json"

    def path(self,index:int)->Path:
        return self.root/f"{self.stream}.{index:06d}.bin"

    def files(self)->tuple[Path,...]:
        return tuple(sorted(self.root.glob(f"{self.stream}.[0-9][0-9][0-9][0-9][0-9][0-9].bin")))

    def scan_segments(self)->tuple[ByteSegment,...]:
        out=[]; offset=0
        for i,p in enumerate(self.files()):
            if p.name!=self.path(i).name:
                raise CaptureIntegrityError(f"segment sequence gap at {i}")
            h=hashlib.sha256(); size=0
            with p.open("rb",buffering=1024*1024) as fh:
                while chunk:=fh.read(1024*1024):
                    h.update(chunk); size+=len(chunk)
            out.append(ByteSegment(i,p.name,offset,offset+size,size,h.hexdigest()))
            offset+=size
        return tuple(out)

    def build_manifest(self,segments:tuple[ByteSegment,...],sealed:bool)->CaptureManifest:
        total=sum(x.size for x in segments)
        base={
            "schema_version":1,
            "stream":self.stream,
            "total_bytes":total,
            "segments":[asdict(x) for x in segments],
            "sealed":sealed,
        }
        digest=hashlib.sha256(
            json.dumps(base,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        ).hexdigest()
        return CaptureManifest(1,self.stream,total,segments,sealed,digest)

    def write_manifest(self,manifest:CaptureManifest)->None:
        raw=json.dumps(asdict(manifest),sort_keys=True,ensure_ascii=False,indent=2).encode()
        atomic_replace_bytes(self.manifest_path, raw)

    def verify_manifest(self)->CaptureManifest:
        segments=self.scan_segments()
        actual=self.build_manifest(segments,self.manifest_path.exists())
        if not self.manifest_path.exists():
            return actual
        stored=json.loads(self.manifest_path.read_text(encoding="utf-8"))
        expected=tuple(ByteSegment(**x) for x in stored["segments"])
        if expected!=segments or stored["total_bytes"]!=actual.total_bytes or not stored.get("sealed"):
            raise CaptureIntegrityError("sealed capture segment digest/size mismatch")
        if actual.manifest_sha256!=stored.get("manifest_sha256"):
            raise CaptureIntegrityError("capture manifest digest mismatch")
        return actual

    def total_size(self)->int:
        return sum(p.stat().st_size for p in self.files())

    def active_size(self)->int:
        files=self.files()
        return files[-1].stat().st_size if files else 0

    def read_range_unverified(self,offset:int,length:int)->bytes:
        """Read a bounded byte range without manifest verification.

        Algorithm-Complexity: O(N)
        Algorithm-Rationale: N is segment metadata visited plus requested bytes consumed; inner readinto calls partition the requested range and therefore sum rather than multiply across segments.
        """
        if offset < 0 or length < 0:
            raise ValueError("offset and length must be non-negative")
        if length == 0:
            return b""

        # Snapshot segment sizes once so the output buffer is exactly bounded by
        # available capture data.  This avoids the old list-of-chunks + join
        # double residency while also avoiding an attacker-sized allocation when
        # ``length`` extends past EOF.
        segments: list[tuple[Path, int, int, int]] = []
        cursor = 0
        for path in self.files():
            size = path.stat().st_size
            segments.append((path, size, cursor, cursor + size))
            cursor += size
        available = max(0, min(length, cursor - offset))
        if available == 0:
            return b""

        target_end = offset + available
        buffer = bytearray(available)
        written = 0
        for path, _size, seg_start, seg_end in segments:
            if seg_end <= offset or seg_start >= target_end:
                continue
            local_start = max(offset, seg_start) - seg_start
            local_end = min(target_end, seg_end) - seg_start
            wanted = local_end - local_start
            with path.open("rb", buffering=1024 * 1024) as handle:
                handle.seek(local_start)
                view = memoryview(buffer)[written : written + wanted]
                consumed = 0
                while consumed < wanted:
                    count = handle.readinto(view[consumed:])
                    if not count:
                        break
                    consumed += count
                written += consumed
                if consumed != wanted:
                    # The unverified API permits concurrent files, but it must not
                    # expose zero-filled bytes when a segment is truncated mid-read.
                    return bytes(buffer[:written])
        return bytes(buffer[:written])

    def load_tail(self,total:int,limit:int)->bytes:
        remaining=min(total,limit)
        return self.read_range_unverified(total-remaining,remaining) if remaining else b""
