# Phase B：图与 Harness 可靠性

## Status

`in_progress`

## 目标

根据Phase A已冻结的控制合同，直接消费tracked [`CONTROL_PROTOCOL_0_4.json`](../phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)，复用A02 identity protocol、A02C01 schema `0.4` bootstrap与`ControlOperation 0.1`、A03 artifact invalidation infrastructure，实现独立于LangGraph checkpoint的durable mutation/resume、有限循环和A01产品路线改造，并使用Fake Agents建立分层graph harness证明控制系统正确。实现者不得从A04/A05 prose重新发明type、variant、phase、edge、ownership、outcome或construction order。

A02/A03 的 re-review、analysis rerun、code fix 和 replan tests只证明 transition-time identity与invalidation protocol；它们不是 Phase B 的完整 product-route、forbidden-route、budget 或 recovery coverage。Phase B必须复用这些 primitives，不得另建第二套 current-selection或失效规则。

## 验收权威

[A07 Harness Acceptance](../phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)已经冻结Phase B的唯一完成标准。Required control acceptance必须network-free、deterministic并使用production入口和exact semantic assertions；legacy compatibility regression必须继续通过但单独报告；provider/RAG/科学质量等capability evaluation不能填补control coverage。

六层验收模型固定为：

0. schema、replay与跨head invariants；
1. node、Code Agent subgraph、Fake backend与trusted boundary；
2. route、guard、Transition与A03 invalidation；
3. exact trajectory、Cycle和termination；
4. durable recovery、双client/process concurrency与fault injection；
5. project-owned interface与新的`/private/tmp/lqcd-agent-phase-b-*` smoke。

Tracked requirement catalog version为`0.4.0`，包含A01、A02、A02C01、A03、A03C01、A04、A05、A06和A07九个owner的131项required requirements。B00必须按exact bytes消费protocol SHA-256 `7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`与catalog SHA-256 `ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726`。

## Matrix 与证据门槛

B00创建test-owned `tests/phase_b/acceptance_matrix.json`，使用`PhaseBAcceptanceMatrix 0.1`并绑定上述protocol/catalog version与digest。每个required scenario必须引用catalog中的stable required ID、固定layer、deterministic fixture、project-owned entrypoint、typed expected result/invariants、适用的exact normalized trace及至少一个可collect且passing的pytest node ID。

以下为[B00冻结合同](B00_ACCEPTANCE_FOUNDATION.md)已实现的验收协议：每个scenario使用`validation_stage=construction | final`，保持原requirement owner；construction仅确认当前slice的construction证据，累计`requirements.covered/remaining`仅表示映射覆盖与缺口，未重验的全局`requirements.passed/passed_ids=null`，两个完成标志均为false。

Final须同时验证两个stage的全部required scenarios及独立于matrix的final obligations。每个registry entry必须有实际production hook、触发证据、适用outcome、passing nodeid和exact trace；META-006/015不能仅凭inventory或静态检查完成，META-015还须覆盖publication、fresh Analysis、consumption release及7×4 post-claim paths。Unknown、non-required、duplicate、stale、uncollectable、skip、xfail、deselect、live-only或缺失trace/invariant均失败。

统一`PhaseBAcceptanceReport 0.1`及closed exit evidence以B00为唯一字段定义：`requirements_zero_gap`表示131项全部适用证据通过；`phase_b_complete`还要求全部exit checks有效且通过。Final创建本次session、执行检查、核验token/实际工作树输入及合同摘要后才生成报告；旧证据和自报passing不可复用，规范化报告排除临时路径/token。

## Implementation Ticket 拆分

A07执行时只冻结以下拆分；其后起草的六张票见下方Draft Tickets：

