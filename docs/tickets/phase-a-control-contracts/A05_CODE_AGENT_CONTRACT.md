---
ticket_id: A05
phase: phase-a-control-contracts
status: review
type: design
depends_on: [A01, A02, A03, A03C01, A04]
---

# 定义 Graph-managed Code Agent Contract

## Goal

冻结 graph-managed `CodeAgentSubgraph`、可替换 `CodingBackend`、typed task/result、isolated workspace、change bundle、trusted verification 和 authority 合同，使主图可以在不了解具体编码工具循环的情况下安全消费代码修改结果。Phase B使用遵守同一接口的deterministic Fake；Python Codex SDK只是通过Phase C capability gate后的条件性首选真实backend，不在本ticket中锁定为已证明实现。

本 ticket 只确认设计并同步核心 source-of-truth 文档；不实现 Code Agent、产品 graph 路线、sandbox、backend、依赖或测试。

## Why

当前 `codex_handoff` 是 file-based compatibility path：它生成 task packet，选择性调用当前仓库中的外部 Codex worker，再读取 Markdown summary 与 `tests_status.json`。A02 已明确该 physical node 的 canonical kind 是 `legacy_codex_handoff`，不能直接改名为 `code_agent`。

目标系统需要一个 graph-managed control boundary，而不是让主图直接持有编码工具循环或让外部 worker 修改运行中的控制仓库。A05 将生命周期与执行实现分为两层：`CodeAgentSubgraph` 管理受信控制流程，`CodingBackend` 只完成 Attempt-bound external coding operation。Phase B用`FakeCodingBackend`验证全部控制合同；Phase C先通过独立C00 feasibility ticket验证候选实现，再在不改变主图合同的情况下接入通过门禁的真实backend。

OpenAI官方Codex SDK文档确认Python SDK通过JSON-RPC控制本地app-server、可以创建/运行Codex thread，并提供`Sandbox.workspace_write`把写权限限制在workspace与显式writable roots。这些能力使它适合作为候选，但官方页面本身没有为本ticket更强的durable `dispatch/lookup/fetch_result/cancel`、逐tool audit、停止后无activity和进程重启恢复语义提供完整合同。完整Agents SDK `SandboxAgent`拥有Manifest、provider、mount、port、snapshot与resumable sandbox session等更重runtime abstraction，且当前为beta，也不在本ticket中预先选定：

- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)
- [Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)

## Read First

