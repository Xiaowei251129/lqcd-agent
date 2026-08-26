---
ticket_id: A05
phase: phase-a-control-contracts
status: review
type: design
depends_on: [A01, A02, A03, A03C01, A04]
---

# 定义 Graph-managed Code Agent Contract

## Goal

冻结 Fake 与真实 Code Agent 共同遵守的 typed task、external execution、result、change bundle、verification、sandbox 和 authority 合同，使主图可以在不了解具体 SDK、CLI、subgraph 或 provider 内部循环的情况下安全消费代码修改结果。

本 ticket 只确认设计并同步核心 source-of-truth 文档；不实现 Code Agent、产品 graph 路线、sandbox、adapter 或测试。

## Why

当前 `codex_handoff` 是 file-based compatibility path：它生成 task packet，选择性调用当前仓库中的外部 Codex worker，再读取 Markdown summary 与 `tests_status.json`。A02 已明确该 physical node 的 canonical kind 是 `legacy_codex_handoff`，不能直接改名为 `code_agent`。

目标系统需要一个 graph-managed control boundary，而不是让主图直接持有编码工具循环或让外部 worker 修改运行中的控制仓库。A05 必须冻结 immutable task、独立 workspace、content-addressed change set、可信验证和 structured outcome，使 Phase B 可先用 Fake adapter 验证 A01 路线，再由 Phase C 在不改变主图合同的情况下替换为真实 adapter。

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

## Scope

- 冻结 `CodeAgentTask`、`CodeAgentExternalResult` 与 canonical `CodeAgentResult` schema `0.1`；
- 冻结 canonical `code_agent` Attempt、external adapter 与主图的职责边界；
- 冻结每 Attempt 独立 workspace、base revision、path/tool/network policy 与不可突破的安全边界；
- 冻结 content-addressed change bundle、trusted verification evidence 和 code artifact 注册规则；
- 冻结 success、no-change、failure、human escalation 与 budget outcome taxonomy；
- 冻结 A04 `external_result` Pause、dispatch/delivery idempotency 和 crash 行为；
- 冻结 Code Agent result 到 A01 Analysis/Coordinator 路线的 guards；
- 冻结 Fake adapter 必须覆盖的 deterministic scenarios；
- 将产品 Fake、真实 adapter、sandbox 与 graph integration 分别交给 A07 和后续 Phase B/Phase C implementation tickets。

## Non-goals

- 不选择 Codex SDK、Codex CLI、独立 LangGraph subgraph、container、remote sandbox 或其他具体 provider；
- 不实现 Fake/真实 Code Agent、A01 产品 edge、A04 resume API 或 A06 budget manager；
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

主图只看见一个 canonical `code_agent` Attempt 和一个稳定 adapter protocol。具体实现可以是 deterministic Fake、CLI、SDK、受控 subgraph 或远程 worker，但不得改变 task/result schema、A04 Pause、artifact bundle 或 route guards。

第一版 Code Agent 固定为受控 external adapter：

```text
trusted control plane freezes CodeAgentTask
-> A06 admits and reserves the external producer operation
-> A04 opens external_result Pause
-> trusted Host dispatches one isolated adapter operation
-> adapter returns CodeAgentExternalResult
-> resume_run atomically claims the Pause
-> A06 settles the exact reservation before the target Attempt starts
-> code_agent node validates and registers CodeAgentResult bundle
-> resume operation records the consumed Pause outcome
-> A01 guard routes to Analysis Engineer or Decision Coordinator
```

外部 adapter 的工具循环不是 graph event，也无权修改 graph state、execution ledger、artifact registry、Pause lifecycle 或 route。`code_agent` node 只负责消费 exact Attempt-matched result、执行独立验证与 scope checks、注册 canonical artifact 并返回 structured outcome。

## Contract and Identity Version

`CodeAgentTask`、`CodeAgentExternalResult`、`CodeAgentResult`、change manifest 与 verification result 使用独立 schema version `0.1`。它们不把 A03 artifact registry schema 升级为新的版本，也不兼容解释当前 legacy handoff files。

每个 task 使用 deterministic `task_id = <attempt_id>:code_task`，并冻结：

