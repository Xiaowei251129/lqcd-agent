# Artifact Contracts

## 第二阶段文档定位

本文记录当前 runtime 已经实现并由测试覆盖的 artifact contracts。下面保留英文 schema identifiers、field names、status values 和文件名，解释以这些精确合同为准。

A02 已完成 Run/Cycle/Attempt/Transition/Human execution ledger，A03 已完成 per-attempt domain-artifact namespace、artifact history/current index、supersession/invalidation 和 fixed-path compatibility projection。A04已冻结后继Pause/Run lifecycle、checkpoint evidence与child lineage目标合同，A05已冻结后继Code Agent task/result、workspace evidence、code bundle、trusted verification与fresh Analysis handoff合同，A06已冻结后继budget policy、budget events、resource envelope与fingerprint/grant evidence合同；这些目标合同均未改变当前artifact schema或runtime。Physics RAG evidence bundle仍未获批，只能在后续独立ticket中定义。

B02当前实现边界：独立0.4 control入口持久化Run-local immutable inputs、policy、Pause/checkpoint与child lineage，fenced invocation复用A03 bundle注册；normal/timeout消费和preparation经typed domain ports验证顺序，默认0.2及slot policy不变。完整来源轨迹包含artifact历史原文；trace0.4先证明external Pause `reservation_digest`指向同Run/Attempt/producer的真实`resource_reserved`记录，再做语义规范化，其他material摘要仍精确比较。B03 canonical Code schemas、Backend和workspace由后续票据实现。当前已验证范围见[B02完成记录](tickets/completions/B02_COMPLETION.md)。

## Execution Identity History

[A02 Run/Cycle/Attempt Model](tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md) 在每个 run root 写入：

```text
<output_root>/<case_id>/<run_id>/execution_history.jsonl
```

ledger schema version 是 `0.2`，`record_type` 固定为 `run`、`cycle`、`attempt`、`transition`、`human_request` 或 `human_response`。新 Run 的前四条 authoritative records 顺序固定为：

```text
Run created
-> initial Cycle created
-> Planner Attempt scheduled
-> START -> method_planner Transition committed
```

每个 Run 恰好一个 Run `created` record，记录 `parent_run_id`、`creation_reason`、root-goal reference/digest、input-snapshot reference/digest、canonical output root 和 Run-owned `checkpoint_thread_id`。Cycle `created` record 只记录自身 Run/Cycle lineage、trigger 和 creating Attempt，不混入旧 Attempt envelope。

每次 node invocation 的 Attempt 使用同一 ID 追加以下 lifecycle records：

```text
scheduled -> started -> finished (succeeded | failed | pending)
scheduled -> abandoned
```

Attempt record 分开记录 canonical `attempt_kind` 和 physical `node_name`、parent Attempt、inbound Transition、input/output references 与 optional error。当前 physical `codex_handoff` 的 canonical kind 是 `legacy_codex_handoff`；`code_agent` 只为 A05/Phase B protocol 预留，当前产品 graph 不执行它。

每条来源路线另外写一个 Transition `committed` record，包括 deterministic ID/index、source/target Cycle、source/target Attempt、physical target、canonical target kind、route/trigger/reason/evidence，以及 applied state-update keys/digest。END transition 的 target fields 为 null。target Attempt 在 Transition commit 中、目标节点任何副作用之前预分配；fixed 和 conditional routes 使用相同协议。

Human Request/Response 是独立 records，不是 Human Gate Attempt。Coordinator 进入 Gate 时创建 `human_request_*`，记录 request kind、requesting Coordinator Attempt、authorization scope 和 packet reference。外部提交创建 `human_response_*`；同一 response ID 依次追加 `submitted -> validated -> consumed` 或 `submitted -> invalid`，并记录 payload snapshot/digest、validated decision、logical authorized route、精确 authorized Transition route/target、validator Gate Attempt、consumer Gate Attempt 和 authorized target Attempt。validated response 只能消费一次。

文件只允许 append，不允许覆盖；legacy incomplete-Run re-entry 从已有 records 恢复 counters，不能复用旧 IDs，也不能被描述为 A04 durable resume。registry恢复和读取还要求每类Run-local Cycle、Attempt、Transition、Human Request和Human Response index为正整数、deterministic identity唯一且序列从1连续到max；同一identity的lifecycle字段必须稳定，不同identity不能复用index。

event log、route decisions、approval packet、memory update 和 final report 记录 relevant current identity。Attempt ledger 的 input/output references 使用 canonical paths 与 `current_artifact_ids`；Human Response ledger references 使用 immutable snapshot path/digest，不引用随后可能变化的 ingress projection。

## A03 Artifact Registry 与 Current Contract

Run root 继续是 `<output_root>/<case_id>/<run_id>/`。graph-managed domain artifacts 的 canonical immutable namespace 是：

```text
<run_root>/attempts/<attempt_id>/...
```

同一 Attempt/slot 最多注册一个 bundle，artifact ID 固定为 `<attempt_id>:<slot>`。slots 固定为：

```text
plan -> optional code -> analysis -> review -> decision -> approval -> terminal
```

每个 Run 还写：

```text
artifact_history.jsonl
artifact_index.json
```

