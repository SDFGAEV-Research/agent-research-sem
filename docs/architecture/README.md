# Architecture Documents

This directory owns the final platform architecture and its topology-facing
design. The source-of-truth topology remains
`research_platform/governance/system_registry/catalog.json`; the JSON mirror in
this directory is generated and checked against it.

Use these documents for recursive ownership, composition-time binding,
runtime ports, event-spine boundaries, migration rules and data flow. Project
method details do not belong here.

## Current topology-query implementation notes

The in-memory system registry may maintain derived child indexes for query efficiency, but `governance/system_registry/catalog.json` remains the only topology authority. Indexed `children()` and `descendants()` projections must preserve deterministic sorted breadth-first ordering and must never become independent durable state.

Architecture hotspot scanning likewise reuses the source index and performs one AST-node traversal per module; optimization may remove repeated parsing/traversal but may not change the public hotspot scoring formula.