- `run_id`、`case_id`、`cycle_id`、`attempt_id`；
- `attempt_kind = code_agent` 与 physical `node_name = code_agent`；Fake/real差异只记录在adapter identity，不改变graph node；
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
- external producer contract、`producer_operation_id` 与 expected result schema。

Requirements、acceptance criteria、evidence、write scope 与 required verification 都必须非空。所有 nullable 字段必须显式存在。自由文本不能覆盖 typed path、tool、budget、risk 或 authorization policy。

`base_revision` 必须是可信 Host 解析的完整 immutable commit identity，不能是 branch、tag、`HEAD` 或其他可变 ref。第一版不接受 dirty control-repository worktree 作为 base；如未来需要非 committed source snapshot，必须由独立 design ticket 定义 immutable packaging 与 provenance。

Coordinator code-fix Transition必须在A03 invalidation前冻结触发诊断的exact artifact IDs/digests，并通过Transition/task provenance引用它们。Transition之后，这些旧analysis/review/decision artifacts只作为immutable historical evidence读取，不恢复为current，也不成为新code pointer对stale current的隐式依赖。

Repository workspace paths与Run evidence paths属于不同namespace。Evidence refs必须是A03 registry验证过的Run-relative canonical members；Trusted Host只把task明确选择且经过数据政策过滤的evidence复制为read-only context snapshots，并记录source/member digest。Adapter不能读取整个Run root，也不能把context snapshot作为workspace change返回。

## Path, Tool and Data Authority

Trusted Host 必须在 dispatch 前规范化并验证 task policy：

- 所有路径必须是 repository-relative normalized POSIX paths；拒绝 absolute path、空路径、`..`、路径逃逸和 normalization collision；
- `forbidden_paths` 优先于 read/write allowlist；write 必须同时落在 explicit `write_paths` 且不在任一 deny rule；
- symlink、hardlink、submodule、device、socket、Git metadata/ref 与 filesystem mount escape 都不能绕过 scope；
- workspace 只能修改普通文件；adapter遇到unsupported file type、unexpected executable-bit change或未授权binary change时必须在落盘前安全拒绝并返回`policy_blocked`，validator实际观察到此类content时按invalid ingress处理；
- `.git`、raw data、Run outputs、accepted results、checkpoint/control records、secrets、credential files、Human responses 与 provider credentials 永远不可写；
- secrets 不挂载到 Code Agent workspace，network 默认关闭；task payload 或模型输出不能启用 network；
- tool execution使用 Host allowlisted typed argv、working directory、environment keys 和 timeout policy，禁止把自由 shell 字符串直接交给 shell；
- Code Agent 不能生成、修改或解释自己的 authorization、budget、scope 或 verification policy。

`ephemeral_paths`只允许trusted verifier写入明确的cache/temp目录；它不能与forbidden/control/data/accepted路径相交，不能由Agent扩大，必须在最终scope scan前清除，并永远不能进入change manifest或artifact bundle。

Network默认关闭约束的是workspace、tool process与verification process。Trusted Host可以按既有provider policy在sandbox外使用批准的adapter transport，但不得把provider credential挂载进workspace、把通用network tool转交Code Agent或由task payload改变provider/network配置。

Repository instructions 和相关合同文档可以作为只读 evidence。Raw numeric data、accepted-result payload 或非必要敏感 artifact 默认不进入 Code Agent context；若任务确实需要新数据权限，停止并新开安全设计 ticket。

## Isolated Workspace Contract

每个 Code Agent Attempt 必须拥有新的 `workspace_id` 和独立、一次性、不可共享的 worktree/container/sandbox：

- workspace 从 exact `base_revision` 和 `base_tree_digest` materialize；
- 运行前记录 base manifest、workspace implementation、policy digest 与 producer identity；
- 不复用前一 Attempt 的 mutable filesystem、process、module cache、untracked files 或 tool session；
- adapter 无权写 control repository、Run artifact root 或另一 workspace；
- scope validation比较 base snapshot 与最终 filesystem content，不能只信 Agent 声明或 `git status`；
- adapter 完成后 workspace 只作为临时证据源；主图不得把 mutable workspace path 当作结果或长期 source of truth。

成功 change bundle 被用于后续 Analysis 时，trusted Host 必须在 fresh execution environment 中从同一 base重新materialize并应用已验证的 exact content-addressed change set。不得让当前控制进程通过 module reload 继续使用被修改源码。

