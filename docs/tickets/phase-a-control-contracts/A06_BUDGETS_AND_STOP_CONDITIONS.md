---
ticket_id: A06
phase: phase-a-control-contracts
status: review
type: design
depends_on: [A01, A02, A03, A03C01, A04, A05]
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
- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)
- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)
- [`A05_CODE_AGENT_CONTRACT.md`](A05_CODE_AGENT_CONTRACT.md)
- `src/lqcd_agent/graph/state.py`
- `src/lqcd_agent/graph/routing.py`
- `src/lqcd_agent/llm/trace.py`

## Scope

- 冻结 `BudgetPolicy 0.1`、`BudgetDecision 0.1`、`FailureFingerprint 0.1` 和 single-use `BudgetGrant 0.1`；
- 冻结 `balanced_v1` 与 deterministic `phase_b_test` allowlisted profiles；
- 冻结 Cycle、automatic fallback、Attempt、Transition、LLM、tool、verification 和 active-time 的 ownership 与计数时点；
- 冻结 execution schema `0.4` 的 budget ledger events、Run-local identity 和 bounded state projection；
- 冻结副作用前 reservation、crash accounting、admission order 和 terminal control reserve；
- 冻结 failure fingerprint、重复失败、risk-first escalation 与停止语义；
- 冻结 Human `approve_budget_window` 的 exact scope、single-use consumption 和绝对 ceiling；
- 冻结 Pause deadline，以及 start/resume/replay/fork 的 policy compatibility；
- 把 runtime、schema validators、budget ledger 和 tests 交给后续 Phase B implementation tickets。

## Non-goals

- 不实现 budget manager、ledger builder、state validator、clock、graph edge、API、CLI 或 tests；
- 不修改 A01 路线、A02 identity、A03 artifact/accepted-result policy、A04 Pause lifecycle 或 A05 Code Agent outcome 含义；
- 不实现 token 或货币 hard budget，不设计 provider billing、pricing normalization、invoice reconciliation 或成本优化；
- 不新增生产认证、distributed lock、checkpoint backend、partial-commit repair 或 schema migration；
- 不允许 Agent、provider、route payload、Human 自由文本或恢复 payload 修改 policy 或 counters；
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

Agent、model/provider output、tool output、Code Agent adapter、graph route payload和Human自由文本都是不可信输入。它们可以提供候选诊断或usage evidence，但不能选择profile、改写policy、直接递增/递减counter、签发grant或提交Transition。

## Contract Versions and Run Binding

`BudgetPolicy`、`BudgetDecision`、`FailureFingerprint` 和 `BudgetGrant` 使用独立 schema version `0.1`。后续实现本合同会把 execution schema 从 A04 的 `0.3` 升级为 `0.4`；A03 artifact registry schema不因本 ticket 改变。

每个新 Run 在正式 Run creation record 前由可信 Host 选择一个 allowlisted profile，并生成：

```text
<run_root>/budget_policy.json
```

`budget_policy.json` 是 project-owned immutable control artifact，不属于七个 current artifact slots，不允许被 Agent、tool、external adapter 或 Human payload覆盖。其 canonical digest 计算时排除自描述的 digest 字段；文件内容、reference 或digest任一不一致均 fail closed。

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
| Reserved terminal Control Attempts | 4 | 4 |
| Reserved terminal Transitions | 5 | 5 |

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
- Active time由可信Host clock度量Attempt或external operation实际执行窗口；被动paused时间不计入，等待中的外部Code Agent操作本身属于active operation并计入。

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

## Resource Reservation and Crash Accounting

每个LLM call、tool call和verification command必须具有在Attempt内唯一的stable `resource_operation_id`。调用顺序固定为：

```text
validate current heads and policy
-> prove per-Attempt and per-Run capacity
-> append resource_reserved
-> perform exactly one external side effect
-> append resource_settled
```

`resource_reserved`至少冻结resource kind、Attempt identity、ordinal、requested units、applicable limits、remaining-before、operation timeout和input/task/config/policy digests。相同operation ID不能再次调用；不同ID也不能绕过Attempt/Run limits或重复同一不确定副作用。

