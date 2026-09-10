---
ticket_id: A04
phase: phase-a-control-contracts
status: ready
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

- 冻结项目自有的 `start_run`、`resume_run`、`replay_run`、`fork_run` 与 `cancel_pause` 外部合同，以及内部`advance_run`、`publish_pause`、`close_run`与`resolve_external_interrupt`publication合同；
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

所有可验证head上的terminal decision都必须使用唯一terminal publication protocol；graph到达`END`、node抛错、budget decision或bounded state显示terminal都不能单独成为Run terminal authority。普通END、非Pause failure，以及不存在unresolved ExternalOperation时的独立policy/operator/internal stop使用`operation_type = close_run`。存在live ExternalOperation时，operation timeout、hard-limit、policy stop、terminal operator stop或integrity trigger必须使用本ticket的`resolve_external_interrupt`唯一variant，不能预先或随后再创建`close_run`。已经由`cancel_pause`、terminal `resolve_external_interrupt`、`resume_run(abandon_and_halt)`或post-claim external-result消费失败持有唯一Pause/Run ownership的路径把相同terminal eligibility/lifecycle/checkpoint/result closure嵌入其冻结phase，并占用同一Run terminal closure ownership，不再创建第二个`close_run` operation。

正常`memory_report -> END`的唯一顺序为：Memory Report Attempt terminal lifecycle及required artifact registration完整提交，随后由`advance_run`按typed-null target分支append `memory_report -> END` terminal Transition并验证resulting heads；`advance_run`提交后Host再创建`close_run` operation，验证该END Transition、execution/artifact heads和terminal disposition，append `run_lifecycle(running -> completed)`，持久化包含其resulting head且清空active/pending Pause与control projection的terminal checkpoint，最后提交`close_run` result。END Transition之前不得追加completed lifecycle，terminal checkpoint之前不得返回completed。

非Pause runtime failure必须先提交可用的Attempt failure/abandonment与typed failure evidence，再由`close_run`验证当前完整head，append`run_lifecycle(initializing | running | paused -> failed)`适用的合法边、持久化terminal checkpoint并提交result。没有unresolved ExternalOperation的policy/operator stop必须先提交typed stop evidence，再以相同步骤发布`halted`；live ExternalOperation的停止证据与publication则由`resolve_external_interrupt`原子拥有。Termination、write-lease revocation、verify-empty、bounded drain或post-stop stability任一维度为false或unknown时属于`recovery_required + terminal_closure = unavailable`，即使Run heads仍可append也不得发布failed lifecycle。只有完整`safe_stop`之后另有已证明的overage、tamper或违规副作用，且Run authority仍完整可append，才发布`failed`。Invalid Human Response容量不足等internal stop必须先提交exact `decision_recorded(halt)`，再由该decision确定性触发`close_run`，不得直接append halted lifecycle。

唯一stop route由机器协议的`stop_route_contract`先把typed trigger归入有限`trigger_class`，再按reservation前的External上下文选择：显式Pause取消对任何latest opened且cancelable的Pause只走`cancel_pause`，不依赖ExternalOperation存在、缺失或已决议；已dispatch并绑定opened external-result Pause的operation timeout只走`resolve_external_interrupt/recoverable_timeout`；hard-limit、policy或terminal operator stop在live ExternalOperation上走`controlled_halt`，在ExternalOperation `absent | safely_terminal_and_detached | normal_safe_stop_attached_opened_pause`时走`close_run`；clear evidence发布`halted`，已证明overage/tamper/policy violation发布`failed`；live ExternalOperation的proven integrity trigger或normal final proof不可用只走`integrity_failure`；END、non-Pause runtime failure或internal terminal decision只在无unresolved ExternalOperation时走`close_run`。每个trigger class声明完整required context集合，route表必须逐项覆盖且不能重叠；选择后不得用第二个terminal operation补写或替换winner。

若execution/artifact/policy authority自身损坏到不能安全验证或append，coordinator将`close_run`标记`failed`并隔离Run，返回typed `terminal_closure = unavailable`；此时不存在新的权威Run terminal status，不得伪造`run_lifecycle`、截断history或以bounded projection制造`run_status: failed`。该控制失败与一个已经完整发布的`run_status: failed`不同；API必须分别报告`operation_status = failed`、`terminal_closure = unavailable`和nullable post-operation `run_status`。

### Run terminal closure ownership and idempotency

Coordinator必须为每个已分配Run维护monotonic `terminal_closure_revision`、nullable single-assignment `terminal_closure_owner_operation_id`、`terminal_trigger_reference/digest`、`terminal_request_digest`、immutable `terminal_disposition_contract`、nullable single-assignment `resolved_terminal_disposition`、immutable `terminal_preclose_contract`、nullable single-assignment `resolved_preclose_heads`与`terminal_closure = pending | committed | unavailable`。这些字段是terminal publication ownership与结果重放authority，不替代execution ledger中的`run_lifecycle`。普通`close_run`与`abandon_and_halt`在reservation时冻结fixed disposition和exact/deterministically derived pre-close heads；`cancel_pause`在reservation保存machine contract digest，并按`unavailable -> no lifecycle`、`safe_stop + proven overage/tamper/policy violation -> failed`、`typed-null或safe_stop + clear integrity -> halted`、`preexisting winner observation -> no lifecycle`的总函数解析；interrupt固定映射`recoverable_delivery -> running recovery/no terminal lifecycle`、`halted_closure -> halted`、`failed_closure -> failed`、`unavailable_closure -> no lifecycle`。Owner-bearing safe或typed-null路径只在`terminal_eligibility_verified`解析terminal字段；unavailable路径在`terminal_closure_unavailable_recorded`冻结无lifecycle结果；preexisting winner在`resolution_winner_observed`只返回当前winner，不解析或改写Run terminal字段。`terminal_lifecycle_recorded`必须携带resolved disposition与contract digest，不得由worker从任意合法edge中自由选择。

可信control plane必须从已有canonical terminal trigger确定性派生internal `close_run` idempotency scope/key；派生输入至少包含`run_locator`、trigger kind/reference/digest、requested terminal disposition或typed unavailable contract、last trusted/expected pre-close execution/artifact/policy/checkpoint heads与policy digest，以及`external_operation_precondition = absent | safely_terminal_and_detached | normal_safe_stop_attached_opened_pause`及其proof digest。正常END使用exact terminal Transition作为trigger，runtime failure使用exact failure evidence，没有unresolved ExternalOperation的policy/budget/operator stop使用exact stop decision/evidence。Authority已无法验证的uncloseable case只能使用先保存在coordinator/quarantine authority中的canonical integrity trigger、last trusted heads及`terminal_preclose_contract = unavailable_by_construction`派生operation；它不声称observed corrupt bytes是合法current head，并在取得Run closure ownership后终止为`operation_status: failed + terminal_closure: unavailable`。调用方、Agent、bounded state或wall clock不能自选key、改变contract或生成第二个trigger；live ExternalOperation或既有Run terminal owner使`close_run` reservation直接失败。

