---
ticket_id: A03
phase: phase-a-control-contracts
status: completed
type: implementation
depends_on: [A01, A02]
---

# 实现 Artifact Namespace、Current Index 与 Invalidation

## Goal

在不开放 A01 新产品回退路线的前提下，复用 A02 已验收的 Run/Cycle/Attempt/Transition identity，实际实现 immutable per-attempt domain-artifact namespace、append-only artifact history、typed current-artifact index、确定性的下游 invalidation 和 v0.2 fixed-path compatibility projections。

完成后，当前 runtime 与 A02 fallback StateGraph harness 必须能够证明：同一 Run 内的新 Attempt 不覆盖旧 canonical artifacts；每次成功的 Transition commit 都在目标节点副作用前建立正确的 current-validity 边界；旧 artifacts、Human decisions 和 accepted results 继续保留完整 provenance，但不会被误当作当前结果。

## Why

当前 domain artifacts 主要写入 `<output_root>/<case_id>/<run_id>/` 下的固定路径。该布局适合单轮 demo，但同一 Run 内的 review retry、analysis rerun、code fix 或 replan 会遇到两个问题：writer 拒绝覆盖已有文件，或者调用方通过 fixed path 误读旧结果。

A02 已经保证每个目标节点在副作用前获得新的 Attempt identity，并且所有 current routes 统一经过 `commit_transition()`。A03 必须把该 identity 真正用于 artifact versioning 和 current selection；仅更新文档、仅增加 standalone helper 或只在测试中模拟 invalidation 都不算完成。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md`
- `docs/tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md`
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`
- `src/lqcd_agent/graph/state.py`
- `src/lqcd_agent/graph/nodes.py`
- 所有本 ticket 实际修改的 artifact writers、readers 和对应 tests

## Scope

- 新增 Run-local artifact registry/history 和 current index；
- 将 graph-managed domain artifacts 写入 producing Attempt 的独立目录；
- 为 current state 增加 bounded typed artifact references，并保持现有 convenience path fields 与 current index 一致；
- 在 Transition commit 中按 canonical target layer 执行确定性 invalidation；
- 将 current runtime 的 plan、legacy code handoff、analysis、review、decision、approval 和 terminal/report artifacts 接入 registry；
- 将 LLM traces、analysis manifest/log/output files 作为 producing bundle 的成员保留 provenance；
- 为 fixed v0.2 artifact paths 建立明确标记的 current compatibility projections；
- 将 Human Response payload 保存为按 `human_response_id` versioned 的 immutable snapshot；
- 保护 accepted memory/result、Human decisions、raw data、execution ledger 和历史 outputs；
- 扩展 A02 的最小 StateGraph fallback harness，验证四层 invalidation，但不把这些 harness routes 宣布为当前 product routes；
- 更新受到实现影响的 source-of-truth、阶段说明和验证文档。

## Non-goals

- 不开放或重连 A01 的 re-review、analysis rerun、code fix、replan 产品 graph edges；
- 不实现 A04 的 durable PAUSE/resume、checkpoint replay、fork、technical recovery、partial-commit recovery、并发提交或 delivery idempotency；
- 不定义或实现 A05 Fake/real graph-managed Code Agent、patch bundle 或 sandbox contract；
- 不定义 A06 budgets、failure fingerprint、repeated-failure policy 或 human-granted execution window；
- 不完成 A07/Phase B 的完整 allowed-route、forbidden-route 和 recovery harness；
- 不迁移、重写或删除既有 Run output trees；
- 不改变 raw-data、provider opt-in、command allowlist、accepted-result promotion 或 Human approval policy；
- 不定义 RAG evidence bundle；
- 不新增第三方 dependency。

## Allowed Files

### Ticket and source-of-truth documents

- `docs/tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md`
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`
- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`
- `docs/NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md`
- 根目录 `README.md`，仅当 stale-documentation scan 证明其中描述因本 ticket 变得不正确时

