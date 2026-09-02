# Phase A：控制合同澄清

## Status

`in_progress`

## 目标

确认第二阶段的控制层合同，包括允许路线、执行身份、artifact 失效、pause/resume、Code Agent 接口、循环预算和 Phase B harness 验收条件；当已执行内容与已确认合同不一致时，使用独立 implementation ticket 先完成纠偏和验证。

本阶段主要产生经过确认的设计与核心文档更新，并在合同要求时执行边界明确的 corrective implementation。A02 已接入 execution identity，A03 已接入 artifact namespace/invalidation；这不授权提前实现 A04–A07。

## 进入条件

- `v0.2-demo` 基线已冻结；
- 第二阶段文档与 ticket 工作流已建立；
- 第一阶段原始计划已归档在 milestone/tag 中，不作为当前执行入口。

## 退出条件

- A01–A07 均经过讨论并完成；
- 已确认的设计同步进入核心 source-of-truth 文档；
- Phase B 可以在不自行补充架构决定的情况下建立实现 tickets；
- 未解决问题被明确记录，而不是隐藏在实现假设中。

## Completed Tickets

- [`A01_TRANSITION_MATRIX.md`](A01_TRANSITION_MATRIX.md)
- [`A02_RUN_CYCLE_ATTEMPT_MODEL.md`](A02_RUN_CYCLE_ATTEMPT_MODEL.md)
- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)

## Completed Corrective Tickets

- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)：在不修改原A03 ticket的前提下，已绑定registry与execution ledger全局head及Transition target shape。

执行结果与后续纠偏历史分别记录在[`../completions/`](../completions/README.md)和[`../corrections/`](../corrections/README.md)；completed ticket正文不再承担累积日志功能。

## Review Tickets

- [`A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md`](A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)
- [`A05_CODE_AGENT_CONTRACT.md`](A05_CODE_AGENT_CONTRACT.md)
- [`A06_BUDGETS_AND_STOP_CONDITIONS.md`](A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [`A07_PHASE_B_HARNESS_ACCEPTANCE.md`](A07_PHASE_B_HARNESS_ACCEPTANCE.md)

A01已完成逻辑transition contract。A02已完成formal execution identity；A03已完成immutable Attempt artifact namespace、typed current index、managed projections、Human Response snapshots及四层invalidation harness；A03C01已补齐execution global-head与Transition target-shape完整性。四层fallback仍是harness-only，不是产品edges。

2026-08-26至27日交叉审查先后闭合schema `0.4` bootstrap、Transition/invalidation、Pause双阶段发布、Run lifecycle、durable coordinator、single-owner closure与External resolution CAS。最新修订把system interrupt从`cancel_pause`中拆为internal `resolve_external_interrupt/recoverable_timeout | controlled_halt | integrity_failure`，让safe timeout恢复到Coordinator、terminal stop关闭Run、unavailable proof统一形成Pause N/A/quarantine与Run unavailable closure；并进一步把preexisting cancel/interrupt结果改为可达的只读winner observation、禁止`normal + unavailable`、冻结上下文/trigger唯一stop route。十一种ControlOperation组合均有reservation overlay；所有multi-successor phase使用互斥穷尽guard，typed-null与External proof使用tagged evidence union。tracked [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json) machine schema 0.4是上述phase、guard、terminal tuple、组合owner状态、CAS、stop route、authority、evidence、outcome和construction DAG的单一机器枚举，并由[`scripts/validate_phase_a_control_protocol.py`](../../../scripts/validate_phase_a_control_protocol.py)在冻结前验证。A02C01与A04–A07保持`review`；独立交叉审核和用户最终确认前不得提升为`ready`或执行。
