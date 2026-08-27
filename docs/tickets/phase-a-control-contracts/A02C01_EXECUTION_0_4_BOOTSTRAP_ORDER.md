---
ticket_id: A02C01
phase: phase-a-control-contracts
status: review
type: corrective-implementation
depends_on: [A02, A03, A03C01]
---

# 修正 Execution 0.4 Run Bootstrap 顺序

## Goal

为 execution schema `0.4+` 冻结预算可审计、可幂等恢复且在 Planner 副作用前完成的 Run bootstrap 顺序，解决 A02 schema `0.2` 固定四记录初始化与 A06 `policy_initialized`、`decision_recorded` admission 合同之间的冲突。

本 ticket 只冻结后继 schema 的 corrective design 和下游实现约束；不修改 A02 已完成正文、当前 schema `0.2` runtime、graph、tests 或历史 Run。

## Why

A02 §5 将新 Run 的前四条权威记录固定为 Run、initial Cycle、Planner Attempt 和 START Transition。A06 schema `0.4` 又要求 budget policy 与 admission evidence 在可能创建 Cycle、Attempt 或 Transition 的动作前持久化。由于正式 Run ledger 在 Run creation 前尚不存在，这两个顺序不能同时通过文字解释成立。

Schema `0.4+` 必须显式扩展 bootstrap，而不是让初始 Cycle/Attempt/Transition 成为不受 budget contract 约束的隐藏例外，也不能追溯改写 schema `0.2` 历史。

## Read First