`artifact_history.jsonl` schema version 是 `0.1`，event 固定为 `registered`、`current_set`、`current_cleared`、`protected_snapshot_registered`。event ID/index Run-local 单调递增；member 至少记录 logical name、Run-relative canonical path、SHA-256、size 和 media type。每个普通`registered` event还冻结完整 typed current pointer和producing `node_name`，并且必须立即跟随同一artifact唯一一次`current_set`；清除后的artifact不能再次成为current。history append-only，并验证 identity、固定reason code、顺序、member containment、digest和pointer内部一致性；history、index与execution ledger中的duplicate JSON object key均拒绝。校验不仅检查已有event是否合法，还从execution ledger反向派生必需event：finished Attempt的output references必须覆盖其registered bundle，registered bundle的Attempt必须至少具有合法`scheduled → started`生命周期；缺失整个registration/current-set序列同样fail closed。每个带target Attempt的committed Transition必须反向对应exactly one合法Attempt lifecycle，且Transition的Run、Case、target Cycle、Attempt、Kind、Node与Attempt provenance exact-equal；bounded state中已填充的current Attempt也必须与该lifecycle最新状态exact-equal。普通member必须位于其producing `attempts/<attempt_id>/`内，canonical相对Attempt的路径必须与logical/projection path一致。producing Attempt的`run_id`、`case_id`、`cycle_id`、`attempt_id`、`attempt_kind`、`node_name`必须全部存在并与execution ledger exact-equal。

`artifact_index.json` schema version 是 `0.1`，以原子替换发布，记录 revision/head、七个 typed current pointers 和 `managed_projections` owner map。正常 current selection 只读取该 index 或与其验证一致的 bounded state，不允许按目录、mtime 或文件名猜测最新结果。registry按`registered → current_set → current_cleared`重放history，重放得到的七个current slots必须与index exact-equal；`managed_projections`也必须由这些current pointer的member paths唯一派生并与index exact-equal。projection必须是Run-relative、留在Run root内，且不能指向Attempt、control、Human Response、checkpoint、context、raw-data或accepted-result路径；重复、额外、缺失、未知或错误owner均fail closed。恢复已有Run时，只有显式的空重建state（counter为0、`current_artifacts`为空且全部artifact convenience path为`None`）可以从validated registry同步；任何已populated state必须先与history/index、canonical digest和managed projection完整一致，不能被initialize静默覆盖或修复。index/history head、state counter、current pointer、dependency、canonical digest 或 projection ownership不一致时 fail closed，不自动迁移或修复缺少新identity字段的实验性A03 registry。

bounded state必须绑定execution ledger的全局head，而不只是绑定某个局部合法lifecycle：Cycle lineage、Attempt完整provenance/latest status、Transition ID/index/route、latest Human Request字段和Run-global Human Response counter都必须等于各自max index；active Human Response必须是latest Human Request下max response index对应的latest lifecycle，或在该request尚无response时为`None`。合法Human Request lifecycle为`created`后可选`packet_written`，并可最终`satisfied`。Human Response snapshot publication只允许确定性的next global response ID/index作为一次性pending preflight，且decision、validator、consumer和target fields必须为空；恢复、普通读取和save不接受该例外。

committed Transition的target shape也属于registry完整性边界：只有`end`/`__end__` route允许`target_attempt_id`为`None`，且其他三个target fields必须显式存在并同时为`None`；字段缺失不等同于null。任何非terminal route必须提供完整的target Attempt/Node/Cycle/Kind tuple并与exact target Attempt lifecycle双向一致。删除目标Attempt或artifact、回滚state并把非terminal target协调置空不能形成合法head。bounded state和Attempt/Cycle ledger中的nullable identity fields同样必须显式存在，不能通过删除字段伪装成合法null。

bundle dependencies在注册时冻结：code依赖 plan；analysis 依赖 plan 和存在时的 code；review依赖 analysis；decision、approval 和 terminal记录它们实际读取的全部 current upstream artifact IDs。history replay必须按注册时的current slots重算基础dependency前缀，额外dependency只能引用此前已注册artifact；forward、wrong-slot、non-current replacement或重复dependency均fail closed。`current` 只表示最新有效链成员，不等于 success、usable 或 accepted。

Transition commit 在 target Attempt 副作用前执行确定性 invalidation：

| Target | Cleared current slots |
| --- | --- |
| `scientific_reviewer` | `review`, `decision`, `approval`, `terminal` |
| `analysis_engineer` | `analysis`, `review`, `decision`, `approval`, `terminal` |
| `legacy_codex_handoff` / `code_agent` | `code`, `analysis`, `review`, `decision`, `approval`, `terminal` |
| `method_planner` | all slots |
| `decision_coordinator` | `decision`, `approval`, `terminal` |
| new-request `human_gate` | `approval`, `terminal` |
| same-request validation `human_gate` | none |
| `memory_report` | `terminal` |

Invalidation 清除 index/state current 和 owned projection，但不删除 canonical members、history 或 protected snapshot。每个`current_cleared`必须清除当时该slot真实current的同一artifact，并将triggering `transition_id`、target/triggering `attempt_id`、target Cycle、Attempt kind/Node和reason code与execution ledger中的唯一committed Transition及其目标Attempt exact-equal；slot还必须属于该target kind的固定invalidation policy。反向校验从每个scheduled Attempt的`input_references.current_artifact_ids`和target policy派生完整expected-clear map，并要求同一target Attempt的actual clear map exact-equal，因此删除单个或全部required clear后即使协调修改history/index/state也会fail closed。initial与legacy incomplete-Run re-entry的Planner调度使用同一invalidation入口；目标 Attempt随后失败、pending或没有bundle时，旧pointer不会恢复。