### Artifact registry and graph integration

- `src/lqcd_agent/artifacts/__init__.py`
- `src/lqcd_agent/artifacts/registry.py`
- `src/lqcd_agent/graph/state.py`
- `src/lqcd_agent/graph/nodes.py`
- `src/lqcd_agent/graph/run_graph.py`
- `src/lqcd_agent/graph/run_graph_with_codex_handoff.py`
- `src/lqcd_agent/graph/approval_packet.py`
- `src/lqcd_agent/demo/server.py`

### Existing domain-artifact writers and readers

- `src/lqcd_agent/agents/method_planner.py`
- `src/lqcd_agent/agents/analysis_engineer.py`
- `src/lqcd_agent/agents/scientific_reviewer.py`
- `src/lqcd_agent/agents/decision_coordinator.py`
- `src/lqcd_agent/coder/task_packet.py`
- `src/lqcd_agent/coder/codex_handoff.py`
- `src/lqcd_agent/coder/codex_handoff_worker.py`
- `src/lqcd_agent/coder/test_runner.py`
- `src/lqcd_agent/llm/trace.py`
- `src/lqcd_agent/memory/store.py`
- `src/lqcd_agent/report/generate_report.py`
- `src/lqcd_agent/tools/manifest.py`
- `src/lqcd_agent/tools/command_runner.py`
- `src/lqcd_agent/tools/output_validator.py`

不要求修改上面每个文件。只有当其 fixed-path 行为、输入输出路径或 current lookup 确实受 A03 影响时才允许修改。

### Tests

- 新增 `tests/test_artifact_registry.py`
- `tests/test_execution_identity.py`
- `tests/test_state_schema.py`
- `tests/test_graph_smoke.py`
- `tests/test_run_graph_with_codex_handoff.py`
- `tests/test_method_planner_mock.py`
- `tests/test_analysis_engineer.py`
- `tests/test_scientific_reviewer.py`
- `tests/test_decision_coordinator.py`
- `tests/test_approval_packet.py`
- `tests/test_codex_handoff_worker.py`
- `tests/test_demo_server.py`
- `tests/test_memory.py`
- `tests/test_report.py`
- `tests/test_manifest.py`
- `tests/test_llm_mock_provider.py`
- `tests/test_llm_config.py`

### Approved benchmark compatibility exception

- `evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py`

该文件由用户在执行期间明确批准加入 Allowed Files，仅用于让 benchmark 通过 `artifact_history.jsonl` 读取已失效但仍可审计的历史 analysis evidence；不得恢复 stale current pointer，也不得修改 scenarios、expected behavior 或 reference outputs。

同样只修改受到新 namespace、current lookup、versioned Human Response 或 compatibility projection 影响的测试；不得借机重写无关测试。

## Do Not Touch

- `configs/`
- `raw_data/`
- `outputs/`
- `accepted_results/`（如果本地存在）
- `evaluation/reference_outputs/`
- `evaluation/expected_behavior/`
- `evaluation/synthetic_benchmarks/scenarios/`
- `evaluation/synthetic_benchmarks/expected/`
- milestone 历史文档，除非只做已证实的事实勘误并先停止请求批准
- dependency/lock files
- provider credential files、环境变量和任何外部系统
- 与 artifact namespace/invalidation 无关的 Agent reasoning、physics logic、prompt 内容和 graph topology

所有验证输出必须写到新的 `/private/tmp/lqcd-agent-a03-*` 路径或 pytest 临时目录，不得把仓库内历史 `outputs/` 当作验收证据。

## 已确认的设计决定

本节解决旧 draft 中的全部待确认问题。实现者不得改选其他 namespace、current-selection source、invalidation matrix 或 compatibility 策略。

### 1. Canonical namespace 使用独立 Attempt 目录

Run root 保持：

```text
<output_root>/<case_id>/<run_id>/
```

graph-managed domain artifacts 的 canonical immutable path 使用：

