# Infrastructure Documents

This directory documents reusable platform infrastructure. Each subtree owns a bounded capability and exposes public contracts that downstream applications may compose without making a concrete application part of the platform.

- [`ai/`](ai/README.md) — model identity, assets, serving, prompts, qualification, and runtime asset management.
- [`runtime/`](runtime/README.md) — lifecycle, operator, service, release, endpoint, and execution control.
- [`server/`](server/README.md) — generic remote-host identity, connection, capacity, repository transport, and persistent-session control.
- [`observability/`](observability/README.md) — logs, telemetry, traces, diagnostics, and I/O/performance observation.

Concrete environment providers, benchmark runtimes, model selections, and deployment fleets belong downstream and bind to these infrastructure contracts through public APIs.
