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
- [`Control Protocol 0.4`](CONTROL_PROTOCOL_0_4.json)
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
- 以tracked [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)作为ExternalOperation phase/status/resolution graph、single final-evidence mapping、CAS guards、pre-start dependency DAG和field binding的唯一机器可读枚举；
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

A04通用Attempt execution lease只约束结果消费、verification与domain artifacts。Pre-start workspace/Backend由机器`external_prestart_authority`授权：绑定committed Code Agent target authorization、immutable core、current external epoch与Run closure revision，并拒绝冲突stop owner；dispatch另要求public paused checkpoint。该scope不能兑换Attempt lease或提前写started。

`CodeAgentSubgraph` 是控制意义上的 graph-managed lifecycle，不表示 Codex 工具循环成为 graph event，也不允许 SDK 修改 graph state。它在 A04 safe boundary 内协调的第一版顺序固定为：

- `prepare_external_operation`与`wait_external_result`是trusted deterministic control stages，不是Agent/work Attempt，不分配新的Attempt kind，也不得写target `started`；
- `consume_code_agent_result`是唯一映射canonical `attempt_kind = code_agent`和physical `node_name = code_agent`的work stage，只能在Pause claim、A06 settlement、`pause_consumed`、`run_lifecycle(paused -> running)`与resume checkpoint完整后领取scheduled target Attempt；
- internal control stages只能写A04/A06允许的checkpoint、reservation、Pause与immutable control/audit evidence，不能产生code artifact、执行backend工具循环或绕过A02 target consumption。

```text
inbound Transition allocates scheduled code_agent Attempt
-> trusted Host reserves ExternalOperation identity, workspace identity, and initial lease_epoch
-> CodeAgentSubgraph validates and freezes CodeAgentTask bound to producer_operation_id
-> trusted Host publishes WorkspaceManifest without materializing the workspace
-> A06 admits and reserves the aggregate against task and manifest digests
-> trusted Host commits the immutable ExternalOperation core
-> trusted Host materializes the isolated workspace under the current external-operation epoch
-> A04 opens external_result Pause
-> trusted Host dispatches CodingBackend outside the replayable graph node
-> backend returns immutable CodeAgentExternalResult evidence
-> resume_run atomically claims the Pause
-> A06 settles the exact reservation before the target Attempt starts
-> append pause_consumed, run_lifecycle(paused -> running), and resume checkpoint
-> code_agent Attempt starts once
-> CodeAgentSubgraph validates, verifies and registers CodeAgentResult bundle
-> code_agent Attempt finishes with structured outcome
-> A01 guard routes to Analysis Engineer or Decision Coordinator
```

任何可能由 LangGraph resume 重新进入的节点都不得在 Pause `opened` 发布前启动 backend、创建第二个编码 operation 或执行其他不可安全重放的外部副作用。Backend dispatch只能由可信Host在图已安全暂停后完成，并通过stable、Host-owned `producer_operation_id`幂等化；该字段就是项目权威backend operation identity，不由provider job/thread ID派生或替代。

Pause前的producer operation stub、task snapshot、WorkspaceManifest、resource reservation、immutable core、workspace materialization与Pause publication同样必须使用Attempt/operation-bound create-new identities幂等执行：exact重复返回已有identity和digest，不同内容撞到已有identity必须conflict。它们不能依赖只存在于当前Python进程的临时状态，也不能在ExternalOperation identity与initial epoch持久化前创建workspace bytes。

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
- `cancel`只能作用于exact existing operation，必须幂等撤销workspace写lease并由Host终止其dedicated process/runtime及全部descendant process/tool；它不能创建替代operation、修改Run/Pause lifecycle或伪造完成结果；
- `BackendDispatchReceipt`至少绑定Host-owned producer operation、task、workspace、backend kind/version、nullable provider operation/thread references、dispatch status与canonical digest；
- `BackendOperationStatus`只允许`accepted | running | completed | failed | cancelled | unknown`，并绑定operation/backend identity与查询时间；除`unknown`外必须引用原`BackendDispatchReceipt`，`unknown`必须显式使用null receipt且表示不能证明原operation状态，不授权再次dispatch；
- provider job/thread identity只在candidate backend实际提供且C00证明可稳定恢复时记录；不适用或不可证明时必须显式为null，不能伪造synthetic provider identity。Fake只需稳定的Host-owned producer operation identity；
- provider job ID、Codex thread ID或其他provider reference只属于backend audit evidence，不能代替Run、Cycle、Attempt、Transition、Pause、reservation或producer operation identity；
- `FakeCodingBackend`和任何通过C00的真实backend必须通过相同port、ingress validator、trusted verifier与registry path，不能建立provider-specific route或resume API。

### Durable `ExternalOperation 0.1`

每个`producer_operation_id`必须先在A02C01同一`control_operations.sqlite`的project-owned external-operation authority中占用，不能仅存在于Backend、provider或Run-local receipt。Logical record至少冻结：

```text
producer_operation_id
parent_control_operation_id (nullable)
run_id / cycle_id / attempt_id
pause_id (nullable until pause_prepared) / pause_binding_digest
workspace_id / managed_workspace_locator_digest
task_digest (nullable until task_committed)
workspace_manifest_digest (nullable until workspace_manifest_committed)
reservation_id / reservation_digest (nullable until reservation_committed)
backend_kind / backend_version
operation_contract_digest (nullable until core_contract_committed)
operation_status / operation_phase / phase_revision
resolution_owner (nullable, single-assignment normal | cancel | interrupt)
worker_owner_id / worker_lease_expires_at / lease_epoch
hard_deadline / cancel_intent / cancel_reason
dispatch_receipt_reference / dispatch_receipt_digest
provider_operation_reference
result_reference / result_digest / workspace_seal_digest
last_observed_status / last_observed_at
terminal_evidence_reference / terminal_evidence_digest
proof_kind (nullable until final safe_stop | unavailable)
quarantine_reference / missing_proof_dimensions
```

