---
ticket_id: B00C09
phase: phase-b-graph-harness
status: ready
type: corrective-implementation
depends_on: [B00, B01, B02, B03, B00C05, B00C06, B00C07, B00C08]
---

# 修正 B03 的活动时间账本与恢复边界

## Goal

审定并实现 B03 canonical Code path 的 Host setup Run-only 与 Code Attempt active time 记账：由可信 Host 时钟产生、在同一 execution ledger 持久化、由独立 reader 重放，并在 admission、deadline、Pause、Restart、Replay/Fork 与失败收尾中保持一致。完成本票只解除 B03 的活动时间合同阻塞；B03 的 Backend、bundle、Analysis 和 28/645 验收仍由冻结 B03 票完成。

本票明确补充 A06 七类 budget event 与 B03 Allowed Files/Stop Conditions，不静默重解释旧记录。冻结的 Phase A ticket、protocol/catalog 和 B03 正文均不改写。YAML 的 `depends_on: B03` 表示纠偏目标，不要求已 blocked 的 B03 先完成。仅在本票获得用户确认、YAML 变为 `ready` 后执行 runtime 修改。

## Why

`tests/phase_b/test_b03_active_time_boundary.py` 的 6 项反例稳定复现缺口；反例通过不表示记账已实现。真实 producer、pre-start、物理 workspace 和 public Pause 中，FakeClock 前进 3 秒，`clock.measure("host_setup")` 给出 Run=3/Attempt=0；新进程重放只得到 aggregate maximum 的 Run=10/Attempt=10，而非至少 Run=13/Attempt=10。独立无资源调用 Attempt `started -> finished` 前进 6 秒，两种 active 计数仍为 0。原始证据在 `/private/tmp/lqcd-agent-b00c08-review/active-time-report.json`。

