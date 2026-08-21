# Managed server connections

This document defines the non-secret server-management contract. SSH identity,
remote runtime layout and persistent operator-session transport are separate
profiles composed by the platform. No project may construct SSH/tmux/scp
arguments, guess a remote path or keep a second server registry.

## `sem-ubuntu`

| Field | Verified value |
|---|---|
| Logical server ID | `sem-ubuntu` |
| OS | Ubuntu 22.04.5 LTS |
| Kernel | Linux 6.8.0-136-generic |
| CPU / RAM | 256 logical CPUs / 503 GiB |
| Storage | `/` 917 GB (about 843 GB free); `/data` 102 TB (about 92 TB free) |
| SSH endpoint | port `60320`, user `ubuntu` |
| Platform root | `/data/research-platform` |
| Managed Python | `/data/research-platform/envs/sem-paper/bin/python` |
| Managed Node | `/data/research-platform/toolchains/node-v22.22.2-linux-x64/bin/node` |
| Managed Java | `/data/ubuntu/cef-hicc-multiserver-D/runtime/jre-21.0.8/bin/java` |
| Managed tmux | `/usr/local/bin/tmux`, version `3.0a` |
| tmux binary digest | `b079dbc82b2ca2544caa7f84d7a618e2be3990c45f4f4c51e43a24348f393bdd` |

The inventory was verified by the server-health route and read-only remote
inspection on 2026-08-21. The values above are operational facts, not
credentials. If a toolchain is moved, update the profile and re-run health
before using it; do not silently fall back to a system executable.

## Environment binding

Copy `configs/server_profiles/sem-ubuntu.example.env` to an ignored local
profile. The profile has two explicit
parts:

1. `HOST`, `PORT`, `USER`, key/known-hosts/config and SSH/scp executable
   variables: connection identity only.
2. `PLATFORM_ROOT`, `RELEASE_ROOT`, `OPERATOR_CWD`, remote executable paths,
   the attested tmux digest, session name, remote `HOME/PATH`, and the local
   binding directory: remote lifecycle identity only.

Passwords are not accepted by the platform and are never stored in files,
bindings, command arguments or logs. An interactive OpenSSH prompt is allowed
only when the command is explicitly given `--interactive`; unattended work
requires a key or SSH agent. The three operational entry points accept the
same profile directly, so a caller no longer needs to reproduce a long list of
`export` statements:

```bash
PROFILE=configs/server_profiles/sem-ubuntu.local.env
python scripts/server_health.py sem-ubuntu --profile-file "$PROFILE" --interactive
python scripts/server_session.py ensure sem-ubuntu --profile-file "$PROFILE" --interactive
python scripts/server_session.py status sem-ubuntu --profile-file "$PROFILE" --interactive
python scripts/server_release_publish.py sem-ubuntu release.zip --profile-file "$PROFILE" --interactive
```

`RP_SERVER_PROFILE_FILE` may be used instead of repeating `--profile-file`.
The loader is a literal `KEY=value` parser: it performs no shell expansion,
rejects duplicate keys and removes inherited `RP_SERVER_*` values before
loading the file. Thus a missing or changed field fails at profile material-
ization instead of being silently filled by stale process state.

## Persistent operator session

```bash
python scripts/server_session.py ensure sem-ubuntu --interactive
python scripts/server_session.py status sem-ubuntu --interactive
python scripts/server_session.py attach sem-ubuntu
python scripts/server_session.py terminate sem-ubuntu --interactive
```

The command is only a thin composition entry point. The actual behavior is:

1. compose the SSH identity from `runtime/server/identity`;
2. materialize the remote lifecycle profile from environment;
3. read-only attest the exact remote tmux binary SHA-256;
4. run the generic `runtime/session` tmux codec through the SSH command port;
5. persist a checksummed local binding for session name, cwd, command,
   environment, release identity and transport identity;
6. reconcile the remote session using `PersistentSessionManager`.