## A04 External-result Lifecycle

Inbound Transition 先按 A02/A03 分配 `scheduled` code_agent Attempt并清除 code/downstream current artifacts。随后 control plane冻结 task，在该 Attempt `started` 之前按 A04 发布 `external_result` Pause。

Pause 必须绑定 task digest、target Attempt、`producer_operation_id`、A06在`opened`前已持久化的resource reservation identity/digest、expected adapter/result schema、runtime fingerprint、checkpoint、state digest及execution/artifact heads。只有可信 Host 可以把 task交给 adapter或提交结果；Code Agent本身不能调用`resume_run`。

完整`CodeAgentTask`必须在`opened`前以create-new、不可覆盖的方式保存到Run control/audit namespace，Pause绑定其canonical path、owner与digest。它在此阶段不是A03 current `code` artifact。External result到达后，Host同样先创建immutable delivery snapshot并验证owner/path/digest，再把该snapshot reference放入`resume_run`；mutable provider response或workspace path不能直接作为resume input。

Dispatch/delivery 必须满足：

- 一个 Pause 只绑定一个 stable `producer_operation_id`；
- 同 operation ID 和 task digest 的重复 dispatch 返回同一 job/result identity，不创建第二 workspace execution；
- 同 operation ID 不同 task 或同 Pause 不同 operation ID 必须 conflict；
- dispatch receipt、workspace identity 与 external result digest 持久化后才能提交 resume；
- dispatch receipt与delivery snapshot位于immutable control/audit namespace，在Pause claim前不append execution/budget record、不改变bounded graph state或A04 `opened_execution_head`；
- dispatch outcome 不确定时不得自动启动第二个 adapter operation；Run 保持 paused，直到 exact result 到达、operator 显式取消，或 A06 后续定义的 policy 触发受控升级；
- `resume_run` 只接收 immutable `CodeAgentExternalResult` snapshot/reference 与 digest，不接受 workspace path、state patch 或 route；
- claim 后崩溃、重复 delivery 与 head mismatch 完全遵守 A04，不建立 Code Agent 专用 resume/retry入口。

Resume在claim前必须完成delivery envelope的duplicate-key、schema、identity、owner、path、digest、member-shape和reservation/usage preflight。Claim必须对exact A04 `opened_execution_head`成功；随后在target code_agent Attempt `started`前append exact `resource_settled`。Claim后settlement失败或崩溃返回`recovery_required`，不得重新dispatch或启动target Attempt。Settlement完整后，target code_agent Attempt只`started`一次；该node materialize已通过preflight的change，运行trusted verification/scope checks，计算canonical result，注册bundle，然后写terminal Attempt lifecycle，不再次Pause。若结果表达`needs_input`或`needs_human`，先完成当前Attempt并交给Coordinator，由Coordinator按A04建立新的`human_input` Pause。

## `CodeAgentExternalResult` and Trust Boundary

Adapter 返回的 external result 是 untrusted ingress，即使来自本地 Fake 或签名 provider也不能直接成为 current code artifact。它至少包含：

- exact task/execution/base/workspace/producer identities 与 digests；
- declared result status、change manifest、change blobs/patch和tool audit references；
- adapter执行的verification claims、resource usage、warnings、errors与failure evidence；
- adapter type/version和result canonical digest。

Trusted code_agent node必须重新验证 schema、identity、path containment、base-to-result content、member digests、scope、authorization和budget envelope。Required verification由trusted verifier在materialized result workspace中重新运行；adapter自报“tests passed”只能作为audit evidence，不能满足route guard。Canonical `status`、`usable`、`failure_class`和`retryability`必须由trusted validator根据validated change、policy和verification evidence计算或约束，不能直接复制adapter声明。

Malformed、duplicate-key、identity mismatch、digest mismatch、path escape或无法完整验证的external result不能注册为合法`CodeAgentResult`。这些问题在preflight发现时拒绝claim并保持原Pause；如果只有claim后才发现且无法证明结果heads完整，则按A04返回`recovery_required`，不得自动重跑Attempt。不得把invalid payload静默规范化为success、复用旧bundle或让Agent选择fallback route。

