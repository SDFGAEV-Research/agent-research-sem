# Concurrency Governance Report

- Source digest: `05a0d0502bd6cb9b6d0e7416b12ea74db64c0ef5c1aa2b68f59f4bc86d7f7a25`
- Hotspots: **267**
- Findings: **1**
- P0/P1 debt: **0**

## Coverage

| Language | Files | Hotspots | Parse errors |
|---|---:|---:|---:|
| python | 2409 | 266 | 0 |
| shell | 2 | 1 | 0 |

## Finding summary

| Code | Count |
|---|---:|
| `timeoutless-wait` | 1 |

## Hotspots

### `research_platform/runtime/server/identity/providers/ssh.py::SSHServerConnection.run_interactive`
- **P2** `timeoutless-wait` line 371: blocking wait has no explicit deadline/timeout