```text
<run_root>/attempts/<attempt_id>/...
```

- `attempt_id` 在 Run 内唯一，因此路径不重复包含 `cycle_id`；Cycle identity 写入 registry entry 和 artifact metadata；
- writer 可以在 Attempt 目录内保留现有相对文件名和子目录，例如 `method_plan.json`、`analysis_outputs/`、`llm_calls/`；
- 一个 Attempt 对同一 artifact slot 最多注册一个 bundle；重复注册或覆盖 canonical member 必须失败；
- standalone helper 的 legacy output behavior 可以保持兼容，但 graph runtime 必须显式使用 Attempt namespace；不能用 standalone compatibility 逃避 graph integration；
- `execution_history.jsonl`、`graph_state.json`、checkpoint database、artifact registry/index 和 external ingress 不放入 Attempt domain-artifact bundle。

禁止使用 run-root versioned filenames，例如 `method_plan.attempt_000001.json`；禁止通过时间戳、目录扫描或最新 mtime 选择 current artifact。

### 2. Artifact slots 与依赖层次

current index 的 canonical slots 固定为：

```text
plan
code
analysis
review
decision
approval
terminal
```

依赖关系固定为：

```text
plan
  -> optional code
  -> analysis
  -> review
  -> decision
  -> approval
  -> terminal
```

具体 bundle：

- `plan`：`method_plan.json`、同一 Planner Attempt 产生的 `coder_task_packet.yaml`、对应 LLM trace；
- `code`：当前 legacy handoff 的 `code_change_summary.md`、`tests_status.json` 和 worker audit files；未来 A05 Code Agent bundle 仍由 A05 定义；
- `analysis`：`run_result.json`、`manifest.json`、`run.log`、`analysis_outputs/` 及 Analysis Attempt 的相关 trace；
- `review`：`scientific_review_report.json` 及 Reviewer Attempt trace；
- `decision`：`decision_log.json` 及 Coordinator Attempt trace；
- `approval`：identity-bound approval packet、summary 和 decision template；Human Response snapshot 不属于可失效 approval bundle；
- `terminal`：`memory_update.json` 和 `final_report.md`。

`code` 是可选依赖。未需要或尚未产生 code bundle 时，analysis 直接依赖 current plan；存在适用的 current code bundle 时，analysis 必须同时记录 plan 和 code artifact IDs。Review 直接依赖 analysis；Decision、Approval 和 Terminal 必须冻结它们实际读取的全部 current upstream artifact IDs，而不能只依赖隐式路径。

failed 或 pending bundle 可以是某 slot 的最新 current evidence，但 `current` 与 `status/usable/accepted` 是不同概念。下游 guard 仍必须检查既有 structured status，不能把 current 自动解释为成功。

### 3. Artifact identity、history 与 current index

Run root 新增两个 control-plane files：

```text
<run_root>/artifact_history.jsonl
<run_root>/artifact_index.json
```

`artifact_history.jsonl` 是 append-only artifact audit source。schema version 从 `0.1` 开始，每条 record 至少包含：

- `schema_version`
- deterministic Run-local `event_id` / `event_index`
- `event`: `registered`、`current_set`、`current_cleared` 或 `protected_snapshot_registered`
- `run_id` / `case_id` / `cycle_id`
- producing or triggering `attempt_id`
- optional `transition_id` / `human_request_id` / `human_response_id`
- typed `slot` for bundle/current events；`protected_snapshot_registered` 使用 `slot: null` 和 typed `protected_kind`
- deterministic `artifact_id`
- canonical Run-relative path and member records
- direct dependency artifact IDs
- structured reason code
- timestamp

普通 bundle 的 `artifact_id` 固定由 producing Attempt 和 slot 组成：

```text
<attempt_id>:<slot>
```