1. **B00 — Acceptance Foundation**：strict protocol/catalog/matrix schemas与validators、pytest collection、normalized trace codec和failpoint registry；
2. **B01 — Execution 0.4 Control Foundation**：budget policy/ledger、Run lifecycle、bounded projection、trusted clock、canonical validators与cross-head integrity；
3. **B02 — Durable Control Operations**：durable coordinator、ControlOperation guarded graph、leases/fencing、可信start/replay/fork bootstrap admission、Pause/Resume/Replay/Fork/Cancel、internal advance/pause/close/interrupt、ownership、child saga与restart recovery；
4. **B03 — Graph-managed Fake Code Agent**：CodeAgentSubgraph、Fake backend port、ExternalOperation/watchdog/containment、ingress/trusted verification、canonical bundle与fresh Analysis；
5. **B04 — Target Product Topology and Budgeted Loops**：接入A01产品edges、四层fallback、Human Gate return、A03 invalidation与A06后续产品route/resource/grant/stop admission，复用B01基础和B02 bootstrap；
6. **B05 — Acceptance Integration and End-to-End Harness**：完整normalized traces、fault/concurrency、compatibility、CLI smoke与最终zero-gap evidence。

依赖固定为B00；B01 depends on B00；B02 depends on B00/B01；B03 depends on B00–B02；B04 depends on B00–B03；B05 depends on B00–B04。每张票必须独立冻结Allowed Files、Do Not Touch、migration边界、owned requirement IDs与focused verification，不能合并成一张未审查的大票。

## 进入条件

- Phase A A01–A07、A02C01及A03C01全部completed；
- frozen Control Protocol与requirement catalog的exact SHA-256已由A07 completion记录，且design validator通过；
- transition、identity、invalidation、resume、budget 和 harness acceptance 已进入核心文档；
- 实现者不需要自行补充控制层设计决定。

这些阶段级进入条件已由A07 completion满足。B00在`f654f44`、B01在`537d10c`、B02在`83681a7`冻结后执行；三票均已completed。B02历史来源、reservation语义和trace/进程证据前置问题分别由B02C01与B00C01–B00C04关闭；本轮原B02运行修复与完整验收通过，见[B02完成记录](../completions/B02_COMPLETION.md)。B03已在`b78c15a`冻结；B00C05关闭首次reservation分类阻塞；B00C06已关闭A05来源轨迹前置，接续B03又确认状态投影/golden授权边界，因此B03仍blocked，待窄范围补充审阅。B04/B05仍draft。

## Implementation Tickets

- [B02审查](../corrections/B02_EXECUTABILITY_REVIEW.md)保留历史诊断；[B02C01](B02C01_LEGACY_SOURCE_FINGERPRINT.md)、[B00C03](B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)和[B00C04](B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)均已completed。
- [`B00C01_SOURCE_BOUND_SEMANTIC_TRACES.md`](B00C01_SOURCE_BOUND_SEMANTIC_TRACES.md)与[B00C02](B00C02_SEMANTIC_TRACE_EXIT_BINDING.md)：`completed`，来源绑定的semantic trace及exit完整接线已复验通过，B02解除前置阻塞。见[B00C02完成记录](../completions/B00C02_COMPLETION.md)。
- [`B00_ACCEPTANCE_FOUNDATION.md`](B00_ACCEPTANCE_FOUNDATION.md)：`completed`，验收基础已实现；执行记录见[B00 Completion](../completions/B00_COMPLETION.md)，只证明construction证据，不证明runtime已通过。
- [`B01_EXECUTION_0_4_CONTROL_FOUNDATION.md`](B01_EXECUTION_0_4_CONTROL_FOUNDATION.md)：`completed`，已实现纯Execution `0.4` records、budget/lifecycle replay、trusted clock、bounded projection与cross-head integrity；见[B01 Completion](../completions/B01_COMPLETION.md)。未接入默认产品图，不授权后续durable/product实现。
- [`B02_DURABLE_CONTROL_OPERATIONS.md`](B02_DURABLE_CONTROL_OPERATIONS.md)：`completed`；单一coordinator、bootstrap/advance/Pause/Resume/Replay/Fork/Cancel/interrupt/terminal及failure recovery交付。Construction30/30，205个boundary下1410个独立runtime case全部通过；见[B02完成记录](../completions/B02_COMPLETION.md)。
- [`B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md`](B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md)：`blocked`；C05/C06已完成，来源前置已关闭，现因A05状态投影/golden授权边界待补充审阅。原冻结正文不变，canonical实现及28项construction、645 runtime仍未完成。
- [`B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md`](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)：拟接入A01产品图、四层fallback、Human return、A03 invalidation与A06 admission/grant/stop；当前只供review，不可执行。
- [`B05_ACCEPTANCE_INTEGRATION_AND_END_TO_END_HARNESS.md`](B05_ACCEPTANCE_INTEGRATION_AND_END_TO_END_HARNESS.md)：拟完成cross-system faults/concurrency、CLI smoke、legacy/mock regression及final zero-gap exit；当前只供review，不可执行。

