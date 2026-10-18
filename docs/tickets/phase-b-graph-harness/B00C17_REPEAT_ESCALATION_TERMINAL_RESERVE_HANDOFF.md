---
ticket_id: B00C17
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C15, B00C16, B04]
---

# B00C17：重复失败升级与 Human terminal reserve 接续

## Goal

修复 C15 fingerprint 接入后，重复失败升级产生容量不足的普通 Human Pause 的生产路由缺口，并完成因此阻塞的 C16 原全部验收。C15/C16/B04 是纠偏目标，不要求先 completed。创建不代表批准或实施；三票保持 blocked。本票不直接完成 C15 或 B04。

## Why

C16 已形成 canonical audit/逐 owner 来源候选及七组双 fresh expected；当前 C13 回归仍有三项生产失败：`test_real_stop_uses_five_remaining_control_without_work[reject_or_hold|approve_with_conditions]` 与 `test_out_of_scope_stop_response_can_be_corrected_without_work`。

原产品 `phase_b_test` 端口运行相同 Reviewer revalidation 材料，首次 automatic review 后同科学 failure 的 occurrence 从 1 到 2。Coordinator 因 repeat 提前选择普通 Human 升级，没有按受限预算形成原 `budget_stop/stop_sequence_id`。发布后的 Pause 剩余 control=5；原 `Pause.resume` 普通入口要求 `1 + terminal_reserve.control_attempts = 6`，遂在提交 response/启动 validator 前拒绝 `Human validation lacks reserved terminal capacity`。现有 terminal sequence 则使用原 3 control/4 transition 校验。不能放宽 Resume、削减 reserve、伪造终态或改变 fixture 科学材料来绕过本反例。

六份原端口双 fresh 反例保存在 `/private/tmp/lqcd-agent-b00c16-execution-20261007-p5r0266z/terminal-stop-counterexamples/`，涵盖上述三种 response；原失败专项日志为 `/private/tmp/lqcd-agent-b00c16-human-handoff-regression.log`。这是 production 路由问题；C16 禁止修改 `src/`，因此触发其 Stop Conditions。

## Read First

- [AGENTS](../../../AGENTS.md)、[文档入口](../../README.md)、[工作流](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)；
- [C15](B00C15_PRODUCT_FAILURE_FINGERPRINT_AND_GRANT_SOURCE_HANDOFF.md)、[C16](B00C16_CANONICAL_CODE_AUDIT_SOURCE_HANDOFF.md)、[B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)冻结正文及各 completion；
- A01/A04/A06/A07、Protocol/catalog；C13 completion/来源合同、B04 maintenance；
- `graph/{routing,nodes,analysis_graph}.py`、`control/{pause,budget,execution,operations}.py`、C13 stop/ordinary capacity 测试、C15 Grant/故障测试及 C16 来源/消费者测试。

## Scope

- Coordinator escalation 的原预算与 Human admission 接续；在保留 risk/repeat 升级语义时，判断原普通 Human validator 与 terminal reserve 是否可达；
- 普通入口不足但原 terminal tail 可达时，使用原预算 stop、原 sequence 与原 terminal-only Human/Coordinator/Memory/close 端口；
- 原 Human、C15 Grant 及 C16 新版本来源候选的回归与剩余整票验收交接。

## Non-goals

- 不改预算收费/算法、limits、reserve、Grant 权限/发行阶段/目标/单次消费，不增加 Work 机会；
- 不实现 Code parent、B04 owned 或 B05 adapter，不改科学接受与安全优先级；不 commit/push。

## Allowed Files

- `src/lqcd_agent/graph/routing.py` 仅 Coordinator repeat/risk→Human 的容量前置判断及原 budget-stop 路由；`nodes.py` 仅相应原 terminal-only Request/continuation 的一致接线；
- `tests/phase_b/test_b00c17_terminal_reserve_handoff.py`、`fixtures/b00c17/`、`expected_traces/b00c17/`；C13/C15 专用 tests 只补相应原合同回归，保持既有 nodeids/observe IDs/原业务结果；
- C16 原 Allowed Files 中的 harness/collector/tests/fixtures/current Human 接线，仅完成已批准的同版本来源候选及原全部验收，不增 profile/proof 字段或科学 recipe；
- `acceptance_matrix.json` 仅 B00 A07-META-006/015 的上述 meta，保留原 owner/IDs/分类；
- 前置 expected 仅审定 runtime fingerprint 与经完整 preimage 证明的派生 head/reference；新 C16/C17 expected 可同步由本票修复及真实 runtime fingerprint 更新产生的已批准来源结果。Code 的科学 config/context/FP 如依法包含更新后的 runtime fingerprint，必须按冻结 C15 recipe 完整重算并逐项审计其派生值，不能删字段或将其当作任意可替换摘要；
- 本票 YAML、新独立 contract/completion，C15/C16/B04 completion 与 maintenance 追加，Current State/Overview/索引及必要源文档/Decision Log。

## Do Not Touch

- `control/pause.py` 的原 Resume 门槛、budget primitive/计费/limits/reserve、production wire、authority、Grant 消费及科学接受；
- 其他 production、Phase A、冻结正文、旧 sealed evidence、旧 trace 0.1–0.7 解释、旧 C11/C12/C13 0.7 expected；
- B00 schema/catalog/cases/Session/failpoint判定/exclusion、B02/B03 owned 语义/owner、legacy tests、依赖/configs、raw/outputs/accepted/secrets、外部系统与 B05。

## Requirements

