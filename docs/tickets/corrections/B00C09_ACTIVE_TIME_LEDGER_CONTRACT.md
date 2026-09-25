# B00C09 Active-Time Ledger Contract

2026-09-24。此合同补充 B03 canonical Code path 的活动时间 authority；[B00C09 冻结票](../phase-b-graph-harness/B00C09_ACTIVE_TIME_LEDGER_HANDOFF.md)限定实现和验收范围。Phase A protocol/catalog 字节、旧 B02 synthetic 路径、A05 public 0.1 artifact 和既有 ControlOperation phase 均不变。

## Authority 与计费

唯一计费 authority 是 `execution_history.jsonl` 的 schema 0.4 budget record。新增 closed `active_interval_reserved` / `active_interval_settled`，payload 版本固定为 `active_time_0.1`；旧七类事件按原字节与含义回放。reservation 在每个未结算前缀按 `maximum_seconds` 计，settlement 只可把同一 ID 收敛为可信 actual 或 conservative maximum，不可重开、重复结算或退款。Replay 同时校验连续 event/head、policy、Run/Attempt identity、owner、clock epoch、单调时间、maximum 和边界相邻关系。

| Stage | Reservation owner | Run active | Code Attempt active | Settlement boundary |
|---|---|---:|---:|---|
| `host_setup` | 原 ExternalOperation producer | 是 | 否 | public Pause frozen suffix；或原 interrupt terminal winner 的安全停止后缀 |
| `code_backend_operation` resource | 原 ExternalOperation producer | 是 | 是 | A05 final evidence 的原 resource settlement |
| `attempt_active` | normal resume 或 recoverable-timeout interrupt winner | 是 | 是 | 同一 owner 的 Attempt.finished 前一条 record |

`active_interval_reserved` 固定 `interval_id/stage/attempt_id/producer_operation_id/owner_operation_id/clock_epoch_id/start_at/maximum_seconds/run_remaining_before/attempt_remaining_before/deadline_monotonic_seconds`。`start_at` 与 record `created_at` 均为可信 Host 首次 durable freeze 时间。`active_interval_settled` 复述同一 identity，另含 `settlement_operation_id/lease_epoch/phase_revision/clock_epoch_id/end_at/actual_seconds/disposition/evidence_digest`。Actual 的 `end_at` 等于 record 时间，秒数精确等于同一 epoch 的单调时钟差；跨 epoch、缺失可信 end 或不确定 effect 按 maximum。可信 overage 保留观测值于 failure evidence 并进入完整性失败，绝不裁成 maximum 后宣称成功。

## 发布与恢复

首次 producer stub 的单一 SQLite COMMIT 冻结 setup record 完整字节、source head、三段正数 maximum 和后续 Attempt ID；task、aggregate、workspace 与 Pause 仍为空。该 record 是第一个 pre-start ledger suffix，必须先于这些物理效果。普通 pre-start effect 同时受 worker lease、producer hard deadline 和 setup deadline 限制。COMMIT 后文件写入前的 crash 可由同一 producer exact materialize 冻结 record；若原 effect lease 已失效，Host 仅为 exact setup publication 在同一内部 journal CAS 取得 `recovery_only` 新 epoch，旧 epoch 立即失效。该恢复 lease 不准执行 task、manifest、aggregate 或 workspace effect；原 record、start time、maximum 和 interval owner 不变。首次终止请求先完成这个 handoff，再取得 terminal owner。

Pause 的 `pause_opened_recorded` 原 phase 在最后 durable freeze 时间写 `host_setup` settlement，再写同时间 `pause_opened`。新 proof 的 `active_time.interval_id` 和 `settlement_execution_head` 绑定相邻 head；旧 proof 只适用于没有新 setup interval 的 B02 synthetic Pause。部分 Pause 的 prepared/paused-lifecycle 前缀由原 interrupt owner 的 stop proof 收尾。正常与 recoverable-timeout 消费均按原 A05 owner/phase 先写 `attempt_active` reservation、紧邻 `Attempt.started`，结束时写 settlement、紧邻 `Attempt.finished`；无资源调用仍计全区间。未取得可信同 epoch end 或不确定 side effect 保留 maximum，并按原 terminal outcome 分类。

Verification resource 保留正 timeout、原 `resource_reserved.maximum_charge.active_seconds`、可信实测 `resource_settled.actual.active_seconds` 与 command 次数。只有 reservation/settlement 均在同一未关闭的 `attempt_active` interval 内，且 producer、consumer owner、时间、head 一致，Replay 才把其 active seconds 标为 nested audit；command 次数始终计一次。可用嵌套时窗同时受 parent deadline 和已占用 nested maximum/actual 限制。没有 parent 的旧 resource 仍按原规则叠加 Run/Attempt active。

`validate_control_root` 对 canonical pre-start 只接受 setup-only 或 setup+aggregate 的 exact source prefix；旧 B02 synthetic 仍为 aggregate-only。Canonical producer 内部 intent 缺失、旧 epoch 写入、foreign settlement 或 source head 漂移均拒绝。Replay/Fork 只读取父 ledger 的已结算 actual 或 pending maximum，子 Run 不继承这些计数。

四份 A05 contract-source 与七份受影响的 B02 source-bound expected trace 更新只涉及 runtime `application_build` 的下游 semantic digest/head。独立双 fresh-root 对比、逐字段旧/新差异与源版本摘要分别保存在 `/private/tmp/lqcd-agent-b00c09-golden-review.json` 和 `/private/tmp/lqcd-agent-b00c09-b02-golden-review/`；原 B02 expected 排版、旧 fixture 输入、case owner/outcome 和 trace 版本不变。
