# B04 接续执行审查与必修缺口

## 状态与范围

2026-10-01，用户确认本次核验目标是B04，并要求按审查建议补齐缺口。本轮修订仍为`review`的[B00C10](../phase-b-graph-harness/B00C10_ORDINARY_RESOURCE_TRACE_HANDOFF.md)，补齐来源、fixture和验收边界；不提升ready或实施新版本。B03已completed，B04仍blocked，冻结正文不改。以下是实际反例与恢复后必修项，**不是修复完成记录**；未来实现另追加[B04 maintenance](B04_MAINTENANCE.md)和[completion](../completions/B04_COMPLETION.md)。

## C10 前置修订

- Trace0.5 ordinary settlement `missing_source -> kind`阻塞已在两个fresh production根复跑确认，2项测试通过。新trace0.6/proof0.3须验证actual input/config/return与原ledger/owner闭包，不能靠只补collector或更新golden解决。
- 确定性身份采用待审的Host identity fixture窄例外：只作用于四个project-owned模块的UUID提供对象，原分配函数和所有identity校验仍执行，raw身份字面值保留；不修改process-global UUID、route/state/ledger或ephemeral exclusions。
- Collector被动捕获actual preimage，在Host修改diagnostic/content前冻结；settled structured failure与未结算异常分别验证，不虚构settlement。
- Mixed仅组合同一fresh Run内原B02/InvocationLeases资源入口与原B03 ports，证明来源交接；不依赖未实现B04 Code parent，不计47/144或产品edge通过。
- 四条trace消费路径、failure/grant/stop引用、合法材料变化的exact差异和源码fingerprint golden审定均已纳入C10待审验收。此修订未使任何新合同或fixture例外生效。

## 已复现的 B04 实现缺口

### 1. Human validator 出版与接续

实际failed Analysis进入Human Pause；合法`approve_rerun`经原`resume_run`得到submitted/validated响应和succeeded validator Attempt，但resume为`recovery_required`，错误：`Producing Attempt output is missing its registered artifact: attempt_000005:approval`。Run留在running，未进入新的Coordinator/Analysis。

来源位置：[ProductNode Human validator](../../../src/lqcd_agent/graph/nodes.py)、[原control完整性检查](../../../src/lqcd_agent/control/integrity.py)。Validator outcome的输出引用与实际registration没有闭合，不能通过降低A03校验修复。原external validator physical node为`human_approval_gate`，canonical产品node为`human_gate`；其接续也须明确使用原Attempt kind与实际committed Transition。

另有尚未走到的静态冲突：[product selector](../../../src/lqcd_agent/graph/routing.py)给所有Human route附`stop_sequence_id`，带此sequence的Work dispatch又被禁止。普通审批不得消耗真正terminal stop reserve或阻止有效的后续授权工作；预算stop的terminal tail仍禁止恢复Work。此项是源码检查结论，不声称已完成端到端复现。

恢复后验收：

- Validator无domain输出时复用原B02合法no-output合同；如有输出，按原A03规范注册，finished refs逐项匹配。不得补假artifact或绕过integrity。
- 合法响应先由原resume消费和验证，validator完成后由**新的**`advance_run`提交`human_gate -> decision_coordinator`产品edge；external control Transition不混入17条产品rows。
- approve/reject/hold、invalid-response repause/halt、重复提交和重放均验证snapshot/scope/single-use、无重复Agent调用。
- 普通批准可在原风险/预算条件下进入授权Work；真正budget terminal sequence只能完成控制/Memory/closure，不派发Work。Physical node与canonical kind衔接不重命名legacy入口。

反例：[实际响应与历史](/private/tmp/lqcd-agent-c10-review-b7rw__mp/valid-human-resume.json)、[独立复现与错误栈](/private/tmp/lqcd-agent-c10-human-review-dpewqths/human-resume-error.json)。

### 2. Ordinary resource overrun / uncertain 收尾

实际Planner调用获准1秒，仅通过FakeClock令实际返回耗时2秒，原reservation留存、无settlement，完成时报`Invocation cannot finish with unsettled resources`，Run留在running。Maximum未被退款，也未重派发；欠缺的是原authority下的typed recovery/stop/closure。

来源位置：[run_resource](../../../src/lqcd_agent/control/budget.py)、[Invocation completion](../../../src/lqcd_agent/control/capabilities.py)。

恢复后验收：

- 可信actual只在原admitted window及原owner/epoch内结算一次；跨clock、exception、overrun、crash的不确定效果保留maximum，无退款或自动重跑。
- 原reservation前/后、effect前/后、settlement publication前/后和新进程恢复分别验证；started/uncertain不能借重新进入图执行同一effect。
- 原A06/B02 stop分类决定recoverable/failed/halted/unavailable与Pause disposition、settlement/release/Run closure，不能无限留running，也不能把uncertain冒充success。
- Global active/resource耗尽时，确定性的控制尾部仍可安全收尾；不得产生新的provider/tool/accepted-memory副作用或超过absolute ceilings/terminal reserve。
- 调用边界的timeout和Host deadline须有可验证的有界返回/停止策略；传递`timeout_seconds`及返回后检查不能独自证明被阻塞的effect已停止。若现有primitive不足而需改变公共恢复/containment合同，按AGENTS另审。