执行`close_run`的terminal ownership phase、`resume_run(abandon_and_halt)`的combined-ownership phase、interrupt terminal variant或`cancel_pause`的owner-bearing仲裁结果时，single-writer coordinator transaction必须同时验证request digest、disposition/pre-close contracts与当时已知的expected heads，将空Run closure owner CAS为该operation并递增`terminal_closure_revision`；embedded tail还要取得适用Pause owner。Cancel的preexisting-interrupt结果明确不取得上述owners。Cancel/interrupt不得声称提前知道尚未产生的termination、usage、settlement或post-stop digests；这些值只能由A05 final evidence与terminal eligibility解析。Same trigger/same digest读取或继续同一operation；竞争trigger、contract、head或operation一律`conflict`。Ownership提交后，所有Run mutation都必须CAS exact revision并证明writer是terminal owner。Owner operation在closure commit前终止为`failed | recovery_required`时必须同步把closure设为`unavailable`，不得释放owner或制造failed lifecycle；只有exact materializable prefix可由同operation的新`lease_epoch`继续。

## Project-owned Control Interface

LangGraph checkpoint、thread configuration 与 serializer 都是内部实现细节。CLI/UI 只能调用项目自有接口，不得接收 raw checkpoint ID，也不得直接调用 LangGraph resume primitive。

```text
start_run(StartRunRequest) -> ControlOperationResult
resume_run(ResumeRunRequest) -> ControlOperationResult
replay_run(ReplayRunRequest) -> ControlOperationResult
fork_run(ForkRunRequest) -> ControlOperationResult
cancel_pause(CancelPauseRequest) -> ControlOperationResult
```

`advance_run`、`publish_pause`、`close_run`与`resolve_external_interrupt`只允许可信control plane内部调用，不暴露给Agent、model output或任意客户端；它们仍使用与public mutation相同的ControlOperation coordinator、幂等、lease和result replay合同。Internal `close_run(CloseRunRequest)`只接受上一节已存在的canonical terminal trigger、expected pre-close heads及ExternalOperation close-source precondition proof，不接受客户端提供的任意status或reason。

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

### Normal-result stop handoff

`close_run` reservation冻结机器`close_source_contract`的source snapshot与precondition proof。Normal已提交`safe_stop`但尚未交付、Pause仍opened且target仍scheduled时，system stop直接进入同一`close_run/not_applicable`；`terminal_ownership_reserved`在coordinator事务中比较source heads、Pause status/owner、Run owner和normal final revision/epoch/digest，并原子取得Run及Pause disposition owner。它只读normal resolution，禁止把normal改写为interrupt或再次停止Backend。固定后缀为`resource_disposition_committed -> close_source_disposition_committed -> terminal_eligibility_verified -> terminal_lifecycle_recorded -> terminal_checkpoint_committed -> result_committed`。Source disposition将scheduled target记为abandoned、opened Pause记为interrupted，并把settlement/Pause/target/final digest闭包作为detachment证据；无对象时必须使用typed N/A。其它close source的适用prepared/opened Pause也必须在同owner下aborted/interrupted，不能留下可resume Pause。

CAS失败的已reserved contender只记录terminal conflict且不取得任何domain owner；不能改写其request/source digest或复用旧snapshot。内部system-stop重分类保留原trigger digest，并使用绑定所选route和新source revision的派生幂等键；失败contender可留审计tombstone，但同trigger只能有一个取得Run closure ownership的winner。新请求先查询existing stop owner，已有winner则只观察，不派生第二个closure；这不放宽public same-key/different-digest conflict。

若normal CAS先赢，stop消费该safe final并走上述close；若interrupt先赢，只继续原interrupt tail。若resume先取得Pause owner，close CAS无副作用冲突，stop必须在下一可信边界按新source重新分类，不能使用旧snapshot强行detach；若已有cancel/interrupt/close owner，只观察该winner，不创建第二次closure。Close system stop在terminal eligibility结合可信integrity证据解析clear→halted、proven overage/tamper/policy violation→failed。停止条件不因normal domain result成功而丢失。

### Invocation authorization and execution lease

机器`invocation_capability_contract`区分不可变authorization和独立execution lease。Committed producer result激活authorization，不延续producer worker lease；新worker只通过显式领取事务取得单调递增的invocation epoch和expiry，不修改producer tombstone/result。领取或替换expired未启动lease必须同时证明producer activation有效、target scheduled、无started record或side-effect intent、无冲突owner、当前heads匹配授权anchor、Run无terminal owner且closure revision仍匹配。第一次执行先CAS持久化started intent，再append A02 started，最后才允许副作用；崩溃落在intent之后即不能自动接管并重跑。只有同一仍存活worker/current epoch可续期started lease，且不能越过原Attempt/Run预算与deadline。所有旧epoch都被fence；查询不领取或续租。

`advance_run`的Code Agent target授权scope固定为`external_prestart_only`，仅用于绑定Host-owned ExternalOperation；其workspace materialization和dispatch分别验证immutable core、external epoch、Run closure revision、无冲突stop owner及dispatch所需public paused checkpoint，不领取Attempt lease、不写started。`resume_run/continue_execution`在结果claim、settlement及running checkpoint后才授予该target的`attempt_execution` scope，verification和domain artifact publication只能发生在这一边界之后。其它START/Replay/Fork/ordinary target正常领取Attempt lease。Authorization anchor作为不可变provenance保留；初次claim之后的heads只能沿同一invocation验证过的append chain推进，不能接受foreign append或回滚head。

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
- Pause lifecycle status固定为`prepared | opened | claimed | consumed | cancelled | aborted | interrupted | quarantined`；对应ledger event type固定为`pause_prepared | pause_opened | pause_claimed | pause_consumed | pause_cancelled | pause_aborted | pause_interrupted | pause_quarantined`，其中`pause_prepared`尚不可见，`aborted`表示public open前安全终止，`interrupted`表示opened Pause由持有处置权限的terminal interrupt或close_run在完整safe stop后关闭，或claim-owned opened/claimed Pause由同一resume owner在取得Run terminal ownership、完整consumer safe-stop proof及可安全append的Run authority后按消费失败合同关闭；已consumed Pause保持consumed，不得改写为interrupted或quarantined。`quarantined`表示外部停止proof不可用；
- 现有领域`status`：scientific/workflow disposition。

`operation_status`变化不能自行改变`run_status`；唯一例外是持有Run closure ownership的operation在terminal lifecycle前终止时，必须与其terminal status原子地把`terminal_closure: pending -> unavailable`，但仍不能制造failed lifecycle。Worker lease过期不能重新打开Pause，checkpoint中的projection不能创建或取得operation/terminal ownership。读取/query接口可以投影上述状态，但不得因读取、poll或Host启动而创建operation、刷新lease或写入任何Run history。