- [`AGENTS.md`](../../../AGENTS.md)
- [`docs/README.md`](../../README.md)
- [`docs/tickets/README.md`](../README.md)
- [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`docs/AGENT_ROLES_AND_BOUNDARIES.md`](../../AGENT_ROLES_AND_BOUNDARIES.md)
- [`docs/STATE_SCHEMA.md`](../../STATE_SCHEMA.md)
- [`docs/ARTIFACT_CONTRACTS.md`](../../ARTIFACT_CONTRACTS.md)
- [`docs/SECURITY_AND_DATA_POLICY.md`](../../SECURITY_AND_DATA_POLICY.md)
- [`docs/VERIFICATION_GUIDE.md`](../../VERIFICATION_GUIDE.md)
- [`docs/REPO_CURRENT_STATE.md`](../../REPO_CURRENT_STATE.md)
- [`A01_TRANSITION_MATRIX.md`](A01_TRANSITION_MATRIX.md)
- [`A02_RUN_CYCLE_ATTEMPT_MODEL.md`](A02_RUN_CYCLE_ATTEMPT_MODEL.md)
- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)
- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)
- `src/lqcd_agent/coder/task_packet.py`
- `src/lqcd_agent/coder/codex_handoff.py`
- `src/lqcd_agent/coder/codex_handoff_worker.py`
- `src/lqcd_agent/coder/test_runner.py`
- [OpenAI Codex SDK documentation](https://learn.chatgpt.com/docs/codex-sdk)
- [OpenAI Sandbox Agents documentation](https://developers.openai.com/api/docs/guides/agents/sandboxes)

## Scope

- 冻结 `CodeAgentTask`、`CodeAgentExternalResult` 与 canonical `CodeAgentResult` schema `0.1`；
- 冻结 canonical `code_agent` Attempt、`CodeAgentSubgraph`、`CodingBackend` 与主图的职责边界；
- 冻结Phase B `FakeCodingBackend`与Phase C通过capability gate后真实`CodingBackend`的替换边界，并将Python`CodexSdkBackend`记录为条件性首选候选；
- 冻结每 Attempt 独立 workspace、base revision、path/tool/network policy 与不可突破的安全边界；
- 冻结 `WorkspaceManifest`、`WorkspaceSeal`、backend dispatch receipt 与 checkpoint/workspace identity 规则；
- 冻结 content-addressed change bundle、trusted verification evidence 和 code artifact 注册规则；
- 冻结 success、no-change、failure、human escalation 与 budget outcome taxonomy；
- 冻结 A04 `external_result` Pause、dispatch/delivery idempotency 和 crash 行为；
- 冻结 Code Agent result 到 A01 Analysis/Coordinator 路线的 guards，以及 verified bundle 到 fresh Analysis execution 的交接；
- 冻结 Fake backend 必须覆盖的 deterministic scenarios；
- 将产品 subgraph、Fake backend、真实 backend、workspace manager 与 graph integration 分别交给 A07 和后续 Phase B/Phase C implementation tickets。

## Non-goals

- 不实现 `CodeAgentSubgraph`、Fake/真实 backend、A01 产品 edge、A04 resume API 或 A06 budget manager；
- 不安装 Python Codex SDK，不选择其具体版本、Codex model、reasoning profile、provider credential 或生产部署配置；
- 不引入完整 Agents SDK `SandboxAgent`、container/hosted provider、remote sandbox、mount、port 或 snapshot runtime；
- 不定义具体 token、tool、wall-clock、cost 或 retry 数值；
- 不自动修改运行中的控制仓库，不实现 patch promotion、commit、merge、push、PR 或 deployment；
- 不批准 dependency、security policy、graph topology、schema 或 scientific method 的任意修改；
- 不把测试通过解释为科学接受、Human approval 或 accepted-result authorization；
- 不迁移、删除或重命名当前 `legacy_codex_handoff` artifacts/path；
- 不运行 live-provider 测试。

## Allowed Files

本 ticket 提升为 `ready` 并执行时，只允许修改：

- `docs/tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md`：仅允许更新 YAML 状态元数据，不向正文追加执行日志；
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`；
- `docs/tickets/completions/A05_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/ARCHITECTURE.md`；
- `docs/AGENT_ROLES_AND_BOUNDARIES.md`；
- `docs/STATE_SCHEMA.md`；
- `docs/ARTIFACT_CONTRACTS.md`；
- `docs/SECURITY_AND_DATA_POLICY.md`；
- `docs/VERIFICATION_GUIDE.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

- A01–A04、A03C01 以及 A06–A07 ticket 正文；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/` 和 accepted artifacts；
- graph topology、checkpoint backend、dependency versions、provider 配置、认证与 secrets；
- 当前 `legacy_codex_handoff` runtime 与 artifacts；
- 已完成 ticket、completion/correction history、milestone 或 tag。

## Canonical Architecture Boundary

主图只看见一个 canonical `code_agent` Attempt 和一个稳定 `CodeAgentSubgraph` boundary。Subgraph 管理 task、workspace identity、budget reservation、Pause/Resume、trusted verification、artifact registration 与 structured route outcome；它通过 `CodingBackend` port 请求图外编码工作，但不持有具体工具循环。

```text
Parent LangGraph
└── CodeAgentSubgraph
    ├── prepare_external_operation  trusted deterministic control stage
    ├── wait_external_result        A04 Pause boundary
    │       └── trusted Host dispatches outside graph
    │           └── CodingBackend
    │               ├── FakeCodingBackend   Phase B
    │               └── RealCodingBackend  Phase C, selected only after C00 gate
    └── consume_code_agent_result   physical node_name = code_agent
```

`CodeAgentSubgraph` 是控制意义上的 graph-managed lifecycle，不表示 Codex 工具循环成为 graph event，也不允许 SDK 修改 graph state。它在 A04 safe boundary 内协调的第一版顺序固定为：

- `prepare_external_operation`与`wait_external_result`是trusted deterministic control stages，不是Agent/work Attempt，不分配新的Attempt kind，也不得写target `started`；
- `consume_code_agent_result`是唯一映射canonical `attempt_kind = code_agent`和physical `node_name = code_agent`的work stage，只能在Pause claim与A06 settlement完成后领取scheduled target Attempt；
- internal control stages只能写A04/A06允许的checkpoint、reservation、Pause与immutable control/audit evidence，不能产生code artifact、执行backend工具循环或绕过A02 target consumption。

```text
inbound Transition allocates scheduled code_agent Attempt
-> CodeAgentSubgraph validates and freezes CodeAgentTask
-> trusted Host prepares WorkspaceManifest and isolated workspace
-> A06 admits and reserves the external producer operation
-> A04 opens external_result Pause
-> trusted Host dispatches CodingBackend outside the replayable graph node
-> backend returns immutable CodeAgentExternalResult evidence
-> resume_run atomically claims the Pause
-> A06 settles the exact reservation before the target Attempt starts
-> code_agent Attempt starts once
-> CodeAgentSubgraph validates, verifies and registers CodeAgentResult bundle
-> code_agent Attempt finishes and resume records consumed outcome
-> A01 guard routes to Analysis Engineer or Decision Coordinator
```

任何可能由 LangGraph resume 重新进入的节点都不得在 Pause `opened` 发布前启动 backend、创建第二个编码 operation 或执行其他不可安全重放的外部副作用。Backend dispatch只能由可信Host在图已安全暂停后完成，并通过stable、Host-owned `producer_operation_id`幂等化；该字段就是项目权威backend operation identity，不由provider job/thread ID派生或替代。

Pause前的task snapshot、workspace preparation、resource reservation与Pause publication同样必须使用Attempt/operation-bound create-new identities幂等执行：exact重复返回已有identity和digest，不同内容撞到已有identity必须conflict。它们不能依赖只存在于当前Python进程的临时状态。

外部 backend 的工具循环无权修改 graph state、execution ledger、artifact registry、Pause lifecycle、budget policy 或 route。Subgraph 只消费 exact Attempt-matched result、执行独立验证与 scope checks、注册 canonical artifact 并返回 structured outcome。

### `CodingBackend` Port

所有 backend 必须实现同一语义接口；具体语言 signature 由 implementation ticket 冻结，但不得改变以下操作含义：

```text
dispatch(task_ref, workspace_manifest_ref, producer_operation_id)
    -> BackendDispatchReceipt
lookup(producer_operation_id)
    -> BackendOperationStatus
fetch_result(producer_operation_id)
    -> immutable CodeAgentExternalResult reference
cancel(producer_operation_id, typed_reason)
    -> BackendOperationStatus
```

- `dispatch` 对 exact operation/task/workspace 必须幂等；同 operation identity 的不同输入必须 conflict；
- `lookup` 是 dispatch 结果不确定、Host 重启或 delivery 重试时的唯一查询入口，不能隐式启动新 operation；其status在operation已知时必须携带同一canonical dispatch receipt reference/digest，使Host能在“provider已接受但Run-local receipt尚未publication”的崩溃窗口恢复exact receipt；
- `fetch_result` 只能返回已经持久化且可按 digest 验证的 immutable result reference，不能返回 mutable workspace path；
- `cancel`只能作用于exact existing operation，必须幂等撤销workspace写lease并由Host终止其dedicated process/runtime；它不能创建替代operation、修改Run/Pause lifecycle或伪造完成结果；
- `BackendDispatchReceipt`至少绑定Host-owned producer operation、task、workspace、backend kind/version、nullable provider operation/thread references、dispatch status与canonical digest；
- `BackendOperationStatus`只允许`accepted | running | completed | failed | cancelled | unknown`，并绑定operation/backend identity与查询时间；除`unknown`外必须引用原`BackendDispatchReceipt`，`unknown`必须显式使用null receipt且表示不能证明原operation状态，不授权再次dispatch；
- provider job/thread identity只在candidate backend实际提供且C00证明可稳定恢复时记录；不适用或不可证明时必须显式为null，不能伪造synthetic provider identity。Fake只需稳定的Host-owned producer operation identity；
- provider job ID、Codex thread ID或其他provider reference只属于backend audit evidence，不能代替Run、Cycle、Attempt、Transition、Pause、reservation或producer operation identity；
- `FakeCodingBackend`和任何通过C00的真实backend必须通过相同port、ingress validator、trusted verifier与registry path，不能建立provider-specific route或resume API。

Budget、Pause deadline与Run cancellation authority仍只属于A04/A06可信控制层。Backend只执行控制层对exact operation下达的停止命令；Host wrapper必须在aggregate hard limit、operation timeout或`cancel_pause`要求停止external execution时阻止新的tool/LLM side effect并终止dedicated runtime。无法证明停止、写lease撤销或停止后filesystem稳定时，Run/result fail closed且workspace隔离保留，不得注册bundle或重新dispatch。

## Contract and Identity Version

`CodeAgentTask`、`CodeAgentExternalResult`、`CodeAgentResult`、`BackendDispatchReceipt`、`WorkspaceManifest`、`WorkspaceSeal`、change manifest 与 verification result 使用独立 schema version `0.1`。Host-owned `AnalysisExecutionSpec` 同样使用独立 schema `0.1`，但属于目标 Analysis Attempt 的 control/audit input，不是 Code Agent bundle member，也不把 A03 artifact registry schema 升级为新的版本。这些合同均不兼容解释当前 legacy handoff files。

每个 task 使用 deterministic `task_id = <attempt_id>:code_task`，并冻结：

- `run_id`、`case_id`、`cycle_id`、`attempt_id`；
- `attempt_kind = code_agent` 与 physical `node_name = code_agent`只映射subgraph的`consume_code_agent_result` work stage；pre-start control stages不创建或领取Attempt；Fake/real差异只记录在backend identity，不改变graph/subgraph boundary；
- exact inbound `transition_id`、source Attempt 与 task origin；
- task、base、policy、authorization 与 evidence canonical digests。

Task、external result、Pause、producing Attempt、execution heads 与 final artifact pointer 中任一 identity 缺失或不一致都必须在 code artifact 注册前 fail closed。调用方不能选择另一 Attempt、复用旧 task/result 或把 `legacy_codex_handoff` 输出声明为 `code_agent` 结果。

## `CodeAgentTask` Contract

`CodeAgentTask` 由可信 control plane 从 current validated plan、Coordinator remediation、inbound Transition 和可选 Human authorization 派生。Agent output 只能提供候选描述，不能自行扩大最终 task。

Task 至少冻结：

- `schema_version`、全部 execution identity、`task_id` 与 `task_digest`；
- `task_origin = planner_gap | coordinator_code_fix`；
- bounded `task_summary`、requirements 与 acceptance criteria；
- exact evidence artifact IDs、paths、digests 与 validated execution/artifact heads；
- full immutable Git `base_revision`、`base_tree_digest` 与 source runtime fingerprint；
- normalized repository-relative `read_paths`、`write_paths` 与 `forbidden_paths`；
- typed tool policy、network policy 与 filesystem policy，其中包含Host-owned verification-only `ephemeral_paths`；
- ordered required `verification_specs`；
- A06-owned `budget_envelope_ref` 与 digest，不在 A05 填写默认数值；
- nullable `human_authorization_ref`、授权 action/scope/digest 与 single-use identity；
- exact `coding_backend_kind`、external producer contract、`producer_operation_id` 与 expected result schema。

Requirements、acceptance criteria、evidence、write scope 与 required verification 都必须非空。所有 nullable 字段必须显式存在。自由文本不能覆盖 typed path、tool、budget、risk 或 authorization policy。

`base_revision` 必须是可信 Host 解析的完整 immutable commit identity，不能是 branch、tag、`HEAD` 或其他可变 ref。第一版不接受 dirty control-repository worktree 作为 base；如未来需要非 committed source snapshot，必须由独立 design ticket 定义 immutable packaging 与 provenance。

Coordinator code-fix Transition必须在A03 invalidation前冻结触发诊断的exact artifact IDs/digests，并通过Transition/task provenance引用它们。Transition之后，这些旧analysis/review/decision artifacts只作为immutable historical evidence读取，不恢复为current，也不成为新code pointer对stale current的隐式依赖。

Repository workspace paths与Run evidence paths属于不同namespace。Evidence refs必须是A03 registry验证过的Run-relative canonical members；Trusted Host只把task明确选择且经过数据政策过滤的evidence复制为read-only context snapshots，并记录source/member digest。Backend不能读取整个Run root，也不能把context snapshot作为workspace change返回。

## Path, Tool and Data Authority

Trusted Host 必须在 dispatch 前规范化并验证 task policy：

- 所有路径必须是 repository-relative normalized POSIX paths；拒绝 absolute path、空路径、`..`、路径逃逸和 normalization collision；
- `forbidden_paths` 优先于 read/write allowlist；write 必须同时落在 explicit `write_paths` 且不在任一 deny rule；
- symlink、hardlink、submodule、device、socket、Git metadata/ref 与 filesystem mount escape 都不能绕过 scope；
- workspace 只能修改普通文件；backend遇到unsupported file type、unexpected executable-bit change或未授权binary change时必须在落盘前安全拒绝并返回`policy_blocked`，validator实际观察到此类content时按invalid ingress处理；
- `.git`、raw data、Run outputs、accepted results、checkpoint/control records、secrets、credential files、Human responses 与 provider credentials 永远不可写；
- secrets 不挂载到 Code Agent workspace，network 默认关闭；task payload 或模型输出不能启用 network；
- tool execution使用 Host allowlisted typed argv、working directory、environment keys 和 timeout policy，禁止把自由 shell 字符串直接交给 shell；
- Code Agent 不能生成、修改或解释自己的 authorization、budget、scope 或 verification policy。

`ephemeral_paths`只允许trusted verifier写入明确的cache/temp目录；它不能与forbidden/control/data/accepted路径相交，不能由Agent扩大，必须在最终scope scan前清除，并永远不能进入change manifest或artifact bundle。

Network默认关闭约束的是workspace、tool process与verification process。Trusted Host可以按既有provider policy在sandbox外使用批准的backend transport，但不得把provider credential挂载进workspace、把通用network tool转交Code Agent或由task payload改变provider/network配置。

Repository instructions 和相关合同文档可以作为只读 evidence。Raw numeric data、accepted-result payload 或非必要敏感 artifact 默认不进入 Code Agent context；若任务确实需要新数据权限，停止并新开安全设计 ticket。

## Isolated Workspace Contract

每个Code Agent Attempt必须拥有新的`workspace_id`和独立、一次性、不可共享的workspace。Phase C首个真实实现候选使用由可信Host创建的Git worktree；只有C00证明所选backend能满足本ticket全部隔离、停止、审计和恢复合同后才能冻结具体实现。Fake可以使用deterministic synthetic workspace，但必须遵守完全相同的identity、manifest、seal与scope contracts。

### `WorkspaceManifest 0.1`

`WorkspaceManifest` 是 create-new、不可覆盖的起始合同，至少冻结：

- `schema_version`、`workspace_id`、正整数 `workspace_generation` 与 manifest digest；
- exact Run、Case、Cycle、code_agent Attempt、inbound Transition、task 与 `producer_operation_id`；
- exact `base_revision`、`base_tree_digest` 与 source runtime fingerprint；
- `coding_backend_kind`、backend version/runtime fingerprint 与 workspace implementation；
- read/write/forbidden、tool、network、filesystem 与 ephemeral policy digests；
- trusted Host 的创建时间、owner 与 dedicated workspace-root identity。

Checkpoint和bounded state只允许保存`workspace_id`与manifest digest，不保存由resume payload或Agent提供的physical path。可信Host必须通过process restart后仍可重建或读取的project-owned managed-root规则维护`workspace_id -> managed physical path`映射；该映射不能由resume payload、Backend或workspace内文件提供。每次dispatch、lookup、resume和verification前都必须确认manifest、Attempt、operation、base、policy、lease与managed root exact-match。

### Workspace lifecycle and `WorkspaceSeal 0.1`

Workspace lifecycle 的控制状态依次为：

```text
prepared -> leased -> running -> sealed -> verified -> released
```

这些状态只能由可信 Host 记录为 append-only control evidence，不能回写或覆盖原 `WorkspaceManifest`。Backend 完成或被可信Host终止后，Host 必须关闭该 operation 的写 lease并创建 immutable `WorkspaceSeal`，至少冻结 workspace/manifest/operation/backend identity、terminal backend status、final tree digest、change manifest digest、tool-audit digest、seal time 与确认不再接受 backend 写入的证据。无法证明终止和seal完整时只允许隔离该workspace并fail closed，不能把不完整seal包装成合法结果。

- workspace 从 exact `base_revision` 和 `base_tree_digest` materialize；
- 不复用前一 Attempt 的 mutable filesystem、process、module cache、untracked files、Codex thread 或 tool session；
- backend 无权写 control repository、Run artifact root、raw data、accepted results 或另一 workspace；
- scope validation比较 base snapshot 与最终 filesystem content，不能只信模型声明、backend summary或`git status`；
- seal后任何filesystem变化、workspace path替换、base drift、foreign lease或identity mismatch都使该result不可注册；
- workspace缺失或无法证明仍是exact Attempt workspace时进入A04/A05规定的rejection或`recovery_required`，不能静默重建同一Attempt并重新运行backend；
- backend workspace只作为临时证据源；主图不得把mutable path当作结果或长期source of truth。

### Conditional Phase C Codex SDK sandbox layers

Git worktree只提供repository state isolation，不单独构成安全sandbox。如果C00选择`CodexSdkBackend`，其implementation ticket必须同时使用：

- 每Attempt新的Host-owned worktree，来源为exact immutable base；
- Python Codex SDK `Sandbox.workspace_write`，workspace指向该worktree；
- Codex SDK不配置worktree之外的额外writable roots；Host-owned ephemeral verification目录只供独立trusted verifier使用，不暴露给backend；
- workspace、tool process与trusted verification process默认关闭network；
- 不向workspace挂载provider credential、secret、Run output、raw data、accepted result或checkpoint/control records；
- Host-owned path normalization、filesystem diff、scope validation、fresh verification与content digest checks。

Codex SDK sandbox preset是filesystem access policy，不替代worktree identity、Host policy、trusted verification或durable Pause。完整Agents SDK `SandboxAgent`不作为默认第一版；如果C00证明Codex SDK/Host wrapper不满足合同，必须先由新design ticket在Codex App Server、CLI/MCP、Agents Sandbox或其他backend间选择，不得在C01中静默降级。任何provider或Agents SDK run/session/recovery状态都不得成为A04之外的第二套产品Run、Pause或resume authority。

### Phase C `C00_CODEX_SDK_BACKEND_FEASIBILITY` gate

Phase C在创建真实backend implementation ticket前必须先创建、审查、批准并执行独立C00 feasibility ticket。C00使用pinned SDK/runtime版本和非生产fixture，只验证能力，不接入产品graph、不降低A05合同，至少证明：

1. Host-owned producer operation可以在进程重启后对同一provider execution执行稳定lookup，不重复dispatch；
2. 每次真实tool invocation可由SDK事件或Host wrapper可靠派生连续、完整、不可伪造的`tool_audit.jsonl`；
3. timeout/operator cancel可以终止exact operation、撤销write lease，并证明停止后没有新的process/tool/filesystem activity；
4. workspace-write只覆盖exact Attempt worktree且没有额外writable roots、credential、raw/accepted/control data暴露；
5. terminal result、dispatch receipt、usage evidence、WorkspaceSeal和content digests可以create-new持久化并在重启后exact读取；
6. unknown provider state、event缺失、result冲突和Host crash均能映射为本ticket的fail-closed outcome，不需要第二套Run/Pause/budget authority。

C00通过后，C01才能把pinned Python Codex SDK冻结为首个真实backend。任一required capability失败时，C00必须停止并记录capability matrix；随后另建design ticket选择替代backend，不能把缺失event写成0、伪造provider identity、放宽cancel/audit/workspace/result合同，或修改主图`CodingBackend` port来迁就provider。

## A04 External-result Lifecycle

Inbound Transition 先按 A02/A03 分配 `scheduled` code_agent Attempt并清除 code/downstream current artifacts。随后 control plane冻结 task，在该 Attempt `started` 之前按 A04 发布 `external_result` Pause。

Pause 必须绑定 task digest、target Attempt、`producer_operation_id`、`coding_backend_kind`、workspace manifest identity/digest、A06在`opened`前已持久化的resource reservation identity/digest、expected backend/result schema、runtime fingerprint、checkpoint、state digest及execution/artifact heads。只有可信 Host 可以调用`CodingBackend`或提交结果；Code Agent本身不能调用`resume_run`。

完整`CodeAgentTask`必须在`opened`前以create-new、不可覆盖的方式保存到Run control/audit namespace，Pause绑定其canonical path、owner与digest。它在此阶段不是A03 current `code` artifact。External result到达后，Host同样先创建immutable delivery snapshot并验证owner/path/digest，再把该snapshot reference放入`resume_run`；mutable provider response或workspace path不能直接作为resume input。

Pause期间产生的task、workspace lifecycle、dispatch receipt、seal、external result与delivery snapshot使用由Run/Pause/Attempt/operation identity确定的唯一canonical relative path和exclusive-create语义：exact bytes重复读取已有对象，不同bytes撞到同一identity/path必须conflict。它们不建立第二个mutable current index或独立head；claim preflight必须从Pause和delivery envelope验证完整的owner/path/digest闭包，orphan、missing、duplicate、cross-operation或无法闭合的evidence全部拒绝。

Dispatch/delivery 必须满足：

- 一个 Pause 只绑定一个 stable `producer_operation_id`；
- 同 operation ID、task digest与workspace manifest digest的重复 dispatch 返回同一receipt/job/result identity，不创建第二workspace execution或Codex thread；
- 同 operation ID 不同task/workspace/backend，或同Pause不同operation ID必须conflict；
- Host必须先把`BackendDispatchReceipt`以create-new方式持久化；receipt、workspace manifest/seal identity与external result digest完整后才能提交resume；
- dispatch receipt与delivery snapshot位于immutable control/audit namespace，在Pause claim前不append execution/budget record、不改变bounded graph state或A04 `opened_execution_head`；
- dispatch outcome 不确定时只能使用`CodingBackend.lookup(producer_operation_id)`确认原operation并恢复同一receipt reference，不得自动启动第二个backend operation；Run保持paused，直到exact result到达、operator显式取消，或A06后续定义的policy触发受控升级；
- backend完成后必须通过`fetch_result`取得immutable result reference并验证exact receipt、task、workspace、operation和digest，不能接受模型文本或Codex thread summary作为delivery authority；
- operation timeout、aggregate hard limit或operator取消必须通过`CodingBackend.cancel`停止exact operation并撤销写lease；`cancel_pause`本身仍遵守A04 lifecycle，不能由backend调用或替代；
- `resume_run` 只接收 immutable `CodeAgentExternalResult` snapshot/reference 与 digest，不接受 workspace path、state patch 或 route；
- claim 后崩溃、重复 delivery 与 head mismatch 完全遵守 A04，不建立 Code Agent 专用 resume/retry入口。

对尚未claim的`external_result` Pause执行`cancel_pause`时，可信Host必须先证明operation尚未dispatch，或对已dispatch operation执行幂等`cancel`、撤销write lease并持久化terminal status/seal control evidence；随后才按A04对exact `opened_execution_head`追加`cancelled`并将Run置为`halted`。Backend不能自行取消Pause。停止或lease证据不完整时不得接受result，workspace必须隔离，Run按fail-closed停止，aggregate按A06保守结算。

Resume在claim前必须完成delivery envelope的duplicate-key、schema、identity、owner、path、digest、member-shape、dispatch receipt、workspace manifest/seal和reservation/usage preflight。Claim必须对exact A04 `opened_execution_head`成功；随后在target code_agent Attempt `started`前append exact `resource_settled`。Claim后settlement失败或崩溃返回`recovery_required`，不得重新dispatch或启动target Attempt。Settlement完整后，target code_agent Attempt只`started`一次；`CodeAgentSubgraph` materialize已通过preflight的change，在fresh verifier workspace运行trusted verification/scope checks，计算canonical result，注册bundle，然后写terminal Attempt lifecycle，不再次Pause。若结果表达`needs_input`或`needs_human`，先完成当前Attempt并交给Coordinator，由Coordinator按A04建立新的`human_input` Pause。

## `CodeAgentExternalResult` and Trust Boundary

Backend 返回的 external result 是 untrusted ingress，即使来自本地 Fake、Codex SDK或签名 provider也不能直接成为 current code artifact。它至少包含：

- exact task/execution/base/workspace/producer identities 与 digests；
- exact backend kind/version、dispatch receipt、provider job/thread audit identity与digests；
- declared result status、change manifest、change blobs/patch和tool audit references；
- backend执行的verification claims、resource usage、warnings、errors与failure evidence；
- workspace seal identity/digest和result canonical digest。

Trusted `CodeAgentSubgraph`必须重新验证 schema、identity、path containment、base-to-result content、member digests、scope、authorization和budget envelope。Required verification由trusted verifier在fresh materialized workspace中重新运行；backend或Codex自报“tests passed”只能作为audit evidence，不能满足route guard。Backend实际usage超过aggregate maximum、停止后继续产生side effect或无法验证停止边界时属于control/policy failure，不得通过按maximum结算掩盖超额执行。Canonical `status`、`usable`、`failure_class`和`retryability`必须由trusted validator根据validated change、policy和verification evidence计算或约束，不能直接复制backend声明。

Malformed、duplicate-key、identity mismatch、digest mismatch、path escape或无法完整验证的external result不能注册为合法`CodeAgentResult`。这些问题在preflight发现时拒绝claim并保持原Pause；如果只有claim后才发现且无法证明结果heads完整，则按A04返回`recovery_required`，不得自动重跑Attempt。不得把invalid payload静默规范化为success、复用旧bundle或让Agent选择fallback route。

Backend若在自身边界发现内部输出无效，可以返回一个schema-valid、无usable change的`failed` envelope，并使用`failure_class = result_invalid`；该可信可归属的failure evidence经Host验证后才可形成canonical failed bundle并交给Coordinator。它与把malformed ingress规范化为合法结果不是同一行为。

## Canonical Result Status and Failure Taxonomy

合法 `CodeAgentResult.status` 只允许：

| Status | Meaning | Route eligibility |
|---|---|---|
| `success` | 非空change set通过scope、policy和全部required trusted verification | 可在全部A01 guards通过后进入Analysis Engineer |
| `no_change` | final content与base exact-equal，并有证据说明任务已满足或无安全修改 | 只能进入Decision Coordinator |
| `failed` | tool、workspace、change或verification未成功 | 只能进入Decision Coordinator |
| `needs_input` | task缺少完成所需的typed信息，且未扩大scope | 只能进入Decision Coordinator |
| `needs_human` | 需要新的approval、scope或高影响决定，且未执行未授权修改 | 只能进入Decision Coordinator |
| `budget_exhausted` | A06 budget envelope阻止继续执行 | 只能进入Decision Coordinator |
| `policy_blocked` | backend在产生违规change之前安全拒绝了违反policy/scope的请求 | 只能进入Decision Coordinator |

不定义模糊的`partial_success`。只要change非空但required verification失败或不完整，结果就是`failed`；change evidence可以保留为audit-only，但`usable=false`且不能进入Analysis。

`policy_blocked`只表示安全的pre-change拒绝。External payload实际包含out-of-scope member、path escape、forbidden target或其他违规filesystem content时属于invalid ingress：不注册canonical code artifact；claim前只记录control rejection evidence并保留Pause，claim后无法形成完整validated heads时按A04进入`recovery_required`。

`scope_violation`与`policy_violation` failure class在canonical `CodeAgentResult`中只允许描述已验证的pre-change `policy_blocked`拒绝或无违规content的安全失败。若external result或workspace实际含违规content，这两个label只能作为control rejection audit reason，不能把invalid ingress规范化、注册或路由为合法failed bundle。

Result还必须包含typed `failure_class`：

```text
none | task_invalid | base_mismatch | workspace_setup | tool_error |
verification_failed | scope_violation | policy_violation |
dependency_unavailable | timeout | external_interruption |
no_safe_change | result_invalid
```

以及 advisory `retryability`：

```text
not_retryable | new_attempt_allowed | new_evidence_required | human_required
```

`recommended_action` 只能是 bounded advice，不能提交 Transition。是否re-review、analysis rerun、code fix、replan、Human Gate或terminal仍由Decision Coordinator依据A01/A06决定。A06负责failure fingerprint、重复失败和剩余预算；A05只提供稳定的diagnostic inputs与usage evidence。

## Canonical Code Artifact Bundle

每个完成验证的 code_agent Attempt注册一个 A03 `code` slot artifact，`artifact_id = <attempt_id>:code`，canonical root位于该Attempt namespace。Bundle schema `0.1` 固定包含：

- `code_agent_task.json`：实际执行的immutable task snapshot；
- `code_agent_result.json`：唯一authoritative structured outcome；
- `backend_dispatch_receipt.json`：producer operation、backend、provider job/thread与dispatch identities；
- `workspace_manifest.json`：immutable base/workspace/backend/policy creation contract；
- `workspace_seal.json`：final tree、change/tool-audit digests与closed write lease evidence；
- `change_manifest.json`：按path排序的change entries；
- `verification_results.json`：task中每个required spec的trusted result；
- `tool_audit.jsonl`：经过redaction的bounded backend tool audit；
- `changes.patch`：仅在change manifest非空时存在，并与manifest/blob digests交叉校验。

`tool_audit.jsonl`由backend wrapper而不是模型文本生成。每个真实tool invocation使用从1连续的`tool_event_index`，并绑定task/workspace/tool identity、typed argv digest、cwd、start/end、status、affected paths、bounded output digest和resource usage；缺失、重复、乱序或identity变化使result无效。零tool-call outcome允许空audit file，但其digest仍必须被result引用。C00 feasibility ticket必须先验证候选backend能够提供或由Host wrapper可靠派生该合同；无法满足时停止，不得降低trusted audit或伪造缺失events。

每个 change entry 至少冻结 normalized path、`added | modified | deleted`、before/after SHA-256、file mode和content/blob identity。Member path、digest、size、status-required member set与producer Attempt必须由A03 registry验证。`code_agent_result.json`必须引用task、backend receipt、workspace manifest/seal、change、verification和tool-audit digests，但不自引用整个bundle digest。

`success`要求non-empty manifest、present patch、全部required verification passed、无scope/policy violation并设置`usable=true`。`no_change`要求empty manifest、absent patch、base/final tree exact-equal且`usable=false`。其他状态可保存非空change evidence，但必须`usable=false`；A03 current只表示最新evidence，不代表可执行或已接受。

Artifact pointer `status`必须exact等于canonical `CodeAgentResult.status`。Pointer dependencies继续遵守A03：至少包含当时current plan；需要Human authorization时，额外绑定其exact protected Human Response snapshot artifact ID。被code-fix Transition清除的历史diagnostic artifacts保留在task context references中，不能重新成为current dependency。

Human-readable summary可以作为derived member或projection，但routing只能读取validated `code_agent_result.json`。External ingress snapshot、mutable sandbox和legacy `code_change_summary.md`/`tests_status.json`都不能冒充canonical Code Agent bundle。

## Bounded State Projection

Phase B为canonical Code Agent增加以下bounded nullable state fields：

```text
code_agent_task_path
code_agent_result_path
code_change_manifest_path
code_verification_results_path
code_agent_status
code_agent_usable
```

它们只在canonical `code` bundle注册后设置，并必须与current pointer、member paths及structured result exact-match；不保存mutable workspace path、patch content、tool transcript或完整verification logs。Code invalidation必须原子清空全部canonical Code Agent fields。

Legacy `code_change_summary_path`和`tests_status_path`继续存在但不与新字段混用。Future code-slot state-path policy对两类producer使用同一完整nullable path-key set：`legacy_codex_handoff`只填legacy paths，`code_agent`只填canonical paths，另一组必须显式为null；`code_agent_status`与`code_agent_usable`作为独立bounded scalars交叉验证。无current code pointer时，两组paths和两个scalars全部显式为空。

## Trusted Verification Contract

每个 `VerificationSpec` 至少冻结 stable ID、typed argv、repository-relative cwd、timeout policy、required flag、expected exit codes与environment allowlist。每个result status只允许`passed | failed | blocked | timeout | not_run`。Phase B implementation可以先支持有限command registry，但不能把task中的自由文本作为shell执行。

Trusted verifier必须：

- 在exact base加validated change set的fresh workspace运行；
- 对每个required spec产生exactly one result；
- 记录command identity、exit/timeout/blocked status、bounded stdout/stderr digest和produced-file evidence；
- 对日志执行secret/path redaction，不能把credential或raw sensitive content写入artifact；
- 运行结束后清除Host-owned ephemeral paths，再次执行content manifest与scope check，捕获测试产生的未授权持久文件；
- 对missing、duplicate、skipped、blocked、timeout或non-passing required result判定verification不通过。

只有`success` candidate必须实际运行全部required specs。对`needs_input`、`needs_human`、`budget_exhausted`或safe pre-change `policy_blocked`等提前停止结果，每个未执行spec仍须记录`not_run`和typed reason，不能缺失或伪装为passed。

Agent自行选择的exploratory commands只进入tool audit，不能替代required verification。Verification通过也只证明task-level engineering checks，不代表科学有效、风险批准、patch promotion或accepted memory。

## Approval and Promotion Boundary

Coordinator/trusted policy layer在dispatch前决定task是否可自动执行。以下类别至少需要预先存在、single-use且与task digest exact绑定的Human authorization，或由更高层policy直接禁止：

- dependency/lockfile、build/release、CI、provider或network policy变化；
- security、permission、sandbox、checkpoint、control API或graph topology变化；
- execution/state/artifact schema与accepted-result policy变化；
- 可能改变科学方法、fit/model选择、默认物理参数或结论解释的实现变化；
- 超出常规低影响source/test/docs修复的其他高影响change class。

Human authorization不能覆盖always-forbidden data、secret、Git history或accepted-result边界。若执行中发现必须扩大scope或改变risk class，Code Agent必须停止并返回`needs_human`，由Coordinator创建新Human request；批准后创建新的code_agent Attempt和新task。旧Attempt不能在结果生成后获得追溯性授权。

即使`success`，主图也只获得一个Run-local immutable code evidence bundle。它可以在fresh Analysis environment中被验证使用，但不得自动写回control repository、创建commit、merge、push、发布或改变accepted status。Patch promotion需要未来独立、Human-authorized implementation/workflow ticket。

## A01 Route Guards

`code_agent -> analysis_engineer`只允许同时满足：

- producing Attempt、Transition、task、Pause、external result与A03 code artifact identity exact-match；
- result status为`success`且`usable=true`；
- base/runtime、change member、scope、policy、authorization和全部trusted verification有效；
- current plan/code pointers与scheduled Analysis Attempt dependencies符合A03；
- A06 budget/duplicate-failure guard允许继续；
- 没有`needs_human`、policy violation或head mismatch；需要Human authorization时，其exact scope已由该task/Attempt合法单次消费，且没有复用或越权。

所有其他valid result进入Decision Coordinator。Invalid ingress在claim前拒绝，claim后不确定性按A04进入`recovery_required`；只有schema-valid且可归属的`failed/result_invalid` result可以形成failed bundle后进入Coordinator。Code Agent不允许自行选择Analysis、rerun、replan、Human Gate或END。

Code fix保持同Run/Cycle并创建新的code_agent Attempt。成功后创建新的Analysis Attempt，旧code及下游artifacts按A03失效；Code Agent永远不能覆盖旧canonical bytes或复用旧Attempt bundle。

## Verified Code Bundle to Fresh Analysis

`success` Code Agent result不能直接让当前control process加载或执行backend workspace中的代码。只有canonical Code Bundle完整注册、成为A03 current `code` pointer且全部execution/artifact heads重新验证后，source wrapper才可以在pure route selection与A06 admission通过后提交`code_agent -> analysis_engineer` Transition。

固定交接顺序是：

```text
trusted verification succeeds
-> canonical Code Bundle registers and becomes current code
-> route guard validates exact current plan/code heads
-> commit_transition preallocates the new scheduled Analysis Attempt
-> A03 clears analysis and downstream current slots for that exact target
-> code_agent -> analysis_engineer Transition record commits with that exact target
-> Host creates immutable AnalysisExecutionSpec
-> Host materializes fresh Analysis worktree from exact base + verified change
-> Host verifies expected effective tree digest
-> Analysis Attempt starts in a new subprocess
-> Analysis artifact depends on the exact Code Bundle
```

### `AnalysisExecutionSpec 0.1`

Host-owned spec使用deterministic `analysis_execution_spec_id = <target_analysis_attempt_id>:analysis_execution_spec`；fresh workspace identity同样从target Attempt和spec identity确定，不能由resume payload、Agent或physical path选择。Spec至少冻结：

- `schema_version`、spec ID/digest、Run/Case/Cycle、target Analysis Attempt与inbound Transition；
- source code_agent Attempt、current code artifact ID、bundle/member digests与producing task；
- exact base revision/tree、change manifest/patch digest与expected effective tree digest；
- current plan和其他selected input artifact IDs/digests；
- analysis runtime fingerprint、environment policy、allowed command/entrypoint与expected outputs；
- fresh Analysis workspace ID/manifest digest；physical path不得进入spec或bounded state。

Spec在目标Analysis Attempt`started`前以create-new方式写入该Attempt的control/audit namespace。Exact重复必须得到同一canonical bytes；同identity不同bytes必须conflict。它不是新的current artifact，也不能修改已提交Transition。Spec publication和workspace preparation是trusted pre-start control steps：必须先验证scheduled target与唯一inbound Transition，不创建额外Attempt/Transition、不执行repository code、不写domain artifact，也不把target标为`started`。Analysis Host必须从同一base重新materialize并应用exact verified content-addressed change，不能复制mutable Code Agent workspace、读取control repository当前文件、继承Codex process/module cache或使用Python module reload。

Analysis注册的artifact必须依赖exact source Code Bundle；base、patch、effective tree、runtime、Transition、Attempt或current head任一不一致均不得启动或注册Analysis结果。

失败边界固定为：

- Code Bundle已注册但outbound Transition尚未提交：保留current code，验证heads后继续正常route commit，不重跑backend；
- Transition已提交但spec或Analysis workspace尚未materialize：保持target Attempt为`scheduled`，按deterministic spec/workspace identity幂等创建，不重新提交Transition；
- Analysis启动前发现code/artifact head、spec、workspace或effective tree不一致：返回`recovery_required`或按完整性政策`halted`；旧target不得启动、自动abandon或被retarget，同一source Attempt不得提交第二条outbound Transition，原Run不再自动继续；只有满足A04 source validation时才允许operator显式replay/fork到新Run；
- Analysis subprocess已运行但artifact未完整注册：不得根据process exit或文件存在声称成功，按A02/A04 recovery与Attempt lifecycle处理。

Patch promotion与fresh Analysis execution是不同操作。Analysis可以消费Run-local verified bundle，但A05不允许把该patch自动写回control repository、commit、merge、push或发布。

## Fake Backend Contract

`FakeCodingBackend`与任何通过C00的真实backend必须接收相同`CodeAgentTask`和`WorkspaceManifest`，实现相同`dispatch`/`lookup`/`fetch_result`/`cancel`语义，并产生相同`BackendDispatchReceipt`、`WorkspaceSeal`与`CodeAgentExternalResult` schemas；Fake不能通过直接patch graph state、跳过A04 Pause、伪造trusted verification、写canonical bundle或直接构造Analysis state来获得捷径。

Fake fixtures由scenario ID选择，scenario只能由test harness/trusted Host配置，不能由Agent task自由文本触发。每个fixture必须有固定base、workspace manifest/seal、dispatch receipt、change members、digests、tool audit、usage和declared outcome，并经过同一个production backend port、ingress validator、trusted verifier、artifact registration与fresh Analysis materialization path。

A07至少为Fake backend冻结以下scenario classes：

- valid `success` scoped change；
- `no_change`；
- tool/workspace `failed`；
- required verification failed、blocked和timeout；
- `needs_input`、`needs_human`和`budget_exhausted`；
- safe pre-change `policy_blocked`，以及实际scope/path/symlink violation导致的invalid ingress；
- malformed/duplicate-key、wrong Attempt/task/base/workspace/result digest；
- external dispatch/delivery duplicate、conflict和claim后崩溃；
- aggregate hard limit、operation timeout、operator cancellation、duplicate/conflicting cancel与停止后activity；
- missing/tampered/reused workspace、foreign lease、base drift与seal后filesystem变化；
- verified bundle到fresh Analysis的spec、patch、effective tree、runtime或head mismatch；
- change存在但verification不完整，确认不能作为partial success进入Analysis。

## Legacy Compatibility

当前`legacy_codex_handoff`、`coder_task_packet.yaml`、`code_change_summary.md`与`tests_status.json`继续保持原合同。A05不迁移历史Run、不把legacy artifact转换为schema `0.1` Code Agent bundle，也不让legacy physical node产生canonical `code_agent` Attempt。

Canonical Code Agent只允许出现在实现A04 Pause lifecycle的新Run中：本ticket冻结时的基础版本为execution schema `0.3`，A06定义的`0.4`是保留该Pause合同的明确后继版本；其他未知或不支持版本fail closed。不能向pre-A04或正在运行的legacy Run附加code_agent Attempt；符合A04 source validation时，只能显式replay/fork到新child Run后使用新合同。

Phase B product topology可以在显式implementation ticket中选择保留legacy route作为compatibility path或停止新Run使用它，但不得静默让两套result contract共享同一个route guard。

## Downstream Contract Boundaries

- A06定义budget ownership、具体envelope、failure fingerprint、重复失败与stop policy；不得改变A05 status含义或把budget exhaustion当success；
- A07把A01 routes、A04 Pause与本ticket Fake backend scenarios映射为deterministic Phase B acceptance matrix，并把`CodeAgentSubgraph + FakeCodingBackend`作为B03目标；
- Phase B implementation tickets实现`CodeAgentSubgraph`、完整`CodingBackend` port、`FakeCodingBackend`、deterministic workspace/seal manager、schema validator、artifact bundle、A04 integration，以及真实fresh worktree/subprocess的Analysis handoff harness；
- Phase C先执行`C00_CODEX_SDK_BACKEND_FEASIBILITY`；只有全部required capabilities通过后，后续C01才实现pinned Python `CodexSdkBackend`与Code Agent Attempt worktree/sandbox integration，并复用Phase B已经验收的fresh Analysis materialization/subprocess合同；
- C00不通过时由新design ticket选择Codex App Server、CLI/MCP、完整Agents SDK `SandboxAgent`或其他backend；remote/container/hosted provider和snapshot session不得在C01中顺带引入；
- patch promotion、repo mutation、PR/merge/deploy必须另开未来ticket，不属于A05–A07执行。

## Deliverables

- versioned Code Agent task/external-result/result schemas；
- `CodeAgentSubgraph`、`CodingBackend` port、A04 Pause与Attempt lifecycle合同；
- `WorkspaceManifest`、`WorkspaceSeal`、backend receipt、sandbox、path/tool/data、authorization和immutable base invariants；
- content-addressed code artifact bundle与trusted verification合同；
- verified Code Bundle到`AnalysisExecutionSpec`和fresh Analysis subprocess的交接合同；
- structured outcome/failure/retryability taxonomy与A01 route guards；
- Fake backend scenario inventory；
- 对A06、A07和Phase B/Phase C implementation tickets的明确输入；
- 核心source-of-truth文档更新和独立A05 completion record。

## Acceptance Criteria

- `CodeAgentSubgraph`拥有控制生命周期，Fake与任何通过C00的真实backend可以在不修改主图routing、Pause、task/result schema或artifact contract的情况下替换；
- subgraph pre-start control stages不领取target Attempt，`consume_code_agent_result`只在Pause claim与settlement后把同一scheduled Attempt启动一次；
- canonical code_agent Attempt与legacy handoff严格分离，全部identity与A02/A03/A04 heads exact绑定；
- 每次真实执行使用新的immutable-base worktree、`WorkspaceManifest`与`WorkspaceSeal`，不接触control repository或另一Attempt workspace；
- 若C00选择Python `CodexSdkBackend`，它必须使用`Sandbox.workspace_write`、无额外writable roots且默认关闭workspace network；SDK选择本身不能替代C00对lookup/cancel/tool-audit/restart能力的证明；
- 主图只消费validated content-addressed bundle，不消费mutable workspace或Markdown声明；
- external dispatch/delivery、Pause claim和进程崩溃均single-operation且fail closed；
- aggregate hard limit、operation timeout与operator cancellation由可信Host通过exact `cancel`强制执行；Backend不能超额后只靠usage report结算，也不能取消Run/Pause；
- backend result只有在fresh trusted workspace验证后才能注册，registered bundle只有通过`AnalysisExecutionSpec`在新worktree/subprocess中执行；
- scope/path/symlink、policy、authorization、digest或trusted verification任一失败都不能进入Analysis；
- `success`以外的所有valid status进入Coordinator，invalid ingress不能注册为成功artifact；
- change加tests通过不等于科学接受、repo promotion或accepted memory；
- task发现需要扩权时创建新Human authorization与新Attempt，不追溯批准旧change；
- A06/A07及后续实现无需自行发明另一套Code Agent lifecycle或result taxonomy。

## Required A07 and Implementation Scenarios

A07和后续implementation tickets至少必须覆盖：

- `A05-CODE-001`：Method Planner implementation gap和Coordinator code fix两种task origin；
- `A05-CODE-002`：process退出后的external Code Agent result准确恢复一次；
- `A05-CODE-003`：external operation在Pause `opened`前reserve，dispatch/delivery不改变`opened_execution_head`，claim后settlement必须先于target `started`；
- `A05-CODE-004`：pre-start control stages重复进入时task/workspace/reservation/Pause exact幂等，且不产生target `started`、backend dispatch或code artifact；
- `A05-CODE-005`：same operation/task重复dispatch、conflicting dispatch、same delivery重复resume和竞争claim；
- `A05-CODE-006`：dispatch状态不确定时`lookup`返回running/completed/unknown且绝不创建第二operation；known operation必须返回同一receipt reference/digest并支持receipt publication崩溃恢复，unknown不得伪造receipt；
- `A05-CODE-007`：operation timeout、aggregate hard limit和operator cancellation通过同一`cancel`port停止exact operation、撤销write lease且不创建替代operation；
- `A05-CODE-008`：process在dispatch receipt、backend completion、result snapshot、Pause claim、settlement、bundle registration各边界退出；
- `A05-CODE-009`：success result通过`AnalysisExecutionSpec`进入fresh Analysis Attempt，plan/code dependencies和A03 invalidation正确；
- `A05-CODE-010`：no-change、failed、needs-input、needs-human、budget-exhausted、policy-blocked全部进入Coordinator；
- `A05-CODE-011`：backend自报pass但trusted verification failed/blocked/timeout时拒绝Analysis；
- `A05-CODE-012`：out-of-scope file、path escape、symlink escape、Git metadata、secret/raw/accepted/control target拒绝；
- `A05-CODE-013`：wrong Run/Case/Cycle/Attempt/Transition/task/base/workspace/pause/result/member digest拒绝；
- `A05-CODE-014`：missing/tampered/reused workspace、foreign lease、base drift、path swap与seal后filesystem变化拒绝；
- `A05-CODE-015`：Code Bundle已注册但Transition未提交、Transition已提交但Analysis workspace未创建的幂等恢复；
- `A05-CODE-016`：Analysis spec、patch、effective tree、runtime或current head mismatch时旧target不启动、不自动abandon、不retarget、不从同一source提交第二条outbound Transition且不读取control repository；原Run只进入`recovery_required`/`halted`边界；
- `A05-CODE-017`：non-empty unverified change不能伪装partial success；
- `A05-CODE-018`：Human授权scope/digest错误、已消费授权或执行中扩权全部fail closed；
- `A05-CODE-019`：multiple code attempts使用独立workspace和artifact，旧code/downstream不再current但canonical bytes保留；
- `A05-CODE-020`：Fake与future real backend contract fixtures通过同一`dispatch`/`lookup`/`fetch_result`/`cancel` port、validator、verification、registration和fresh Analysis入口；
- `A05-CODE-021`：legacy handoff不能被读取为canonical Code Agent result。

## Pre-freeze Review Gate

本ticket从`review`提升为`ready`前必须确认：

- YAML保持`status: review`，直到A02C01与A04–A07完成交叉审查、catalog核验并获得用户最终确认；
- 本ticket不含未决设计问题、占位符或内嵌执行记录；
- A04的Pause/external-result合同与本ticket的dispatch、delivery和claim语义一致；
- A06/A07未引入第二套Code Agent budget status、Fake contract、Pause delivery或route authority，并完整保留本ticket的required scenarios；
- A07明确把`CodeAgentSubgraph + FakeCodingBackend`作为Phase B目标，Phase C边界明确为`C00 capability gate -> selected RealCodingBackend + Attempt worktree + fresh Analysis subprocess`；
- dependency、Allowed Files与Do Not Touch无冲突，所有相对Markdown links和Read First仓库路径有效；
- Phase Overview、`docs/README.md`与`docs/REPO_CURRENT_STATE.md`一致将A02C01与A04–A07标为`review`；
- review diff不包含runtime、test、dependency、provider configuration或sandbox implementation改动。

## Verification

执行本design ticket时只运行静态、文档与scope检查：

```bash
git diff --check
```

还必须验证：

- ticket在`ready`之后只变更YAML lifecycle metadata，正文与执行前冻结commit一致；
- A04及本 ticket的其他dependencies已`completed`，A06/A07正文未修改；
- Required Documentation Updates已同步，并明确区分“已确认的A05目标合同”与“尚未由Phase B/Phase C实现的Code Agent能力”；
- Phase Overview、Docs Index与Current State一致记录A05完成及A06/A07的当时lifecycle状态；
- `docs/tickets/completions/A05_COMPLETION.md`已建立并加入completion index；
- Allowed Files/Do Not Touch与实际diff一致，所有现行Markdown relative links有效；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`和accepted artifacts没有本ticket产生的diff；
- 不运行runtime、benchmark或live-provider测试，因为本ticket只冻结设计合同。

## Stop Conditions

- 需要改变A01 route authority、A02 identity、A03 artifact/accepted-result或A04 Pause合同；
- 无法在不改变主图合同的情况下实现`CodeAgentSubgraph + CodingBackend`两层边界；
- A05设计执行本身要求在C00之前把Python Codex SDK或其他provider固定为真实backend；
- C00未通过却要求继续实现Codex SDK、降低required workspace/idempotency/hard-limit/termination/tool-audit/result/restart合同，或在没有新design ticket时静默改用其他backend；
- A05设计执行本身要求安装dependency、选择具体Codex model/version、修改provider credential或部署生产基础设施；
- 无法把external execution限定在Attempt-isolated workspace；
- 无法从verified Code Bundle在fresh worktree/subprocess中启动Analysis，或必须通过module reload/当前control repository执行新代码；
- 必须让Code Agent修改control repository、Run output、raw data、accepted result、secret或Git history；
- 必须信任Agent自报tests/scope而无法执行独立验证；
- 必须复用mutable workspace、old result或旧Human authorization；
- 需要自动commit、merge、push、deploy或追溯批准out-of-scope change；
- 实现工作无法拆入独立Phase B/Phase C implementation ticket。

遇到以上任一条件时停止执行并新开corrective/design ticket，不修改本ticket已冻结正文。

## Required Documentation Updates

- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/AGENT_ROLES_AND_BOUNDARIES.md`
- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`
- `docs/tickets/completions/A05_COMPLETION.md`
- `docs/tickets/completions/README.md`
