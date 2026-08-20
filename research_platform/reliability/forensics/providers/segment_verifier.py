from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from research_platform.reliability.forensics.providers.hashlog import HashChainError, HashChainedJSONL


@dataclass(frozen=True, slots=True)
class SegmentScanSummary:
    index: int
    rows: int
    bytes: int
    start_prev_hash: str
    end_hash: str
    filename: str


@dataclass(frozen=True, slots=True)
class SegmentScanResult:
    total_rows: int
    tail_hash: str
    summaries: tuple[SegmentScanSummary,...]


def segment_files(root: Path) -> tuple[Path,...]:
    return tuple(sorted(root.glob("[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].jsonl")))


def scan_segment_chain(root: Path) -> SegmentScanResult:
    """Pure verifier: reads authoritative segment bytes and never writes a manifest/index."""
    prev="0"*64; total=0; summaries=[]; files=segment_files(root)
    for expected_index,path in enumerate(files):
        if path.name!=f"{expected_index:08d}.jsonl":
            raise HashChainError(f"segment sequence gap: expected {expected_index:08d}.jsonl, found {path.name}")
        start_prev=prev; rows=0
        with path.open("r",encoding="utf-8") as fh:
            for lineno,line in enumerate(fh,1):
                if not line.strip(): continue
                try: row=json.loads(line)
                except json.JSONDecodeError as exc: raise HashChainError(f"segment {expected_index} line {lineno}: invalid/truncated JSON") from exc
                payload=row.get("payload")
                if not isinstance(payload,dict): raise HashChainError(f"segment {expected_index} line {lineno}: invalid payload")
                if row.get("prev_hash")!=prev: raise HashChainError(f"segment {expected_index} line {lineno}: previous hash mismatch")
                expected=HashChainedJSONL._hash(prev,payload)
                if row.get("row_hash")!=expected: raise HashChainError(f"segment {expected_index} line {lineno}: row hash mismatch")
                prev=expected; rows+=1; total+=1
        summaries.append(SegmentScanSummary(expected_index,rows,path.stat().st_size,start_prev,prev,path.name))
    return SegmentScanResult(total,prev,tuple(summaries))

def scan_segment_chain_payloads(
    root: Path,
    *,
    start_after: int = 0,
) -> tuple[SegmentScanResult, str, tuple[dict[str, object], ...]]:
    """Verify the global segmented chain and return payloads after a row checkpoint."""
    if start_after < 0:
        raise ValueError("start_after must be non-negative")
    prev = "0" * 64
    checkpoint = prev
    total = 0
    summaries: list[SegmentScanSummary] = []
    payloads: list[dict[str, object]] = []
    files = segment_files(root)
    for expected_index, path in enumerate(files):
        if path.name != f"{expected_index:08d}.jsonl":
            raise HashChainError(
                f"segment sequence gap: expected {expected_index:08d}.jsonl, found {path.name}"
            )
        start_prev = prev
        rows = 0
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise HashChainError(
                        f"segment {expected_index} line {lineno}: invalid/truncated JSON"
                    ) from exc
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    raise HashChainError(f"segment {expected_index} line {lineno}: invalid payload")
                if row.get("prev_hash") != prev:
                    raise HashChainError(
                        f"segment {expected_index} line {lineno}: previous hash mismatch"
                    )
                expected = HashChainedJSONL._hash(prev, payload)
                if row.get("row_hash") != expected:
                    raise HashChainError(f"segment {expected_index} line {lineno}: row hash mismatch")
                prev = expected
                rows += 1
                total += 1
                if total == start_after:
                    checkpoint = expected
                if total > start_after:
                    payloads.append(payload)
        summaries.append(
            SegmentScanSummary(expected_index, rows, path.stat().st_size, start_prev, prev, path.name)
        )
    if start_after > total:
        raise HashChainError(
            f"projection checkpoint rows={start_after} exceeds authoritative rows={total}"
        )
    if start_after == total:
        checkpoint = prev
    return SegmentScanResult(total, prev, tuple(summaries)), checkpoint, tuple(payloads)

