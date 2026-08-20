# Round 22 — SEM Core Physical Decomposition

- Split evolution contracts / eligibility / compiler-verifier / pipeline.
- Preserve public `research_platform.scientific.projects.sem_paper.method.self_evolving_memory.evolution` import surface through the package `__init__`, not a compatibility runtime shim.
- Latest-only method snapshot schema v2, method-owned hash verification, session binding, no legacy migrations.
- Explicit session close behavior and diagnostics fields.
