---
ticket_id: B00C18
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C13, B00C15, B00C16, B00C17, B04]
---

# B00C18：普通 Human repause 与 C15–C17 预算来源链闭合

## Goal

修复 invalid Human response 后普通 repause 的容量与来源缺口，并在一个稳定候选输入上闭合 C15–C17 的原全部要求和验收，形成可独立复核的 B04 前置交接。C15/C16/C17/B04 是纠偏目标，不要求先 completed；B00/C13 须已 completed。本票新增授权仅为下面列明的 repause 来源/容量修复，其余按 C15/C16/C17 已冻结合同完成，不重写其正文。

2026-10-07 跨票审查修订：把“C15 原专项”改为 C15 全部冻结验收的逐项责任，补齐执行前覆盖表、预算 publication 故障表及统一最终 Session。仍为 **review**；修订不代表批准、实施或阻塞已解除，C15/C16/C17/B04 保持 blocked。证据全部通过后分别复核并记录各票完成；B04 仍须独立入口复核，不由本票自动 ready/completed。

## Why

C17 已修复 Coordinator 重复失败升级的 Human publisher/validator 容量预检，并限制原 terminal Request 的 Work/Grant scope。原三项 C13 terminal 反例、普通审批容量边界和合法 Grant 专项共 5 passed；尚无完整当前 Session 验收。

在原 `phase_b_test` 普通 Analysis failure/Human 路径，Pause 剩余 control=6、transitions=16，无 stop sequence。实际 `request_code_change` 超出冻结 Analysis scope，原 validator 将 response 记为 invalid，剩余 control=5、transitions=15。`ProductRouteAdapter.repause` 无论普通或 terminal 都使用 3/4 门槛，因而发布新的普通 Pause。合法纠正 `reject_or_hold` 被原 Resume 的普通 6/7 门槛拒绝：`Human validation lacks reserved terminal capacity`。Run 保持 paused，调用 2→2，拒绝无 mutation。

两份原端口 fresh raw/normalized/facts 保存在 `/private/tmp/lqcd-agent-b00c17-execution-20261007-t7slh_nw/ordinary-invalid-probe/`。C17 只允许 `routing.py` 和相应 terminal-only `nodes.py` 修改；本缺口涉及 `analysis_graph.py::ProductRouteAdapter.repause` 与 `operations.py::invalid_response_admission` 的可信原停止链来源输入，超出其冻结范围。不能修改原 Resume、增加普通 admission 门槛来改变 C13 原合法普通 Pause，或修改 fixture 输入掩盖反例。

另在原 terminal invalid→纠正路径的两 fresh 根，实际均安全 halted、零 Work/Grant、同 sequence，完整0.8来源各自可验证，但 normalized 有55处派生摘要差异。完整preimage追溯到原 `repause` BudgetDecision 的 `proposal_id` 仍按 literal 保留包含真实 execution heads 的 raw digest；绑定内容原属于已验证 consumed Pause/finished validator/Request/next Pause identity及dimensions。材料与首处preimage保存在同执行根 `route-candidate-probes/invalid_corrected-*`。不能将两份raw摘要互相别名、掩盖proposal或直接覆盖fixed expected；本票补充显式0.8下原repause recipe的来源绑定，旧版本保持。

### 跨票根因与当前证据边界

| 票据 | 已证实的问题及其边界 | 本轮闭合责任 |
| --- | --- | --- |
| C15 | 原 A05 harness audit dialect 与 production canonical audit 不同；相同 SHA 单 owner 假设不能表达真实多 Attempt 来源。原 18 项仅覆盖部分 FP/Grant 与两类 budget event 的 Python 异常 before/after，未完成故障表。 | 复用 C16 显式 profile/独立 owner；补完 C15 全部科学材料、Grant 拒绝、四消费者及故障表，不能以 18 项替代。 |
| C16 | 来源候选 37 项曾通过，但 FP occurrence=2 改变路由，产生 control=5、无 sequence 的普通 Human Pause；修复需要 production，超出其范围。 | 对当前 production build 重验来源候选及原 Human 全链；旧 37 项不是当前输入通过证据。 |
| C17 | 原三项 terminal、普通容量与 Grant 共 5 项通过；遗漏普通 invalid 后 repause 的另一入口，修复所需两个函数不在其 production 范围。 | 同时覆盖 Human 初次发布、validator、repause、纠正、收尾及预算边界，不能只修初次路由。 |
| C18 原稿 | 已列普通 repause 和 proposal 来源两个反例，但只要求 C15“原专项”，且未明确预期 recovery/拒绝与真正 Stop 的区别。 | 用下列覆盖表承接 C15–C17 全部未完成义务；负向分支正确拒绝/保留 recovery 是通过条件，不自动成为新阻塞。 |