v0.2 run-root fixed paths保持为 current compatibility copies，包括 plan/code/analysis/review/decision/approval/terminal paths和 `llm_calls/`。copy publication 对单文件使用同目录临时文件与 `os.replace()`；目录按成员受控 materialize，不使用 symlink。publication在复制任何bytes前必须preflight全部member；另一个current artifact已经拥有的projection会使整个注册失败，history、index和既有projection保持不变。只有 index 中记录正确current artifact owner 的 projection 可以替换/清除；没有 A03 index 的 legacy tree拒绝接管。外部 handoff result files与 Human decision file仍是明确 ingress，消费后 canonical evidence由 registry保留；这两类ingress只豁免projection digest比较，不豁免路径、存在性和owner验证。

Human Response payload写入 `<run_root>/human_responses/<human_response_id>/payload.json`，artifact ID必须为 `<human_response_id>:payload`，唯一member必须是同一identity下的`payload.json`，并使用 `protected_kind: human_response`；protected event的Run/Case/Cycle/Request/Response、canonical path和digest必须与唯一`submitted` Human Response ledger record exact-equal，且每个submitted ledger identity必须反向对应exactly one Human Response protection。每个Human Response ledger identity必须形成合法有序的`submitted → validated|invalid → consumed?`生命周期，跨事件的Run、Case、Request、Response、index、payload path与digest不可变化；bounded state声明的active Human Response必须存在于ledger，并与其最新lifecycle状态、decision、route、validator、consumer和authorized target exact-equal。accepted terminal bundle继续使用 `<attempt_id>:terminal`，但只有当它是当时current、slot为`terminal`且pointer status为`accepted`时，才能追加唯一`protected_kind: accepted_result`事件；每个registered accepted terminal也必须反向对应exactly one protection，未知protected kind、非terminal/non-accepted、缺失或重复protection均fail closed。为保持正常原子写入顺序，invalidation、Human Response snapshot和accepted protection API只对正在写入的唯一target/response/producing Attempt开放一次受限preflight例外；恢复、读取和state保存不接受该例外。`memory_update.json`冻结 source artifact IDs/member digests和 Human Response identity。A03不提供跨进程 partial-commit recovery或 replay；A04已冻结这些后继语义，但尚未实现。

## A04 已确认的 Pause 与 Child-Run Evidence Contract（尚未实现）

A04目标execution schema `0.3`在A02 ledger上增加append-only `run_lifecycle`以及`pause_prepared | pause_opened | pause_claimed | pause_consumed | pause_cancelled | pause_aborted | pause_interrupted | pause_quarantined` records。每条record携带自身event identity、sequence与canonical digest，resulting execution head由record bytes派生；payload不得嵌入自己的未来digest/head。bounded `run_status`和Pause fields只是这些records的projection。

Pause publication evidence固定形成非对称closure：

```text
pause_prepared resulting head
-> prepared checkpoint
-> run_lifecycle(running -> paused)
-> pause_opened resulting head
-> public paused checkpoint
```

prepared event引用append前execution/artifact heads、typed reason/input/authorization contract、requesting/nullable target Attempt、canonical state digest和runtime fingerprint；prepared checkpoint引用prepared resulting head；opened再绑定prepared checkpoint及lifecycle pre-head；public checkpoint最终引用opened resulting head。Checkpoint、bounded state、execution/artifact heads或Pause/Run lifecycle任一不一致均不可resume，且不得通过读取或state patch补写history。

所有public mutation与internal publication由`<output_root>/.lqcd/control_operations.sqlite`中的ControlOperation journal先取得owner；operation records、checkpoint manifests、Pause events与result closure都绑定exact `operation_id + lease_epoch + phase_revision`。同key同request只重放原result，同key不同digest或竞争owner冲突；只有已预计算、head-exact且无副作用的缺失suffix可由原operation materialize。`recovery_required`、integrity failure和`terminal_closure: unavailable`是控制证据，不得伪造domain artifact、accepted result或Run lifecycle。

Replay/Fork child在任何child bytes前冻结field-disjoint `SourceSnapshotProof/replay_root | fork_head`、exact source Run identity、lineage digest、target policy与initial Planner capability inputs。Replay只复制validated immutable root-input snapshot；Fork只引用coordinator CAS接受的latest stable paused/terminal source head上的eligible immutable evidence。Child获得自己的Run/Cycle/Attempt/Transition、ledger、registry、checkpoint与current pointers；source bytes、accepted artifact bytes和protection history保持不变，Human authorization、active Pause与accepted status均不继承。

外部结果Pause还必须引用A05已定义的ExternalOperation core、one-time Pause binding和final evidence，以及A06已确认的resource reservation/settlement；这些control records不改变A03 domain artifact slots。只有消费、Attempt terminal artifact、settlement与active binding release形成exact closure后，checkpoint和后续Transition才能发布。

## A05 已确认的 Code Agent Artifact Contract（尚未实现）

