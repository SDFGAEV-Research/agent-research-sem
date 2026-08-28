# Documentation Change Policy

Documentation is part of the governed change surface. A source, configuration, test, packaging, deployment, or governance change is incomplete until the owning documentation is updated in the same change set.

## Required same-change updates

Update the smallest canonical document that owns the changed contract or verified state:

- architecture or ownership change -> `docs/architecture/`;
- reusable infrastructure change -> the matching `docs/infrastructure/<owner>/` document;
- governance or operational-policy change -> `docs/governance/`;
- current platform development/verification state change -> `docs/status/`;
- important completed platform milestone -> an immutable note under `docs/history/rounds/platform/` when useful.

Downstream project methods, benchmark/environment implementations, model selections, deployment inventories, and scientific results are documented in the downstream repository, not copied into the upstream platform documentation tree.

A code comment, commit message, chat transcript, or generated report is not a substitute for the canonical owner document.
## Current-state rule

`docs/status/CURRENT_DEVELOPMENT_BASELINE.md` is the current development truth for the reusable upstream tree. Update it when repository boundaries, package/release identity, validation state, or active platform migration gates materially change.

Generated algorithm, concurrency, and performance reports belong under `docs/status/`. Root scan files may exist as release artifacts but are current authority only when regenerated for the exact release being inspected.

## Upstream-source evidence rule

When an adapter/provider change depends on third-party protocol or library behavior, inspect the exact pinned upstream version before changing behavior. Record the relevant upstream contract in the owning downstream/provider documentation, implement the narrowest compatible change, and validate against the pinned dependency. Do not invent wire behavior, event ordering, tolerance rules, or lifecycle semantics when authoritative upstream source can answer the question.

## Commit discipline

Prefer one reviewable change set containing implementation, focused tests, generated governance evidence when required, and the owning documentation. If unrelated work is already dirty, stage only files owned by the current change and preserve the unrelated worktree state.

Frozen release evidence is never rewritten merely to make documentation appear current. Generate new evidence for a new release/source identity.
