# Server Connection Contract

The platform server layer models a remote host as an explicit `server_id` plus a complete connection/runtime profile. It does not ship with a fleet catalogue.

A deployment or downstream project selects its own server IDs and provides profile values outside the reusable source tree. The platform parses and validates those values; it does not guess hostnames, users, ports, paths, toolchains, or credentials.

## Profile naming

For a server ID such as `server-a`, the environment prefix is derived mechanically as `RP_SERVER_SERVER_A_...`. Fleet membership is explicit through `RP_SERVER_CATALOG_IDS`.

The checked-in example [`../../../configs/server_profiles/server.example.env`](../../../configs/server_profiles/server.example.env) documents the supported fields without selecting any real machine.

## Authentication

Prefer an SSH key or agent for unattended operations. Passwords and private keys are never committed. Local SSH configuration and control-socket paths remain operator-local.
## Runtime and path identity

Remote filesystem roots, interpreter/toolchain paths, session configuration, and repository roots are part of the deployment profile because they affect reproducibility and mutation safety. A downstream deployment may pin executable digests when exact toolchain attestation is required.

Command execution, file transfer, repository operations, and persistent sessions have independent timeout/budget controls. Server operations are journaled with typed observation/mutation intent so retries do not silently duplicate uncertain external effects.

## Durable operation lifecycle

Managed SSH/SCP effects are recorded in an append-only server-operation ledger. Each operation id has one legal durable lifecycle:

```text
STARTED -> FINISHED
   |
   +------> RESOLVED   (only while the external effect is uncertain)
```

`record_started`, `record_finished`, and `record_resolved` are transition-safe writes. A per-operation interprocess transition lock fences concurrent controllers before they inspect the current record and append the next event. A duplicate finish, duplicate resolution, finish after reconciliation, or profile/request/effect identity drift raises `ServerOperationTransitionConflict` **before** the ledger is modified. The short global append lock remains responsible only for byte ordering and fsync, so unrelated operation ids do not share a long lifecycle lock.

Replay independently revalidates the same state machine. Corrupt or externally edited records fail closed with `ServerOperationJournalIntegrityError`; replay is not used as permission for a writer to append an illegal transition. A resolution proves only the disposition of a previously uncertain server operation. It is not scientific evidence and does not authorize a blind retry.

The JSONL ledger is the Runtime operation-history authority, not current remote process truth. Live state must be reconciled through the server/process runtime ports. Reliability effect/reconciliation contracts remain a cross-system seam and must not be duplicated by adding a second generic effect authority inside Runtime.

## Repository boundary

Concrete machine inventories and their current state belong in the downstream deployment repository or an ignored operator inventory. They must not be added to this upstream document, the generic README, or the platform release manifest.
