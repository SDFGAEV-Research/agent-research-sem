# Round 06 — Method Plugin Internal Decoupling

Added the first concrete `projects/sem_paper/method/self_evolving_memory` plugin skeleton with hard internal authority boundaries, separate evidence stores, generation-pinned serving, J_mem-only materialization and a six-stage evolution pipeline.

This is a replacement architecture, not a compatibility wrapper around old `memory_runtime/evolution/mc_runtime` packages.
