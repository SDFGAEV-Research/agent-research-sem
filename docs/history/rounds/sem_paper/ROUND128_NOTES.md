# Round 128 — server-first regression fixture and repository status repair

## Failure evidence

The first server-side full-regression diagnostic reached 284 passing tests and
then failed in `test_minecraft_branch_runtime_v1.py` because its fixture used
the invalid username `paper-bot`. The current Minecraft ABI correctly accepts
only `[A-Za-z0-9_]{3,16}` usernames.

The same recovery pass found a diagnostic projection defect: repository status
without an explicit `staging_revision` constructed the target checkout itself
as the staging path, falsely reporting `staging_kind=directory` for every
valid checkout.

## Root-cause repairs

- Changed the fixture to `paper_bot`; production validation was not relaxed.
- Made the status provider emit `staging_kind=absent` unless a concrete
  revision-specific staging path is requested.
- Added a regression covering the no-revision status path.
- The controller entrypoint caught a missing explicit string concatenation in
  the first local patch; it was corrected before the commit was republished.

## Verification gate

The managed Ubuntu regression must rerun the focused repository-status suite
and the full suite before this round is considered verified. The previous
pytest failure was reconciled as `effect_not_applied` after an independent
exact-head, clean-worktree and explicit-staging inspection.
