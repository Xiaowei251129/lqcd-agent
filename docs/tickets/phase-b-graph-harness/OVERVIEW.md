# Phase B：图与 Harness 可靠性

## Status

`planned`

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

以下为[B00草稿](B00_ACCEPTANCE_FOUNDATION.md)拟统一的验收协议，尚未成为ready执行合同：每个scenario使用`validation_stage=construction | final`，保持原requirement owner；construction仅确认当前slice的construction证据，累计`requirements.covered/remaining`仅表示映射覆盖与缺口，未重验的全局`requirements.passed/passed_ids=null`，两个完成标志均为false。

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

这些阶段级进入条件已由A07 completion满足，但Phase B仍为`planned`：B00已由用户批准为`ready`；B01–B05保持`draft`，尚不可执行。Execution仍严格按依赖顺序从B00开始；后续draft的存在不表示前置条件已满足。

## Draft Tickets

- [`B00_ACCEPTANCE_FOUNDATION.md`](B00_ACCEPTANCE_FOUNDATION.md)：已批准为`ready`，执行范围为protocol generated projection、strict matrix validator、pytest evidence、normalized trace codec和failpoint registry。
- [`B01_EXECUTION_0_4_CONTROL_FOUNDATION.md`](B01_EXECUTION_0_4_CONTROL_FOUNDATION.md)：拟建立Execution `0.4` records、budget/lifecycle foundation、trusted clock、bounded projection与cross-head integrity；当前只供review，不可执行。
- [`B02_DURABLE_CONTROL_OPERATIONS.md`](B02_DURABLE_CONTROL_OPERATIONS.md)：拟实现single SQLite coordinator、ControlOperation、Pause/Resume/Replay/Fork/Cancel、terminal ownership与restart recovery；当前只供review，不可执行。
- [`B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md`](B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md)：拟实现CodeAgentSubgraph、Fake Backend、ExternalOperation、trusted verification、Code Bundle与fresh Analysis；当前只供review，不可执行。
- [`B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md`](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)：拟接入A01产品图、四层fallback、Human return、A03 invalidation与A06 admission/grant/stop；当前只供review，不可执行。
- [`B05_ACCEPTANCE_INTEGRATION_AND_END_TO_END_HARNESS.md`](B05_ACCEPTANCE_INTEGRATION_AND_END_TO_END_HARNESS.md)：拟完成cross-system faults/concurrency、CLI smoke、legacy/mock regression及final zero-gap exit；当前只供review，不可执行。

Draft proposed ownership固定为：B00 15项、B01 11项、B02 30项、B03 28项、B04 47项，五个slice互斥并集为131项；B05不拥有catalog ID，只补充保持原owner的final场景并接入统一final exit检查。该分配只有在各ticket经过review并提升为`ready`后才成为执行合同。

草稿还统一了兼容与治理边界：0.2验证来源后仅replay；0.3禁止原地resume/migration，但合格来源可replay/fork为0.4 child；0.4遵守冻结fingerprint/source proof/资格。B01提供policy/record/clock校验基础，B02可信入口在bootstrap前核验initial Cycle、Planner Attempt、START Transition及terminal reserve并持久化decision，caller/Agent/test不能注入allow；B04负责后续产品admission。每票Allowed Files包含本票maintenance记录及corrections index追加，已有历史不可改写；缺失前置功能或合同/架构/验收边界变化仍须corrective ticket。

当前B00为唯一`ready` Phase B ticket；尚无matrix、Phase B tests或runtime实现。

## 退出门槛

草稿采用final统一驱动：同一次调用必须执行并核验Layer 0–5、cross-system fault/concurrency、Phase B suite、完整pytest、compileall、synthetic tests、full mock benchmark、legacy regression、CLI smoke及文档/scope检查。任一缺失、失败或证据无效均非零；benchmark退出0但任一case/checklist失败也不通过。只有`requirements_zero_gap=true`且全部退出证据有效时才可`phase_b_complete=true`，不能先生成成功报告再补smoke/benchmark。

B04的131 covered/0 remaining仅表示映射齐全；允许调用final作负向探针，缺runtime或exit evidence必须机器失败。Completion record仍须列出每层命令、摘要与totals、full suite、mock benchmark、smoke root及deferred capabilities。

当前 physical `codex_handoff` / canonical `legacy_codex_handoff` 仅为兼容路径，不能计入canonical A01 coverage。Phase B使用A05 `CodeAgentSubgraph + FakeCodingBackend`，不安装或调用Codex SDK、不运行live provider、不读取raw numeric data、不复用历史`outputs/`，也不实现parallel graph。真实隔离backend属于Phase C，parallel control需要未来独立design ticket。

## 退出方向

完成后进入Phase C，先执行C00 capability gate，再把Fake Code Agent替换为通过门禁的隔离真实实现。当前下一步执行已批准为`ready`的B00；B01–B05仍须独立review，不因B00批准而获得执行授权。