反复停止的共同原因是按首个失败点切分范围、缺少整条 producer→consumer 路径的覆盖核对；每次 production 修改又改变 runtime fingerprint，早前 fixed expected/Session 需要重新审定。停止保护了冻结合同，但此前审查与验收规划未充分预见相邻分支。当前缺失证据与已复现代码缺陷分别列示，不能把每项未测都宣布为已确认的新 bug。

## Read First

- [AGENTS](../../../AGENTS.md)、[文档入口](../../README.md)、[工作流](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)、[验证指南](../../VERIFICATION_GUIDE.md)；
- [C17](B00C17_REPEAT_ESCALATION_TERMINAL_RESERVE_HANDOFF.md)、[C16](B00C16_CANONICAL_CODE_AUDIT_SOURCE_HANDOFF.md)、[C15](B00C15_PRODUCT_FAILURE_FINGERPRINT_AND_GRANT_SOURCE_HANDOFF.md)、[B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)冻结正文及独立 completion；
- C13 冻结票/来源合同/completion、A01/A04/A06/A07、Protocol/catalog 和 B04 maintenance；
- `graph/analysis_graph.py::ProductRouteAdapter.repause`、`control/operations.py::invalid_response_admission`、`control/capabilities.py` 的 invalid completion/repause publication、`control/pause.py` 原门槛/sequence 传播；
- C13 ordinary/terminal/invalid/duplicate/suffix 测试，C15 Grant/预算故障及 C16 来源/四消费者测试。

## Scope

- 从原已验证 execution prefix 证明当前 invalid validator 属于普通 Human 还是原 terminal sequence；
- 普通 repause 预留下一 validator 加完整 immutable reserve，原 terminal repause 使用已证明 tail；
- 显式0.8验证原repause proposal完整来源及既有字段的派生引用，形成双fresh固定轨迹；
- 不可安全消费时复用原 insufficient decision/close 或原 authority 不确定分类；
- C15/C16/C17 候选的合同保持修复、原全部验收及独立完成复核；同一最终输入的证据可逐项引用，不重复构造不同输入的“全量通过”。

## Non-goals

- 不改 Resume 门槛、收费/计数/limits/reserve、预算 primitive、Grant 权限/消费规则、科学接受或风险优先级；
- 不把普通 Pause 转造为 terminal，不增加 Work 机会，不新增 runtime wire/proof/profile；
- 不完成 Code parent、B04 owned、通用 graph publication 修复或 B05，不 commit/push。

## Allowed Files