当前 `budget.EVENTS` 是七项 closed union，`execution._budget_projection` 仅累计 resource actual/maximum；普通 resource `active_seconds` 同时扣 Run 和 Attempt。把 setup 塞进 Backend aggregate、自由文本、可变 graph row 或另一份 counter 都不能满足 Run-only 与跨进程重放。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`；
- A04/A05/A06/A07 frozen contracts、`CONTROL_PROTOCOL_0_4.json`、`PHASE_B_REQUIREMENT_CATALOG.json`；
- B01/B02/B03、B00C05–B00C08 tickets（尤其 B00C05 首次 stub 事务 COMMIT 前后语义）、B03 completion/maintenance 和当前状态；
- `control/{budget,clock,records,execution,pause,operations,capabilities,coordinator,integrity,projections}.py`、`code_agent/{prestart,external_operation,verification_resources}.py` 与本票列出的 tests。

## Scope

- 在原 B02 execution ledger 内实现两个版本化活动区间 event、可信时钟/owner 门禁、完整 replay/projection 和 canonical Code path 发布；
- 将 B03 setup、Backend aggregate、normal/timeout Attempt、nested verification 与 Pause/失败恢复接到同一预算 authority；
- 用 fault、restart、独立 reader 和兼容 golden 证据确认旧路径与新的计费边界。

## Non-goals

- 不交付 B03 全部 Backend、Bundle、Analysis、28 项 construction 或 645 项 runtime 验收；不接 B04 产品路由或真实 Backend。
- 不改 Phase A frozen protocol/catalog、旧 ledger 输入、legacy runtime，也不为其他 resource kind 引入通用 nested 计费。

## Requirements: Closed Wire and Charging Contract

在现有 schema 0.4 execution ledger 的 `record_type: budget` 下新增两类 closed event：`active_interval_reserved` 与 `active_interval_settled`，payload 的 `schema_version` 固定为 `active_time_0.1`。它们沿用连续 `budget_event_id/index`、policy digest、execution/artifact head、可信 `created_at` 与 checkpoint authority；不新增维度、文件、独立 head、Attempt、resource kind、aggregate 或产品 route。旧七类 event 与旧 payload 字节仍按原合同读取。为使 B00C05 COMMIT 后、ledger append 前的恢复具有 exact authority，本纠偏明确允许在同一 `ExternalOperation 0.1` 内部 row 的 `prestart.active_time` journal 增加冻结意图；这是唯一获准的 A05 内部字段扩展，不改变 CodeAgentTask/Result/Workspace 等 public 0.1 artifacts 或既有 phase/status/member/port。复用 resource reservation 无法表达 Run-only setup，且让无调用 Attempt 依赖虚构 resource，故不采用。

| Event | 必需 payload 字段 | 约束 |
|---|---|---|
| `active_interval_reserved` | `schema_version`, `interval_id`, `stage`, `attempt_id`, `producer_operation_id`, `owner_operation_id`, `clock_epoch_id`, `start_at`, `maximum_seconds`, `run_remaining_before`, `attempt_remaining_before`, `deadline_monotonic_seconds` | `stage` 仅 `host_setup`/`attempt_active`；每个 producer + stage + Attempt 恰有一个稳定 ID；`start_at == record.created_at`，均取首次 durable freeze 的可信逻辑时间，即使 physical append 稍后发生也不重新采样；maximum 为有限正数，deadline = start monotonic + maximum；remaining 来自此前完整 replay；setup 的 Attempt remaining 为 `null`。 |
| `active_interval_settled` | `schema_version`, `interval_id`, `stage`, `attempt_id`, `producer_operation_id`, `owner_operation_id`, `settlement_operation_id`, `lease_epoch`, `phase_revision`, `clock_epoch_id`, `end_at`, `actual_seconds`, `disposition`, `evidence_digest` | `disposition` 仅 `actual`/`conservative_maximum`；`settlement_operation_id` 指实际 fenced publisher，其 lease epoch/revision 被记录；actual 时 `end_at == record.created_at`，同源同 clock epoch、无回退，秒数精确等于 monotonic 差；超 maximum 的可信 actual 保留原值并进入完整性失败，不能按成功结算；保守时 end/actual 为 `null`、clock epoch 沿用 reservation，按 maximum 扣费；evidence digest 绑定实际 stop/typed absence，原 owner 或其单次合法 handoff 只可结算一次。 |

`clock_epoch_id` 由可信 HostClock 为当前进程时钟实例生成不可复用的 epoch；FakeClock 使用显式稳定的测试 epoch，task、Backend 和 caller 不能自报。进程重启后的跨 epoch interval 必须按 maximum，不尝试跨进程追认 actual。跨 epoch、时钟回退、缺失、无可信 end 或 crash 未结算按 maximum，禁止按 wall time 猜测 actual、自动退款或重开 interval。未结算 reservation 在每个账本前缀均按 maximum；结算后按 actual 或保守 maximum。可信 observed overage 不得 clip，按 A06 integrity/outcome matrix 处理。`producer_operation_id` 在两种 stage 中均指原 ExternalOperation；setup 的 `owner_operation_id` 是该 producer，Attempt 的 `owner_operation_id` 是取得消费所有权的 normal `resume_run` 或原 `resolve_external_interrupt` operation；两个 ID 不可互换。setup 的 public Pause settlement 可由已绑定原 producer 的唯一 `publish_pause` operation 发布，failure settlement 可由既有 terminal winner 发布；必须以 `settlement_operation_id`、该 publisher 的 fencing 和原 owner 的单次 handoff 证明，不能将 publisher 当作新 interval owner 或第二个结算权。

计费公式固定为：

```text
Run.active = setup + backend_aggregate + attempt_interval + non_nested_resource
Attempt.active = backend_aggregate + its_attempt_interval + non_nested_resource
```

setup 只计 Run；Backend aggregate 同时计 Run 和 scheduled Code target；Attempt interval 同时计 Run 和该 Attempt。嵌套 verification 的 resource payload 保留正数 `active_seconds` maximum 与可信测得的非负 actual，独立 replay 仅在证明其完整位于同一 `attempt_active` interval 内时将其秒数标为非叠加；命令次数继续由原 resource reservation 计。正常例子：setup 3 秒、Backend 6 秒、消费 5 秒（其中 verification 2 秒），最终 Run=14、Code Attempt=11；被动等待 100 秒不变。未结算时分别显示 setup/aggregate/Attempt 的 maximum，不能用最终 actual 掩盖 crash 前缀。

## Publication and Owner Order

1. **Setup**：保留 B00C05 首次 `external_operation_reserved` 的单一 SQLite 事务与 COMMIT 边界。该事务从 inbound Transition 和完整 budget replay 采样可信开始时间/epoch，分配原 producer ID，并在 stub 的内部 `prestart.active_time` journal 冻结稳定 setup/Attempt interval ID、setup maximum、计划 Backend aggregate 与后续 Attempt active maximum、原 ledger head、exact setup `active_interval_reserved` record bytes/digest 和未发布状态；task/manifest/aggregate/core/Pause refs 仍为 `null`，此 journal 不是第二份计费 authority。预检 setup+Backend+Attempt maximum 不超 Run 剩余量、Backend+Attempt maximum 不超 target Attempt 剩余量，三段 maximum 均为正数；setup/Backend 的顺序 deadline 不超 producer hard deadline。无法为之后的正常或 recoverable-timeout Attempt 留出正数区间时不得创建 producer，走原 A06 预算停止/升级入口，不能在超时后伪造零时长 Attempt。COMMIT 前 crash 全部 rollback、没有 producer/interval 或可恢复工作；COMMIT 后仅原 fenced producer 可从同一 stub materialize 冻结的 reservation，作为第一个 pre-start ledger suffix，在此之前不得推进该 Run 的其他 budget/execution head，也不得发布 task、manifest、aggregate、core、workspace 或 Pause。终止请求若先到，必须先由原 fenced producer exact materialize 该 event，再由既有 terminal owner 分类；若 event/source 已无法安全发布，原 operation 为 `recovery_required`，已有 terminal owner 的 closure 为 `unavailable`、未取得者为 `not_applicable`，不能跳过 setup 计费后声称完整 terminal。COMMIT 后到 ledger append 之间的 crash 只可 exact 续写原 record，不能重新采样、换 ID、扩大 window 或对外执行 pre-start effect；重复 `reserve` 先完成这一交接或返回明确 pending，不可把未发布 stub 当作可执行 producer。`start_at` 与 record `created_at` 是 stub 事务的可信逻辑 freeze 时间，physical append 可稍后发生。每个后续 pre-start effect 检查 setup/producer deadline；Backend aggregate 必须 exact 匹配已冻结 maximum，Attempt interval 不得扩大已冻结 maximum。task 的 `execution_head` 仍绑定原 inbound Transition；`CodePrestart` 与 validator 证明其后唯一 exact setup reservation，不把 budget event 冒充 Transition。
2. **Pause**：`pause_prepared`、prepared checkpoint 和 paused lifecycle 可以保留 setup maximum。原 `pause_opened_recorded` phase 的同一 frozen suffix 先写唯一 setup settlement，再写同一可信 close 时间的 `pause_opened`，随后 public paused checkpoint；不增加 B02 protocol phase。`pause_opened.proof` 新变体增添 closed `active_time: {interval_id, settlement_execution_head}`，`replay_pauses` 和 prepared/public root validators 必须证明 `paused_lifecycle -> settlement -> pause_opened` 连续 head；旧 proof 形状仅适用无此版本 setup interval 的旧 Pause。close 时间须在最终后缀的 durable freeze 边界采样，不能使用最初 Pause operation reserve 时间。本补充把“Pause 安全发布”的活动时间边界精确定为：原 owner 已 durable 冻结 exact public suffix 且之后不能再执行 setup 领域工作；后续字节 materialization 只是同一意图的恢复发布，不再扩张活动区间。public Pause 后至适用 disposition owner 取得所有权前不推进 budget/execution head；此前的部分前缀按其实际 reservation/settlement 重放。若现有预计算机制无法安全实现此 late freeze，停止本票，不用早采样时间假结算。
3. **Backend**：仍只由唯一 `code_backend_operation` aggregate 的 active seconds 计费。开始于成功 dispatch，结束于 immutable result 与 WorkspaceSeal 都完成的较晚可信时间；轮询、Pause waiting、claim 不延长。未结算按 aggregate maximum。不另开 Backend interval，不把 target Attempt 提前标为 started；Backend 与 setup 不重叠。
4. **Attempt**：normal `resume_run` 与 `recoverable_timeout` 的同一 `resolve_external_interrupt` winner 均在 external-result claim、aggregate settlement、Pause consumed 和 running checkpoint 后，通过各自原 capability 的 frozen `started_intent` 先发布 `attempt_active` reservation，再发布同一可信开始时间的 `Attempt.started`；其后才允许可信消费。normal winner 完成 verifier/bundle 后，由同一消费 owner 冻结唯一 settlement、同一可信结束时间的 `Attempt.finished` 和原 A05 terminal checkpoint，不为该 Code Attempt 新建 Pause。recoverable timeout winner 不运行 verifier：它以 A05 safe-stop、typed failed delivery 和 failed bundle 完成原 scheduled Attempt，冻结同样的 interval settlement/failed `Attempt.finished`/release/final checkpoint。两条路径都保留各自原 owner 和 A05 后继 Transition 责任；无资源调用仍计整个 interval。无可信 end 则保留或显式结算 maximum，按 A06 stop proof 决定 `recovery_required`/terminal disposition，停止自动 retry。每次 Code Attempt 独立，旧 B02 手工 target 不补写新事件。
5. **Verification**：原 `verification_command` 的 `resource_reserved.maximum_charge.active_seconds` 仍为正数且覆盖正 timeout，`resource_settled.actual.active_seconds` 保留可信测量值；原 resource payload/audit 形状不变。对 B03 Code Attempt，replay 仅在同一 Attempt 的 reservation、effect 与 settlement 都可证明处于已打开的 exact `attempt_active` interval 内、producer/owner/epoch/时间及 head 一致时，将该 resource 的 active seconds 作为 nested audit 而不再加到 Run/Attempt active counters；`verification_commands` 仍按原 reservation/settlement 计一次。未结算的 nested resource maximum 必须被 pending parent maximum 覆盖，已结算的 verifier 时长不得越过 parent actual/window；否则 fail closed，不得把不明重叠当作免费。命令 timeout 门禁仍校验可信当前时间、外围 deadline、原 Run/Attempt 开始余量、命令自身 timeout、owner lease 及 policy；不能用外围 full-maximum hold 后显示的 0 remaining 错拒合法内嵌命令，也不能因此放宽物理 deadline。无外围 interval 的旧 resource 路径照旧叠加 active 计费；本票不扩展普通 LLM/tool 的 nested 例外。
6. **Failure tails**：setup deadline/producer hard limit 在 aggregate 前、aggregate 后以及 Pause prepared/paused lifecycle 已部分发布但尚未 public opened 时，都由原 producer 或既有 `resolve_external_interrupt` terminal variant / `close_run` owner 按 A05 snapshot 分类完成 `not_dispatched`、资源有无、Pause absent/prepared/opened 的 typed disposition。该 owner 在可安全 append 且有可信同 epoch end 时结算原 setup interval 的实际秒数；否则保留/显式结算原 maximum，并先证明所有相关 side effect 已停止。已打开的 Attempt 在 verifier 或 bundle failure 后由原消费/interrupt owner按同一规则收尾；无完整 stop proof 或无可信 authority 时走 A06 `recovery_required`/`terminal_closure = unavailable`，不能靠 maximum 伪造 failed Run 或新建 Pause。每个 interval 只能有一个 settlement，failure/takeover/retry 不换 owner、不重复收费；未发布的 frozen suffix 只能 exact materialize。

## Recovery and Compatibility

- `execution.replay`、bounded state、checkpoint 和 public reader 从同一 validated ledger 得到相同 counter；账本自身验证已出现的 interval/resource 及其 policy、epoch、head、nested 时长关系，不能凭缺失的独立 marker 猜测旧记录所属路径。canonical 路径的强制存在性由 `validate_control_root` 与 ExternalOperation 内部 `prestart.active_time` intent、capability/owner、Pause 和原 inbound Transition 交叉证明：stub COMMIT 后、ledger event 前是唯一可恢复 pending prefix；event 后缺 marker、重复/foreign settlement、变更 maximum、stale writer 或 old epoch 一律 fail closed，不能默认为零。
- `validate_control_root` 对 `external_prestart` 验证两个 exact 阶段前缀：setup event 发布后只有唯一 `active_interval_reserved`；aggregate 发布后按序为该 setup event 加原唯一 `resource_reserved`。旧 B02 synthetic 外部前缀仍只含 aggregate。`CodePrestart.commit_task` 从父 advance snapshot 证明最后的 inbound Transition 与 task `execution_head`，再证明其后 setup event，而非假设 ledger 最后一条必须是 Transition。setup 暂存期间的 task/aggregate/core/workspace 继续由原 B02/B03 owner 控制；新 head 必须贯穿 pre-start projection、Pause source、checkpoint、trace 与 failure recovery。`retain_materialized_record` 对新 settlement 的 lease epoch 与 frozen bytes 执行同等 exact takeover 校验；不确定 workspace/verification effect 保留 maximum，走原 A06 `recovery_required`/terminal owner，不从另一个 operation 重试。
- nested verification 只在 B03 Code Attempt 有已验证的 parent interval 时启用：resource payload 保留正 timeout 与实测时长；`remaining_before.active_seconds` 表示原 interval 冻结余量内的可用嵌套时窗，replay 对该字段、`applicable_limits` 与 `maximum_charge` 使用明确版本分支核验 parent deadline/剩余时窗，不沿用已被 parent maximum 占用的普通投影剩余；其他维度、旧 resource 及无 parent 情况仍按原验算。跨 interval、失败/未结算 resource、clock epoch 改变、重复命令或不完整 stop proof 均不得免除资源审计和 conservative maximum；pending parent 最大值只能为其覆盖的 nested 时长计一次。
- Replay/Fork 不补写或重新计时父 Run；source proof 使用父 ledger 的 actual 或 pending maximum，子 Run 仍按 fresh policy/bootstrap 起步。旧 schema 0.2/0.3/0.4、B02 synthetic fixture 的 ledger/event 字节及旧 trace/proof 的格式与 reader 解释不变；旧路径不自动套用新 interval。当前 runtime 源文件变化会改变 `runtime_fingerprint.application_build`，所以受影响的 expected golden 可仅在独立证明后更新真实新 budget 轨迹或该派生 digest/head；逐项保存旧/新差异、来源证据与两个 fresh 根结果。不得改写旧版本语义、历史 fixture 输入、case owner/outcome 或在验收时从当前 runtime 自动生成 expected。新的 canonical Code path 必须有 marker 与完整证据，不能借兼容入口漏计。
- 本补充仅对 B03 canonical path 扩展 A06 七项 closed union、A05 内部 `prestart.active_time` journal 和普通 verification 秒数叠加规则。A04 旧 Pause proof、B02 phase/outcome、A05 其他 0.1 schema/status/member/port、policy limits 及 case/requirement ownership 不变。将最终版本门禁与优先级写入独立合同和核心 source-of-truth。

## Allowed Files

- 本 ticket ready 后只改 YAML lifecycle metadata；`docs/tickets/phase-b-graph-harness/B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md` 仅可在本票完成并复核后改 YAML lifecycle status；新增 `docs/tickets/corrections/B00C09_ACTIVE_TIME_LEDGER_CONTRACT.md`、`docs/tickets/completions/B00C09_COMPLETION.md`，仅向 `docs/tickets/corrections/README.md`、`docs/tickets/completions/README.md` 追加链接；
- `src/lqcd_agent/control/{budget,clock,records,execution,pause,operations,capabilities,coordinator,integrity,projections}.py`：限字段验证、producer/interval owner、精确发布与重放、Pause proof 和失败恢复绑定；
- `src/lqcd_agent/code_agent/{prestart,external_operation,verification_resources}.py`：限 setup/Backend envelope、Attempt/verification 交接与门禁；
- `tests/phase_b/test_b03_active_time_boundary.py`、`test_b03_reservation_boundaries.py`、`test_code_prestart.py`、`test_b03_verification_resources.py`、`test_pause_control.py`、现行 control budget/replay/lease/recovery tests、新 `test_b00c09_active_time_ledger.py`；仅在真实受影响时更新相应 `tests/phase_b/fixtures/`、`expected_traces/`，逐项记录语义与 runtime fingerprint 派生差异并以两个 fresh 根复核；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`、`docs/README.md`、`docs/ARCHITECTURE.md`、`docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`、`docs/EVALS_AND_OBSERVABILITY.md`、`docs/VERIFICATION_GUIDE.md`、`docs/REPO_CURRENT_STATE.md`、`docs/DECISION_LOG.md`：仅同步本票合同和事实。

