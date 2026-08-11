# Verification Guide

## 使用原则

验证应与改动风险相匹配。普通文档迁移不运行 live provider；runtime、graph 或 schema 改动必须运行完整 deterministic suite，并按 ticket 增加针对性检查。

当前执行入口是 [Docs Index](README.md) 与 [Tickets](tickets/README.md)。第一阶段原始计划和 prompt 历史只从 milestone tag 查看，不存在当前执行权威。

## 快速检查

对所有修改至少运行：

```bash
git diff --check
pytest -q
```

只做文档迁移时，还应检查：

- Markdown relative links 全部指向现有文件；
- `git diff --name-status` 没有意外的 `D` 或 `R`；
- 没有修改 `src/`、`tests/`、configs 或 runtime schema；
- milestone tag 仍 peel 到锁定 commit；
- ticket metadata 与目录结构符合治理规则。

## 第二阶段文档完整性

当前 source-of-truth 文件：

```bash
test -f docs/README.md
test -f docs/PROJECT_SPEC.md
test -f docs/ARCHITECTURE.md
test -f docs/AGENT_ROLES_AND_BOUNDARIES.md
test -f docs/STATE_SCHEMA.md
test -f docs/ARTIFACT_CONTRACTS.md
test -f docs/SECURITY_AND_DATA_POLICY.md
test -f docs/EVALS_AND_OBSERVABILITY.md
test -f docs/VERIFICATION_GUIDE.md
test -f docs/REPO_CURRENT_STATE.md
test -f docs/DECISION_LOG.md
test -f docs/milestones/V0_2_DEMO_BASELINE.md
test -f docs/tickets/README.md
test -f docs/tickets/TEMPLATE.md
```

阶段骨架必须包含：

- `phase-a-control-contracts/`：Overview 和 A01–A07；
- `phase-b-graph-harness/`：本轮只有 Overview；
- `phase-c-code-agent/`：本轮只有 Overview；
- `phase-d-agent-capabilities/`：本轮只有 Overview；
- `phase-e-integrated-benchmark/`：本轮只有 Overview。

## Deterministic Runtime 验证

完整本地 suite：

```bash
pytest -q
```

常用针对性检查：

```bash
pytest tests/test_graph_smoke.py tests/test_routing.py tests/test_state_schema.py -q
pytest tests/test_analysis_engineer.py tests/test_command_runner.py tests/test_manifest.py -q
pytest tests/test_scientific_reviewer.py tests/test_decision_coordinator.py -q
pytest tests/test_approval_packet.py tests/test_memory.py tests/test_report.py -q
pytest tests/test_llm_config.py tests/test_llm_mock_provider.py -q
```

provider dry-run 不发出 live call，也不得打印 secret：

```bash
python -m lqcd_agent.llm.provider_factory --config configs/runtime/openai.yaml --dry-run
python -m lqcd_agent.llm.provider_factory --config configs/runtime/deepseek.yaml --dry-run
```

## Graph 与 Demo 检查

deterministic smoke：

```bash
python -m lqcd_agent.graph.run_graph \
  --case configs/cases/mock_lqcd_goal.yaml \
  --output-dir /private/tmp/lqcd-agent-smoke
```

Golden Demo：

```bash
bash scripts/run_langgraph_demo.sh
```

Golden Demo 必须保持 synthetic、read-only provenance、高风险进入 Human Gate、未批准时 `accepted_result: false`。普通开发验证应优先写入 `/private/tmp`；不要把 repo-local `outputs/` 当成 reference evidence。

## Synthetic Evaluation 与 Benchmark

```bash
python evaluation/run_evaluation.py
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py \
  --provider mock \
  --case-set full \
  --output-dir /private/tmp/lqcd-agent-phase10c-mock
```

两者默认都必须 network-free。runner 若需要清理已存在的 synthetic run，只有明确知道目标是临时评估目录时才使用 `--force-clean`。

## 可选 Live Checks

live provider tests/demo 默认不运行，也不属于普通 ticket 的完成条件。只有 ticket 明确要求、用户同意且本地 secrets 已安全配置时，才使用：

```bash
RUN_LIVE_LLM_TESTS=1 pytest -q
```

或对应 benchmark/graph 命令。不得把 key 写入 command、artifact 或文档。

## Ticket 完成检查

执行一个 `status: ready` ticket 时，完成前必须逐项核对：

1. 只修改 `Allowed Files`，没有触碰 `Do Not Touch`；
2. 满足 Acceptance Criteria 和 Verification；
3. 没有触发 Stop Conditions；
4. 相应核心文档已同步；
5. `REPO_CURRENT_STATE.md` 已更新；
6. 架构或政策变化已追加 `DECISION_LOG.md`；
7. Completion Record 只追加事实，不重写原始目标；
8. ticket status 的变更经过用户要求或确认。

若 implementation 与文档不一致，应更新 source-of-truth 或停止并报告冲突，不能只在 completed ticket 中留下新合同。

## 第二阶段 Docs 治理验收

第二阶段文档迁移还必须满足：

- 不删除或移动现有文件；
- 第一阶段 Legacy 文件已从当前工作树删除，必要规则已迁入 `AGENTS.md`、Ticket Workflow、Template、安全策略和 Verification Guide；
- 初次文档迁移验收时 Phase A 七个 ticket 均为 `draft`；后续状态必须与各 ticket front matter、Phase Overview 和 `REPO_CURRENT_STATE.md` 一致；
- Phase B–E 没有提前创建执行 ticket；
- `v0.2-demo^{commit}` 仍为 `e73e4d3b967008f290259851caf05f28e087cd5b`；
- 当前 Markdown links 不再依赖已删除文件；历史原文仍可从 `v0.2-demo` 查看；
- 本地 Markdown link check、`git diff --check` 与 `pytest -q` 全部通过。

## 相关文档

- [Repository Current State](REPO_CURRENT_STATE.md)
- [Milestone Baseline](milestones/V0_2_DEMO_BASELINE.md)
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
