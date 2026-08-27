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

- `phase-a-control-contracts/`：Overview、A01–A07、A02C01、tracked Control Protocol和requirement catalog；
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

### Phase A Control Protocol Pre-freeze 验证

A02C01与A04–A07从`review`提升为`ready`前必须运行tracked design validator：

```bash
python scripts/validate_phase_a_control_protocol.py
```

该检查strict读取[`CONTROL_PROTOCOL_0_4.json`](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)和[`PHASE_B_REQUIREMENT_CATALOG.json`](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)，验证ControlOperation type/variant/phase/edge穷尽与终结、ExternalOperation final-proof union、Pause lifecycle visibility/finality、Run lifecycle唯一声明循环、atomic combined ownership、pre-start dependency DAG、field allocation/binding顺序、ticket/catalog stable IDs、required文档引用以及protocol exact-byte SHA绑定。它是design-time lint，不表示Phase B runtime、fault fixture或acceptance matrix已经实现；B00仍须把同一合同转为collectable tests和normalized traces。

### A02 Execution Identity 验收

A02 的 targeted suite 必须同时覆盖 primitive、真实 compiled graph、demo Human continuation、legacy handoff compatibility 和最小 fallback identity harness：

```bash
pytest -q \
  tests/test_execution_identity.py \
  tests/test_state_schema.py \
  tests/test_routing.py \
  tests/test_graph_smoke.py \
  tests/test_approval_packet.py \
  tests/test_demo_server.py \
  tests/test_memory.py \
  tests/test_report.py \
  tests/test_run_graph_with_codex_handoff.py

python -m compileall -q src/lqcd_agent
```

验收不能只看 pass count，还必须检查：

- 每个新 Run 的 ledger 前四条 records 是 formal Run、initial Cycle、scheduled Planner Attempt、committed START Transition；
- current fixed/conditional/END routes 都通过 Transition commit，且 target wrapper 消费同一个预分配 Attempt；
- physical `codex_handoff` 的 canonical kind 始终是 `legacy_codex_handoff`，没有被伪装成 `code_agent`；
- Human Request/Response 有独立 IDs，validator/consumer/authorized-target lineage 可追踪，重复提交不会增加 Attempt counter 或重写 memory/report；
- re-review、analysis rerun、code fix 和 replan 只作为最小 StateGraph identity harness 证据，不被统计为 current product edge coverage；
- incomplete-Run re-entry 只证明 immutable identity/counter continuity，不被描述成 A04 durable resume。

A02 的完成证据已记录为 targeted suite `125 passed`、full suite `218 passed`，并包含 compileall、scope、29-file Markdown links、stale-doc scan、ticket metadata 和 `git diff --check`。后续修改该合同仍需重复本节检查，不能只沿用历史 pass count。

### A03 Artifact Namespace / Invalidation 验收

A03 targeted verification：

```bash
pytest -q tests/test_artifact_registry.py tests/test_execution_identity.py tests/test_state_schema.py
pytest -q tests/test_graph_smoke.py tests/test_run_graph_with_codex_handoff.py
pytest -q tests/test_method_planner_mock.py tests/test_analysis_engineer.py \
  tests/test_scientific_reviewer.py tests/test_decision_coordinator.py
pytest -q tests/test_approval_packet.py tests/test_codex_handoff_worker.py \
  tests/test_demo_server.py tests/test_memory.py tests/test_report.py
pytest -q
python -m compileall -q src tests evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py
```

除 pass count 外还必须检查：

