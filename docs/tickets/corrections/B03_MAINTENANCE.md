# B03 Maintenance Record

## 2026-09-24 — Verification resources in the original resume transaction domain

- Ticket：[B03](../phase-b-graph-harness/B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md)，既有 Allowed Files 内的 resource binding、invocation fencing 与 consumption failure 接线；不更改 A04/A05/A06 合同。
- 原因：B02 consumer 在单个 SQLite writer transaction 内执行，且 effect/completion 只接受 Attempt started 时的 ledger head，无法容纳独立持久化的 verification reservation/settlement。
- 改动：normal external consumer 在 writer 外运行；member publication 使用短事务及原 resume owner/invocation 双重 fence。独立命令预留与结算保存在已有 capability row 的精确 publication journal，复用原 budget record/replay 与原 resume 失败收尾。未新增预算 authority、数据库或可重跑许可。
- 恢复：进程中断只补齐已经提交的精确 ledger/index suffix，随后由原 resume 关闭失败；已有 completion intent 才能恢复完成。过期 worker 不能继续结算，pending reservation 由原 owner 保守计费；其他 attempt 的资源不改变当前 completion 条件。
- 不可追加分支：Run index 被篡改时，failure snapshot 从已验证的 durable journal 保留全部 pending verification IDs；这些历史记录不构成当前可追加 authority，不允许据此伪造 failed lifecycle。
- 验证：11 项资源测试覆盖预算耗尽、重复命令、consumer error、authority tamper、过期 lease 以及五个真实新进程 crash/recovery 边界。相关 B02 回归初次 163 passed；增加历史 journal 保留后继续定向复验。日志位于 `/private/tmp/lqcd-agent-b00c08-review/`。
- 限制：这些测试不计 canonical Backend/Bundle/Analysis 或 B03 的 28/645 验收；最终 full suite、同 Session runtime 和来源 golden 仍须整体验证。

### Resume takeover follow-up

授权尚未消费时，合法接管后的首次 invocation 必须绑定 acquire 时的 resume epoch，而非旧 authorization 的 producing epoch。已将该绑定保存在 invocation lease 私有元数据，并在 started publication、资源和 member/completion 的共同 fence 中验证；这同时阻止仍持有 invocation lease 的旧 resume worker 继续写入。单个 verification timeout 也必须完整落在当前 resume lease 窗口内。

基础回归 **294 passed**；上述 epoch 修复后，12 项资源/恢复与 external consumption、failure closure 定向复验合计 **108 passed**（`continued-focused.log`、`epoch-regression.log`）。其中新增真正的授权提交后、首次 Attempt started 前的进程退出与 epoch 2 恢复。未重跑完整 suite，未计 B03-owned acceptance。

### Workspace recovery follow-up

新增独立 immutable Git base 的只读 materialization、全树 path/type/scope 检查及 managed workspace identity 校验。Private device/inode ownership 不进入 public content digest。Physical workspace 在 core 后 create-new；中断恢复只补同 owner、同 bytes 的预计算文件，未知或替换 root 拒绝。

新进程在 `external.workspace_materialized/after` 退出时，恢复流程会重读此前 core；原 phase gate 错误拒绝这个无副作用读取。已允许该 phase 下复核并返回 exact core，不重新推进 phase 或覆盖内容。Prestart **23 passed**（10 个进程故障边界），workspace **14 passed**；Unix socket 负例只在 `/private/tmp` 创建本地文件，没有网络连接。

活动时间账本表达缺口属于另一个合同问题，未借本 maintenance 实施；见待审 B00C09 与 B03 completion 最后条目。
