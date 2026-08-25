# Round 48 — Enroll all known SSH endpoints in the server catalog

Date: 2026-08-25

## Change

The server-management boundary now has one committed enrollment template for
the three SSH endpoints currently present in the local SSH configuration:

| Logical ID | Endpoint | User | Enrollment state |
|---|---|---|---|
| sem-ubuntu | 103.40.13.126:60320 | ubuntu | connection enrolled; runtime profile remains the existing attested SEM profile |
| node-121-48-164-162 | 121.48.164.162:22 | courseliu | connection enrolled; remote runtime not attested |
| node-121-48-162-165 | 121.48.162.165:32769 | ubuntu | connection enrolled; remote runtime not attested |

The template is
configs/server_profiles/three-servers.example.env. It contains no
credential, private-key material or guessed remote path. A local copy belongs
under the ignored *.local.env pattern.

## Evidence boundary

The two additional endpoints were checked with bounded, non-interactive SSH
probes before enrollment. Their TCP endpoints were reachable, but the current
local SSH identity was rejected by both servers. The SEM endpoint timed out at
the network boundary during the same check. No remote command or mutation was
performed.

Therefore enrollment is deliberately split into two states:

1. catalog membership records the known connection identity for all three;
2. runtime composition becomes ready only after the server's platform root,
   executable paths, digests, session identity and local binding are attested.

server_doctor.py list is the authoritative offline check. It must report
missing runtime fields for an incomplete entry and must never infer a Python,
Node, Java, tmux or repository path from another server.

## Invariants

- RP_SERVER_CATALOG_IDS is the only server membership authority.
- Each server has one logical namespace under RP_SERVER_<ID>_*.
- Connection identity and remote runtime identity remain separate projections.
- No password or secret is accepted, persisted or logged.
- A connection-enrolled server is not treated as ready for repository,
  release, session or experiment mutation.