[A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)冻结独立schema `0.1`的`CodeAgentTask`、`CodeAgentExternalResult`、`CodeAgentResult`、`BackendDispatchReceipt`、`WorkspaceManifest`、`WorkspaceSeal`、change manifest与verification results。它们不兼容解释当前`coder_task_packet.yaml`、`code_change_summary.md`或`tests_status.json`。

Task使用`task_id = <attempt_id>:code_task`，绑定exact Run/Case/Cycle/Attempt/Transition、origin、current evidence heads、immutable full Git base revision/tree、normalized read/write/forbidden paths、typed tool/network/filesystem policy、ordered verification specs、A06 budget reference、nullable single-use Human authorization及Host-owned`producer_operation_id`。Task与manifest在Run control/audit namespace中create-new保存，尚不是A03 current `code` artifact。

每个Attempt使用独立`workspace_id`。`WorkspaceManifest 0.1`在physical workspace之前冻结base、backend/runtime、managed-root identity与policy digests；`WorkspaceSeal 0.1`在backend停止且write lease关闭后冻结final tree、change manifest、tool audit和terminal backend evidence。Workspace lifecycle为`prepared -> leased -> running -> sealed -> verified -> released`，由Host append-only记录。Mutable workspace、provider response或thread summary都不是可消费artifact；missing/reused/tampered workspace、foreign lease、base drift或seal后变化均fail closed。

每个完成trusted validation的canonical `code_agent` Attempt注册一个A03 `code` slot bundle，`artifact_id = <attempt_id>:code`，canonical root位于`attempts/<attempt_id>/`。常规`result_origin = backend_delivery`成员固定为：

- `code_agent_task.json`
- `code_agent_result.json`
- `backend_dispatch_receipt.json`
- `workspace_manifest.json`
- `workspace_seal.json`
- `change_manifest.json`
- `verification_results.json`
- `tool_audit.jsonl`
- non-empty change时存在的`changes.patch`

`result_origin = host_timeout`只用于Control Protocol指定的recoverable safe timeout：它包含task、failed result、workspace manifest、`interrupt_evidence.json`、empty change manifest及逐spec `not_run/operation_timeout` results，并按dispatch phase引用真实receipt或typed absence；不得伪造seal、tool audit或patch。Unavailable stop proof、integrity failure或不完整backend bytes不能包装为`host_timeout` bundle。

`CodeAgentResult.status`只允许`success | no_change | failed | needs_input | needs_human | budget_exhausted | policy_blocked`，不定义`partial_success`。`success`要求non-empty manifest、present patch、完整scope/policy/authorization checks及所有required trusted verification passed，并且`usable=true`；`no_change`要求empty manifest、absent patch与base/final tree exact-equal；其余合法status均`usable=false`。实际越权content属于invalid ingress，不注册canonical artifact；schema-valid、Attempt-attributable且经Host验证的`failed/result_invalid`才可形成canonical failed bundle。

Trusted verifier读取task中typed `VerificationSpec`，在exact base加validated change的fresh workspace运行。每个required spec恰有一个`passed | failed | blocked | timeout | not_run`结果，并记录typed command identity、bounded output digest及produced-file evidence；missing、duplicate、skipped、blocked、timeout或non-passing required result均不能产生usable success。Backend/Agent自报tests和exploratory tool audit不能替代trusted verification。

`success` bundle注册并成为current后，Host为新scheduled Analysis Attempt冻结独立`AnalysisExecutionSpec 0.1`，绑定source Code Agent Attempt、current plan/code artifact及member digests、base、patch、expected effective tree、runtime policy和fresh Analysis workspace identity。Spec是目标Attempt的control/audit input，不是Code bundle member或current artifact。Analysis必须从exact base加verified change重新materialize worktree并在新subprocess中执行，不能复制mutable coding workspace、读取当前control repository或复用provider/tool session。

Artifact pointer status必须exact等于structured result，dependencies至少包含当时current plan及适用的protected Human Response snapshot。A03 invalidation清除bounded current pointer和projection，但保留immutable task、ExternalOperation/workspace evidence、bundle及historical diagnostic bytes；physical workspace仍按Host lifecycle隔离、释放，不能成为长期source of truth。A05不批准把bundle写回control repository，也不批准commit、merge、push、PR、deployment、scientific acceptance或accepted-result promotion。

## B01 Read-only Cross-head Adapter

显式0.4输入由`control.integrity.validate_run_root`读取`execution_history.jsonl`、`artifact_history.jsonl`、`artifact_index.json`和immutable `budget_policy.json`。它验证canonical bytes及policy binding，然后复用A03原有history/index、slot、dependency、current/projection owner、invalidation和protected snapshot校验；没有新增pending-publication例外。

A03 domain artifact schema/七个slots保持0.1原语义。0.4 control envelope为artifact event增加`previous_artifact_head`与当时`execution_head`，index绑定latest `execution_head/artifact_head`。历史chain与execution记录中的artifact pre-head双向验证，stable checkpoint绑定exact pair。Adapter拒绝partial/conflicting publication、旧合法bounded head、跨Run、nullable omission以及通过重算摘要伪装的非法producer/target；返回typed `control_integrity_failure`，不写failed lifecycle或修复文件。该能力不声称能在没有外部immutable anchor时发现任意完整历史的协调重写，与A03C01边界一致。

