---
ticket_id: A04
phase: phase-a-control-contracts
status: draft
type: design
depends_on: [A01, A02, A03]
---

# 定义 Pause、Resume、Replay 与 Fork 语义

## Goal

确认 Human Gate、等待代码修改和可恢复错误如何在同一执行上下文中暂停和继续。

## Why

当前 runner 主要从新初始 state 调用图，部分 pending 状态写入 artifacts 后结束，尚未形成统一 durable execution 协议。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/STATE_SCHEMA.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- Phase A 前置 tickets

## Scope

- 区分 pause、terminal stop、resume、replay 和 fork；
- 定义恢复授权、恢复输入和 thread identity；
- 定义 interrupt 前副作用的幂等要求；
- 确认 CLI/UI 对外需要表达的最小语义。

## Non-goals

- 不实现 CLI 或 UI；
- 不更换 checkpoint backend；
- 不实现 Code Agent。

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

- resume 必须加载明确 thread/checkpoint；
- replay 和 resume 不能混为一谈；
- 重复恢复不能重复不可逆副作用；
- Human Gate 决定不能被 Agent 改写。

## 待确认问题

- `approve_rerun` 应 resume 同一 execution，还是创建派生 attempt/fork？
- 采用 LangGraph interrupt/resume，还是先用显式 CLI/API resume contract？
- process 已退出后写入 human decision file，下一次调用如何绑定唯一 checkpoint？
- checkpoint 与代码版本不兼容时应拒绝、replay 还是 fork？

## Deliverables

- durable execution 状态转换定义；
- start/resume/replay/fork 的最小外部合同；
- 幂等和授权规则。

## Acceptance Criteria

- 每类 pending/terminal 状态都有明确后续行为；
- Human Gate 可以安全恢复到允许路线；
- 重复请求和过期 checkpoint 有明确处理；
- Phase B 可据此编写恢复测试。

## Verification

```bash
git diff --check
```

## Stop Conditions

- 需要选择新的生产基础设施时停止；
- 无法保证 side-effect idempotency 时停止；
- resume 会隐式复用被保护的完成态 run directory 时停止。

## Required Documentation Updates

- `docs/ARCHITECTURE.md`
- `docs/STATE_SCHEMA.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`

## Completion Record

- Status：未执行
- Changed：未执行
- Verified：未执行
- Commit：未执行
- Follow-ups：未执行
