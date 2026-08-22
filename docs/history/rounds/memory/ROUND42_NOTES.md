# Round 42 — Strict Canonical SEM State + Two-Phase Adoption

- Added one method-owned strict canonical serializer; `default=str` is removed from SEM scientific paths.
- Candidate compilation, materialization contracts, evidence digests, snapshot payloads and adoption digests now fail closed on unsupported/non-finite values.
- Split adoption into `AdoptionPreparer` and `AdoptionCommitter`.
- Any failure after generation allocation (including clean materialization/canonical digest construction) explicitly abandons the prepared generation.
- Architecture head and evolution ledger remain one atomic CAS batch; commit failure cannot leave an active half-adoption.
- Generation lifecycle is now thread-safe and externally observable through immutable snapshots.
