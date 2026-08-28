# Round 129 — post-migration release and server-test contract repair

## Failure evidence

The first full regression on the exact GitHub revision `bb386135` reached
`972 passed, 7 failed`. The failures were confined to release-document and
server-repository unit contracts; the server checkout remained clean at the
exact revision after the run.

## Root causes

1. The release-document test still addressed the retired top-level
   `docs/INTEGRATION_PLAN.md` and asserted pre-migration README wording.
2. Release metadata for a synthetic tree fell back to the controller's
   installed `research-platform` distribution, creating an ambient second
   version authority.
3. Repository command/sync test doubles did not expose the now-required
   profile-bound repository timeout.
4. The command test asserted the old quoted shell assignment even though the
   current safe shell serializer emits an unquoted hexadecimal SHA.

## Repairs

- Release documentation tests now use the authoritative
  `docs/architecture/INTEGRATION_PLAN.md` and current status baseline.
- Source trees without a root `pyproject.toml` are explicitly `unversioned`
  when allowed; installed package metadata is never inherited.
- Server repository test doubles now model the profile timeout contract.
- The command assertion now checks the actual canonical SHA assignment.

No legacy documentation path or compatibility file was restored. No
Minecraft process, model call or scientific experiment was started.

## Verification gate

The repaired revision must be published to GitHub, synchronized through the
managed repository script and rerun on Ubuntu. The full regression is not
considered repaired until the seven previously failing tests and the complete
suite pass on that exact server checkout.
