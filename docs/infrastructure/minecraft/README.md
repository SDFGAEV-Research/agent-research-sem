# Minecraft Infrastructure Documents

This directory owns reusable Minecraft environment concerns such as source
server readiness, world cuts, branch runtime and environment-system audits.
Paper methods consume these capabilities through composition ports.

- `MC_ACTION_CAPABILITY_SYSTEM.md` documents the typed Mineflayer action ABI.
- `MC_RUNTIME_BOOTSTRAP_AND_SCENARIOS.md` documents verified server acquisition,
  deterministic source-world provisioning and the live scripted-smoke route.
- Current live status and upstream-version evidence are recorded in [`../../status/CURRENT_EXECUTION_STATUS_20260828.md`](../../status/CURRENT_EXECUTION_STATUS_20260828.md).

Minecraft provider changes must follow the exact-version GitHub source audit in [`../../governance/DOCUMENTATION_CHANGE_POLICY.md`](../../governance/DOCUMENTATION_CHANGE_POLICY.md); do not infer protocol/pathfinder/entity behavior when the locked upstream source can establish it.