`ensure` is idempotent only for an exact binding. A reused session with a
different command, cwd, environment, tmux server label, config or binary
identity is reported as drift and is not overwritten. `status` is read-only;
`attach` forces a TTY and attaches to the attested remote tmux server;
`terminate` refuses to kill an unbound or drifted session. The shell survives
an SSH disconnect, but it is only an operator controller and is not evidence
that a model, Minecraft server or scientific run is healthy.

The optional `SSH_CONTROL_PATH` profile field enables OpenSSH
`ControlMaster=auto`/`ControlPersist` reuse for all SSH and scp operations of
one server profile. This removes repeated authentication prompts inside one
health/session/release operation while keeping the password outside the
platform. The path is local to the controller and must be short enough for
OpenSSH's 108-byte Unix socket limit after `%C` expansion; profile loading
rejects an oversized or unsupported template before any network action.

## Release and health operations

Release publication takes its target root from the same lifecycle profile:

```bash
python scripts/server_release_publish.py sem-ubuntu release.zip --interactive
```

An explicit positional release root is still available for a deliberate
one-off target, but the managed path is the profile authority. Health checks
must be expanded with the same managed paths and exact toolchain identities;
the old `python3/git/tmux/df` probe is only a connectivity smoke check and
must not be interpreted as platform readiness.

The local Windows OpenSSH permission issue was repaired by removing the stale
`UNKNOWN` SID from `C:\Users\25676\.ssh\config` while preserving the owner,
current-user, SYSTEM and Administrators access. On another machine, use an
explicit readable SSH config path; do not use the Windows device name `NUL`.

## Server management control plane

All health, persistent-session and release entry points now compose one
`runtime/server` binding from the same profile mapping. The binding computes a
profile digest over the non-secret connection and remote-runtime projections,
then injects the resulting connection and file-transfer ports into the leaf
systems. A script must not independently materialize an SSH profile and a
remote lifecycle profile: doing so can connect to one identity while operating
on another runtime layout.

Every SSH command and SCP upload emits two records to the controller-local
`<LOCAL_BINDING_ROOT>/server-operations.jsonl`: `started` and `finished`. The
record contains an operation ID, server ID, profile/request digests,
timestamps, duration, return code, transport-failure class, output sizes and
output digests. It never stores passwords or raw remote command text. The
append is fsync-backed and uses the platform's cross-platform interprocess
lock. Interactive attach
is also journaled; only the identity provider can execute its TTY argv. A
missing operation ledger is a composition failure, so an unobserved side
effect is not silently allowed.

The ledger is replayable through the read-only operation command:

```bash
python scripts/server_operations.py sem-ubuntu --profile-file "$PROFILE"
```

An operation with `started` but no `finished` record is returned as
`effect_uncertain=true` and makes the command exit with status `1`. This is a
reconciliation signal, not a retry queue: inspect the owning remote effect
first, then intentionally submit or retire the operation. A malformed ledger
fails closed with a typed integrity error rather than being partially read.

The transport profile bounds command duration with
`SSH_COMMAND_TIMEOUT_SECONDS` (default 120 seconds) and bounds retained
stdout/stderr at `SSH_OUTPUT_LIMIT_BYTES` (default 8 MiB). Timeout,
authentication failure, network failure, remote non-zero exit and local
process-spawn failure are distinct result classes; they must be diagnosed from
the structured result and operation ledger rather than collapsed into a
generic SSH error. Interactive mode requests a real TTY so password and
host-key prompts are not attempted through a pipe. A timeout or interrupted
mutating operation still requires reconciliation before retrying.

When a session operation reports `binding_drift`, compare the exact profile
file used by both commands. Do not hand-edit or bypass the binding check: a
different remote HOME, PATH, shell arguments, release root, or transport
identity is a different frozen controller and must be intentionally rebound
under a new session name/profile.

Release finalization uses the exact `RP_SERVER_<ID>_PYTHON` executable from the
same composed remote profile. It never silently invokes a system `python3`
outside the managed environment.
