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
- `src/lqcd_agent/graph/analysis_graph.py`
- `src/lqcd_agent/graph/run_graph.py`
- `src/lqcd_agent/demo/server.py`

## Scope

- 冻结项目自有的 `start_run`、`resume_run`、`replay_run`、`fork_run` 与 `cancel_pause` 外部合同；
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
- 不选择或部署生产 checkpoint backend、认证服务、分布式锁或事务系统；
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
- **Terminal**：control `run_status`为`completed`、`failed`或`halted`；terminal Run不能resume。
- **Domain status**：现有`AnalysisState.status`表达领域/workflow结果，可以在正常报告完成后保持`success`、`pending`或其他既有值，但不再决定Run是否terminal或可resume。
- **Recovery required**：claim 后结果不确定或 control heads 不一致；禁止自动重新执行目标 Attempt，只能在验证 source 后显式 replay/fork。

Execution schema `0.3`新增权威control字段`run_status = running | paused | completed | failed | halted`。现有`AnalysisState.status`在Phase B迁移中保留为领域/workflow compatibility字段，不改名、不作为resume authority；`pending`只能出现在该领域字段或typed terminal disposition中，不能成为`run_status`。

映射固定为：新Run完成其execution schema适用的bootstrap后是`running`，其中schema `0.4+`必须使用A02C01；只有latest active Pause为`opened`且全部绑定heads exact-match时是`paused`；accept、reject、hold或pending report正常到达`memory_report -> END`均是`completed`，同时保留各自领域结果；control/runtime完整性失败是`failed`；operator取消、budget/security hard stop是`halted`。只有`run_status: paused`可调用`resume_run`，其余值均不可resume。缺少`run_status`、control/domain字段互相伪造、`paused`但无exact active Pause或terminal head与`run_status`不一致均fail closed。

## Project-owned Control Interface

LangGraph checkpoint、thread configuration 与 serializer 都是内部实现细节。CLI/UI 只能调用项目自有接口，不得接收 raw checkpoint ID，也不得直接调用 LangGraph resume primitive。

```text
start_run(StartRunRequest) -> ControlOperationResult
resume_run(ResumeRunRequest) -> ControlOperationResult
replay_run(ReplayRunRequest) -> ControlOperationResult
fork_run(ForkRunRequest) -> ControlOperationResult
cancel_pause(CancelPauseRequest) -> ControlOperationResult
```

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

`ControlOperationResult`必须区分控制操作结果、权威control lifecycle和领域结果，至少能表达`completed`、`already_applied`、`conflict`、`rejected`、`recovery_required`，以及操作后的`run_status`、nullable `domain_status`、head和active `pause_id`。

### Other typed requests

- `StartRunRequest`：包含可信 Host 解析后的 immutable root inputs、canonical digest、new Run locator policy、`idempotency_key` 与 `ActorContext`；不能指定现有 Run root、checkpoint 或 parent；
- `ReplayRunRequest`：包含 source `RunLocator`、source root-input digest、`idempotency_key` 与具备 replay scope 的 `ActorContext`；不能覆盖 source root inputs；
- `ForkRunRequest`：包含 source `RunLocator`、source latest validated head digest、显式选择的 eligible artifact IDs、`idempotency_key` 与具备 fork scope 的 `ActorContext`；不能指定旧 checkpoint；
- `CancelPauseRequest`：包含 exact `RunLocator`、active `pause_id`、`idempotency_key`、typed cancellation reason 与具备 cancel scope 的 `ActorContext`。

Start、replay 和 fork 分别建立 `root`、`replay_of` 与 `fork_of` typed lineage。所有请求字段、source validation result 与返回的 child Run identity 都纳入该操作的 canonical request/result digest。

## Execution Schema `0.3` and Pause Identity

A04 将 execution schema 从 `0.2` 升级为 `0.3`。每个 Run 维护单调递增的正整数 `pause_index`，并据此分配 Run-local、唯一、无间隙的 `pause_id = pause_NNNNNN`。Pause identity 不能由调用方选择或复用。

Execution ledger 使用 append-only lifecycle：

```text
opened -> claimed -> consumed
opened -> cancelled
```

### `opened`

`opened` 事件冻结：

- `run_id`、`case_id`、`cycle_id`；
- `pause_id`、`pause_index`、typed reason；
- exact `run_status = paused`与当时的领域`status`；
- requesting Attempt，以及reason-specific target binding：`external_result`必须绑定状态为`scheduled`、具有唯一committed inbound Transition且尚未`started`的target Attempt；`human_input`与不继续既有target的`recovery_decision`使用显式null target，并冻结claim后允许创建的target kind/action；
- typed input contract 与 authorization scope；
- internal thread identity 与 checkpoint identity；
- runtime compatibility fingerprint；
- canonical state digest；
- append 前的 execution ledger head 与 artifact history/index head。