成功settlement使用可信测量的actual units/seconds；token/cost可以是`unknown`。如果进程在reservation后、settlement前崩溃，reservation按声明的maximum charge全额消耗，并将operation视为outcome uncertain；禁止自动退款、自动重新调用或用新operation ID重复副作用。

对A05 `external_result` Pause，`resource_reserved`必须在Pause `opened`之前持久化，并由Pause绑定exact reservation identity/digest。Pause对外可见后到claim前不得append budget record；dispatch receipt、workspace evidence、delivery snapshot和usage evidence位于不推进execution head的immutable control/audit namespace。`resume_run`对A04 exact `opened_execution_head`完成claim后，必须在target Attempt `started`前append该reservation的唯一`resource_settled`。claim后settlement不完整时按maximum charge计费并返回`recovery_required`，不得重新dispatch或启动target Attempt。

Active time按可信Host clock与durable lifecycle边界计算：

- Attempt从`started`到`finished`、安全Pause或明确失败的active interval计费；
- Run active time是所有Attempt与受控external operation active intervals的总和，不把被动Pause等待计入；
- external dispatch在Run paused期间的实际operation interval仍计费；
- 单次provider/tool/verification timeout必须小于等于该operation自己的limit、Attempt剩余active seconds和Run剩余active seconds三者的最小值；
- clock回退、active interval缺失或crash导致无法可靠settle时，按该Attempt可用的剩余active window保守计费并停止自动重试。

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
5. produce and persist BudgetDecision; reserve resource when applicable
6. commit the Transition and A03 current-artifact invalidation atomically as specified by their contracts
7. allow the already-scheduled target Attempt or exact resource operation to execute
```

Budget admission只检查proposed action，不得提前创建target Attempt、commit Transition、清除current artifacts、消费grant或调用Agent/provider/tool。如果capacity不足，existing current artifacts与source Attempt保持不变，只能进入本ticket允许的Gate或halt路径。

一个`allow` decision只绑定该次exact proposed action，不能作为后续任意route的额度票据。若进程在`decision_recorded`之后、对应reservation或Transition commit之前崩溃，恢复必须报告A04 `recovery_required`并禁止自动重放decision、消费grant、调度Attempt或修补partial sequence；只有在完整source heads仍可验证时由operator显式replay/fork。本ticket不引入partial-commit repair。

Budget不能降低risk floor。即使额度充足，高/严重风险、authorization不足、head不一致、accepted-result保护冲突、policy/security/data错误或non-retryable scientific failure也不能获得automatic `allow`。

## `FailureFingerprint 0.1`

可信控制层从typed outcome和validated artifacts构造fingerprint。Canonical body至少包含适用字段：

- failure layer：`control | provider | tool | verification | code | data | scientific | policy | security`；
- stable failure class与code；
- 目标program、tool、verification spec/test IDs；
- 与失败相关的input member IDs和content digests；
- plan、code、base revision/tree、CodeAgentTask、runtime config和budget policy digests；
- 稳定诊断事实，例如exit code、signal、failing test IDs和sorted structured validator errors。

Canonical body必须排除：

- Run/Cycle/Attempt/Transition identity；
- timestamp、duration、随机ID和临时/绝对路径；
- Human/Agent自由文本、summary措辞和原始日志；
- 只反映重试次数而非原因的字段。

Fingerprint还必须包含`causal_context_digest`：它由目标program/tool/verification IDs、相关input member digests以及plan/code/base/task/config/policy digests计算，不包含failure code、diagnostic outcome或execution identity。`fingerprint_digest`再由完整canonical body计算。重复判定key固定为同一Run内的`(causal_context_digest, fingerprint_digest)`；因为material input/evidence/config/policy digests属于causal context，只有这些稳定证据实际变化才会建立新的context。仅创建新Attempt/Cycle、重复同一Human approval、改写summary、改变临时路径或复制日志都不算新证据。

每次`failure_observed`都必须写出该digest在Run内的连续occurrence。第一次exact fingerprint可以进入automatic handling的必要条件是：

- risk为low或medium；
- technical diagnosis唯一且typed；
- failure不属于policy/security/data或non-retryable scientific class；
- route与resource budget充足且terminal reserve仍可保持。

同一exact fingerprint第二次出现时禁止任何automatic fallback，直接请求Human Gate。high/critical risk、诊断歧义、policy/security/data错误和non-retryable scientific failure在第一次出现时就进入Human Gate。head、identity、policy或ledger完整性失败不是可授权重试的普通fingerprint，必须按fail-closed规则halt。

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
- Control Attempt或Transition绝对ceiling将被突破、terminal reserve已经受损、无法证明heads/counters一致，或没有足够reserve到达安全结尾时，直接fail closed为Run `status: halted`。
- `halted`只允许写必要的deterministic audit/control evidence；不得运行Agent、provider/tool、Code Agent，不得生成或更新accepted memory。

不得新增`budget_exhausted` Run status。预算结果由`BudgetDecision`与typed reason表达，并映射为A04 paused Human Gate或既有`halted` terminal状态；A05的`budget_exhausted`只能是structured Code Agent/control outcome，不是Run status。

资源预算耗尽后的terminal tail必须是deterministic control code，不得依赖新的LLM/provider/tool调用。预算停止不能被解释为scientific success或accepted result。

## Reserved Terminal Control Tail

每个Run从创建时保留4个Control Attempts和5个Transitions。普通forward、fallback、Human-approved work route、Agent请求或resource call都不能消费该reserve。

Reserve只允许一个带typed `stop_sequence_id`的安全收尾链使用。完整5条Transition和4个target Control Attempts覆盖A01允许的唯一完整收尾链：

```text
current Attempt -> Decision Coordinator -> Human Gate -> Decision Coordinator -> Memory Report -> END
```

若budget decision本身已经由current Coordinator产生，可以省略第一条inbound Transition和对应的新Coordinator Attempt；未使用的reserve仍保留，不能转给普通路线。reserve中的target Attempt和Transition仍计入Run absolute totals。每次普通admission必须证明动作提交后仍剩余完整4/5 reserve；否则该普通动作不得执行。

若进入Human Gate前已经无法保留所需reserve，控制层不得尝试部分链或先运行Gate Agent，必须直接提交最小`halted` audit evidence。任何伪造`stop_sequence_id`、不在allowed tail中的edge或试图从reserve返回Work Attempt都fail closed。

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

Grant必须在exact target Transition commit时原子消费，并用`grant_consumed`绑定该Transition。相同grant重复消费、错误route/fingerprint/Cycle/target、snapshot或actor不一致、旧Pause授权复用、竞争claim落败、target在签发后改变，均拒绝且不能自动签发替代grant。

A04 `approve_rerun`仍表示同一Run/Cycle中的新Analysis Attempt；它不自动扩大budget。如果该route已经用尽automatic allowance，必须同时满足本节exact grant合同。replan仍创建新Cycle并受Cycles/Run与automatic replan上限约束。

## Pause Deadline

Pause deadline由`opened_at + policy.pause_deadline_seconds`派生，使用trusted Host clock。deadline不是background timer，也不产生自动ledger event。

- deadline前成功claim的resume继续遵守A04 single-use lifecycle；后续执行时钟越过deadline不撤销已成功claim。
- deadline后调用`resume_run`返回typed `pause_expired`，不得claim、consume、创建Attempt、commit Transition或修改Run/Pause/history。
- Run在存储上保持`status: paused`，但该Pause已不具备resume资格；只有trusted operator显式调用`cancel_pause`、`replay_run`或`fork_run`才能继续处置。
- 不自动cancel、不自动转`halted`、不自动replay/fork，也不因轮询或进程启动写事件。
- clock regression、trusted time缺失或deadline计算溢出时fail closed并拒绝resume。

## Start, Resume, Replay and Fork Policy

- `start_run`默认选择`balanced_v1`；只有具有明确profile-selection scope的trusted Host可以选择allowlist中的其他profile。
- `resume_run`必须exact-match原Run的policy bytes、version、profile、digest和runtime fingerprint；调用方不能提供替换值。schema `0.3`及更早Run不可resume且不自动迁移。
- `replay_run`创建全新child Run并从0计数。若source policy/profile仍受当前runtime支持，则复用其canonical policy；pre-A06 source默认使用当前`balanced_v1`，且必须作为新child policy显式记录。
- `fork_run`创建全新child Run并从0计数；具备scope的Host可以为target选择任一当前allowlisted profile，不要求与source相同。
- replay/fork均不继承reservation、failure occurrence、grant、Pause deadline、used counters、current pointers、Human authorization或accepted state；source Run不被修改。
- policy不受支持、source heads不可验证或A04 replay/fork前置条件不满足时拒绝操作，不能通过选择较宽profile修复损坏source。

## Required Phase B and A07 Acceptance Inputs

A07及后续Phase B implementation tickets至少必须映射并验证：

- 每个automatic route在limit前允许，达到limit后进入Gate；initial forward execution不误扣automatic额度；
- Work/Control/Transition absolute ceilings和4/5 terminal reserve，普通route无法消费reserve；
- LLM/tool/verification reservation、settlement、unsettled crash charge和重复operation拒绝；
- `external_result` operation的pre-open reservation、Pause期间zero execution-head drift、post-claim/pre-start settlement与claim后settlement crash fail-closed；
- per-Attempt/per-Run active time、paused time排除、external operation计费和fake clock；
- second exact fingerprint升级，真实material evidence变化生成新fingerprint，identity/summary变化不生成新fingerprint；
- first-occurrence technical/risk gates，以及policy/security/data/scientific failure immediate escalation；
- single-use Human grant、错误actor/scope/route/fingerprint/target、竞争与重复消费拒绝，global ceiling不可突破；
- Pause deadline前后边界，expired resume无mutation且必须显式cancel/replay/fork；
- budget policy、state projection、ledger counter、event identity、reservation、fingerprint和grant篡改fail closed；
- start默认profile、resume exact policy、replay/fork计数清零和schema `0.3`不迁移；
- missing token/cost usage保持`unknown`且不参与hard gate；
- budget stop不能绕过risk floor、Human Gate、A03 invalidation或accepted-result保护；
- terminal resource exhaustion不触发新的provider/tool调用或accepted memory。

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
- policy、ledger、bounded state、Pause、CodeAgentTask与runtime fingerprint具有唯一且可验证的digest关系；
- failure fingerprint只对material evidence敏感，第二次exact occurrence不能自动回退；
- Human grant只有exact +1能力，不能重置计数、恢复reserve或突破Run hard ceilings；
- Pause expiry没有隐藏background mutation，resume/replay/fork compatibility明确；
- A07/Phase B无需自行发明预算数值、event identity、route exhaustion或stop语义；
- Allowed Files/Do Not Touch、相对links和status文档一致，且没有runtime/tests/configs diff。

## Pre-freeze Review Gate

本ticket从`review`提升为`ready`前必须确认：

- YAML保持`status: review`，直到A04–A07完成交叉审查并获得用户统一确认；
- ticket内没有待确认架构问题、未决占位符或内嵌执行记录；
- A04的Pause/deadline/claim规则和A05的budget envelope/status语义与本ticket一致；
- A07完整保留本ticket的policy、reservation、fingerprint、grant、deadline、reserve与stop scenarios；
- dependency、Allowed Files与Do Not Touch无冲突，所有相对Markdown links和Read First仓库路径有效；
- Phase Overview、Docs Index和Current State一致记录A04–A07为`review`；
- review diff不包含runtime、tests、configs、dependency或provider改动。

## Verification

执行本design ticket时只运行静态、文档与scope检查：

```bash
git diff --check
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
