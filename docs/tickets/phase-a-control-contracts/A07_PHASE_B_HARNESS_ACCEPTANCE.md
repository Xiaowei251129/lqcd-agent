---
ticket_id: A07
phase: phase-a-control-contracts
status: draft
type: design
depends_on: [A01, A02, A03, A04, A05, A06]
---

# 冻结 Phase B Harness 验收合同

## Goal

把 Phase A 已确认的控制合同转化为 Phase B 可以直接实施的测试层次、场景清单和完成标准。

## Why

Phase B 的实现者不应自行判断哪些边、循环、恢复和失败场景算“已经打通”。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/EVALS_AND_OBSERVABILITY.md`
- `docs/VERIFICATION_GUIDE.md`
- Phase A A01–A06

## Scope

- 定义 schema/invariant、node、route、partial path、trajectory、cycle、failure injection、resume 和未来 parallel tests；
- 区分 strict deterministic assertions 与允许多条合理路径的评估；
- 定义 Fake Code Agent 覆盖；
- 定义 Phase B 完成和未覆盖路线报告。

## Non-goals

- 不实现测试；
- 不引入 LangSmith、Harbor 或 AgentEvals；
- 不运行 live-provider benchmark。

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

- 每条允许路线至少映射到一个测试场景；
- 必须覆盖成功循环、失败循环、预算耗尽和 Human Gate；
- deterministic control tests 不依赖 live LLM；
- capability benchmark 与 control-plane correctness 分开；
- uncovered edge 必须可见，不能默认为通过。

## 待确认问题

- Phase B 必须覆盖所有 declared edges，还是只覆盖 A01 批准的 product routes？
- trajectory 应逐步完全相等，还是允许多个符合合同的 path class？
- pause/resume、budget exhaustion 和 repeated-failure 各需要哪些最小场景？
- parallel reducer 尚未实现时，Phase B 应只冻结未来 acceptance，还是实现最小并行测试支架？

## Deliverables

- Phase B acceptance matrix；
- required scenario inventory；
- test-layer ownership；
- Phase B implementation ticket 拆分输入。

## Acceptance Criteria

- A01–A06 的每项合同都有验证映射；
- Fake Agent 足以验证控制层；
- live-provider eval 被明确留在独立层；
- Phase B 的结束标准无需实现者补充设计决定。

## Verification

```bash
git diff --check
```

## Stop Conditions

- A01–A06 仍有影响测试设计的 unresolved 决定时停止；
- 必须先选择第三方 eval 平台才能定义 acceptance 时停止；
- 测试要求会读取未批准 raw data 时停止。

## Required Documentation Updates

- `docs/EVALS_AND_OBSERVABILITY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`

## Completion Record

- Status：未执行
- Changed：未执行
- Verified：未执行
- Commit：未执行
- Follow-ups：未执行