`artifact_binding`只生成待验证的immutable envelope；A03已有publication函数未被改造成0.4 writer。实际0.4持久化和publication ownership属于B02–B04。B01测试只在新建`/private/tmp/lqcd-agent-b01-*`目录构造证据，不修改existing Runs。

## A06 已确认的 Budget Control Artifact Contract（B01基础已实现，durable接入待实现）

[A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)为每个Phase B schema `0.4` Run冻结：

```text
<run_root>/budget_policy.json
```

`budget_policy.json`是project-owned immutable control artifact，使用独立`BudgetPolicy 0.1` schema。它不属于A03七个current slots，也不接受Agent、tool、Backend、Human payload或compatibility projection覆盖。Canonical digest排除自描述digest字段；Run identity、runtime fingerprint、Pause、bounded state和A05 `CodeAgentTask`必须保存exact version/profile/reference/digest。A05的`budget_envelope_ref/digest`指向允许该Attempt的exact `BudgetDecision` event，不复制mutable remaining counters。

所有policy、reservation、settlement、failure、grant和decision evidence追加到同一Run的`execution_history.jsonl`，不新增可漂移的`budget_history.jsonl`。Execution schema `0.4`的`record_type: budget`使用连续`budget_event_NNNNNN`；grant另有连续`budget_grant_NNNNNN` identity，但创建与消费仍由budget records承载。Records必须绑定policy digest、validated execution/artifact heads、trusted timestamp及event-specific operation/Attempt/Transition/Pause/Human snapshot evidence。

每个project-owned LLM/tool/verification side effect在调用前冻结stable resource operation、maximum charge、timeout、input/config/policy digests与remaining-before，并exactly once结算。每个scheduled Code Agent Attempt只允许一个`code_backend_operation` aggregate，绑定producer operation、task、semantic `code_task_context_digest`、backend/runtime与unmaterialized workspace manifest；它不得预占Pause identity。Pause随后单向绑定exact reservation，Backend receipt/audit/seal/result只提供可信settlement evidence，不能成为第二套counter或refund authority。

`FailureFingerprint 0.1`保存稳定typed cause与`causal_context_digest`，排除Run/Attempt/workspace/job/session identity、timestamp、物理路径、自由文本和原始日志；完整task/manifest/spec digests保留provenance，但重复判定使用排除execution identity的semantic context digests。`BudgetGrant 0.1`绑定validated Human Response snapshot、exact route/fingerprint occurrence/target、actor scope及single-use consumption Transition。A03 current invalidation和accepted-result protection不因budget evidence而放宽；这些control artifacts也不注册为domain result。

## 当前通用规则

以下通用 metadata 规则适用于 domain artifacts；`execution_history.jsonl` 使用上一节按 `record_type` 区分的 ledger contract，不要求把 domain artifact 的 `producer`、`summary`、`warnings` 和 `errors` 无差别复制到每条 identity record。

影响 routing 的 artifact 必须 machine-readable；支持人工 review 的内容应同时 human-readable。JSON/YAML 可以驱动 routing，Markdown 只用于 report 和 summary。

实际 Run root 写入 `<output_root>/<case_id>/<run_id>/`，canonical domain artifacts写入其 Attempt namespace。仓库内 `outputs/` 是 ignored actual-run storage，不是 reference-output storage。curated evaluation baseline 属于 `evaluation/reference_outputs/`，expected behavior 属于 `evaluation/expected_behavior/`。

所有影响 decision 的 artifact 必须包含：

- `schema_version`
- `run_id`
- `case_id`
- `created_at`
- `producer`
- `status`
- `summary`
- `warnings`
- `errors`

## LLM Call Traces

Provider-backed Method Planner, Scientific Reviewer, and Decision Coordinator calls write audit records under:

```text
<output_root>/<case_id>/<run_id>/attempts/<attempt_id>/llm_calls/<agent>.json
```

Each trace records the agent, timestamp, status, non-secret provider metadata, structured request, provider response when available, parsed artifact path, and structured errors. API keys and environment-variable values must never be written. The producing bundle registers trace members; current run-root `llm_calls/` files are managed projections. The final report links canonical current traces for reproducibility.

## Method Plan

`method_plan.json` records:

- `physics_goal`
- `target_observables`
- `method_steps`
- `required_inputs`
- `required_outputs`
- `implementation_gaps`
- `code_needed`
- `coder_task_summary`

When critical planner inputs are missing, `method_plan.json` uses `status: needs_more_info`,
records the missing fields in `errors`, and leaves downstream planning lists empty. Critical
planner inputs are `user_goal`, `case_config`, `case_config.case_id`, and `repo_inventory`.

## Coder Task Packet

`coder_task_packet.yaml` is written only when `method_plan.json` has `status: success` and
`code_needed: true`. It records:

- general artifact metadata
- `task_summary`
- `physics_goal`
- `implementation_gaps`
- `allowed_files`
- `forbidden_paths`
- `requirements`
- `acceptance_criteria`
- `verification_commands`
- `context_artifacts`

The Phase 3 task-packet schema uses `schema_version: "0.1"` and `status: pending`.
Required string fields are `schema_version`, `run_id`, `case_id`, `created_at`,
`producer`, `status`, `summary`, `task_summary`, and `physics_goal`. Required list
fields are `warnings`, `errors`, `implementation_gaps`, `allowed_files`,
`forbidden_paths`, `requirements`, `acceptance_criteria`, `verification_commands`,
and `context_artifacts`. `allowed_files`, `forbidden_paths`, `requirements`,
`acceptance_criteria`, `verification_commands`, and `context_artifacts` must be
non-empty lists.

