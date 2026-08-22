# Round 128 — profile-bound direct server command environment

Date: 2026-08-22

## Root cause

The server profile already declared the managed Node/Python/Java path, but that
environment was injected only into persistent operator sessions. A direct SSH
command still inherited the remote login shell's system `PATH`. Calling the
managed npm executable by absolute path therefore selected the system Node 12
through npm's `#!/usr/bin/env node` shebang, producing `Cannot find module
'node:path'` before dependency installation began.

This was a server-management ownership defect, not a project dependency
defect. Each caller should not have to reconstruct the server's toolchain
environment.

## Structural correction

Added `ProfileBoundServerConnection` under the server provider boundary and
composed it in the single server-management root. It binds every direct SSH
command and interactive command to the declared `ServerRemoteProfile`
environment (`HOME`, locale, `PATH` and `TERM`) through the declared remote
shell. The original command remains the caller-visible command and operation
evidence identity; the wrapper does not select fallback executables.

Persistent tmux sessions and direct commands now consume the same profile
environment contract.

## Server evidence

- The failed npm mutation was independently inspected and reconciled as
  `effect_not_applied` before retry.
- The corrected Node 22 PATH was verified on the Ubuntu host.
- Locked Minecraft bridge dependency installation completed: **92 packages
  added**.
- New profile-bound connection regression: **6 passed**.
- Complete server control-plane regression: **82 passed + 4 subtests**.
- Server architecture gate: **`ARCHITECTURE_GATE_PASS`**.
- No model service or Minecraft experiment was started by this repair.

## Remaining Paper-1 gate

The Qwen3.6-35B-A3B asset is still downloading and is not registered. The
model-backed baseline remains blocked until its complete artifact closure,
registration and endpoint health are independently verified.
