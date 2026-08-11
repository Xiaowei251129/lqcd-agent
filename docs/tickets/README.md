# 第二阶段 Ticket 工作流

## 目的

Ticket 是一次具体工作的执行合同，不是当前系统事实的长期来源。方向文档说明为什么改进，Phase Overview 说明阶段目标，ready ticket 说明本次具体做什么，核心 source-of-truth 文档说明执行后系统实际变成什么。

执行 ticket 前必须先阅读：

- [`../../AGENTS.md`](../../AGENTS.md)
- [`../README.md`](../README.md)
- ticket 的 `Read First`

## 生命周期

```text
draft → review → ready → in_progress → completed
                     ↘ blocked
draft/review/ready → superseded
```

- `draft`：正在讨论，不能执行；
- `review`：内容基本形成，等待最终确认，不能执行；
- `ready`：用户已经确认，可以执行；
- `in_progress`：正在执行；
- `completed`：目标和验证已完成；
- `blocked`：满足 Stop Conditions 或存在外部阻塞；
- `superseded`：已被新的设计或 ticket 替代。

只有用户确认后的 `status: ready` ticket 可以进入执行。Codex 不得自行把 ticket 从 `draft` 或 `review` 提升为 `ready`。

## 执行规则

- 一个 ticket 只解决一个可以验证的目标；
- Phase Overview 不是执行 prompt；
- 严格遵守 Allowed Files、Do Not Touch 和 Stop Conditions；
- deterministic/mock path 保持默认；只有 ticket 明确批准时才能改变 provider 或 data policy；
- ticket 不能静默放宽 `AGENTS.md`、raw-data、security、approval 或 public contract；
- 需要新 state field、artifact schema、graph edge、status value 或 dependency 时，如果 ticket 没有明确批准，必须停止；
- 实现 Agent/Node 的 ticket 必须把它接入 graph 与相应 harness；如果本轮明确只做 standalone module，必须写出原因和后续 integration ticket；
- 验证必须与风险相称，并记录实际结果；
- verification 默认使用 `/private/tmp/lqcd-agent-...` 或新的 run id，不能把历史 `outputs/` 当成验收证据；
- 完成后同步受到影响的核心文档和 `REPO_CURRENT_STATE.md`；
- 架构、政策、schema 或阶段顺序发生变化时，追加 `DECISION_LOG.md`；
- final response 前执行 stale-documentation scan：检查根 README、相关核心文档、Current State、Decision Log 和本次涉及的 TODO 是否仍与实现一致，只修改本 ticket 导致过时的内容；
- completed ticket 只追加 Completion Record 或事实勘误，不重写原始目标；
- completed ticket 是工作记录，不能替代当前核心文档。

## 使用方式

用户可以指定一个 ready ticket，例如：

```text
Codex，请执行 docs/tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md
```

Codex 应先验证其 `status`，再按 ticket 的完整合同执行。如果状态不是 `ready`，只能继续讨论或完善 ticket，不能实施其内容。

## 阶段目录

- [`phase-a-control-contracts/OVERVIEW.md`](phase-a-control-contracts/OVERVIEW.md)：控制合同澄清；
- [`phase-b-graph-harness/OVERVIEW.md`](phase-b-graph-harness/OVERVIEW.md)：图与 harness 可靠性；
- [`phase-c-code-agent/OVERVIEW.md`](phase-c-code-agent/OVERVIEW.md)：graph-managed Code Agent；
- [`phase-d-agent-capabilities/OVERVIEW.md`](phase-d-agent-capabilities/OVERVIEW.md)：Agent 能力与物理知识；
- [`phase-e-integrated-benchmark/OVERVIEW.md`](phase-e-integrated-benchmark/OVERVIEW.md)：综合 benchmark 与下一 milestone。

新 ticket 必须从 [`TEMPLATE.md`](TEMPLATE.md) 创建。