`operation_status`固定为`reserved | active | stop_requested | completed | failed | cancelled | interrupted | recovery_required`。`completed | failed | cancelled | interrupted | recovery_required`只允许出现在唯一terminal phase `external_final_evidence_committed`且不可逆；`cancel_intent_committed | interrupt_stop_intent_committed | termination_evidence_committed`均为`stop_requested`。Exact、预计算且无副作用的publication suffix保持原non-terminal status并使用`materialization_pending` observation，不得进入`recovery_required`后继续。`last_observed_status`使用上节独立的Backend status enum；provider `unknown`不能把ExternalOperation改回reserved或授权dispatch。

ExternalOperation使用两阶段identity/core publication消除task、workspace、reservation与producer identity之间的创建环。第一笔external-operation authority transaction只执行`external_operation_reserved`：可信Host分配并持久化`producer_operation_id`、Run/Cycle/Attempt、backend/deadline policy、`workspace_id`、managed workspace locator digest、initial owner和`lease_epoch`，同时将task、manifest、reservation、core和Pause字段显式保存为null。该stub已经是workspace创建的唯一fencing authority，但尚不授权materialize workspace、创建Pause或dispatch。

ExternalOperation exact phase enum、normal/cancel/interrupt success edges、phase-to-status mapping、authority、effect class、continuation policy、CAS guards和required evidence只由tracked [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)定义；本ticket不再维护可漂移的第二份phase graph。语义上normal path仍是`external_operation_reserved`预留identity/epoch，随后冻结task、manifest、reservation和immutable core，materialize workspace并绑定Pause，只有public paused checkpoint完成后才授权dispatch。Normal、cancel和interrupt最终都收敛到唯一`external_final_evidence_committed`；intent或termination observation都不是terminal proof。

Design-time validator必须证明该联合success graph无环、所有phase可达、每个nonterminal phase都有穷尽successor且只能终结于唯一final phase；所有multi-successor work phase必须使用machine-readable guard，且每个terminal tuple的typed consumer必须属于其声明的ControlOperation graph。唯一允许的domain-flow consumer是机器白名单中的`normal + safe_stop` canonical result delivery；任何`unavailable`都必须进入可验证的cancel或interrupt terminal tail；normal candidate unavailable只进入`resolve_external_interrupt`图，不能用自由字符串绕过Pause/Run ownership。Validator还必须枚举normal/cancel/interrupt CAS在每个适用phase的交错，证明恰好一个winner，interrupt获胜后cancel不能取得Pause/Run ownership；`recoverable_timeout`只在dispatch后的两个可中断phase合法。Pre-start dependency DAG继续证明producer/workspace identity先于task/manifest/reservation引用，immutable core先于physical workspace，Pause identity先分配再绑定，public paused checkpoint先于dispatch。

`CodeAgentTask`引用已存在的`producer_operation_id`和允许该route的A06 BudgetDecision；`WorkspaceManifest`再引用task与同一producer/workspace identity，但此时physical workspace仍不存在。A06 aggregate reservation随后绑定exact task和manifest digests。`core_contract_committed`使用current external-operation epoch和phase revision执行一次性CAS，填入task、manifest、reservation references/digests并计算immutable `operation_contract_digest`；此后这些字段不可变。只有core commit后，current epoch worker才能按manifest materialize workspace并提交`workspace_materialized`。这条DAG不允许先创建task/workspace/reservation再补建producer operation，也不允许physical workspace早于durable epoch owner或immutable core。

Status与phase映射固定为：`external_operation_reserved`到`pause_bound`使用`reserved`；`dispatch_authorized`到`result_reference_committed`使用`active`；两个stop intent与termination observation使用`stop_requested`；只有`external_final_evidence_committed`使用terminal status。该final phase必须保存`resolution_kind`、`interrupt_disposition`、`proof_kind`、proof classification timing、termination或typed `not_dispatched`、write-lease revocation、containment `verify_empty`、bounded drain、post-stop stability及适用的quarantine/missing-proof evidence。机器proof classifier规定：termination必须confirmed或为typed `not_dispatched`且其他四维全部true才能使用`safe_stop`；任一维度false、unknown或missing时`unavailable`优先。Normal finalization的classifier先在normal contender request中生成candidate proof与digest：只有request-owned `safe_stop` candidate可执行normal terminal CAS并原子提交`normal + safe_stop -> completed | failed`；发现`unavailable`时不修改ExternalOperation公共字段且不得取得normal owner，而要确定性创建或复用`resolve_external_interrupt/integrity_failure`，以`normal_finalization_unavailable`为typed reason争用空resolution owner。Cancel/interrupt在各自intent CAS获胜后执行stop，随后在final evidence前分类；`cancel + safe_stop`映射`cancelled | failed`，`interrupt + safe_stop`映射`interrupted`，cancel/interrupt的`unavailable`只映射`recovery_required`。产品Run/route结果由A04的typed consumer决定，不能从ExternalOperation status直接推导。

`pause_id`与`pause_binding_digest`在`pause_prepared`前保持null；不得预占或推测A04尚未分配的Pause identity。A04 append `pause_prepared`后，coordinator必须用current external-operation `lease_epoch`和phase revision执行一次性CAS，把该row推进到`pause_bound`并绑定exact `pause_id`、prepared event identity/digest与reservation；同值重放读取原binding，不同Pause或digest冲突。`pause_opened`绑定该closure，dispatch在完整public paused checkpoint前仍被禁止。动态owner、epoch、observation与terminal evidence不进入immutable core contract digest。

ExternalOperation row与ControlOperation、Pause owner和Run terminal owner位于A02C01同一`coordinator_sqlite`物理事务域。`resolution_owner = normal | cancel | interrupt`为nullable single-assignment field：normal final CAS、cancel-intent CAS和interrupt-intent CAS都比较exact `external_operation_id + phase_revision + lease_epoch + resolution_owner IS NULL`并递增revision；normal CAS还比较normal finalization request自有的`normal_candidate_digest`，且只接受其candidate proof为`safe_stop`，并与terminal final evidence原子提交；candidate不得写入共享ExternalOperation work state。Normal final与cancel/interrupt intent谁先提交谁获胜；失败者只能读取winner，不能改写resolution或重开另一terminal branch。A04 `cancel_arbitrated`把Pause/Run owner CAS与条件性的cancel-intent CAS放进同一write transaction，从根源消除ownership后分类窗口；normal candidate unavailable不写resolution owner或共享proof字段，而是确定性创建或复用`integrity_failure` contender，由它以`interrupt_intent`竞争CAS，因此不存在`normal + unavailable` winner。