Adapter若在自身边界发现内部输出无效，可以返回一个schema-valid、无usable change的`failed` envelope，并使用`failure_class = result_invalid`；该可信可归属的failure evidence经Host验证后才可形成canonical failed bundle并交给Coordinator。它与把malformed ingress规范化为合法结果不是同一行为。

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
| `policy_blocked` | adapter在产生违规change之前安全拒绝了违反policy/scope的请求 | 只能进入Decision Coordinator |

不定义模糊的`partial_success`。只要change非空但required verification失败或不完整，结果就是`failed`；change evidence可以保留为audit-only，但`usable=false`且不能进入Analysis。

`policy_blocked`只表示安全的pre-change拒绝。External payload实际包含out-of-scope member、path escape、forbidden target或其他违规filesystem content时属于invalid ingress：不注册canonical code artifact；claim前只记录control rejection evidence并保留Pause，claim后无法形成完整validated heads时按A04进入`recovery_required`。

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
- `workspace_manifest.json`：base/workspace/adapter/policy identities；
- `change_manifest.json`：按path排序的change entries；
- `verification_results.json`：task中每个required spec的trusted result；
- `tool_audit.jsonl`：经过redaction的bounded adapter tool audit；
- `changes.patch`：仅在change manifest非空时存在，并与manifest/blob digests交叉校验。

`tool_audit.jsonl`由adapter wrapper而不是模型文本生成。每个真实tool invocation使用从1连续的`tool_event_index`，并绑定task/workspace/tool identity、typed argv digest、cwd、start/end、status、affected paths、bounded output digest和resource usage；缺失、重复、乱序或identity变化使result无效。零tool-call outcome允许空audit file，但其digest仍必须被result引用。

每个 change entry 至少冻结 normalized path、`added | modified | deleted`、before/after SHA-256、file mode和content/blob identity。Member path、digest、size、status-required member set与producer Attempt必须由A03 registry验证。`code_agent_result.json`必须引用task、workspace、change、verification和tool-audit digests，但不自引用整个bundle digest。

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

## Fake Adapter Contract

Fake与真实adapter必须接收相同`CodeAgentTask`并产生相同`CodeAgentExternalResult` schema；Fake不能通过直接patch graph state、跳过A04 Pause、伪造trusted verification或写canonical bundle来获得捷径。

Fake fixtures由scenario ID选择，scenario只能由test harness/trusted Host配置，不能由Agent task自由文本触发。每个fixture必须有固定base、change members、digests、tool audit、usage和declared outcome，并经过同一个production validator、trusted verifier接口与artifact registration path。

A07至少为Fake adapter冻结以下scenario classes：

- valid `success` scoped change；
- `no_change`；
- tool/workspace `failed`；
- required verification failed、blocked和timeout；
- `needs_input`、`needs_human`和`budget_exhausted`；
- safe pre-change `policy_blocked`，以及实际scope/path/symlink violation导致的invalid ingress；
- malformed/duplicate-key、wrong Attempt/task/base/workspace/result digest；
- external dispatch/delivery duplicate、conflict和claim后崩溃；
- change存在但verification不完整，确认不能作为partial success进入Analysis。

## Legacy Compatibility

当前`legacy_codex_handoff`、`coder_task_packet.yaml`、`code_change_summary.md`与`tests_status.json`继续保持原合同。A05不迁移历史Run、不把legacy artifact转换为schema `0.1` Code Agent bundle，也不让legacy physical node产生canonical `code_agent` Attempt。

Canonical Code Agent只允许出现在实现A04 Pause lifecycle的新Run中：本ticket冻结时的基础版本为execution schema `0.3`，A06定义的`0.4`是保留该Pause合同的明确后继版本；其他未知或不支持版本fail closed。不能向pre-A04或正在运行的legacy Run附加code_agent Attempt；符合A04 source validation时，只能显式replay/fork到新child Run后使用新合同。

Phase B product topology可以在显式implementation ticket中选择保留legacy route作为compatibility path或停止新Run使用它，但不得静默让两套result contract共享同一个route guard。

## Downstream Contract Boundaries

