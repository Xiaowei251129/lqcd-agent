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

Construction模式只验证当前ticket owned subset并明确报告remaining IDs，不能用placeholder、skip或xfail伪造覆盖。B05 final模式要求catalog required IDs与required scenarios coverage set-equal；unknown、non-required、duplicate、stale、uncollectable、skipped、xfail、deselected、live-only或缺失trace/invariant都必须非零退出。Completion evidence必须报告matrix digest、required/covered/passed totals和zero-gap结果，不能只写pytest总数。

## Implementation Ticket 拆分

A07只冻结以下拆分，没有创建这些ticket文件：

1. **B00 — Acceptance Foundation**：strict protocol/catalog/matrix schemas与validators、pytest collection、normalized trace codec和failpoint registry；
2. **B01 — Execution 0.4 Control Foundation**：budget policy/ledger、Run lifecycle、bounded projection、trusted clock、canonical validators与cross-head integrity；
3. **B02 — Durable Control Operations**：durable coordinator、ControlOperation guarded graph、leases/fencing、Pause/Resume/Replay/Fork/Cancel、internal advance/pause/close/interrupt、ownership、child saga与restart recovery；
4. **B03 — Graph-managed Fake Code Agent**：CodeAgentSubgraph、Fake backend port、ExternalOperation/watchdog/containment、ingress/trusted verification、canonical bundle与fresh Analysis；
5. **B04 — Target Product Topology and Budgeted Loops**：接入A01产品edges、四层fallback、Human Gate return、A03 invalidation与A06 admission/grant/stop；
6. **B05 — Acceptance Integration and End-to-End Harness**：完整normalized traces、fault/concurrency、compatibility、CLI smoke与最终zero-gap evidence。

依赖固定为B00；B01 depends on B00；B02 depends on B00/B01；B03 depends on B00–B02；B04 depends on B00–B03；B05 depends on B00–B04。每张票必须独立冻结Allowed Files、Do Not Touch、migration边界、owned requirement IDs与focused verification，不能合并成一张未审查的大票。

## 进入条件

- Phase A A01–A07、A02C01及A03C01全部completed；
- frozen Control Protocol与requirement catalog的exact SHA-256已由A07 completion记录，且design validator通过；
- transition、identity、invalidation、resume、budget 和 harness acceptance 已进入核心文档；
- 实现者不需要自行补充控制层设计决定。

这些阶段级进入条件已由A07 completion满足，但Phase B仍为`planned`：当前没有B00–B05 ticket，必须先起草B00并经过`draft → review → ready`确认，不能直接修改runtime。

## 退出门槛

Phase B只有在matrix final模式zero-gap、所有required deterministic scenarios无skip/xfail/unknown、Layer 0–5 focused suites与完整`pytest -q`通过、compileall通过、synthetic tests与full mock benchmark通过、全新CLI smoke验证ledger/state/checkpoint/artifact/budget/Pause/child/accepted invariants、legacy regression单独通过，以及links/metadata/scope/stale-doc/diff检查闭合后才能完成。Completion record必须列出每层命令、matrix digest与totals、full suite、mock benchmark、smoke root及deferred capabilities。

当前 physical `codex_handoff` / canonical `legacy_codex_handoff` 仅为兼容路径，不能计入canonical A01 coverage。Phase B使用A05 `CodeAgentSubgraph + FakeCodingBackend`，不安装或调用Codex SDK、不运行live provider、不读取raw numeric data、不复用历史`outputs/`，也不实现parallel graph。真实隔离backend属于Phase C，parallel control需要未来独立design ticket。

## 退出方向

完成后进入Phase C，先执行C00 capability gate，再把Fake Code Agent替换为通过门禁的隔离真实实现。当前下一步仅是起草B00 Acceptance Foundation；尚无可执行Phase B ticket。