Cancel winner固定执行`cancel_intent_committed -> termination_evidence_committed -> external_final_evidence_committed`；interrupt winner固定执行`interrupt_stop_intent_committed -> termination_evidence_committed -> external_final_evidence_committed`。从未dispatch时termination保存typed `not_dispatched`，但final仍必须证明没有active lease/process/post-stop activity。若能够证明完整停止，final使用`safe_stop`；若lookup/cancel/containment后仍无法证明termination、lease revocation或stability，final使用`unavailable`、保存quarantine及缺失proof维度并终止为`recovery_required`。它不得停在旧nonterminal phase上携带terminal status，也不得在terminal后继续cleanup。`dispatch_authorized`必须先于Backend调用；调用结果不确定时只lookup原operation，绝不redispatch。

该record是dispatch ownership、restart-safe monitoring、deadline与stop intent的authority，但不是Run/Pause/Attempt或budget authority。ExternalOperation维护独立单调`lease_epoch`，不复用parent ControlOperation epoch；逻辑authority虽独立，物理row必须与Coordinator同库以支持A04仲裁事务。创建、dispatch authorization、lease takeover、status observation、resolution intent与final commit都必须验证current epoch和phase revision；normal final、cancel与interrupt intent还必须CAS空`resolution_owner`。Stale worker不能调用dispatch/fetch/cancel、刷新workspace lease或发布receipt/result。

Durable watchdog必须扫描non-terminal external operations和trusted deadline，使用新epoch接管过期monitoring lease，并且只允许`lookup`、恢复exact receipt、`fetch_result`或对原operation执行`cancel`。它绝不能因为Host重启、receipt缺失、provider status unknown或deadline经过而redispatch。真实backend若不能在进程重启后用stable operation identity执行lookup/cancel，就不能通过C00 hard-limit capability gate。

### Containment capability

Budget、Pause deadline与Run cancellation authority仍只属于A04/A06可信控制层。Backend只执行控制层对exact operation下达的停止命令。每个真实local/runtime backend必须提供Host-owned`ContainmentProvider`语义：`start`、`revoke_writes`、`terminate`、`kill_all`与`verify_empty`。停止顺序固定为先fence新的tool/LLM/filesystem side effect与撤销write capability，再graceful terminate、policy-bounded grace、containment-level kill-all、有界关闭stdout/stderr reader，最后验证无存活descendant、无新tool event且filesystem在观察边界内稳定。

Linux strict provider使用dedicated cgroup v2或等价不可breakaway containment；Windows strict provider使用Job Object或等价机制。独立process group/session只能作为containment内部的graceful cleanup或非严格开发provider，因为不可信descendant可能创建新session/process group；仅有process-group kill的host不能声明`strict_descendant_containment`，也不能通过真实Backend capability gate。Phase B可以用deterministic containment fixture证明control contract，平台真实containment属于明确分离的capability evaluation。

完整受控停止按A06 outcome matrix映射为A04 Coordinator恢复、`halted`、已证明`failed`或typed cancelled outcome。Termination、lease revocation、verify-empty、bounded drain或post-stop stability任一false/unknown时，workspace隔离保留，ExternalOperation为`recovery_required`，关联Pause为N/A或`quarantined`，Run closure为`unavailable`且不得注册bundle、重新dispatch或发布failed lifecycle；Run authority可append不能补足缺失的stop proof。

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

Manifest publication只声明将要创建的workspace identity、base与policy，不证明physical workspace已经存在。它必须发生在`external_operation_reserved`和`task_committed`之后、A06 aggregate reservation与`core_contract_committed`之前；actual directory/worktree creation只能由持有current ExternalOperation `lease_epoch`的worker在`core_contract_committed`后执行，并以`workspace_materialized`phase确认。Manifest identity/digest、managed locator或existing filesystem与stub不一致时fail closed，不能换path或建立第二个workspace。

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
- `workspace_materialized`前、stub/core/manifest全部exact且physical workspace从未创建时，current epoch worker可以保持non-terminal并materialize一次；phase已声明materialized后workspace缺失、被替换或无法证明仍是exact Attempt workspace属于`failed` integrity outcome，不能静默重建同一Attempt或重新运行backend；
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

Phase C在创建真实backend implementation ticket前必须先创建、审查、批准并执行独立C00 feasibility ticket。C00使用pinned SDK/runtime版本和非生产fixture，只验证能力，不接入产品graph、不降低A05合同。Capability report必须记录SDK distribution version、Codex CLI/app-server build version及可追溯的release tag或open-source commit；moving `main`源码只能解释候选实现，不能替代实际build的黑盒能力测试。C00至少证明：

1. Host-owned producer operation可以在进程重启后对同一provider execution执行稳定lookup，不重复dispatch；
2. 每次真实tool invocation可由SDK事件或Host wrapper可靠派生连续、完整、不可伪造的`tool_audit.jsonl`；
3. timeout/operator cancel可以终止exact operation的完整process tree，经过bounded grace和强制终止后撤销write lease，并证明停止后没有新的process/tool/filesystem activity或挂住的output reader；
4. workspace-write只覆盖exact Attempt worktree且没有额外writable roots、credential、raw/accepted/control data暴露；
5. terminal result、dispatch receipt、usage evidence、WorkspaceSeal和content digests可以create-new持久化并在重启后exact读取；
6. unknown provider state、event缺失、result冲突和Host crash均能映射为本ticket的fail-closed outcome，不需要第二套Run/Pause/budget authority。

