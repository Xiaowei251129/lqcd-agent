---
ticket_id: A04
phase: phase-a-control-contracts
status: review
type: design
depends_on: [A01, A02, A02C01, A03, A03C01]
---

# 定义 Pause、Resume、Replay 与 Fork 语义

## Goal

冻结 Run 级 durable Pause、Resume、Replay、Fork 与取消合同，使后续 Phase B implementation tickets 可以直接实现和验证，不再自行补充控制语义。

本 ticket 只确认设计并同步核心 source-of-truth 文档；不修改 runtime、graph、checkpoint backend 或测试代码。

## Why

当前 CLI 只能从新初始 state 启动 Run，Demo 中的部分等待状态依赖手工读取 `graph_state` 后继续，legacy re-entry 也只处理有限计数器。这些行为均不构成可跨进程恢复、可审计、single-use 且 fail-closed 的正式 resume 合同。

A02 已冻结 Run/Cycle/Attempt/Transition identity，A03 与 A03C01 已冻结 artifact registry、execution ledger 及 global-head 完整性。A04 必须在此基础上明确暂停边界、恢复授权、并发声明、崩溃语义以及 replay/fork 的身份隔离，避免 Phase B 将 LangGraph 内部 checkpoint 直接暴露为产品接口。

## Read First

- [`AGENTS.md`](../../../AGENTS.md)
- [`docs/README.md`](../../README.md)
- [`docs/tickets/README.md`](../README.md)
- [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`docs/STATE_SCHEMA.md`](../../STATE_SCHEMA.md)
- [`docs/ARTIFACT_CONTRACTS.md`](../../ARTIFACT_CONTRACTS.md)
- [`docs/SECURITY_AND_DATA_POLICY.md`](../../SECURITY_AND_DATA_POLICY.md)
- [`docs/VERIFICATION_GUIDE.md`](../../VERIFICATION_GUIDE.md)
- [`docs/REPO_CURRENT_STATE.md`](../../REPO_CURRENT_STATE.md)
- [`A01_TRANSITION_MATRIX.md`](A01_TRANSITION_MATRIX.md)
- [`A02_RUN_CYCLE_ATTEMPT_MODEL.md`](A02_RUN_CYCLE_ATTEMPT_MODEL.md)
- [`A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md`](A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)
- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)
- [`Control Protocol 0.4`](CONTROL_PROTOCOL_0_4.json)
- `src/lqcd_agent/graph/analysis_graph.py`
- `src/lqcd_agent/graph/run_graph.py`
- `src/lqcd_agent/demo/server.py`

## Scope

- 冻结项目自有的 `start_run`、`resume_run`、`replay_run`、`fork_run` 与 `cancel_pause` 外部合同，以及内部`publish_pause`与`close_run`publication合同；
- 复用A02C01 `ControlOperation 0.1`冻结所有public mutation的durable journal、operation phase、worker lease和result replay；
- 以tracked [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)作为ControlOperation type/variant、phase、success edge、authority、ownership以及Pause/Run lifecycle edge的唯一机器可读枚举；
- 冻结 Pause identity、append-only lifecycle、Run 状态约束和安全 checkpoint 边界；
- 分离权威control `run_status`与现有领域/workflow `status`，消除terminal `pending`死区；
- 冻结 `human_input`、`external_result`、`recovery_decision` 三类 typed Pause；
- 冻结幂等、原子 claim、崩溃后不确定性和 fail-closed 行为；
- 冻结 runtime compatibility fingerprint 与 pre-A04 Run 处理；
- 区分 replay 与 fork 的 source、identity、输入继承和 artifact 规则；
- 将实现及验收输入明确交给 A05、A06、A07 和后续 Phase B implementation tickets；
- 执行时仅同步本 ticket 指定的核心文档与独立 completion record。

## Non-goals

- 不实现 API、CLI、UI、runtime、graph edge、checkpoint adapter 或测试；
- 不选择或部署生产 checkpoint backend、认证服务或分布式事务系统；Phase B按A02C01实现独立于LangGraph checkpoint的project-owned SQLite coordinator；
- 不实现 Code Agent、自动 timeout、预算、failure fingerprint 或 Phase B harness；
- 不提供 arbitrary state patch、自由 route、raw checkpoint 恢复、force overwrite 或自动 partial-commit repair；
- 不迁移或自动修复 schema `0.2` 及更早的实验 Run；
- 不改变 A01 transition policy、A02 identity、A03 artifact/accepted-result policy 或 provider policy；
- 不执行 live-provider 测试。

## Allowed Files

本 ticket 提升为 `ready` 并执行时，只允许修改：

- `docs/tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md`：仅允许更新 YAML 状态元数据，不向正文追加执行日志；
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`；
- `docs/tickets/completions/A04_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/ARCHITECTURE.md`；
- `docs/STATE_SCHEMA.md`；
- `docs/ARTIFACT_CONTRACTS.md`；
- `docs/SECURITY_AND_DATA_POLICY.md`；
- `docs/VERIFICATION_GUIDE.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

