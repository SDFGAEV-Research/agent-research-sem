# Round 111 — pinned J_mem to live Deluxe projection

## Root cause

The Deluxe provider and typed materializer already existed, but the real SEM
session could only use Deluxe when a caller manually supplied a prebuilt
`TypedMaterializedGeneration`. That left the production composition path
without a read-side projection from the session's current evidence cut.

## Structural change

`EvidenceMaterializationSource` is now a read-only seam exposing exactly
`snapshot()` and `read_view()`. The mutable `J_mem` store still implements it,
but typed materialization no longer requires a mutable store.

`PinnedEvidenceMaterializationSource` adapts one `EvidenceReadPort` cut without
copying or reopening the mutable store. `LiveTypedDeluxeSnapshotSource` then:

1. obtains the session generation and pinned `J_mem` read view atomically;
2. materializes typed node records through the injected `TypedNodeBuilderPort`;
3. validates the architecture and node payloads;
4. publishes an ephemeral `NodePartitionedDeluxeSnapshot` for serving only.

`build_live_typed_snapshot_factory` makes this path available to the real SEM
session assembly. The projection is never written back and never becomes a
second evidence authority.

## Traceability invariant

Every typed Deluxe record must carry non-empty `source_refs`. During live
materialization, every reference must point to either the pinned `J_mem`
evidence cut or another record in the same typed generation. Unknown and
untraceable records fail with `TypedMaterializationError`; they are not
filtered or silently replaced.

## Verification

- Deluxe projection, adoption, session composition, project firewall and
  architecture tests: **74 passed**;
- changed SEM modules compile successfully;
- no new platform authority or legacy import was introduced;
- the first projected snapshot remains unchanged after later `J_mem` writes,
  while a newly opened snapshot observes the later cut;
- no Minecraft server, model, or scientific experiment was run.

This closes the pinned read-side D2 seam. It does not yet claim the complete
Deluxe research treatment: the project still needs a production architecture
configuration and typed semantic builder, Deluxe evolution/identifiability/
candidate evaluation, evidence bundle governance, and the staged MC execution
ladder.
