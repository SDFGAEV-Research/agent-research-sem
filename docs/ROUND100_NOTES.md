# Round 100 Notes — project method projection and participant binding ownership

Date: 2026-08-20

This round continues the final-architecture migration. It does not change the
scientific method, run Minecraft, train a model, or claim an experiment.

## Completed structural changes

### 1. Paper method projection is now explicit and project-owned

`projects/sem_paper/composition/participant.py` projects each Paper-1
`MethodEndpointPort` into the generic Participant runtime contract. The
projection preserves the method endpoint as the scientific authority while
deriving the outer participant implementation/runtime identities needed by
experiment-level binding.

Resolution is exact on the complete implementation/runtime digest pair. Empty
or duplicate treatment ids, unknown identities, and colliding projections fail
closed. Projection has no session opening, state write, model call, server
operation, or Minecraft side effect.

This is an interface seam, not a generic SEM implementation in the platform.
Another paper project can provide its own projection and its own logging,
serving, persistence, and evolution implementations behind the same platform
ports.

### 2. Participant resolver ownership was physically migrated

`LocalParticipantResolver` now lives at
`research_platform/participant/binding/runtime/local_resolver.py`, where it
joins participant implementation, session-runtime, and configuration
identities. The old
`research_platform/platform/composition/participants/local_resolution.py`
file was deleted; no re-export or compatibility forwarding path remains.

The resolver still consumes the participant-core catalog contracts. That is an
explicit next migration debt: catalog/configuration authority must be split
into the registered participant leaves before the core package can be removed.

## Verification

- project composition and projection checks: 6 direct checks passed;
- focused migration regression: 23 unit tests passed under the available
  Python 3.11 runtime;
- architecture, silent-failure, and no-degradation static gates: pending this
  round's final rerun;
- CodeGraph circular-dependency audit: pending this round's final rerun;
- full post-migration regression: still pending.

## Environment limitation

The available LibreOffice Python 3.11 runtime cannot import `sqlite3`. The
study-identity regression imports the SQLite forensics provider and therefore
cannot be collected in this environment. This was recorded as an environment
limitation rather than bypassed or weakened; the resolver-specific direct
checks remain runnable.

## Non-claims

This round does not claim that the generic host has completed
`ProjectDefinition -> experiment/run -> environment/runtime -> model/effect`
wiring. It also does not claim that participant-core catalogs or the remaining
platform composition roots are retired. Those remain ordered migration slices.
