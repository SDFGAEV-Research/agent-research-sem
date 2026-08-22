# Self-Evolving Memory Plugin Boundary

The Paper-1 method is now treated as one concrete plugin behind the generic Method ABI.

## Internal ownership

```text
self_evolving_memory/
├── evidence.py          J_mem / J_audit / J_eval physical API separation
├── serving.py           generation-pinned read-only recall
├── materialization.py   only J_mem view can build method memory
├── evolution.py         diagnosis -> synthesis -> compile -> evaluate -> accept -> adopt
├── authority.py         Core/Standard/Deluxe authority equality
└── plugin.py            generic ResearchMethod entrypoint
```

## Authority rules

- Diagnosis can observe only neutral structural evidence.
- Synthesis can propose exactly the frozen edit grammar; it cannot activate.
- Compiler produces a candidate; it cannot evaluate/adopt.
- Evaluator produces comparability/isolation evidence and metrics; it cannot adopt.
- Acceptance policy decides scientific acceptance; generic evaluator proof is not acceptance.
- Adoption is the only architecture-head writer.
- Materialization can see only `MemoryEvidenceView`; Audit/Eval stores are not constructor inputs.
- Serving is read-only and pins one generation for the full recall call.

## Tier rule

Core/Standard/Deluxe may differ in providers and observations but not in scientific authority. Optional Deluxe systems must not acquire evidence-write, acceptance-policy-write, planner-write, verifier-write or audit-materialization authority.