C00通过后，C01才能把pinned Python Codex SDK冻结为首个真实backend。任一required capability失败时，C00必须停止并记录capability matrix；随后另建design ticket选择替代backend，不能把缺失event写成0、伪造provider identity、放宽cancel/audit/workspace/result合同，或修改主图`CodingBackend` port来迁就provider。

## A04 External-result Lifecycle

Inbound Transition 先按 A02/A03 分配 `scheduled` code_agent Attempt并清除 code/downstream current artifacts。随后control plane严格执行`external_operation_reserved -> task_committed -> workspace_manifest_committed -> A06 reservation_committed -> core_contract_committed -> workspace_materialized`，并在该Attempt `started`之前按A04 `pause_prepared -> ExternalOperation Pause binding -> prepared checkpoint -> run_lifecycle -> pause_opened -> public paused checkpoint`协议发布`external_result` Pause。

Pause 必须绑定 task digest、target Attempt、`producer_operation_id`、immutable external-operation contract reference/digest、`coding_backend_kind`、workspace manifest identity/digest、A06在`prepared`前已持久化的resource reservation identity/digest、expected backend/result schema、runtime fingerprint、两个Pause publication checkpoints、state digest及execution/artifact heads。Pause不冻结会因合法watchdog takeover而变化的current epoch；resume preflight必须验证从创建epoch到latest terminal evidence的单调external-operation history。只有持有current external-operation epoch的可信Host或watchdog可以调用允许的`CodingBackend`操作；Code Agent本身不能调用`resume_run`。

完整`CodeAgentTask`必须在`prepared`前以create-new、不可覆盖的方式保存到Run control/audit namespace，Pause绑定其canonical path、owner与digest。它在此阶段不是A03 current `code` artifact。External result到达后，Host同样先创建immutable delivery snapshot并验证owner/path/digest，再把该snapshot reference放入`resume_run`；mutable provider response或workspace path不能直接作为resume input。

Pause期间产生的task、workspace lifecycle、dispatch receipt、seal、external result与delivery snapshot使用由Run/Pause/Attempt/operation identity确定的唯一canonical relative path和exclusive-create语义：exact bytes重复读取已有对象，不同bytes撞到同一identity/path必须conflict。它们不建立第二个mutable current index或独立head；claim preflight必须从Pause和delivery envelope验证完整的owner/path/digest闭包，orphan、missing、duplicate、cross-operation或无法闭合的evidence全部拒绝。

Dispatch/delivery 必须满足：

- 一个 Pause 只绑定一个 stable `producer_operation_id`；
- dispatch前external-operation row必须处于exact authorized phase并由current `lease_epoch` fence；Backend receipt、result、seal和terminal evidence都引用产生它们的epoch，takeover history单调连接到latest evidence，stale epoch publication拒绝；
- 同 operation ID、task digest与workspace manifest digest的重复 dispatch 返回同一receipt/job/result identity，不创建第二workspace execution或Codex thread；
- 同 operation ID 不同task/workspace/backend，或同Pause不同operation ID必须conflict；
- Host必须先把`BackendDispatchReceipt`以create-new方式持久化；receipt、workspace manifest/seal identity与external result digest完整后才能提交resume；
- dispatch receipt与delivery snapshot位于immutable control/audit namespace，在Pause claim前不append execution/budget record、不改变bounded graph state或A04 `opened_execution_head`；
- dispatch outcome 不确定时只能使用`CodingBackend.lookup(producer_operation_id)`确认原operation并恢复同一receipt reference，不得自动启动第二个backend operation；Run保持paused，直到exact result到达、operator显式取消，或A06后续定义的policy触发受控升级；
- backend完成后必须通过`fetch_result`取得immutable result reference并验证exact receipt、task、workspace、operation和digest，不能接受模型文本或Codex thread summary作为delivery authority；
- operation timeout、aggregate hard limit或terminal policy/operator stop必须由A04 internal `resolve_external_interrupt`以`phase_revision + lease_epoch + resolution_owner IS NULL`执行ExternalOperation interrupt CAS；显式`cancel_pause`使用cancel CAS。赢家确定后，durable watchdog只能通过`CodingBackend.cancel`停止exact operation、撤销写lease并提交唯一`external_final_evidence_committed`；失败者只读取赢家，不能创建第二个stop或取得冲突ownership；
- `resume_run` 只接收 immutable `CodeAgentExternalResult` snapshot/reference 与 digest，不接受 workspace path、state patch 或 route；
- claim 后崩溃、重复 delivery 与 head mismatch 完全遵守 A04，不建立 Code Agent 专用 resume/retry入口。

对尚未claim的`external_result` Pause执行`cancel_pause`时，可信Host通过A04 `cancel_arbitrated`区分typed-null、cancel-won、normal-won、preexisting-cancel与preexisting-interrupt。前三类owner-bearing结果按机器outcome guard原子取得Pause/Run owner；两个preexisting winner只记录`resolution_winner_observed`并返回winner identity/revision/current state，不要求owner为空、不取得owner或消费winner final evidence。观察必须验证现有Pause/Run owner与winner operation一致，same-key retry继续原operation。Safe-stop和typed-null分别使用`PauseCancelProof/external_safe_stop | no_external_operation`；unavailable先由same cancel owner完成保守resource disposition，再进入Pause quarantine和Run unavailable closure。中间`termination_evidence_committed`始终不足。

