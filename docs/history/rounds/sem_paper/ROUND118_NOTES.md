# Round 118 - explicit Minecraft world-copy capability handling

Date: 2026-08-21

## Root cause found on Ubuntu

The first remote `scripted-smoke` reached Minecraft startup, TCP readiness,
RCON and the save barrier, then failed while capturing the source world. The
failure was caused by the MC host unconditionally selecting
`cp --reflink=always`; the server's `/data` filesystem returns `Operation not
supported` for reflink cloning. This was an infrastructure capability
mismatch, not an MC protocol, RCON or Mineflayer failure.

## Structural fix

`ReflinkMinecraftWorldCopier` remains strict by default and never silently
falls back. It now accepts an explicitly injected fallback copier and an
isolated reporter. The SEM experiment composition injects the regular
filesystem copier only as an intentional capability fallback and emits
`WORLD_COPY_COPIER_FALLBACK` with the original reflink error. Any other copy
failure still fails closed; a fallback failure is reported as
`REFLINK_FALLBACK_FAILED`.

`MinecraftBranchExecutionError` now includes the underlying cause and cleanup
cause in its message, so a top-level run result preserves the actionable
failure code instead of only saying that branch capture failed.

## Verification

- Local world-cut, branch-runner and MC-host tests: **14 passed**.
- Python compilation of the changed copier, branch runner and entrypoint:
  **PASS**.
- Remote diagnostic copy reproduced the exact `/data` reflink capability
  error without modifying the failed run.
- The failed remote run remains recorded as infrastructure failure and is not
  counted as a scientific result; it must be rerun after deploying this fix.