The packet is a file handoff contract by default. The graph runtime must not call
Codex programmatically unless the run has explicit automatic handoff opt-in. In
automatic handoff mode, the graph invokes the local Codex CLI worker, which must
still respect forbidden paths, allowed files, and verification commands.

## Codex Handoff Results

The Codex Handoff node reads external handoff result files from the run output
directory:

- `code_change_summary.md`
- `tests_status.json`

`code_change_summary.md` is a human-readable summary of the external code change.
It is required before a passing handoff can continue to analysis, but routing must
not be based on markdown content.

`tests_status.json` records:

- general artifact metadata
- `commands`

Each command record includes:

- `command`
- `working_directory`
- `timeout_seconds`
- `return_code`
- `stdout`
- `stderr`
- `produced_files`
- `status`

The Phase 3 test-status schema uses `schema_version: "0.1"` and `producer: test_runner`.
The top-level `status` must be `tests_passed` or `tests_failed`.
Command-level `status` must be `passed`, `failed`, `blocked`, or `timeout`.

Routing after Codex Handoff uses only the structured top-level `tests_status.json`
`status` field. `tests_passed` plus a present `code_change_summary.md` routes to
Analysis Engineer. `tests_failed`, missing result files, or invalid test status
stops safely before analysis with `pending` or `halted` graph state.

## Synthetic Matrix-Element Artifact

The mock golden example uses structured synthetic matrix elements:

- `z_values`
- `pz_values`
- `matrix_elements`
- `normalization`
- `uncertainties`
- `diagnostic_flags`
- `source_kind: synthetic`

Each matrix-element row should include `z`, `Pz`, `component`, `value`, `error`, and optional flags. MVP diagnostics focus on consistency versus `z` and `Pz`; Fourier transform and matching are documented as future slots, not MVP requirements.

The Phase 9 `l64c64a076_m140` demo may also include a `golden_example` provenance object. This metadata links the synthetic artifact to read-only sibling example files; it is not a claim that the mock artifact contains final physics results.

## Phase 10C Synthetic Benchmark Artifacts

Phase 10C advisor-demo benchmark artifacts were implemented on 2026-06-23 as
synthetic-only contracts. They remain separate from Phase 11 raw-data-backed
reference outputs and must not be treated as accepted physics results.

`evaluation/synthetic_benchmarks/scenarios/*.input.json` records:

- general scenario metadata, including `case_id`, scenario category, and user-facing goal
- synthetic input-data path or generator configuration
- fields that agents may read during the run

`evaluation/synthetic_benchmarks/expected/*.expected.json` records the
instructor-only hidden grading contract:

- expected qualitative conclusion
- numeric tolerances where applicable
- expected risk level and recommended action
- expected graph route and route branch
- required or forbidden reviewer warnings
- expected memory status
- Human Approval Gate expectations

Expected behavior must not be passed to agents as input and must not be used as
the main evidence in `final_report.md`.

`analysis_outputs/synthetic_benchmark_input.json` is the per-run copy of the
agent-visible scenario input. It must not contain instructor-only expected
behavior.

`analysis_outputs/synthetic_data.csv` is the per-run synthetic fixture consumed
by the Analysis Engineer.

`analysis_outputs/fit_summary.json` records case-specific analysis results
produced from the scenario synthetic data:

- general artifact metadata with `producer: analysis_engineer`
- input scenario and synthetic-data references
- model or fit method
- fitted parameters and uncertainties
- fit quality or residual diagnostics where applicable
- warnings and errors

`demonstration_checklist.json` records the per-scenario advisor-demo judgment:

- input understood
- method plan written
- Analysis Engineer consumed scenario-specific data
- analysis command recorded
- fit summary produced where applicable
- reviewer findings grounded in artifacts
- decision reasons structured
- expected conclusion observed
- expected route observed
- Human Approval Gate behavior correct when applicable
- memory status correct
- final report coherent
- actual-vs-expected status and notes

`synthetic_rehearsal_summary.md` is the run-level summary. It must list each
scenario, route path, key fit result, reviewer findings, decision/risk/action,
memory status, artifact inspection paths, advisor checklist status, and
actual-vs-expected status.

`advisor_demo_report.md` is the live-provider demonstration handoff. It must
compare each scenario question, hidden expected conclusion summary, actual
agent conclusion, expected and actual route, expected and actual risk/action,
required or forbidden warnings, memory status, Human Gate behavior, pass/fail
or review-needed status, and links to the supporting artifacts.

## Run Result and Manifest

`run_result.json` is written by the Analysis Engineer under the canonical run directory:

```text
<output_root>/<case_id>/<run_id>/run_result.json
```

It records:

- general artifact metadata
- `run_success`
- `failure_type`, using the existing state values `code`, `config_or_data`, `workflow`, `unknown`, or `null`
- `analysis_outputs_dir`
- `expected_outputs`
- `produced_outputs`
- `validation_results`
- `command_references`
- full command records
- `run_log_path`
- `manifest_path`

Phase 4 validates expected outputs before setting `run_success=true`. Missing expected outputs produce `failure_type: config_or_data`. Failed or timed-out configured commands produce `failure_type: code`; blocked unsafe or unapproved commands produce `failure_type: config_or_data`.

