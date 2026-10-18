---
ticket_id: B00C19
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C17, B00C18]
---

# B00C19：Human 容量不可达阈值的验收分层

## Goal

仅补充 C17/C18 容量验收方法：可达路径继续由原端口实跑，原固定 policy 下不可达的独立 transition 阈值由可达性证明和明确标识的纯合同边界测试验证。不改变生产容量、预算或 required/case/owner 集合。C17/C18 是纠偏目标，不要求先 completed；B00 须已 completed。

本票仍 review，创建不代表批准或实施。C18/C17/C16/C15/B04 保持 blocked；本票不能替代 C18 H1–V2 其余验收或宣布整票通过。

## Why

C18 两项候选修复的 3 组双 fresh 原端口测试通过，另有 2 项 C13 回归通过。执行前覆盖表的可达性补查发现：C17 Acceptance 第二项“control/transition 各自边界均用原端口覆盖”及 C18 H1/Acceptance 继承要求包含原合同下不可达的 transition 阈值。

原 execution replay 要求每个非 END Transition 绑定唯一已分配 Attempt 的 inbound_transition_id；原产品 END 只有一次，因此 `T <= W + C + 1`。两固定 policy 的 `(Wmax,Cmax,Tmax)` 分别是 balanced `(16,16,40)`、phase_b_test `(8,8,20)`，Grant 不扩全局上限。若 control 剩余至少 k，则 transition 剩余至少 `Tmax - Wmax - Cmax + k - 1`。

| 路径 | control/transition 所需容量 | balanced 的 transition 保守下界 | phase_b_test 的下界 |
| --- | --- | --- | --- |
| 普通 Human publisher | 7/8 | 14 | 10 |
| terminal Human publisher | 4/5 | 11 | 7 |
| 普通 repause | 6/7 | 13 | 9 |
| terminal repause | 3/4 | 10 | 6 |

上述下界均大于要独立测试的 transition 阈值。即使允许 control 判定失败，真实普通/terminal invalid validator 执行前原 Resume 已要求 control 至少 6/3，执行后至少 5/2；两个 repause 路径在 phase_b_test 的 transition 剩余仍至少 8/5，分别高于 7/4。包含一个 END 的上界已比 Human 接续真实可达集合更宽松。

证明依赖原 `control/execution.py` 的 Transition/Attempt 绑定和预算计数、`records.py` 的 null target、`operations.py` 的 END admission、`budget.py` 原 limits，以及 `pause.py` 原 Resume 门槛。当前所有 6 份 fresh Human ledger 均符合计数关系；对放宽后的有限计数集合枚举也不存在独立 transition 阈值实例。证明报告：`/private/tmp/lqcd-agent-b00c18-execution-20261007-8tu_i792/capacity-reachability-conflict.json`。数学证明与实跑见证分开，不把枚举当 runtime evidence。

## Read First

- [AGENTS](../../../AGENTS.md)、[文档入口](../../README.md)、[工作流](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)；
- [C18](B00C18_ORDINARY_REPAUSE_CAPACITY_SOURCE_HANDOFF.md)、[C18 执行记录](../completions/B00C18_COMPLETION.md)、[C17](B00C17_REPEAT_ESCALATION_TERMINAL_RESERVE_HANDOFF.md)及其冻结依赖；
- 原 A01/A04/A06/A07、CONTROL_PROTOCOL_0_4 与当前 acceptance catalog；
- 上述生产计数/身份代码及 `ProductRouteAdapter.repause`、`select_product_route`，只读核对。

## Scope

- 固定 policy 下各容量路径的可达性证明及原端口见证；
- 不可达 transition 独立阈值的纯函数合同测试，检查 required−1、required、required+1；
- C17/C18 对应验收条款的窄补充及独立文档交接。

## Non-goals

- 不修生产、不改容量/计费/权限/恢复/科学规则，不扩大 C18 production 范围；
- 不替代 C18 其余 Human、source、Grant、publication、四消费者或全量验收；不 commit/push。

## Allowed Files

