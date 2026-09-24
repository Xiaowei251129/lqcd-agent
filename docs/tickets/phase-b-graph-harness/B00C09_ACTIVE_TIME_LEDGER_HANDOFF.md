---
ticket_id: B00C09
phase: phase-b-graph-harness
status: review
type: corrective-contract-design
depends_on: [B00, B01, B02, B00C05, B00C06, B00C07, B00C08]
---

# 审定活动时间账本合同与 B03 交接

## Goal

形成可审查、版本明确的活动时间记账补充合同，关闭 A06 的 Host setup Run-only 与 Attempt active interval 在 B01/B02 持久化回放中的表达缺口，再明确 B03 的实施范围。这是一张待审设计票；不授权现在增加 budget event、改写历史账本或把 B03 标为完成。

本票与 B00C08 的职责不同：C08 已授权 canonical 材料与 source trace 的交接，没有授权改变预算事件集合、计费维度或前置预算轨迹。

## Reproducible Problem

`tests/phase_b/test_b03_active_time_boundary.py` 的 6 项反例/对照全部通过；“通过”表示缺口被稳定复现，不表示计费功能已实现。

- 使用真实 producer、CodePrestart task/manifest/aggregate/core、独立 Git base 的物理 workspace，以及 B02 public Pause publication。
- Trusted FakeClock 在 Host setup 中前进 3 秒。`clock.measure` 正确给出 Run=3、Attempt=0；Pause 已 committed、Run 已 paused、Code Attempt 仍 scheduled。
- 真实 ledger replay 却仅给出 aggregate maximum 的 Run=10、Attempt=10。应至少为 Run=13、Attempt=10；即使恢复时对尚不能精确封闭的 setup 保守计费，也不能遗漏这 3 秒。新 Python process 只读重放得到同样结果。
- 独立纯 ledger 对照中，Attempt started 到 finished 为 6 秒且没有资源调用，当前 active counters 仍均为 0。
- 当前预算 closed union 仅接受 7 类 event、4 类 resource kind；Run-only vector、新 `host_setup` kind 或独立时间 event 均被拒绝。把时间加入现有 resource `active_seconds` 又会同时扣 Run 和该 Attempt。

原始 ledger、实际 Pause 结果、两个进程的 dimensions 在 `/private/tmp/lqcd-agent-b00c08-review/active-time-report.json`；测试日志为同目录 `active-time-boundary.log`。该证据不涉及 Backend dispatch、canonical bundle 或 B03 28/645 验收。

## Contract Sources and Scope Decision

- A06 [Active time](../phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)：Host setup 只计 Run；Backend active 到 result 和 seal 均完成；被动 paused waiting 不计；Attempt started 到结束包含 verification；缺失 interval/crash 使用明确的保守计费。
- B01 `clock.measure` 已交付分类算术，但 `execution._budget_projection` 只累计 resource actual/maximum，未接入上述完整 interval。
- `records`/`budget` 是 closed wire；不能把时间藏进自由文本、诊断 error、artifact path 或 caller 自报计数。
- `replay` 的 budget 由 validated policy/execution ledger 派生。只在 Code 对象、coordinator 私有 row 或 mutable projection 中维护余额，不能解决独立 reader、Restart/Replay/Fork 与下一次 admission 的一致性。
- B03 Stop Conditions 明确禁止未经纠偏改变 schema/A06 reservation semantics；其 control 文件许可也不是通用预算合同设计授权。

现阶段不能简单宣布“修改 replay 即可”：Host setup 的起点/结束、崩溃 uncertainty 与普通 Attempt 中资源调用的重叠需要同一份 durable 证据和计费规则。现有 ledger timestamps 只证明记录写入时间；不能回填为未记录的 setup 起点，也不能把整个 wall-clock 间隔当成可靠执行时间。

## Proposed Design Work

推荐保留单一 execution ledger 和现有 resource reservation authority，增加显式版本化的时间证据合同。设计交付必须包含可逐字段审查的 schema 与示例，不以本节的方向描述直接授权 runtime 修改。

