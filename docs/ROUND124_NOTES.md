# Round 124 — paired SEM candidate execution closure

## Scope

This round prioritizes the Paper-1 Minecraft experiment path. The previous
entrypoint only executed the control branch, so it could not produce a
scientific treatment comparison even though the paired runner and candidate
materializer already existed.

## Structural changes

- Added the project-owned `MinecraftGroundedSemanticTransformer`. It maps
  verified Minecraft `J_mem` observations into the selected typed architecture
  and reduces only from upstream typed records. Every materialized record keeps
  evidence or upstream ancestry; no flat-row or empty-memory fallback exists.
- Added the explicit C→X `seed_x_v018` candidate factory with immutable target
  digest, base generation and primitive structural edits.
- Wired the candidate materializer into the Paper composition root and changed
  the live entrypoint to run both isolated branches through the existing paired
  evaluator. Baseline mode now records control receipt, candidate receipt,
  comparability proof and branch metric deltas. Scripted smoke remains
  plumbing-only and cannot claim a scientific result.
- Hardened managed server-health digest parsing so an empty transport response
  preserves the authentication/transport failure instead of raising an
  `IndexError`.
- Corrected an existing MC host-request regression fixture from the invalid
  hyphenated username `paper-bot` to the ABI-valid `paper_bot`; production
  username validation remains strict.
- Fixed paired workload identity at the experiment composition boundary. The
  control and candidate now share one run-scoped `workload_id`; their branch
  ids remain distinct. The first current-code smoke proved the previous role-
  encoded identity caused a false `workload_id mismatch` comparability failure
  despite both branches completing.

## Verification state

Local verification is limited to Python compilation and `git diff --check`.
The focused semantic-transform, candidate-materializer, MC composition and
server-health regression must run in the Ubuntu managed environment. No model
or Minecraft process has been started by this round yet.

## Remaining experiment gates

1. Publish this source slice to the server and run the focused regression there.
2. Reproduce the unmodified model-backed baseline against a qualified model
   endpoint, preserving exact model/prompt identity.
3. Run paired small smoke, then the declared full task manifest.
4. Archive branch receipts, model requests, evidence and failure diagnostics
   before making any scientific conclusion.