`operation_status`严格复用A02C01：`accepted -> in_progress -> committed | failed | recovery_required`，后三者均为不可逆terminal tombstone。所有下列非terminal phase（包括同owner消费失败收尾）都对应`in_progress`；只有`result_committed`使status成为`committed`。Exact durable prefix尚缺预计算、无副作用publication suffix时，query返回`in_progress/materialization_pending`并允许current-epoch worker继续；缺少预授权事实、发生结果不确定副作用或无法安全继续原动作时才终止为`recovery_required`，之后不得推进phase。

Operation type/variant-specific exact phase enum、穷尽success-edge graph、terminal outcomes与`operation_reserved` evidence overlays只由tracked [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)定义；本ticket不再维护可漂移的第二份机器列表。冻结的分支集合为：`start_run/not_applicable`、`advance_run/not_applicable`、`publish_pause/not_applicable`、`resume_run/continue_execution`、`resume_run/abandon_and_halt`、`cancel_pause/not_applicable`、`resolve_external_interrupt/recoverable_timeout | controlled_halt | integrity_failure`、`replay_run/not_applicable`、`fork_run/not_applicable`与`close_run/not_applicable`。Reservation transaction必须把variant写入request digest，并保存该variant overlay冻结的exact evidence；未出现在机器合同中的type、variant、phase、edge或evidence字段全部非法。

机器合同同时为每个phase冻结authority、effect class、continuation policy、required evidence、ownership acquisition和terminal outcomes。每个multi-successor phase还必须具有machine-readable、互斥且穷尽的`branch_contract`，每个多形proof必须使用tagged `evidence_union`；guard只能引用在选边前已不可变绑定的字段。每个variant还必须为所有noninitial phase声明一个producer dependency，且该producer在每条成功路径上支配consumer。Design-time validator除计算dominators外，还必须用独立冻结的ControlOperation graph/dependency语义摘要核对完整十二种variant；同时修改success graph与dependency declaration仍不得绕过start、resume、advance及terminal publication顺序。Validator必须证明每个ControlOperation graph全部phase可达、无隐藏cycle、每个nonterminal phase都有穷尽successor且所有合法路径只到达声明的terminal outcome；正常路径到达`result_committed/committed`，cancel或interrupt unavailable路径只能到达`terminal_closure_unavailable_recorded/recovery_required`；消费失败unavailable路径到达`consumption_failure_unavailable_recorded/recovery_required`。其他`failed | recovery_required`仍只能作为保存typed cause并冻结当前phase的不可逆ControlOperation interrupt terminal status，不能伪装成success edge。下文保留各phase的语义、evidence与cross-machine约束说明，但不能扩展机器枚举。

Schema/auth/scope rejection发生在operation acceptance前，不创建operation row；same-key conflict返回已有operation identity但不推进其status/phase。成功的reservation transaction将`accepted`推进为`in_progress + operation_reserved`。任一nonterminal phase都可以在保存typed evidence后终止为`failed`或`recovery_required`，终止时phase冻结在最后成功边界且以后不得推进；不存在从terminal status回到`in_progress`、跨过中间phase或从一类operation phase跳入另一类operation phase的边。

`pause_dependencies_bound`在`external_result`时提交A05 ExternalOperation one-time binding，在其他Pause reason时提交typed `not_applicable` verification，不能跳过phase。`resume_disposition_committed`持久化reservation transaction已经冻结的`continue_execution | abandon_and_halt` variant；普通human/external input和`continue_existing_target`映射前者，RecoveryDecision `abandon_and_halt`映射后者，之后不得换支。Continue branch以`pause_ownership_reserved`取得单一Pause claim owner；abandon branch以一个coordinator transaction和一个`pause_and_terminal_ownership_reserved` phase同时CAS Pause claim owner与空的Run terminal closure owner，不能拆成两个可观察phase。`prestart_records_committed`只存在于continue branch，必须闭合reason-specific target allocation、A03 invalidation、Transition intent与A06 settlement，不能用可选隐藏步骤改变trace。Abandon branch不创建或启动target；其target/resource disposition没有对象时仍提交typed `not_applicable` evidence。`invocation_authorized`只发布绑定operation/Attempt、`lease_epoch`、exact heads与当前`terminal_closure_revision`的invocation-lifetime capability；Attempt执行副作用仍必须先append A02 `started`；A05 scheduled Code Agent的Host-owned pre-start workspace/Backend副作用使用独立ExternalOperation authority，不能兑换Attempt执行授权，closure revision一旦变化该capability立即失效。Crash时若不存在`started`或其他副作用evidence，可以继续同一invocation；若`started`后是否执行副作用不确定，则operation终止为`recovery_required`且不得自动rerun。`stable_boundary_committed`只可引用另一个已committed `publish_pause`、已committed `close_run`或不含pending side effect的validated running checkpoint。

`advance_run`是START bootstrap与Human Response resume之外所有普通Transition的唯一durable owner。Reservation在任何budget、target、invalidation或Transition bytes前冻结source Run/Attempt/heads、route、canonical budget decision、grant consumption、Human Request前置条件、target Attempt或typed-null END、invalidation set、Transition bytes/digest、expected post-transition heads与terminal closure revision。公共顺序为`operation_reserved -> budget_decision_committed -> transition_target_classified`；Attempt target固定继续`route_prerequisites_committed -> target_attempt_scheduled -> target_artifacts_invalidated -> transition_committed -> transition_heads_verified -> target_preparation_committed -> invocation_capability_prepared -> result_committed`，END固定继续`terminal_transition_committed -> transition_heads_verified -> result_committed`。Attempt capability在prepare phase仍不可兑换，只有同一operation的`result_committed` revision使其激活；END不生成capability，随后才允许`close_run`消费该terminal Transition。Recoverable external timeout在原interrupt operation中提交canonical failed Code Agent delivery、恢复到running checkpoint，并完成原Code Agent Attempt的started、failed artifact、failed lifecycle、活动绑定释放和最终checkpoint，operation committed后必须新建`advance_run`发布`code_agent -> decision_coordinator`，不得在interrupt图内隐藏产品Transition或Coordinator invocation。崩溃恢复只能由同一operation materialize预计算且head-exact的无副作用suffix，不能重新求值admission、重分配identity或重跑副作用。