- canonical member位于 `attempts/<attempt_id>/`，第二个同类 Attempt不改变第一个的 bytes/digest；
- history/index/state heads一致，current selection不使用目录扫描或 mtime；
- `registered` event冻结完整typed pointer和`node_name`，并将Run、Case、Cycle、Attempt、Kind、Node六个identity字段与execution ledger exact-equal；字段缺失、变化或不一致必须fail closed；
- history重放结果与index current exact-equal；普通registration必须紧邻唯一一次current-set，已clear artifact不得重新set；篡改pointer identity、status、members、state paths、跨slot引用或set/clear顺序必须fail closed；
- 每个current-clear必须同时匹配当时current artifact、target Attempt完整provenance、其inbound committed Transition和固定slot policy；transition/target/triggering Attempt/Cycle/reason任一不一致必须fail closed；
- 每个带target Attempt的committed Transition必须反向对应exactly one合法Attempt lifecycle；删除整个target lifecycle后即使同时删除其artifact并协调index/state paths仍必须fail closed；bounded state的current Attempt必须与ledger最新lifecycle exact-equal；
- Cycle、Attempt、Transition、Human Request和Human Response的Run-local deterministic ID/index必须唯一并从1连续到max；bounded state必须指向各类全局latest head，不能回滚到自身仍合法的旧Attempt、旧request或旧response；
- target-null committed Transition只允许terminal `end`/`__end__` route且全部target fields显式存在并为`None`；字段缺失不得当作null；非terminal Transition必须保留完整target tuple并exact匹配目标Attempt，协调删除target Attempt/artifact、回滚state并清空target仍必须fail closed；
- bounded execution-head state和Cycle/Attempt ledger中的nullable identity fields必须显式存在；删除字段即使其期望值为`None`也必须fail closed；
- 每个scheduled Attempt的input current IDs与target policy必须反向派生exact required-clear map；删除一个或全部required clear并协调修改history/index/state仍必须fail closed；legacy incomplete-Run re-entry必须在新Planner副作用前清除旧current；
- dependency必须与注册时replayed current chain一致，不能引用future、wrong-slot或替换后的non-current artifact；普通canonical member必须留在producing Attempt且与logical/projection path一一对应；
- `managed_projections`必须与replayed current members派生结果exact-equal；路径逃逸、protected/control target、重复key、额外/缺失entry、未知或错误owner必须fail closed；
- fixed projection bytes等于 current canonical member，invalidation后不再暴露旧 current；跨slot projection collision必须在写入前失败且保持history/index/projection bytes不变；external code/Human ingress可跳过内容digest比较，但仍必须通过路径、存在性和ownership校验；
- 四层 fallback StateGraph 都经过真实 commit、target allocation 与 side-effect前清除；replan创建新 Cycle，其余保持 Cycle；
- failed/pending target不恢复旧 pointer；Human Response snapshot必须与唯一submitted ledger identity/path/digest一致；accepted-result protection只允许当时current且status为accepted的terminal；未知kind、非terminal/non-accepted或重复protection必须在registry写入前失败；两类protected evidence在后续invalidation后仍可验证；
- Human Request ledger允许`created → packet_written? → satisfied?`且identity稳定；Human Response ledger必须形成合法有序且identity稳定的lifecycle；state声明的active response必须是latest request下max response identity并与其latest record及snapshot protection一致，删除response ledger/protection chain或回滚同一request内response后恢复必须fail closed；只有snapshot写入中的deterministic next response可使用一次受限preflight例外；
- finished Attempt output references必须反向覆盖其registered artifact，registered artifact必须具有合法scheduled/started lifecycle；删除started、整个registration/current-set或accepted/Human protection event必须fail closed；
- 已populated bounded state在initialize时必须先exact validation，不能被registry静默覆盖；仅counter/current/convenience paths全部为空的明确重建state可以从validated registry同步；history/index/execution ledger duplicate JSON key必须fail closed；
- unmanaged legacy fixture byte-for-byte不变；corrupt history/index/member digest fail closed；
- synthetic benchmark若需要检查已失效分析，只能通过 validated artifact history读取 historical evidence，不能恢复 `run_result_path` current。

A03/A03C01 CLI smoke必须写新的 `/private/tmp/lqcd-agent-a03*` output root，并核对 `artifact_history.jsonl`、`artifact_index.json`、execution heads、canonical paths、compatibility projections和accepted-result protection。A03 corrective verification还必须独立重跑stale Attempt、same-request stale Response和nonterminal target-null协调篡改。A03不要求 live provider。

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
7. ticket正文从`ready`起保持冻结，只更新YAML lifecycle metadata；
8. completion record位于`docs/tickets/completions/`，没有追加回原ticket；
9. 局部修复有maintenance record，改变合同边界的修复有独立ready corrective ticket；
10. ticket status 的变更经过用户要求或确认。

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