`opened` 自身的 event identity、sequence 与 canonical digest 构成 `opened_execution_head`。可恢复 Pause 对外发布后，当前 execution head 必须等于该 resulting head；因此事件不自引用，后续 claim 可以对 exact `opened_execution_head` 执行 compare-and-set。

### `claimed`

`claimed` 事件保留所有 `opened` identity，引用 exact `opened_execution_head`，并增加稳定的 control operation ID、`idempotency_key`、canonical request digest、trusted actor identity/scopes、typed input reference 与 digest。

### `consumed` and `cancelled`

`consumed`事件记录claim对应的operation identity、结果control `run_status`、领域`status`、结果control heads，以及需要继续等待时新分配的`pause_id`。`cancelled`事件记录operator、取消原因与结果`run_status = halted`。

任一必需字段缺失、identity 改变、事件乱序、重复消费、对非 active Pause 操作或多个成功 claim 都必须 fail closed。已 claim 的 Pause 不能再取消、重新打开或由另一请求接管。`recovery_required` 是 control operation outcome，不新增可恢复 Run status；claimed operation 未形成 validated `consumed` head 时，物理 checkpoint 中即使仍显示 `paused` 也不满足 resume eligibility。

Bounded graph state增加权威`run_status`及nullable active Pause projection：counter、active `pause_id`、reason、lifecycle status、requesting Attempt、target Attempt和typed scope。`run_status: paused`必须与execution ledger中最新`opened`且未claim/cancel的Pause exact-match；无active Pause时所有nullable Pause字段必须显式为空。现有领域`status`不得覆盖`run_status`或把terminal `pending`伪装成可resume状态。

Schema `0.2` 及更早的实验 Run 默认不可 resume，也不自动迁移。只有 root inputs 仍可完整验证时才允许显式 replay；只有最新 source head 满足本 ticket 的 fork 验证规则时才允许显式 fork。

## Safe Pause Publication Boundary

Pause 只能发布在安全 checkpoint 边界：requesting Attempt已经形成可暂停的typed outcome；若reason要求既有target，则该Attempt identity已分配但`started` event尚未写入且target node没有业务副作用；`human_input`使用null target时，Pause发布不得预分配或执行未来validator，claim后仍必须按A02在任何target side effect前完成唯一分配与Transition commit；null-target `recovery_decision`只允许halt且始终不得分配target。

发布顺序必须是：

1. runtime只在内存中分配新的Pause identity/projection；`external_result`验证并复用A02已提交的唯一scheduled target Attempt，nullable-target reason验证target为空和allowed target/action contract；
2. internal checkpointer 持久化完整 state 并返回 checkpoint identity；
3. runtime append `opened` 事件，将 checkpoint、runtime fingerprint、state digest、execution head 与 artifact head 绑定；
4. 仅在 checkpoint、ledger、artifact registry 和 bounded state exact-match 后，Host 才返回 public `pause_id`。

等待期间不提交 `END`。允许写入显式标记为 audit-only 的暂停证据，但不得写入 Memory Report、accepted memory 或其他代表已接受业务结果的 artifact。跨文件 partial commit、orphan checkpoint 或未完成的 `opened` 发布都不可 resume，必须返回 `recovery_required`。

## Typed Pause Reasons

| Reason | Typed input | Required frozen scope |
|---|---|---|
| `human_input` | `human_response` | exact Human Gate/request identity、null target、claim后只允许A02 Human validation control path、single-use authorization scope |
| `external_result` | `external_result` | producer contract、target Attempt、A06 pre-open resource reservation、artifact kind/path/digest 与允许的 ingress schema |
| `recovery_decision` | `recovery_decision` | failure/error identity、reason-specific existing或null target、`continue_existing_target | abandon_and_halt` action |

`human_input` Pause不预分配未来Human Gate validation Attempt。Claim成功后，control plane才按A02 Human Response顺序提交exact external control Transition并分配一个scheduled validation Attempt，随后才能启动validator；这不是`human_gate -> human_gate`产品Transition。无效Human Response也消费本次恢复窗口：本次validator Attempt按A02 lifecycle终结，旧Pause记录为`consumed`，request保持open；只有A06 admission证明下一次validation和完整terminal tail仍有容量时，才在新安全边界分配使用null target的新`pause_id`，且下一份response成功claim前不创建下一validation Attempt；容量不足时直接形成typed `halted` control outcome，不发布无法安全消费的新Pause。旧Pause不重新打开，single-use authorization不继承。