- 本票新增 repause 范围：`src/lqcd_agent/control/operations.py::invalid_response_admission` 的原普通/terminal 来源核验及内部 adapter view；
- 本票新增 repause 范围：`src/lqcd_agent/graph/analysis_graph.py::ProductRouteAdapter.repause` 的原 policy/reserve 容量选择；不开放通用 graph 自动接续；
- C17 原 `graph/routing.py` 与相应 terminal-only `nodes.py` 范围，完成其候选及全部剩余验收；
- C15 原 Allowed Files 的最小 Host FP/validated Grant 集成与 exact failure snapshot/response scope、原 publication/单次消费接线，仍受其原 Scope/Do Not Touch/Stop 限制。涉及 `graph/{nodes,routing,state,analysis_graph}.py`、`control/{budget,capabilities,operations,pause}.py` 时须逐 hunk 关联 C15 具体要求及反例；不因此开放整个文件、底层 primitive、通用 graph 恢复或新的消费/接管规则。上面两项 repause 函数是本票额外授权的唯一 production 语义补充；
- C15/C16 原 harness/collector/tests/fixtures/current Human 接线范围，用于完成其已批准 0.8 来源和全部验收，不扩大 canonical profile/科学 recipe。另允许 `tests/phase_b/harness/product_failure_trace.py` 及确需的被动 collector 在 0.8 按原 repause recipe 绑定现有 proposal_id/原 binding 引用；不新增 kind/profile/proof 字段、不改变旧版本；
- 新 `tests/phase_b/test_b00c18_ordinary_repause_handoff.py`、`fixtures/b00c18/`、`expected_traces/b00c18/`；C17 原待交付 `test_b00c17_terminal_reserve_handoff.py`、`fixtures/b00c17/`、`expected_traces/b00c17/`；C13/C15 专用测试只补原合同回归，既有 nodeids/observe IDs/业务结果保持；
- `acceptance_matrix.json` 仅 B00 A07-META-006/015 的相应来源 meta；
- 前置 expected 仅经 before/after raw、双 fresh 和完整 preimage DAG 审定 runtime fingerprint/派生引用；C15/C16/C17/C18 新路径按批准版本审定实际来源变化。Code config/context/FP 如包含更新后的 runtime fingerprint，按冻结 C15 recipe 完整重算并审计，不任意替换科学摘要；
- 本票 YAML、新独立 contract/completion；C15 原待交付来源 contract、C16/C17 contract 及各独立 completion/maintenance，B04 completion/maintenance 追加、Current State/Overview/索引及必要源合同/Decision Log。准备/完成记录须区分实测与待验，不能提前制造完成记录。

## Do Not Touch

- `control/pause.py` 原 Resume/sequence 门槛和传播、budget primitive/算法/limits/reserve、authority、Grant 消费规则及科学接受；C15 已批准的集成接线不构成放宽这些规则；
- 其他 production、Phase A、冻结正文、旧 sealed evidence、trace 0.1–0.7 解释、旧 C11/C12/C13 0.7 expected；
- B00 schema/catalog/cases/Session/failpoint/exclusion、B02/B03 owned 语义/owner、legacy tests、依赖/configs、raw/outputs/accepted/secrets、外部系统与 B05。

## Requirements

