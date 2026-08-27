# Documentation Change Policy

Documentation is part of the governed change surface. A source/configuration/test/deployment change is incomplete until the owning documentation is updated in the same change set.

## Required same-change updates

Every modification must update the smallest canonical document that owns the changed contract or observed state:

- architecture or ownership change -> `docs/architecture/`;
- reusable runtime/model/server/Minecraft/observability change -> matching `docs/infrastructure/<owner>/` document;
- SEM method, protocol, matrix or claim-gate change -> `docs/research/` or `docs/projects/sem_paper/`;
- governance rule or operational policy change -> `docs/governance/`;
- current verified runtime/development state change -> `docs/status/`;
- important completed milestone -> add an immutable note under `docs/history/rounds/<owner>/` when useful.

A code comment, commit message or chat transcript is not a substitute for the owner document.

## Current-state rule

`docs/status/CURRENT_EXECUTION_STATUS_20260828.md` is the live operational projection for the current SEM/server/model work. Update it whenever a change materially alters server readiness, model state, live-run blockers, qualification state, scientific-run state or the active optimization lane.

`docs/status/CURRENT_DEVELOPMENT_BASELINE.md` remains the broader development baseline and must link to the latest execution projection. Historical dated sections inside it are evidence, not current-state claims.
## Generated-report rule

Current algorithm, concurrency and performance reports belong under `docs/status/`. Root scan files may remain when a frozen `RELEASE_MANIFEST.json` references their paths; those root files are release compatibility artifacts and must not be presented as current authority unless regenerated for that exact release.

## Minecraft source-evidence rule

Changes that depend on Mineflayer, Prismarine or Minecraft protocol behavior require an upstream evidence step before implementation:

1. identify the exact lockfile package version;
2. inspect the matching GitHub tag/commit through the authorized Windows controller;
3. record the relevant upstream API/event/behavior in the owning Minecraft document or current status;
4. implement the narrowest compatible change;
5. run locked-dependency Node tests and live Minecraft validation.

Do not invent protocol behavior, positional tolerances, event ordering or pathfinder semantics when upstream code can answer the question.

## Commit discipline

Prefer one change set that contains implementation, tests and documentation together. If unrelated work is already dirty, stage only the files owned by the current change and preserve the unrelated worktree state.

Release manifests and historical evidence must not be rewritten merely to make documentation appear current. Current state is updated forward; frozen evidence remains immutable.