External interrupt只由A04 internal `resolve_external_interrupt`消费。`recoverable_timeout`要求Backend已dispatch、ExternalOperation仍在`dispatch_authorized | dispatch_receipt_committed`、reservation snapshot为`present`且绑定exact opened `external_result` Pause；safe stop提交ExternalOperation `interrupted`后形成canonical Attempt-attributable failed delivery，同一interrupt operation在Pause consume与running checkpoint后领取原scheduled Code Agent Attempt，完成started、failed code artifact、Attempt failed、活动绑定释放与最终checkpoint再提交result，随后由新的`advance_run`唯一发布`code_agent -> decision_coordinator` Transition。`controlled_halt`与`integrity_failure`允许Pause snapshot为absent/prepared/opened，并按机器correlation分别形成N/A、`pause_aborted`或`pause_interrupted`；resource snapshot在reservation前只可为typed absence、reservation后只可为present，其ExternalOperation identity/phase/revision/epoch必须逐字段匹配interrupt reservation保存的exact resolution tuple，present reservation的binding digest还必须覆盖ExternalOperation和reservation identity/digest。Unavailable disposition必须由相同snapshot映射到N/A/`pause_quarantined`并由terminal proof绑定该disposition digest。任一stop proof维度缺失均为ExternalOperation `recovery_required`、Pause N/A/`quarantined`和Run closure unavailable。Backend dispatch必须晚于public Pause，因此pre-Pause ordinary timeout非法；pre-Pause hard-limit/policy stop使用terminal variant与typed `not_dispatched`。

Recoverable timeout使用同一`consume_code_agent_result`的trusted-host failed input，来源是完整safe-stop和usage/integrity证据，而非伪造Backend result、seal或成功verification。Host在`canonical_failed_delivery_committed`冻结schema-valid `failed`、`usable=false`、`operation_timeout`结果及完整failed bundle bytes；所有未执行verification spec保留`not_run/operation_timeout`，不携带可promote change。该路径不要求不存在的Backend result/seal，保留其typed absence及真实stop证据，且不得消费不可信workspace。随后在same interrupt winner下完成原Attempt started、failed bundle注册、failed lifecycle、活动绑定释放和final checkpoint；不启动verification或重复结算。Normal Backend delivery仍遵守下列resume preflight。

Resume在claim前必须完成delivery envelope的duplicate-key、schema、identity、owner、path、digest、member-shape、dispatch receipt、workspace manifest/seal和reservation/usage preflight。Claim必须对exact A04 `opened_execution_head`成功；随后在target code_agent Attempt `started`前append exact `resource_settled`。Claim后settlement崩溃在existing evidence exact、settlement identity/digest已预计算且仅无副作用publication未闭合时保持`in_progress/materialization_pending`；缺少可信settlement evidence或副作用结果不确定时终止为`recovery_required`，实际usage/identity/head mismatch进入`failed`。后两者都不得重新dispatch或启动target Attempt。Settlement完整后，target code_agent Attempt只`started`一次；`CodeAgentSubgraph` materialize已通过preflight的change，在fresh verifier workspace运行trusted verification/scope checks，计算canonical result，注册bundle，然后写terminal Attempt lifecycle，不再次Pause。若结果表达`needs_input`或`needs_human`，先完成当前Attempt并交给Coordinator，由Coordinator按A04建立新的`human_input` Pause。

## `CodeAgentExternalResult` and Trust Boundary

Backend 返回的 external result 是 untrusted ingress，即使来自本地 Fake、Codex SDK或签名 provider也不能直接成为 current code artifact。Ingress preflight由sandbox和replayable graph node之外的Trusted Host执行；sandbox只能声明结果，不能决定canonical status、路由或是否可信。External result至少包含：

- exact task/execution/base/workspace/producer identities 与 digests；
- exact backend kind/version、dispatch receipt、provider job/thread audit identity与digests；
- declared result status、change manifest、change blobs/patch和tool audit references；
- backend执行的verification claims、resource usage、warnings、errors与failure evidence；
- workspace seal identity/digest和result canonical digest。

Trusted `CodeAgentSubgraph`必须重新验证 schema、identity、path containment、base-to-result content、member digests、scope、authorization和budget envelope。Required verification由trusted verifier在fresh materialized workspace中重新运行；backend或Codex自报“tests passed”只能作为audit evidence，不能满足route guard。Backend实际usage超过aggregate maximum且完整safe stop后仍有可验证overage evidence时才可形成已证明integrity failure；停止后继续产生side effect或无法验证停止边界一律进入`recovery_required + unavailable`并隔离，不得通过按maximum结算或`run_status = failed`掩盖仍可能活动的执行。Canonical `status`、`usable`、`failure_class`和`retryability`必须由trusted validator根据validated change、policy和verification evidence计算或约束，不能直接复制backend声明。

Malformed、duplicate-key、identity mismatch、digest mismatch、path escape或无法完整验证的external result不能注册为合法`CodeAgentResult`。这些问题在preflight发现时拒绝claim并保持原Pause；claim后若观察到实际tamper、mismatch或违规content，必须隔离workspace/evidence并由同一resume owner进入A04 consumption_failure尾部：消费者/verifier停止证明完整且Run authority仍可验证和安全append时发布`run_status = failed`；停止证明或authority不可验证时返回`terminal_closure = unavailable`。只有已存在bytes/identity/heads全部exact、没有违规或新副作用且closure suffix已预计算时，原operation才保持`in_progress/materialization_pending`并补齐；无法安全继续但没有完整性违规时终止为`recovery_required`。后两种情况都不得自动重跑Attempt。不得把invalid payload静默规范化为success、复用旧bundle或让Agent选择fallback route。

Backend若在自身边界发现内部输出无效，可以返回一个schema-valid、无usable change的`failed` envelope，并使用`failure_class = result_invalid`；该可信可归属的failure evidence经Host验证后才可形成canonical failed bundle并交给Coordinator。它与把malformed ingress规范化为合法结果不是同一行为。

Post-claim integrity failure不使用canonical Code result作为cleanup门槛。原resume在failure intent处取得唯一Run terminal owner并fence消费执行，停止consumer/verifier且结算其独立resource operations；Backend normal final与原aggregate settlement保持不变。完整safe proof用typed artifact-absence/rejection evidence完成Attempt/Pause处置与活动绑定释放，再复用terminal checkpoint关闭为failed；不完整proof用same-owner unavailable tombstone隔离。该分支禁止走advance、伪造host_timeout或failed Code bundle、重开consumed Pause、创建close_run或第二个External interrupt。

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