1. 内部 `repause` view 可新增闭合 `human_continuation` 来源对象，字段 exact 为 `mode,validator_transition_head,stop_sequence_id,budget_stop_transition_head`；`mode` 仅 `ordinary|terminal`。该对象只由原 `invalid_response_admission` 从已验证 prefix 构造，不从 response、Agent、自由文本或 latest pointer 自报；不新增 runtime ledger、proof 或 authority 字段。
2. validator transition 必须唯一、绑定当前 invalid response 的 validator Attempt、原 Run/Case/Request/Pause 和 exact finished prefix。普通模式两个 stop 字段为 null，不能借历史另一条 sequence 使用 tail。terminal 模式绑定当前原 HUMAN_RESPONSE Transition 的 sequence 和同 Run 原 budget-stop Transition；sequence 必须按原 Run/source Attempt/reason recipe exact，owner、head、scope及连续传播真实可证明。
3. 普通 repause 需要下一 validator 的 1 control/1 transition 加原 immutable reserve 5/6；terminal repause 仍使用原 3/4 tail。仅改变合法 proposal 的 lookahead/projected_after，不改变 used/remaining、实际 charge、counter 或 reserve，不复制可写预算状态。
4. insufficient 分支使用原 closed BudgetDecision/RepauseAdmission 和原 publication/close suffix，不发布不可消费新 Pause，不伪造停止/closure、不退款、不再执行 effect；authority/停止不确定保持原 recovery/integrity/unavailable。普通 invalid control6→5 必须由原 close 安全 halted，新普通 Pause 不存在。
5. 容量充足的普通 invalid response 可以在新 Pause 纠正；原 terminal control5 的 invalid→合法纠正保持原结果、sequence 和零 Work/Grant。ordinary approval、风险/科学 guard、合法 BudgetGrant 发行和原单次消费保持。
6. committed 同 key/exact request 重试只读复用；合法未完成 publication 前缀由原有效 owner 补齐冻结 suffix。不确定/冲突保留原分类，不能重新分配 Attempt/Transition、接管 started invocation、重发/重消费 Grant 或重跑 consumer。
7. 保持旧 adapter 及 B02/B03 行为；内部来源输入不得放宽原权威或原验证器。补充 wrong/foreign/missing/stale mode/sequence/head 来源拒绝，source 重读不得执行 effect。
8. 完成后逐项独立复核 C15/C16/C17 全部冻结要求/验收，不能只重跑现存专项。保存原要求→实际 test/nodeid→双 fresh raw/固定 normalized→原消费者结果→最终 Session 的对应表；未实现、未运行、失败必须分别标识。只有全部原要求有合格证据后才更新相应完成状态；B04 原职责保持。
9. 0.8中的每个原repause proposal，按原闭合binding字段 `consumed_old_pause,finished_validator_attempt,open_human_request,derived_next_pause_identity,terminal_tail_capacity` exact重算raw proposal_id。前两项逐一绑定同Run真实consumed Pause及当前finished invalid validator的原record head；Request与next Pause identity按该prefix重放计数exact；dimensions与原BudgetDecision完整一致。仅核验成功后按完整normalized binding建立派生引用，所有字段保持material，不使用SHA全局别名。缺失/foreign/stale/篡改来源或无法独立证明时拒绝；旧0.1–0.7解释/拒绝保持，双fresh与科学/容量合法变化分别验证。
10. 执行前先建立下面的完整覆盖表及原端口可达性清单，检查每条路径的 producer、实际读取、publication、来源 recipe 与四消费者是否都有对应；保存当前反例及原始摘要，再按工作流进入实施。已经可读的源码/历史证据只作定位，不冒充本轮 fresh。遇到验收路径不可达或合同不一致，应在扩大实现前保存依据并处理 Stop，不修改科学输入、policy/计数或验收要求制造可达性。
11. 两种合法 terminal 直接收尾保持原四条同 sequence Transition；原 invalid→纠正另有真实 invalid response 的 HUMAN_RESPONSE Transition，当前原端口实际共五条、同 sequence。分别按完整原序列审计，保留 C13 原测试断言；不能为了统一条数删除真实事件或增加 Work/Grant。

### 必须逐项关闭的覆盖表

本表是 C15–C17 原验收与本票新增两项修正的执行索引，不缩减原要求；证据可以复用同一当前输入的实际运行，不能只给累计 passed 总数。