`manifest.json` records provenance:

- `run_id`
- `case_id`
- `created_at` and timestamp
- git commit and bounded status summary
- config hash
- input files
- output files
- commands
- tool versions
- environment summary
- warnings and errors

`run.log` is a plain-text execution log written beside `run_result.json` and `manifest.json`.

Phase 4 analysis outputs are written under:

```text
<output_root>/<case_id>/<run_id>/analysis_outputs/
```

The default mock output is:

```text
analysis_outputs/synthetic_matrix_elements.json
```

The Analysis Engineer refuses to overwrite existing `run_result.json`, `manifest.json`, or `run.log` unless explicit force behavior is enabled by the caller.

## Scientific Review Report

`scientific_review_report.json` records:

- `correlator_diagnostics`
- `fit_diagnostics`
- `matrix_element_diagnostics`
- `findings`
- evidence
- warnings
- recommended checks
- confidence

The Phase 5 schema uses `schema_version: "0.1"` and `producer: scientific_reviewer`.
The report is written under the canonical run directory:

```text
<output_root>/<case_id>/<run_id>/scientific_review_report.json
```

Each diagnostic section records:

- `status`
- `summary`
- `evidence`
- `findings`
- `warnings`
- `recommended_checks`

`correlator_diagnostics` and `fit_diagnostics` remain present for every review. When the
mock MVP has no correlator or fit summary artifacts, these sections use
`status: not_populated_mvp` without creating a warning. `matrix_element_diagnostics`
reviews the synthetic matrix-element artifact for source kind, required fields, finite
values, positive errors, diagnostic flags, simple consistency versus `z` and `Pz`, and
`mock_unit` normalization at `z=0`.

Every warning must include concrete evidence fields:

- `section`
- `code`
- `severity`
- `decision_coordinator_flag`
- `message`
- `path`
- `field`
- `value`

Severe warnings use `severity: severe` and `decision_coordinator_flag: true` so the
Decision Coordinator can treat them as high-risk evidence in Phase 6. Non-severe warnings
use `severity: warning` and `decision_coordinator_flag: false`.

## Decision Log

`decision_log.json` records:

- general artifact metadata with `producer: decision_coordinator`
- `risk_rubric`
- `risk_level`
- `recommended_action`
- `human_approval_required`
- structured `reasons`
- structured `evidence`
- `next_actions`
- structured `routing_decision`

The Phase 6 schema uses `schema_version: "0.1"`. `risk_level` uses the existing
state values `low`, `medium`, `high`, or `critical` after the decision is made.
`recommended_action` is one of the Phase 6 deterministic actions:

- `accept_mock_result`
- `human_review_recommended`
- `pending_human_approval`
- `targeted_rerun`
- `code_fix`

Exactly one `next_actions` entry must use `primary: true`. The route fields in
`routing_decision` are structured and include `actual_route`, `requested_route`,
`proposed_follow_up_route`, and the state fields used for routing intent:
`risk_level`, `recommended_action`, `human_approval_required`,
`rerun_requested`, `rerun_target`, and `code_fix_requested`.
`actual_route` records the Decision Coordinator's immediate graph route:
`human_approval_gate` when human approval is required, otherwise `memory_report`.

Phase 6 risk policy:

- `critical`: required artifacts are missing or unreadable, artifact schema or
  run identity conflicts with the active run, or the method plan is not usable.
- `high`: the run failed and needs a code fix or targeted rerun, or the
  Scientific Reviewer produced a severe or Decision-Coordinator-flagged warning.
- `medium`: the run succeeded, but non-severe warnings, medium review
  confidence, or missing review evidence prevent low-risk acceptance.
- `low`: the method plan, run result, and scientific review all succeeded with
  no warnings and structured review evidence.

Severe warnings must never produce low risk. High and critical risk always set
`human_approval_required: true`. Medium risk must remain pending or
human-review-recommended and must not be written as accepted memory.

## Approval Packet

An approval packet is generated only when `human_approval_required` is true. It is
written under:

```text
<output_root>/<case_id>/<run_id>/approval_packet/
```

The directory contains:

- `approval_packet.json`
- `approval_summary.md`
- `07_human_decision.yaml`

`approval_packet.json` records:

- general artifact metadata with `producer: human_approval_gate`
- `cycle_id`, `human_request_id`, `requesting_attempt_id`, current `attempt_id`, and `parent_attempt_id`
- the request `authorization_scope`
- requested decision
- human-readable summary
- method and run context
- available comparisons
- scientific review report reference
- AI recommendation
- risk rationale
- decision options
- human decision template path

The current approval projection uses `schema_version: "0.2"` and `status: pending`.

`07_human_decision.yaml` is a flat YAML decision file with:

- `schema_version`
- `run_id`
- `case_id`
- `cycle_id`
- `human_request_id`
- `requesting_attempt_id`
- `human_response_id`
- `decision`
- `conditions`
- `reason`
- `decided_by`
- `decided_at`

Supported `decision` values are:

- `approve_with_conditions`
- `approve_rerun`
- `request_code_change`
- `reject_or_hold`

