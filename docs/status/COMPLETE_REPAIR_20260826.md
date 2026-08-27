# Complete repair checkpoint — 2026-08-26

This checkpoint records the source-level repairs completed in the current
development tree. It is not a substitute for qualified external live evidence.

## Closed in source

- Production SEM composition roots now use `build_durable_platform_meta()`.
- Scope hierarchy, resource ownership/leases, and endpoint allocations use one
  SQLite authority with WAL, `synchronous=FULL`, transactional fencing, and
  restart-safe reads.
- Endpoint records are persisted separately from the lease port while sharing
  the same database and lease authority.
- Linux-first Docker Compose, Java 21, Python 3.12, Node 22, Mineflayer lockfile
  installation, Mojang SHA-1 server download, persistent volumes, and WSL2
  workspace-daemon bootstrap are versioned in the repository.
- Release manifest/evidence was regenerated from the current tree: 1135 tests,
  1135 passed, 0 skipped, 10 isolated shards.

## Still intentionally fail-closed

`LIVE_EXECUTION_EVIDENCE` remains open until a qualified deployment closure and
live T2B evidence are present in the current checkout. No scientific result is
claimed from the source-level regression alone.
