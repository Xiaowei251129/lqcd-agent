---
ticket_id: A06
phase: phase-a-control-contracts
status: draft
type: design
depends_on: [A01, A02, A04, A05]
---

# 定义预算与停止条件

## Goal

确认 graph cycle、replan、analysis rerun、code attempt、LLM 调用和重复失败的有限预算与升级规则。

## Why

循环必须能够证明会停止；预算同时控制成本、重复副作用和没有新证据的无效科研循环。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- Phase A 前置 tickets

## Scope

- 盘点需要预算的循环和资源；
- 定义预算 ownership、耗尽状态和 Human Gate 升级；
- 讨论 failure fingerprint 和连续相同失败；
- 区分 retryable technical failure 与 non-retryable scientific/data failure。

## Non-goals

- 不填写未经验证的具体数值；
- 不实现 timeout 或 recursion config；
- 不设计计费系统。

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

- 所有允许循环都有有限停止条件；
- 相同失败在没有新证据时不能无限重试；
- budget exhaustion 必须进入明确 terminal 或 Human Gate 路线；
- 安全边界不能因预算不足而被跳过。

## 待确认问题

- budget 由整个 Run、Cycle、具体 route 还是多个层级共同拥有？
- retry/cycle/LLM/tool/time/cost 哪些预算必须进入第一版合同？
- 什么证据足以判断“同一失败重复出现”？
- 默认数值应现在冻结，还是先通过 Phase B 数据再确定？

## Deliverables

- budget categories 与 ownership；
- exhaustion/duplicate-failure 路由规则；
- 后续 state、config 和 harness 约束。

## Acceptance Criteria

- 每类循环都能回答何时停止；
- 技术重试与科学重新分析被区分；
- 预算状态可审计；
- Phase B 可以构造预算耗尽测试。

## Verification

```bash
git diff --check
```

## Stop Conditions

- 缺少成本或运行数据却必须冻结具体默认值时停止；
- budget 设计需要改变 provider billing 或外部基础设施时停止；
- 停止策略可能绕过 Human Gate 时停止。

## Required Documentation Updates

- `docs/ARCHITECTURE.md`
- `docs/STATE_SCHEMA.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/EVALS_AND_OBSERVABILITY.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`

## Completion Record

- Status：未执行
- Changed：未执行
- Verified：未执行
- Commit：未执行
- Follow-ups：未执行
