# Round 41 — SEM Session State Cell

- Replaced distributed session mutation (`_state`, `_evidence`, `_closed`, `_lock`) with one `SEMSessionStateCell` authority.
- Every successful live mutation advances a monotonic revision and records a `SessionMutationReceipt`.
- Ingest performs all fallible validation/reducer work before canonical `J_mem` append.
- Restore rebuilds and verifies the complete evidence store outside the live-state critical section, then performs one state swap.
- `SEMSession` is now a thin façade; session authority is isolated for future telemetry/forensics integration.
- No compatibility mode or fallback path was added.
