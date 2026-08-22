# Round 122 — server-side Minecraft smoke closure

## Server-only verification policy

The active verification target is the Ubuntu server. Local Windows Python is
not used as evidence for this round; the default local interpreter is 3.10,
while the project contract requires Python >=3.11.

## Evidence

Commit `6a1bb31` was extracted into an isolated server staging release. The
server-side environment was prepared with:

- Python 3.11.15 in the managed `sem-paper` environment;
- Node.js 22.22.2 and npm 10.9.7, activated as one toolchain;
- the locked Mineflayer bridge dependencies (`92` packages, `93` audited);
- the existing Minecraft 1.20.1 server jar for infrastructure smoke only.

The focused Minecraft regression suite passed on the server:

```text
30 passed in 0.56s
```

The fourth scripted smoke also completed. Its durable result reported
`status=completed`, `scientific_claim=false`, and
`scientific_scope=control_branch_plumbing_only`; `failures.jsonl` contained
zero rows and the run wrote the source checkpoint, branch receipt, event log,
metrics and workload artifacts.

The smoke is infrastructure evidence, not a paper result. Its scripted task
policy intentionally produced a control-only aggregate and is not used to
compare methods.

The exact vanilla 1.21.8 artifact was then acquired from Mojang's
content-addressed server URL and verified on the server:

```text
sha256 2349d9a8f0d4be2c40e7692890ef46a4b07015e7955b075460d02793be7fbbe7
```

Its preflight passed, and a second scripted smoke using that artifact
completed with `status=completed`; the durable failure file was absent (zero
failure records) and the event log contained 43 records. This closes the
environment smoke for the paper's declared 1.21.8 identity, but it still does
not constitute a model-backed baseline.

## Environment root causes recorded

1. Calling the npm executable by absolute path without activating its Node
   directory caused the npm shebang to select the system Node 12. The managed
   Node 22 `bin` directory must be prepended to `PATH` as one toolchain.
2. The server Python environment had no pytest. The test runner was installed
   into the managed environment rather than changing project runtime
   dependencies.
3. A user-site Hydra pytest plugin polluted collection and required an
   unrelated `yaml` package. Server test invocation disables third-party
   pytest autoloading; project tests themselves remain fully enabled.

These are deployment/environment-management findings and must become explicit
managed-environment state, not ad-hoc shell assumptions.

The first attempt to use the platform manager found one remaining old entry
point in `pyproject.toml`: `research-platform-manage` still referenced the
deleted pre-migration `research_platform.operator.management_cli` module. The
entry point is now bound to the sole current runtime-management composition
root under `operator/maintenance/runtime`; no compatibility module is added.

The environment-management boundary also now fails closed on a nonzero
subprocess return code. Previously `env check` returned a failed `pip check`
result inside an `ok=true` CLI envelope. The management CLI now converts that
result into a typed failed command with the captured diagnostic detail.

## Remaining gates before baseline

- provision and qualify a model deployment, then freeze its endpoint and model
  identity;
- run the unmodified model-backed baseline only after both identities are
  complete;
- bind the current SEM Deluxe candidate materializer and paired evaluator
  before any scientific comparison claim.