1. 对比两种表达：复用带版本判别的 budget resource 变体，或增加独立的 closed active-interval budget 变体；给出唯一选定方案、为何另一方案不能更简单满足合同，以及旧记录的 reader 行为。
2. 冻结 Host setup、Backend active、Attempt active、verification 与 paused waiting 的边界、owner、clock source/epoch、唯一 identity、最大窗口、实际/保守结算、缺失与回退分类。
3. 用明确计算式避免重复计费：Backend interval 属于 scheduled Code target，独立加到 Run/Attempt；verification 已在消费 Attempt interval 内，不能再重复累计其时长。资源调用次数仍按原 reservation 计数。
4. 明确 pre-start DAG 中新证据的发布位置，以及 public Pause 之前的预算证明、Pause 后不推进 head 的约束、唯一 aggregate、当前 external/resume owner 和安全失败收尾。不得增加虚假 Attempt 或重复 aggregate。
5. 覆盖实时 admission 与 hard deadline：不仅结束时账面正确，Host setup、verification 和无工具调用的消费阶段也不能超过 Run/Attempt 剩余窗口。Restart 后不可因遗漏或退款获得额外窗口。
6. 审定 replay、bounded state、checkpoint、pause/dependency、owned publication prefix、failure closure、historical readers 的兼容规则与修改范围。不能默默改变旧 0.2/0.3/0.4 的解释，也不能靠正常流程缺字段时默认零通过新路径。
7. 先产生受影响测试/trace/golden/protocol 的精确清单，区分 runtime fingerprint 派生变化与真实 budget semantics 变化。后者不在 C07/C08 原授权内，必须在本票最终交接中显式审定。

## Design Deliverables

- 独立版本化补充合同及完整正常/崩溃/overlap/超额例子；保留冻结 Phase A ticket、protocol/catalog 原文，明确补充与旧合同的适用关系。
- implementation handoff：逐文件范围、public schema/version、发布与恢复顺序、兼容策略、具体验收命令及 Stop Conditions。
- 单次 3 秒 setup + 6 秒 Backend + 5 秒消费（其中 2 秒 verification）例子的最终 Run=14、Code Attempt=11；被动等待任意延长不得改变结果。分别展示未结算 maximum 和最终 actual 的适用时刻，不以这个最终数值覆盖 crash maximum。
- no-call Attempt、多个命令的重叠去重、多次 Pause、setup 中断、clock 回退、old epoch、Run/Attempt 剩余窗口恰好耗尽、前后进程独立 reader 的反例设计。
- 原 owner 不变的验收影响清单：当前 mapped56/remaining75、B02 1410、B03 645、B04 144 为当前事实。若确需新增 protocol phase/boundary/runtime obligation，必须显式列出增量及新总数，不能沿用旧数声称覆盖新增语义。
- 完成记录与当前状态同步。设计完成不等于 runtime 修正完成，更不等于 B03 完成。

## Allowed Files for the Design

- 本票在 ready 前可审改，ready 后仅 YAML lifecycle metadata；
- 新增独立合同 `docs/tickets/corrections/B00C09_ACTIVE_TIME_LEDGER_CONTRACT.md`、corrections index 追加；
- `docs/tickets/completions/B00C09_COMPLETION.md`、completion index 追加；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`、`docs/README.md`、`docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`：仅在合同正式审定后追加；
- `tests/phase_b/test_b03_active_time_boundary.py`：只补充只读/临时 Run 的合同反例，不改为未实现功能的通过证据。

## Do Not Touch

设计阶段不改 production、frozen tickets/protocol/catalog、旧 goldens、matrix、runtime inventory、legacy runtime、依赖、产品 route、真实 Backend、raw/accepted/secrets 或控制仓库的产品执行行为。未获审定的 runtime handoff 不能借本设计票自动执行。

## Review Gate

本草案有意只授权设计，不预填未审定的 wire 方案。用户可批准开展设计；设计输出及其 implementation handoff 必须形成具体可审查的合同后，再明确批准运行时修改。原 B03 的执行授权保留，但该合同边界审定并完成所需前置后才能恢复。

若选择直接扩充为 implementation corrective ticket，应先在本票 ready 前补齐上面的具体 schema、文件清单和验收变更；不得在 ready 后扩写被冻结正文。
