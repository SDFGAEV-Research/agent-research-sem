# Server management control-plane audit — 2026-08-22

## Conclusion

The managed server control plane is now a real, profile-bound system for
connection identity, remote health, file transfer, immutable release
publication, persistent operator sessions, operation evidence, effect
reconciliation and per-server mutation serialization.

It is not yet the final server platform. The remaining gaps are a unified
diagnostic orchestration entry and a first-class multi-server inventory
catalog. The old standalone runtime-session launcher has now been migrated
into the `runtime/server` lifecycle composition and deleted.

## Evidence-based root causes addressed in this slice

| Symptom | Root cause | Structural correction |
|---|---|---|
| An operator could attach to a session that was not durably bound or whose live command had drifted | `server_session attach` requested a TTY argv directly from the transport adapter | `PersistentSessionManager.attach` now proves the exact binding and live snapshot before materializing the attach argv |
| A profile could change while status still reported the old session as exact | status only checked the stored binding, not the current composed server profile | the current server profile digest is included in the session identity; the status probe compares the expected current spec |
| A remote host could be healthy while the next mutation was unsafe | health exit status ignored unresolved effect-uncertain operations | health now exposes `reconciliation_required` and `ready_for_mutation`; success requires both platform readiness and an empty pending set |
| Broken local SSH paths appeared as remote authentication/network failures | key, known-hosts and SSH-config paths were not validated before spawning OpenSSH | composition requires absolute, readable regular local files before any network action |
| The same server tools worked as CLI scripts but failed when imported by tests/orchestration | entrypoints used a script-directory-relative `server_common` import | server entrypoints use the package-qualified `scripts.server_common` seam |

## Current authoritative flow

```text
literal profile
  -> runtime/server composition
  -> one connection profile + one remote runtime profile
  -> one profile digest + one operation journal
  -> observed SSH/SCP ports
  -> health / release / session lifecycle consumers
```

Remote effects follow:

```text
start journal record
  -> per-server mutation lock
  -> SSH/SCP/tmux mutation
  -> finish journal record
  -> effect uncertainty gate on timeout/network/failure
  -> explicit evidence-bound resolution before another write
```

Observation operations remain concurrent. Mutation operations for one logical
server are serialized; different logical servers have different lock files.

## Capability coverage

| Capability | Authority | Current state |
|---|---|---|
| connection identity | `runtime/server/identity` | implemented and profile-bound |
| local identity preflight | `runtime/server/identity` | implemented for configured local files |
| remote tool/path identity | `runtime/server/lifecycle` + `health` | implemented and digest-verified |
| command and transfer transport | `runtime/server/identity` | implemented through SSH/SCP providers |
| operation correlation and previews | `runtime/server/runtime` + observer | implemented with durable JSONL evidence |
| effect recovery | `runtime/server/api` + journal | implemented, mutation gate enforced |
| release publication | `runtime/server/lifecycle` | content-addressed and transactional |
| persistent operator session | `runtime/session` composed by `runtime/server` | binding, drift, attestation and recovery integrated |
| multi-server isolation | server-scoped journal queries and locks | implemented for the managed control plane |
| one-click remote diagnosis | no single diagnostic orchestration entry yet | remaining |
| final runtime launch authority | `scripts/server_runtime.py` + lifecycle bootstrap | implemented and profile-bound |
| server inventory/catalog | environment profile fields only | remaining; must be introduced without a locator |

## Verification

- Ubuntu compile succeeded for the changed server/session/entrypoint modules.
- Ubuntu focused regression: **60 passed**.
- Ubuntu architecture gate: **`ARCHITECTURE_GATE_PASS`**.
- Real Ubuntu health: `reachable=true`, `platform_ready=true`, all managed
  binary/package identities verified, `pending_operations=[]`,
  `ready_for_mutation=true`.
- Operation ledger replay succeeded with no reconciliation required.
- The profile-bound runtime-launch seam added in the same migration passed an
  additional **13 Ubuntu tests**, including remote release-directory
  verification, manifest decoding and controller-environment parsing.
- A malformed runtime-manifest dry-run failed before any SSH or tmux operation.
- No model, Minecraft, or scientific experiment was started in this slice.

## Next migration boundary

The next server-management slice should add a read-only diagnostic projection
that joins local profile validation, remote health, operation recovery and
bound-session status without becoming a service locator. It should then be
followed by a profile catalog for multiple servers. No project may recreate
SSH/tmux/scp arguments while those capabilities are added.