反例：[真实overrun prefix](/private/tmp/lqcd-agent-c10-resource-review-p7f5j9z3/overrun.json)。C10只验证该prefix来源，不代修此收尾。

### 3. Agent 保留字段覆盖 Host identity

仅在structured Agent content加入`run_id=foreign-run`、`producer=foreign-role`，真实产品图仍completed，注册的`method_plan.json`带foreign值。来源：[ProductNode成员序列化](../../../src/lqcd_agent/graph/nodes.py)中`**content`覆盖先写入的Host字段。

恢复后验收：

- Agent输出在任何member publication前检查保留字段：`schema_version`、case/run/cycle/attempt/transition identity、`attempt_kind`、`node_name`、`producer`及Host派生`status`不得覆盖；按现有identity envelope确认实际闭合字段，不将Agent payload解释为control authority。
- Foreign/相同值覆盖均拒绝，不能仅靠序列化顺序静默丢弃非法字段；合法domain/science内容保持原材料。
- Wrong target/parent、越scope证据、伪造Human authorization和完整audit直接进入prompt的负例仍在target副作用前拒绝。Raw bytes、registration、diagnostic与实际ledger身份逐项相等。
- 负例没有canonical member/registry/Transition/accepted-memory publication；必须区分诊断调用已实际发生与后续被拒绝的Host publication，不能声称LLM调用也没有发生。

反例：[已完成Run及foreign成员](/private/tmp/lqcd-agent-c10-resource-review-p7f5j9z3/host_identity_override.json)。

上述修复分别在B04既有graph/control Allowed Files与原Human、budget、Agent边界验收内，不授予C10修改src的权限。实际修复若改变schema/architecture/authority/public contract、Allowed Files或验收边界，仍须独立纠偏。

## 前置回归与 Golden

本轮实际执行相关137项：**132 passed、5 failed in151.36s**。文件为`test_fake_code_agent.py`、`test_code_agent_trust_boundary.py`、`test_b03_analysis_handoff.py`、`test_b03_repeat_code_attempts.py`和`test_a05_source_traces.py`。五项失败都是fixed golden的exact比较：

| Golden | normalized字段差异数 | 双fresh根相等 | 旧raw重建当前expected |
| --- | --- | --- | --- |
| a05_normal | 12 | 是 | 是 |
| a05_timeout | 10 | 是 | 是 |
| a05_failed | 7 | 是 | 是 |
| a05_unavailable | 6 | 是 | 是 |
| b03_repeat_code | 22 | 是 | 是 |

Raw fingerprint的`application_build`与`graph_topology`随B04源码改变；normalized差异仅head/digest/reference，event/route/outcome不变。尚未更新expected；原材料、lease、usage、owner或流程差异不能套用fingerprint例外。其他golden与当前完整回归仍须检查，不能把五项视为全部剩余失败。

审定资料：[双根摘要](/private/tmp/lqcd-agent-c10-golden-review-kzamifyq/summary.json)，同目录保存五份current raw与逐字段diff。

历史B03/B02同Session的645/645、1410/1410和全仓3514/Phase B3189报告仍存在；当前worktree input不同，历史passed不代替当前fresh结果。见[输入核对](/private/tmp/lqcd-agent-c10-status-review-3d2_kddt/baseline.json)。本轮protocol validator、generator --check、inputs loader和diff检查通过，131 required/84 covered/remaining47、2199 cases保持；B04冻结body SHA-256仍`3a1e273839579721e330c02fb430fcec615b6d5e7428e051a02255f2196134ca`。

## 恢复顺序与完成门槛

1. C10经用户批准ready、冻结后实施并通过自身来源与前置验收；原0.5拒绝及旧版本语义保留。
2. B04按原授权恢复；先修上述三项及其关联Human/terminal/作用边界，逐项追加maintenance与passing证据。
3. 完成B03 Code parent/Fake/fresh Analysis、四层fallback、Host fingerprint repetition、single-use grant及完整terminal/recovery。
4. 当前同输入完成B04 47 construction/144 runtime、前置B00–B03 construction及B02/B03 owned runtime、全部golden和full pytest；global final负向仅保留B05的15项exit adapter缺口。

当前未完成第1–4步。本记录、passing反例与contract-only meta都不计B04 owned runtime通过；Phase B仍未完成。不以C10完成宣称后续没有阻塞，后续新scope/contract冲突仍按冻结Stop Conditions处理。
