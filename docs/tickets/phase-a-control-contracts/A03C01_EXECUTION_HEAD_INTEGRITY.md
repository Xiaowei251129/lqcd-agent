---
ticket_id: A03C01
phase: phase-a-control-contracts
status: completed
type: corrective-implementation
depends_on: [A03]
---

# 绑定 A03 Registry 与 Execution Ledger 全局 Head

## Goal

修复A03 registry只验证“state所指identity自身合法”、却未验证其为execution ledger全局current head的问题，并冻结terminal/non-terminal Transition target语义。恢复或读取时，旧Attempt、旧Human Request/Response或伪造target-null Transition必须fail closed。

## Why

独立协调篡改实验确认三个缺口：state可从最新Attempt回退到旧Attempt；同一Human Request下state可从最新Response回退到旧Response；非terminal `memory_report` Transition可把target字段改为`None`并删除目标Attempt/artifact。三者属于同一根因：局部lifecycle校验没有与Run-local global head和Transition target shape绑定。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/tickets/README.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/STATE_SCHEMA.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md`
- `docs/tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md`
- `docs/tickets/corrections/A03_LEGACY_CORRECTIVE_HISTORY.md`
- `src/lqcd_agent/artifacts/registry.py`
- `src/lqcd_agent/graph/state.py`
- `tests/test_artifact_registry.py`

## Scope

- 验证Cycle、Attempt、Transition、Human Request和Human Response的Run-local index/identity唯一性与连续head；
- 要求bounded state的Cycle、Attempt、Transition、Human Request/Response counters和active identity等于ledger最新合法head；
- 保持每个Attempt与Human lifecycle既有顺序和跨记录identity验证；
- 要求target-null committed Transition只能使用terminal `end`/`__end__` route，且全部target字段为`None`；
- 要求非terminal Transition具有完整target tuple并继续与exact target Attempt lifecycle交叉校验；
- 收紧Human Response snapshot publication的唯一pending-response preflight，只允许确定性的next response identity/index；
- 增加协调回退、counter/identity篡改和正常恢复测试；
- 同步受影响source-of-truth与独立completion record。

## Non-goals

- 不修改原A03 ticket正文或legacy corrective history；
- 不实现A04 crash recovery、partial-commit repair、resume、replay或fork；
- 不引入签名、MAC、external immutable head或对任意全文件协调重写的密码学检测；
- 不改变artifact schema `0.1`、execution schema `0.2`或AnalysisState字段；
- 不改变graph topology、provider、Human approval、accepted-result或fallback product policy；
- 不自动迁移或修复旧/损坏registry。

## Allowed Files

- `docs/tickets/phase-a-control-contracts/A03C01_EXECUTION_HEAD_INTEGRITY.md`（执行开始后仅YAML lifecycle metadata）
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`
- `docs/tickets/completions/A03C01_COMPLETION.md`
- `docs/tickets/completions/README.md`
- `docs/tickets/corrections/README.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`
- `src/lqcd_agent/artifacts/registry.py`
- `tests/test_artifact_registry.py`

## Do Not Touch

- `docs/tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md`
- `docs/tickets/corrections/A03_LEGACY_CORRECTIVE_HISTORY.md`
- A01、A02、A04–A07 ticket正文；
- `src/lqcd_agent/graph/state.py`及其他runtime modules；
- `configs/`、`raw_data/`、`outputs/`、`accepted_results/`；
- evaluation scenarios、expected/reference outputs、dependencies、providers与external systems。

## Requirements

- 每类Run-local index必须为positive integer、identity格式正确、同一identity跨lifecycle稳定、不同identity不得复用index，已存在序列必须从1连续到max；
- state `cycle_id/cycle_index/parent_cycle_id`必须等于latest Cycle creation；
- state `attempt_id/attempt_index/parent_attempt_id/attempt_kind/attempt_node/attempt_trigger/attempt_status/inbound_transition_id`必须等于max Attempt index对应lifecycle的provenance与latest status；
- state `transition_index/committed_transition_id/committed_route`必须等于max committed Transition index；
- target-null Transition必须满足route为`end`或`__end__`，且`target_node/target_cycle_id/target_attempt_kind`也全部为`None`；否则target tuple全部非空并exact匹配目标Attempt；
- state Human Request fields/counter必须等于max request index的latest lifecycle；无request时必须保持zero/null head；
- state `human_response_index`必须等于Run global max response index；active response必须是latest Human Request下max response index对应lifecycle，或在该request没有response时为`None`；
- snapshot preflight只允许`human_response_index == ledger_max + 1`、deterministic next ID、`submitted`初始state及空decision/validator/consumer fields；恢复、读取和save不得使用该例外；
- 三项已复现实验必须由永久测试拒绝，未篡改Run必须正常恢复。

## Deliverables

- bounded execution-head validator；
- Transition target shape validator；
- deterministic pending Human Response preflight；
- focused negative/positive regression tests；
- source-of-truth更新和独立completion record。

## Acceptance Criteria

- stale Attempt state即使指向合法旧lifecycle也被拒绝；
- stale Human Response state即使匹配合法旧response latest record也被拒绝；
- 非terminal target被置空并协调删除target Attempt/artifact后被拒绝；
- Cycle、Attempt、Transition、Human Request/Response counter或identity reuse/gap被拒绝；
- initial invalid-response retry、normal terminal Run、fallback harness和registry restore继续通过；
- full deterministic suite、synthetic benchmark tests、compileall、Markdown links和`git diff --check`通过；
- 原A03 ticket和legacy corrective history没有变化。

## Verification

```bash
pytest -q tests/test_artifact_registry.py tests/test_execution_identity.py tests/test_state_schema.py
pytest -q
pytest -q tests/test_synthetic_benchmarks.py
python -m compileall -q src tests evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py
git diff --check
```

- 重跑三项独立协调篡改实验；
- 使用新的`/private/tmp/lqcd-agent-a03c01-*` deterministic CLI smoke；
- 检查tracked与本轮新增Markdown relative links；
- 相对ticket开始状态审计Allowed Files与Do Not Touch。

## Stop Conditions

- 修复需要改变state或ledger schema时停止；
- 修复需要修改`graph/state.py`或其他Do Not Touch runtime时停止；
- 发现需要A04 recovery或cryptographic integrity才能解决的问题时停止；
- 需要改变原A03 public artifact contract或扩大Allowed Files时停止；
- 正常write path无法在限定pending preflight内通过时停止。

## Required Documentation Updates

- `docs/ARTIFACT_CONTRACTS.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`
- `docs/tickets/completions/A03C01_COMPLETION.md`
