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

### Phase A Control Protocol 静态验证

A02C01与A04–A07从`review`提升为`ready`前及各design/corrective ticket执行时必须运行tracked design validator：

```bash
python scripts/validate_phase_a_control_protocol.py
```

该检查strict读取[`CONTROL_PROTOCOL_0_4.json`](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json) machine schema 0.4和[`PHASE_B_REQUIREMENT_CATALOG.json`](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json) catalog 0.4.0，验证ControlOperation graph终结、multi-successor guard互斥/穷尽、tagged evidence与incoming edge匹配、十二种variant overlay、单一transaction domain、normal/cancel/interrupt CAS交错、winner-observation组合owner状态、request-owned normal safe-stop candidate classification、每个trigger class/context的唯一stop route、cancel branch到resolution tuple/phase闭包、START/Replay/Fork/ordinary Transition的commit-gated capability、exact terminal lifecycle、reservation到ExternalOperation tuple及source proof到request Run/lineage的绑定、Replay source-policy确定性分类、stable paused/terminal fork、Pause aborted/interrupted/quarantined finality、Run lifecycle循环、independent graph seal、variant phase dominance、pre-start DAG、field binding、131个ticket/catalog stable IDs及protocol SHA。本次还补齐normal-result stop的原子Pause/Run handoff、ExternalOperation pre-start与Attempt执行授权分离、不可变authorization下的独立execution lease，以及Cancel unavailable保守结算；本轮补齐recoverable timeout原Attempt失败消费与advance持有的fresh Analysis准备，以及消费后的活动绑定释放、RecoveryDecision目标授权和严格JSON/对象结构校验；最新修复由原resume owner完成post-claim完整性失败的消费者停止、结算与failed/unavailable收尾，不依赖Code artifact；101项semantic、3项structural、178项publication-order mutations及6项JSON/catalog负向检查验证这些边界。它是design-time lint，不表示Phase B runtime、fault fixture或acceptance matrix已经实现；B00仍须把同一合同转为collectable tests和normalized traces。

### A04 Pause/Resume 设计合同验收

A04是文档限定design ticket。执行时运行：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

并静态核对：

- A04在`ready`后只有YAML lifecycle metadata改变，冻结正文与执行前hash一致；A01–A03/A03C01保持`completed`，A05–A07正文、protocol与catalog bytes不变；
- Architecture、State Schema、Artifact Contracts和Security Policy一致区分已确认的A04目标合同与当前schema `0.2` runtime；
- 只有stable exact paused/opened/public-checkpoint closure可以resume，三类typed Pause、single-use claim、terminal owner、cancel/interrupt、compatibility及Replay/Fork isolation均保留；
- A04的21个required IDs继续存在于catalog，A07/Phase B承担fault-injection和runtime acceptance，不把design validator当成实现测试；
- Allowed Files、Do Not Touch、Markdown relative links、ticket metadata和删除/重命名审计通过，且`src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`及accepted artifacts没有A04产生的diff。

A04明确不运行runtime、benchmark或live-provider测试；其完成证明合同同步和静态一致性，不证明Pause/Resume API已可执行。

### A05 Code Agent 设计合同验收

A05是文档限定design ticket。执行时运行：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

并静态核对：

- A05在`ready`后只有YAML lifecycle metadata改变，冻结正文SHA-256保持一致；A01–A04/A02C01/A03C01保持`completed`，A06/A07正文、protocol与catalog exact bytes不变；
- Architecture和Agent Roles一致冻结`CodeAgentSubgraph`控制层与replaceable `CodingBackend`执行层，且current `legacy_codex_handoff`没有被重命名、迁移或当作canonical Code Agent；
- State Schema与Artifact Contracts记录schema `0.1` task/external-result/result、workspace manifest/seal、canonical bundle、bounded projection、trusted verification和`AnalysisExecutionSpec`，同时明确它们尚未进入当前schema `0.2` runtime；
- Security Policy保留Attempt-isolated immutable base、normalized path/tool/network policy、no-secrets/no-control-repo writes、single-operation dispatch、strict containment、fresh verification、Human authorization与no-promotion边界；
- A04 `external_result` Pause、A06 reservation/settlement与ExternalOperation single-winner/final-evidence合同没有出现第二套resume、budget、route或terminal authority；
- Phase B Fake和未来real backend使用同一port/validator/verifier/registry/fresh Analysis path；Python Codex SDK只保留为独立C00全部required capabilities通过后的条件性候选；
- A05的29个required IDs继续存在于catalog，A07/Phase B承担deterministic scenarios与runtime acceptance，不把design validator当成实现测试；
- Allowed Files、Do Not Touch、Markdown relative links、ticket metadata和删除/重命名审计通过，且`src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`及accepted artifacts没有A05产生的diff。

