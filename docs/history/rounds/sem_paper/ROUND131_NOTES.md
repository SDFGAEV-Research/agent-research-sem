# Round 131 — bridge dependency boundary

## Scope

Close the environment-boundary gap that would otherwise make installing the
pinned Mineflayer bridge dependencies contaminate the exact server checkout.

## Structural correction

The bridge now declares `node_modules/` as runtime-only environment state in
its local `.gitignore`. `package.json`, `package-lock.json` and `bridge.js`
remain tracked authorities. The source repository clean/exact gate therefore
continues to cover all source and dependency-lock changes while allowing the
server-owned Node dependency tree to be materialized in the bridge runtime.

Installation is performed through the existing profile-bound persistent
server repository command; no ad-hoc SSH or temporary installation script is
introduced.

## Verification

- The managed Ubuntu profile resolved the pinned Node toolchain's npm as
  `10.9.7` through `scripts/server_repository_command.py`.
- The command ran at the exact server revision `976c7951eea76a04c71af27c333015f4b1d641aa`.
- The operation was non-interactive and recorded in the server operation
  ledger; no pending operation was present before the check.
- Dependency installation and live T2B execution remain pending until this
  tracked boundary change is published and synchronized.
