---
ticket_id: A02
phase: phase-a-control-contracts
status: draft
type: design
depends_on: [A01]
---

# 定义 Run、Cycle 与 Attempt 模型

## Goal

确认第二阶段如何表达一次完整科研任务、一次方法到决策循环和可重试工作单元，并定义它们的身份和父子关系。

## Why

当前 state 主要保存单套 artifact paths，无法可靠表达多轮 rerun、code fix 和 replan 历史。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md`

## Scope

- 比较最小两层和三层身份模型；
- 定义身份稳定范围、父子关系和触发原因；
- 讨论 checkpoint thread、run directory 与 execution identity 的关系；
- 确定哪些信息进入 state，哪些只进入 artifacts。

## Non-goals

- 不实现 schema 或目录迁移；
- 不决定具体 invalidation 规则；
- 不修改 checkpoint backend。

## Allowed Files

- 本 ticket 文件；
- 经讨论明确批准的核心文档。

## Do Not Touch

- `src/`
- `tests/`
- `configs/`
- `raw_data/`
- `outputs/`

## Requirements

- 逻辑回退不能覆盖历史；
- identity 必须支持 provenance 和确定性测试；
- 模型保持满足需求的最小复杂度；
- 未确认字段不能提前进入 public schema。

## 待确认问题

- 最小模型需要 Run/Cycle/Attempt 三层，还是 Run/Attempt 两层已经足够？
- plan、code、analysis、review 是否共享一种 attempt，还是需要不同 subtype？
- 哪一层拥有 `checkpoint_thread_id`，哪一层拥有 output namespace？
- 新 attempt 的 identity 应在 transition 前创建，还是由目标节点开始时创建？

## Deliverables

- 经确认的身份层次和术语；
- 最小字段与 artifact metadata 候选；
- 对 checkpoint 和目录设计的约束。

## Acceptance Criteria

- rerun、code fix、replan 均能明确归属；
- 能追踪父 execution 和触发原因；
- 核心文档对术语使用一致；
- 实现者无需自行选择两层或三层模型。

## Verification

```bash
git diff --check
```

## Stop Conditions

- 身份模型会改变 canonical output root 时停止；
- 需要引入数据库或外部服务时停止；
- checkpoint 与 artifact ownership 无法一致定义时停止。

## Required Documentation Updates

- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/ARCHITECTURE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`

## Completion Record

- Status：未执行
- Changed：未执行
- Verified：未执行
- Commit：未执行
- Follow-ups：未执行