- A01–A03、A03C01 以及 A05–A07 ticket 正文；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/` 和 accepted artifacts；
- graph topology、checkpoint backend、dependency versions、provider 配置、认证与 secrets；
- 已完成 ticket 的原始正文、correction history、milestone 或 tag。

## Terms and Run State Classes

- **Pause**：Run 在安全 checkpoint 边界停止推进，持有一个最新、未消费的 typed `pause_id`，等待可信 Host 提交受约束输入。
- **Resume**：在同一 Run、同一 thread 与已冻结 checkpoint 上消费一次 Pause，并继续原 execution。
- **Replay**：从 source Run 的 immutable root inputs 创建新的 child Run，并从 `START` 重新执行。
- **Fork**：从 source Run 最新 validated paused 或 terminal head 选择可继承的 immutable evidence，创建新的 child Run，并从 `START` 执行。
- **Initializing**：Run identity已由A02C01 coordinator分配，bootstrap bytes正在按合法prefix物化；不得执行graph或对外声明为running。
- **Terminal**：control `run_status`为`completed`、`failed`或`halted`；terminal Run不能resume。
- **Domain status**：现有`AnalysisState.status`表达领域/workflow结果，可以在正常报告完成后保持`success`、`pending`或其他既有值，但不再决定Run是否terminal或可resume。
- **Recovery required**：已接受operation发生结果不确定副作用、缺少预授权事实或无法安全materialize原动作后的terminal control outcome；禁止自动重新执行目标 Attempt或继续原operation，只能在验证 source 后显式 replay/fork或由operator resolution处置。Exact、无副作用且已预计算的publication suffix仍属于`in_progress/materialization_pending`，不是recovery。

Execution schema `0.3`新增权威control字段`run_status = initializing | running | paused | completed | failed | halted`。现有`AnalysisState.status`在Phase B迁移中保留为领域/workflow compatibility字段，不改名、不作为resume authority；`pending`只能出现在该领域字段或typed terminal disposition中，不能成为`run_status`。

稳定映射固定为：coordinator已分配Run但适用bootstrap尚未完整公开时是`initializing`；新Run完成其execution schema适用的bootstrap后是`running`，其中schema `0.4+`必须使用A02C01；只有latest active Pause为`opened`、public paused checkpoint包含该resulting head且全部绑定exact closure时是可resume的`paused`；accept、reject、hold或pending report正常到达`memory_report -> END`均是`completed`，同时保留各自领域结果；control/runtime完整性失败是`failed`；operator取消、budget/security hard stop是`halted`。Claim或cancel ownership已提交而对应running/terminal closure未完成的短暂窗口保留上一条`run_lifecycle`的paused值，但必须绑定in-progress ControlOperation并作为不可resume transitional state查询，不能伪装成稳定paused。只有稳定`run_status: paused`可调用`resume_run`，其余值均不可resume。缺少`run_status`、control/domain字段互相伪造、稳定`paused`但无exact active Pause或terminal head与`run_status`不一致均fail closed。

### Append-only Run lifecycle authority

Execution ledger增加独立`record_type = run_lifecycle`。每条record至少冻结`from_status`、`to_status`、typed reason、触发它的nullable control operation/Attempt/Pause/budget event identity、append前的`previous_execution_head`与当时artifact heads。该record自身的event identity、sequence与canonical digest派生resulting execution head，record payload不得嵌入自己的未来digest/head；下游checkpoint和control record引用该resulting head。Exact lifecycle edges只由 [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)定义；唯一允许的循环是带new Pause identity、new ControlOperation identity及budget admission/terminal reserve单调guards的`running <-> paused`。正常`completed`只由running状态下已经提交的`memory_report -> END`触发；paused Run没有可产生normal END的执行者，因此不存在orphan `paused -> completed`边，只能恢复为running或通过terminal owner进入halted/failed。

`completed | halted | failed`全部terminal且不可逆。A02C01 bootstrap追加`initializing -> running`后，只有包含该resulting execution head的checkpoint与committed start result完整时才能执行Planner；Pause `opened`、`consumed`或`cancelled`必须与相应`run_lifecycle`变化建立exact reference。缺失、重复、非法from/to或terminal后继续追加非audit execution record均fail closed。

Bounded `run_status`只是该append-only lifecycle的受限projection，不是第二套authority。LangGraph checkpoint保存恢复所需projection，但不能通过state patch创建lifecycle变化；query不得因发现投影落后而自动补写history。

### Authoritative terminal publication

所有可验证head上的正常完成、普通runtime failure、policy stop和operator stop都必须使用本节`close_run` terminal publication protocol；graph到达`END`、node抛错、budget decision或bounded state显示terminal都不能单独成为Run terminal authority。普通END、非Pause failure和独立stop使用`operation_type = close_run`；已经由`cancel_pause`或`resume_run(abandon_and_halt)`持有唯一Pause ownership的路径把相同terminal eligibility/lifecycle/checkpoint/result closure嵌入其冻结phase，并占用同一Run terminal closure ownership，不再创建第二个`close_run` operation。

正常`memory_report -> END`的唯一顺序为：Memory Report Attempt terminal lifecycle及required artifact registration完整提交，随后append具有显式null target tuple的`memory_report -> END` terminal Transition；Host再创建`close_run` operation并验证该END Transition、execution/artifact heads和terminal disposition，append `run_lifecycle(running -> completed)`，持久化包含其resulting head且清空active/pending Pause与control projection的terminal checkpoint，最后提交`close_run` result。END Transition之前不得追加completed lifecycle，terminal checkpoint之前不得返回completed。

非Pause runtime failure必须先提交可用的Attempt failure/abandonment与typed failure evidence，再由`close_run`验证当前完整head，append`run_lifecycle(initializing | running | paused -> failed)`适用的合法边、持久化terminal checkpoint并提交result。Policy/operator stop必须先完成A05/A06要求的termination、settlement或typed stop evidence，再以相同步骤发布`halted`；停止完整性失败在权威heads仍可验证和安全append时发布`failed`，不得伪装为halted。Invalid Human Response容量不足等internal stop必须先提交exact `decision_recorded(halt)`，再由该decision确定性触发`close_run`，不得直接append halted lifecycle。

若execution/artifact/policy authority自身损坏到不能安全验证或append，coordinator将`close_run`标记`failed`并隔离Run，返回typed `terminal_closure = unavailable`；此时不存在新的权威Run terminal status，不得伪造`run_lifecycle`、截断history或以bounded projection制造`run_status: failed`。该控制失败与一个已经完整发布的`run_status: failed`不同；API必须分别报告`operation_status = failed`、`terminal_closure = unavailable`和nullable post-operation `run_status`。

### Run terminal closure ownership and idempotency

Coordinator必须为每个已分配Run维护monotonic `terminal_closure_revision`、nullable single-assignment `terminal_closure_owner_operation_id`、`terminal_trigger_reference/digest`、`terminal_request_digest`、immutable `terminal_disposition_contract`、nullable single-assignment `resolved_terminal_disposition`、immutable `terminal_preclose_contract`、nullable single-assignment `resolved_preclose_heads`与`terminal_closure = pending | committed | unavailable`。这些字段是terminal publication ownership与结果重放authority，不替代execution ledger中的`run_lifecycle`。普通`close_run`与`abandon_and_halt`在reservation时冻结fixed disposition和exact/deterministically derived pre-close heads；`cancel_pause`冻结`confirmed_stop -> halted | failed_stop_integrity -> failed`的typed disposition contract，以及从final cancellation evidence、target disposition和resource settlement解析pre-close heads的typed contract。两个resolved字段只在`terminal_eligibility_verified`由canonical final evidence解析一次，不得由worker自由选择或改写。

可信control plane必须从已有canonical terminal trigger确定性派生internal `close_run` idempotency scope/key；派生输入至少包含`run_locator`、trigger kind/reference/digest、requested terminal disposition或typed unavailable contract、last trusted/expected pre-close execution/artifact/policy/checkpoint heads与policy digest。正常END使用exact terminal Transition作为trigger，runtime failure使用exact failure evidence，policy/budget/operator stop使用exact stop decision/evidence。Authority已无法验证的uncloseable case只能使用先保存在coordinator/quarantine authority中的canonical integrity trigger、last trusted heads及`terminal_preclose_contract = unavailable_by_construction`派生operation；它不声称observed corrupt bytes是合法current head，并在取得Run closure ownership后终止为`operation_status: failed + terminal_closure: unavailable`。调用方、Agent、bounded state或wall clock不能自选key、改变contract或生成第二个trigger。

执行`close_run`的terminal ownership phase，或`cancel_pause`/`resume_run(abandon_and_halt)`的combined-ownership phase时，single-writer coordinator transaction必须同时验证request digest、disposition/pre-close contracts与当时已经可知的expected heads，将空的Run closure owner compare-and-set为该operation并递增`terminal_closure_revision`；embedded tail还要在同一事务中取得exact Pause owner。Cancel不得声称提前知道尚未产生的termination、usage、settlement或post-stop digests；这些值只能按冻结contract在terminal eligibility phase解析。Same trigger/same digest读取或继续同一operation；不同trigger、contract、已冻结expected head或operation竞争同一Run一律`conflict`。Ownership提交后，所有Run execution/artifact/checkpoint mutation都必须CAS exact revision并证明writer是该terminal owner；旧invocation capability、其他ControlOperation和stale worker即使持有未过期lease也一律拒绝，只有owner冻结phase所列的停止、disposition与closure suffix可以继续。Operation terminal为`recovery_required | failed`时ownership tombstone仍保留，不能释放owner后创建第二个close。`terminal_closure = pending`只允许owner operation仍为nonterminal；若owner operation在closure commit前终止为`failed | recovery_required`，必须同时把closure设为`unavailable`并记录typed cause。该值只表示此Run无法再形成新的权威terminal closure，不等同于`run_status: failed`，也不一定表示ledger authority损坏。只有exact materializable prefix可以由同operation的新`lease_epoch`继续。

## Project-owned Control Interface

LangGraph checkpoint、thread configuration 与 serializer 都是内部实现细节。CLI/UI 只能调用项目自有接口，不得接收 raw checkpoint ID，也不得直接调用 LangGraph resume primitive。

```text
start_run(StartRunRequest) -> ControlOperationResult
resume_run(ResumeRunRequest) -> ControlOperationResult
replay_run(ReplayRunRequest) -> ControlOperationResult
fork_run(ForkRunRequest) -> ControlOperationResult
cancel_pause(CancelPauseRequest) -> ControlOperationResult
```

`publish_pause`与`close_run`只允许可信control plane内部调用，不暴露给Agent、model output或任意客户端；它们仍使用与public mutation相同的ControlOperation coordinator、幂等、lease和result replay合同。Internal `close_run(CloseRunRequest)`只接受上一节已存在的canonical terminal trigger和expected pre-close heads，不接受客户端提供的任意status或reason。

### Shared request identity

- `RunLocator` 必须至少包含 `case_id` 与 `run_id`；output root 由可信 Host 配置，不接受 Agent 或恢复 payload 提供的任意路径；
- 所有 mutation 请求必须携带调用方生成的 `idempotency_key`；
- `ActorContext` 由可信 Host 在认证后构造，至少包含 typed `actor_id`、`actor_type` 与 authorization scopes；payload 不能自签或覆盖该上下文；
- Agent、graph node 和 model output 永远无权调用这些控制接口；本地 CLI 只在其进程边界被视为 trusted operator。

### Resume request

`ResumeRunRequest` 必须包含：

- exact `RunLocator`；
- exact active `pause_id`；
- `idempotency_key`；
- trusted `ActorContext`；
- 与 Pause reason 对应的一个 typed resume input。

Typed resume input 只能是 `human_response`、`external_result` 或 `recovery_decision`。请求必须携带其 immutable snapshot/reference 与 canonical digest，并通过 Pause 冻结的 schema 和 authorization scope 验证。请求不得包含任意 state patch、route override、checkpoint ID、thread ID 或 graph command。

`ControlOperationResult`必须区分控制操作结果、权威control lifecycle和领域结果，至少能表达`in_progress/materialization_pending`、`completed`、`already_applied`、`conflict`、`rejected`、terminal `recovery_required`，以及`operation_status`、`terminal_closure = not_applicable | pending | committed | unavailable`、nullable操作后`run_status`、nullable `domain_status`、head和active `pause_id`。`operation_status = failed`不能单独推导`run_status = failed`。

### Other typed requests

- `StartRunRequest`：包含可信 Host 解析后的 immutable root inputs、canonical digest、new Run locator policy、`idempotency_key` 与 `ActorContext`；不能指定现有 Run root、checkpoint 或 parent；
- `ReplayRunRequest`：包含 source `RunLocator`、source root-input digest、`idempotency_key` 与具备 replay scope 的 `ActorContext`；不能覆盖 source root inputs；
- `ForkRunRequest`：包含 source `RunLocator`、source latest validated head digest、显式选择的 eligible artifact IDs、`idempotency_key` 与具备 fork scope 的 `ActorContext`；不能指定旧 checkpoint；
- `CancelPauseRequest`：包含 exact `RunLocator`、active `pause_id`、`idempotency_key`、typed cancellation reason 与具备 cancel scope 的 `ActorContext`。

Start、replay 和 fork 分别建立 `root`、`replay_of` 与 `fork_of` typed lineage。所有请求字段、source validation result 与返回的 child Run identity 都纳入该操作的 canonical request/result digest。

### Durable operation journal and authority split

所有通过认证且schema-valid的public mutation都必须先进入A02C01定义的`<output_root>/.lqcd/control_operations.sqlite`；不能先写Run ledger、checkpoint、Pause、child Run或外部副作用，再补记幂等键。`start_run`复用A02C01已经分配的target Run locator；`resume_run`和`cancel_pause`绑定exact source Run/Pause/opened head；`replay_run`和`fork_run`在coordinator transaction中分配不可变child Run locator。

Graph/control plane内部创建Pause也必须先建立同库`operation_type = publish_pause`的ControlOperation，不能把当前LangGraph invocation或checkpoint task当作durable publication owner。其deterministic idempotency scope/key/request digest绑定Run、source execution/artifact/checkpoint heads、typed reason、requesting/target Attempt、input contract，以及适用的reservation/ExternalOperation core digest；coordinator在任何`pause_prepared` bytes前取得owner和initial `lease_epoch`。相同source proposal只继续同一operation，不同reason/target/scope冲突；public paused checkpoint和closure完整后才提交operation result。Repause使用新的source head与新的`publish_pause` operation，旧Pause或旧operation都不重新打开。

Internal `close_run`同样必须在任何terminal lifecycle bytes前建立ControlOperation并取得Run terminal closure owner。其deterministic scope/key/request digest绑定上一节terminal trigger、disposition contract、pre-close contract和当时已知的expected heads；same trigger只能物化一个operation/closure，任何END、failure、budget或operator路径都不得直接写terminal lifecycle后再补建operation。

每个operation保持五类状态严格分离：

- `operation_status/operation_phase`：一次API mutation的持久进度、ownership和结果重放；
- Run terminal closure ownership/status：该Run是否已有terminal owner以及closure为`pending | committed | unavailable`；
- append-only `run_lifecycle`与其`run_status` projection：Run是否initializing、running、paused或terminal；
- Pause lifecycle status固定为`prepared | opened | claimed | consumed | cancelled`；对应ledger event type固定为`pause_prepared | pause_opened | pause_claimed | pause_consumed | pause_cancelled`，其中`pause_prepared`尚不可见；
- 现有领域`status`：scientific/workflow disposition。

`operation_status`变化不能自行改变`run_status`；唯一例外是持有Run closure ownership的operation在terminal lifecycle前终止时，必须与其terminal status原子地把`terminal_closure: pending -> unavailable`，但仍不能制造failed lifecycle。Worker lease过期不能重新打开Pause，checkpoint中的projection不能创建或取得operation/terminal ownership。读取/query接口可以投影上述状态，但不得因读取、poll或Host启动而创建operation、刷新lease或写入任何Run history。

`operation_status`严格复用A02C01：`accepted -> in_progress -> committed | failed | recovery_required`，后三者均为不可逆terminal tombstone。所有下列非terminal phase都对应`in_progress`；只有`result_committed`使status成为`committed`。Exact durable prefix尚缺预计算、无副作用publication suffix时，query返回`in_progress/materialization_pending`并允许current-epoch worker继续；缺少预授权事实、发生结果不确定副作用或无法安全继续原动作时才终止为`recovery_required`，之后不得推进phase。

Operation type/variant-specific exact phase enum与穷尽success-edge graph只由tracked [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)定义；本ticket不再维护可漂移的第二份phase列表。冻结的分支集合为：`start_run/not_applicable`、`publish_pause/not_applicable`、`resume_run/continue_execution`、`resume_run/abandon_and_halt`、`cancel_pause/not_applicable`、`replay_run/not_applicable`、`fork_run/not_applicable`与`close_run/not_applicable`。Reservation transaction必须把variant写入request digest；未出现在机器合同中的type、variant、phase或edge全部非法。

机器合同同时为每个phase冻结authority、effect class、continuation policy、required evidence和ownership acquisition。Design-time validator必须证明每个ControlOperation success graph全部phase可达、无隐藏cycle、每个nonterminal phase都有穷尽successor且所有合法success path只到达`result_committed`；`failed | recovery_required`只能作为冻结当前phase的不可逆interrupt terminal status，不能伪装成success edge。下文保留各phase的语义、evidence与cross-machine约束说明，但不能扩展机器枚举。

Schema/auth/scope rejection发生在operation acceptance前，不创建operation row；same-key conflict返回已有operation identity但不推进其status/phase。成功的reservation transaction将`accepted`推进为`in_progress + operation_reserved`。任一nonterminal phase都可以在保存typed evidence后终止为`failed`或`recovery_required`，终止时phase冻结在最后成功边界且以后不得推进；不存在从terminal status回到`in_progress`、跨过中间phase或从一类operation phase跳入另一类operation phase的边。

`pause_dependencies_bound`在`external_result`时提交A05 ExternalOperation one-time binding，在其他Pause reason时提交typed `not_applicable` verification，不能跳过phase。`resume_disposition_committed`持久化reservation transaction已经冻结的`continue_execution | abandon_and_halt` variant；普通human/external input和`continue_existing_target`映射前者，RecoveryDecision `abandon_and_halt`映射后者，之后不得换支。Continue branch以`pause_ownership_reserved`取得单一Pause claim owner；abandon branch以一个coordinator transaction和一个`pause_and_terminal_ownership_reserved` phase同时CAS Pause claim owner与空的Run terminal closure owner，不能拆成两个可观察phase。`prestart_records_committed`只存在于continue branch，必须闭合reason-specific target allocation、A03 invalidation、Transition intent与A06 settlement，不能用可选隐藏步骤改变trace。Abandon branch不创建或启动target；其target/resource disposition没有对象时仍提交typed `not_applicable` evidence。`invocation_authorized`只发布绑定operation/Attempt、`lease_epoch`、exact heads与当前`terminal_closure_revision`的invocation-lifetime capability；target仍必须先append A02 `started`才能产生Agent/provider/tool副作用，closure revision一旦变化该capability立即失效。Crash时若不存在`started`或其他副作用evidence，可以继续同一invocation；若`started`后是否执行副作用不确定，则operation终止为`recovery_required`且不得自动rerun。`stable_boundary_committed`只可引用另一个已committed `publish_pause`、已committed `close_run`或不含pending side effect的validated running checkpoint。

`cancel_pause`以一个coordinator transaction和一个`pause_and_terminal_cancel_ownership_reserved` phase同时CAS Pause cancel owner与空的Run terminal closure owner；任一CAS失败时两者都不得变化。其ControlOperation `cancel_intent_committed`始终存在并保存typed `active_external_cancel_requested | external_already_terminal | no_external_operation` classification；后两种不能改写ExternalOperation或伪造cancel intent。`target_disposition_committed`与`resource_disposition_committed`也始终存在：没有target/reservation时分别提交canonical typed `not_applicable` evidence，不能省略phase。`external_terminal_closure_verified`对无ExternalOperation提交typed `not_applicable`；对仍nonterminal或已进入cancellation branch的ExternalOperation必须引用A05 terminal `cancellation_evidence_committed`及`cancelled | failed` status；对ownership前已normal terminal的operation必须引用immutable `terminal_evidence_committed`及`completed | failed` status，并验证其中同等级的termination、lease revocation、verify-empty、bounded drain和post-stop stability closure。两类proof互斥且穷尽，不得改写terminal phase；中间`termination_evidence_committed`不足以推进Pause。`terminal_eligibility_verified`再按冻结contracts只解析一次resolved disposition/pre-close heads，并exact验证final stop integrity、execution/artifact/policy heads与前置dispositions；不能由ExternalOperation terminal status标签单独替代，也不能把ownership时未知的usage或settlement digest伪装成预先冻结值。Replay与fork的child-prefixed phases分别一一复用A02C01 root/policy/ledger/bootstrap/lifecycle/checkpoint durability边界；`source_snapshot_committed`中replay冻结validated root input，fork还必须完成source head与control revision CAS。`terminal_ownership_reserved`只用于standalone `close_run`；两个combined-ownership phases分别证明cancel或abandon embedded tail已原子取得同一Run closure owner。Phase enum、variant、allowed edges、status映射和required evidence不得由Phase B实现自行扩展。

Invocation capability fencing适用于所有target start，不只适用于resume branch：initial Planner和任何committed Transition target都必须在A02 `started`及Agent/provider/tool/workspace副作用前，从可信control plane取得绑定Run/Attempt、exact heads、适用operation/epoch和当前`terminal_closure_revision`的短生命周期capability。Resume把该边界显式持久化为`invocation_authorized` phase；普通source-wrapper可在其已冻结的A02/A03 target allocation/invalidation/Transition前提完整后签发等价capability，但不得新增产品route或改写A02历史records。每个side-effect boundary都重新验证revision/expiry；terminal owner递增revision后，旧capability不能继续调用provider/tool或写workspace/Run bytes。

对`resume_run`和`cancel_pause`，初始reservation transaction必须验证或创建same-key/same-digest operation、冻结resume variant（适用时）、分配initial `lease_epoch`并保存exact Pause/opened-head条件与预计算的下一ledger event identity/digest，但尚不修改Pause或Run closure owner。随后current-epoch worker只能通过上文对应的单一ownership phase执行一个single-writer transaction：continue branch只CAS Pause claim owner；cancel与abandon branch同时CAS exact active `pause_id`/`opened_execution_head`的Pause owner和empty Run terminal closure owner。该事务成功后才允许append`pause_claimed`或cancel intent。任一CAS失败时全部ownership保持不变并返回`conflict`；不能留下半个owner、等待lease后改支或创建第二个claim/terminal owner。

worker lease仅调度同一`operation_id`、exact current `lease_epoch`的materialization：

- 每个由该operation产生的`pause_claimed`、`pause_consumed`、`pause_cancelled`、target allocation/abandonment、`run_lifecycle`、checkpoint manifest和public result都必须冻结或通过canonical closure引用producing `operation_id + lease_epoch + phase_revision`；换epoch takeover后只能以新epoch继续尚未materialize的phase，已存在record保持原producing epoch且不得重写；
- transaction提交前退出，没有claim/cancel ownership，same request可正常重试；
- `resume_run` transaction已提交但`claimed` ledger record尚未append时，operation保持`in_progress/materialization_pending`，只允许同一operation在重新验证opened head未变化后create-new exact预计算record；不得运行graph、Backend、validator或其他外部副作用；
- `cancel_pause` transaction提交后，同一ControlOperation先把exact cancel intent关联到A05 ExternalOperation；只有持有其独立current `lease_epoch`的durable watchdog可以对原Backend operation执行幂等cancel并发布terminal evidence。ControlOperation在opened head未变化且A06 stop evidence闭合后append预计算`cancelled` record；两类lease均只能继续该停止流程，不能dispatch、启动target或创建替代operation；
- ledger record完整后，operation phase只能向前；若后续target allocation、settlement、checkpoint或result publication仅缺少仍可由exact existing evidence与预计算identity确定的无副作用后缀，operation保持`in_progress/materialization_pending`，不得借worker lease重跑Attempt或外部副作用；任何旧epoch worker即使稍后恢复也不能append ledger、刷新workspace lease、调用Backend或提交result；
- coordinator、execution ledger、artifact heads与checkpoint projection的已存在事实全部exact但publication closure未完成时，只有满足上一条materialization条件才能继续。若缺少预授权identity/digest或副作用结果不确定则终止为`recovery_required`；若观察到实际head/digest/identity/tamper矛盾则进入`failed` integrity outcome并隔离。两者都不能创建替代operation或用recovery掩盖损坏。

Bounded state可以保存nullable `active_control_operation_id`、`active_control_operation_status`、`active_control_operation_phase`、phase revision与`active_control_lease_epoch`作为受限projection；每次恢复必须从coordinator读取并与Pause/ledger heads exact-match。它们不进入Agent prompt，也不能替代coordinator查询。

Coordinator还维护每Run单调`source_control_revision`作为public mutation与child-source snapshot的并发guard。该revision只在coordinator接受会改变resume/fork/cancel eligibility的operation ownership或在exact run-lifecycle/head closure同步完成时递增；它是execution head与run status的受限并发projection，不得创建、覆盖或修复ledger事实。Revision与ledger head存在实际矛盾时public mutation全部拒绝并进入`failed` integrity处理；两者各自existing facts exact且同步suffix已预计算时原operation保持`in_progress/materialization_pending`，不满足该条件则终止为`recovery_required`。

## Execution Schema `0.3` and Pause Identity

A04 将 execution schema 从 `0.2` 升级为 `0.3`。每个 Run 维护单调递增的正整数 `pause_index`，并据此分配 Run-local、唯一、无间隙的 `pause_id = pause_NNNNNN`。Pause identity 不能由调用方选择或复用。

Execution ledger 使用 append-only lifecycle：

```text
prepared -> opened -> claimed -> consumed
prepared -> opened -> cancelled
```

### `prepared`

`pause_prepared` event是Pause identity的首次durable allocation，并把lifecycle置为`prepared`；它冻结`pause_id`、`pause_index`、typed reason、requesting/nullable target Attempt、typed input/authorization contract、runtime fingerprint、preparation前execution/artifact heads与canonical state digest。对`external_result`，它还单向绑定此前已持久化且尚未绑定其他Pause的A06 reservation identity/digest与A05 ExternalOperation immutable core contract digest；这些pre-prepared records不能提前分配或猜测`pause_id`。它不包含未来checkpoint identity，不改变`run_status`，也不创建active Pause；prepared-only状态不得对外返回`pause_id`、接受resume、dispatch Backend或执行未来target。

`prepared` resulting head称为`prepared_execution_head`。同一Run一次只能有一个与当前heads exact-match的未完成prepared Pause；相同确定性publication operation可以补齐其checkpoint/opened后缀。已存在facts全部exact且后续identity/digest已预计算的side-effect-free partial保持`in_progress/materialization_pending`；缺少预授权closure或存在副作用不确定性时终止为`recovery_required`；不同identity、different reason/scope、额外execution record或head/digest contradiction进入`failed` integrity outcome。三者均不能另分配第二个Pause。

### `opened`

`pause_opened` event把lifecycle置为`opened`并冻结：

- `run_id`、`case_id`、`cycle_id`；
- `pause_id`、`pause_index`、typed reason；
- exact `run_status = paused`与当时的领域`status`；
- requesting Attempt，以及reason-specific target binding：`external_result`必须绑定状态为`scheduled`、具有唯一committed inbound Transition且尚未`started`的target Attempt；`human_input`与不继续既有target的`recovery_decision`使用显式null target，并冻结claim后允许创建的target kind/action；
- typed input contract 与 authorization scope；
- internal thread identity、exact `prepared_execution_head`与prepared checkpoint identity/digest；
- runtime compatibility fingerprint；
- canonical state digest；
- append 前的 execution ledger head 与 artifact history/index head；该pre-head必须是绑定exact prepared Pause的`run_lifecycle(running -> paused)` resulting head，任何新Pause都不得伪造`paused -> paused` lifecycle record。

`opened` 自身的 event identity、sequence 与 canonical digest 构成 `opened_execution_head`。可恢复 Pause 对外发布后，当前 execution head 必须等于该 resulting head；因此事件不自引用，后续 claim 可以对 exact `opened_execution_head` 执行 compare-and-set。

### `claimed`

`claimed` 事件保留所有 `opened` identity，引用 exact `opened_execution_head`，并增加coordinator中稳定的 control operation ID、operation phase revision、current `lease_epoch`、`idempotency_key`、canonical request digest、trusted actor identity/scopes、typed input reference 与 digest。

### `consumed` and `cancelled`

`pause_consumed` event表示typed resume input已通过claim后的全部必要pre-start control步骤并被不可逆交给exact target/action；它记录claim operation/`lease_epoch`、typed input、target/Transition、settlement与control heads，不记录尚未产生的领域结果，也不得自行分配下一`pause_id`。对继续执行的resume，固定顺序是`pause_claimed -> pre-start allocation/settlement -> pause_consumed -> run_lifecycle(paused -> running) -> resume checkpoint -> target started`；target在running checkpoint完整前不得启动。对`abandon_and_halt`，resume operation先通过combined phase同时占用Pause claim与Run terminal closure owner，再按其冻结branch在consumed后append existing target `abandoned`（如有）与`run_lifecycle(paused -> halted)`，不进入running。`pause_cancelled`只在A05 final ExternalOperation terminal closure proof与Run closure ownership完整后记录operator、取消原因与停止证据，随后按cancel embedded tail追加`run_lifecycle(paused -> halted | failed)`；不能用cancelled伪装为受控halt。

任一必需字段缺失、identity 改变、事件乱序、重复消费、对非 active Pause 操作或多个成功 claim 都必须 fail closed。已 claim 的 Pause 不能再取消、重新打开或由另一请求接管。`recovery_required` 是terminal control operation outcome，不新增可恢复 Run status；claimed operation未形成validated consumed/running-checkpoint closure时，权威`run_status`仍是paused但该Pause已不具备resume eligibility。可确定materialize的前缀查询返回`in_progress/materialization_pending`，副作用结果不确定或缺少预授权时返回terminal `recovery_required`；target不得在这个过渡窗口被重复运行。

Bounded graph state增加`run_status`受限projection、nullable pending Pause projection与nullable active Pause projection：counter、`pause_id`、reason、lifecycle status、requesting Attempt、target Attempt和typed scope，并保存上一节规定的nullable active ControlOperation projection。prepared checkpoint只能包含pending projection且active字段全部为空；public paused checkpoint必须清空pending并保存exact active opened projection。稳定`run_status: paused`必须与execution ledger中最新`opened`且未claim/cancel的Pause、public checkpoint及coordinator ownership exact-match。Claim/cancel ownership提交后旧public checkpoint可以仍含opened projection，但recovery/query必须以coordinator ownership和任何已materialize的newer `pause_claimed`/`pause_cancelled` ledger fact派生不可resume的transitional state，不能把stale checkpoint projection当authority；resume或terminal checkpoint再清空active Pause。无active或transitional Pause时所有active字段必须显式为空。现有领域`status`不得覆盖`run_status`或把terminal `pending`伪装成可resume状态。

Schema `0.2`及更早的实验Run不可resume或fork，也不自动迁移；只有root inputs仍可完整验证时才允许显式replay。Schema `0.3` Run是否能由其原runtime resume取决于exact fingerprint support；Phase B `0.4`不原地resume/migrate它，但其latest paused/terminal source head满足本ticket fork验证规则时允许显式fork，否则只允许replay。

## Safe Pause Publication Boundary

Pause 只能发布在安全 checkpoint 边界：requesting Attempt已经形成可暂停的typed outcome；若reason要求既有target，则该Attempt identity已分配但`started` event尚未写入且target node没有业务副作用；`human_input`使用null target时，Pause发布不得预分配或执行未来validator，claim后仍必须按A02在任何target side effect前完成唯一分配与Transition commit；null-target `recovery_decision`只允许halt且始终不得分配target。

发布顺序必须是：

1. coordinator reserve/verify exact `publish_pause` operation与current `lease_epoch`，随后runtime确定性派生Pause identity；`external_result`验证并复用A02已提交的唯一scheduled target Attempt，nullable-target reason验证target为空和allowed target/action contract；
2. append `pause_prepared`，首次durable allocation该identity，但不创建active Pause；
3. 对`external_result`，coordinator同时验证publish-pause与ExternalOperation各自current epoch，以fenced one-time compare-and-set把ExternalOperation的nullable Pause binding闭合到exact `pause_id`、prepared event和reservation；随后internal checkpointer持久化pending-Pause state与exact `prepared_execution_head`，返回prepared checkpoint identity/digest；
4. append引用prepared event的`run_lifecycle(running -> paused)`；所有新Pause都必须来自running安全边界，不允许`paused -> paused` no-op lifecycle；
5. append `pause_opened`，绑定prepared event/checkpoint、ExternalOperation one-time Pause binding（如适用）、runtime fingerprint、state digest、pre-execution head与artifact heads；
6. internal checkpointer持久化public paused state，清空pending projection并包含exact `opened_execution_head`；
7. 仅在public checkpoint、opened/lifecycle records、artifact registry、bounded state和适用control operation形成下述非对称exact closure后，Host才返回public `pause_id`。

非对称exact closure固定为：prepared event引用其append前heads；prepared checkpoint引用prepared resulting head；running-to-paused lifecycle引用prepared event；opened引用prepared checkpoint及其append前head；public paused checkpoint引用opened resulting head。不得要求prepared checkpoint提前包含未来opened head，也不得让opened反向引用尚未生成的public paused checkpoint。

等待期间不提交 `END`。允许写入显式标记为 audit-only 的暂停证据，但不得写入 Memory Report、accepted memory 或其他代表已接受业务结果的 artifact。prepared-only、缺少任一checkpoint/opened/lifecycle binding、跨文件partial commit或orphan checkpoint都不可resume；同一publication operation只在closure identity/digest已预计算且现有facts exact时保持`in_progress`并补齐side-effect-free后缀，否则终止为`recovery_required`或在完整性冲突时`failed`。

## Typed Pause Reasons

| Reason | Typed input | Required frozen scope |
|---|---|---|
| `human_input` | `human_response` | exact Human Gate/request identity、null target、claim后只允许A02 Human validation control path、single-use authorization scope |
| `external_result` | `external_result` | producer contract、target Attempt、A06 pre-prepared resource reservation、artifact kind/path/digest 与允许的 ingress schema |
| `recovery_decision` | `recovery_decision` | failure/error identity、reason-specific existing或null target、`continue_existing_target | abandon_and_halt` action |

`human_input` Pause不预分配未来Human Gate validation Attempt。Claim成功后，control plane才按A02 Human Response顺序提交exact external control Transition并分配一个scheduled validation Attempt；随后append old `pause_consumed`、`run_lifecycle(paused -> running)`和resume checkpoint，最后才能启动validator。这不是`human_gate -> human_gate`产品Transition。无效Human Response发生时旧Pause早已永久consumed；本次validator Attempt按A02 lifecycle终结且request保持open。只有A06 admission证明下一次validation和完整terminal tail仍有容量时，才从新的running安全边界分配使用null target的新`pause_id`，且下一份response成功claim前不创建下一validation Attempt；容量不足时从running形成typed stop decision并由deterministic `close_run`发布`halted`，不发布无法安全消费的新Pause。旧Pause不重新打开，single-use authorization不继承。

Invalid Human Response终结validator Attempt后的durable顺序固定为：

```text
validate latest execution/artifact/checkpoint heads, finished validator and still-open Human Request
-> derive the deterministic next_pause_id without publishing it
-> append A06 decision_recorded(allow_repause | halt)