同一 Attempt/slot 第二次注册必须 fail closed。Human Response 使用 `<human_response_id>:payload` 作为 protected artifact ID，记录 `protected_kind: human_response`，不伪造成 Agent Attempt artifact。Accepted terminal bundle继续使用 `<attempt_id>:terminal`，并在成为 accepted result 时追加引用同一 artifact ID 的 `protected_snapshot_registered` event和 `protected_kind: accepted_result`；该 event只增加保护语义，不创建第二份可变内容。

每个 member record 至少保存 logical name、Run-relative canonical path、SHA-256、size 和 media type。所有路径必须通过 resolve-and-containment 校验，禁止绝对路径逃逸、`..` traversal、symlink 逃逸，或指向 `raw_data/`、`accepted_results/` 和 Run 外部。

`artifact_index.json` 是 machine-readable current projection，schema version 从 `0.1` 开始，至少包含：

- `schema_version`
- `run_id` / `case_id`
- monotonic `revision`
- `last_event_id`
- `current` map；每个 slot 为 typed artifact pointer 或 `null`

typed pointer 至少包含 `artifact_id`、slot、producing Cycle/Attempt、canonical member references 和 direct dependency IDs。运行时 current selection 只允许读取该 typed index 或已与 index 校验一致的 bounded state pointers。

`artifact_history.jsonl` 保存完整审计；`artifact_index.json` 可以原子替换并从 history 重建，但 A04 之前不宣称具备跨进程 crash recovery。index 与 history identity、revision 或 referenced files 不一致时必须 fail closed，不能通过目录扫描猜测 current。

A03 不向 A02 `execution_history.jsonl` 增加新的 `record_type`。Artifact history 通过 Attempt 和 Transition IDs 与 execution ledger 关联，保持 A02 的 identity source-of-truth 边界。

### 4. Bounded state pointers

A03 明确批准为 `AnalysisState` 增加：

- `artifact_history_path`
- `artifact_index_path`
- `artifact_event_index`
- typed bounded `current_artifacts` map

现有 `method_plan_path`、`run_result_path`、`scientific_review_report_path` 等 convenience path fields 保留，但必须指向 canonical Attempt members，并在以下时机与 `current_artifacts`/index 同步：

- bundle 成功注册并成为 current；
- Transition invalidation 清除对应 slot；
- graph state 被保存；
- current reader 在节点副作用前验证输入。

Agent、provider payload、router 和自由文本都不能写 `artifact_event_index`、`current_artifacts` 或 current convenience paths。它们属于 control plane fields，并纳入 A02 identity-envelope 等价的保护校验。

完整 artifact history 不进入 Agent prompt。Agent-facing context 只包含 scoped current bundle members、typed remediation references 和已有 bounded summaries。

### 5. Deterministic invalidation matrix

当一个 committed route 将创建下列 target Attempt 时，必须清除 target layer 及所有 downstream current slots：

| Target Attempt | 保持 current | 清除 current |
| --- | --- | --- |
| `scientific_reviewer` | `plan`, optional `code`, `analysis` | `review`, `decision`, `approval`, `terminal` |
| `analysis_engineer` | `plan`, optional `code` | `analysis`, `review`, `decision`, `approval`, `terminal` |
| `code_agent` 或 `legacy_codex_handoff` | `plan` 和外部 authorization history | `code`, `analysis`, `review`, `decision`, `approval`, `terminal` |
| `method_planner` | Run-level goal/input identity、政策、history | `plan`, `code`, `analysis`, `review`, `decision`, `approval`, `terminal` |

辅助 current-route 规则同时固定为：

- target `decision_coordinator` 清除 `decision`, `approval`, `terminal`；
- 创建新的 Human Request 并 target `human_gate` 时清除旧 `approval`, `terminal`；同一 open request 的 validation Attempt 不清除其 approval packet；
- target `memory_report` 只清除旧 `terminal`；
- END 不清除任何 slot；
- 普通 forward route 与 fallback route 使用同一 target-layer 规则，不能靠 route reason 自由文本区分；
- `method_planner` 只有 A02 已批准的 replan Transition 才创建新 Cycle；A03 invalidation 不创建额外 Cycle 或 Attempt。

