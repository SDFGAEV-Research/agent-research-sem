# Round 102 — participant leaf ownership and baseline diagnosis

## Scope

This round completes the participant implementation/catalog ownership slice while
preserving the preceding cleanup of the unused SEM-specific participant
projection. The projection had no production caller; it is not restored as a
compatibility path.

## Structural change

The historical aggregated participant implementation/runtime authorities are now
physically absent. Ownership is explicit:

- implementation identity and factory catalog: `participant/definition/runtime`;
- configuration catalog and binding resolver: `participant/binding/runtime`;
- session-runtime catalog, endpoint join and checkpoint runtime:
  `participant/session/runtime`.

`LocalParticipantResolver` depends only on binding API protocols. Concrete leaf
catalogs and the local endpoint are joined in
`participant/binding/composition/local.py`; no generic service locator or
cross-leaf concrete import is used by the resolver.

## Verification

- Python 3.12 syntax compilation of the migrated source and callers: pass.
- Architecture gate: pass; package cycles 0, import/source/authority findings 0.
- Direct resolver identity/configuration regression: pass.
- Direct architecture source audit and project API firewall check: pass.
- Retired aggregated participant paths and the temporary platform resolver have
  no active source/documentation references.

## Baseline diagnosis

The unmodified server baseline completed with 733 passing tests, 8 failures and
4 subtests. All eight failures shared one root cause: tests supplied a synthetic
placeholder tmux digest while pointing at a real host tmux executable, so the
runtime correctly raised `TmuxBinaryIdentityMismatch`. The test fixtures now use
an intentionally absent executable for runner-only identity tests; production
binary verification is unchanged. Smoke execution remains blocked until the
corrected baseline is rerun successfully.

The local Windows environment is not used as the Linux tmux regression oracle:
its `pathlib` absolute-path semantics differ for the server fixture paths. The
server Python 3.11 environment remains the authoritative execution target for
the baseline ladder.

## Next gate

Deploy this complete local slice, rerun the unmodified-equivalent baseline under
the corrected host-independent fixtures, and enter smoke only after exit status
zero. No Minecraft or paper scientific result is claimed by this round.
