---
ticket_id: TEMPLATE
phase: phase-name
status: draft
type: design
depends_on: []
---

# Ticket 标题

## Goal

用一个可验证的结果描述本 ticket 最终要完成什么。

## Why

说明为什么现在需要完成这个任务，以及它解决什么问题。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/VERIFICATION_GUIDE.md`
- 列出完成本 ticket 必须阅读的核心文档、代码和前置 ticket。

## Scope

- 列出本 ticket 包含的工作。

## Non-goals

- 明确本 ticket 不处理的相邻问题。

## Allowed Files

- 列出允许修改的文件或最小目录。

## Do Not Touch

- 列出禁止修改的文件、目录、数据和外部系统。

## Requirements

- 列出必须满足的行为、合同和约束。

## Deliverables

- 列出完成后应存在的代码、文档或 artifacts。

## Acceptance Criteria

- 使用可观察、可判断的完成条件。

## Verification

```bash
# 列出验证命令；纯设计任务可以使用文档和链接检查。
```

## Stop Conditions

- 缺少必要上下文或需要未经批准的设计决定时停止；
- 需要扩大 Allowed Files 或触碰 Do Not Touch 时停止；
- 需要改变未被本 ticket 批准的 public contract 时停止；
- 需要新增未被本 ticket 批准的 dependency 时停止；
- 无法运行必要验证时停止。

## Required Documentation Updates

- `docs/REPO_CURRENT_STATE.md`
- 根据实际变化列出其他核心文档；
- 架构或政策变化时追加 `docs/DECISION_LOG.md`。
- 完成 stale-documentation scan，并检查本 ticket 涉及的 TODO。

## Completion Record

- Status：未执行
- Changed：未执行
- Verified：未执行
- Commit：未执行
- Follow-ups：未执行
