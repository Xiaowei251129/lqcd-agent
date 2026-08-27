---
ticket_id: A06
phase: phase-a-control-contracts
status: review
type: design
depends_on: [A01, A02, A02C01, A03, A03C01, A04, A05]
---

# 定义 Budget 与 Stop Conditions 合同

## Goal

冻结可信控制层的预算、重复失败和停止合同，使每条自动循环都具有可审计的有限上限，并使后续 Phase B implementation tickets 可以直接实现 admission、reservation、Human grant、Pause deadline 和 fail-closed stop behavior。

本 ticket 只确认设计并同步核心 source-of-truth 文档；不修改 runtime、graph、tests、configs、provider 或 checkpoint backend。

## Why

A01 已冻结四层回退的逻辑路线，A02 已冻结 Run/Cycle/Attempt/Transition identity，A03/A03C01 已冻结 artifact 与 execution head 完整性，A04/A05 已分别形成 Pause/Resume 和 Code Agent 合同稿。系统仍缺少统一答案来说明：一次自动动作是否还能被调度、崩溃前的外部调用如何计费、相同失败何时必须停止、Human 可以增加多大窗口，以及预算耗尽时能否安全到达 Human Gate 或 terminal state。

预算不能只是 prompt 中的建议或可被 Agent 修改的计数器。A06 必须把 policy、ledger、bounded state、admission order 和 terminal reserve 绑定为 fail-closed control contract，同时保留 accepted-result、risk floor 和 Human authorization 边界。

## Read First

- [`AGENTS.md`](../../../AGENTS.md)
- [`docs/README.md`](../../README.md)
- [`docs/tickets/README.md`](../README.md)
- [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`docs/AGENT_ROLES_AND_BOUNDARIES.md`](../../AGENT_ROLES_AND_BOUNDARIES.md)
- [`docs/STATE_SCHEMA.md`](../../STATE_SCHEMA.md)
- [`docs/ARTIFACT_CONTRACTS.md`](../../ARTIFACT_CONTRACTS.md)
- [`docs/SECURITY_AND_DATA_POLICY.md`](../../SECURITY_AND_DATA_POLICY.md)
- [`docs/EVALS_AND_OBSERVABILITY.md`](../../EVALS_AND_OBSERVABILITY.md)
- [`docs/VERIFICATION_GUIDE.md`](../../VERIFICATION_GUIDE.md)
- [`docs/REPO_CURRENT_STATE.md`](../../REPO_CURRENT_STATE.md)
- [`A01_TRANSITION_MATRIX.md`](A01_TRANSITION_MATRIX.md)
- [`A02_RUN_CYCLE_ATTEMPT_MODEL.md`](A02_RUN_CYCLE_ATTEMPT_MODEL.md)
- [`A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md`](A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)
- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)
- [`A05_CODE_AGENT_CONTRACT.md`](A05_CODE_AGENT_CONTRACT.md)
- [`Control Protocol 0.4`](CONTROL_PROTOCOL_0_4.json)
- [`A03 Transition Publication-order Clarification`](../corrections/A03_TRANSITION_PUBLICATION_ORDER_CLARIFICATION.md)
- `src/lqcd_agent/graph/state.py`
- `src/lqcd_agent/graph/routing.py`
- `src/lqcd_agent/llm/trace.py`

## Scope

- 冻结 `BudgetPolicy 0.1`、`BudgetDecision 0.1`、`FailureFingerprint 0.1` 和 single-use `BudgetGrant 0.1`；
- 冻结 `balanced_v1` 与 deterministic `phase_b_test` allowlisted profiles；
- 冻结 Cycle、automatic fallback、Attempt、Transition、LLM、tool、verification 和 active-time 的 ownership 与计数时点；
- 冻结 execution schema `0.4` 的 budget ledger events、Run-local identity 和 bounded state projection；
- 冻结副作用前 reservation、每个Code Agent Attempt唯一的`code_backend_operation` aggregate、crash accounting、admission order 和 terminal control reserve；
- 冻结 failure fingerprint、重复失败、risk-first escalation 与停止语义；
- 冻结 Human `approve_budget_window` 的 exact scope、single-use consumption 和绝对 ceiling；
- 冻结 Pause deadline，以及 start/resume/replay/fork 的 policy compatibility；
- 复用tracked [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)中互斥的continuation/outcome classes、Run lifecycle edge与pre-start dependency DAG，不在budget prose中建立第二套状态机；
- 把 runtime、schema validators、budget ledger 和 tests 交给后续 Phase B implementation tickets。

## Non-goals

- 不实现 budget manager、ledger builder、state validator、clock、graph edge、API、CLI 或 tests；
- 不修改 A01 路线、A02 identity、A03 artifact/accepted-result policy、A04 Pause lifecycle 或 A05 Code Agent outcome 含义；
- 不实现 token 或货币 hard budget，不设计 provider billing、pricing normalization、invoice reconciliation 或成本优化；
- 不新增生产认证、distributed lock、checkpoint backend、partial-commit repair 或 schema migration；
- 不允许 Agent、provider、route payload、Human 自由文本或恢复 payload 修改 policy 或 counters；
- 不允许CodingBackend、Codex thread/job或未来SandboxAgent建立第二套budget、refund、retry或stop authority；Backend只执行可信控制层对exact operation下达的envelope与cancel命令；
- 不用自动 timeout 事件改变 paused Run，不自动取消、replay、fork 或重启 Attempt；
- 不运行 live-provider 测试。

## Allowed Files

本 ticket 提升为 `ready` 并执行时，只允许修改：

- `docs/tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md`：仅允许更新 YAML lifecycle metadata，不向正文追加执行日志；
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`；
- `docs/tickets/completions/A06_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/ARCHITECTURE.md`；
- `docs/AGENT_ROLES_AND_BOUNDARIES.md`；
- `docs/STATE_SCHEMA.md`；
- `docs/ARTIFACT_CONTRACTS.md`；
- `docs/SECURITY_AND_DATA_POLICY.md`；
- `docs/EVALS_AND_OBSERVABILITY.md`；
- `docs/VERIFICATION_GUIDE.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