- A06定义budget ownership、具体envelope、failure fingerprint、重复失败与stop policy；不得改变A05 status含义或把budget exhaustion当success；
- A07把A01 routes、A04 Pause与本ticket Fake scenarios映射为deterministic Phase B acceptance matrix；
- Phase B implementation tickets实现Fake adapter、schema validator、artifact bundle、A04 integration和product route harness；
- Phase C implementation tickets实现真实adapter、isolated workspace与fresh Analysis materialization；
- patch promotion、repo mutation、PR/merge/deploy必须另开未来ticket，不属于A05–A07执行。

## Deliverables

- versioned Code Agent task/external-result/result schemas；
- external adapter、A04 Pause与Attempt lifecycle合同；
- sandbox、path/tool/data、authorization和immutable base invariants；
- content-addressed code artifact bundle与trusted verification合同；
- structured outcome/failure/retryability taxonomy与A01 route guards；
- Fake adapter scenario inventory；
- 对A06、A07和Phase B/Phase C implementation tickets的明确输入；
- 核心source-of-truth文档更新和独立A05 completion record。

## Acceptance Criteria

- Fake和真实adapter可以在不修改主图routing、task/result schema或artifact contract的情况下替换；
- canonical code_agent Attempt与legacy handoff严格分离，全部identity与A02/A03/A04 heads exact绑定；
- 每次真实执行使用新的immutable-base workspace，不接触control repository或另一Attempt workspace；
- 主图只消费validated content-addressed bundle，不消费mutable workspace或Markdown声明；
- external dispatch/delivery、Pause claim和进程崩溃均single-operation且fail closed；
- scope/path/symlink、policy、authorization、digest或trusted verification任一失败都不能进入Analysis；
- `success`以外的所有valid status进入Coordinator，invalid ingress不能注册为成功artifact；
- change加tests通过不等于科学接受、repo promotion或accepted memory；
- task发现需要扩权时创建新Human authorization与新Attempt，不追溯批准旧change；
- A06/A07及后续实现无需自行发明另一套Code Agent lifecycle或result taxonomy。

## Required A07 and Implementation Scenarios

A07和后续implementation tickets至少必须覆盖：

- Method Planner implementation gap和Coordinator code fix两种task origin；
- process退出后的external Code Agent result准确恢复一次；
- external operation在Pause `opened`前reserve，dispatch/delivery不改变`opened_execution_head`，claim后settlement必须先于target `started`；
- same operation/task重复dispatch、conflicting dispatch、same delivery重复resume和竞争claim；
- success result进入fresh Analysis Attempt，plan/code dependencies和A03 invalidation正确；
- no-change、failed、needs-input、needs-human、budget-exhausted、policy-blocked全部进入Coordinator；
- adapter自报pass但trusted verification failed/blocked/timeout时拒绝Analysis；
- out-of-scope file、path escape、symlink escape、Git metadata、secret/raw/accepted/control target拒绝；
- wrong Run/Case/Cycle/Attempt/Transition/task/base/workspace/pause/result/member digest拒绝；
- non-empty unverified change不能伪装partial success；
- Human授权scope/digest错误、已消费授权或执行中扩权全部fail closed；
- multiple code attempts使用独立workspace和artifact，旧code/downstream不再current但canonical bytes保留；
- Fake和真实contract fixtures通过同一validator、verification和registration入口；
- legacy handoff不能被读取为canonical Code Agent result。

## Pre-freeze Review Gate

本ticket从`review`提升为`ready`前必须确认：

- YAML保持`status: review`，直到A04–A07完成交叉审查并获得用户统一确认；
- 本ticket不含未决设计问题、占位符或内嵌执行记录；
- A04的Pause/external-result合同与本ticket的dispatch、delivery和claim语义一致；
- A06/A07未引入第二套Code Agent budget status、Fake contract、Pause delivery或route authority，并完整保留本ticket的required scenarios；
- dependency、Allowed Files与Do Not Touch无冲突，所有相对Markdown links和Read First仓库路径有效；
- Phase Overview、`docs/README.md`与`docs/REPO_CURRENT_STATE.md`一致将A04–A07标为`review`；
- review diff不包含runtime、test、dependency、provider或sandbox改动。

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
- 需要选择具体provider、SDK、CLI、sandbox backend、dependency或生产基础设施；
- 无法把external execution限定在Attempt-isolated workspace；
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
