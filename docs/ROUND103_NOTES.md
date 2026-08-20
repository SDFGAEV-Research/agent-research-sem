# Round 103 — segmented forensic log ownership signal

## Scope

修复 d3fb115 服务器基线中唯一失败的分段事件日志回归：拥有者在外部新增段文件后必须拒绝继续 append，同时保持 steady-state append 不枚举全部段文件。

## 根因证据

- `SegmentedHashChainedJSONL._ensure_owned()` 只比较根目录 `stat_signature` 与当前活动段签名。
- 服务器上的临时目录在创建 `99999999.jsonl` 后，根目录返回的 `(st_dev, st_ino, st_size, st_mtime_ns)` 与外部创建前完全相同；目录实际已经包含两个段文件。
- 因此旧检查既没有观察到目录成员变化，也没有触发 verifier，第二次 append 被错误接受。

## 结构性修复

- 新增 `DirectoryChangeSignal` 作为 forensics provider 内部的变更信号抽象。
- Linux 使用非阻塞 inotify 事件队列；正常 append 只消费事件队列，不按段数枚举目录。
- 不支持 inotify 的平台保留 `stat_signature` 后备路径。
- `SegmentWriterState.directory_signature` 仍是唯一的预期状态权威；signal 只维护 watcher 游标和 fail-closed pending 状态，不复制目录状态。
- 所有者完成自身写入后确认本次事件；外部目录事件保持 pending，并先执行完整 verifier，再拒绝当前 append。

## 验证状态

- 修复前服务器最小回归：`1 failed, 1 passed`，失败正是外部段目录变化未被拒绝。
- 本地 provider 源码 compile：通过。
- 修复后服务器定向测试、完整基线和架构/治理门禁：待提交部署后执行。

## 下一步

提交并部署后先重跑该定向回归，再重跑完整服务器基线；基线全绿前不进入论文 smoke/full 阶梯。