## Do Not Touch

Phase A frozen tickets/protocol/catalog、B00–B03 正文、B04/B05、已有 completion/correction 历史、legacy graph/coder/default CLI、product route、真实 Backend/provider/network、raw/accepted/secrets、control repo Git state、依赖和配置。不得删 case、改 owner、放宽 old validator、跳过失败路径或重写旧 expected trace 版本。

## Deliverables

- 同一 execution ledger 中的 versioned active interval 事件、canonical producer/consumer 交接、Pause proof 与独立 replay；
- 独立合同、completion record、仅受影响的 source-of-truth 更新和可复核的 fresh fault/golden 证据。

## Acceptance Criteria

- closed event/Pause proof、账本顺序、single-owner、epoch 和兼容规则均有正负测试；现有 6 项反例改为直接证明修复，fresh 进程重放与 live projection 完全一致。B00C05 原四个首次事务切点保持 COMMIT 前 rollback、COMMIT 后 exact stub；新增 stub 已提交但 setup event 未发布的退出与重入反例，验证原 interval/record/digest 只发布一次，未发布前无 task/workspace/aggregate/Pause 效果。
- 正常 3+6+5（含 2 秒 verifier）给 Run14/Attempt11；setup3 加未结算 Backend10 给 Run13/Attempt10；无其他 active charge 的独立 no-call Attempt6 给 Run6/Attempt6（或在已有数值上各增加 6）；等待任意延长不变。两个 verifier 仍有各自正 timeout 与可审计 measured seconds，active 不重复加秒、command count 为 2；跨 interval/越过 deadline、resource 未结算、parent 先关闭和缺失可信时序各有拒绝或保守收费测试。
- normal `resume_run` 与 `recoverable_timeout` interrupt 各自验证原 owner、started intent、failed/success bundle、唯一 Attempt settlement/finished/release；timeout 不运行 verifier，normal Code consumption 不另开 Pause。首次准入须为 setup、Backend 与后续正数 Attempt 区间同时留足 Run/Attempt 窗口；不足时不创建 producer。setup/Attempt/Backend timeout、恰好耗尽、超额、crash maximum、clock rollback/epoch change、pre-Pause absent/prepared/paused-lifecycle partial、Pause 后 head 禁止推进、重复/foreign/stale settlement、同 key retry 均 fail closed 或 exact replay，且不以账面 maximum 替代完整 stop proof。
- B02 old fixtures/0.2 legacy 无迁移、无退化；旧 ledger/fixture 输入和旧 trace/proof 版本语义保持。若当前 expected golden 因新 canonical 预算轨迹或 `application_build` 派生 digest/head 变化，逐项证明并以两个 fresh 根生成独立 expected diff，不更改 case/owner/outcome。受影响的 B02 1410、B03 645 独立 case 集合和原 owner 保持。若确需新增 protocol phase/boundary/runtime obligation 或修改冻结 Phase A bytes，依 Stop Conditions 停止并审定新 corrective，不暗改总数。
- 本票完成只可按真实进度将 B03 从 `blocked` 恢复至 `ready`/`in_progress`；不得声称 B03 28 项、累计 84/131 或 645 runtime 已通过。B00–B02 15/11/30、mapped56/remaining75 是历史基线，本票须报告 fresh evidence。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b03_active_time_boundary.py tests/phase_b/test_b00c09_active_time_ledger.py
pytest -q tests/phase_b/test_b03_reservation_boundaries.py tests/phase_b/test_code_prestart.py tests/phase_b/test_b03_verification_resources.py tests/phase_b/test_pause_control.py
pytest -q tests/phase_b
pytest -q
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

