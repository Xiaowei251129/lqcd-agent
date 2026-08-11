---
ticket_id: A03
phase: phase-a-control-contracts
status: draft
type: design
depends_on: [A01, A02]
---

# 定义 Artifact Namespace 与 Invalidation

## Goal

确认不同回退路线产生的新 artifacts 如何命名、继承和失效，同时永久保留历史 provenance。

## Why

当前固定 artifact paths 适合单轮 demo，但多轮执行可能覆盖旧结果或让下游误读已经失效的 artifacts。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md`
- `docs/tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md`

## Scope

- 定义 plan、code、analysis、review、decision 的依赖层次；
- 定义回到不同节点时的失效范围；
- 讨论 current pointer、历史目录和 manifest 表达；
- 保护 human decisions、accepted results 和 raw data。

## Non-goals

- 不实施目录迁移；
- 不删除历史 outputs；
- 不定义 RAG evidence bundle。

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

- invalidation 只能改变“当前有效性”，不能删除历史；
- 不同回退目标必须有确定性的下游失效范围；
- human decisions 和 accepted results 保持 append-only 或 versioned；
- current artifact 选择不能依赖自由文本。

## 待确认问题

- 每个 attempt 使用独立目录，还是在现有 run directory 内使用 versioned filenames？
- current artifact 由 state pointer、manifest relation 还是单独 index 表达？
- replan、code fix、analysis rerun 和 reviewer retry 分别使哪些下游 artifacts 失效？
- 已被 human decision 引用的 artifact 失效后如何保留引用一致性？

## Deliverables

- artifact dependency/invalidation matrix；
- namespace 和 current-result 表达决定；
- 后续迁移与测试约束。

## Acceptance Criteria

- 四类主要回退都有明确失效范围；
- 旧 artifact 不会被误认为当前结果；
- 历史仍可审计和复现；
- 实现者无需自行决定覆盖策略。

## Verification

```bash
git diff --check
```

## Stop Conditions

- 需要删除或改写历史 artifacts 时停止；
- 需要放宽 raw-data 或 accepted-result policy 时停止；
- namespace 选择会破坏 v0.2 read compatibility 时停止。

## Required Documentation Updates

- `docs/ARTIFACT_CONTRACTS.md`
- `docs/STATE_SCHEMA.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`

## Completion Record

- Status：未执行
- Changed：未执行
- Verified：未执行
- Commit：未执行
- Follow-ups：未执行
