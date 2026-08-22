# Round 40 — SEM Session Authority and Exact Method Recovery

Round 40 moves Self-Evolving Memory session ownership out of the plugin façade and makes the method's own recovery closure exact.

## Changes

- `plugin.py` is now composition only; lifecycle/state mutation moved to `session.py`.
- Pure immutable state transitions live in `session_reducer.py`.
- Snapshot schema is latest-only **v3** and method implementation is **0.23.0**; no legacy migration path is retained.
- The opaque method snapshot now contains both SEM runtime state and the canonical `J_mem` evidence cut.
- `J_mem` restoration rebuilds and re-verifies every evidence digest plus the aggregate snapshot digest before live-state swap.
- JSON checkpoint encoding is strict and lossless for supported data; `default=str` coercion is removed.
- Session mutation is serialized with one method-owned lock; 32-way concurrent ingest is regression tested for contiguous sequence assignment.
- Failed ingest/restore is zero-state-change: the live session is swapped only after full validation succeeds.

## Debugging impact

A checkpoint now proves the exact method state that was resumed, including the canonical memory evidence digest. If the state/evidence sequence or any nested evidence digest diverges, restore fails before the live session changes.