Invalid Human Response终结validator Attempt后的durable顺序固定为：

```text
validate latest execution/artifact/checkpoint heads and the still-open Human Request
-> derive the deterministic next_pause_id without publishing it
-> append A06 decision_recorded(allow_repause | halt)

allow_repause:
-> append old Pause consumed(run_status = paused, next_pause_id)
-> build the new null-target active-Pause projection in memory
-> persist the new checkpoint
-> append new Pause opened
   bind pre_execution_head = old consumed resulting head
-> validate checkpoint/state/execution/artifact heads
-> publish the new pause_id

halt:
-> append old Pause consumed(run_status = halted, next_pause_id = null)
-> persist and validate the terminal checkpoint/head
-> publish no new Pause
```

`decision_recorded`必须绑定old Pause、validator Attempt、open request、derived next Pause identity和terminal-tail计算。`consumed`是next Pause identity的首次durable allocation；新checkpoint必须包含old consumed resulting execution head与new active projection，新的`opened`再绑定该checkpoint。任一中间崩溃都返回`recovery_required`：旧Pause不重新打开，未完整`opened`的新Pause不接收response，同key不得补写第二个Pause或重新执行validator。

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
- `external_result` Pause必须绑定在`opened`前已持久化的exact resource reservation；Pause对外可见后到claim前不得append任何execution/budget record，dispatch receipt与delivery snapshot只能作为不推进execution head的immutable control evidence；
- `external_result` claim必须对exact `opened_execution_head`执行compare-and-set；claim成功后、target Attempt `started`前才允许append该reservation的exact settlement。claim后settlement未完整即进入`recovery_required`，不得重新dispatch或启动target Attempt；
- null-target `human_input` Pause claim成功后，target allocation、A03 invalidation、Transition append或validator start任一partial sequence都进入`recovery_required`；同key重试不得再分配第二个Attempt或第二条Transition；null-target `recovery_decision`不得分配target；
- claim 之后 runtime 不得因客户端重试、进程重启或超时自动重新执行 target Attempt；
- 若无法证明 claimed operation 已消费且结果 heads 完整，查询或同 key 重试只能返回 `recovery_required`，不得重新调用 node；该 claimed source 只有在 latest heads 可完整验证后才能作为显式 replay 的来源，或在另有 validated terminal head 时作为 fork 来源，原 Run 不恢复执行；
- checkpoint、state、execution ledger 或 artifact registry 任一 head 不一致时，resume 在 claim 前拒绝，在 claim 后进入 `recovery_required`。

底层的 compare-and-set、事务或锁实现由 Phase B 选择，但实现必须满足以上单一成功 claim 和稳定重放结果，不得降低为进程内 best effort。

## Runtime Compatibility Fingerprint

每个 Pause 必须冻结至少以下 compatibility components 的 canonical fingerprint：

- control contract/version；
- application source/build digest；
- graph topology digest；
- state schema version；
- execution schema `0.3` 与 artifact schema version；
- LangGraph、checkpointer 与 serializer 的实现及版本。

Resume 前必须 exact-match 当前 runtime 与 Pause fingerprint；缺失、不支持或任一 component 不一致都拒绝 resume。不得 best-effort 恢复或原地迁移。满足 source 验证条件时，operator 只能显式选择 replay 或 fork；新 child Run 记录 source 与 target runtime fingerprints。

## Explicit Cancellation

`cancel_pause` 只允许取消 source Run 最新的 `opened` 且尚未 claim 的 Pause，并要求 exact Run/Pause identity、幂等键与具备取消 scope 的 trusted actor。成功的逻辑cancel commit必须append`cancelled`并把Run转为`halted`；若Pause绑定existing scheduled target，还必须按A02为同一Attempt append`abandoned`，null target则不创建Attempt。实现可以在同一durable transaction提交；否则先对exact `opened_execution_head`提交`cancelled`，再提交`abandoned`。两条record之间崩溃时Run保持`halted`、target永不启动，control operation返回`recovery_required`且不得自动repair。取消后不得执行graph、Agent、Human authorization或accepted-result写入。

A04 不定义自动 timeout、deadline 或 budget cancellation；这些由 A06 定义，但不得改变 single-use claim、显式取消和 fail-closed crash 规则。

## Replay Contract

Replay 仅从 source Run 的 immutable root input snapshot 与 canonical digest 创建新的 child Run，并从 `START` 重新执行。