allow_repause:
-> append new pause_prepared
   first durable allocation of the derived next_pause_id
   freeze source_execution_head = decision_recorded resulting head
-> persist the pending-Pause prepared checkpoint
-> append run_lifecycle(running -> paused)
-> append new pause_opened
   bind prepared resulting head, prepared checkpoint and lifecycle pre-head
-> persist the public paused checkpoint containing the new opened resulting head
-> validate the asymmetric checkpoint/state/execution/artifact closure
-> publish the new pause_id

halt:
-> derive/reserve close_run from this exact decision_recorded resulting head
-> reserve the Run terminal closure owner
-> verify terminal eligibility and exact pre-close heads
-> append run_lifecycle(running -> halted, reason = validation_capacity_exhausted)
-> persist and validate the terminal checkpoint/head
-> commit the close_run result
-> publish no new Pause
```

`decision_recorded`必须绑定已consumed old Pause、finished validator Attempt、open request、derived next Pause identity和terminal-tail计算，但该derived identity在`pause_prepared`前仍未分配。新`pause_prepared`是next Pause identity的首次durable allocation；prepared checkpoint只含pending projection，`run_lifecycle(running -> paused)`绑定prepared event，新的`pause_opened`绑定checkpoint与lifecycle pre-head，public paused checkpoint再包含opened resulting head。Halt branch的decision resulting head是唯一terminal trigger，必须复用本ticket的`close_run` ownership/idempotency/phase graph。任一中间崩溃都不重新打开旧Pause；同一operation对预计算且仍exact的side-effect-free suffix保持`in_progress/materialization_pending`，缺少预授权或存在副作用不确定性时终止为`recovery_required`，实际冲突进入`failed`，且不得补写第二个Pause、重新执行validator或直接绕过`close_run`追加terminal lifecycle。

`RecoveryDecision 0.1`首版只允许两个typed actions：

- `continue_existing_target`：Pause必须绑定existing scheduled target、唯一committed inbound Transition、完整current heads，并证明该target从未`started`、没有业务副作用、没有unsettled resource或外部operation；claim后只能启动该exact target一次；
- `abandon_and_halt`：可以绑定existing scheduled target或null target；claim后将existing target按A02写为`abandoned`（如有），Run转为`halted`，不得创建新Attempt、Transition或domain artifact。

`recovery_decision`不能提交route override、改写state、重试不确定side effect、创建替代target、退款或修补partial commit。Replay与fork只能分别调用`replay_run`/`fork_run`并创建新Run；`recovery_required` outcome本身不能通过打开新的`recovery_decision` Pause变回可resume状态。Null-target recovery只允许`abandon_and_halt`。

`approve_rerun` 表示同一 Run/Cycle 内创建新的 Analysis Attempt，不是 replay 或 fork。只有 replan 才创建新 Cycle。授权只对 Pause 冻结的 exact action、target 和输入有效，不能扩大到后续 Pause。

## Idempotency, Claim and Crash Semantics

- `idempotency_key` 与完整 canonical request digest 绑定；
- 同一 key、同一 request 返回同一个 control operation result，不重新执行；
- 同一 key、不同 request digest 必须 conflict；
- 多个不同 key 竞争同一 Pause 时，只有第一个成功原子 claim，其余请求 conflict；
- 上述key、operation和Pause ownership必须由A02C01 coordinator transaction持久化，不能使用进程内lock、checkpoint metadata或先append后补登记；worker lease过期后只允许持有新`lease_epoch`的worker继续同一operation的确定性phase，所有旧epoch写入fail closed；
- `external_result` Pause必须绑定在`pause_prepared`前已持久化的exact resource reservation与A05 `ExternalOperation` immutable contract digest；Pause对外可见后到claim前不得append任何execution/budget record，dispatch receipt与delivery snapshot只能作为不推进execution head的immutable control evidence；
- `external_result` claim必须对exact `opened_execution_head`执行compare-and-set；claim成功后、target Attempt `started`前才允许append该reservation的exact settlement。claim后settlement的existing evidence exact、settlement bytes已预计算且仅无副作用publication未完整时保持`in_progress/materialization_pending`；缺少可信settlement evidence或副作用结果不确定时终止为`recovery_required`，实际mismatch/tamper进入`failed`。后两者都不得重新dispatch或启动target Attempt；
- null-target `human_input` Pause claim成功后，target allocation、A03 invalidation与Transition append只有在其identity/digest已由`prestart_records_committed`前置事务预计算、existing records/heads exact且target尚未`started`时才能作为`in_progress/materialization_pending`继续；缺少该预授权或validator副作用结果不确定时终止为`recovery_required`，实际identity/head conflict进入`failed`。同key重试不得再分配第二个Attempt或第二条Transition；null-target `recovery_decision`不得分配target；
- claim 之后 runtime 不得因客户端重试、进程重启或超时自动重新执行 target Attempt；
- claimed operation的查询、takeover与same-key重试必须按下列互斥优先级分类，不能再使用“consumed/result尚未完整”作为单独的recovery条件：
  1. exact `result_committed`及其closure已存在时返回原committed result；
  2. checkpoint、state、execution ledger、artifact registry、policy或identity存在实际mismatch/tamper时进入integrity outcome；权威heads仍可验证并安全append时由唯一terminal owner发布`run_status: failed`，authority自身不可验证/append时返回`terminal_closure = unavailable`且不得伪造Run status；
  3. 缺少预授权identity/digest、必须重新求值decision，或`started`/provider/tool/Backend等副作用是否发生无法证明时终止为`recovery_required`，不得重新调用node；
  4. 除缺失publication suffix外所有existing bytes/identity/heads exact、suffix已预计算且补齐不产生副作用时保持`in_progress/materialization_pending`，只能由同operation/current epoch补齐。
- terminal `recovery_required` claimed source只有在latest heads可完整验证后才能作为显式replay来源，或在另有validated paused/terminal head时作为fork来源；原Run不恢复执行。

底层的 compare-and-set、事务或锁实现由 Phase B 选择，但实现必须满足以上单一成功 claim 和稳定重放结果，不得降低为进程内 best effort。

## Runtime Compatibility Fingerprint

Version compatibility固定为：

| Execution schema | Contract meaning | Phase B schema `0.4` behavior |
|---|---|---|
| `0.2` | A02 legacy创建顺序与legacy `status: running`，没有A04 Pause/run-lifecycle authority | 不原地resume或补写；source通过验证时只可replay为新Run |
| `0.3` | A04 Pause、run-lifecycle与compatibility fingerprint的语义版本，不包含A02C01/A06完整bootstrap和budget coordinator | 不原地resume、迁移或把`status`重解释为`run_status`；source通过验证时只可replay/fork为`0.4` child |
| `0.4` | 保留A04语义并增加A02C01 bootstrap、A06 policy/budget与完整coordinator合同 | 只resume exact supported `0.4` schema和runtime fingerprint |

Schema `0.3`合同本身不是“不可恢复”的定义：显式实现并在fingerprint中声明支持`0.3`的runtime可以处理自己创建的`0.3` Pause。Phase B目标runtime只实现`0.4`，因此它拒绝对`0.3`原地恢复；这是一条runtime support/migration边界，不否定A04的Pause语义。

每个 Pause 必须冻结至少以下 compatibility components 的 canonical fingerprint：

- control contract/version；
- application source/build digest；
- graph topology digest；
- state schema version；
- source Run实际execution schema version（`0.3` Run冻结`0.3`，`0.4` Run冻结`0.4`）与artifact schema version；
- LangGraph、checkpointer 与 serializer 的实现及版本。

Resume 前必须 exact-match 当前 runtime 与 Pause fingerprint；缺失、不支持或任一 component 不一致都拒绝 resume。不得 best-effort 恢复或原地迁移。满足source验证条件时，schema `0.2` source只允许replay，schema `0.3` paused/terminal source按A04 fork eligibility允许replay或fork；新child Run记录source与target runtime fingerprints并使用schema `0.4` bootstrap。

## Explicit Cancellation

`cancel_pause` 只允许取消 source Run 最新的 `opened` 且尚未 claim 的 Pause，并要求 exact Run/Pause identity、幂等键、current `lease_epoch`与具备取消 scope 的 trusted actor。取得cancel ownership时必须在同一combined-ownership transaction中同时占用Run terminal closure owner。`pause_cancelled`表示该恢复窗口已由cancel operation永久关闭，必须记录`stop_integrity = confirmed | failed`，且只能在`external_terminal_closure_verified`已引用A05 final `cancellation_evidence_committed`或ownership前已存在的normal `terminal_evidence_committed`后追加；中间`termination_evidence_committed`不能自行宣称Backend cancellation完整。若Pause绑定existing scheduled target，还必须按A02为同一Attempt append`abandoned`，null target则不创建Attempt。固定publication顺序为`combined Pause/Run closure ownership -> cancel intent or already-terminal classification -> final ExternalOperation proof -> pause_cancelled -> abandoned(if any) -> A06 resource_settled(if any) -> terminal eligibility -> run_lifecycle(paused -> halted | failed) -> terminal checkpoint`，并与上文`cancel_pause` phase逐项对应；只有A05/A06证明termination、lease revocation、verify-empty、bounded drain和post-stop stability时选择halted，停止完整性失败在Run authority仍可安全append时选择failed，否则control operation失败且`terminal_closure = unavailable`。中间崩溃时target永不启动；existing evidence exact、各disposition已预计算且只缺无副作用publication suffix时operation保持`in_progress/materialization_pending`并只能由同operation/new epoch补齐；缺少预授权或停止副作用结果不确定时终止为`recovery_required`，实际head/digest/stop-evidence矛盾进入integrity outcome。取消后不得执行graph、Agent、Human authorization或accepted-result写入。

A04 不定义自动 timeout、deadline 或 budget cancellation；这些由 A06 定义，但不得改变 single-use claim、显式取消和 fail-closed crash 规则。

## Child-run Bootstrap Saga

`replay_run`与`fork_run`必须复用A02C01 coordinator、lease fencing、durability profile与schema `0.4+` bootstrap，不得在A04建立第二套child creator。Coordinator transaction在任何child root bytes前固定完成：验证same-key/same-digest operation、分配immutable child Run locator与initial `lease_epoch`、保存canonical child policy bytes/digest，以及冻结typed lineage snapshot/digest。

Child bootstrap使用上文`replay_run`/`fork_run` exact phase enum，并让每个child-prefixed phase一一复用A02C01对应durability边界；其`Run created(initializing)`必须绑定parent operation和lineage snapshot，并在`policy_initialized`前追加exact `lineage_initialized(root | replay_of | fork_of)` record。完成bootstrap records后同样追加`run_lifecycle(initializing -> running)`、持久化包含resulting head的checkpoint，再提交operation result。相同key只返回同一child；changed digest冲突；预计算且exact的partial child root保持`in_progress/materialization_pending`，只能由同operation/current epoch补齐。

Fork coordinator transaction还必须对source最新validated paused/terminal execution head、artifact heads、`run_status`与单调`source_control_revision`执行compare-and-set，并在成功transaction中冻结source snapshot。该CAS只取得snapshot authority，不修改source history或阻止transaction之后合法的source操作；child lineage永远引用已接受的exact snapshot，不能因source后来resume、cancel或归档而漂移。CAS前发现旧head、claimed/uncertain Pause或不同revision必须拒绝且不得创建child root。

## Replay Contract

Replay 仅从 source Run 的 immutable root input snapshot 与 canonical digest 创建新的 child Run，并从 `START` 重新执行。

- child 获得新的 Run root、`run_id`、thread、Cycle、Attempt、Transition 与 parent-link identities，并通过上一节saga从`initializing`进入`running`；
- 不复制 source checkpoint、current pointers、execution/artifact counters、Pause control state或 Human authorization；
- 不继承 approval、accepted 状态、预算消耗或未消费 resume input；
- 不允许 replay 请求修改 root input、provider/security policy、artifact contract 或选择中间 checkpoint；
- source Run、source artifacts 与 accepted artifacts 保持不可变；
- source root inputs 无法完整验证时拒绝 replay。

## Fork Contract

Fork 仅允许使用coordinator transaction成功CAS的source Run最新validated paused或terminal head，并从`START`创建全新的child Run/Cycle/Attempt/Transition identities。不能选择被后续execution/artifact history否定的旧checkpoint或旧current state，也不能在source snapshot CAS失败后先创建child bytes再补记lineage。

Fork 可以显式选择 source head 上仍 validated 的 current/protected artifacts 作为 immutable input evidence，但必须：

- 验证 exact path、digest、provenance、source heads 与 artifact kind eligibility；
- 在 child Run 中记录 child-owned immutable reference/snapshot 与 source provenance；
- 不复制 source current pointers、managed projections、checkpoint control state、Pause、Human authorization 或 accepted status；
- 只把 accepted artifact 作为不可变 evidence，而不把其 accepted 状态或写权限带入 child；
- 保持 source Run 及其 artifact tree 不变。

Fork source head 不是可继续执行的 checkpoint。所有 child execution 都从 `START` 进入，并由新 Run 的 policy 决定如何消费所选 evidence。

仅有 `claimed` 而没有 validated `consumed` 的不确定 head 不属于 validated paused head；若 source 也没有后续 validated terminal head，则只能 replay，不能 fork。

## Downstream Contract Boundaries

- A05 必须把 Code Agent 或其他外部执行结果映射为 `external_result` typed Pause/input，不得建立第二套 resume 机制；
- A06 可以定义 deadline、budget 与 stop decision，但必须保留 A04 的 claim、cancel、compatibility 和 crash 语义；
- A07 必须把本 ticket 的所有 acceptance scenarios 固化为 Phase B harness 验收输入；
- 生产实现、checkpoint adapter、atomic claim storage、CLI/API/UI 和 migration policy 必须分别进入新的 Phase B implementation tickets，不得追加到本 design ticket。

## Deliverables

- Pause/Resume/Replay/Fork/Cancel 的项目级公开合同；
- execution schema `0.3` append-only`run_lifecycle`、`run_status`投影、领域`status`分离与terminal immutability；
- `prepared -> opened`两阶段Pause publication、idempotency、authorization、lease fencing、compatibility和crash semantics；
- replay/fork 的source CAS、A02C01 child bootstrap、identity isolation和artifact inheritance规则；
- 对 A05–A07 与 Phase B implementation tickets 的明确约束；
- 核心 source-of-truth 文档更新和独立 A04 completion record。

## Acceptance Criteria

- 只有`run_status: paused`且具有最新exact active `pause_id`与public paused checkpoint的Run可resume；`initializing`、`running`、`completed`、`failed`、`halted`、prepared-only及伪paused projection均拒绝，领域`status: pending`到达END时映射为`run_status: completed`而不是生命周期死区；
- 三类 typed Pause 均可跨进程恢复且最多消费一次；
- public mutation在写Run/child/Pause/checkpoint前已取得durable operation ownership与current`lease_epoch`，stale owner不能继续写，且active operation projection不能冒充Run或Pause authority；
- 外部接口不暴露 raw LangGraph checkpoint，也不接受 arbitrary state/route patch；
- 重复 key、变更 payload、竞争 claim、错误 actor、错误 Run/Pause 和过期 Pause 都有确定的 fail-closed 结果；
- invalid Human Response在A06容量允许时按prepared/两个checkpoint/opened协议生成新Pause，否则通过run lifecycle安全`halted`；旧Pause与single-use authorization均不复用；
- `human_input` opened时target显式为null，claim后才分配exactly one Human Gate validation Attempt；`external_result` opened时必须绑定already-scheduled exact target；
- `recovery_decision`只接受`continue_existing_target | abandon_and_halt`，且null target只能halt；replay/fork和`recovery_required`不得伪装成resume action；
- `cancel_pause`使existing scheduled target进入`abandoned`并使null target保持null；partial cancel commit不允许target启动或自动repair；
- fingerprint mismatch、schema `0.2`/unsupported `0.3` Run与claimed后不确定崩溃均不能自动resume/rerun；预计算且exact的无副作用partial publication只允许原operation保持`in_progress`并materialize，不能创建第二个operation；
- replay/fork通过A02C01 child saga创建全新child Run identity，source Run和accepted artifacts不变；
- fork只使用coordinator CAS接受的latest validated head，且不继承source current pointers、checkpoint control state、Human authorization或accepted status；
- A05、A06、A07 与 Phase B 无需自行发明另一套控制机制。

## Required A07 and Phase B Scenarios

A07 与后续 Phase B implementation tickets 至少必须覆盖：

- `A04-PAUSE-001`：process退出后，`human_input`、`external_result`与`recovery_decision` Pause都可准确恢复一次；
- `A04-PAUSE-002`：同key同payload、同key不同payload、不同key竞争claim；
- `A04-PAUSE-003`：错误actor/scope、错误Run/Pause、过期Pause、typed payload digest变化；
- `A04-PAUSE-004`：human response按claim → validation target allocation → old pause_consumed → `run_lifecycle(paused -> running)` → resume checkpoint → validator start精确消费旧窗口；invalid result随后按decision → new pause_prepared → prepared checkpoint → `run_lifecycle(running -> paused)` → new pause_opened → public paused checkpoint创建新窗口，或从running安全`halted`；
- `A04-PAUSE-005`：human/recovery nullable-target与external-result preallocated-target两类Pause均验证各自target shape、claim后allocation和partial-commit fail-closed行为；
- `A04-PAUSE-006`：recovery continue/halt、wrong target/action、unsettled side effect、attempt reuse、route override以及用recovery Pause代替replay/fork均有negative scenarios；
- `A04-PAUSE-007`：只有stable exact `run_status: paused`、active opened Pause与public paused checkpoint可以resume；claimed/cancel-owned transitional paused query不可resume，`initializing | running | completed | failed | halted`、prepared-only、伪paused projection、schema `0.2`、Phase B不支持的`0.3`与runtime fingerprint mismatch均拒绝，领域pending report正常终结为`completed`；同时验证显式支持`0.3`的runtime语义与Phase B `0.4` migration policy不被混淆；
- `A04-PAUSE-008`：`pause_prepared`、ExternalOperation one-time binding、prepared checkpoint、running-to-paused lifecycle、`pause_opened`、public paused checkpoint、`pause_claimed`、pre-start allocation/settlement、`pause_consumed`、paused-to-running lifecycle、resume checkpoint、invalid-response repause及结果heads每个publication边界的崩溃，并区分`in_progress/materialization_pending`、terminal `recovery_required`与`failed`；
- `A04-PAUSE-009`：`external_result`在`pause_prepared`前完成A05 ExternalOperation identity stub、task、manifest、exact resource reservation、immutable core与workspace materialization，prepared后以fenced one-time CAS补齐Pause binding；Pause期间dispatch/delivery不推进execution head，claim后settlement先于target `started`，且claim后settlement崩溃三分类fail closed；
- `A04-PAUSE-010`：验证prepared/opened/public checkpoint非对称closure，拒绝checkpoint、bounded state、run lifecycle、execution ledger与artifact registry任一head不一致；
- `A04-PAUSE-011`：replay/fork通过A02C01 phases生成新child identities，source与accepted artifacts bytes不变，child partial prefix只由原operation继续；
- `A04-PAUSE-012`：fork source-control-revision CAS拒绝旧checkpoint、被后续history否定的artifact、非最新source head与竞争source mutation；
- `A04-PAUSE-013`：replay/fork不继承Human authorization、accepted status或active Pause。
- `A04-PAUSE-014`：所有public mutation与internal `publish_pause`/`close_run`先进入独立`ControlOperation` coordinator；逐项验证本ticket冻结的operation type/variant、phase enum、穷尽allowed-edge graph、phase evidence与terminal status映射，并由两个独立process验证same-key replay、changed-payload conflict、single Pause publication/claim owner、lease takeover递增epoch、stale-owner写拒绝、operation/run/domain/Pause状态正交以及coordinator/checkpoint/ledger authority分离。
- `A04-PAUSE-015`：从bootstrap initializing到running、Pause running到paused、resume paused到running及completed/halted/failed terminal的append-only run lifecycle可完整重放；normal `memory_report -> END`、普通non-Pause runtime failure、independent confirmed halt与uncloseable integrity failure遵守唯一`close_run` operation trace，cancel/abandon则只能使用其已占用同一Run closure ownership的embedded tail；uncloseable只返回`terminal_closure = unavailable`且不伪造Run failed lifecycle，非法from/to、terminal后继续和bounded projection伪造全部fail closed。
- `A04-PAUSE-016`：`resume_run`在reservation时冻结`continue_execution | abandon_and_halt` variant；continue branch只取得Pause owner并经过prestart/running/checkpoint/invocation，abandon branch以单一combined-ownership phase原子取得Pause与Run closure owner，再经过consumed/target-resource disposition/terminal eligibility/embedded terminal tail，且绝不进入running或启动target；未列出的跨支、回退、半ownership或跳phase全部拒绝。
- `A04-PAUSE-017`：每个Run只有一个terminal closure owner；END、runtime failure、budget/policy/operator stop使用由canonical trigger和pre-close contract派生的same-key `close_run`，cancel与`abandon_and_halt`使用同一ownership的embedded tail；ownership递增Run closure revision并拒绝所有非owner/stale invocation写入，cancel只在final evidence后解析一次disposition/pre-close heads并经过terminal eligibility，竞争trigger/contract冲突，same trigger exact replay，materializable prefix只由原operation继续，owner operation提前terminal则closure同步变为`unavailable`而不伪造Run status。

## Pre-freeze Review Gate

本 ticket 从 `review` 提升为 `ready` 前必须确认：

- YAML保持`status: review`，直到A02C01与A04–A07完成本轮交叉审查、catalog核验并获得用户最终确认；
- 本 ticket 不含未决设计问题、占位符或内嵌执行记录；
- A01–A03及A03C01均已完成，A02C01 corrective contract已冻结，本ticket的dependency、Allowed Files与Do Not Touch无冲突；
- A05–A07未引入第二套pause/resume/replay/fork机制，并保留本 ticket的required downstream scenarios；
- 所有相对Markdown links和Read First仓库路径有效；
- Phase Overview、`docs/README.md`与`docs/REPO_CURRENT_STATE.md`一致将A02C01与A04–A07标为`review`；
- review diff不包含runtime、test、dependency或provider改动。

## Verification

执行本design ticket时只运行静态、文档与scope检查：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

还必须验证：

- ticket在`ready`之后只变更YAML lifecycle metadata，正文与执行前冻结commit一致；
- A01–A03及A03C01保持`completed`，A05–A07正文未修改；
- Required Documentation Updates已同步，并明确区分“已确认的A04目标合同”与“尚未由Phase B实现的runtime能力”；
- Phase Overview、Docs Index与Current State一致记录A04完成及A05–A07的当时lifecycle状态；
- `docs/tickets/completions/A04_COMPLETION.md`已建立并加入completion index；
- Allowed Files/Do Not Touch与实际diff一致，所有现行Markdown relative links有效；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`和accepted artifacts没有本 ticket产生的diff；
- 不运行runtime、benchmark或live-provider测试，因为本 ticket只冻结设计合同。

## Stop Conditions

- 需要改变 A01 transition、A02 identity、A03 artifact 或 accepted-result 已确认合同；
- 需要选择新的生产基础设施、认证系统、checkpoint backend 或跨存储事务方案；
- 对需要既有target的reason无法把Pause发布限定在target Attempt `started`之前，无法把null-target Human validator allocation限定在成功claim之后、target side effect之前，或null-target recovery必须创建Attempt才能halt；
- 无法保证 single-use atomic claim 或必须依赖自动重跑 claimed Attempt；
- 需要迁移或原地修复 pre-A04 Run；
- replay/fork 必须修改 source Run、继承 Human authorization 或复制 accepted status；
- 实现工作无法放入独立 Phase B implementation ticket。

遇到以上任一条件时停止执行并新开 corrective/design ticket，不修改本 ticket 已冻结正文。

## Required Documentation Updates

- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`
- `docs/tickets/completions/A04_COMPLETION.md`
- `docs/tickets/completions/README.md`
