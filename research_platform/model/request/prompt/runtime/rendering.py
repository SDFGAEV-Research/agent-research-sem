from __future__ import annotations

from dataclasses import dataclass
import hashlib

from .blocks import PromptBlock
from .runtime_contracts import ActivePromptBundle


@dataclass(frozen=True, slots=True)
class PromptBlockStat:
    kind: str
    chars: int
    bytes: int
    source_digest: str


@dataclass(frozen=True, slots=True)
class PromptRenderResult:
    text: str
    dynamic_digest: str
    block_kinds: tuple[str, ...]
    block_stats: tuple[PromptBlockStat, ...]
    compiled_chars: int
    compiled_bytes: int


class PromptRenderer:
    """Pure deterministic renderer over already-validated ordered blocks."""

    def render(
        self,
        bundle: ActivePromptBundle,
        ordered_blocks: tuple[PromptBlock, ...],
    ) -> PromptRenderResult:
        parts = [bundle.text.rstrip()]
        digest = hashlib.sha256()
        stats: list[PromptBlockStat] = []
        for block in ordered_blocks:
            header = f"[{block.kind.value}]"
            parts.append(f"{header}\n{block.content.strip()}")
            digest.update(block.kind.value.encode())
            digest.update(b"\0")
            digest.update(block.source_digest.encode())
            digest.update(b"\0")
            encoded = block.content.encode("utf-8")
            digest.update(encoded)
            stats.append(
                PromptBlockStat(
                    block.kind.value,
                    len(block.content),
                    len(encoded),
                    block.source_digest,
                )
            )
        text = "\n\n".join(parts) + "\n"
        return PromptRenderResult(
            text=text,
            dynamic_digest=digest.hexdigest(),
            block_kinds=tuple(block.kind.value for block in ordered_blocks),
            block_stats=tuple(stats),
            compiled_chars=len(text),
            compiled_bytes=len(text.encode("utf-8")),
        )