A05明确不运行runtime、benchmark或live-provider测试；其完成证明Code Agent目标合同及文档闭合，不证明subgraph、backend、workspace、resume、containment或fresh Analysis runtime已经实现。

### A06 Budget 与 Stop 设计合同验收

A06是文档限定design ticket。执行时运行：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

并静态核对：

- A06在`ready`后只有YAML lifecycle metadata改变，冻结正文SHA-256保持一致；A01–A05/A02C01/A03C01保持`completed`，A07正文、protocol与catalog exact bytes不变；
- Architecture、Agent Roles、State Schema、Artifact Contracts和Security Policy一致记录trusted control plane为唯一budget authority，`BudgetPolicy/Decision/FailureFingerprint/BudgetGrant 0.1`、schema `0.4` budget events与bounded projection尚未进入当前schema `0.2` runtime；
- `balanced_v1`与harness-only `phase_b_test`是唯一profiles；Cycle/Attempt/Transition/automatic route从authoritative records计数，LLM/tool/verification及Code Backend aggregate在side effect前reservation，crash按maximum且不退款/redispatch；
- semantic context fingerprint排除execution identity，自同一Run第二次exact occurrence起禁止automatic fallback；typed Human grant只为exact route/fingerprint/target增加一次机会且不能突破global ceilings或terminal reserve；
- 每个Run保留5 Control Attempts/6 Transitions的terminal tail，invalid response只有保留3 Control/4 Transitions时才可repause；Pause deadline过期resume零mutation，stop proof不完整固定为quarantine及`recovery_required`/`terminal_closure: unavailable`；
- A06的21个required IDs与catalog scenario set一致；A07/Phase B承担fake clock、fault injection、normalized trace和runtime acceptance，不把design validator当成budget manager实现测试；
- Docs Index、Phase Overview、Current State、Decision Log与completion index一致记录A06完成、A07 ready，并明确A06没有修改runtime、graph、checkpoint、tests、configs、providers、data、accepted artifacts或历史Run；
- Allowed Files、Do Not Touch、Markdown relative links、ticket metadata、删除/重命名和stale-documentation审计通过。

A06明确不运行runtime、benchmark或live-provider测试；其完成证明预算、重复失败与停止目标合同闭合，不证明budget ledger、resource enforcement、trusted clock、grant或stop runtime已经存在。

### A07 Phase B Harness Acceptance 设计合同验收

A07是Phase A最后一张文档限定design ticket。执行时运行：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

并静态核对：

- A07在`ready`后只有YAML lifecycle metadata改变，冻结正文SHA-256保持一致；A01–A06/A02C01/A03C01保持`completed`且正文未修改，protocol与catalog exact bytes不变；
- catalog owner集合exact等于A01、A02、A02C01、A03、A03C01、A04、A05、A06、A07，共131项required requirements；A07的15个`A07-META-*` IDs与catalog scenario set一致；
- Evals/Observability记录required control acceptance、compatibility regression与capability evaluation分离，六层模型、exact normalized trace、双client/process concurrency、deterministic fault injection与matrix zero-gap gate完整；
- Phase A Overview标记completed；Phase B Overview记录B00–B05的固定职责和依赖、阶段entry/exit gate，并明确当前仍为planned且没有ready implementation ticket；
- B00–B05 ticket文件、`tests/phase_b/acceptance_matrix.json`、runtime、tests或fixtures均未创建，本次不把design validator当作Phase B scenario pass；
- Docs Index、Current State、Decision Log与completion index一致记录A07及Phase A完成，下一步只是起草和确认B00；
- Allowed Files、Do Not Touch、Markdown relative links、ticket metadata、删除/重命名和A07范围内现行状态文档审计通过。

A07明确不运行pytest、benchmark或live-provider测试；其完成证明“Phase B怎样验收”已经冻结，不证明任何Layer 0–5 scenario、matrix或runtime已实现。

### Phase B Acceptance Foundation（B00）

B00提供可执行的[generator](../scripts/generate_phase_b_protocol.py)、[acceptance CLI](../scripts/validate_phase_b_acceptance.py)、[matrix](../tests/phase_b/acceptance_matrix.json)、[registry](../tests/phase_b/failpoint_registry.json)及[独立final obligations](../tests/phase_b/final_obligations.json)。协议以[B00冻结票据](tickets/phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md)为准；当前只有B00 construction证据，不是Phase B runtime完成证明。