- A01–A05、A03C01 和 A07 ticket 正文；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/` 和 accepted artifacts；
- graph topology、checkpoint backend、dependency versions、providers、认证、secrets 和生产基础设施；
- execution/artifact history、现有 Run、migration、repair 或 compatibility import；
- 已完成 ticket、completion/correction history、milestone 或 tag。

## Authority and Terms

- **Trusted control plane**：唯一可以选择 allowlisted profile、派生 policy、做 budget admission、签发/消费 grant 和提交 stop decision 的项目控制代码。
- **Budget policy**：Run 创建时冻结的 immutable hard-limit contract；不是 Agent prompt 参数。
- **Budget decision**：在 exact validated heads 上，对一个 proposed action 做出的 `allow | human_gate | halt` typed result。
- **Failure fingerprint**：由结构化、稳定、与原因相关的字段生成的 canonical digest；不由错误自由文本直接决定。
- **Budget grant**：由一次 validated Human Response 派生、只允许 exact route/fingerprint/target 使用一次的有限授权。
- **Hard ceiling**：同一 Run 内永远不能由 grant、resume 或 route payload突破的 Work Attempt、Control Attempt 和 Transition 总上限。
- **Terminal control reserve**：从总 hard ceiling 中预留、只允许安全收尾链消费的 Control Attempt 与 Transition 额度。
- **Controlled halt**：policy、budget、security或operator在control evidence仍完整时做出的受控终止，映射A04 `run_status = halted`。
- **Control failure**：head/counter/timer/termination/lease或其他runtime integrity无法验证，映射为ControlOperation `failed`；权威Run closure仍可验证和安全append时由唯一terminal owner进一步发布A04 `run_status = failed`，authority自身不可验证时为`terminal_closure = unavailable`。不能用`halted`掩盖实现失控或证据损坏，也不能用bounded projection伪造failed lifecycle。

Agent、model/provider output、tool output、CodingBackend、graph route payload和Human自由文本都是不可信输入。它们可以提供候选诊断或usage evidence，但不能选择profile、改写policy、直接递增/递减counter、签发grant、决定retry/stop或提交Transition。Codex thread/job ID以及未来SandboxAgent session ID只能作为审计identity，不能成为预算authority或替代A02/A04/A05 identity。

## Contract Versions and Run Binding

`BudgetPolicy`、`BudgetDecision`、`FailureFingerprint` 和 `BudgetGrant` 使用独立 schema version `0.1`。后续实现本合同会把 execution schema 从 A04 的 `0.3` 升级为 `0.4`；A03 artifact registry schema不因本 ticket 改变。

每个新 Run 在A02C01 coordinator transaction已经持久分配`start_run` operation和target Run locator之后、正式 Run creation record之前，由可信 Host 选择一个 allowlisted profile，并生成：

```text
<run_root>/budget_policy.json
```

`budget_policy.json` 是 project-owned immutable control artifact，不属于七个 current artifact slots，不允许被 Agent、tool、CodingBackend 或 Human payload覆盖。其 canonical digest 计算时排除自描述的 digest 字段；文件内容、reference 或digest任一不一致均 fail closed。

execution schema `0.4` 的 Run identity、runtime compatibility fingerprint、每个Pause和bounded state都必须保存exact `budget_policy_version`、`budget_profile_id`、`budget_policy_ref`与`budget_policy_digest`。为保持A05字段合同，`CodeAgentTask`直接保存相同version/profile/digest，并用A05的`budget_envelope_ref`与`budget_envelope_digest`引用允许该Code Attempt的exact `BudgetDecision` event；它不复制一份可变policy或remaining counters。同一Run中不允许热切换profile或生成第二份policy。

## `BudgetPolicy 0.1`

Policy 至少冻结：

- `schema_version = 0.1`、`profile_id` 和 policy canonical digest；
- hard-limit dimensions及其非负整数或秒数上限；
- Work/Control Attempt kind分类；
- automatic route分类与计数scope；
- terminal control reserve；
- Pause deadline；
- token/cost audit-only声明；
- 允许的grant扩展类型以及永远不可突破的global ceilings。

只有下表两个profile属于第一版allowlist。未识别profile、字段缺失、额外维度、负数、非整数计数、reserve大于对应总上限或canonical bytes不一致均拒绝启动或恢复。

| Dimension | `balanced_v1` | `phase_b_test` |
|---|---:|---:|
| Cycles / Run | 2 | 2 |
| Automatic replan / Run | 1 | 1 |
| Automatic code fix / Cycle | 1 | 1 |
| Automatic analysis rerun / Cycle | 1 | 1 |
| Automatic re-review / Cycle | 1 | 1 |
| Work Attempts / Run | 16 | 8 |
| Control Attempts / Run | 16 | 8 |
| Transitions / Run | 40 | 20 |
| LLM calls / Attempt | 4 | 2 |
| LLM calls / Run | 32 | 8 |
| Tool calls / Attempt | 32 | 4 |
| Tool calls / Run | 128 | 16 |
| Verification commands / Code Attempt | 8 | 2 |
| Active seconds / Attempt | 900 | 30 |
| Active seconds / Run | 3600 | 120 |
| Pause deadline seconds | 604800 | 60 |
| Reserved terminal Control Attempts | 5 | 5 |
| Reserved terminal Transitions | 6 | 6 |

`balanced_v1` 是保守安全默认值，不表示已经完成生产吞吐、latency或成本校准。`phase_b_test`只供deterministic harness使用，不能被Agent请求来放宽真实Run；它的上限更小而不是生产fallback。

## Attempt and Route Classification

Work Attempts固定为：

- `method_planner`；
- `legacy_codex_handoff`；
- `code_agent`；
- `analysis_engineer`；
- `scientific_reviewer`。

Control Attempts固定为：

- `decision_coordinator`；
- `human_gate`；
- `memory_report`。

新增或未知Attempt kind不能静默归类，必须先由新的design/corrective ticket更新合同。一次Attempt不能同时计入Work和Control。

A05 `CodeAgentSubgraph`的pre-start trusted control stages不是独立Agent工作：ExternalOperation stub、task、unmaterialized manifest、budget reservation、immutable core、workspace materialization、Pause发布以及Host-owned Backend调度都不能创建额外Work/Control Attempt，也不能增加automatic route计数。`code_agent` Work Attempt仍在其inbound Transition提交并以`scheduled`分配target identity时计数；`consume_code_agent_result`只有在A04 claim、本ticket要求的settlement、`pause_consumed`、paused-to-running lifecycle与resume checkpoint完成后，才可把该既有Attempt推进到`started`。

Automatic route budget固定为：

- Coordinator派发新Cycle Planner时计入`automatic_replan_per_run`；
- Coordinator在同一Cycle派发`code_agent`修复时计入`automatic_code_fix_per_cycle`；
- Coordinator在同一Cycle派发新的Analysis Attempt时计入`automatic_analysis_rerun_per_cycle`；
- Coordinator在同一Cycle派发新的Reviewer Attempt时计入`automatic_re_review_per_cycle`。

Run的initial forward execution不消耗上述automatic route额度，但仍消耗Cycle、Work/Control Attempt和Transition总额度。Human明确授权的route仍计入全部global totals；当它超过对应automatic route allowance时必须消费一个exact BudgetGrant，不能把Human route伪装成initial execution。

## Counting and Ownership Rules

- Cycle在append-only Cycle creation record成功提交时计数；一旦创建，不因后续失败、取消或replan退款。
- Attempt在承载其inbound Transition的target identity被分配、且Attempt lifecycle以`scheduled`提交时计数；即使从未`started`、进程崩溃或副作用失败也不退款。
- Transition在committed record写入时计数；被后续history否定的业务结果不删除原计数。
- Automatic route在对应target Transition commit时计数；grant只允许该次admission，不重置或重写历史used值。
- LLM/tool调用和verification command在外部副作用前reservation；见下文resource lifecycle。
- 每个scheduled `code_agent` Attempt只能建立一个`resource_kind = code_backend_operation` aggregate reservation；Backend内部LLM/tool activity只结算到该envelope，不能生成第二套Backend counter或刷新额度。
- aggregate maximum必须由可信Host wrapper在side effect发生前强制执行；Backend只能消费immutable envelope，不能把事后usage报告当作超额执行的授权。
- Active time由可信Host clock度量Run、Attempt与controlled Backend operation的合同窗口；pre-start Host setup只计Run，Backend执行结算到aggregate预留的target-Attempt与Run active dimensions但不改变Attempt lifecycle，target Attempt启动后的trusted verification同时计Attempt与Run，被动paused delivery等待不计入。

Prompt、completion和total token，以及normalized provider cost，仅作审计维度。provider未返回usage时必须记录`unknown`，不能写成0、估算成0或据此通过hard gate。第一版不得用token或currency决定`allow`、`human_gate`或`halt`。

## Execution Ledger and Event Identity

所有policy、reservation、failure、grant和decision events都append到Run现有的`execution_history.jsonl`。不得新增一个拥有独立可漂移head的`budget_history.jsonl`、mutable counter file或旁路日志。

execution schema `0.4` 增加`record_type: budget`。每个budget record必须具有连续且唯一的Run-local `budget_event_id = budget_event_NNNNNN` 与`budget_event_index`，从1开始且无缺口；bounded state的counter必须等于replayed latest event。grant另有连续唯一的`budget_grant_id = budget_grant_NNNNNN` 与index，但其创建和消费仍由budget records承载。

允许的budget events固定为：

- `policy_initialized`：exactly once，绑定正式Run creation与policy bytes；
- `resource_reserved`：副作用前冻结operation identity、resource kind、maximum charge和heads；
- `resource_settled`：exactly once结算已知actual usage或typed `unknown` audit usage；
- `failure_observed`：冻结canonical fingerprint及occurrence；
- `grant_issued`：绑定validated Human Response snapshot与exact scope；
- `grant_consumed`：绑定唯一admitted Transition；
- `decision_recorded`：冻结`allow | human_gate | halt`及原因。

每个record必须绑定`run_id`、policy version/digest、validated execution/artifact heads、写入时的trusted timestamp以及event-specific identity。未知event、重复ID、index缺口、乱序lifecycle、head回滚、policy漂移或ledger/state不一致均fail closed。

Cycle/Attempt/Transition/automatic route用量由其authoritative execution records重放派生，不能依赖第二份可变`used += 1`记录。Budget events只记录admission证据、resource lifecycle、fingerprint、grant和stop decision，不能取代A02 identity ledger。

### Schema `0.4` bootstrap extension

新Run必须完整遵守A02C01，不把bootstrap作为admission例外。Coordinator先持久化operation、target locator、canonical policy bytes/digest和initial `lease_epoch`，再按`run_root_created -> policy_published -> run_ledger_started -> bootstrap_records_complete -> running_lifecycle_recorded -> checkpoint_committed -> result_committed`物化。正式ledger固定append`Run created(initializing) -> policy_initialized -> bootstrap decision_recorded(allow) -> initial Cycle -> Planner Attempt scheduled -> A03 initial invalidation -> START Transition -> run_lifecycle(initializing -> running)`，checkpoint包含最后resulting execution head后才允许Planner side effect。Bootstrap decision覆盖一次initial Cycle、一次Planner Work Attempt和一次START Transition；实际用量仍从A02 records重放派生。

任一partial bootstrap只能按A02C01由同一`ControlOperation.operation_id`、同key同digest继续严格合法且无副作用的确定性前缀；existing bytes/heads exact、缺失suffix identity/digest已预计算而publication closure未完成时保持`in_progress/materialization_pending`。缺少预授权或副作用结果不确定时终止为`recovery_required`；未知/partial record、head/digest冲突、target已`started`或已证明存在违规Agent/provider/tool/domain-artifact副作用均为`failed` integrity outcome。Schema `0.2`历史顺序不迁移、不补写budget events。

## Resource Reservation and Crash Accounting

每个由项目控制层直接发起的LLM call、tool call和verification command必须具有在Attempt内唯一的stable `resource_operation_id`。A05 CodingBackend内部调用是唯一例外：它们共享下文一个`producer_operation_id`与aggregate reservation，只作为receipt/tool audit中的usage members，不得伪装成新的graph resource operation。普通调用顺序固定为：

```text
validate current heads and policy
-> prove per-Attempt and per-Run capacity
-> append resource_reserved
-> perform exactly one external side effect
-> append resource_settled
```

`resource_reserved`至少冻结resource kind、Attempt identity、ordinal、requested units、applicable limits、remaining-before、operation timeout和input/task/config/policy digests。相同operation ID不能再次调用；不同ID也不能绕过Attempt/Run limits或重复同一不确定副作用。

成功settlement使用可信测量的actual units/seconds；token/cost可以是`unknown`。如果进程在reservation后、settlement前崩溃，reservation按声明的maximum charge全额消耗，并将operation视为outcome uncertain；禁止自动退款、自动重新调用或用新operation ID重复副作用。

对A05 `external_result` Pause，每个scheduled `code_agent` Attempt固定建立且只建立一个aggregate reservation：

- `resource_kind = code_backend_operation`；
- pre-prepared reservation identity绑定target `code_agent` Attempt、A05 `producer_operation_id`、task identity/digest、`code_task_context_digest`、backend kind/runtime fingerprint与`WorkspaceManifest` identity/digest，但不得提前分配、猜测或反向声明尚不存在的Pause；后续`pause_prepared`单向绑定该exact reservation identity/digest；
- `maximum_charge`是在现有hard dimensions上的typed envelope，至少统一预留适用的LLM calls、tool calls与active seconds；它不是新的budget dimension，也不允许Backend为内部调用建立独立ledger/counter；
- verification commands不属于Backend aggregate；它们在target Attempt启动后的trusted verification中继续按既有Code Attempt维度独立预留和结算；
- 相同Attempt、task、operation或workspace不能建立第二份aggregate；`lookup`与`fetch_result`只能读取同一operation，不能创建operation、刷新reservation、增加上限、退款或触发retry。

固定durable顺序为：先由A05持久化`external_operation_reserved` identity/initial epoch，再提交引用该producer identity的CodeAgentTask与尚未materialize的WorkspaceManifest；随后append绑定exact task/manifest digests的aggregate `resource_reserved`，由ExternalOperation CAS提交包含该reservation的immutable core，再由current external epoch materialize workspace。以上步骤全部完成后才能append A04 `pause_prepared`，且此前都不得拥有Pause identity；`pause_prepared`单向绑定exact reservation、producer operation与immutable external-operation core contract digest，随后ExternalOperation以fenced one-time CAS补齐exact Pause binding，`pause_opened`再绑定该closure。Pause不冻结其可合法递增的monitoring `lease_epoch`。Pause对外可见后到claim前不得append budget或execution record。`dispatch`、`lookup`、`fetch_result`、`BackendDispatchReceipt`、`BackendOperationStatus`、workspace evidence、immutable external result和delivery snapshot都位于不推进budget/execution head的immutable control/audit namespace。`resume_run`对A04 exact `opened_execution_head`原子claim后，必须验证external-operation epoch history与latest evidence，并在target Attempt `started`前append该aggregate的唯一`resource_settled`；settlement必须绑定producing resume/cancel ControlOperation `operation_id + lease_epoch + phase_revision`、reservation和latest external-operation terminal evidence/epoch，stale writer不能结算。任何可重放graph node都不能在Pause发布前启动Backend。

若operator对尚未claim的`external_result` Pause执行`cancel_pause`，可信Host通过一个combined-ownership phase同时占用Pause cancel owner与Run terminal closure owner，再按A05分类ExternalOperation：仍nonterminal时证明从未dispatch，或持久化cancel intent并由current-epoch watchdog停止exact Backend operation、撤销write lease，最终提交`cancellation_evidence_committed`；ownership前已经normal terminal时保持并验证原`terminal_evidence_committed`。两类final proof都不推进execution head，且必须聚合termination/not-dispatched、lease revocation、verify-empty、bounded drain和post-stop stability；中间`termination_evidence_committed`不足以关闭Pause。A04验证exact final proof后才固定提交`pause_cancelled -> abandoned(if any) -> resource_settled -> terminal_eligibility_verified -> run_lifecycle(paused -> halted | failed) -> terminal checkpoint`；terminal eligibility按ownership时冻结的contracts只解析一次final disposition和pre-close heads。可证明从未dispatch时actual可以为零；已dispatch且usage可信时使用actual，usage未知但停止完整时按reserved maximum。只有全部stop evidence确认后才选择halted；停止完整性失败在Run authority可安全append时选择failed，authority自身不可验证时返回`terminal_closure = unavailable`。预计算、exact且无副作用的publication partial保持`in_progress/materialization_pending`并只能由原operation/current epoch补齐；停止副作用结果不确定时终止为`recovery_required`并使其已占用的closure变为`unavailable`，不能留下terminal owner加pending closure。Target永不启动且不得resume或重新dispatch。

Settlement只能使用可信Host measurement、Backend receipt、tool audit、`WorkspaceSeal`和immutable result交叉验证后的actual vector。FakeCodingBackend fixture必须提供deterministic usage并走同一reservation/settlement入口；CodexSdkBackend reported usage只是evidence，不能自行结算。只有token/cost允许保持audit-only typed `unknown`。所有hard dimension、停止证据与publication partial严格按下节统一matrix处理，不能用maximum accounting把control failure改写为受控停止。

### Unified stop and settlement outcome matrix

本合同按A04互斥优先级分类crash与stop evidence；四个control outcome class的机器枚举由 [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)唯一冻结，下面的settlement table只增加budget后果，不能改写其status或continuation权限。`materializable_publication_prefix`要求所有已存在bytes/heads exact、后续identity/digest已在coordinator或ledger中预计算、且补齐不重新求值decision、不创建新domain identity、不调用Agent/provider/tool/Backend或执行其他外部副作用；它保持operation `in_progress/materialization_pending`。`non_materializable_domain_gap`表示缺少上述预授权、必须重新求值route/grant或外部副作用结果不确定；它终止为`recovery_required`，原Run不自动继续。已证明tamper、counter/policy冲突或违规activity属于control integrity failure；只有权威Run closure仍可完整验证和安全append时，唯一terminal owner才能进一步发布`run_status: failed`，authority自身不可验证时必须返回`terminal_closure = unavailable`。

| Observed boundary | Settlement | Run/control outcome | Required behavior |
|---|---|---|---|
| termination confirmed，trusted hard usage完整且未超maximum | actual vector | terminal policy/operator stop为`halted`；非terminal retryable timeout可以形成canonical typed non-success并交给Coordinator | 持久化terminal evidence后才发布相应run lifecycle |
| termination confirmed，但任一hard usage缺失/unknown且没有矛盾、超额或继续活动证据 | affected dimensions按reserved maximum | terminal policy/operator stop仍可`halted` | 保留unknown audit reason，不退款、不推断actual |
| termination unconfirmed、write lease revocation unconfirmed、post-stop activity、watchdog失去原operation identity，或可信actual超过maximum；Run authority仍可完整验证和安全append | 保守记录reserved maximum及任何可信observed overage；不能截断observed overage | quarantine workspace/operation；由唯一terminal owner通过`close_run`或cancel embedded tail发布`run_status = failed` | 禁止bundle、resume、retry、redispatch或以`cancelled/halted`结束 |
| `materializable_publication_prefix`，且已存在bytes/heads/identity全部exact | unsettled reservation在materialization期间暂按maximum | operation保持`in_progress/materialization_pending` | 仅原operation/current epoch补齐预计算publication后缀，不重做副作用 |
| `non_materializable_domain_gap`或副作用结果不确定，且未观察到integrity conflict | unsettled reservation按maximum | terminal `recovery_required`；未持有Run closure时`terminal_closure = not_applicable`，已持有terminal owner时与operation terminal原子变为`unavailable` | 原operation不再推进；不得留下terminal owner加pending closure，仅允许满足A04 source validation的显式replay/fork或operator resolution |
| policy/counter/digest/clock或外部evidence已证明tamper/冲突，但authoritative execution/artifact/policy closure仍完整可验证并安全append | 按适用reservation保守结算 | control operation `failed`，并由唯一terminal owner发布`run_status = failed` | fail closed；不得签发grant或把失败改成halted |
| authoritative execution ledger、artifact registry、policy或其current head自身无法验证、无法读取或不能安全append | 只在coordinator/quarantine authority记录maximum assessment与可信observed overage；不得伪造Run ledger settlement | control operation `failed`，`terminal_closure = unavailable`，不声明新的权威`run_status` | 隔离Run；禁止append伪造failed lifecycle、截断/repair history、resume、fork或把bounded projection当authority |

`halted`只表示控制层证明停止已完成且权威evidence闭合；ControlOperation `failed`表示控制边界失去证明或观察到违规，但只有完整发布failed lifecycle时才有权声明`run_status: failed`。`terminal_closure = unavailable`只适用于已经取得Run terminal owner却无法形成权威closure的情况：原因可以是Run authority损坏，也可以是owner operation因无法消除的停止副作用不确定性而terminal；它本身不声明新的`run_status`。`recovery_required`表示原operation已不能安全继续但尚未证明tamper/违规；未取得Run closure owner时其closure字段为`not_applicable`。可补齐的publication不使用这些terminal结果，而保持`in_progress/materialization_pending`。这些类别不得因UI、错误文本或账面maximum互换。

Active time按可信Host clock与durable lifecycle边界计算：

- task冻结、workspace创建与policy检查等pre-start Host setup从开始到Pause安全发布，只计Run active time；这些stage不启动target Attempt、不产生额外Attempt，也不得调用Backend；
- Backend active interval从成功`dispatch`开始，到immutable external result与`WorkspaceSeal`均完成时结束；该interval在Run paused期间仍结算到`code_backend_operation` aggregate预留的target-Attempt与Run active dimensions，但不能据此把Attempt标为`started`；
- Backend完成后等待Host delivery、claim或operator恢复的时间属于被动paused time，不计active time；`lookup`或`fetch_result`轮询不能延长Backend active interval或刷新预算；
- aggregate active/tool/LLM maximum、operation timeout或operator cancellation到达时，可信Host必须先持久化cancel intent，再由A05 durable watchdog和ContainmentProvider阻止exact operation的新side effect、撤销workspace write capability、终止完整process tree、在bounded grace后containment kill-all、有界关闭output readers并verify-empty；失败时适用上一节appendable failed closure或`terminal_closure = unavailable`规则；
- target Attempt从claim后settlement完成并提交`started`起，到`finished`、安全Pause或明确失败的active interval计入Attempt和Run；trusted verification处于这个interval中；
- 单次project-owned provider/tool/verification timeout必须小于等于该operation自己的limit、Attempt剩余active seconds和Run剩余active seconds三者的最小值；Backend timeout则必须小于等于aggregate reserved active seconds与Run剩余active seconds的最小值；
- clock回退、active interval缺失或crash导致无法可靠settle时，普通Attempt operation按该Attempt可用的剩余active window保守计费，Backend aggregate按reserved maximum active seconds计费，并停止自动重试。

测试必须使用trusted injectable fake clock，不能通过真实sleep验证deadline或active-time gate。

## Bounded State Projection

Graph state不是budget authority。它只保存从validated policy与execution ledger重放得到的bounded projection，至少包括：

- policy version、profile ID、reference和digest；
- latest budget event/grant counters；
- 每个hard dimension的`used`和`remaining`；
- 每个automatic route scope的used/remaining；
- active failure fingerprint、Run内occurrence和causal evidence digests；
- nullable active grant identity、scope和consumption state；
- latest `BudgetDecision` summary、exhausted dimensions和typed stop reason。

完整reservation、settlement、fingerprint和grant history不能注入Agent prompt或复制到bounded state。初始化、恢复、读取、route admission与artifact registration前必须重放authoritative ledger，并要求derived projection与state exact-equal。counter、remaining、policy digest、active fingerprint、grant或stop summary任一缺失/篡改均拒绝继续；不能静默重建已populated损坏state。

## Admission Order

每个可能创建Cycle、Attempt、Transition或外部resource side effect的动作都必须由可信控制层按以下顺序执行：

```text
1. validate execution/artifact/checkpoint heads and compatibility
2. apply A01/A03/A04/A05 safety and risk rules
3. derive canonical FailureFingerprint when a failure caused the route
4. replay policy, usage, reservations and grants
5. produce and persist the route BudgetDecision
6. enter the A02/A03 composite commit: create any Human Request, preallocate the target Attempt, apply A03 target-layer invalidation, then append the committed Transition
7. validate the resulting heads; reserve each resource immediately before its side effect, or perform the A05 pre-start aggregate reservation and Pause publication before Backend dispatch
```

Budget admission只检查proposed action，不得提前创建target Attempt、commit Transition、清除current artifacts、消费grant或调用Agent/provider/tool。如果capacity不足，existing current artifacts与source Attempt保持不变，只能进入本ticket允许的Gate或halt路径。Admission成功后的ControlOperation必须先在coordinator中预计算并冻结decision、scheduled target identity、required invalidation set、Transition identity/canonical digest和各publication pre-head，再严格采用A02/A03及其clarification的复合publication：scheduled target allocation先于A03 invalidation，invalidation先于committed Transition record。该顺序不被本ticket重新声明为跨存储原子事务；预计算facts与existing records/heads exact的side-effect-free partial属于`materializable_publication_prefix`并保持`in_progress/materialization_pending`。若这些identity/digests未预先冻结、必须重新求值admission或副作用结果不确定，则终止为`recovery_required`且只允许operator显式replay/fork；实际head/digest conflict进入`failed`，且target不得启动。

对已由Transition分配的`code_agent` target，subgraph pre-start stages只执行A05冻结的`external_operation_reserved -> task_committed -> workspace_manifest_committed -> reservation_committed -> core_contract_committed -> workspace_materialized`与Pause publication；A04 public paused checkpoint完整包含`opened_execution_head`后才允许current-epoch Host-owned幂等`dispatch`。Backend不能由可重放graph node启动。Host保存immutable result后，`resume_run`必须依次claim、settle、append `pause_consumed`、append `run_lifecycle(paused -> running)`并持久化resume checkpoint，最后才允许`consume_code_agent_result`提交该scheduled Attempt的`started` lifecycle；任何顺序颠倒均fail closed。

一个`allow` decision只绑定该次exact proposed action，不能作为后续任意route的额度票据。若进程在`decision_recorded`之后、对应reservation或Transition commit之前崩溃，只有ControlOperation已按上一段冻结exact target/invalidation/Transition closure、source heads仍exact且未发生副作用时，才作为`materializable_publication_prefix`继续原operation；这只是已授权canonical bytes的materialization，不是重新执行decision或partial-commit repair。缺少任一预计算事实、需要重新求值admission或副作用结果不确定时，原operation终止为`recovery_required`，仅允许operator显式replay/fork。

Budget不能降低risk floor。即使额度充足，高/严重风险、authorization不足、head不一致、accepted-result保护冲突、policy/security/data错误或non-retryable scientific failure也不能获得automatic `allow`。

## `FailureFingerprint 0.1`

可信控制层从typed outcome和validated artifacts构造fingerprint。Canonical body至少包含适用字段：

- failure layer：`control | provider | tool | verification | code | data | scientific | policy | security`；
- stable failure class与code；
- 目标program、tool、verification spec/test IDs；
- 与失败相关的input member IDs和content digests；
- plan、code、base revision/tree、input artifact、runtime config和budget policy digests；
- 适用时使用project-owned semantic projection `code_task_context_digest`与`analysis_execution_context_digest`，而不是直接使用包含本次execution identity的完整`CodeAgentTask.digest`、`WorkspaceManifest.digest`或`AnalysisExecutionSpec.digest`；
- 稳定诊断事实，例如exit code、signal、failing test IDs和sorted structured validator errors。

Canonical body必须排除：

- Run/Cycle/Attempt/Transition、task/spec/workspace、Backend operation/reservation、provider job/thread/session identity；
- timestamp、duration、随机ID、workspace generation和物理/临时/绝对路径；
- Human/Agent自由文本、summary措辞和原始日志；
- 只反映重试次数而非原因的字段。

`code_task_context_digest`必须由task要求与acceptance criteria、输入evidence/artifact digests、exact base revision/tree、backend kind与runtime/policy digest以及path/tool/network policy的canonical semantic projection计算。`analysis_execution_context_digest`必须由verified patch/change digest、effective tree digest、exact base、input code/artifact digests、analysis runtime fingerprint与适用policy的canonical semantic projection计算。两者都排除上一段列出的execution identity、物理路径和时间；完整task/manifest/spec digest仍可作为provenance evidence保存，但不能直接改变重复判定context。

Fingerprint还必须包含`causal_context_digest`：它由目标program/tool/verification IDs、相关input member digests、plan/code/base/config/policy digests以及适用的两个semantic context digest计算，不包含failure code、diagnostic outcome或execution identity。`fingerprint_digest`再由完整canonical body计算。重复判定key固定为同一Run内的`(causal_context_digest, fingerprint_digest)`；只有backend版本/runtime、base、policy、verified patch/effective tree或其他material input/evidence真实变化才建立新context。仅创建新Attempt/Cycle/workspace/job/thread/operation、重复同一Human approval、改写summary、改变物理路径或复制日志都不能规避第二次exact fingerprint升级。

每次`failure_observed`都必须写出该digest在Run内的连续occurrence。第一次exact fingerprint可以进入automatic handling的必要条件是：

- risk为low或medium；
- technical diagnosis唯一且typed；
- failure不属于policy/security/data或non-retryable scientific class；
- route与resource budget充足且terminal reserve仍可保持。

同一exact fingerprint第二次出现时禁止任何automatic fallback，直接请求Human Gate。high/critical risk、诊断歧义、policy/security/data错误和non-retryable scientific failure在第一次出现时就进入Human Gate。head、identity、policy或ledger完整性失败不是可授权重试的普通fingerprint，必须按上文integrity outcome fail closed；不能把该终止描述或映射为`run_status: halted`。

## `BudgetDecision 0.1` and Stop Semantics

每次admission生成typed `BudgetDecision`，至少包含：

- schema version、canonical decision digest、policy identity和validated heads；
- proposed route/resource identity与target kind；
- risk class、nullable failure fingerprint与occurrence；
- 所有相关dimensions的used、remaining与projected-after；
- nullable grant identity；
- `decision = allow | human_gate | halt`；
- stable reason code与允许的next control action。

固定决策规则为：

- Automatic route额度耗尽、第二次exact fingerprint、Work Attempt不足，或LLM/tool/verification/active-time资源不足时，进入Human Gate，但前提是terminal reserve与绝对ceilings仍可完整承载该收尾链。
- Human Gate可以解释停止、请求外部动作或签发一次有限grant；它不能直接执行工作Agent、修改policy或accepted memory。
- Control Attempt或Transition绝对ceiling将被突破、terminal reserve已按validated history合法耗尽，或没有足够reserve到达安全结尾时，提交deterministic stop evidence，并以该evidence作为terminal trigger调用A04唯一`close_run`发布`run_status = halted`。
- 无法证明heads/counters/policy/clock一致，reservation或grant history损坏，或Host不能证明external operation已经停止时，属于control integrity failure；authority仍可验证和安全append时由唯一terminal owner发布`run_status = failed`，authority自身不可验证时返回`terminal_closure = unavailable`。不得签发新的BudgetDecision、Pause或grant来把失败改写为受控停止。
- `halted`只允许写必要的deterministic audit/control evidence；不得运行Agent、provider/tool、Code Agent，不得生成或更新accepted memory。

不得新增`budget_exhausted` Run status。预算结果由`BudgetDecision`与typed reason表达，并映射为A04 paused Human Gate或既有`halted` terminal状态；A05的`budget_exhausted`只能是structured Code Agent/control outcome，不是Run status。

资源预算耗尽后的terminal tail必须是deterministic control code，不得依赖新的LLM/provider/tool调用。预算停止不能被解释为scientific success或accepted result。

## Reserved Terminal Control Tail

每个Run从创建时保留5个Control Attempts和6个Transitions。普通forward、fallback、Human-approved work route、Agent请求或resource call都不能消费该reserve。

Reserve只允许一个带typed `stop_sequence_id`的安全收尾链使用。完整6条Transition和5个target Control Attempts覆盖A01/A02/A04允许的唯一完整收尾链；Human Gate request Attempt与response validation Attempt是两个不同Control Attempts：

```text
current Attempt -> Decision Coordinator -> Human Gate request -> PAUSE
-> external Human Response -> Human Gate validation
-> Decision Coordinator -> Memory Report -> END
```

若budget decision本身已经由current Coordinator产生，可以省略第一条inbound Transition和对应的新Coordinator Attempt；未使用的reserve仍保留，不能转给普通路线。reserve中的target Attempt和Transition仍计入Run absolute totals。每次普通admission必须证明动作提交后仍剩余完整5/6 reserve；否则该普通动作不得执行。

该reserve只保证一次well-formed Human Response validation和随后收尾，不保证无限invalid-response retries。每份response在validator `started`前已按A04完成old `pause_consumed`、`run_lifecycle(paused -> running)`与resume checkpoint；每个invalid response仍消费一个Human Gate validation Control Attempt与一条external control Transition。Validator终结后先为exact next Pause proposal append本ticket的`decision_recorded(allow_repause | halt)`。只有仍能保留下一次validation加`Decision Coordinator -> Memory Report -> END`所需的3个Control Attempts和4条Transitions时，A04才按new `pause_prepared` → prepared checkpoint → `run_lifecycle(running -> paused)` → new `pause_opened` → public paused checkpoint顺序发布新的`human_input` Pause；否则以该exact decision resulting head确定性派生并执行唯一`close_run`，由其追加`run_lifecycle(running -> halted)`、terminal checkpoint和result，不创建无容量的新Pause，也不接受新的response。

若进入Human Gate前已经无法保留所需reserve，控制层不得尝试部分链或先运行Gate Agent，必须先提交typed stop decision/evidence，再由deterministic `close_run`完成最小`halted` terminal closure。任何伪造`stop_sequence_id`、不在allowed tail中的edge、绕过Run closure owner直接追加lifecycle或试图从reserve返回Work Attempt都fail closed。

## `BudgetGrant 0.1`

Human只能通过typed `approve_budget_window` action请求一个有限窗口。可信Host验证actor scope、A04 Pause、Human Response snapshot和heads后，由控制层签发grant；自由文本中的“继续”“无限重试”或数值不具有授权效果。

Grant至少绑定：

- `budget_grant_id`/index、Run/Case/Cycle identity和policy digest；
- exact Human Request/Response/Pause identity、response snapshot path与digest；
- exact route class、failure fingerprint digest与occurrence；
- deterministic next target Attempt ID/kind/node和inbound Transition intent；
- `additional_opportunities = 1`；
- issued/consumed lifecycle与authorized actor scope。

Grant只允许对应automatic route allowance增加一次admission机会；historical used值继续增加。它不能增加Cycles、Work Attempts、Control Attempts、Transitions、LLM/tool/verification/active-time global hard ceilings，不能恢复terminal reserve，也不能绕过risk、security、data、accepted-result、head或compatibility检查。

Grant必须与exact target Transition形成一个不可拆分的逻辑commit，并用`grant_consumed`绑定该Transition。实现若能在同一durable transaction中提交两类record可以一次完成；否则ControlOperation必须在append前冻结grant、deterministic target/Transition identity、required invalidation set、canonical digests和pre-heads，随后固定执行`grant_consumed -> target Attempt scheduled -> A03 invalidation -> committed Transition -> head validation`。中间崩溃在预计算facts与existing records/heads exact且无新副作用时属于`materializable_publication_prefix`，保持`in_progress/materialization_pending`并只补齐缺失bytes；缺少预计算事实或需要重新消费/求值grant时终止为`recovery_required`，实际identity/head/digest conflict进入`failed`。已消费grant不退款，且除上述原operation materialization外不得自动创建Transition或invalidation；scheduled target在closure完整前不得启动。相同grant重复消费、错误route/fingerprint/Cycle/target、snapshot或actor不一致、旧Pause授权复用、竞争claim落败、target在签发后改变，均拒绝且不能自动签发替代grant。

A04 `approve_rerun`仍表示同一Run/Cycle中的新Analysis Attempt；它不自动扩大budget。如果该route已经用尽automatic allowance，必须同时满足本节exact grant合同。replan仍创建新Cycle并受Cycles/Run与automatic replan上限约束。

## Pause Deadline

Pause deadline由`opened_at + policy.pause_deadline_seconds`派生，使用trusted Host clock。deadline不是background timer，也不产生自动ledger event。

- deadline前成功claim的resume继续遵守A04 single-use lifecycle；后续执行时钟越过deadline不撤销已成功claim。
- deadline后调用`resume_run`返回typed `pause_expired`，不得claim、consume、创建Attempt、commit Transition或修改Run/Pause/history。
- Run在存储上保持`run_status = paused`，但该Pause已不具备resume资格；只有trusted operator显式调用`cancel_pause`、`replay_run`或`fork_run`才能继续处置。
- 不自动cancel、不自动转`halted`、不自动replay/fork，也不因轮询或进程启动写事件。
- clock regression、trusted time缺失或deadline计算溢出时fail closed并拒绝resume。

## Start, Resume, Replay and Fork Policy

- `start_run`默认选择`balanced_v1`；只有具有明确profile-selection scope的trusted Host可以选择allowlist中的其他profile。
- `resume_run`必须exact-match原Run的policy bytes、version、profile、digest和runtime fingerprint；调用方不能提供替换值。Phase B schema `0.4` runtime只原地resume exact supported `0.4` Run，不对`0.3`或更早Run原地resume/迁移；这不否定A04 schema `0.3`合同可由显式支持`0.3`的runtime处理自身Pause。
- `replay_run`创建全新child Run并从0计数。若source policy/profile仍受当前runtime支持，则复用其canonical policy；pre-A06 source默认使用当前`balanced_v1`，且必须作为新child policy显式记录。
- `fork_run`创建全新child Run并从0计数；具备scope的Host可以为target选择任一当前allowlisted profile，不要求与source相同。
- replay/fork均不继承reservation、failure occurrence、grant、Pause deadline、used counters、current pointers、Human authorization或accepted state；source Run不被修改。
- policy不受支持、source heads不可验证或A04 replay/fork前置条件不满足时拒绝操作，不能通过选择较宽profile修复损坏source。

## Required Phase B and A07 Acceptance Inputs

A07及后续Phase B implementation tickets至少必须映射并验证：

- `A06-BUDGET-001`：每个automatic route在limit前允许，达到limit后进入Gate；initial forward execution不误扣automatic额度；
- `A06-BUDGET-002`：Work/Control/Transition absolute ceilings和5/6 terminal reserve，普通route无法消费reserve；invalid response只有在仍保留下一次validation及后续收尾合计3 Control/4 Transition时才创建新Pause；
- `A06-BUDGET-003`：LLM/tool/verification reservation、settlement、unsettled crash charge和重复operation拒绝；
- `A06-BUDGET-004`：每个`code_agent` Attempt恰有一个`code_backend_operation` aggregate reservation；严格验证producer stub、task、unmaterialized WorkspaceManifest、aggregate reservation、immutable core、workspace materialization与后续`pause_prepared`的无环顺序，覆盖现有LLM/tool/active dimensions，Fake deterministic usage与future real backend evidence走同一lifecycle；
- `A06-BUDGET-005`：aggregate与ExternalOperation不预占Pause identity、prepared后one-time binding、Pause期间dispatch/lookup/fetch/result zero budget/execution-head drift、post-claim/pre-start maximum-or-actual settlement，以及claim后settlement crash按materializable/in-progress、terminal recovery-required和failed三类fail closed；
- `A06-BUDGET-006`：pre-start setup、Backend operation、paused delivery等待与post-start trusted verification的Run/Attempt active-time边界和fake clock；
- `A06-BUDGET-007`：`lookup`/`fetch_result`不创建新operation、不刷新预算、不退款，Backend及任何provider thread/job/session没有独立budget/retry/stop authority；
- `A06-BUDGET-008`：aggregate maximum/timeout与operator cancellation先持久化cancel intent，再经A05 watchdog、exact `cancel`和ContainmentProvider停止完整process tree、撤销write lease、bounded grace、kill-all、关闭output readers并verify-empty；完整terminal stop为`halted`，usage未知但停止完整按maximum且可halted，超额usage、停止/lease失败或停止后activity为`failed`；
- `A06-BUDGET-009`：second exact fingerprint升级；新Attempt/workspace/job identity不改变`code_task_context_digest`或`analysis_execution_context_digest`，backend/base/policy/verified patch/effective tree等material evidence变化才生成新context/fingerprint；
- `A06-BUDGET-010`：first-occurrence technical/risk gates，以及policy/security/data/scientific failure immediate escalation；
- `A06-BUDGET-011`：single-use Human grant、错误actor/scope/route/fingerprint/target、竞争与重复消费拒绝，global ceiling不可突破；
- `A06-BUDGET-012`：Pause deadline前后边界，expired resume无mutation且必须显式cancel/replay/fork；
- `A06-BUDGET-013`：budget policy、state projection、ledger counter、event identity、reservation、fingerprint和grant篡改作为control integrity failure；authority仍可验证和安全append时由唯一terminal owner发布`run_status = failed`，authority自身不可验证时返回`terminal_closure = unavailable`；
- `A06-BUDGET-014`：schema `0.4` start遵守A02C01 bootstrap、resume exact policy、replay/fork计数清零，并验证A02 legacy `status: running`、A04 schema `0.3`语义支持与Phase B `0.4`禁止原地迁移之间的版本边界；
- `A06-BUDGET-015`：missing token/cost usage保持`unknown`且不参与hard gate；
- `A06-BUDGET-016`：budget stop不能绕过risk floor、Human Gate、A03 invalidation或accepted-result保护；
- `A06-BUDGET-017`：terminal resource exhaustion不触发新的provider/tool调用或accepted memory。
- `A06-BUDGET-018`：统一outcome matrix区分confirmed-stop actual、confirmed-stop unknown/max、unconfirmed/quarantined failed、materializable publication prefix、non-materializable domain gap与integrity failed，并分别映射到`halted`、`in_progress/materialization_pending`、terminal `recovery_required`或ControlOperation `failed`，各类Run/control outcome不可互换。
- `A06-BUDGET-019`：integrity failure严格区分“authoritative Run closure仍可验证/append并由唯一terminal owner发布`run_status = failed`”与“authority自身不可验证、只允许coordinator quarantine evidence及`terminal_closure = unavailable`”；同时验证terminal `recovery_required`在未持有Run closure时为`not_applicable`、已持有owner时同步为`unavailable`，任何一种`unavailable`都不得伪造Run settlement、failed lifecycle或bounded status。

所有runtime、execution schema validator、budget ledger builder、fake clock、graph integration和tests必须拆入新的Phase B implementation tickets；不能在执行本design ticket时顺带实现。

## Deliverables

- decision-complete的budget profile、typed contracts、accounting、admission和stop规则；
- A04 Pause、A05 Code Agent与A07 harness可以直接引用的policy/fingerprint/grant输入；
- execution schema `0.4`和bounded state的文档变更计划；
- 受影响核心source-of-truth文档的同步；
- 独立`docs/tickets/completions/A06_COMPLETION.md`及completion索引更新。

## Acceptance Criteria

- ticket内没有待确认架构问题、未决占位符或内嵌执行记录；
- 每个允许循环、resource side effect和Human extension都能回答何时admit、何时计数、何时停止以及崩溃后如何处理；
- policy、ledger、bounded state、Pause、CodeAgentTask、Backend aggregate、WorkspaceManifest与runtime fingerprint具有唯一且可验证的digest关系；
- failure fingerprint只对material evidence敏感，第二次exact occurrence不能自动回退；
- CodeAgentSubgraph pre-start stages不创建额外Attempt或automatic route计数；CodingBackend只消费单一aggregate envelope，不能拥有独立budget、refund、retry或stop authority；
- aggregate maximum/timeout由durable watchdog和current lease epoch强制执行，operator cancellation与A04 Pause lifecycle有确定顺序；unknown usage、超额usage、停止失败、lease revocation失败、publication partial与停止后activity严格按统一matrix分类，不能被maximum settlement掩盖；
- Human grant只有exact +1能力，不能重置计数、恢复reserve或突破Run hard ceilings；
- terminal reserve按A02/A04的request/validation双Attempt模型固定为5 Control/6 Transition，invalid response不能创建无容量的新Pause；
- Pause expiry没有隐藏background mutation，resume/replay/fork compatibility明确；
- A07/Phase B无需自行发明预算数值、event identity、route exhaustion或stop语义；
- Allowed Files/Do Not Touch、相对links和status文档一致，且没有runtime/tests/configs diff。

## Pre-freeze Review Gate

本ticket从`review`提升为`ready`前必须确认：

- YAML保持`status: review`，直到A02C01与A04–A07完成交叉审查、catalog核验并获得用户最终确认；
- ticket内没有待确认架构问题、未决占位符或内嵌执行记录；
- A04的Pause/deadline/claim规则和A05的budget envelope/status语义与本ticket一致；
- A02C01已冻结schema `0.4` bootstrap且本ticket不再重定义另一顺序；
- A05 pre-start reservation、Host-owned dispatch、claim/settlement/pre-start顺序与本ticket一致；
- A07完整保留本ticket的policy、aggregate Backend reservation、active-time、semantic context fingerprint、grant、deadline、reserve与stop scenarios；
- dependency、Allowed Files与Do Not Touch无冲突，所有相对Markdown links和Read First仓库路径有效；
- Phase Overview、Docs Index和Current State一致记录A02C01与A04–A07为`review`；
- review diff不包含runtime、tests、configs、dependency或provider改动。

## Verification

执行本design ticket时只运行静态、文档与scope检查：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

还必须验证：

- ticket在`ready`之后只变更YAML lifecycle metadata，正文与执行前冻结commit一致；
- A04/A05及本ticket的其他dependencies已`completed`，A07正文未修改；
- Required Documentation Updates已同步，并明确区分“已确认的A06目标合同”与“尚未由Phase B实现的budget runtime”；
- Phase Overview、Docs Index与Current State一致记录A06完成及A07的当时lifecycle状态；
- `docs/tickets/completions/A06_COMPLETION.md`已建立并加入completion index；
- Allowed Files/Do Not Touch与实际diff一致，所有现行Markdown relative links有效；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`和accepted artifacts没有本ticket产生的diff；
- 不运行runtime、benchmark或live-provider测试，因为本ticket只冻结设计合同。

