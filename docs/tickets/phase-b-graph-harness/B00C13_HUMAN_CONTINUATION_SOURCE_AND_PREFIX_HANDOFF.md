---
ticket_id: B00C13
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C11, B00C12, B04]
---

# B00C13：Human 接续来源与可重现失败前缀交接

## Goal

解除 B04 在真实 Human 接续中复现的两项来源阻塞：来源 fixture 依赖 validator 实现错误才能得到 `recovery_required`；trace 0.7/proof 0.4 按内容 SHA 保存单一 member owner，使不同 Coordinator Attempt 的相同诊断 bytes 被错误合并。用原生产端口分别证明故障前缀和成功接续，完整保留 request、publisher、validator、consumer 与 artifact 的独立身份。

B04 是纠偏目标，`depends_on: B04` 不要求它先 completed。B00/C11/C12 必须 completed，B04 保持 blocked；2026-10-05 用户授权按审查建议修订后执行，本票修订审核通过才进入 ready 并冻结。完成本票并独立复核阻塞后，才依原授权恢复 B04 ready，继续其原 47/144 验收。

## Why

2026-10-05 B04 按用户指令恢复执行。Human 局部修复候选避免 validator 声称旧 `approval` 为自己的产物，按当前 request 的最新 response 判定 submitted，并将原物理节点 `human_approval_gate` 映射到 canonical `human_gate`。原 resume 随即 committed；C11 的 `helpers/ordinary_human.py` 却固定断言 `recovery_required`。C11/C12 多项 meta 共用此 fixture，并固定不消费 response 的失败前缀。B04 冻结范围禁止修改前置 outcome/owner/invariant，不能通过改断言或覆盖旧 expected 解决。

另在批准重跑和拒绝两条路径各建两个 fresh 根，原 resume 都 committed，Human lifecycle 都为 submitted → validated → consumed，Run 都 completed；批准后实际 fresh Analysis/Reviewer 执行并 accepted，拒绝时没有额外 Work effect，terminal 为 rejected。四份完整 0.7 normalize 都拒绝 `invalid_evidence:ordinary_trace:human_diagnostic_source`。两个 Coordinator 的 `decision_coordinator_diagnostic.json` bytes/SHA 相同，但注册 artifact 分别属于请求前后的不同 Attempt；原 collector 已完整采集这些成员。`OrdinaryProjection.member_values` 仅以 SHA 作 key，后一个 owner 覆盖前一个，导致 requesting Attempt 的绑定丢失。不能靠改变诊断内容、伪造 identity 字段或把两个 producer 合并修复。

定位证据在 `/private/tmp/lqcd-agent-b04-resumed-nz8hjtnr/`：`human-current-request-regression-probe.txt`、`human-blocker-audit.json`、四份 `*-facts.json`/`*-raw.json`、`candidate/manifest.json` 及候选 diff。这些是定位材料，不是本票完成证据；候选 Human 修复已撤回，执行本票必须 fresh 重建。

2026-10-05 独立审查在 `/private/tmp/lqcd-agent-b00c13-review-a12ofir2/` 验证：validator publication 后已有完整 completion_intent 的故障是可物化前缀，原 operation 补齐可 committed，Agent 调用 2→2；强制其 recovery_required 会继续依赖错误分类。另在原 phase_b_test 下真实耗尽 re-review 额度，Human Gate 后剩余 5 Control，原 resume 仍要求 1+完整5 reserve，拒绝合法 terminal tail。原外部 validator Transition 还仅携带 pause_id，丢失原停止链身份。本票因此明确纠正前缀分类及最小 Human reserve/停止链交接，不改 A04/A06 合同。

Planner 进入 Coordinator 时 registry 强制要求 current Analysis、ordinary 收尾及 Code/fallback/grant 等仍是原 B04 的待修责任。本票不声称消除这些产品缺口或完成 B04。

## Read First