1. 使用真实 replayed dimensions 与原 immutable policy/reserve 语义。普通 Human admission 必须预留实际 publisher/Transition 之后原 Resume validator 需要的容量；不得改变实际 charge、projected counters 或剩余值，不复制另一套预算状态。
2. repeat/risk/ambiguity/security/scientific 优先级及诊断保持。容量充分时仍走原普通审批/validated BudgetGrant 路径；route allowance 耗尽但合法 Grant 及所有 hard ceilings/reserve 均可满足时，不得一律降为 terminal stop。
3. 普通入口不可达而 terminal tail 可达时，依真实容量不足冻结原 budget-stop facts，sequence 由原 Run/source Attempt/reason 生成并由原 Transition 传播。不得把普通同意变成停止证明或科学接受；terminal continuation 不发行 Grant、不调度 Work。
4. terminal tail 也不足时，依原可证明 owner/fence 的 close/recovery 规则处理，不能创建无法完成的 Pause、降低门槛或制造 closure。authority/停止事实不可证明时保留原 fail-closed 状态。
5. 拒绝错 owner/epoch/head/Request/response/action、terminal Work/Grant 越权、非法重复消费及重新执行 effect。已 committed 的同 key/exact request 重试只读复用原结果；合法未完成且具有原 authority 的 exact publication 前缀只能补齐原冻结 suffix，不重新分配 Attempt/Transition、领取 started invocation 或重跑 consumer。不确定/冲突前缀保持原 recovery/integrity 分类。原 invalid response 可在原容量允许时纠正，response 保持 single-use，effect 不增加。
6. 保留原 C13 三项反例 fixture 科学材料和 phase_b_test policy，不改变输入来规避 repeat；修复须恢复其原 halted/nonaccepted、四条同 sequence 与不执行 Work 的验收。
7. 原 C15 科学 FP/Grant/故障表与 B04 产品职责保持。完成后逐项独立复核 C16 全部冻结验收；只在 C16 真正通过后完成其交接。C15/B04 仍需各自剩余验收，不自动 completed/ready。

## Deliverables

- 最小生产 admission/terminal 接线修复及独立 maintenance 记录；
- 双 fresh 原端口 before/after raw、原 owner/容量/sequence/response/effect 证据与专用 meta；
- 固定 expected/preimage 审计、C16 原全部验收、独立 completion 与剩余 C15/B04 清单。

## Acceptance Criteria

- 两 fresh 根重现 Reviewer 同科学 occurrence 1/2；修复后三项原 C13 测试全部通过：control=5 的合法两种 terminal response 经原端口 halted，terminal 非 accepted，原四条同 sequence，无新增 Work；错 approve_rerun 仍 invalid，随后合法纠正可安全收尾；
- 普通容量充足、仅 ordinary 不足而 terminal 可达、两者均不足，以及 control/transition 各自边界均用原端口覆盖；risk/ambiguity/security/科学 guard、ordinary approval 与合法 BudgetGrant 发行/单次消费保持；
- lost authority、wrong owner/epoch/head/action、非法重复消费及 effect reentry 不制造 terminal/Grant/Work；已 committed 同 key/exact request 重试只读复用原结果，合法未完成 exact publication 前缀仅由原有效 authority 补齐冻结 suffix，不新增 Attempt/Transition 或重复 effect，不确定/冲突仍按原 recovery/integrity 分类。typed unknown token/cost 与 maximum 语义不变；
- C11/C12/C13 原结果/invariants 与 C15 原专项通过；C16 原 canonical/owner/科学变化/拒绝/四消费者及当前入口交接全部通过，meta 不计 B04 owned；
- 同一当前固定输入 Session 实跑完整 exact collection/suite，独立原验证器检查 B02 1410/B03 645，fresh construction 15/11/30/28，final 的具体缺口仍只有 47 coverage/144 binding/15 exit；不 skip/xfail/过滤、历史材料不 retag；
- 保持 131 required、84 mapped、47 remaining、2199 cases、324 boundaries、28 post-claim、B04 144、15 exit 和原 owner 集合；不将当前局部修复解释为 C15/B04 整票完成。

## Verification

批准 ready 后使用原 Session/native 和有界分批验证；以下 focused 命令不能替代上述完整 gate：

```bash
/opt/anaconda3/bin/python -m pytest tests/phase_b/test_b00c17_terminal_reserve_handoff.py tests/phase_b/test_b00c13_human_continuation.py -q
/opt/anaconda3/bin/python -m pytest tests/phase_b/test_b00c15_product_failure_sources.py tests/phase_b/test_b00c15_budget_publication.py tests/phase_b/test_b00c16_canonical_code_audit_sources.py tests/phase_b/test_b00c16_trace_consumers.py -q
/opt/anaconda3/bin/python -m pytest --collect-only -q
```

Review 阶段只检查模板、依赖、links、scope、冻结摘要与 diff，不实施路由修复或创建完成记录。

## Stop Conditions

- 需要改原 Resume/budget 门槛、limits/reserve、wire/schema/proof、authority/Grant权限或科学 FP recipe；
- 必须改原反例科学输入/原 outcome、弱化 guard、伪造 owner/停止/closure、覆写旧 expected 语义或扩大 exclusion 才能通过；
- 需要未列 profile/production/文件范围，或无法保存与解释真实前缀/单次性；
- 必须跳过失败、过滤 required collection、使用历史 Session 或缩减 owned 集合验收。触发即 blocked，保存反例另审。

## Required Documentation Updates

批准执行后新增独立 contract/completion，追加 maintenance、C15/C16/B04 交接、当前状态/Overview/索引及实际源合同/Decision Log。创建阶段只记 review 与三票 blocked 事实，保留历史，不宣布实施、整票通过或恢复 ready。