- [`AGENTS.md`](../../../AGENTS.md)
- [`docs/README.md`](../../README.md)
- [`docs/tickets/README.md`](../README.md)
- [`docs/STATE_SCHEMA.md`](../../STATE_SCHEMA.md)
- [`docs/ARTIFACT_CONTRACTS.md`](../../ARTIFACT_CONTRACTS.md)
- [`docs/VERIFICATION_GUIDE.md`](../../VERIFICATION_GUIDE.md)
- [`docs/REPO_CURRENT_STATE.md`](../../REPO_CURRENT_STATE.md)
- [`A02_RUN_CYCLE_ATTEMPT_MODEL.md`](A02_RUN_CYCLE_ATTEMPT_MODEL.md)
- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)
- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)
- [`A06_BUDGETS_AND_STOP_CONDITIONS.md`](A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [`A02 Human Gate Commit-order Clarification`](../corrections/A02_HUMAN_GATE_COMMIT_ORDER_CLARIFICATION.md)
- [`A03 Transition Publication-order Clarification`](../corrections/A03_TRANSITION_PUBLICATION_ORDER_CLARIFICATION.md)

## Scope

- 冻结 schema `0.4+` 的 bootstrap policy、identity、ledger、invalidation、checkpoint 和 side-effect 顺序；
- 冻结 `start_run` bootstrap 的幂等 identity、合法 incomplete prefix 和 fail-closed crash 行为；
- 明确本 ticket 对 A02 §5 的版本限定 supersession；
- 向 A04、A06、A07 与 Phase B implementation tickets提供一个唯一 bootstrap contract；
- 执行时只同步治理与目标合同文档，不实现 runtime。

## Non-goals

- 不修改 A02、A03、A03C01 completed ticket正文或其完成记录；
- 不改变 schema `0.2` Run bytes、兼容读取、identity、counter或历史 provenance；
- 不实现 BudgetPolicy、ledger builder、checkpoint backend、`start_run`、graph或tests；
- 不批准对已开始 Agent/provider/tool副作用的自动重试或partial-commit repair；
- 不迁移、恢复或补写现有 incomplete Run；
- 不选择生产事务系统、认证、distributed lock、provider或dependency。

## Allowed Files

本 ticket 提升为 `ready` 并执行时，只允许修改：

- `docs/tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md`：仅允许更新YAML lifecycle metadata；
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`；
- `docs/tickets/completions/A02C01_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

- A01–A03、A03C01及其completion/correction history；
- A04–A07 ticket正文；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`和accepted artifacts；
- 当前 runtime schema、graph topology、checkpoint backend、provider、dependency、认证或secrets；
- milestone、tag或历史Run。

## Versioned Supersession Boundary

- A02 §5继续是execution schema `0.2`的历史权威顺序；本ticket不改写或重新解释其四条记录。
- Execution schema `0.3`若不包含A06 budget records，继续沿用A02顺序并受A04自己的start/replay/fork边界约束。
- Execution schema `0.4+`只对bootstrap顺序采用本ticket；A02其余Run/Cycle/Attempt/Transition identity、counter和target-consumption合同继续有效。
- 未知schema、混合顺序或缺少本ticket任一required bootstrap identity/record的Run不得声明为schema `0.4` completed bootstrap。

## Execution 0.4 Bootstrap Contract

可信Host在正式ledger外先验证`StartRunRequest`、Actor scope、output-root create-new条件和allowlisted canonical BudgetPolicy bytes。失败时不得创建Run root或任何execution identity。

验证成功后的权威顺序固定为：

```text
create immutable BudgetPolicy bytes and canonical digest
-> append Run created
   bind start_operation_id, idempotency-key digest and policy reference/digest
-> append budget policy_initialized
   bind exact Run-creation record and policy bytes
-> append budget decision_recorded(allow, action = bootstrap_initial_route)
   cover one initial Cycle, one Planner Work Attempt and one START Transition
   prove all absolute ceilings and the full terminal reserve remain valid
-> append initial Cycle created
-> append Planner Attempt scheduled
-> apply A03 method_planner target invalidation
   require an empty/new-Run current set and record only canonical no-op/clear evidence
-> append START -> method_planner Transition committed
-> persist and validate bounded state/checkpoint plus execution/artifact heads
-> return the Run and permit Planner side effects
```

`policy_initialized`和bootstrap `decision_recorded`不是普通automatic-route charge。Cycle、Attempt和Transition的实际用量仍从A02权威identity records重放派生，不能在budget record中复制可漂移counter。

Bootstrap使用A02/A03复合Transition publication顺序：先分配scheduled target Attempt，再完成target invalidation，最后append committed Transition。`app.invoke()`、Planner wrapper `started`、Agent/provider/tool调用或任何domain artifact写入只能发生在完整bootstrap验证之后。

## Idempotency and Incomplete Prefix

- `start_operation_id`由可信Host分配并与`idempotency_key`、canonical request digest、Run identity和policy digest绑定；调用方不能选择现有Run root。
- 同key同digest在完整bootstrap后返回同一结果，不创建第二个Run、Cycle、Attempt、Transition、policy或decision。
- 在任何Planner/Agent/provider/tool/domain-artifact副作用前，进程崩溃后只允许同key同digest继续一个严格合法的bootstrap前缀。
- 合法前缀必须从`Run created`开始，按本ticket顺序连续、identity/digest/head exact-match，且不得包含未知record、重复identity、target `started`、domain artifact、external reservation或已公开Pause。
- 继续合法前缀只能append缺失的确定性后缀和持久化缺失checkpoint；不能重写、删除、重新编号或替换已存在record。
- 任一额外record、顺序缺口、digest/head mismatch、side-effect evidence、并发不同请求或无法证明前缀完整时返回`recovery_required`，不得自动repair、replay或改用新identity继续原Run。
- 完整bootstrap前Run不得以`running`或其他可执行状态对外发布；查询只能返回typed initializing/recovery control outcome，不得暴露raw checkpoint恢复入口。

## Required A07 Scenario

- `A02C01-BOOTSTRAP-001`：验证schema `0.4`完整顺序、每个durable边界的合法前缀继续、冲突前缀fail closed、Planner副作用只能在bootstrap head/checkpoint exact-match后开始，以及schema `0.2`历史顺序保持不变。

## Deliverables

- 本ticket冻结的schema `0.4+` bootstrap corrective contract；
- A04/A06/A07一致引用的版本边界和required scenario；
- 独立completion record及受到影响的状态/决策文档更新。

## Acceptance Criteria

- schema `0.4+`在创建initial Cycle/Attempt/Transition前具有持久policy和admission evidence；
- A02 schema `0.2`正文、runtime和历史Run均未修改；
- START Transition遵守scheduled target allocation → A03 invalidation → Transition append顺序；
- Planner side effect只可能发生在完整bootstrap、checkpoint和heads验证后；
- 同key合法prefix continuation与任意冲突/副作用prefix的fail-closed边界可机器验证；
- A04、A06、A07不再定义互相冲突的bootstrap顺序。

## Pre-freeze Review Gate

- YAML保持`status: review`，直到本ticket、A04–A07和requirement catalog完成交叉核验并获得用户最终确认；
- A02/A03/A03C01正文与runtime diff均为零，两个commit-order clarification已进入correction index；
- A04、A06、A07依赖本ticket并使用同一schema `0.4`顺序、prefix continuation和fail-closed边界；
- `PHASE_B_REQUIREMENT_CATALOG.json`恰好包含`A02C01-BOOTSTRAP-001`；
- Phase Overview、Docs Index和Current State一致记录本ticket为`review`且不把target contract描述为当前runtime；
- ticket内没有未决设计问题、占位符或内嵌执行记录。

## Verification

```bash
git diff --check
```

还必须验证全部relative Markdown links、ticket metadata、A02/A03/A03C01正文hash未变化，且本ticket没有runtime/tests/configs diff。

## Stop Conditions

- 需要修改A02/A03/A03C01冻结正文或当前runtime才能确认本设计；
- 无法在Planner副作用前持久化policy、admission、identity、invalidation和checkpoint证据；
- 合法prefix continuation必须重放Agent/provider/tool副作用；
- 需要扩大Allowed Files、选择生产基础设施或引入dependency；
- A04/A06/A07要求另一套不兼容bootstrap identity、顺序或recovery policy。

## Required Documentation Updates

- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`；
- `docs/README.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`；
- `docs/tickets/completions/A02C01_COMPLETION.md`及completion index；
- stale-documentation和relative-link scan。