- `tests/phase_b/test_b00c17_terminal_reserve_handoff.py`、`test_b00c18_ordinary_repause_handoff.py`：仅可达性证明、原端口见证及标识为 contract-only 的容量谓词测试；
- 新 `docs/tickets/corrections/B00C19_HUMAN_CAPACITY_REACHABILITY_ACCEPTANCE.md`、独立 completion、本票 YAML；C18/C17 completion 追加、必要 Current State/Overview/索引/Verification Guide/Decision Log。

## Do Not Touch

- 所有 production、policy/limits/reserve、runtime/schema/proof/profile、authority/Grant、Phase A、冻结正文；
- B00 Session/验证器/registry/cases/分类/owners/exclusions、旧测试与 fixed expected 语义、sealed evidence、依赖、外部系统、raw/outputs/accepted/secrets。

## Requirements

1. 对当前 allowlisted policy 原值独立验证计数不等式及每个路径的上下界，保存源码/输入摘要、推导、枚举结果和实际 ledger 见证。不可只枚举测试中碰巧出现过的路径来声称不可达。
2. 可达的 ordinary/terminal/control 边界、invalid→纠正/安全关闭仍须原端口双 fresh 实跑；不得把任何实际可达故障改成纯合同测试。
3. 仅对上述证明不可达的独立 transition 阈值，允许向原纯容量 adapter/selector 传入明确构造的内存合同 view，验证每维 required−1/required/required+1 和两维组合。不得将该 view 写入 Run、修改 policy/ledger/持久化 counter、调用 Agent/Backend，或用其生成 runtime trace/observe_case/owned evidence。
4. 此类测试命名与结果必须标识 contract-only；它证明防御性容量谓词，不证明可执行 Run。与原端口可达性证明联合满足 C17/C18 对应 transition 边界项，不能单独满足实际来源/authority/Human 验收。
5. 这一补充只替代 C17/C18 中“不可达 transition 独立阈值必须原端口实跑”的方法要求，保留全部业务期望、计数、拒绝规则及原 131/84/47、2199、B02 1410/B03 645/B04 144、15 exits/owners；不回写冻结正文。
6. 若当前 policy/计数或合法端口可以构造反例，证明测试必须失败并重新核验，不能扩大不可达清单。C18 已有执行授权保持；本票完成后核对输入/冻结摘要，按原授权恢复 C18 执行全部剩余工作，C15/C16/C17/B04 不自动完成或恢复。

## Deliverables

- 可复核的推导、原端口见证与明确分层的合同测试；
- 独立补充合同/completion、C18 对应覆盖项交接。

## Acceptance Criteria

- 两原 policy、四条容量路径的可达性证明与实际 ledger 见证一致；
- 原容量函数的 transition 临界值与组合在 contract-only 测试中正确拒绝/允许，无 runtime/effect 或 owned 声明；
- C18 原三组双 fresh repause 和受影响 C13 回归保持；最终全量与同 Session 验收继续由 C18 V2 完成，不能提前声明通过；
- frozen/source/policy/旧 evidence/owners 不变，文档明确哪些是运行证据、哪些是证明/合同测试。

## Verification

批准 ready 后，使用原 pytest 运行上述专用测试及受影响 C13 节点，保存原始日志、推导和双 fresh 根；执行前后核对生产/冻结正文/验收清单摘要。进入 C18 最终固定输入 Session 时这些测试纳入全仓 exact collection，不跳过或过滤。review 阶段仅核验文档、链接、依赖、scope 和证明，不实施合同 view 测试。

## Stop Conditions

- 需要修改生产/policy/计费/authority/schema/原 required 集合或将实际可达路径降格为合同测试；
- 计数不等式或唯一 Transition/Attempt/END 前提不能由原合同证明；
- 需要修改冻结正文、伪造 Run/effect/owner/终态或把 contract-only 结果计入 owned。

## Required Documentation Updates

执行后新增独立补充合同/completion，追加 C18/C17 覆盖交接和实际入口结论，更新当前状态/Overview/索引及必要 Verification Guide/Decision Log。创建阶段只记录 review 与阻塞依据，不宣布批准、实施或整票通过。