invalidation 必须由 control plane 在目标节点任何业务副作用前完成，并写 typed `current_cleared` events。每个 event 记录被清除的 prior artifact ID、slot、triggering Transition、target Attempt 和固定 reason code。对应 canonical files 和 history records不得删除或改写。

目标 Attempt 在完成前失败、pending 或没有注册新 bundle时，被清除的旧下游 artifacts 仍只保留为 history，不能自动恢复为 current。只有新的结构化 Transition/Attempt 可以再次建立 current pointer。

### 6. Registration 与 publication 顺序

成功路径固定为：

```text
Transition commit
-> pre-target invalidation/current clearing
-> target Attempt starts
-> writer creates canonical Attempt members
-> validate members and dependency snapshot
-> append registered/current_set history
-> atomically replace artifact_index.json
-> update bounded state pointers
-> refresh managed compatibility projections
-> finish Attempt with canonical input/output references
```

如果 writer、validation、history append、index publication 或 compatibility publication 失败：

- Attempt 必须失败并 fail closed；
- 未注册文件不得成为 current；
- 不得回退到被清除的旧 pointer；
- 不得使用 `force` 覆盖另一个 Attempt 的 canonical files；
- process-crash 导致的跨文件 partial commit recovery 明确由 A04 负责，A03 只要求一次成功函数调用返回后 history、index、state 和 projections 一致。

所有 index 和单文件 compatibility projection 必须使用同目录临时文件加 `os.replace()` 的原子 publication。不得为此引入第三方 dependency。

### 7. v0.2 fixed-path compatibility projections

以下 run-root fixed paths 保留为 current compatibility projections，而不是 canonical history：

- `method_plan.json`
- `coder_task_packet.yaml`
- `code_change_summary.md`
- `tests_status.json`
- `analysis_outputs/`
- `run_result.json`
- `manifest.json`
- `run.log`
- `scientific_review_report.json`
- `decision_log.json`
- `approval_packet/`
- `memory_update.json`
- `final_report.md`
- 当前 LLM trace compatibility paths

projection 内容必须来自 `artifact_index.json` 指向的 canonical members。新 Run 的 compatibility projection 可以被替换，或在其 source slot invalidated 时被清除；这不属于删除历史，因为 canonical Attempt files 和 history records不变。

为保护旧 outputs：

- 只有存在有效 A03 registry/index、且 projection 被 registry 明确记录为 managed 时，runtime 才能替换或清除它；
- 没有 A03 registry/index 的 legacy Run tree 维持现状，不自动迁移、不删除、不覆盖；
- existing CLI protection 继续拒绝把 terminal/decision Run 当作新 Run 复用；
- canonical artifact reference、Human Response snapshot 和 accepted result 不得引用可变 projection path；
- compatibility reader 的测试必须证明 fixed-path 内容等于 current canonical member，而不是任意历史 member。

目录 projection 使用受控 copy/materialization，不使用 symlink 作为 public contract，避免 output tree 被移动或打包后链接失效。

### 8. Human decisions 与 accepted results

Human Request、Response 和 accepted-result policy 继续服从 A02 和 Security Policy：

- identity-bound approval packet/template 写入 producing Human Gate Attempt directory，并可发布 fixed current projection；
- 外部提交继续使用明确的 current ingress path，但在 validation/consumption 前必须把 payload 以 exclusive-create 方式保存到 `<run_root>/human_responses/<human_response_id>/`；
- execution ledger 的 payload reference/digest 必须指向该 immutable snapshot，而不是随后可能重置的 ingress projection；
- valid、invalid 和 consumed response snapshots 都不得被 invalidation 删除或改写；
- accepted `memory_update.json` 的 canonical Attempt member必须保持 immutable，并记录其实际 source artifact IDs、Human Response ID（如有）和 digests；
- 后续分支清除 `terminal` current pointer不等于撤销历史 acceptance；旧 accepted result 继续可审计，但不能自动代表新 current chain；
- A03 不批准在 terminal Memory Report/END 后重新打开同一 Run；replay/fork 仍由 A04 定义。