`policy_blocked`只表示安全的pre-change拒绝。External payload实际包含out-of-scope member、path escape、forbidden target或其他违规filesystem content时属于invalid ingress：不注册canonical code artifact；claim前只记录control rejection evidence并保留Pause，claim后观察到实际违规content时quarantine并进入A04/A06 integrity outcome，只有Run authority仍可验证和安全append时才发布`run_status = failed`。无违规content、已有bytes与heads均exact且suffix已预计算的side-effect-free publication partial保持`in_progress/materialization_pending`；`recovery_required`只用于无法继续原operation的terminal不确定性。

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

每个完成验证的 code_agent Attempt注册一个 A03 `code` slot artifact，`artifact_id = <attempt_id>:code`，canonical root位于该Attempt namespace。Bundle schema `0.1`按`result_origin = backend_delivery | host_timeout`确定成员集合。常规`backend_delivery`固定包含：

- `code_agent_task.json`：实际执行的immutable task snapshot；
- `code_agent_result.json`：唯一authoritative structured outcome；
- `backend_dispatch_receipt.json`：producer operation、backend、provider job/thread与dispatch identities；
- `workspace_manifest.json`：immutable base/workspace/backend/policy creation contract；
- `workspace_seal.json`：final tree、change/tool-audit digests与closed write lease evidence；
- `change_manifest.json`：按path排序的change entries；
- `verification_results.json`：task中每个required spec的trusted result；
- `tool_audit.jsonl`：经过redaction的bounded backend tool audit；
- `changes.patch`：仅在change manifest非空时存在，并与manifest/blob digests交叉校验。

`host_timeout`只允许机器`recoverable_code_consumption_contract.result_source_contract`指定的可信safe timeout：必需task、result、workspace manifest、`interrupt_evidence.json`、empty change manifest及逐spec `not_run/operation_timeout` verification results。Result为`failed`、`failure_class=timeout`、`usable=false`；interrupt evidence绑定原Attempt、same winner、External final safe-stop digest与trusted usage/integrity证明。Receipt已提交时引用真实原receipt；尚未提交时使用绑定dispatch phase的typed absence，不要求生成虚假receipt。Backend seal/tool audit引用为显式`not_applicable/host_timeout`，bundle禁止seal、tool audit及patch成员；已有不完整Backend bytes只留control audit，不当作完整领域证据。这不是宽松的Backend ingress：`backend_delivery`仍必须满足完整seal/audit/member校验，unavailable或integrity failure不能使用host_timeout注册可恢复failed artifact。

`tool_audit.jsonl`由backend wrapper而不是模型文本生成。每个真实tool invocation使用从1连续的`tool_event_index`，并绑定task/workspace/tool identity、typed argv digest、cwd、start/end、status、affected paths、bounded output digest和resource usage；缺失、重复、乱序或identity变化使result无效。零tool-call outcome允许空audit file，但其digest仍必须被result引用。C00 feasibility ticket必须先验证候选backend能够提供或由Host wrapper可靠派生该合同；无法满足时停止，不得降低trusted audit或伪造缺失events。

每个 change entry 至少冻结 normalized path、`added | modified | deleted`、before/after SHA-256、file mode和content/blob identity。Member path、digest、size、status-required member set与producer Attempt必须由A03 registry验证。`backend_delivery`的`code_agent_result.json`必须引用task、backend receipt、workspace manifest/seal、change、verification和tool-audit digests，但不自引用整个bundle digest。

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

正常Backend结果和trusted host_timeout结果注册并完成原Code Agent Attempt后，都必须由原消费owner提交A04 `external_consumption_released`，再提交最终checkpoint并允许outbound Transition。Release只改变coordinator活动绑定projection，保留原ExternalOperation、resolution、Pause及receipt历史；以后新Code Agent Attempt不能继承旧release proof。Generic RecoveryDecision不得启动尚无ExternalOperation结果的Code Agent；其continue action在claim前拒绝，避免绕过本节唯一pre-start与result-consumption流程。

## A01 Route Guards

`code_agent -> analysis_engineer`只允许同时满足：

- producing Attempt、Transition、task、Pause、external result与A03 code artifact identity exact-match；
- result status为`success`且`usable=true`；
- base/runtime、change member、scope、policy、authorization和全部trusted verification有效；
- current plan/code pointers与scheduled Analysis Attempt dependencies符合A03；
- A06 budget/duplicate-failure guard允许继续；
- 没有`needs_human`、policy violation或head mismatch；需要Human authorization时，其exact scope已由该task/Attempt合法单次消费，且没有复用或越权。

所有其他valid result都只能由`advance_run`进入Decision Coordinator。A01 `invalid outcome`在本合同中仅指schema-valid、Attempt-attributable且经Trusted Host规范化的canonical `failed/result_invalid`，不是sandbox原始invalid payload。Invalid ingress在claim前拒绝且不产生产品Transition；claim后预计算、exact、side-effect-free publication suffix保持`in_progress/materialization_pending`，无法继续原operation的结果不确定性终止为`recovery_required`，实际tamper/identity/digest/path/policy integrity failure进入`failed`。只有上述canonical failure可以形成failed bundle，再由独立`advance_run`发布Coordinator Transition。Code Agent不允许自行选择Analysis、rerun、replan、Human Gate或END。

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
-> advance_run verifies committed Transition heads
-> advance_run materializes reserved immutable AnalysisExecutionSpec
-> Host materializes fresh Analysis worktree from exact base + verified change
-> Host verifies expected effective tree digest and commits target_preparation_committed
-> advance_run prepares capability and commits operation result
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

Spec及manifest的canonical bytes/digests在`advance_run/operation_reserved`随`TargetPreparationSnapshot/analysis_fresh`冻结；在`transition_heads_verified`之后由`target_preparation_committed`负责物化，先于capability准备及operation result。Spec在目标Analysis Attempt`started`前以create-new方式写入该Attempt的control/audit namespace。Exact重复必须得到同一canonical bytes；同identity不同bytes必须conflict。它不是新的current artifact，也不能修改已提交Transition。Spec publication和workspace preparation是trusted pre-start control steps：必须先验证scheduled target与唯一inbound Transition，不创建额外Attempt/Transition、不执行repository code、不写domain artifact，也不把target标为`started`。Analysis Host必须从同一base重新materialize并应用exact verified content-addressed change，不能复制mutable Code Agent workspace、读取control repository当前文件、继承Codex process/module cache或使用Python module reload。

