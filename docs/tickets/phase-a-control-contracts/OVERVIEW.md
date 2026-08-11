# Phase A：控制合同澄清

## Status

`in_progress`

## 目标

确认第二阶段的控制层合同，包括允许路线、执行身份、artifact 失效、pause/resume、Code Agent 接口、循环预算和 Phase B harness 验收条件；当已执行内容与已确认合同不一致时，使用独立 implementation ticket 先完成纠偏和验证。

本阶段主要产生经过确认的设计与核心文档更新，不以大规模能力开发为目标。A02 是明确的 corrective implementation：它必须把 execution identity 接到当前 runtime，不能再次被降成纯设计 ticket；这不授权提前实现 A03–A07。

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

## Draft Tickets

- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)
- [`A05_CODE_AGENT_CONTRACT.md`](A05_CODE_AGENT_CONTRACT.md)
- [`A06_BUDGETS_AND_STOP_CONDITIONS.md`](A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [`A07_PHASE_B_HARNESS_ACCEPTANCE.md`](A07_PHASE_B_HARNESS_ACCEPTANCE.md)

A01 已完成逻辑 transition contract。A02 已完成 formal Run、current-route transition allocation、canonical Attempt kinds、Human single-use identity，以及 full-suite、文档、scope 和 metadata 验收；四层 fallback 仍只经过 identity harness。A03–A07 当前仍为 `draft`，必须分别经过用户确认并提升为 `ready` 后才能执行。