`cancel_pause`只通过一个`cancel_arbitrated` linearization phase取得authority。ControlOperation、Pause owner、Run terminal closure owner和可选ExternalOperation row都位于A02C01同一物理SQLite transaction domain。Reservation绑定typed null时，事务证明不存在ExternalOperation row并原子取得Pause cancel owner与Run terminal owner。绑定non-null ExternalOperation时，它CAS exact current `phase_revision + lease_epoch + resolution_owner`并冻结`cancel_won | normal_terminal_won | preexisting_cancel_resolution | preexisting_interrupt_resolution`之一：`no_external_operation`、`cancel_won`与`normal_terminal_won`三种owner-bearing结果原子取得Pause/Run owner，`cancel_won`还取得External resolution；若interrupt已获胜，则只提交typed `resolution_winner_observed`，不得取得Pause/Run owner或消费interrupt final evidence。Normal、cancel与interrupt CAS使用相同排他tuple，任一交错恰好一个成功。Provider cancel发生在本地cancel intent提交后，只由current ExternalOperation epoch watchdog执行。

`cancel_arbitrated`的四个successor只由机器`branch_contract`选择：`no_external_operation + not_applicable`直达`pause_cancelled_recorded`；cancel/normal winner只在`safe_stop`后进入`external_terminal_closure_verified`；cancel winner的`unavailable`进入`external_unavailable_verified`；preexisting cancel或interrupt均只进入`resolution_winner_observed`。Normal/unavailable在normal CAS前已经重分类为integrity interrupt，不是合法仲裁组合。`pause_cancelled_recorded`消费tagged `PauseCancelProof`：External分支必须给出final digest、resolution revision与完整stop proof，typed-null分支必须给出null identity、absence proof与`not_dispatched`，两者不得混用。`cancel_intent_committed`、`interrupt_stop_intent_committed`或中间`termination_evidence_committed`都不是final proof。Unavailable分支固定`unavailable_resource_disposition_committed -> pause_quarantined -> terminal_closure_unavailable_recorded`且不得追加terminal lifecycle。Replay/fork继续复用A02C01 child phases；`terminal_ownership_reserved`用于通过ExternalOperation precondition的`close_run`，并原子取得Run及适用Pause disposition owner，`pause_and_terminal_ownership_reserved`只用于abandon。

`recoverable_code_consumption_contract`只授权`consume_code_agent_result`对原scheduled Code Agent Attempt执行确定性失败记录消费：`interrupted_code_invocation_authorized`绑定same in-progress interrupt winner、exact delivery digest、running checkpoint、invocation lease和terminal revision。该授权不能启动Coordinator、Backend、verification或provider；不创建新Attempt、不再次claim已consumed Pause，也不重复settlement。`canonical_failed_delivery_committed`先冻结可信Host timeout失败的完整result bytes/digest和Attempt completion，再依机器phase依次提交started、注册failed code artifact、Attempt failed与最终checkpoint。只有interrupt committed result和这组exact heads齐全时，新的`advance_run`才能选择Coordinator；不得从仍scheduled的source提交Transition。已started后只允许current control owner补齐冻结的确定性publication suffix，不能重新领取started invocation或重跑consumer；证据不确定/冲突仍按既有recovery/integrity规则终止。

`advance_run` reservation同时冻结`TargetPreparationSnapshot`。目标为Analysis且选择current Code Bundle时必须使用`analysis_fresh`，保存spec/manifest canonical bytes与摘要、exact target/Transition、base/change/effective tree和runtime policy；其他目标或无Code Bundle的Analysis显式使用`not_applicable`。`target_preparation_committed`在Transition heads验证后、inactive capability准备前完成，仅允许当前advance epoch/closure revision持有者物化冻结spec及fresh workspace并验证effective tree。该phase不能执行repository code、启动target或改变execution/artifact heads。已存在bytes冲突则隔离并进入integrity outcome，不能激活capability；exact未完成prefix由同一advance补齐，禁止重新选route或创建替代operation。

Invocation capability fencing适用于所有target start，不只适用于resume branch：initial Planner和任何committed Transition target都必须在A02 `started`及Agent/provider/tool/workspace副作用前，从可信control plane取得绑定Run/Attempt、exact heads、适用operation/epoch和当前`terminal_closure_revision`的不可变authorization及独立短期execution lease。START、普通Transition及Replay/Fork child bootstrap在`invocation_capability_prepared`生成不可兑换envelope，只有同一`start_run | advance_run | replay_run | fork_run`进入`result_committed/committed`且result revision exact时激活；consumer初次领取验证producer operation、committed result revision、Attempt及head anchor，执行期验证独立invocation epoch/expiry与owned head progression。Resume把运行中授权边界显式持久化为`invocation_authorized` phase，并要求same in-progress resume operation。初次领取execution lease检查授权anchor的exact heads；后续每个Attempt side-effect boundary验证同一invocation拥有的合法append chain、current invocation epoch、closure revision与expiry，不把合法`started`或resource record导致的head变化误判为stale；terminal owner递增revision后，旧capability不能继续调用provider/tool或写workspace/Run bytes。

对`resume_run`和`cancel_pause`，初始reservation transaction必须验证或创建same-key/same-digest operation、冻结resume variant（适用时）、分配initial `lease_epoch`，并按机器overlay保存exact Pause/opened-head条件、预计算下一ledger event identity/digest及variant-specific target/terminal/external evidence，但尚不修改任何owner。随后continue branch只CAS Pause claim owner；abandon branch同时CAS Pause claim与Run terminal owner；cancel branch通过`cancel_arbitrated`同时CAS Pause cancel owner、Run terminal owner及ExternalOperation resolution tuple。任一CAS失败时全部ownership保持不变并返回`conflict`；不能留下半个owner、等待lease后改支或创建第二个claim/terminal owner。

worker lease仅调度同一`operation_id`、exact current `lease_epoch`的materialization：

- 每个由该operation产生的`pause_claimed`、`pause_consumed`、`pause_cancelled`、`pause_quarantined`、target allocation/abandonment、`run_lifecycle`、checkpoint manifest和public result都必须冻结或通过canonical closure引用producing `operation_id + lease_epoch + phase_revision`；换epoch takeover后只能以新epoch继续尚未materialize的phase，已存在record保持原producing epoch且不得重写；
- transaction提交前退出，没有claim/cancel ownership，same request可正常重试；
- `resume_run` transaction已提交但`claimed` ledger record尚未append时，operation保持`in_progress/materialization_pending`，只允许同一operation在重新验证opened head未变化后create-new exact预计算record；不得运行graph、Backend、validator或其他外部副作用；
- `cancel_arbitrated`提交后，若`cancel_won`，只有持有ExternalOperation独立current `lease_epoch`的durable watchdog可以对原Backend operation执行幂等cancel并发布唯一final evidence；若其他resolution已获胜，watchdog只能继续或观察该winner，不能改成cancel。Safe-stop final evidence允许ControlOperation append预计算`pause_cancelled`；unavailable final evidence只允许append预计算`pause_quarantined`并关闭为unavailable。两类lease都不能dispatch、启动target或创建替代operation；
- `resolve_external_interrupt`仲裁提交后，只有该operation与ExternalOperation current-epoch watchdog可继续exact resolution。Recoverable timeout的safe branch依次物化canonical failed delivery、Pause consume、running lifecycle、resume checkpoint、原Code Agent Attempt started、failed artifact、Attempt failed、活动绑定释放和最终checkpoint，再提交operation result；产品Coordinator Transition由随后唯一的新`advance_run`持有。Terminal variants只能按已冻结合同解析resolved outcome并物化其halted/failed closure；unavailable branch只能物化Pause N/A/quarantine与Run unavailable closure。后来的cancel/resume及stale worker均不能取得冲突owner；
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

