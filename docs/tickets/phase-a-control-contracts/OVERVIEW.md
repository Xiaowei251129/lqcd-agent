# Phase A：控制合同澄清

## Status

`completed`

## 目标

确认第二阶段的控制层合同，包括允许路线、执行身份、artifact 失效、pause/resume、Code Agent 接口、循环预算和 Phase B harness 验收条件；当已执行内容与已确认合同不一致时，使用独立 implementation ticket 先完成纠偏和验证。

本阶段主要产生经过确认的设计与核心文档更新，并在合同要求时执行边界明确的 corrective implementation。A02 已接入 execution identity，A03 已接入 artifact namespace/invalidation；完成A04等设计ticket不授权提前接入其目标runtime。

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
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)：已冻结Pause/Resume/Replay/Fork、Run lifecycle、single-use claim、terminal ownership与compatibility目标合同；没有修改当前runtime。
- [`A05_CODE_AGENT_CONTRACT.md`](A05_CODE_AGENT_CONTRACT.md)：已冻结graph-managed `CodeAgentSubgraph`、replaceable `CodingBackend`、isolated workspace、trusted verification、canonical bundle与fresh Analysis handoff目标合同；没有实现Code Agent runtime。
- [`A06_BUDGETS_AND_STOP_CONDITIONS.md`](A06_BUDGETS_AND_STOP_CONDITIONS.md)：已冻结immutable policy、admission/reservation、failure fingerprint、single-use grant、Pause deadline、terminal reserve与fail-closed stop目标合同；没有实现budget runtime。
- [`A07_PHASE_B_HARNESS_ACCEPTANCE.md`](A07_PHASE_B_HARNESS_ACCEPTANCE.md)：已冻结六层deterministic acceptance、machine-readable matrix/catalog、exact trajectory、fault/concurrency、B00–B05拆分与zero-gap exit gate；没有创建或执行Phase B tickets。

## Completed Corrective Tickets

- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)：在不修改原A03 ticket的前提下，已绑定registry与execution ledger全局head及Transition target shape。
- [`A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md`](A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)：已完成schema `0.4+` bootstrap后继合同、版本边界与Phase B实现约束的治理同步；没有修改schema `0.2` runtime。

执行结果与后续纠偏历史分别记录在[`../completions/`](../completions/README.md)和[`../corrections/`](../corrections/README.md)；completed ticket正文不再承担累积日志功能。

## Ready Tickets

无。Phase A已闭合；Phase B尚无经过确认的`ready` implementation ticket。

A01已完成逻辑transition contract。A02已完成formal execution identity；A03已完成immutable Attempt artifact namespace、typed current index、managed projections、Human Response snapshots及四层invalidation harness；A03C01已补齐execution global-head与Transition target-shape完整性。四层fallback仍是harness-only，不是产品edges。

用户已最终确认`f4f0eaa`设计；A01–A07及A02C01/A03C01已按冻结合同闭合，Phase A退出条件满足。A02C01/A04–A07完成只表示目标合同、治理文档和completion evidence已闭合，不代表schema `0.4`、durable resume、Code Agent、budget manager、acceptance matrix或Phase B product graph已实现。B00–B05现已在Phase B目录起草；各票当前状态以其front matter与Phase B Overview为准，仍须独立批准并按冻结依赖顺序执行。

## 合同与验收入口

- 各所属票据保存规则、设计理由和stable requirement IDs；[A07](A07_PHASE_B_HARNESS_ACCEPTANCE.md)定义验收方法、跨合同断言及故障注入边界。
- [Control Protocol 0.4](CONTROL_PROTOCOL_0_4.json)保存唯一机读协议，[需求目录](PHASE_B_REQUIREMENT_CATALOG.json)关联requirement IDs与所属票据。
- [Verification Guide](../../VERIFICATION_GUIDE.md)提供验证入口，[Repo Current State](../../REPO_CURRENT_STATE.md)记录当前结果，[Decision Log](../../DECISION_LOG.md)保留设计变化及理由。
