# Round 44 — Freeze the proven dependency closure into materialization

Date: 2026-08-23

## Root cause found

The v4 probe and evidence model could already prove a recursive dependency
closure, but the resolver still emitted only the backend root package (and the
SGLang kernel root). The application installer then invoked ordinary pip
resolution. That left a semantic gap:

```text
qualified dependency graph  !=  materialized dependency graph
```

Pip could choose a newer or different transitive package after qualification,
so the persisted plan was not yet the complete object being installed.

## Structural correction

The resolver now projects every `PackageDependencyNodeFacts` node into the
same backend candidate's `InstallPackage` tuple. It deduplicates package names
across the backend and its CUDA kernel closure, and rejects conflicting
versions instead of allowing two incompatible package requests into one plan.
The result is still one plan candidate and one evidence record; no second
dependency manager or post-hoc filter was introduced.

The existing Python environment adapter now materializes each source-index
group with:

```text
--no-deps --only-binary=:all:
```

The first flag prevents pip from discovering a new graph, while the second
prevents an unqualified source distribution from entering an installation
that was qualified only through binary wheel evidence. All transitive packages
must therefore already be present in the frozen plan. `pip check` remains the
post-materialization consistency proof owned by the Python environment
authority.

## Verification state

The resolver and installer regressions pass in the available controller
environment, and the changed modules pass syntax compilation. The authoritative
verification remains pending on the Ubuntu server because the declared local
SSH identity is unavailable. The new code has not yet been uploaded or used to
mutate any model environment.

The prior verified server evidence remains unchanged: v3 wheel qualification
passed its recorded focused suite, and v4 recursive closure source was
structurally verified before the diagnostic fix. Neither is promoted to a
verified v4 materialization result by this round.

## Next server sequence

After restoring the SSH identity, upload through the persistent repository
workflow, pull the pushed commit, then run the server focused qualification
suite, architecture gate and no-degradation audit. Only after those pass should
the corrected v4 qualification be rerun. No mutating apply operation is
authorized by this round.

## Non-claims

No package was installed, no serving process was started, and no Minecraft or
SEM experiment was run.