### Claimed external-result consumption failure

`resume_run/continue_execution`领取normal-final ExternalOperation结果后，在`pause_ownership_reserved`至`invocation_authorized`的每个publication边界冻结与exact phase revision绑定的`continue | consumption_failure`结果。该分支只用于`external_result`；human_input/recovery_decision不能消费其failure合同。continue verdict必须与successor phase revision在同一CAS中提交，不能先冻结continue再留下原phase等待不可完成的publication；failure intent只在source revision仍current时竞争，不能改写已提交边。当前边界尚未提交正常successor时，可信Host发现不可注册的tamper、identity/digest/scope违规或消费失败，必须进入同一resume operation的机器failure tail，不能先把operation标记terminal再继续它，也不能创建close_run或重新仲裁ExternalOperation。

`consumption_failure_ownership_reserved`在同一coordinator事务中比较原resume epoch/phase与Pause claim owner，CAS空Run terminal owner为原resume owner，递增terminal closure revision、撤销invocation epoch，并冻结失败snapshot、disposition contract及exact consumer stop intent。失败snapshot绑定原normal final digest、Pause/Attempt及started-intent状态、last trusted heads、待结算resource IDs、artifact registration禁令或已有audit snapshot，以及active binding generation。正常worker的每个后继提交都须比较phase revision/epoch和无failure intent；仲裁落败不能继续发布正常artifact/release或取得第二个Run owner。

停止只针对消费者、fresh verifier、provider/tool调用、workspace写入和output readers；原Backend已terminal，不改写其normal resolution或重跑cancel/dispatch。按revoke/fence → graceful cancel → bounded grace → kill-all → bounded drain → verify-empty/post-stop stability收集独立consumer stop proof。只允许同resource identity的幂等stop/lookup；不能恢复执行。`consumption_failure_classified`在停止及Run authority证据齐全后冻结outcome：safe stop且authority可append走failed_closure，任何stop proof或authority不可验证走unavailable_closure。

Safe tail复用`terminal_eligibility_verified -> terminal_lifecycle_recorded -> terminal_checkpoint_committed -> result_committed`。在此之前，`consumption_failure_disposition_committed`结算尚未结算的消费者资源；原aggregate已结算则exact复用，不重复charge。Scheduled Attempt记abandoned，running记failed，已terminal的record保持不变；claim-owned opened/claimed Pause记interrupted，consumed Pause保持consumed且不再追加Pause终态event。禁止注册invalid CodeAgentResult；artifact证据为`registration_forbidden`及可信rejection digest，或保留原registry head的`already_registered_audit_only`，不能伪造failed Code artifact。原owner以这份failure disposition proof释放活动绑定，不能冒充正常consumption release proof。Terminal eligibility才解析唯一failed disposition；committed控制结果明确报告Run failed，并非Code消费成功。

Unavailable tail仅在原owner coordinator tombstone冻结失败、保守resource charges及隔离状态，不发布Run lifecycle、不伪造Attempt/artifact/settlement，不声称safe detachment。控制authority自身不可持久化时只能停止并报告无法证明durable closure。两类路径的exact publication suffix都由同一current-epoch owner继续，缺少预计算或证据冲突则按既有owner提前终结规则形成unavailable，不能重跑验证器或用新operation补救。正常release已经完成之后的独立失败继续使用既有detached close_run规则。

### External result consumption release

正常`resume_run/continue_execution`在`invocation_authorized`驱动Code Agent消费完成后、`stable_boundary_committed`前必须经过`external_consumption_released`；recoverable interrupt在`interrupted_code_attempt_finished`后、`interrupted_code_checkpoint_committed`前复用同一phase。两者使用`ExternalConsumptionReleaseProof/external_consumed`绑定exact ExternalOperation及final safe-stop digest、消费owner/epoch/phase revision、原reservation settlement、Pause consumed、Code Attempt terminal与artifact heads。Normal resume的human_input/recovery_decision使用与reservation reason exact-match的`not_applicable`；external_result及recoverable interrupt禁止N/A。

活动绑定是coordinator的受限projection，在ExternalOperation one-time Pause binding同一事务中以generation=1创建；不是第二个领域事实源。Release以current consumption owner/epoch对exact binding generation做CAS，原子保存immutable proof并标记released。原ExternalOperation terminal row、resolution、历史Pause identity保持不变；same proof重试无副作用，冲突bytes、stale epoch及重开released binding全部拒绝。后续ExternalOperation使用新identity/generation，不能沿用旧proof。

只有settlement、consumed Pause、原Code Agent Attempt终态及canonical artifact全部完整，才能release；release先于消费最终checkpoint和Code Agent outbound Transition。`safely_terminal_and_detached`只能从所有相关ExternalOperation的完整safe final及release/close-disposition proof、且无活动绑定派生，不能仅凭terminal status或Pause consumed猜测。Normal opened-Pause close的既有source disposition同样只释放活动projection，保留历史row和resolution。Resume赢得claim后的system stop等到release完成再以新source重分类；recoverable interrupt只拥有External resolution，未拥有Run terminal closure，因此release完成后的后续END可以建立唯一close_run。禁止第二次closure的规则仅针对已经持有Run terminal owner的操作。

Release前崩溃由同一current-epoch owner补齐冻结的exact suffix；release后崩溃从durable proof继续checkpoint，不重复消费/settlement/解除绑定。无法证明exact prefix则阻止advance/close并按既有recovery或integrity规则处理，不能伪造detachment。

### `consumed` and `cancelled`

