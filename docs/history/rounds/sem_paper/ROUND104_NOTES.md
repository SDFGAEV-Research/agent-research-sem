# Round 104 — logging leaf ownership migration

## Scope

将日志系统真实实现从旧的 `observability.logging.api/runtime` 聚合入口迁入已注册的递归叶节点，使平台、项目和项目内部只依赖叶节点接口，具体策略由 composition 注入。

## Ownership result

- `logging/context` owns `DiagnosticAddress`。
- `logging/record` owns `LogLevel`、`LogRecord`、`LogBatch` 和 `StructuredLogger`。
- `logging/sink` owns `LogSinkPort`。
- `logging/query` owns `LogQueryPort`。
- `logging/routing` owns `FanoutLogSink`。
- `logging/storage` owns `InMemoryLogStore`。
- Paper-1 continues to customize records through its injected `LogSinkPort`; it does not import a logging implementation.

## Deletion and governance

- Retired parent `logging/api/contracts.py`、`logging/api/ports.py` and `logging/runtime/*` are physically deleted from the working tree.
- The architecture dependency audit rejects imports of the retired parent API/runtime paths and checks that every migrated leaf has a concrete owner.
- No compatibility re-export was retained from the retired runtime path.

## Verification status

- Local source diff and provider compile: pending after this migration.
- Focused logging/project tests and architecture gate: pending.
- Server deployment and complete baseline: pending; current server remains on the previously verified `56dbaa9` release until this slice passes all gates.