Analysis注册的artifact必须依赖exact source Code Bundle；base、patch、effective tree、runtime、Transition、Attempt或current head任一不一致均不得启动或注册Analysis结果。

失败边界固定为：

- Code Bundle已注册但outbound Transition尚未提交：保留current code，验证heads后继续正常route commit，不重跑backend；
- Transition已提交但spec或Analysis workspace尚未materialize：原advance保持`in_progress/materialization_pending`且target Attempt为`scheduled`，current epoch按reservation冻结的spec/workspace bytes与identity幂等创建，不重新提交Transition；
- Analysis启动前发现已知publication phase尚未完成、所有已存在bytes仍exact且spec/workspace identity/digest已预计算时保持`in_progress/materialization_pending`并只补齐该suffix；若target execution是否已开始或产生副作用无法证明，则终止为`recovery_required`。Code/artifact head、spec、workspace或effective tree发生不一致、篡改或无法闭合时进入A04/A06 integrity outcome：authority仍可验证和安全append时发布`run_status = failed`，否则`terminal_closure = unavailable`。旧target不得重复启动、自动abandon或被retarget，同一source Attempt不得提交第二条outbound Transition；只有满足A04 source validation时才允许operator显式replay/fork到新Run；
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

Canonical Code Agent语义以A04 schema `0.3` Pause合同为前身，Phase B实际目标只支持完整execution schema `0.4`。Phase B不得对`0.3` Run原地resume、迁移或附加code_agent Attempt；符合A04 source validation时，只能显式replay/fork到新的`0.4` child后使用本合同。其他未知或不支持版本fail closed，pre-A04或正在运行的legacy Run同样不得附加canonical code_agent Attempt。

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
- coordinator-owned`ExternalOperation 0.1`、durable watchdog、lease fencing与`ContainmentProvider`合同；
- content-addressed code artifact bundle与trusted verification合同；
- verified Code Bundle到`AnalysisExecutionSpec`和fresh Analysis subprocess的交接合同；
- structured outcome/failure/retryability taxonomy与A01 route guards；
- Fake backend scenario inventory；
- 对A06、A07和Phase B/Phase C implementation tickets的明确输入；
- 核心source-of-truth文档更新和独立A05 completion record。

## Acceptance Criteria

- `CodeAgentSubgraph`拥有控制生命周期，Fake与任何通过C00的真实backend可以在不修改主图routing、Pause、task/result schema或artifact contract的情况下替换；
- subgraph pre-start control stages不领取target Attempt，`consume_code_agent_result`只在Pause claim、settlement、`pause_consumed`、paused-to-running lifecycle与resume checkpoint后把同一scheduled Attempt启动一次；
- canonical code_agent Attempt与legacy handoff严格分离，全部identity与A02/A03/A04 heads exact绑定；
- 每次真实执行使用新的immutable-base worktree、`WorkspaceManifest`与`WorkspaceSeal`，不接触control repository或另一Attempt workspace；
- 若C00选择Python `CodexSdkBackend`，它必须使用`Sandbox.workspace_write`、无额外writable roots且默认关闭workspace network；SDK选择本身不能替代C00对lookup/cancel/tool-audit/restart能力的证明；
- 主图只消费validated content-addressed bundle，不消费mutable workspace或Markdown声明；
- producer identity stub必须先于task/manifest/reservation/workspace bytes，immutable core必须先于workspace materialization；external dispatch/delivery、Pause claim和进程崩溃均由durable external-operation row与lease epoch约束为single-operation且fail closed，Host重启或unknown status不能redispatch；
- aggregate hard limit、operation timeout与operator cancellation由durable watchdog通过exact `cancel`和strict containment强制执行到完整process tree并验证post-stop inactivity；safe timeout先形成canonical failed delivery并提交interrupt result，再由`advance_run`进入Coordinator，safe terminal policy/operator stop为`halted`，任一stop proof维度false/unknown均为`recovery_required + terminal_closure = unavailable`且不得伪造failed lifecycle；
- backend result只有在fresh trusted workspace验证后才能注册，registered bundle只有通过`AnalysisExecutionSpec`在新worktree/subprocess中执行；
- scope/path/symlink、policy、authorization、digest或trusted verification任一失败都不能进入Analysis；
- `success`以外的所有canonical valid status由`advance_run`进入Coordinator；A01 `invalid outcome`只表示validated `failed/result_invalid`，invalid ingress不注册artifact也不产生产品Transition；
- change加tests通过不等于科学接受、repo promotion或accepted memory；
- task发现需要扩权时创建新Human authorization与新Attempt，不追溯批准旧change；
- A06/A07及后续实现无需自行发明另一套Code Agent lifecycle或result taxonomy。

## Required A07 and Implementation Scenarios

A07和后续implementation tickets至少必须覆盖：