`pause_consumed` event表示typed resume input已通过claim后的全部必要pre-start control步骤并被不可逆交给exact target/action；它记录claim operation/`lease_epoch`、typed input、target/Transition、settlement与control heads，不记录尚未产生的领域结果，也不得自行分配下一`pause_id`。对继续执行的resume，固定顺序是`pause_claimed -> pre-start allocation/settlement -> pause_consumed -> run_lifecycle(paused -> running) -> resume checkpoint -> target started`；target在running checkpoint完整前不得启动。对`abandon_and_halt`，resume operation先通过combined phase同时占用Pause claim与Run terminal closure owner，再按其冻结branch在consumed后append existing target `abandoned`（如有）与`run_lifecycle(paused -> halted)`，不进入running。`pause_cancelled`只在cancel safe-stop或typed-null proof完整后记录。System interrupt对prepared Pause以`pause_aborted`安全关闭，对opened Pause以`pause_interrupted`安全关闭；停止proof unavailable时prepared/opened均使用`pause_quarantined`。claimed到interrupted仅允许同claim owner已取得Run terminal ownership的消费失败处置。已consumed Pause不能改写为interrupted/quarantined，失败隔离只作用于workspace/evidence及Run。上述terminal Pause及`consumed | cancelled`均不可resume、claim、cancel或reopen；absent Pause必须使用`not_applicable` proof且不创建虚假Pause event。

任一必需字段缺失、identity 改变、事件乱序、重复消费、对非 active Pause 操作或多个成功 claim 都必须 fail closed。已 claim 的 Pause 不能再取消、重新打开或由另一请求接管。`recovery_required` 是terminal control operation outcome，不新增可恢复 Run status；claimed operation未形成validated consumed/running-checkpoint closure时，权威`run_status`仍是paused但该Pause已不具备resume eligibility。可确定materialize的前缀查询返回`in_progress/materialization_pending`，副作用结果不确定或缺少预授权时返回terminal `recovery_required`；target不得在这个过渡窗口被重复运行。

Bounded graph state增加`run_status`受限projection、nullable pending Pause projection与nullable active Pause projection：counter、`pause_id`、reason、lifecycle status、requesting Attempt、target Attempt和typed scope，并保存上一节规定的nullable active ControlOperation projection。prepared checkpoint只能包含pending projection且active字段全部为空；public paused checkpoint必须清空pending并保存exact active opened projection。公开resume必须同时满足latest lifecycle为`opened`、public checkpoint exact、Pause owner为空且Run terminal closure owner为空。Ownership提交后旧public checkpoint可以仍含opened projection，但recovery/query必须以coordinator ownership和任何已materialize的newer `pause_claimed | pause_cancelled | pause_aborted | pause_interrupted | pause_quarantined` fact派生不可resume状态；所有terminal Pause projection只能用于审计且不能被恢复。

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
-> append A06 decision_recorded(allow | halt)

allow (next_control_action = publish_pause):
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

`decision_recorded`使用唯一`BudgetDecision`枚举和机器`budget_decision_contract.invalid_response_cases`；proposed action为`repause`，容量足够时`allow`只授权`publish_pause`，不足时`halt`只授权`close_run`。该record必须绑定已consumed old Pause、finished validator Attempt、open request、derived next Pause identity和terminal-tail计算，但该derived identity在`pause_prepared`前仍未分配。新`pause_prepared`是next Pause identity的首次durable allocation；prepared checkpoint只含pending projection，`run_lifecycle(running -> paused)`绑定prepared event，新的`pause_opened`绑定checkpoint与lifecycle pre-head，public paused checkpoint再包含opened resulting head。Halt branch的decision resulting head是唯一terminal trigger，必须复用本ticket的`close_run` ownership/idempotency/phase graph。任一中间崩溃都不重新打开旧Pause；同一operation对预计算且仍exact的side-effect-free suffix保持`in_progress/materialization_pending`，缺少预授权或存在副作用不确定性时终止为`recovery_required`，实际冲突进入`failed`，且不得补写第二个Pause、重新执行validator或直接绕过`close_run`追加terminal lifecycle。

`RecoveryDecision 0.1`首版只允许两个typed actions：

- `continue_existing_target`：Pause必须绑定existing scheduled target、唯一committed inbound Transition、完整current heads，并证明该target从未`started`、没有业务副作用、没有unsettled resource或外部operation；target kind只允许method_planner、analysis_engineer、scientific_reviewer、decision_coordinator、human_gate、memory_report，Analysis还须保留原advance要求的preparation proof；code_agent与legacy_codex_handoff在claim前拒绝，不能把external-prestart权限升级为Attempt执行权限。Code Agent目标只允许显式abandon_and_halt，拒绝continue本身不自动停止或改变Pause；claim后只能启动允许的exact target一次；
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

## External Interrupt Resolution

Timeout、aggregate hard-limit、policy stop或control integrity trigger不得借用`cancel_pause`图。可信control plane必须创建internal `resolve_external_interrupt`，并在`operation_reserved` overlay冻结exact ExternalOperation ID/revision/epoch、typed reason、Run heads、`PauseSnapshot(absent | prepared | opened)`、resource reservation及确定性delivery/closure identity。External interrupt与normal/cancel共享`external_operation_id + phase_revision + lease_epoch + resolution_owner IS NULL`单点CAS。

`recoverable_timeout`只允许Backend已经dispatch且存在exact opened `external_result` Pause。`interrupt_and_pause_ownership_reserved`在同一SQLite transaction取得External `resolution_owner = interrupt`与Pause interrupt owner。Winner取得stop proof、可信usage/integrity证据并提交resource disposition后，单次解析`resolved_interrupt_outcome`：无integrity failure的safe stop进入`recoverable_delivery`，提交canonical failed Code Agent delivery、claim/consume、paused-to-running lifecycle与resume checkpoint，再以同一interrupt winner授权原scheduled Code Agent Attempt的确定性失败结果消费，依次提交started、failed code artifact、Attempt failed、活动绑定释放和最终checkpoint后结束interrupt operation；之后的新`advance_run`才可发布`code_agent -> decision_coordinator`及目标capability。Safe stop后证明overage、tamper或policy violation则在同一interrupt operation取得Run terminal owner并进入`failed_closure`；任何stop proof维度不可得则进入`unavailable_closure`、quarantine Pause并关闭为unavailable。

`controlled_halt`和`integrity_failure`在首次仲裁中同时取得External resolution、Run terminal owner及适用的Pause/publication owner。触发variant保持不可变，但winner在stop、usage、settlement与integrity证据齐全后解析最终结果：controlled halt可形成`halted_closure | failed_closure | unavailable_closure`，integrity failure可形成`failed_closure | unavailable_closure`。Pause snapshot为`absent`时不写Pause record；`prepared`在safe halted/failed closure时写`pause_aborted`；`opened`写`pause_interrupted`；unavailable时prepared/opened均写`pause_quarantined`。同一winner operation完成Pause disposition、resource settlement、terminal eligibility、lifecycle与checkpoint，禁止再创建第二个terminal operation。

