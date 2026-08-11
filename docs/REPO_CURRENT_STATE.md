# Repository Current State

## 状态摘要

- **更新时间**：2026-08-11
- **当前分支**：`codex/phase-11-agent-harness-upgrade`
- **当前阶段**：Phase A 控制合同澄清；A01 路由合同已完成
- **活动 ticket**：无；A01 `completed`，A02–A07 仍为 `draft`
- **稳定基线**：[`v0.2-demo`](milestones/V0_2_DEMO_BASELINE.md)
- **本轮范围**：完成 A01 transition contract 并同步核心文档；不修改 runtime、graph、tests 或 `AnalysisState`

## 当前稳定实现

`v0.2-demo` 已经提供一个可独立演示的科研多 Agent MVP：

- real LangGraph `StateGraph` 与 deterministic default path；
- Method Planner、file-based Codex Handoff、Analysis Engineer、Scientific Reviewer、Decision Coordinator、Human Approval Gate、Memory and Report；
- SQLite/Memory checkpoint、structured routing、manifest 与 final report；
- allowlisted synthetic analysis、Golden Demo 与 synthetic benchmark；
- optional OpenAI/DeepSeek provider path、strict structured output、local evidence safety floor 与 run-local `llm_calls/` audit；
- high/critical 风险的 Human Gate 与 accepted-memory protection；
- local web console 与 CLI entry points。

第一阶段的 Phase 0–10D 分组成果、复现方式和已知限制不再在本文件累积，统一固定在 [V0_2_DEMO_BASELINE.md](milestones/V0_2_DEMO_BASELINE.md)。

## 第二阶段控制合同状态

已经建立：

- [Docs Index](README.md) 与文档权威顺序；
- [Ticket Workflow](tickets/README.md) 和 [Ticket Template](tickets/TEMPLATE.md)；
- Phase A–E 目录与 Overview；
- Phase A A01–A07 的 control-contract tickets；
- 独立的 `v0.2-demo` milestone 文档；
- 第一阶段 Legacy 规则迁移与删除记录；
- 核心规则文档的第二阶段定位。

A01 已确认：

- graph-level re-review、rerun、code fix 和 replan 由 Decision Coordinator 统一派发；
- low/medium、诊断唯一且预算可用时允许自动回退；high/critical、诊断歧义、重复失败或预算耗尽进入 Human Gate；
- Coordinator 的四层回退目标是 Reviewer、Analysis、Code 和 Planner；
- Human Gate 统一处理 clarification、approval 和 external action，进出只连接 Coordinator；
- 完整 event log 不直接进入 Agent prompt；Agent 使用 scoped context 和相关 attempt history；
- target contract 尚未接入 runtime，具体 identity、invalidation、resume、Code Agent 和 budget 由 A02–A06 继续定义。

第二阶段文档迁移此前已通过 scope check、Markdown link check、ticket metadata、tag、`git diff --check` 与完整 `pytest -q` 验收。

## 当前验证状态

稳定 milestone 与当前 working tree 的验证结果为：

- milestone 封版：`162 passed`；
- Legacy 清理与第二阶段文档迁移后：`162 passed in 4.30s`；
- 9-case full mock synthetic benchmark passed
- 5-case live-provider demo passed
- Golden Demo smoke passed

本轮按计划没有运行 live-provider 测试；上面的 live-provider 与 benchmark 结果是 milestone 的冻结事实。第二阶段文档迁移当时还额外验证了 29 个现行 Markdown 文件的相对 links、Legacy 删除前的规则/依赖审计、当时的 A01–A07 draft 状态、Phase B–E overview-only 结构，以及 `v0.2-demo` 仍 peel 到 `e73e4d3b967008f290259851caf05f28e087cd5b`。第一阶段原始文档仍可从该 tag 恢复。

A01 是纯设计 ticket，没有运行 runtime 或 live-provider tests；本轮验收使用 ticket metadata、scope、Markdown relative links、stale-documentation scan 和 `git diff --check`。

## 下一项工作

下一步不是直接修改 graph，而是讨论 [A02 Run/Cycle/Attempt Model](tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md)，把 A01 的四层回退转换为明确 execution identity 和父子关系。

建议顺序：

1. A02 确认 Run/Cycle/Attempt identity 与 Agent-scoped attempt history；
2. A03–A06 依次确认 invalidation、resume、Code Agent 和 budget contracts；
3. A07 锁定 Phase B harness acceptance；
4. Phase B 通过后再进入真实 Code Agent 与 Agent capability 增强。

## Blockers

当前无 runtime blocker。

治理上的主动限制是：A01 只批准目标控制合同，不批准新 state field、artifact schema 或 runtime edge。A02–A07 仍为 `draft`，因此当前没有可执行的 graph implementation ticket。这是预期状态，不是项目故障。

## 入口

- [Docs Index](README.md)
- [下一阶段改进方向](NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md)
- [Phase A Overview](tickets/phase-a-control-contracts/OVERVIEW.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
