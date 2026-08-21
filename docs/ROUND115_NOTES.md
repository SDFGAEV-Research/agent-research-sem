# Round 115 - server/session runtime ownership migration

## Root cause

`execution/runtime/manager/persistent_session_host.py` owned the frozen
controller command and session-name derivation even though persistent session
identity belongs to `runtime/session`. Separately,
`platform/composition/runtime_control/server_runtime.py` owned immutable release
lookup, session policy validation and server bootstrap despite the declared
`runtime/server/lifecycle` node.

These were real ownership violations, not naming issues: callers imported the
old modules directly and the server bootstrap reached into a concrete session
runtime implementation.

## Structural change

- Moved `RuntimeControllerCommand` into `runtime/session/api`.
- Moved `RuntimePersistentSessionHost` into `runtime/session/runtime`.
- Added `PersistentSessionLaunchManifestPort` and
  `PersistentSessionHostPort`; server lifecycle receives only those narrow
  interfaces.
- Moved `ImmutableServerReleaseLayout`, `ServerRuntimeBootstrap`, launch
  report and policy errors into `runtime/server/lifecycle/runtime`.
- Rewired all production/test callers and physically deleted both old modules:
  `execution/runtime/manager/persistent_session_host.py` and
  `platform/composition/runtime_control/server_runtime.py`.
- Updated the server-session invariant to audit the new owner rather than the
  deleted path.

No compatibility module or re-export was retained.

## Verification

- 37 focused server/session/tmux/release tests passed;
- changed packages compiled successfully;
- architecture gate passed;
- no remote host, model, server or Minecraft process was started.
