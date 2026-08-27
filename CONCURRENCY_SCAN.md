# Concurrency Governance Report

- Source digest: `88f499d3bf87b14e1ee713a4a031e8b694b3c1aada1af153203fc118f2624e05`
- Hotspots: **310**
- Findings: **1**
- P0/P1 debt: **0**

## Coverage

| Language | Files | Hotspots | Parse errors |
|---|---:|---:|---:|
| javascript | 8 | 8 | 0 |
| python | 2578 | 301 | 0 |
| shell | 3 | 1 | 0 |

## Finding summary

| Code | Count |
|---|---:|
| `timeoutless-wait` | 1 |

## Hotspots

### `research_platform/runtime/server/identity/providers/ssh.py::SSHServerConnection.run_interactive`
- **P2** `timeoutless-wait` line 371: blocking wait has no explicit deadline/timeout