```bash
B00_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b00-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
RUN_LIVE_LLM_TESTS=0 pytest --collect-only -q tests/phase_b
RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b
python scripts/validate_phase_b_acceptance.py \
  --mode construction --ticket B00 \
  --evidence-dir "$B00_EVIDENCE_DIR/construction" \
  --report "$B00_EVIDENCE_DIR/construction-report.json"
! python scripts/validate_phase_b_acceptance.py \
  --mode final \
  --evidence-dir "$B00_EVIDENCE_DIR/final" \
  --report "$B00_EVIDENCE_DIR/final-negative-report.json"
RUN_LIVE_LLM_TESTS=0 pytest -q
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

Evidence子目录与report文件必须不存在，并位于仓库外；不能复用旧目录。CLI自行生成token、冻结实际source/tests/scripts/configs/synthetic inputs/docs/manifests的path/type/mode/bytes摘要，启动禁用live opt-in的fresh pytest subprocess，最后复核输入未变化。不要在验收期间修改仓库。公开CLI没有test runner、旧evidence或任意shell命令注入选项。

Construction当前owned/covered/passed必须exact为15项A07 meta IDs，global covered=15、remaining=116、passed/passed_ids=null。两个完成标志为false，runtime状态not_run、passed_case_ids=null，2286条case显式missing；15项exit checks均not_run。META-006/015静态通过不代表production hooks已实现。

真实final先验证全部输入、独立清单、required node collection与适配器selection；当前预期非零，只有三类缺口：116项coverage_gap、2286项runtime_evidence_gap、15项exit_evidence_gap。不能仅凭非零就通过负向验收；任何parser、collection、invalid evidence或internal error都须另行处理。当前preflight不会执行B05完整退出流程。

Final具备前置条件后重新执行两个stage的required scenarios，并分派Layer 0–5、cross-system fault/concurrency、Phase B/full/synthetic/legacy suites、compileall、full mock benchmark、CLI smoke和documentation/scope。实际适配器由B05接入`tests/phase_b/harness/exit_checks.py:production_adapters`，不得改变固定check IDs、schema、stage或完成逻辑。每层selection由matrix派生，cross-system由独立case binding派生，suite selection必须等于fresh全目录collection；B05不能用passing子集替代full suite。

Pytest writer分别记录collection/deselection、setup/call/teardown、skip/xfail/XPASS、逐scenario typed result/invariants/trace、production hook触发与恢复后的case result。Future hooks通过注入的test observer登记真实production调用位置，不让runtime读取test fixture。Final逐项联结本次node pass、hook source、触发、outcome与exact trace；inventory、源码函数名或自报passing均不足以通过。

Exit envelope只引用本次evidence目录内的raw bytes SHA-256。Report使用排除token与allowlisted trace ephemeral字段后的semantic evidence digest，不透传raw token-bearing文件摘要；保留identity/head/authority/digest语义。Benchmark必须覆盖`full.json`全部case和全部13项checklist，退出0或顶层passed=true不够；CLI smoke必须证明ledger/state/checkpoint/artifact/budget/Pause/child/accepted invariants。文档适配器还须记录semantic review依据，关键词扫描不能替代合同审阅。

B00已用隔离synthetic adapters永久测试final完整成功、缺exit/hook/post-claim case、stale token/worktree/contract、内部异常及benchmark虚假成功；隔离fixture不能生成project completion。Schema compatibility和bootstrap admission的production反例仍分别由B02/B03/B04实现，B00未新增其runtime。

只有131项所有适用scenarios及runtime obligations均通过才可`requirements_zero_gap=true`；还需全部exit checks通过且errors为空才可`phase_b_complete=true`。当前二者均为false。后续票仍须独立review并获用户批准。

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

Phase A验证器将structure、semantics和freeze分别检查；104项协议变异中101项直接调用指定语义规则，3项验证结构，另保留6项JSON/catalog检查。每条规则先接受合法协议；结构摘要和graph摘要不能代替语义变异通过。内置28条消费失败路径覆盖stop/authority总函数。文档仅自动检查stable IDs、引用和显式枚举，不锁定自然语言措辞；文义一致性仍须人工review。

Publication顺序另有178项直接语义变异，覆盖六条线性控制路径的相邻逆序（同步修改dependency）、绕过、缺失与不可达阶段。独立安全顺序必须包含每个必需publication阶段，特别是running lifecycle先于checkpoint、ownership先于claim、claim先于consume以及eligibility先于terminal lifecycle；验收不能仅更新冻结摘要来放行顺序变化。
