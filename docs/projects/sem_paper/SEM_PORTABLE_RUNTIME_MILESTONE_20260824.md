# SEM Portable Runtime Milestone — 2026-08-24

本记录是
[`PAPER_IMPLEMENTATION_COMPLETENESS_AUDIT_20260823.md`](PAPER_IMPLEMENTATION_COMPLETENESS_AUDIT_20260823.md)
之后的实现增量，不替代论文设计冻结，也不把可运行性等同于科学结论。

## 本轮完成

1. 平台新增通用、确定性、可检查点恢复的 state-machine environment：领域仅注入
   dynamics，平台统一拥有 session、action identity、effect receipt、reconcile、
   validate-before-mutate restore 与生命周期。
2. SEM 新增真实非 Minecraft 执行入口和 reference closed world provider。它复用
   `ExperimentRunSpec`、`StudyProtocol`、`StudyUnitExecutionPort`、generic workload、
   `MethodSession` 和同一 grounded evidence schema，不在项目中复制执行器。
3. recall 返回的真实 record/node/score/source-ref 与最终 task outcome 进入一个共享的
   session telemetry authority；telemetry 和 task idempotency 状态一同进入 schema-v9
   SEM snapshot，恢复前先完整校验。
4. Minecraft production graph 绑定 branch-local authoritative world checkpoint provider、
   平台 `WorkloadCheckpointCoordinator` 和类型化 checkpoint publication port。每个
   repetition 的 source cut 与每个 branch 的最新 task-boundary checkpoint 通过原子
   `resume_index.json` 联结；恢复会校验 run、protocol、task、candidate、source cut、
   environment/method generation 和 task prefix。
5. 可复用结果上升到平台 API：`MethodTaskOutcome`、`WorkloadBatchResult`、
   `CheckpointedWorkloadBatchResult`、checkpoint publication port 和 state-machine
   contracts 均不依赖 SEM 或 Minecraft 实现。
6. MC environment checkpoint 现在同时封装 world provider payload、state projection、
   observation sequence 和 action verification ledger；恢复会先校验完整 envelope，再
   停 bridge、恢复 world、重连 bridge，失败后的 session 会 fail closed。

## 明确未完成

- production 仍显式使用 `DisabledSessionEvolutionFactory` 与 static Seed-X candidate；
  真实 stage providers、单一 adoption/serving authority 尚未完成。
- Core-6、RuleBased、必要 ablation、冻结 repetition/seed/order/budget 尚未执行。
- LTE-SR、LPI、TDP、ELCE、HPEF、GAG 等完整 estimand/attribution/cost registry 尚未发布。
- 当前 checkout 没有 qualified live deployment closure、真实 Minecraft T2B PASS bundle
  或正式实验结果；两个新入口均不会据此发布 scientific claim。
- topology declaration-only leaves 与既有 opaque API debt 仍由专项架构迁移处理。

## 验证边界

- deterministic non-MC reference study 已执行端到端，结果固定标记
  `scientific_claim=false`。
- Python compile、global architecture gate、silent-failure audit、no-degradation audit 与
  SEM architecture audit 均在当前源码上执行。
- 完整 pytest 集合在当前托管容器中需剔除两个依赖 `/proc/<Popen pid>` 的 Linux
  process tests：容器返回的 child PID 不存在于其挂载的 `/proc`，即使 child 仍在运行。
  该宿主限制不应通过弱化 production procfs identity 校验来规避；目标 Linux 主机仍需
  执行这两个测试。当前容器结果为 `1051 passed, 2 deselected, 4 subtests passed`。

## 下一优先级

下一里程碑应先完成真实 session-scoped evolution composition，再冻结完整 comparator /
ablation matrix 与 metric registry；只有通过 qualified model、真实 MC T2B、完整 evidence
和统计门禁后，才允许把运行产物提升为论文科学证据。
