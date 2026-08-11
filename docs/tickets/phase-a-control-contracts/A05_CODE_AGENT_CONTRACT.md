---
ticket_id: A05
phase: phase-a-control-contracts
status: draft
type: design
depends_on: [A01, A02, A03]
---

# 定义 Graph-managed Code Agent Contract

## Goal

定义 Fake 和真实 Code Agent 共同遵守的最小结构化输入输出、安全边界和失败分类。

## Why

图必须先有稳定“插座”才能独立验证路由，真实 Code Agent 也必须在隔离环境中可替换接入。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/AGENT_ROLES_AND_BOUNDARIES.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- Phase A 前置 tickets

## Scope

- 定义 task、base revision、scope、budget 和 verification 输入；
- 定义 success、failed、no-change、needs-human 等结果类别；
- 定义 patch/diff、changed files、tests 和 failure evidence；
- 定义隔离 workspace 与主图之间的边界；
- 定义 Fake implementation 需要模拟的结果。

## Non-goals

- 不选择 Codex SDK、CLI adapter 或具体 sandbox provider；
- 不实现 Code Agent；
- 不批准 push、merge 或 production deployment。

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

- Fake 和真实实现使用同一结果合同；
- Code Agent 不能修改 raw data、accepted results、secrets 或 Human Gate；
- 每个 attempt 必须可识别、可预算、可审计；
- 真实修改应发生在独立 worktree/container/sandbox；
- 测试通过不能自动等价于科学接受。

## 待确认问题

- Code Agent 应表现为单一 graph node、可暂停 subgraph，还是受控 external adapter？
- 主图接收 patch/diff artifact，还是接收隔离 workspace revision？
- 哪些修改可以自动应用，哪些必须经过 human approval？
- Fake Code Agent 最少需要模拟哪些 failure 与 partial-success 类型？

## Deliverables

- Code Agent input/output contract；
- failure taxonomy 与 retryability 规则；
- isolation 和 approval invariants；
- Fake Code Agent 场景集合。

## Acceptance Criteria

- 主图 routing 不需要了解 Code Agent 内部工具循环；
- Fake 和真实实现可以互换；
- 成功、失败、预算耗尽和人工介入都有明确结果；
- 合同不会自行扩大代码写权限。

## Verification

```bash
git diff --check
```

## Stop Conditions

- 需要决定具体 provider 或新增依赖时停止；
- 需要允许直接修改主运行目录时停止；
- 需要改变科学审批边界时停止。

## Required Documentation Updates

- `docs/AGENT_ROLES_AND_BOUNDARIES.md`
- `docs/ARCHITECTURE.md`
- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`

## Completion Record

- Status：未执行
- Changed：未执行
- Verified：未执行
- Commit：未执行
- Follow-ups：未执行