### 9. Registry validation 与安全边界

- 所有 registry write、index read、projection refresh 和 invalidation 必须验证 active Run/Case identity；
- producing Attempt 必须是 active、已由 A02 control plane 分配且 node/kind 与 slot policy匹配；
- dependency IDs 必须存在于同一 Run history，并在 registration 时与 current index snapshot 一致；
- registry/index 不得把 raw data、config、repository files、secrets 或 external provider files复制进 domain namespace；只保存已有政策允许的 references/digests；
- LLM trace 继续禁止 secrets，并保持 bounded content；
- Markdown、mtime、glob 顺序、文件名后缀和 provider reasoning 都不能决定 current pointer 或 invalidation scope；
- registry corruption、unknown slot/event、counter mismatch、missing canonical member、digest mismatch 或 projection path escape 必须 fail closed。

## 明确延期的问题

以下问题已经明确 owner，不属于 A03 实现者可自行决定的内容：

| 问题 | Owner | A03 边界 |
| --- | --- | --- |
| crash 发生在 execution ledger、artifact history 和 index 多文件写入之间时如何恢复 | A04 | 成功返回后的状态必须一致；检测到不一致 fail closed |
| checkpoint resume 时如何重放未完成的 projection publication | A04 | 不实现 replay/recovery API |
| concurrent Human Response、network retry 和 idempotency key | A04 | 保持 A02 single-use local behavior |
| graph-managed Code Agent 的 patch/evidence bundle 内容 | A05 | A03 只注册当前 legacy code artifacts 和预留 `code` slot |
| retry budgets、failure fingerprint 和重复失败停止 | A06 | A03 不根据次数或文本决定 invalidation |
| A01 四层产品路线何时开放 | A07/Phase B | A03 只在 current runtime 和 fallback harness 验证 infrastructure |
| 是否批量迁移 v0.2 历史 outputs | 独立 migration ticket | A03 明确禁止迁移 |
| accepted result 的跨 Run promotion/revocation lifecycle | 独立 policy ticket | A03 只保护 immutable historical acceptance |

执行 A03 不存在其他待确认架构问题。如果实现发现必须改变上述 namespace、slot model、history/index authority、invalidation matrix、projection策略或保护政策，必须触发 Stop Conditions，不能现场选择替代设计。

## Requirements

### Registry primitives

- 实现单一、集中、可测试的 artifact registry 模块；不得把 slot/invalidation mapping 分散复制到多个 Agent；
- registry API 必须覆盖 initialization、validation、bundle registration、current lookup、target-layer invalidation、projection publication 和 protected snapshot registration；
- event/index counters、artifact IDs 和 slot mapping 必须 deterministic；
- canonical files immutable，current index mutable但原子发布，history append-only；
- registry 不得依赖 directory scan 来重建正常 current selection；显式 repair/rebuild helper 如果实现，只能从 validated history 重建并作为测试/未来 A04基础，不能静默运行。

### Runtime integration

- current product graph 中所有实际产生 domain artifacts 的节点必须写入 producing Attempt namespace并注册 bundle；
- 节点读取的 upstream artifacts 必须与 typed current index一致；stale、missing、digest mismatch 或 wrong dependency chain 必须在业务副作用或 routing前失败；
- A02 Attempt finished records 的 input/output references 必须指向 canonical artifacts或 registry IDs，不得只记录 fixed compatibility projections；
- current graph topology、route outcomes、risk policy、provider opt-in 和 command allowlist保持不变；
- legacy Codex handoff 与 Demo Human decision ingress 必须在消费时做 immutable snapshot，且多 Attempt 不复用旧 ingress 内容；
- `run_mock_graph()` 对新 Run 启用 A03 namespace；对已有 unmanaged legacy Run保持现有拒绝/compatibility boundary。