Backend dispatch只能发生在public opened Pause之后，因此pre-Pause ordinary operation timeout是非法观测；`recoverable_timeout` CAS只接受`dispatch_authorized | dispatch_receipt_committed`的ExternalOperation、opened Pause及`ExternalResourceReservationSnapshot/present`。Snapshot公共envelope必须携带exact `external_operation_id`、phase、phase revision与lease epoch，并与reservation overlay中的`exact_external_operation_resolution_tuple`逐字段相等；`present`还携带真实reservation identity/digest/status及绑定ExternalOperation和reservation的digest，禁止`reservation_fields_are_null`与no-budget-event proof。Terminal interrupt在`external_operation_reserved | task_committed | workspace_manifest_committed`只接受`absent_before_reservation`，从`reservation_committed`起只接受`present`；该variant/phase/tag矩阵由机器合同逐项列出。Pre-Pause hard-limit/policy stop使用terminal interrupt variant与typed `not_dispatched` proof。Interrupt一旦赢得resolution，之后的cancel只通过只读winner-observation guard返回`resolution_winner_observed`，验证winner operation、revision、epoch及已有Pause/Run owner与winner identity一致，不能要求owner为空、取得owner或消费final proof。已由另一个`cancel_pause`赢得cancel resolution时，同样只观察该winner；same-key retry则继续原ControlOperation，不重新仲裁。上述三个variant的exact phase、guard和tagged evidence union只由机器协议定义；Pause snapshot与safe/unavailable disposition tag必须按协议的一对一correlation匹配，terminal unavailable proof还必须绑定前一Pause disposition proof digest。

## Explicit Cancellation

`cancel_pause`的owner-bearing admission只允许处置source Run最新的`opened`且尚未claim、尚无owner的Pause，并要求exact Run/Pause identity、幂等键、current ControlOperation epoch与具备取消scope的trusted actor。Winner-observation admission可以读取已由exact preexisting cancel/interrupt winner拥有或终结的同一public source Pause，但不能改变它；absent/prepared snapshot从未构成public cancel source，不能为了观察winner伪造Pause。机器overlay在reservation时冻结exact Pause/opened head、ExternalOperation ID或typed null、cancel reason及预计算cancel/quarantine event identity。Typed-null、cancel-won与normal-won在`cancel_arbitrated`按outcome-conditioned guard取得Pause/Run ownership；preexisting-cancel和preexisting-interrupt均不取得任何领域owner，只返回winner identity、resolution revision和当前状态。不存在先取得owner再判断resolution的窗口。

当A05唯一`external_final_evidence_committed`给出`safe_stop`时，固定publication顺序为`cancel_arbitrated -> external_terminal_closure_verified -> pause_cancelled -> target disposition -> resource disposition -> terminal eligibility -> run_lifecycle(paused -> halted | failed) -> terminal checkpoint -> result`；具体status只能由上述machine total function选择，clear integrity为halted，safe-stop后证明overage/tamper/policy violation为failed。Typed-null/no-ExternalOperation顺序省略external verification phase并固定halted，使用`PauseCancelProof/no_external_operation`。当ExternalOperation final给出`unavailable`时，唯一顺序为`cancel_arbitrated -> external_unavailable_verified -> unavailable_resource_disposition_committed -> pause_quarantined -> terminal_closure_unavailable_recorded`且不得写Run lifecycle。Preexisting cancel或interrupt固定为`cancel_arbitrated -> resolution_winner_observed -> result`，不进入上述任何cancel ownership或proof消费路径。观察guard要求existing Pause/Run owner为null或exact winner-owned的合法shape，并且绝不修改领域owner；所有分支由协议guard唯一选择，中间intent/termination observation不足以推进。

A04 不定义自动 timeout、deadline 或 budget cancellation；这些由 A06 定义，但不得改变 single-use claim、显式取消和 fail-closed crash 规则。

## Child-run Bootstrap Saga

`replay_run`与`fork_run`必须复用A02C01 coordinator、lease fencing、durability profile与schema `0.4+` bootstrap，不得在A04建立第二套child creator。Coordinator transaction在任何child root bytes前固定完成：验证same-key/same-digest operation、分配immutable child Run locator与initial `lease_epoch`、保存canonical child policy bytes/digest/profile/version/selection authority和initial Planner capability inputs，以及冻结`SourceSnapshotProof` tagged union与lineage digest。两个source proof variant都必须携带exact source Run identity；它与request source locator逐字段相等，并进入lineage digest，禁止跨Run移植proof。Replay只接受`replay_root`，它只证明immutable root input、schema与fingerprint，禁止run status、latest heads、raw control revision、source revision CAS、eligible artifact snapshot、Pause、authorization和accepted status；schema `0.2`必须使用`legacy_control_revision_not_applicable`，schema `0.3 | 0.4`必须使用`versioned_control_revision_not_consumed_for_root_replay`。Fork只接受`fork_head`，必须携带schema `0.3 | 0.4`、latest heads、run status、`exact_source_control_revision`、source revision CAS和eligible artifact snapshot，并禁止携带replay-only root input/digest/fingerprint；source status只允许stable `paused | completed | halted | failed`，paused还必须证明latest opened unclaimed Pause、public checkpoint及空Run terminal owner，terminal还必须证明latest lifecycle head与committed closure；schema `0.2`不得fork。Replay source policy只能由trusted Host根据source Run identity、schema、权威policy presence/absence、canonical bytes/digest/profile/version和runtime-supported-set digest生成`pre_a06 | supported | unsupported` classification proof；`pre_a06`只接受0.2/0.3权威absence并固定当前`balanced_v1`，`supported`只接受0.4且复用exact source policy，`unsupported`在operation reservation前拒绝。Fork只使用具profile-selection scope的trusted Host选择的当前allowlisted target policy。Policy bytes、profile、version和selection authority必须共同匹配digest，`phase_b_test`只可用于deterministic harness。

