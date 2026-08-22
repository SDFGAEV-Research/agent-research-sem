# Round 120 — Minecraft username protocol contract

## Root cause

The third remote Minecraft scripted smoke reached world-cut, branch
materialization and RCON readiness, then failed while opening the Mineflayer
workload. The server rejected the bridge login because the default username
`ResearchPlatformBot` has 19 characters, while the Minecraft protocol allows
at most 16 characters.

This was a contract defect: the platform accepted an invalid agent identity
and allowed the failure to occur remotely during the bridge handshake.

## Change

- `MinecraftAgentSpec` now validates usernames against the protocol-compatible
  language `[A-Za-z0-9_]{3,16}` before provider composition.
- The platform and Mineflayer bridge default is now `ResearchBot`.
- The invalid historical default is covered by a focused regression test.

The validation is fail-closed. It does not truncate, rewrite, retry with a
different identity, or otherwise weaken the server contract.

## Verification target

Run the focused Minecraft environment tests locally, then repeat the remote
scripted smoke with the exact same infrastructure inputs and the corrected
identity. A passing smoke demonstrates only that the server/bridge execution
path is healthy; it is not a scientific result.
