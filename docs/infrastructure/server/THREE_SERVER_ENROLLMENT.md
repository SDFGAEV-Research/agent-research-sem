# Three-server enrollment

This page records the three SSH endpoints currently known to the local
controller and their boundary in the server-management system.

| Logical ID | Endpoint | User | Enrollment state |
|---|---|---|---|
| sem-ubuntu | 103.40.13.126:60320 | ubuntu | connection enrolled; complete runtime profile exists in the attested SEM template |
| node-121-48-164-162 | 121.48.164.162:22 | courseliu | connection enrolled; remote runtime not attested |
| node-121-48-162-165 | 121.48.162.165:32769 | ubuntu | connection enrolled; remote runtime not attested |

## Configuration

The committed non-secret enrollment template is
configs/server_profiles/three-servers.example.env. The local working copy
used for controller diagnostics is
configs/server_profiles/three-servers.local.env; it is ignored by git and
contains only local SSH file paths, never private-key contents or passwords.

All three identities are members of one explicit RP_SERVER_CATALOG_IDS
projection. No project may keep another server list or construct SSH, SCP or
tmux arguments directly.

## Readiness semantics

Enrollment is not readiness. The catalog separates connection identity
(HOST, PORT, USER) from remote runtime identity: platform root, repository
root, executable paths, exact digests, session identity and controller-local
binding. server_doctor.py list reports both groups without network I/O.
composition_ready is true only when every required field is present.

The two additional entries deliberately contain no guessed Python, Node, Java,
tmux, repository or remote-home paths. They become operational only after the
read-only qualification route authenticates and attests their actual runtime.
Until then they must not be used for repository synchronization, release
publication, persistent sessions or experiments.

## Current evidence

The bounded non-interactive probe performed on 2026-08-25 observed:

- sem-ubuntu: endpoint timed out at the network boundary;
- node-121-48-164-162: TCP reachable, current local SSH identity rejected;
- node-121-48-162-165: TCP reachable, current local SSH identity rejected.

No remote command or mutation was performed by that probe. These observations
are transport/authentication evidence only and do not certify remote runtime
availability.
