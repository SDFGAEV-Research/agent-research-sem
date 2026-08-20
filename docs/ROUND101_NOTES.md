# Round 101 Notes — deployment baseline and operator-route test migration

Date: 2026-08-20

This round begins server execution for the current final-architecture commit.
It does not claim a scientific result, a Minecraft run, or model performance.

## Deployment

- GitHub `origin/master` and the server release both point to
  `cf2e291f48efa18b29d80ffa40f6e5267096871f`.
- The server has an immutable release directory selected by a `current`
  pointer and an isolated Python 3.11 environment with pytest 9.1.1.
- Accelerator resources were already occupied by unrelated processes during
  the audit. No process was stopped and no model service was started.

## Baseline execution evidence

The unmodified baseline was attempted in a persistent tmux run:

`baseline-cf2e291` (the full path remains in the remote operator record)

Attempt 1 stopped during pytest collection because user-site packages injected
Hydra from the remote user's local package directory and then failed on
missing `yaml`.
Attempt 2 isolated user-site packages with `PYTHONNOUSERSITE=1` and reached
project collection, then stopped on a stale test import:

```text
tests/test_runtime_status_cli_v79.py
from research_platform.operator.runtime.handlers import handle
```

The current operator architecture exposes `OperatorHandler.handle` as an
injected object method and owns runtime-status behavior in
`operator/query/runtime/route_runtime.py`; the deleted module-level `handle`
was an obsolete test boundary, not a missing production capability.

## Change in this round

The test now calls `route_runtime(args)` directly. No compatibility function
was added to the retired module. This keeps the old boundary physically
deleted and aligns the test with the current route ownership.

## Next verification

1. Commit and push this test migration.
2. Deploy the new commit to a new immutable release directory.
3. Re-run the unmodified baseline under `PYTHONNOUSERSITE=1`.
4. Only a passing baseline permits a small SEM integration smoke test.

The repository currently contains no executable Minecraft environment/task
driver, so a paper/Minecraft experiment cannot be claimed until that runtime
and its frozen workload are supplied and wired to the project composition
root.