- [AGENTS.md](../../../AGENTS.md)、[docs 入口](../../README.md)、[ticket 工作流](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)和[验证指南](../../VERIFICATION_GUIDE.md)；
- [B04 冻结票](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[执行记录](../completions/B04_COMPLETION.md)和[maintenance](../corrections/B04_MAINTENANCE.md)；
- [C11](B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_HANDOFF.md)、[C12](B00C12_HUMAN_REQUEST_PACKET_TRACE_HANDOFF.md)及其 [基础合同](../corrections/B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_CONTRACT.md)、[补充合同](../corrections/B00C12_HUMAN_REQUEST_PACKET_TRACE_CONTRACT.md)和独立 completion；
- [A01](../phase-a-control-contracts/A01_TRANSITION_MATRIX.md)、[A03](../phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md)、[A04](../phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)、[A06](../phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)、[A07](../phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)、[Control Protocol 0.4](../phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)及[需求目录](../phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)；
- `src/lqcd_agent/graph/{nodes,analysis_graph,routing,state}.py`、`control/{capabilities,pause,operations,budget,interfaces}.py` 和 `artifacts/registry.py`；
- `tests/phase_b/harness/{ordinary_trace,ordinary_maximum_trace,a05_trace,trace,pytest_evidence,matrix,exit_checks,session,failpoints}.py`、`helpers/{ordinary_human,ordinary_sources,ordinary_maximum,control_traces}.py`及 C11/C12 Human/消费者测试；
- B00C04 有界分批、B02/B03 独立 owned 集合及 C12 同 Session 验收记录。

## Scope

- 仅在 0.7/0.4 中修复同 bytes、多 member owner 的诊断来源索引和严格 DAG 引用，沿用既有 declarations、注册材料及被动采集；
- 将原 Human 失败来源 fixture 绑定到已有生产 publication boundary，按 A04/A06 分别证明可物化前缀和真正缺失 domain completion 的 recovery_required，消除其对 runtime bug 的依赖；
- 完成支撑实际来源验收所需的最小 Human 接续修复：validator output ownership、当前 request/latest response、physical/canonical node 识别，以及普通审批与真实 terminal sequence 的区分；
- 用新专用 fixtures/expected 分别验证失败前缀、批准接续、拒绝接续及重复 request/response 场景，并核验四条消费路径；
- 交付独立来源补充合同、逐项 completion 和当前输入回归，再独立复核 B04 入口。

## Non-goals

- 不实施 Planner/Code 到 Coordinator 的完整 dependency 集成、四层 fallback、fingerprint 算法/发行、BudgetGrant 产品发行、ordinary maximum 收尾、Code parent、完整 fresh Analysis 或 B04 47/144；
- 不新增 trace/proof 版本、schema、slot、operation、phase、预算算法、风险政策、owner 或 case 分类；
- 不把已有 protected snapshot、validated、consumed 或 grant contract-only 证据相互替代；
- 不修改 Phase A、冻结票正文、旧 sealed raw/expected、legacy runtime/测试或实际 inputs/outputs/accepted；
- 不 commit/push/PR/deploy，不访问真实 provider/Backend/network/raw/secrets，不新增依赖。

## Allowed Files

- 本票 ready 后只改 YAML lifecycle；B04 仅在完成后独立入口复核通过时更新 YAML lifecycle，正文保持冻结；
- `src/lqcd_agent/graph/nodes.py`：仅当前 request/latest response 的 Human 校验、validator output refs 与既有 approval ownership 的最小修复，以及原停止链来源读取与 deterministic terminal evidence/收尾；不得把旧 approval 重新注册给 validator，不增加虚假或 accepted artifact；
- `src/lqcd_agent/graph/analysis_graph.py`：仅严格 physical/canonical Human kind 识别、原 resume/advance 接续、committed duplicate 只读和原停止链的 close 接线，不修改 compiled 17 edges 或一般 Code/Agent execution；
- `src/lqcd_agent/graph/routing.py`：仅普通 Human 审批与真实 terminal sequence 的区分及传播，复用原预算决策，不修改 limits/reserve/算法；
- `src/lqcd_agent/control/pause.py`：仅 Human resume 的 exact completion publication 前缀分类、原 request/publisher/validator 停止链身份交接，以及已合法进入 terminal tail 的 reserve admission；普通 Human validation 仍保留完整 reserve，禁止从 tail 返回 Work；不改 external_result/recovery_decision、operation/phase/lease/authority 或预算算法；
- `src/lqcd_agent/control/capabilities.py`：仅复用原 completion materialization 的来源/bytes/heads 验证，为上述 Human 分类提供必要的只读核验；不重执行 target、不新增 completion/恢复策略，不修改 external consumption、预算或 producer authority；
- `tests/phase_b/harness/ordinary_maximum_trace.py`：仅 0.7 的 member owner/diagnostic/request/remediation 与原停止链 DAG 绑定；`ordinary_trace.py` 仅必要的显式新版本接口，0.6 及以下保持原语义和拒绝行为；`a05_trace.py`/`trace.py` 仅经验证来源的必要 DAG 接线，不增加 exclusion 或任意 locator；
- `tests/phase_b/helpers/ordinary_human.py`：仅已有 observer boundary 的 scoped failpoint 与生产端口场景；`ordinary_sources.py`/`ordinary_maximum.py`/`control_traces.py` 仅确需的被动完整来源采集；禁止 patch graph、selector、port、ledger 或 outcome；
- `tests/phase_b/test_b00c11_human_snapshot.py`、`test_b00c11_trace_consumers.py`、`test_b00c12_human_request_packet.py`、`test_b00c12_trace_consumers.py`：仅失败 fixture 与新独立 expected 的交接，明确允许将原 bug 导致的 recovery_required 断言改为本票审定的 materialization_pending；原 scenario/observe IDs、来源拒绝/敏感性、protected snapshot、exact/Session/no-consumed 义务保留，另加独立真实 recovery_required 分支；
- 新 `tests/phase_b/test_b00c13_human_continuation.py`、`test_b00c13_trace_consumers.py`、`fixtures/b00c13/`、`expected_traces/b00c13/`；不覆盖旧 C11/C12 expected；
- `tests/phase_b/acceptance_matrix.json` 仅原 B00 `A07-META-006`/`A07-META-015` 的专用来源 meta 接线，保留既有 observe IDs；共用 matrix/pytest/exit/failpoint 文件仅必要的 0.7 接线，不改变选择、报告、Session、runtime 或 exit 判定；
- 其他旧 expected/关联 fixture 仅审定真实 runtime fingerprint 及已证明的派生 head/reference。逐字段保存 old/new raw 和差异，双 fresh 重建；不得改变 outcome/owner/invariant；
- 新 `docs/tickets/corrections/B00C13_HUMAN_CONTINUATION_SOURCE_CONTRACT.md` 和 `completions/B00C13_COMPLETION.md`，只在批准执行后记录实际合同/结果；本票局部生产修复另追加原 `B04_MAINTENANCE.md`；
- `docs/tickets/completions/B04_COMPLETION.md`、两目录 README、Phase B Overview、`docs/README.md`、`docs/REPO_CURRENT_STATE.md` 仅追加入口、事实及当前摘要；生效后 `docs/{ARCHITECTURE,VERIFICATION_GUIDE,EVALS_AND_OBSERVABILITY,DECISION_LOG}.md` 仅实际合同同步。

## Do Not Touch

- Phase A、B00 必需 schemas/catalog/cases/obligations、已冻结 ticket bodies、旧 sealed evidence、milestones/tags；
- C11/C12 已完成合同/completion 历史；新合同以独立补充交接，不改旧记录；
- production control/budget/registry/code_agent（仅上列 pause.py/capabilities.py 的 Human 合同保持修复例外）、Agent prompt/LLM/工具、legacy tests、dependencies/configs；
- repository outputs、raw、accepted artifacts、human ingress/decision 文件及 secrets；
- B04 construction/runtime ownership、B05 正文与后续实现。

## Requirements

### 1. 相同内容与不同 owner 严格区分

- 同 SHA 可以共享已验证内容，但必须保留完整 `(case, run, artifact_id, registration_head, Attempt, logical member)` 关系；不能用 SHA、同内容或同字段名代替 producer/authority/registration。
- Human created 的 `requesting_attempt_id` 只能绑定该 Attempt 唯一真实 Coordinator diagnostic；后续 Coordinator 的相同 bytes 不得覆盖它。所有历史成员必须保持原注册、canonical path、digest、size、namespace、执行顺序与 evidence 引用核验。
- packet requester/publisher、response validator/consumer、remediation owner 各自使用原合同。重复、foreign、错 request/Attempt/member、篡改或缺失来源均拒绝，即使 bytes 相同或 outer hash 已重算。
- 0.7 修复须显式隔离；0.1–0.6 原解释、拒绝行为、sealed expected 和未经批准的路径位置不变。

### 2. 故障前缀严格遵守 A04/A06 分类

- 原 Human 来源 meta 使用 validator 已有 publication boundary 的 scoped observer 故障，证明 submitted/validated 后尚未 consumed 的可物化前缀。已有 exact completion_intent、预计算 identity/bytes/heads 且核验通过时保持 in_progress/materialization_pending；原 owner 仅补齐冻结后缀，不重新运行 validator/Agent/effect，不重新求值 route。
- 缺少 completion_intent 的真实 started invocation 另验 recovery_required/no-consumed：在已有 validator started boundary 发生实际故障，保存 started authority 与未取得 domain completion 的事实；不得凭测试者知道未执行 effect 而重新派发。此分支不要求 validated，也不伪造 validator outcome。已证明 integrity conflict 仍按原 failed/unavailable 分类，不能冒充 pending 或 recovery。
- Failpoint 必须绑定原 Run/request/validator/resume producer，保存触发回执、completion 是否冻结、原公开 operation 状态和实际 effect 计数；不替换返回、不合成 ledger、不主动执行第二次 effect。
- 保留原 meta IDs、protected snapshot、request packet、single-use/no-consumed 与 Session/exact 义务。本票显式纠正旧 fixture 的错误状态断言，并使用新 C13 expected 保存故障 bytes/error/phase 和审定派生差异；旧 C11/C12 expected/raw 及完成历史保留，不倒改历史事实。
- committed 的同 key 请求只读重放；in_progress 的 exact publication 前缀允许原 operation 物化，不能与只读 replay 混为一谈。真正 recovery_required 不再推进。
- 若既有 fault boundary 不能分别闭合这两类真实前缀，或 exact 来源不可核验，必须 Stop，不以 fake target/error 或放松来源断言替代。

### 3. 实际接续与普通审批

- validator 不声称自己生产旧 approval；同 request validation 不清除/重注册原 packet，不改 protected response bytes。仅最新、当前 request 的 submitted response 可校验，旧 consumed/invalid response 不得用于新 request。
- canonical `human_gate` 只接受合同已声明的 Human physical node 与 exact kind，不采用泛化 alias；external resume validator 不计 A01 产品 edge，后续 `human_gate -> decision_coordinator` 仍由新 advance 独占。
- 普通风险/澄清/审批不创建 terminal sequence；只有真实预算/停止触发保留原 terminal sequence。审批不能恢复 terminal reserve、突破 absolute ceiling 或授权停止后 Work。
- 原 request 的停止链必须由真实预算 decision 与 requester/publisher inbound 证明，并通过 HUMAN_RESPONSE validator Transition、新 advance、Coordinator 与 terminal sink 连续传递；foreign/伪造/失去来源的 sequence 拒绝，不能扫描任意旧 sequence 当 authority。0.7 来源验证同样绑定原链，不对后继 owner 重造 sequence。
- 普通 validation 保留完整5/6 reserve；已合法进入 terminal tail 的 validation 使用原 reserve，并按剩余实际收尾链核验 absolute Control/Transition 容量，不能再次要求完整 reserve。以 phase_b_test 中真实 re-review 额度耗尽、Gate 后剩余5 Control复现，拒绝响应必须到达原 deterministic terminal closure，Work effect 不增加；另覆盖不够收尾容量时原 deterministic stop/close，而非永远 paused 或恢复 Work。
- 实际 `approve_rerun` 只经 Coordinator 派发 scope 内一次有限 Work；拒绝/hold 经 deterministic terminal sink。Response 单次消费，committed duplicate 即使后续 graph 尚未 advance 或 Run 仍 running 也只读；completed reentry 不产生新 effect、Attempt/Transition 或 registry/protection。物化前缀只允许上节原 operation 的预计算补齐。
- 这里只闭合无 Code 的专用 Human 来源路径；BudgetGrant 发行、四层 fallback 和 Code integration 仍属 B04。不得用本票正向替代原 B04 owned runtime。

### 4. 来源消费与完整回归

- 成功接续需完整 normalize/compare，不能停在 snapshot 或只测 selector；相同诊断两个 owner 必须保持且通过，合法 reason/evidence/scope 变化必须改变 normalized 结果。
- collector、正式 matrix、runtime validator、exit semantic digest 共用严格来源和当前 Session；missing/tampered/foreign/stale token 或任一 digest 均拒绝。Meta 标明 B04_owned=false，保留原 B00 owner。
- 所有 source 实现稳定后，在同一当前输入 fresh Session 实跑 B02 1410/1410、B03 645/645、C11/C12/C13 专项及完整 repository suite，并独立完成 fresh construction 15/11/30/28；先固定验证输入，后区分合同/记录交付输入。
- 保持 131 required、84 mapped、47 remaining、2199 cases（1410/645/144）、324 boundaries、28 post-claim、15 exit checks 及原 owner 集合；B04 0/144，final 仍精确为其未完成的 47 coverage/144 binding/15 adapter 缺口。

## Deliverables

- 版本隔离的 owner 绑定修复及最小 Human 接续；
- 故障前缀与批准/拒绝/重复 request 的双 fresh raw、normalized、固定新 expected、原端口结果和 failpoint/effect 证明；
- 四消费者反例及同 Session 完整回归、独立 construction/final 审核；
- 新来源补充合同、completion 逐项证据、B04 maintenance 和入口复核。

## Acceptance Criteria

1. 批准重跑与拒绝各在两个 fresh 根使用原 compiled graph/resume/advance/close；分别实际 accepted/rejected，Human submitted→validated→consumed exact，无额外/重复 effect，0.7 双根 exact 通过。
2. 两个 Coordinator 的诊断 SHA 相同但注册 owner 独立；request 绑定原 requester，后继绑定原 consumer，不靠改变成员内容通过。缺失/篡改、重复 owner、foreign Run/Attempt/registration、错误引用均拒绝。
3. 原 negative meta 由真实 scoped publication failpoint 产生 in_progress/materialization_pending、submitted/validated/no-consumed，原 operation 补齐不新增 effect；另以真实 started/no-completion 故障证明 recovery_required 不推进。原 observe IDs 与全部拒绝/敏感性义务通过；新 expected 保存审定状态/故障/派生差异，旧 evidence/expected 不变。
4. 当前 request 与旧 response、committed 后尚未 graph advance/仍 running 的 duplicate、物理节点错 kind、ordinary approval 与真实 budget stop 分支通过 production 验证。真实 stop sequence 穿过原 validator/advance/Coordinator；phase_b_test 的5 Control剩余反例与不足容量分支形成合法 terminal closure。停止后的 Work effect 为零，最大费用或提交成功本身不构成安全停止证明。
5. 四消费路径、stale Session/每项 digest 反例、旧版本拒绝和来源 material sensitivity 通过；meta 不计 B04 runtime。
6. 同一当前输入 Session B02/B03 1410/645、来源专项、完整 suite 和 fresh 15/11/30/28 全通过；inventory/owners/final 缺口保持，禁止 skip/xfail/live-only 替代。
7. 冻结正文/旧 sealed hash、scope、文档链接与状态审核通过，无 commit/push；本票 completed 后独立复核实际 B04 阻塞，才能按原授权恢复 ready。

## Verification

创建阶段只检查 YAML/模板/依赖/链接、范围、冻结正文摘要和 diff。批准执行后使用以下专项及既有 B00C04 bounded Session runner；普通 pytest 输出不能替代 Session/runtime/exit 证明。

```bash
pytest -q tests/phase_b/test_b00c13_human_continuation.py tests/phase_b/test_b00c13_trace_consumers.py
pytest -q tests/phase_b/test_b00c11_human_snapshot.py tests/phase_b/test_b00c12_human_request_packet.py
pytest -q tests/phase_b/test_b00c11_trace_consumers.py tests/phase_b/test_b00c12_trace_consumers.py
pytest -q tests/phase_b/test_b04_product_graph.py tests/phase_b/test_b04_resources.py tests/phase_b/test_b04_host_boundary.py
```

另以原 construction runner 在独立 fresh Session 验证 B00/B01/B02/B03；稳定输入的 full Session 对全仓 nodeid exact 收集、有界分批、合并 validate_pytest/observations/runtime/exit，独立验证 owned 1410/645 集合及 final 精确缺口。完成记录列出真实命令、输入 manifest、Session token、report 和双根差异证据，不能凭库存预填完成。

## Stop Conditions

- 原 prerequisite 不 completed、来源旧 sealed preimage 无法核验或无可信输入基线；
- 需要新增版本/schema/slot/operation/phase、改变风险/预算/停止/authority 或 B00 required/case/owner；
- 需要扩大 production 修复、触碰 Do Not Touch 或篡改旧 C11/C12 合同/证据；
- 无法用原边界分别产生可物化 completion 前缀与真实 started/no-completion recovery_required，或新的 owner/DAG/停止链位置尚未证明；
- 必须 patch runtime graph/selector/state/port、排除 material、合并 owner、动态重写 expected、skip/xfail 才能通过；
- 所需完整回归不能在本票范围内以合同保持修复闭合。

## Required Documentation Updates

创建时：本 review 票、Phase B Overview、docs/corrections 索引、当前状态及 B04 completion 关联；保留历史。本票批准执行后才创建独立合同和 completion，追加实际 B04 maintenance，并同步实际生效的来源/验证说明和决定。B04 剩余 Planner dependency、Host/guard 全路径、ordinary 收尾、Code parent、四层 fallback、fresh Analysis、fingerprint/grant、terminal/recovery 与原 47/144 仍逐项执行，不因本票 completed 而预填产品通过。
