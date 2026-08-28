# SEM Evolution decomposition v22

The former `evolution.py` mixed contracts, scheduling, compilation/verifier and orchestration. It is now a package:

- `evolution/contracts.py`: immutable domain messages + ports only;
- `evolution/eligibility.py`: deterministic scheduling, no edit-direction authority;
- `evolution/compiler.py`: structural sugar -> CREATE/RETIRE primitives and operational verification;
- `evolution/pipeline.py`: stage sequencing only.

The Method Session snapshot is now method-owned schema v2 and contains architecture generation, evidence sequence, evolution epoch, completed-task count and last grounded payload. The outer Reliability plane still sees only opaque bytes + hash + method/session/schema identity.

Because no real scientific run has been performed and the user explicitly selected latest-only architecture, v22 intentionally rejects all old snapshot implementation/schema identities instead of maintaining migrations or compatibility branches.