Child bootstrap使用上文`replay_run`/`fork_run` exact phase enum，并让每个child-prefixed phase一一复用A02C01对应durability边界；其`Run created(initializing)`必须绑定parent operation和lineage snapshot，并在`policy_initialized`前追加exact `lineage_initialized(root | replay_of | fork_of)` record。完成bootstrap records后同样追加`run_lifecycle(initializing -> running)`、持久化包含resulting head的checkpoint、进入`invocation_capability_prepared`，再提交operation result并以该exact committed result revision激活initial Planner capability。相同key只返回同一child；changed digest冲突；预计算且exact的partial child root保持`in_progress/materialization_pending`，只能由同operation/current epoch补齐。

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
- `A04-PAUSE-005`：human/recovery nullable-target与external-result preallocated-target两类Pause均验证各自target shape、claim后allocation和partial-commit fail-closed行为；RecoveryDecision continue对code_agent/legacy_codex_handoff在claim前拒绝，其余target必须满足冻结的kind/scope/preparation条件；
- `A04-PAUSE-006`：recovery continue/halt、wrong target/action、unsettled side effect、attempt reuse、route override以及用recovery Pause代替replay/fork均有negative scenarios；
- `A04-PAUSE-007`：只有stable exact `run_status: paused`、active opened Pause与public paused checkpoint可以resume；claimed/cancel-owned transitional paused query不可resume，`initializing | running | completed | failed | halted`、prepared-only、伪paused projection、schema `0.2`、Phase B不支持的`0.3`与runtime fingerprint mismatch均拒绝，领域pending report正常终结为`completed`；同时验证显式支持`0.3`的runtime语义与Phase B `0.4` migration policy不被混淆；
- `A04-PAUSE-008`：`pause_prepared`、ExternalOperation one-time binding、prepared checkpoint、running-to-paused lifecycle、`pause_opened`、public paused checkpoint、`pause_claimed`、pre-start allocation/settlement、`pause_consumed`、paused-to-running lifecycle、resume checkpoint、invalid-response repause及结果heads每个publication边界的崩溃，并区分`in_progress/materialization_pending`、terminal `recovery_required`与`failed`；
- `A04-PAUSE-009`：`external_result`在`pause_prepared`前完成A05 ExternalOperation identity stub、task、manifest、exact resource reservation、immutable core与workspace materialization，prepared后以fenced one-time CAS补齐Pause binding；Pause期间dispatch/delivery不推进execution head，claim后settlement先于target `started`，且claim后settlement崩溃三分类fail closed；
- `A04-PAUSE-010`：验证prepared/opened/public checkpoint非对称closure，拒绝checkpoint、bounded state、run lifecycle、execution ledger与artifact registry任一head不一致；
- `A04-PAUSE-011`：replay/fork通过A02C01 phases生成新child identities，在任何child bytes前以`SourceSnapshotProof/replay_root | fork_head`冻结exact source Run identity、字段互斥的source evidence、source-schema/revision-proof合法组合、lineage binding、canonical child policy bytes/digest/profile/version/selection authority及initial Planner capability inputs；Replay另冻结由权威source policy evidence确定性生成的classification proof，0.2只可replay，versioned replay不消费head revision，fork只接受0.3/0.4 stable paused/terminal exact head revision；child checkpoint后prepare capability且只由same-operation committed result激活，source与accepted artifacts bytes不变，child partial prefix只由原operation继续；
- `A04-PAUSE-012`：fork source-control-revision CAS拒绝旧checkpoint、被后续history否定的artifact、非最新source head与竞争source mutation；
- `A04-PAUSE-013`：replay/fork不继承Human authorization、accepted status或active Pause。
- `A04-PAUSE-014`：所有public mutation与internal `advance_run`/`publish_pause`/`close_run`/`resolve_external_interrupt`先进入独立`ControlOperation` coordinator；逐项验证本ticket冻结的operation type/variant、phase enum、穷尽allowed-edge graph、phase evidence与terminal status映射，并由两个独立process验证same-key replay、changed-payload conflict、single Pause publication/claim owner、lease takeover递增epoch、stale-owner写拒绝、operation/run/domain/Pause状态正交以及coordinator/checkpoint/ledger authority分离。
- `A04-PAUSE-015`：从bootstrap initializing到running、Pause running到paused、resume paused到running及completed/halted/failed terminal的append-only run lifecycle可完整重放；normal `memory_report -> END`、普通non-Pause runtime failure、ExternalOperation absent/detached或normal safe-stop attached opened Pause的independent confirmed halt与uncloseable Run-authority failure遵守唯一`close_run` operation trace，cancel/terminal interrupt/abandon则只能使用其已占用同一Run closure ownership的embedded tail；uncloseable只返回`terminal_closure = unavailable`且不伪造Run failed lifecycle，非法from/to、terminal后继续和bounded projection伪造全部fail closed。
- `A04-PAUSE-016`：`resume_run`在reservation时冻结`continue_execution | abandon_and_halt` variant；continue branch只取得Pause owner并经过prestart/running/checkpoint/invocation，abandon branch以单一combined-ownership phase原子取得Pause与Run closure owner，再经过consumed/target-resource disposition/terminal eligibility/embedded terminal tail，且绝不进入running或启动target；未列出的跨支、回退、半ownership或跳phase全部拒绝。
- `A04-PAUSE-017`：每个Run只有一个terminal closure owner；END、runtime failure及没有unresolved ExternalOperation的独立stop使用由canonical trigger、ExternalOperation close-source precondition proof和pre-close contract派生的same-key `close_run`，cancel、terminal interrupt与`abandon_and_halt`使用同一ownership的embedded tail；ownership递增Run closure revision并拒绝所有非owner/stale invocation写入，cancel只在final evidence后解析一次disposition/pre-close heads并经过terminal eligibility，竞争trigger/contract冲突，same trigger exact replay，normal safe-stop且仍绑定opened unclaimed Pause的system stop由close原子取得Pause/Run owner并完成settlement、target/Pause disposition和detach；materializable prefix只由原operation继续，owner operation提前terminal则closure同步变为`unavailable`而不伪造Run status。
- `A04-PAUSE-018`：任何latest opened且cancelable的Pause在explicit trigger下都进入`cancel_pause`；`cancel_arbitrated`与terminal resolution消费同一合法tuple domain，机器guard穷尽typed-null、cancel、normal、preexisting-cancel和preexisting-interrupt。三个owner-bearing分支取得Pause/Run owner并在terminal eligibility解析，两个preexisting winner只读且在winner-observation phase返回，unavailable只进入quarantine与unavailable closure；
- `A04-PAUSE-019`：`resolve_external_interrupt`按variant/external-phase矩阵消费字段互斥的`ExternalResourceReservationSnapshot`：公共envelope的ExternalOperation identity/phase/revision/epoch必须与exact resolution tuple匹配，present reservation另以binding digest绑定同一ExternalOperation；recoverable timeout只能在dispatch后使用真实`present`，terminal interrupt在reservation前使用`absent_before_reservation`、reservation后使用`present`；同一winner在stop、usage、settlement和integrity证据后解析recoverable/halted/failed/unavailable outcome并完成Pause recovery或terminal Run closure；
- `A04-PAUSE-020`：preexisting cancel或interrupt winner存在时，后续cancel通过无需空owner的只读guard到达`resolution_winner_observed`；它验证External winner operation/revision/epoch与现有Pause/Run owner exact一致，不取得或改写任何领域owner，same-key replay继续原operation而不被误分类；
- `A04-PAUSE-021`：START和Human Response resume之外的每个普通Transition都由`advance_run/not_applicable`持有；recoverable interrupt必须完成原Code Agent Attempt的started、failed artifact、failed lifecycle和最终running checkpoint，随后另建`advance_run`发布Coordinator Transition。Operation先冻结admission、route、target、invalidation、Transition与expected heads，严格按target allocation、A03 invalidation、Transition、head verification、target preparation、inactive capability preparation和operation-result activation顺序物化，END使用typed-null target且不签发capability；

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
