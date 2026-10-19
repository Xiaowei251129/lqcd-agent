---
ticket_id: B00C29
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C04]
---

# Pytest runner 单次时限调整为 450 秒

## Goal

按用户 2026-10-19 明确指令“把300 秒限制改成450秒”，将统一 pytest evidence runner 的单次子进程时限由 300 秒调整为 450 秒。该授权仅覆盖此时限和对应文档，不执行 B05。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`
- `tests/phase_b/harness/pytest_evidence.py`
- `docs/tickets/corrections/TEST_INFRASTRUCTURE_MAINTENANCE.md`

## Scope and Requirements

1. 只修改现有 `run_pytest` 的 `subprocess.run(timeout=300)` 为 `timeout=450`。收集及批处理调用继续共用该路径，不新增配置项、兼容分支或 wrapper。
2. 现有 selection、双 fresh、assertions、Session 绑定、envelope/observation validators、失败传播及批次合并规则保持。业务预算、Agent/Code/Analysis deadline 和其他 child 时限保持。
3. 此政策明确取代历史纠偏票及记录中关于该 runner 必须维持 300 秒的限制；历史正文和旧结果保持原样，当前 B05 review 草案与验证指南使用 450 秒。
4. 运行现有 evidence/final 和 process-hook 测试，并通过实际 `run_pytest_batches(batch_size=1)` 运行 C21 `triple_success`，以原 validators 检查真实 envelope、来源和 observation。保存冻结输入及实际结果，不把旧 422.545 秒结果重标为新 runner 的通过证据。

## Allowed Files

- `tests/phase_b/harness/pytest_evidence.py`：仅上述时限字面量。
- 本票进入 ready 后仅 YAML lifecycle；新 `docs/tickets/completions/B00C29_COMPLETION.md`。
- `README.md`、`docs/README.md`、`docs/REPO_CURRENT_STATE.md`、`docs/VERIFICATION_GUIDE.md`、`docs/DECISION_LOG.md`。
- `docs/tickets/corrections/TEST_INFRASTRUCTURE_MAINTENANCE.md`、Phase B `OVERVIEW.md` 和仍为 review 的 B05 票据：仅本政策及当前结果同步。

## Do Not Touch

全部 `src/`、业务合同/预算/deadline、依赖/配置、existing tests、helpers、expected、matrix/registry/owners、历史票据正文和完成记录。B05 保持 review 且未实施；不 commit/push。

## Acceptance Criteria and Verification

- runner diff 精确为 `timeout=300` → `timeout=450`，所有原验证规则保持。
- `tests/phase_b/test_evidence_and_final.py` 和 `tests/phase_b/test_process_hook_evidence.py` 通过，包括原失败/skip/xfail/证据篡改拒绝及完整批次检查。
- C21 原双 fresh 节点通过真实 450 秒 runner，原 `validate_pytest`、`validate_observations` 和 Session unchanged 检查通过。
- 当前政策文档一致；compile、链接、scope 和 `git diff --check` 通过。全仓完整回归仍为 B05 前置，不以本票局部结果代替。

## Stop Conditions

450 秒仍超时、出现原断言失败或需要修改上述时限之外的实现时，保留失败并报告，不继续提高时限或扩大范围。

## Deliverables

单行 runner 修改、独立完成记录、真实定向结果与输入快照、更新后的当前政策文档。完成结果不追加到本票正文。