- child 获得新的 Run root、`run_id`、thread、Cycle、Attempt、Transition 与 parent-link identities；
- 不复制 source checkpoint、current pointers、execution/artifact counters、Pause control state或 Human authorization；
- 不继承 approval、accepted 状态、预算消耗或未消费 resume input；
- 不允许 replay 请求修改 root input、provider/security policy、artifact contract 或选择中间 checkpoint；
- source Run、source artifacts 与 accepted artifacts 保持不可变；
- source root inputs 无法完整验证时拒绝 replay。

## Fork Contract

Fork 仅允许使用 source Run 的最新 validated paused 或 terminal head，并从 `START` 创建全新的 child Run/Cycle/Attempt/Transition identities。不能选择被后续 execution/artifact history 否定的旧 checkpoint 或旧 current state。

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
- execution schema `0.3`权威`run_status`、领域`status`分离、Pause identity与append-only lifecycle；
- safe Pause publication、idempotency、authorization、compatibility 和 crash semantics；
- replay/fork 的 source validation、identity isolation 和 artifact inheritance 规则；
- 对 A05–A07 与 Phase B implementation tickets 的明确约束；
- 核心 source-of-truth 文档更新和独立 A04 completion record。

## Acceptance Criteria

- 只有`run_status: paused`且具有最新exact active `pause_id`的Run可resume；`running`、`completed`、`failed`、`halted`及伪paused projection均拒绝，领域`status: pending`到达END时映射为`run_status: completed`而不是生命周期死区；
- 三类 typed Pause 均可跨进程恢复且最多消费一次；
- 外部接口不暴露 raw LangGraph checkpoint，也不接受 arbitrary state/route patch；
- 重复 key、变更 payload、竞争 claim、错误 actor、错误 Run/Pause 和过期 Pause 都有确定的 fail-closed 结果；
- invalid Human Response在A06容量允许时生成新Pause，否则安全`halted`；旧Pause与single-use authorization均不复用；
- `human_input` opened时target显式为null，claim后才分配exactly one Human Gate validation Attempt；`external_result` opened时必须绑定already-scheduled exact target；
- `recovery_decision`只接受`continue_existing_target | abandon_and_halt`，且null target只能halt；replay/fork和`recovery_required`不得伪装成resume action；
- `cancel_pause`使existing scheduled target进入`abandoned`并使null target保持null；partial cancel commit不允许target启动或自动repair；
- fingerprint mismatch、schema `0.2` Run、partial publication 与 claimed 后不确定崩溃均不能自动 resume/rerun；
- replay/fork 创建全新 child Run identity，source Run 和 accepted artifacts 不变；
- fork 只使用最新 validated head，且不继承 source current pointers、checkpoint control state、Human authorization 或 accepted status；
- A05、A06、A07 与 Phase B 无需自行发明另一套控制机制。

## Required A07 and Phase B Scenarios

A07 与后续 Phase B implementation tickets 至少必须覆盖：

- `A04-PAUSE-001`：process退出后，`human_input`、`external_result`与`recovery_decision` Pause都可准确恢复一次；
- `A04-PAUSE-002`：同key同payload、同key不同payload、不同key竞争claim；
- `A04-PAUSE-003`：错误actor/scope、错误Run/Pause、过期Pause、typed payload digest变化；
- `A04-PAUSE-004`：invalid Human Response按decision → old consumed → checkpoint → new opened精确顺序消费旧窗口，并根据A06剩余terminal-tail容量生成新`pause_id`或安全`halted`；
- `A04-PAUSE-005`：human/recovery nullable-target与external-result preallocated-target两类Pause均验证各自target shape、claim后allocation和partial-commit fail-closed行为；
- `A04-PAUSE-006`：recovery continue/halt、wrong target/action、unsettled side effect、attempt reuse、route override以及用recovery Pause代替replay/fork均有negative scenarios；
- `A04-PAUSE-007`：只有exact `run_status: paused`可以resume；`running | completed | failed | halted`、伪paused projection、schema `0.2`与runtime fingerprint mismatch均拒绝，领域pending report正常终结为`completed`；
- `A04-PAUSE-008`：checkpoint写入前、checkpoint写入后但`opened`前、claim后消费前、invalid-response repause每个publication边界和结果heads partial commit的崩溃；
- `A04-PAUSE-009`：`external_result`在`opened`前完成exact resource reservation、Pause期间dispatch/delivery不推进execution head、claim后settlement先于target `started`，以及claim后settlement崩溃fail closed；
- `A04-PAUSE-010`：checkpoint、bounded state、execution ledger与artifact registry head不一致；
- `A04-PAUSE-011`：replay/fork生成新child identities，source与accepted artifacts bytes不变；
- `A04-PAUSE-012`：fork拒绝旧checkpoint、被后续history否定的artifact与非最新source head；
- `A04-PAUSE-013`：replay/fork不继承Human authorization、accepted status或active Pause。

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