If `07_human_decision.yaml` is missing or has `decision: null`, the Human
Approval Gate remains pending and the request remains open. A non-empty 0.2
decision must match the active Run, Cycle, request, requesting Attempt, and
control-plane-assigned response ID. Invalid decision files append an invalid
response lifecycle record and leave the request open. A worker Agent does not
rewrite an identity-bound human decision. The control plane refreshes the fixed
current template to `decision: null` when a new request replaces the previous
request, and the external submission path writes the response projection.

Schema 0.1 is not auto-bound to the active request. It can only be parsed by an
explicit legacy-import caller that supplies the missing identity bindings and
proves that the ledger has exactly one matching open request. A validated 0.2
response is single-use: its frozen decision, logical route, exact Transition
route/target, validation Attempt, consuming Gate Attempt, authorized target
Attempt, and satisfied request are recorded in `execution_history.jsonl`.
Duplicate submission or consumption is rejected and must not change counters,
append ledger records, create a new target Attempt, or rewrite memory/report
artifacts. Network-delivery idempotency keys and replay semantics are frozen by
A04 as a target contract but are not implemented by the current demo API.

The current demo still follows the Phase 7 compatibility topology:
`request_code_change` transitions directly to legacy Codex Handoff,
approve/reject reporting decisions transition directly to Memory Report, and
`approve_rerun` consumes the response but records intent and ends pending rather
than executing Analysis Engineer. The graph still declares an Analysis Engineer
compatibility target for the Gate, but the current selector does not execute that
target for `approve_rerun`. None of this is the A01 target contract, where a
valid Human response must return to Decision Coordinator. A04 has frozen durable
PAUSE/resume semantics, while A07/Phase B owns their runtime and product-route migration.

## Final Report and Memory Update

`final_report.md` contains metadata, method summary, run summary, scientific review, warnings, decision status, approval status, next actions, and reproducibility notes.

Memory updates are categorized as accepted, pending, or rejected. High and critical risk outcomes require human approval before accepted memory can be written.

In Phase 8, low-risk `recommended_action: accept_mock_result` writes accepted
memory when no human approval is required. Medium outcomes write pending memory.
High and critical outcomes write an approval packet and may continue to the
Memory and Report Node only to write pending `memory_update.json` and
`final_report.md` artifacts. They must not write accepted memory until a valid
human decision permits it. A valid `approve_with_conditions` decision can write
accepted memory, while a valid `reject_or_hold` decision writes rejected memory.

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [State Schema](STATE_SCHEMA.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)

## B02C01：Legacy replay provenance（2026-09-18）

合法0.2 replay在新child lineage中如实记录source fingerprint未记录：`{"availability":"not_recorded","reason":"legacy_schema_0_2"}`。该值只存在于source proof与相等的source lineage字段，不能用作target/Pause fingerprint。原始goal/config bytes先按历史Run-created摘要验证，child再保存canonical `root_goal={"goal": verified_user_goal}`与完整validated config object；不复制旧graph state、checkpoint、approval或accepted状态。Source bytes不回填、不重写。

`pre_a06` proof结合受支持的closed Run-created、同Run旧schema records、policy文件不存在及无冲突versioned authority，并冻结source creation与ledger bytes摘要；不能仅凭policy文件缺失降级0.4。详见[B02C01](tickets/phase-b-graph-harness/B02C01_LEGACY_SOURCE_FINGERPRINT.md)和[验证记录](tickets/completions/B02C01_COMPLETION.md)。

2026-09-18 B02进展：normal/timeout消费及Analysis准备通过typed external/domain ports验证控制顺序，synthetic artifacts/receipts不等同A05 canonical Bundle或真实workspace。Historical source Fork检查原selected pointer/member bytes并保持来源不可变；child lineage引用真实历史head。当前B00 trace 0.2不支持该0.3 head引用图，不能将runtime成功写成验收通过，详见[B00C03 review](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)。

## B00C07 approved implementation handoff

2026-09-24：B00C07已按用户同意补强，ready冻结于`7ab58ce`并完成文档交接。B03恢复ready；四个canonical paths来源修复与B02 needs_input fixture窄替换获得明确授权，尚未实现。先推进B03预算事务/失败恢复，再完成canonical实现与28/645验收；当前mapped56/remaining75、Phase B未完成。

详见[B00C07冻结补充票](tickets/phase-b-graph-harness/B00C07_A05_STATE_PROJECTION_GOLDEN_HANDOFF.md)。旧0.2/0.3格式保持原字节，新0.4使用完整nullable path集合与独立status/usable；trace0.5仅修复受来源约束的四个canonical paths，旧trace版本保持。B02材料适配保留原控制断言并使用相同canonical validator；不得将文档交接当作已实现能力。

## B00C08 approved handoff

2026-09-24：B00C08在13f3b74冻结并完成治理交接；B03恢复ready。Normal/timeout完整来源、source trace0.5、独立Analysis success前置及其golden审计范围已批准，尚待B03实现。预算事务与canonical交付未完成，mapped56/remaining75、Phase B未完成。

[B00C08](tickets/phase-b-graph-harness/B00C08_B02_CANONICAL_EVIDENCE_TRACE_HANDOFF.md)明确替代C07受影响source证据不得升级0.5的限制，补齐upstream与safe-timeout材料。迁移source轨迹另存0.5 expected；无成员摘要的phase-only证据仍为0.1。Analysis前置使用独立success/usable bundle，normal needs_input不计canonical Analysis成功。以上为待实施边界。
