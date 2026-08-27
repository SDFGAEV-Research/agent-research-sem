# Concurrency Governance Report

- Source digest: `621eb0a1e15a4c9001f529cb1255d2db6a2459553ce60d665d5d229ffe3baba1`
- Hotspots: **410**
- Findings: **1**
- P0/P1 debt: **0**

## Coverage

| Language | Files | Hotspots | Parse errors |
|---|---:|---:|---:|
| javascript | 203 | 107 | 0 |
| python | 2602 | 302 | 0 |
| shell | 19 | 1 | 0 |

## Finding summary

| Code | Count |
|---|---:|
| `timeoutless-wait` | 1 |

## Hotspots

### `research_platform/runtime/server/identity/providers/ssh.py::SSHServerConnection.run_interactive`
- **P2** `timeoutless-wait` line 371: blocking wait has no explicit deadline/timeout
