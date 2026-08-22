# Server management control-plane audit — 2026-08-22

## Conclusion

The managed server control plane is now a real, profile-bound system for
connection identity, remote health, file transfer, immutable release
publication, persistent operator sessions, operation evidence, effect
reconciliation and per-server mutation serialization.

It is not yet the final server platform, but the two highest-friction control-
plane gaps from the previous audit are now closed: a unified diagnostic
orchestration entry and an explicit multi-server profile catalog. The old
standalone runtime-session launcher has now been migrated into the
`runtime/server` lifecycle composition and deleted.

## Evidence-based root causes addressed in this slice

| Symptom | Root cause | Structural correction |
|---|---|---|
| An operator could attach to a session that was not durably bound or whose live command had drifted | `server_session attach` requested a TTY argv directly from the transport adapter | `PersistentSessionManager.attach` now proves the exact binding and live snapshot before materializing the attach argv |
| A profile could change while status still reported the old session as exact | status only checked the stored binding, not the current composed server profile | the current server profile digest is included in the session identity; the status probe compares the expected current spec |
| A remote host could be healthy while the next mutation was unsafe | health exit status ignored unresolved effect-uncertain operations | health now exposes `reconciliation_required` and `ready_for_mutation`; success requires both platform readiness and an empty pending set |
| Broken local SSH paths appeared as remote authentication/network failures | key, known-hosts and SSH-config paths were not validated before spawning OpenSSH | composition requires absolute, readable regular local files before any network action |
| The same server tools worked as CLI scripts but failed when imported by tests/orchestration | entrypoints used a script-directory-relative `server_common` import | server entrypoints use the package-qualified `scripts.server_common` seam |
| A healthy server still required manually joining health, operation and session commands | observations were exposed only through separate CLI projections | `scripts/server_doctor.py inspect` joins all three under one profile digest without issuing mutations |
| A typo or stale second server namespace could be selected late | profile membership was implicit in environment variable prefixes | `RP_SERVER_CATALOG_IDS` is an explicit immutable catalog; undeclared namespaces and incomplete identities fail before network I/O |
| An old-profile pending operation was safe-blocking but opaque | the recovery gate queried only server id | the diagnostic projection classifies profile-mismatched or unidentified pending operations and points to their operation evidence |

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
| one-click remote diagnosis | `scripts/server_doctor.py inspect` | implemented; read-only joined projection |
| final runtime launch authority | `scripts/server_runtime.py` + lifecycle bootstrap | implemented and profile-bound |
| server inventory/catalog | `runtime/server/identity` explicit profile catalog | implemented; membership is composition data, not a provider locator |

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

The diagnostic entry is intentionally separate from mutation commands:

```bash
python scripts/server_doctor.py list --profile-file "$PROFILE"
python scripts/server_doctor.py inspect sem-ubuntu --profile-file "$PROFILE"
```

`list` performs no network I/O. `inspect` observes the remote health route,
replays the controller-local operation ledger and checks the current
profile-bound operator session. It never retries an uncertain effect and never
resolves or mutates the ledger.

## Next migration boundary

The next server-management slice should extend the same diagnostic evidence
contract to deployment receipts and run-controller state. It must preserve the
same composition locality: no project may recreate SSH/tmux/scp arguments,
introduce a second server registry, or turn the observation projection into a
command bus.
