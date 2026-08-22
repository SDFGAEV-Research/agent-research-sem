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

These controller entry points require Python 3.11 or newer because the server
control-plane contracts use the platform's typed runtime APIs. The controller
Python is separate from the remote managed Python in the profile. Do not run
the scripts through an older system `python`; use the project's managed
controller environment and treat `ControllerPythonVersionError` as a local
environment defect, not as an SSH or remote-runtime failure.

Copy `configs/server_profiles/sem-ubuntu.example.env` to an ignored local
profile. The profile begins with an explicit `RP_SERVER_CATALOG_IDS` list and
then has two per-server
parts:

1. `HOST`, `PORT`, `USER`, key/known-hosts/config and SSH/scp executable
   variables: connection identity only.
2. `PLATFORM_ROOT`, `RELEASE_ROOT`, `OPERATOR_CWD`, remote executable paths,
   the attested Python/Node/Java/platform-management binary digests, the
   sorted `pip freeze --all` digest, session name, remote `HOME/PATH`, and the
   local binding directory: remote lifecycle identity only.

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

The catalog is the only profile membership and profile-schema authority. `list`
is local and secret-free; it rejects duplicate ids, undeclared
`RP_SERVER_<ID>_*` namespaces and missing connection fields before any network
action. It also reports every missing remote-runtime/session/local-state field
consumed by the composed server system, so a malformed profile is diagnosed in
one pass rather than one `ServerRemoteProfile` exception at a time:

```bash
python scripts/server_doctor.py list --profile-file "$PROFILE"
```

The projection separates `missing_identity_fields` (`HOST`, `PORT`, `USER`)
from `missing_runtime_fields` (remote paths, attested toolchains, tmux/session
identity and the controller-local binding root). `composition_ready` is true
only when both sets are empty. The catalog still does not claim that a remote
path exists or that a digest matches; those remain health observations.

For a complete read-only diagnosis use the joined doctor entry rather than
manually correlating three command outputs:

```bash
python scripts/server_doctor.py inspect sem-ubuntu --profile-file "$PROFILE"
```

The output carries one profile digest, remote health checks, pending and recent
operation evidence, and the current profile-bound operator-session state.
`ready_for_mutation` is true only when the remote managed runtime is ready and
the operation ledger has no uncertain effect. The doctor never retries,
resolves, or mutates anything.

Configured local identity files are also checked at profile materialization:
`KEY_PATH`, `KNOWN_HOSTS` and `SSH_CONFIG`, when present, must be absolute,
readable regular files. A relative path, stale mount, Windows device name or
unreadable ACL fails locally before OpenSSH is spawned; it is not reported as a
remote authentication or network failure.

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
identity is reported as drift and is not overwritten. `status` is read-only and
compares the current profile-bound session spec with the durable binding;
`attach` first proves that binding and the live controller snapshot, then
forces a TTY and attaches to the attested remote tmux server;
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

Release publication has no ad-hoc positional remote-root override. The
`RELEASE_ROOT` field in the composed server profile is the only release-path
authority; this prevents a publisher from uploading code to a path that health,
session binding and recovery do not govern. Health checks must be expanded with
the same managed paths and exact toolchain identities;
the old `python3/git/tmux/df` probe is only a connectivity smoke check and
must not be interpreted as platform readiness.

Release upload is also transactional at the remote path level. SCP writes only
`incoming/<digest>.zip.part`; the authoritative `<digest>.zip` is never the
direct SCP target. Finalization verifies the digest, extracts into a unique
temporary directory under `releases`, validates the release manifest/evidence,
then atomically renames that directory to `releases/<digest>`. A failed upload
or finalization therefore cannot turn a partial archive or a fixed stale
staging directory into a release-path conflict on the next reconciled attempt.

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

Every SSH command and SCP upload/download emits two records to the controller-local
`<LOCAL_BINDING_ROOT>/server-operations.jsonl`: `started` and `finished`. The
record contains an operation ID, server ID, profile/request digests,
timestamps, duration, return code, transport-failure class, output sizes and
output digests, and short platform-redacted stdout/stderr previews. It never
stores passwords or raw remote command text. The
append is fsync-backed and uses the platform's cross-platform interprocess
lock. Interactive attach
is also journaled; only the identity provider can execute its TTY argv. A
missing operation ledger is a composition failure, so an unobserved side
effect is not silently allowed.

