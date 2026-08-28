# Round 113 - server health ownership cutover

## Root cause

The `runtime/server/identity` node was declared as the owner of stable server
identity and deployment attachment, but its connection port also exposed a
live health operation and its API owned `ServerHealthReport`. That made health
semantics part of the identity provider and prevented the declared
`runtime/server/health` node from becoming a real implementation.

## Structural change

`ServerConnectionPort` now contains only the server profile and remote command
execution. `ServerHealthReport`, `ServerHealthProbePort` and
`SSHServerHealthProbe` are physically owned by `runtime/server/health`.
`scripts/server_health.py` composes both nodes explicitly and passes the
identity connection into the health probe.

The health provider owns parsing of health facts, while the identity provider
owns only OpenSSH argument construction and command execution. No health
storage, global service locator, fallback connection or compatibility alias
was added.

## Verification

- 8 focused server/path tests passed;
- 38 server/MC/runtime tests passed;
- changed runtime and script modules compiled successfully;
- architecture gate passed;
- no remote host, model, server or Minecraft process was started.