### Invalidation behavior

- 四类主要 target 的 exact matrix 必须由一个 typed mapping实现并单元测试；
- invalidation 清除 index pointer、bounded state pointer和 managed fixed projection，但不删除 canonical members/history/protected snapshots；
- replan invalidation 必须与 A02 new Cycle identity一致；其他三类保持 current Cycle；
- 同一 target layer 的 forward、retry 和 fallback 使用相同规则；
- target node side effect开始前，读取旧 downstream convenience path必须得到 null/absent，而不是 stale path；
- 任何 failure不得恢复已清除的旧 downstream current pointer。

### Compatibility and protection

- 现有 v0.2 fixed-path consumers 在 single-pass current run 后仍能读取预期文件；
- compatibility projection 必须可追溯到 current canonical artifact ID和 digest；
- unmanaged legacy Run outputs、raw data、accepted results和 Human Response snapshots不可修改；
- accepted memory只能继续由既有 policy产生；A03 不得增加新的 acceptance route；
- 代码注释只使用英文。

## Deliverables

- `src/lqcd_agent/artifacts/` 下的 registry/history/index/invalidation 实现；
- 接入 current graph nodes和 artifact writers/readers 的 per-attempt namespace；
- typed bounded current-artifact state和 canonical Attempt input/output references；
- v0.2 managed compatibility projection layer；
- versioned Human Response snapshots和 accepted-result source references；
- 四层 fallback invalidation StateGraph harness与 current runtime integration tests；
- 更新后的 artifact、state、architecture、安全、验证、current-state、阶段和 decision-log 文档；
- 本 ticket Completion Record中的实际 changed files、verification结果、commit和 follow-ups。

## Acceptance Criteria

### Namespace and immutability

- 同一 Run 中两个相同 kind的 Attempts 产生不同 canonical directories和 artifact IDs；
- 第二个 Attempt不会改写第一个 Attempt的任何 canonical bytes；
- 重复 Attempt/slot registration、path escape和 canonical overwrite均被拒绝；
- registry member digest和实际文件一致。

### Current selection and compatibility

- current selection只由 typed index/state pointer决定；
- index、state convenience paths和 managed fixed projection指向同一 canonical content；
- invalidation后旧 fixed projection不再暴露 stale current结果；
- existing unmanaged legacy Run tree在测试中保持 byte-for-byte不变；
- current single-pass CLI/demo 的外部 fixed-path read compatibility保持通过。

### Four-layer invalidation

- re-review只清除 review及下游；
- analysis rerun清除 analysis及下游；
- code fix清除 code及下游；
- replan创建新 Cycle并清除 plan及全部下游；
- 每个场景都经过真实 StateGraph selection/commit/scheduled-target-consumption harness，而不是只调用 invalidation helper；
- harness仍明确不是 product route已经开放。

### Failure and provenance

- invalidation发生后目标 Attempt失败或pending时，旧结果只在 history中存在，不恢复为 current；
- Attempt ledger input/output references、artifact history和index identity可交叉核对；
- Human decision引用的旧 artifact失效后，引用的 ID/path/digest仍可验证；
- accepted result保持 immutable和可审计，但不自动成为新 chain的 current result；
- 无效 registry/index/digest或 identity mismatch均 fail closed。

### Runtime and documentation

- current deterministic/mock graph、legacy handoff和 Human decision continuation通过 integration tests；
- full test suite通过，且不依赖 live provider、network或仓库历史 `outputs/`；
- source-of-truth只宣布实际实现并通过测试的 A03能力；
- Phase B文档改为复用 A03 invalidation infrastructure，而不是重复声明尚未实现；
- A04/A05/A06/A07边界保持清楚，没有被 A03提前实现；
- stale-documentation scan、Allowed Files scope audit和 ticket metadata检查通过。

