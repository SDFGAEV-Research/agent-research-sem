# Round 119 - Minecraft readiness includes RCON control-plane readiness

Date: 2026-08-21

## Root cause found on Ubuntu

After the world-copy capability fix, the next scripted smoke showed that the
vanilla server's game TCP port became reachable before its RCON listener was
accepting connections. The old readiness contract stopped at TCP readiness and
immediately entered the save barrier; `save-off` therefore failed with
`RCON_CONNECT_FAILED` and the recovery `save-on` failed for the same reason.

## Structural fix

`MinecraftServerReadinessProbe` now composes the existing TCP readiness probe
with a read-only RCON `list` command whenever the server specification enables
RCON. The generic service lifecycle is not changed. A service is reported ready
only after both endpoint facts are verified, and the readiness evidence binds
the TCP and RCON evidence references together. RCON connection refusal during
startup is retained as the latest diagnostic and retried within the declared
readiness window; authentication/protocol failures are never converted into a
false ready state.

Servers without RCON retain the original TCP-only contract. The source MC
server used by world-cut experiments necessarily has RCON, so this closes the
actual failing path rather than adding a paper-specific sleep.

## Verification

- Local MC server-factory, readiness, environment, world-cut and host tests:
  **29 passed**.
- Python compilation of the readiness composition and test: **PASS**.
- The second remote smoke failure is preserved as evidence of the old readiness
  gap; it is not counted as a scientific result.