The observed file-transfer port supports downloading an absolute remote POSIX
file to an absolute local target. Downloads use the same profile, timeout,
bounded output, failure classification and `started`/`finished` ledger records
as uploads. Projects must not invoke a second raw `scp` path to retrieve logs,
checkpoints or result artifacts.

The ledger is replayable through the read-only operation command:

```bash
python scripts/server_operations.py sem-ubuntu --profile-file "$PROFILE"
```

An operation with an unknown effect, including `started` without `finished` or
a timed-out/failed mutation, is returned as `effect_uncertain=true` and makes
the command exit with status `1`. This is a reconciliation signal, not a retry
queue: inspect the owning remote effect first, then record an explicit
resolution before submitting another mutation. A malformed ledger fails
closed with a typed integrity error rather than being partially read.

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

## Operation effect and recovery

The operation ledger now records an effect class for every operation:
`observation`, `mutation`, or `unknown`. A timeout, interrupted operation,
network failure, or failed operation whose effect is not proven absent is
`effect_uncertain=true`, including operations that already have a `finished`
record. This closes the previous gap where a timed-out operation could look
complete merely because the local SSH process returned.

The observed mutation ports refuse to submit a new write while any uncertain
operation for that server remains. This is a recovery gate, not an automatic
retry policy. After independently inspecting the remote effect, record the
operator decision and evidence without submitting another command:

```bash
python scripts/server_operations.py sem-ubuntu \
  --profile-file "$PROFILE" \
  --reconcile-operation srv-op-... \
  --disposition effect_not_applied \
  --evidence-ref health-check:2026-08-22T... \
  --evidence-digest <sha256-of-the-evidence>
```

Only `effect_confirmed` and `effect_not_applied` are accepted. The ledger
stores the evidence reference and digest, never the evidence contents or a
secret. Reconciliation is profile-bound: an operation from a different
profile generation must be inspected under that original identity instead of
being cleared from a new profile.

The same server-scoped ledger also owns a long-lived mutation lock around each
remote command or file transfer. The lock is distinct from the short append
lock: it covers the remote side-effect window, so two controllers cannot both
observe an empty pending set and concurrently mutate the same server. A
controller crash releases the kernel lock, while its durable `started` record
still forces reconciliation before the next mutation.

Downloads are written to a same-directory temporary file and atomically
renamed only after SCP succeeds and the temporary artifact exists. A failed or
interrupted download therefore preserves the previous authoritative target
and cannot leave a partial result at its final path.

The recovery query is server-scoped. A shared local binding directory may hold
records for several logical servers, but a pending operation for server A never
blocks or appears in the recovery output for server B. Persistent tmux session
operations carry the same effect semantics through the generic session seam:
session inspection and binary attestation are observations, while session
creation and termination are mutations. A failed or interrupted remote session
mutation therefore enters the same reconciliation gate as release and
file-transfer mutations instead of bypassing it through the session adapter.

`server_health.py` reports two distinct facts: `platform_ready` means the
remote managed runtime identities are verified; `ready_for_mutation` additionally
requires an empty effect-recovery queue. Its exit status is successful only
when both are true. A healthy host with an unresolved timeout is therefore
still intentionally blocked for new writes.

`LOCAL_BINDING_ROOT` and `SSH_CONTROL_PATH` are controller-local paths;
`PLATFORM_ROOT`, `RELEASE_ROOT`, and all managed executable paths are remote
POSIX paths. Never put `/data/...` into a local field. The validation profile
uses a workspace-local binding root so normal and elevated controller
processes share the same audit state. On the Windows controller, the
validation profile leaves `SSH_CONTROL_PATH` unset because the local OpenSSH
implementation did not complete a qualified control-socket handshake; Ubuntu
controllers may enable it with a short local socket path after qualification.