| 组 | 必须包含的路径与反例 | 当前审查事实 |
| --- | --- | --- |
| H1 Human 容量 | 初次 ordinary/terminal；普通容量充足、仅 terminal 可达、两者不足；control/transition 各自边界；普通/terminal invalid 后可纠正或安全关闭；原 risk/ambiguity/security/science 优先级。 | C17 5 项局部通过；普通 repause 缺陷未修，其他组合不得据此宣称通过。 |
| H2 Human 单次性 | 合法同 key/exact request 只读；错 Request/Pause/action/owner/epoch/head/sequence；pending completion 原 suffix、started/no-completion、lost authority；无新 Work/Grant、无假终态。 | 复用 C13 原合同并重验当前 build；预期 recovery/拒绝必须保留。 |
| S1 科学来源 | C15 各固定 profile/十二项 context 的完整材料、真实变化与 incidental 区分；same-Run occurrence/replan；正常成功不重观察；Code/verified change/fresh Analysis 的真实原端口。 | C15 部分专项及 C16 候选存在，完整原验收尚未关闭。 |
| S2 owner 与 repause 来源 | C16 空/非空 canonical audit、same-Run 多 Code Attempt 内容共享且各 owner 独立；本票普通/terminal repause 原 binding raw digest 及所有派生引用；双 fresh 完整 normalized 一致。 | C16 旧输入曾 37 项通过；terminal invalid 双 fresh 仍有 55 处 proposal 派生差异。 |
| G1 Grant 授权 | validated→consumed→Coordinator started→完整 preflight→issue→原 advance consume；exact actor/decided_by/scope/Request/Pause/occurrence/target/heads；replan Cycle；错误 action、validator 提前发行、ceilings/reserve、foreign、重复发行/消费拒绝。 | 已有成功/重入局部证据，全部正负向矩阵仍须按 C15 补齐。 |
| F1 预算 intent | failure_observed/grant_issued intent 冻结未完整发布，以及已发布但 completion 未冻结；各 before/after 双 fresh，原 owner 只补原 bytes；无完整 completion 不重 invoke。 | 现有 4 个参数 case 是 Python BaseException；不能当作真实进程死亡，亦不覆盖以下两组。 |
| F2 completion 发布 | C15 原故障表的 frozen completion→attempt_finished/index/checkpoint 各部分 publication，原 owner 的 publish_completion suffix；缺失/篡改 completion/intent/heads、失效 owner/epoch。 | 尚缺完整表；须分别标识 Python 异常和真实进程中断。不得要求 B04 通用 graph 自动重入已修复。 |
| F3 Grant 消费 | 原 advance grant_consumed 冻结/已发布，target/invalidation/Transition 未闭合及已完整提交；各实际 before/after 双 fresh。未激活 Work effect=0；原 operation 补同 facts，缺事实或 authority 保留 recovery/unavailable，conflict 按原分类；不退款/重发/重消费。 | 尚缺完整表，不能被正常 Grant 成功用例替代。 |
| V1 消费与兼容 | C15 failure/Grant、C16 canonical owner、本票 repause 分别进入 collector/matrix/runtime validator/exit digest；missing/duplicate/orphan/order/foreign/stale Session/未知字段/profile/bytes 篡改拒绝；旧 0.1–0.7 行为及 Human 原不变量。 | C15 专用 trace_consumers 尚未交付；C16 的 Code 四消费者不能替代 Grant/repause 证据。 |
| V2 整体验收 | 当前输入 fixed expected 审计、完整 exact suite、同 Session B02/B03 owned、construction、具体 final ID 集合及冻结/scope 文档核验。 | 目前 3861 仅 collection；没有当前完整 suite/owned/construction/final 通过声明。 |

F1–F3 逐行执行 C15 原故障表，不改变原分类；进程中断必须保存独立进程与真实终止证据，原 authority 失效时不能用新 owner 接管 started Invocation。恢复成功和按合同保留 recovery/unavailable 都按各自真实前缀验收，不以最终 halted 作为所有故障的共同目标。

## Deliverables

- 最小原 repause 来源与容量修复、独立 maintenance；
- 原反例双 fresh before/after raw、sequence/owner/容量/response/Pause/closure/effect 证据；
- 固定新 expected/preimage 审计、专用 meta/四消费者、完整覆盖表及 C15/C16/C17 原全部当前输入验收；
- 独立 contract/completion，各冻结票逐项完成复核，以及 B04 独立入口结论与原剩余工作清单。

## Acceptance Criteria

- 两 fresh 根原端口复现普通 control6→invalid→5；修复后原 insufficient decision 安全 halted、不发布新 Pause、非 accepted，调用保持2，原 response invalid/single-use。重试不增加 effect；
- 普通容量充足时 invalid→纠正通过；terminal control5 的两种合法收尾及 invalid→纠正保持原 halted、sequence 和零 Work/Grant；C13 原三项及普通容量、packet、duplicate、publication/recovery 全部不变量保持；
- 普通/terminal repause双fresh完整normalized固定一致，raw proposal差异由原recipe及完整preimage可解释；missing/foreign/stale/wrong binding/维度/Request/Pause/validator篡改必须拒绝，真实响应/容量材料变化必须改变normalized，重读无effect；
- 普通/terminal 容量边界、无 tail、wrong owner/epoch/head/Request/action/sequence、stale/lost authority、真实 suffix 切点由原端口及闭合来源核验；token/cost typed unknown/maximum 原含义保持；
- H1–V2 全部关闭，C15 原全部 FP/Grant/预算故障表/来源拒绝及四消费者、C16 canonical/独立 owner/current Human、C17 全部冻结验收通过；不能以现存 18/37/5 项专项代替。meta 不计 B04 owned；
- 按原 Session/native 有界分批实跑同一当前固定输入完整 exact collection/suite；独立验证 B02 1410/B03 645，fresh construction15/11/30/28，final具体仍只有47 coverage/144 binding/15 exit；不 skip/xfail/过滤/历史 retag；
- 保持131 required/84 mapped/47 remaining、2199 cases、324 boundaries、28 post-claim、B04 144、15 exit及原owners；C15/C16/C17 分别具备全部证据后独立记录完成，不把 C18 状态当作其他票通过的替代。B04 owned 仍 0/144，Code parent、四层 fallback/fresh Analysis 产品集成、ordinary finished/publication 通用接续及原 47/144 留给 B04。

