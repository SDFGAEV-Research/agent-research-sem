from __future__ import annotations

import json
from pathlib import Path

from research_platform.reliability.forensics.providers.hashchain_core import ZERO_HASH, hash_payload


class HashChainError(RuntimeError):
    pass


def scan_hash_chain(path:Path)->tuple[int,str]:
    prev=ZERO_HASH
    count=0
    if not path.exists():
        return count,prev
    with path.open("r",encoding="utf-8") as fh:
        for lineno,line in enumerate(fh,1):
            if not line.strip():
                continue
            try:
                row=json.loads(line)
            except json.JSONDecodeError as exc:
                raise HashChainError(f"line {lineno}: invalid/truncated JSON") from exc
            payload=row.get("payload")
            if not isinstance(payload,dict):
                raise HashChainError(f"line {lineno}: invalid payload")
            if row.get("prev_hash")!=prev:
                raise HashChainError(f"line {lineno}: previous hash mismatch")
            expected=hash_payload(prev,payload)
            if row.get("row_hash")!=expected:
                raise HashChainError(f"line {lineno}: row hash mismatch")
            prev=expected
            count+=1
    return count,prev


def scan_hash_chain_payloads(
    path: Path,
    *,
    start_after: int = 0,
) -> tuple[int, str, str, tuple[dict[str, object], ...]]:
    """Verify the whole chain and return payloads strictly after `start_after`.

    The returned checkpoint hash is the row hash at `start_after` (ZERO_HASH for 0),
    allowing disposable projections to detect that their previously projected prefix
    still belongs to the same authoritative chain.
    """
    if start_after < 0:
        raise ValueError("start_after must be non-negative")
    prev=ZERO_HASH
    checkpoint=ZERO_HASH
    count=0
    payloads:list[dict[str,object]]=[]
    if not path.exists():
        if start_after:
            raise HashChainError("projection checkpoint exceeds missing ledger")
        return 0,prev,checkpoint,()
    with path.open("r",encoding="utf-8") as fh:
        for lineno,line in enumerate(fh,1):
            if not line.strip():
                continue
            try:
                row=json.loads(line)
            except json.JSONDecodeError as exc:
                raise HashChainError(f"line {lineno}: invalid/truncated JSON") from exc
            payload=row.get("payload")
            if not isinstance(payload,dict):
                raise HashChainError(f"line {lineno}: invalid payload")
            if row.get("prev_hash")!=prev:
                raise HashChainError(f"line {lineno}: previous hash mismatch")
            expected=hash_payload(prev,payload)
            if row.get("row_hash")!=expected:
                raise HashChainError(f"line {lineno}: row hash mismatch")
            prev=expected; count+=1
            if count==start_after:
                checkpoint=expected
            if count>start_after:
                payloads.append(payload)
    if start_after>count:
        raise HashChainError(
            f"projection checkpoint rows={start_after} exceeds authoritative rows={count}"
        )
    if start_after==count:
        checkpoint=prev
    return count,prev,checkpoint,tuple(payloads)