## Stop Conditions

- 必须改变A01 route、A02 identity、A03 registry/accepted-result、A04 Pause或A05 Code Agent既有语义才能完成本合同；
- 必须新增未批准Run status、graph topology、provider billing、生产认证、checkpoint backend、migration或partial-commit repair；
- 任何设计允许Agent、Human自由文本、provider或route payload修改policy/counter，或允许grant突破global ceiling、安全边界或accepted-result保护；
- 无法在副作用前durably reserve，或无法从execution ledger唯一重放budget state；
- CodingBackend、Codex thread/job或未来SandboxAgent需要独立budget ledger、refund、retry或stop authority，或无法把Backend内部使用结算到唯一`code_backend_operation` aggregate；
- 无法构造排除execution identity的`code_task_context_digest`或`analysis_execution_context_digest`，导致新Attempt/workspace/job可以规避重复失败升级；
- 需要扩大Allowed Files或触碰Do Not Touch；
- A04–A07交叉审查发现会改变本ticket核心contract的冲突；此时保持`review`并先请求用户确认，不现场执行实现。

## Required Documentation Updates

执行本ticket时同步：

- `docs/ARCHITECTURE.md`：trusted budget admission、terminal reserve与control flow；
- `docs/AGENT_ROLES_AND_BOUNDARIES.md`：control plane、Agent、Host与Human authority；
- `docs/STATE_SCHEMA.md`：execution schema `0.4`、budget events与bounded projection；
- `docs/ARTIFACT_CONTRACTS.md`：immutable `budget_policy.json`及digest binding；
- `docs/SECURITY_AND_DATA_POLICY.md`：policy immutability、grant scope与fail-closed rules；
- `docs/EVALS_AND_OBSERVABILITY.md`：resource usage、unknown token/cost和stop metrics；
- `docs/VERIFICATION_GUIDE.md`：deterministic budget/fingerprint/deadline/tamper scenarios；
- `docs/README.md`、Phase Overview、`docs/REPO_CURRENT_STATE.md`和`docs/DECISION_LOG.md`；
- 独立completion record与completion index。
