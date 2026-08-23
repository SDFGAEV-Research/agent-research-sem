# Minecraft Infrastructure Documents

This directory owns reusable Minecraft environment concerns such as source
server readiness, world cuts, branch runtime and environment-system audits.
Paper methods consume these capabilities through composition ports.

- `MC_ACTION_CAPABILITY_SYSTEM.md` documents the typed Mineflayer action ABI.
- `MC_RUNTIME_BOOTSTRAP_AND_SCENARIOS.md` documents verified server acquisition,
  deterministic source-world provisioning and the live scripted-smoke route.