- `A05-CODE-001`：Method Planner implementation gap和Coordinator code fix两种task origin；
- `A05-CODE-002`：process退出后的external Code Agent result准确恢复一次；
- `A05-CODE-003`：严格验证`external_operation_reserved -> task_committed -> workspace_manifest_committed -> reservation_committed -> core_contract_committed -> workspace_materialized -> pause_bound`，producer identity/epoch先于任何workspace bytes且不预占Pause identity；prepared后以fenced one-time CAS补齐Pause binding，dispatch/delivery不改变`opened_execution_head`，claim后settlement必须先于target `started`；
- `A05-CODE-004`：pre-start control stages重复进入时stub/task/manifest/reservation/core/workspace/Pause exact幂等，且不产生第二identity、target `started`、backend dispatch或code artifact；
- `A05-CODE-005`：same operation/task重复dispatch、conflicting dispatch、same delivery重复resume和竞争claim；
- `A05-CODE-006`：dispatch状态不确定时`lookup`返回running/completed/unknown且绝不创建第二operation；known operation必须返回同一receipt reference/digest并支持receipt publication崩溃恢复，unknown不得伪造receipt；
- `A05-CODE-007`：operation timeout、aggregate hard limit和operator cancellation先通过各自typed resolution operation持久化stop intent，再通过同一`cancel`port和ContainmentProvider停止exact process tree，执行revoke/fence → graceful terminate → bounded grace → containment kill-all → bounded output drain → verify-empty；完整recoverable safe stop先提交delivery，完成原Code Agent Attempt的started/failed artifact/failed lifecycle/final checkpoint与interrupt result，再由唯一`advance_run`进入Coordinator，terminal safe stop映射halted或已证明failed；任一stop proof缺失只进入recovery-required/unavailable，且都不创建替代stop/terminal operation；
- `A05-CODE-008`：process在dispatch receipt、backend completion、result snapshot、Pause claim、settlement、`pause_consumed`、paused-to-running lifecycle、resume checkpoint、target start与bundle registration各边界退出；
- `A05-CODE-009`：success result通过`AnalysisExecutionSpec`进入fresh Analysis Attempt，plan/code dependencies和A03 invalidation正确；
- `A05-CODE-010`：no-change、failed、needs-input、needs-human、budget-exhausted、policy-blocked全部进入Coordinator；
- `A05-CODE-011`：backend自报pass但trusted verification failed/blocked/timeout时拒绝Analysis；
- `A05-CODE-012`：out-of-scope file、path escape、symlink escape、Git metadata、secret/raw/accepted/control target拒绝；
- `A05-CODE-013`：wrong Run/Case/Cycle/Attempt/Transition/task/base/workspace/pause/result/member digest拒绝；
- `A05-CODE-014`：missing/tampered/reused workspace、foreign lease、base drift、path swap与seal后filesystem变化拒绝；
- `A05-CODE-015`：Code Bundle已注册但Transition未提交、Transition已提交但Analysis workspace未创建的幂等恢复；
- `A05-CODE-016`：Analysis handoff的预计算、exact、side-effect-free partial publication保持`in_progress/materialization_pending`；target execution结果不确定时为terminal `recovery_required`，spec、patch、effective tree、runtime或current head mismatch映射`failed`，旧target不重复启动、不自动abandon、不retarget、不从同一source提交第二条outbound Transition且不读取control repository；
- `A05-CODE-017`：non-empty unverified change不能伪装partial success；
- `A05-CODE-018`：Human授权scope/digest错误、已消费授权或执行中扩权全部fail closed；
- `A05-CODE-019`：multiple code attempts使用独立workspace和artifact，旧code/downstream不再current但canonical bytes保留；
- `A05-CODE-020`：Fake与future real backend contract fixtures通过同一`dispatch`/`lookup`/`fetch_result`/`cancel` port、validator、verification、registration和fresh Analysis入口；
- `A05-CODE-021`：legacy handoff不能被读取为canonical Code Agent result。
- `A05-CODE-022`：ExternalOperation两阶段identity/core及完整phase在dispatch前持久化；Host crash后watchdog以新lease epoch只materialize预计算的pre-dispatch suffix或lookup/fetch/cancel原operation，stale worker写入拒绝，unknown状态绝不redispatch；
- `A05-CODE-023`：malformed/tampered/identity-digest-path invalid ingress在图外拒绝且不产生产品Transition；claim后预计算、exact、side-effect-free publication partial保持`in_progress/materialization_pending`，不可继续的不确定性为terminal `recovery_required`，实际tamper/mismatch为`failed`；schema-valid、Attempt-attributable `failed/result_invalid`经Host验证后形成canonical failed bundle，再由独立`advance_run`进入Coordinator；
- `A05-CODE-024`：strict containment fixture证明breakaway/concurrent-fork descendant仍被kill-all；仅process-group provider不能声明strict capability，真实Backend在缺少restart-safe lookup/cancel或strict containment时capability gate失败。
- `A05-CODE-025`：normal、cancel和interrupt resolution全部收敛到唯一terminal phase `external_final_evidence_committed`；它完整携带resolution kind、适用于该resolution的proof、termination或typed `not_dispatched`、lease revocation、verify-empty、bounded drain与post-stop stability，任何中间observation都不得关闭Pause，normal只允许`safe_stop`。
- `A05-CODE-026`：normal terminal、cancel intent与interrupt intent必须以exact ExternalOperation `phase_revision + lease_epoch + resolution_owner IS NULL`单点CAS仲裁；normal刚好早于/晚于cancel、stale revision/epoch以及winner后的迟到写入均证明恰好一个resolution owner胜出，失败者只能沿赢家路径读取。
- `A05-CODE-027`：interrupt在pre-dispatch、dispatch-authorized和receipt不确定窗口均经过`interrupt_stop_intent_committed -> termination_evidence_committed -> external_final_evidence_committed`；safe stop使用terminal status `interrupted`并由typed disposition决定Coordinator恢复、halted或已证明failed，任一停止证明维度缺失时产生`recovery_required/unavailable`，且terminal status不得出现在nonterminal phase。
- `A05-CODE-028`：每个interrupt terminal tuple携带`interrupt_disposition`并由同一`resolve_external_interrupt` variant消费；resource snapshot的ExternalOperation identity/phase/revision/epoch必须匹配该tuple，present reservation binding digest覆盖同一ExternalOperation与reservation。Recoverable timeout只允许已dispatch/opened Pause，pre-Pause ordinary timeout拒绝，terminal interrupt按Pause absent/prepared/opened形成N/A/aborted/interrupted或unavailable quarantine。Interrupt获胜后cancel只能观察winner，不能取得Pause/Run owner或消费interrupt proof。
- `A05-CODE-029`：normal safe-stop candidate只存在于normal finalization request并以digest参与CAS；unavailable candidate在任何normal CAS前确定性创建或复用integrity interrupt，cancel/interrupt不携带伪造N/A candidate，共享ExternalOperation不保存可冲突的预分类字段；

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
python scripts/validate_phase_a_control_protocol.py
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