## Verification

批准 ready 后使用原 Session/native 及有界分批；focused 命令不替代完整 gate：

```bash
/opt/anaconda3/bin/python -m pytest tests/phase_b/test_b00c18_ordinary_repause_handoff.py tests/phase_b/test_b00c13_human_continuation.py -q
/opt/anaconda3/bin/python -m pytest tests/phase_b/test_b00c15_product_failure_sources.py tests/phase_b/test_b00c15_trace_consumers.py tests/phase_b/test_b00c15_budget_publication.py tests/phase_b/test_b00c16_canonical_code_audit_sources.py tests/phase_b/test_b00c16_trace_consumers.py tests/phase_b/test_b00c17_terminal_reserve_handoff.py -q
/opt/anaconda3/bin/python -m pytest --collect-only -q
```

顺序为：覆盖/可达性核对→H1/H2 两反例与相邻原端口→S1/S2/G1/F1–F3 全矩阵→四消费者及前置交接→完整 expected preimage 审计→冻结最终输入执行 V2。批准后补齐上列尚未创建的专用测试文件；review 不把命令列出等同测试已存在或通过。

最终源码、测试、fixture、expected 和验收输入稳定后创建一个当前 Session，按原 native 有界分批实跑全部 exact collection；分别用原独立验证器核对每票所需证据、B02 1410/B03 645、construction15/11/30/28、final47/144/15。已有历史结果只用于定位/对比；原 Session 绑定输入变化后不得继续使用其通过声明。C15/C16/C17 可引用同一合格最终输入的证据，不为每票重算不同输入的全量结果。验证输入 manifest 与之后状态/完成文档交付 manifest 分开保存。

Review 阶段只核验模板、依赖、links、scope、冻结摘要与 diff；不实施、创建完成记录或恢复其他票据状态。

## Stop Conditions

- 需要改原 Resume/budget 门槛、limits/reserve、runtime wire/proof、authority/Grant权限或科学 recipe；
- 只能凭 latest/SHA/response 自报猜 mode/sequence，必须转换普通 Pause、伪造停止/closure/预算、改变原反例输入或业务结果；
- 需要未列 production/profile/文件范围、覆写旧 expected 语义、扩大 exclusion、跳过失败/required/owned 或 retag历史；
- 合法正向路径无法证明原来源/authority/publication prefix，且完成原验收需要改变未授权合同或制造事实。故意注入的 missing/foreign/stale/lost authority 等负向用例按原合同拒绝或保留 recovery/unavailable 是验收结果，本身不触发 Stop；实际实现不满足该结果时，在本票及继承的明确范围内修复并记录 maintenance，越界才停止。触发 Stop 保存具体反例、所需改动和准确冲突条款，不因新增测试或范围内局部 bug 自动新建纠偏票。

## Required Documentation Updates

执行后新增独立 contract/completion，逐项核对 C15/C16/C17 原合同及实际交付，追加维护与 B04 入口/剩余责任、当前状态/Overview/索引及必要源合同/Decision Log。修订阶段只记录 review 与四票 blocked，不宣布实施、整票通过或恢复 ready，保留历史。当前审查未发现能证明所有未来分支已无缺陷的证据；本票目标是关闭全部已知缺口和原验收，不承诺未经实跑的“之后必定无阻塞”。