使用新 `/private/tmp/lqcd-agent-b00c09-*` 根及 FakeClock，以独立新进程验证 Run reader、Restart、Replay/Fork、同 owner exact 续写与 stale epoch；保存原 ledger/projection、expected diff、nodeids 和命令结果。B03 full construction/final matrix 由 B03 完成，不以本票 targeted pytest 冒充 28/645 结果。

## Stop Conditions

- 无法在原 B02 phase 集合内完成 Pause late freeze、safe public checkpoint 或旧 proof 兼容；不得用最初 operation reserve 时间假结算。
- 需改 Phase A frozen protocol/catalog、已明确授权的内部 journal 以外的 A05 0.1 schema/status/member/port、policy limits、B04 route、case/requirement ownership，或扩大 Allowed Files；
- 可信 Host epoch、deadline、owner/fence、pre-start effect 与 reservation 顺序无法证明，或必须依赖 wall-time 猜测/独立 mutable counter；
- crash/uncertain effect 无法维持 conservative maximum 与 A06 原 terminal outcome；
- 必需验证无法在允许范围内通过，或必须触碰 Do Not Touch、网络/真实 Backend、raw/accepted 数据。

触发时保持 B03 blocked，记录证据并另提最小纠偏，不把未审定设计写进冻结 ticket。

## Required Documentation Updates

完成时建立独立合同和 completion record；同步受影响的核心 source-of-truth、Phase B Overview、Docs Index、Current State，并向 Decision Log 追加预算/Phase A 合同决定。执行 stale-documentation/TODO scan，只修改本票造成过时的叙述。