Draft proposed ownership固定为：B00 15项、B01 11项、B02 30项、B03 28项、B04 47项，五个slice互斥并集为131项；B05不拥有catalog ID，只补充保持原owner的final场景并接入统一final exit检查。该分配只有在各ticket经过review并提升为`ready`后才成为执行合同。

草稿还统一了兼容与治理边界：0.2验证来源后仅replay；0.3禁止原地resume/migration，但合格来源可replay/fork为0.4 child；0.4遵守冻结fingerprint/source proof/资格。B01提供policy/record/clock校验基础，B02可信入口在bootstrap前核验initial Cycle、Planner Attempt、START Transition及terminal reserve并持久化decision，caller/Agent/test不能注入allow；B04负责后续产品admission。每票Allowed Files包含本票maintenance记录及corrections index追加，已有历史不可改写；缺失前置功能或合同/架构/验收边界变化仍须corrective ticket。

当前matrix包含B00/B01/B02三个slice。B00/B01/B02 construction分别为 **15/15、11/11、30/30**，累计映射 **56/131、remaining75**。B02的 **205个boundary、1410个独立case** 全部具有同一冻结输入、同一fresh session的通过证据；完整suite **2617 passed**。全局final仍仅报告 **75 coverage / 789 runtime / 15 exit** 缺口，`requirements.passed=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。独立清单为324个boundary、2199个case，保留全部28个post-claim组合；B03初始reservation义务按B00C05窄修正，B04集合保持。

2026-09-22已复核上述交付，新增114项定向回归通过。B03–B05仍为draft，已澄清START/Human owner、消费完整性失败、B03预留责任、corrective基线、前置golden派生同步与完整分批验收；B03/B04分别保留101/654、18/144个boundary/case，见[本轮审查记录](../corrections/B00_B05_READINESS_REVIEW.md)。B03须审定为ready后实施，不因B02完成而自动开始。

## 退出门槛

B00已建立final统一驱动机制，实际退出适配器仍由B05接入：同一次调用必须执行并核验Layer 0–5、cross-system fault/concurrency、Phase B suite、完整pytest、compileall、synthetic tests、full mock benchmark、legacy regression、CLI smoke及文档/scope检查。任一缺失、失败或证据无效均非零；benchmark退出0但任一case/checklist失败也不通过。只有`requirements_zero_gap=true`且全部退出证据有效时才可`phase_b_complete=true`，不能先生成成功报告再补smoke/benchmark。

B04的131 covered/0 remaining仅表示映射齐全；允许调用final作负向探针，缺runtime或exit evidence必须机器失败。Completion record仍须列出每层命令、摘要与totals、full suite、mock benchmark、smoke root及deferred capabilities。

当前 physical `codex_handoff` / canonical `legacy_codex_handoff` 仅为兼容路径，不能计入canonical A01 coverage。Phase B使用A05 `CodeAgentSubgraph + FakeCodingBackend`，不安装或调用Codex SDK、不运行live provider、不读取raw numeric data、不复用历史`outputs/`，也不实现parallel graph。真实隔离backend属于Phase C，parallel control需要未来独立design ticket。

## 退出方向

整个Phase B完成后进入Phase C，先执行C00 capability gate。当前B00–B02及B00C01–B00C06、B02C01已完成；B03因状态投影/golden授权边界保持blocked，B04/B05仍须分别审定。

2026-09-18批准后：B02C01 ready快照为`5e753d6`，当前in_progress，见[执行记录](../completions/B02C01_COMPLETION.md)。原B02批准范围继续有效，其30项slice与全量控制验收仍待完成。

2026-09-18验证完成：B02C01已completed，真实0.2 source只读Replay及历史fingerprint缺失证明通过78项定向、833项全量测试；B00/B01 fresh construction仍15/15、11/11。原B02继续in_progress，coverage仍26/remaining105，不能将本次兼容修正当作整票完成。

2026-09-18最新：B02C01 completed；B02继续实现后因0.3 Fork历史head无法进入B00 trace 0.2而blocked。[B00C03](B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)为review、未批准实施。Normal external/timeout/失败收尾/preparation/historical reader的控制进展不代表B02完整验收；covered26/remaining105不变，见[B02 completion](../completions/B02_COMPLETION.md)。

2026-09-21：[B00C03](B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)已completed，ready快照`3c53a41`。历史0.3 Fork来源绑定轨迹已通过完整1063项回归；原B02恢复执行，仍未完成30项construction及205/1488 runtime bindings。B00/B01为15/15、11/11，mapped26/remaining105；B03–B05仍draft。详见[完成记录](../completions/B00C03_COMPLETION.md)。

2026-09-21后续：B02因首次reservation事务未提交、无原operation的fault outcome未被冻结case集合表达而blocked。[B00C04](B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)为review草案、未实施；B00C03保持completed。六项真实回滚/immutable replay检查通过，详见[B02最新记录](../completions/B02_COMPLETION.md#2026-09-21--reservation-fault-case-executability-audit)。

## 2026-09-21 B00C04 integrated correction

B00C04已按用户批准扩充并in_progress，统一完成case0.2、trace0.4与进程证据前置。现行独立case2214/B02义务1416；B02仍blocked，待C04完整验证后恢复原票运行修复和30项construction，当前covered26/remaining105。

2026-09-21 B00C04完成：case0.2、trace0.4、直接production进程回执及严格分批验证落地；旧1488个B02 case为1370 retained/118 replaced，现行B02 **1416**、总数 **2214**，全部324 boundary及B03/B04集合不变。完整pytest **1118 passed**、新增定向 **32 passed**，fresh B00/B01 **15/15、11/11**，coverage26/remaining105。Global passed null、phase_b_complete false。B02验收前置阻塞已解除，接续原票处理已审定的runtime缺陷及完整验收；本修正票不代表B02完成。证据见[B00C04完成记录](../completions/B00C04_COMPLETION.md)。

2026-09-21 C04补充审查：Fork `child.source_revision_cas`在首次reservation提交前，两项独立进程反例均完整回滚。沿用原票已批准的全boundary审查范围补齐这一遗漏；C04重新in_progress，B02暂为blocked。旧1488个B02 case现为1362 retained/126 replaced，现行总数 **2208**、B02 **1410**，减少78均有提交前反例；324 boundary、B03/B04及28 post-claim保持。之前2214/1416及C04完成报告保留为当时验证事实。coverage仍26/105；尚无B02 slice。

2026-09-21 C04集成补验完成：完整pytest1158 passed，fresh B00/B01 15/15、11/11；C04现completed，B02继续in_progress。现行独立case2208/B02 1410，covered26/remaining105，尚无B02 slice；此前blocked及补验in_progress为历史过程。详见[B00C04完成记录](../completions/B00C04_COMPLETION.md)。

2026-09-21 B02验收接线：C04已completed后，新增B02完整30项slice、5条完整来源轨迹及1410个独立runtime case绑定。初始reservation的两项C04进程反例作为并列必需final证据保留，没有移除旧正负检查；历史trace回归只隔离其B00/B01前置slice，完整matrix另行验证。现行映射56/131、remaining75；B02仍in_progress，正执行fresh验收，不能将接线或离线通过当作完成。全局final规则未改变，其他票据798个runtime binding及15项exit仍未交付。

2026-09-24：B03已获明确执行授权，ready快照`b78c15a`。独立进程证明首次external stub在COMMIT前完整回滚，但当前独立case未明确表达该上下文，B03现blocked，已完成[B00C05](B00C05_EXTERNAL_RESERVATION_FAULT_CASE_SEMANTICS.md)。现行324/2208与B03 101/654不变；case0.3/645/2199只是待批准方案，详见[B03执行记录](../completions/B03_COMPLETION.md)。

2026-09-24 B00C05续执行：用户批准补齐审阅建议并执行，ready冻结于`52c508b`；真实初始producer入口与case0.3修正已实现，70项定向检查通过，完整集成验证尚未完成。工作树独立集合为2199/B03 645，前置B02 1410、B04 144及28 post-claim保持；B03仍blocked，不能把此项修正计为canonical Backend完成。此前2208/654/798计数为case0.2冻结基线。

2026-09-24 B00C05完成：B00C05已完成并解除B03首次ExternalOperation reservation分类阻塞：真实初始producer与case0.3已验证，独立集合2199（B02 1410、B03 645、B04 144），324 boundaries和28 post-claim不变。Fresh B00/B01/B02为15/11/30，完整2617 passed、同Session B02-owned 1410/1410；mapped56/remaining75，final仅75 coverage / 789 runtime binding / 15 exit，global passed=null、Phase B未完成。B03恢复ready，canonical Backend与其28项验收仍待交付。

2026-09-24 B03接续审查：B00C05已completed并提交为`7af288c`；真实B02 Code target/C05 producer及A05/A06 contract-shaped数据反例确认trace0.4存在派生摘要投影缺口，B03现blocked，待审B00C06。反例不计canonical Backend验收；case0.3、2199/645及mapped56/remaining75不变。详见B03执行记录最后条目。

2026-09-24 B00C06：用户批准补强、冻结提交并执行，ready commit `cd29d9f`。显式 trace 0.5 / proof 0.2 及 A05 全链 contract/meta 证据正在集成验证，旧 trace、旧 goldens、src、case0.3 不变。B03 暂保持 blocked；通过后仅解除来源轨迹前置，预算事务和状态投影兼容仍须独立核验。

2026-09-24 B00C06完成：trace0.5/proof0.2 全链来源与四条验收路径通过，2677 passed、同 Session B02 runtime1410/1410，fresh B00/B01/B02为15/11/30；mapped56/remaining75，final仅75/789/15。旧trace、旧goldens、src、case0.3保持。B03来源阻塞已解除，但接续实证确认A05空字段投影超出原fingerprint-only golden授权，因该独立边界继续blocked，待窄范围补充审阅。

2026-09-24：已形成待审 [B00C07 状态投影与 golden 窄范围补充](B00C07_A05_STATE_PROJECTION_GOLDEN_HANDOFF.md)。该票为 review，尚未批准或执行；只提出 B03 的版本隔离、已知 nullable projection 派生同步与兼容核验边界，不预先交付 runtime。原 B03 授权保留，但依其冻结 Stop Conditions 暂保持 blocked，待本补充批准后继续。

2026-09-24：B00C07已按用户同意补强，ready冻结于`7ab58ce`并完成文档交接。B03恢复ready；四个canonical paths来源修复与B02 needs_input fixture窄替换获得明确授权，尚未实现。先推进B03预算事务/失败恢复，再完成canonical实现与28/645验收；当前mapped56/remaining75、Phase B未完成。

2026-09-24 B03接续：B00C07已完成治理交接，但新注册member反例确认其B02 fixture替换与禁止trace0.5的限制冲突，B03再次blocked，待审B00C08。未修改production或golden；15项定向反例/回归通过。当前mapped56/remaining75，预算事务与canonical B03仍未实现。 见[B00C08待审票](B00C08_B02_CANONICAL_EVIDENCE_TRACE_HANDOFF.md)。

2026-09-24：B00C08在13f3b74冻结并完成治理交接；B03恢复ready。Normal/timeout完整来源、source trace0.5、独立Analysis success前置及其golden审计范围已批准，尚待B03实现。预算事务与canonical交付未完成，mapped56/remaining75、Phase B未完成。