## Verification

实现期间先运行 focused tests，最终必须运行完整验证：

```bash
pytest -q tests/test_artifact_registry.py tests/test_execution_identity.py tests/test_state_schema.py
pytest -q tests/test_graph_smoke.py tests/test_run_graph_with_codex_handoff.py
pytest -q tests/test_method_planner_mock.py tests/test_analysis_engineer.py tests/test_scientific_reviewer.py tests/test_decision_coordinator.py
pytest -q tests/test_approval_packet.py tests/test_codex_handoff_worker.py tests/test_demo_server.py tests/test_memory.py tests/test_report.py
pytest -q
python -m compileall -q src tests
git diff --check
```

还必须执行并在 Completion Record记录：

- 一个写入新 `/private/tmp/lqcd-agent-a03-*` root的 deterministic CLI smoke；
- artifact history/index schema与 cross-reference检查；
- 四层 invalidation trajectory检查；
- unmanaged legacy output fixture byte-preservation检查；
- repository Markdown relative-link检查；
- ticket metadata/status检查；
- 相对 A03开始提交的 Allowed Files scope audit；
- 根 README、核心 docs、Phase Overview、Current State、Decision Log和 A03/A04/A05/A06/A07 TODO的 stale-documentation scan。

本 ticket不要求 live-provider测试。若修改影响 provider-backed path，必须使用 deterministic injected/mock provider覆盖 path和 trace行为；不得用真实 credentials作为验收条件。

## Stop Conditions

- 需要删除、改写或自动迁移任何既有 canonical/history artifacts时停止；
- 需要把 unmanaged legacy fixed paths当作可删除 projection时停止；
- 需要放宽 raw-data、accepted-result、Human approval、provider、command或secret policy时停止；
- 需要新增 execution ledger `record_type`、改变 A02 identity语义或复用 terminal Attempt时停止；
- 需要开放新的 product graph edge、实现 durable resume、Code Agent contract或 budget/fingerprint时停止；
- 无法在 target side effect前建立确定性 invalidation边界时停止；
- 需要改用 versioned run-root filenames、directory scan、mtime、symlink public contract或自由文本 current selection时停止；
- 需要修改 Allowed Files之外的源码、测试、数据、配置或 dependency时停止；
- 发现 current public contract与本 ticket已确认设计冲突，且不能通过列出的 source-of-truth同步解决时停止；
- 无法运行 focused tests、full `pytest -q`、compileall、scope audit或 required smoke时停止；
- 发现 A02 baseline本身不通过、working tree含来源不明且与 A03重叠的改动，或无法建立可靠 diff baseline时停止。

## Required Documentation Updates

- `docs/ARTIFACT_CONTRACTS.md`：记录 canonical namespace、registry/history/index、bundle members、compatibility projections和 protected snapshots；
- `docs/STATE_SCHEMA.md`：记录新增 bounded fields、slot types、current synchronization和 control-plane ownership；
- `docs/ARCHITECTURE.md`：记录 transition-time invalidation、runtime integration和仍未开放的 product routes；
- `docs/SECURITY_AND_DATA_POLICY.md`：记录 managed projection与 immutable canonical/history/accepted/Human边界；
- `docs/VERIFICATION_GUIDE.md`：增加 A03 focused、trajectory、compatibility和 full-suite验证入口；
- `docs/REPO_CURRENT_STATE.md`：只记录实际完成并通过验收的 A03能力与剩余边界；
- `docs/DECISION_LOG.md`：追加 A03 namespace、index authority、matrix、projection和阶段顺序决定；
- `docs/README.md`、Phase A Overview、Phase B Overview和 `docs/NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md`：同步 A03 status以及 Phase B从“实现 invalidation”调整为“复用并验证 A03 invalidation”；
- 完成 stale-documentation scan，只修改因 A03实现而过时的内容。
