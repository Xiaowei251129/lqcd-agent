---
ticket_id: A02C01
phase: phase-a-control-contracts
status: review
type: corrective-implementation
depends_on: [A02, A03, A03C01]
---

# 修正 Execution 0.4 Run Bootstrap 顺序

## Goal

为 execution schema `0.4+` 冻结预算可审计、可幂等恢复且在 Planner 副作用前完成的 Run bootstrap 顺序，并建立正式 Run ledger 之前可持久化的 `ControlOperation 0.1`，解决 A02 schema `0.2` 固定四记录初始化、A06 admission 合同与首次持久化幂等之间的冲突。

本 ticket 使用仓库支持的 `corrective-implementation` 类型冻结后继 schema 的纠正合同和下游实现约束；该治理分类不表示本轮实现 runtime。本 ticket 不修改 A02 已完成正文、当前 schema `0.2` runtime、graph、tests 或历史 Run。

## Why

A02 §5 将新 Run 的前四条权威记录固定为 Run、initial Cycle、Planner Attempt 和 START Transition。A06 schema `0.4` 又要求 budget policy 与 admission evidence 在可能创建 Cycle、Attempt 或 Transition 的动作前持久化。由于正式 Run ledger 在 Run creation 前尚不存在，这两个顺序不能同时通过文字解释成立。

Schema `0.4+` 必须显式扩展 bootstrap，而不是让初始 Cycle/Attempt/Transition 成为不受 budget contract 约束的隐藏例外，也不能追溯改写 schema `0.2` 历史。

此外，`start_run`不能把尚不存在的Run ledger当作自己的幂等authority。若Host先创建Run root或写入`Run created`再记录幂等键，并发请求和该边界上的进程退出都可能产生第二个Run或无法归属的partial prefix。必须先在per-Run root之外建立durable operation ownership，再按确定性phase物化Run。

## Read First

- [`AGENTS.md`](../../../AGENTS.md)
- [`docs/README.md`](../../README.md)
- [`docs/tickets/README.md`](../README.md)
- [`docs/STATE_SCHEMA.md`](../../STATE_SCHEMA.md)
- [`docs/ARTIFACT_CONTRACTS.md`](../../ARTIFACT_CONTRACTS.md)
- [`docs/VERIFICATION_GUIDE.md`](../../VERIFICATION_GUIDE.md)
- [`docs/REPO_CURRENT_STATE.md`](../../REPO_CURRENT_STATE.md)
- [`A02_RUN_CYCLE_ATTEMPT_MODEL.md`](A02_RUN_CYCLE_ATTEMPT_MODEL.md)
- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)
- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)
- [`A06_BUDGETS_AND_STOP_CONDITIONS.md`](A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [`Control Protocol 0.4`](CONTROL_PROTOCOL_0_4.json)
- [`A02 Human Gate Commit-order Clarification`](../corrections/A02_HUMAN_GATE_COMMIT_ORDER_CLARIFICATION.md)
- [`A03 Transition Publication-order Clarification`](../corrections/A03_TRANSITION_PUBLICATION_ORDER_CLARIFICATION.md)

## Scope

- 冻结 schema `0.4+` 的 bootstrap policy、identity、ledger、invalidation、checkpoint 和 side-effect 顺序；
- 冻结 `start_run` bootstrap 的幂等 identity、合法 incomplete prefix 和 fail-closed crash 行为；
- 冻结项目自有`ControlOperation 0.1`、幂等键tombstone、operation phase和per-Run ledger之前的持久化边界；
- 以tracked [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)作为`start_run` phase、edge、authority与evidence的唯一机器可读枚举；
- 明确本 ticket 对 A02 §5 的版本限定 supersession；
- 向 A04、A06、A07 与 Phase B implementation tickets提供一个唯一 bootstrap contract；
- 执行时只同步治理与目标合同文档，不实现 runtime。

## Non-goals

- 不修改 A02、A03、A03C01 completed ticket正文或其完成记录；
- 不改变 schema `0.2` Run bytes、兼容读取、identity、counter或历史 provenance；
- 不实现 BudgetPolicy、ledger builder、checkpoint backend、`start_run`、graph或tests；
- 不批准对已开始 Agent/provider/tool副作用的自动重试或partial-commit repair；
- 不迁移、恢复或补写现有 incomplete Run；
- 不选择分布式生产事务系统、认证、provider或新dependency；Phase B只实现本ticket规定的project-owned SQLite reference backend。

## Allowed Files

本 ticket 提升为 `ready` 并执行时，只允许修改：

- `docs/tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md`：仅允许更新YAML lifecycle metadata；
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`；
- `docs/tickets/completions/A02C01_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

- A01–A03、A03C01及其completion/correction history；
- A04–A07 ticket正文；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`和accepted artifacts；
- 当前 runtime schema、graph topology、checkpoint backend、provider、dependency、认证或secrets；
- milestone、tag或历史Run。

## Versioned Supersession Boundary

- A02 §5继续是execution schema `0.2`的历史权威顺序；本ticket不改写或重新解释其四条记录。
- A02 schema `0.2` Run-created record中的legacy `status: running`只描述该版本当时的创建结果；schema `0.4+`以权威control `run_status: initializing`版本化取代该创建时状态。Reader不得把legacy字段改写成新字段、向旧Run补写lifecycle，或把两种创建顺序混合在同一Run中。
- Execution schema `0.3`是A04 Pause/run-lifecycle语义前身；它不包含本ticket和A06要求的完整bootstrap/budget coordinator合同。显式实现并在runtime fingerprint中声明支持`0.3`的旧runtime可以按A04合同处理自己的Run，但Phase B schema `0.4` runtime不得对`0.3` Run原地resume或迁移，只能在source validation通过后显式replay/fork为新的`0.4` child。
- Execution schema `0.4+`只对bootstrap顺序采用本ticket；A02其余Run/Cycle/Attempt/Transition identity、counter和target-consumption合同继续有效。
- 未知schema、混合顺序或缺少本ticket任一required bootstrap identity/record的Run不得声明为schema `0.4` completed bootstrap。

## Project-owned `ControlOperation 0.1`

Phase B必须在可信`<output_root>/.lqcd/control_operations.sqlite`实现project-owned durable operation coordinator。它位于所有`<case_id>/<run_id>/`目录之外，与每个Run的`checkpoints/graph_checkpoints.sqlite`分离；LangGraph checkpoint不得存放幂等键、claim ownership或operation result authority。若目标filesystem不能提供SQLite所需的exclusive transaction/locking与durability语义，Host必须在创建Run root前preflight失败。

Coordinator至少维护以下logical fields；implementation ticket可以规范化为多个table，但不能改变其authority：

```text
operation_id
operation_type
operation_variant
idempotency_scope
idempotency_key
request_digest
actor_digest
source_run_locator
target_run_locator
operation_status
operation_phase
phase_revision
worker_owner_id
worker_lease_expires_at
lease_epoch
canonical_policy_reference
canonical_policy_digest
result_reference
result_digest
error_code
created_at
updated_at
```

- `(idempotency_scope, idempotency_key)`全局唯一；`operation_type`、required `operation_variant`、canonical request与actor scope都进入`request_digest`，不能通过换operation type或variant复用同一key；线性operation固定使用typed `not_applicable` variant，存在合法分支的operation必须在reservation transaction中冻结一个枚举variant，之后不得按运行时观察改写分支；
- `operation_id`与new target Run locator由可信Host分配并在任何Run root、policy或ledger bytes创建前持久化；调用方不能选择现有Run或覆盖identity；
- `operation_status = accepted | in_progress | committed | failed | recovery_required`只表达控制调用结果，不是A04 `run_status`、领域`status`或Pause lifecycle；`operation_phase`是operation-type/variant-specific无环transition graph中的当前节点，`phase_revision`只能compare-and-set递增。每种variant必须冻结穷尽的allowed-edge map；线性operation只是每个nonterminal phase恰有一个successor的特例，不能用“单调”隐藏合法分支、跳phase或运行时发明新边；
- `accepted -> in_progress -> committed | failed | recovery_required`是唯一合法status graph。`committed | failed | recovery_required`都是不可逆terminal tombstone：仍可由exact、无副作用、预计算bytes唯一确定的publication suffix没有进入recovery，它保持`in_progress`并由同一operation的新current epoch继续；只有缺少预授权事实、发生过结果不确定副作用或已无法安全materialize原动作时才进入`recovery_required`，此后原operation不得继续，只能由显式replay/fork或operator resolution产生新的operation；
- `lease_epoch`是每次lease acquisition或takeover时在同一coordinator transaction中严格递增的fencing token；本ControlOperation直接拥有的phase compare-and-set、ledger/control publication与workspace lease materialization都必须验证exact `operation_id + worker_owner_id + lease_epoch + expected phase_revision`，任何旧epoch写入都必须拒绝；A05 `ExternalOperation`维护自己的独立单调epoch，不复用committed parent epoch，只有同一动作同时推进两类authority时才分别验证两者；
- worker lease只允许另一worker使用新`lease_epoch`继续同一`operation_id`的已验证phase；lease过期不释放幂等键、不创建新operation、不重新分配Run identity，也不授权重做外部副作用；
- committed、failed与recovery-required operation及其幂等键作为tombstone保留，至少与其可能引用的Run/artifact寿命一致；归档必须保留等价的key、request digest、result/error和identity证据；
- 同scope/key同digest返回原`operation_id`和已持久结果；同scope/key不同digest返回`conflict`且不创建第二个operation；
- Phase B SQLite reference implementation必须用单一write transaction（至少等价于`BEGIN IMMEDIATE`）完成key占用、operation row、target Run locator、canonical policy bytes/digest和initial `lease_epoch`分配，并在返回success前持久化result reference/digest；
- coordinator是mutation admission、ownership、phase与result replay的authority；Run创建后的领域/control历史仍以append-only`execution_history.jsonl`为authority，checkpoint只保存graph恢复状态，immutable artifacts/manifest保存科学产物。三者不能互相伪造或成为同一事实的可漂移双重authority。

### Reference durability profile

Phase B project-owned SQLite authority必须在创建任何Run bytes前验证实际生效的durability profile：local filesystem、`journal_mode = WAL`、`synchronous = FULL`、foreign keys enabled和policy-bounded busy timeout。实现必须检查SQLite返回的journal mode，不能假设请求的pragma已生效；不满足locking、atomic-rename、file-sync或directory-sync前提的filesystem必须preflight失败。

Coordinator备份、迁移或恢复必须使用SQLite backup API或等价的一致snapshot机制，并把database、WAL与SHM视为同一durability unit；运行中不得用raw file copy只复制主database。该profile只冻结Phase B reference backend，不宣称任意硬件、filesystem或远程mount都提供相同power-loss保证，harness必须包含进程重启和durability-boundary fault tests。

Append-only JSONL与immutable file publication必须完整写入一个record/file、flush userspace buffers、对file执行durable sync，并在首次创建或rename新名称时sync parent directory后才确认该publication phase。EOF trailing partial record、缺少newline的未完成record、digest不完整或parent publication不确定都不是合法history；reader必须fail closed，不能静默截断后把后续bytes当成完整prefix。

本ticket只使用`operation_type = start_run`。A04必须复用同一coordinator定义其余public mutations和Pause claim，不能新建第二套idempotency store。

## Execution 0.4 Bootstrap Contract

可信Host先验证`StartRunRequest`、Actor scope、output-root reserved control path与allowlisted canonical BudgetPolicy input。失败时不得创建ControlOperation、Run root或任何execution identity。验证成功后的第一项durable mutation必须是在coordinator中占用幂等键、创建`start_run` operation、分配target Run locator与initial `lease_epoch`，并保存后续只能exact materialize的canonical BudgetPolicy bytes/digest；只有该transaction提交后才能创建Run root、policy file或正式ledger。

`start_run/not_applicable`的exact phase enum、success edges、phase authority、required evidence与continuation policy只由tracked [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)定义。本节后续顺序是该机器合同的语义说明，不得增加隐藏phase、跳过edge或形成第二份独立枚举；design-time validator必须在冻结前证明该success graph全部可达、无环且只能终结于`result_committed`。

验证成功后的权威顺序固定为：

```text
BEGIN IMMEDIATE coordinator transaction
-> reserve idempotency key and create start_run ControlOperation
-> allocate immutable target Run locator and initial lease_epoch
-> persist canonical BudgetPolicy bytes/digest and commit operation_reserved
-> exclusively create the Run root and durably publish its parent entry
-> compare-and-set operation phase to run_root_created
-> exclusively publish the exact immutable BudgetPolicy bytes
-> compare-and-set operation phase to policy_published
-> append Run created
   bind run_status = initializing, operation_id, idempotency-key digest,
   request digest and policy reference/digest
-> compare-and-set operation phase to run_ledger_started
-> append budget policy_initialized
   bind exact Run-creation record and policy bytes
-> append budget decision_recorded(allow, action = bootstrap_initial_route)
   cover one initial Cycle, one Planner Work Attempt and one START Transition
   prove all absolute ceilings and the full terminal reserve remain valid
-> append initial Cycle created
-> append Planner Attempt scheduled
-> apply A03 method_planner target invalidation
   require an empty/new-Run current set and record only canonical no-op/clear evidence
-> append START -> method_planner Transition committed
-> compare-and-set operation phase to bootstrap_records_complete
-> append run_lifecycle(initializing -> running, reason = bootstrap_completed)
-> compare-and-set operation phase to running_lifecycle_recorded
-> persist checkpoint containing the resulting run_lifecycle execution head
-> validate bounded state/checkpoint plus execution/artifact heads
-> compare-and-set operation phase to checkpoint_committed
-> commit ControlOperation result reference/digest and result_committed
-> return the Run and permit Planner side effects
```

`policy_initialized`和bootstrap `decision_recorded`不是普通automatic-route charge。Cycle、Attempt和Transition的实际用量仍从A02权威identity records重放派生，不能在budget record中复制可漂移counter。

Bootstrap使用A02/A03复合Transition publication顺序：先分配scheduled target Attempt，再完成target invalidation，最后append committed Transition。`app.invoke()`、Planner wrapper `started`、Agent/provider/tool调用或任何domain artifact写入只能发生在完整bootstrap验证之后。

## Idempotency and Incomplete Prefix

- `operation_id`及target Run locator先由可信Host在coordinator事务中分配，并与`idempotency_key`、canonical request digest、actor digest和后续policy digest绑定；调用方不能选择现有Run root。
- 同key同digest在完整bootstrap后返回同一结果，不创建第二个Run、Cycle、Attempt、Transition、policy或decision。
- 同key不同digest必须在读取原operation后返回`conflict`；不能另建operation、另选Run identity或覆盖原request/result。
- coordinator transaction提交后但Run root创建前退出时，同key同digest只能以新`lease_epoch`领取同一operation的expired worker lease并从已记录phase继续；不得把没有Run目录解释为“请求从未发生”。
- 在任何Planner/Agent/provider/tool/domain-artifact副作用前，进程崩溃后只允许同key同digest继续一个严格合法的bootstrap前缀。
- 合法prefix class显式包括：`operation_reserved`后无Run root、已持久化空Run root、只含exact policy file、从`Run created(initializing)`开始的连续ledger prefix、完整bootstrap records、已追加`run_lifecycle(initializing -> running)`但尚未完成checkpoint，以及已完成checkpoint但尚未提交operation result。每一class都必须与coordinator phase、policy digest、identity和heads exact-match，且不得包含未知record、重复identity、target `started`、domain artifact、external reservation或已公开Pause。
- 继续合法前缀只能append缺失的确定性后缀和持久化缺失checkpoint；不能重写、删除、重新编号或替换已存在record。
- 额外record、顺序缺口、partial JSONL bytes、digest/head mismatch、tamper或已发生Planner/Agent/provider/tool/domain side effect属于integrity failure：隔离该Run并把`start_run` operation终止为`failed`，不得自动repair、replay、截断history或改用新identity继续原Run。若已分配Run的authoritative execution/artifact/policy heads仍可完整验证和安全append，可信Host必须从该exact integrity evidence确定性派生A04唯一`close_run`并发布`run_status: failed`；若authority自身无法验证或append，仍建立该deterministic close ownership但使其`operation_status: failed`、`terminal_closure: unavailable`且nullable post-operation `run_status`不产生新terminal值。两种情况都不能伪造halted lifecycle或用`start_run`的failed status冒充Run closure。
- 只有已存在bytes/identity/heads全部exact、没有新副作用且缺失suffix的canonical identity/digest已经由current phase唯一预计算时，operation才保持`in_progress`并允许同operation/current epoch补齐确定性后缀；对外查询返回typed `in_progress/materialization_pending`，不是`recovery_required`。并发不同request按幂等规则返回`conflict`，不是recovery。
- 每个成功持久化边界后才能用包含owner与`lease_epoch`的compare-and-set推进`operation_phase`；phase落后于exact durable prefix时允许同operation补记phase，phase领先或identity/digest冲突属于`failed` integrity outcome，stale epoch只拒绝该writer且不改变authoritative outcome。已有exact bytes但暂时没有current owner时保持`in_progress`等待lease takeover；无法证明原动作是否已产生不可重放副作用时原operation终止为`recovery_required`。Phase不能倒退。
- 完整bootstrap和ControlOperation committed result前Run不得以`running`或其他可执行状态对外发布；安全materialization期间查询返回typed initializing/in-progress control outcome，只有原operation已不可继续时才返回terminal `recovery_required`，且都不得暴露raw checkpoint恢复入口。

## Required A07 Scenario

- `A02C01-BOOTSTRAP-001`：验证schema `0.4`完整顺序、每个durable边界的合法前缀以`in_progress/materialization_pending`继续、冲突前缀fail closed、Planner副作用只能在bootstrap head/checkpoint exact-match后开始，以及schema `0.2`历史顺序保持不变。
- `A02C01-BOOTSTRAP-002`：使用两个独立client/process验证coordinator先于Run root原子占用key、Run locator、canonical policy bytes/digest和initial lease epoch，same-key/same-digest结果重放、same-key/different-digest冲突、worker lease只以新epoch继续原operation、stale-owner publication拒绝、terminal key tombstone及coordinator/checkpoint/ledger authority分离。
- `A02C01-BOOTSTRAP-003`：验证SQLite effective durability profile、consistent backup boundary、root/policy/file/directory sync failpoints、empty-root与policy-only合法prefix，以及partial JSONL record、raw database-only copy或不支持filesystem均fail closed；bootstrap integrity failure还必须区分appendable deterministic failed closure与unappendable `terminal_closure: unavailable`，不能从`start_run` failure推导Run status。

## Deliverables

- 本ticket冻结的`ControlOperation 0.1`与schema `0.4+` bootstrap corrective contract；
- A04/A06/A07一致引用的版本边界和required scenario；
- 独立completion record及受到影响的状态/决策文档更新。

## Acceptance Criteria

- schema `0.4+`在创建initial Cycle/Attempt/Transition前具有持久policy和admission evidence；
- `start_run`在创建Run root前已持久占用幂等键、operation identity和target Run locator，且不依赖LangGraph checkpoint实现幂等；
- A02 schema `0.2`正文、runtime和历史Run均未修改；
- START Transition遵守scheduled target allocation → A03 invalidation → Transition append顺序；
- Planner side effect只可能发生在完整bootstrap、checkpoint和heads验证后；
- 同key对empty-root、policy-only、ledger、lifecycle与checkpoint合法prefix的`in_progress` continuation，以及任意冲突/副作用prefix的fail-closed边界可机器验证；
- worker lease takeover产生更高`lease_epoch`，所有由该ControlOperation直接拥有的stale-owner phase、ledger、workspace或result写入被拒绝；A05 external-operation写入由其独立epoch fencing拒绝；
- SQLite、JSONL和immutable file的durability acknowledgement boundary明确且可注入故障验证；
- operation status/phase、A04 Run status、领域status和ledger history各自authority明确且不可互相代替；
- A04、A06、A07不再定义互相冲突的bootstrap顺序。

## Pre-freeze Review Gate

- YAML保持`status: review`，直到本ticket、A04–A07和requirement catalog完成交叉核验并获得用户最终确认；
- A02/A03/A03C01正文与runtime diff均为零，两个commit-order clarification已进入correction index；
- A04、A06、A07依赖本ticket并使用同一schema `0.4`顺序、prefix continuation和fail-closed边界；
- `PHASE_B_REQUIREMENT_CATALOG.json`恰好包含`A02C01-BOOTSTRAP-001`、`A02C01-BOOTSTRAP-002`和`A02C01-BOOTSTRAP-003`；
- Phase Overview、Docs Index和Current State一致记录本ticket为`review`且不把target contract描述为当前runtime；
- ticket内没有未决设计问题、占位符或内嵌执行记录。

## Verification

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

还必须验证全部relative Markdown links、ticket metadata、A02/A03/A03C01正文hash未变化，且本ticket没有runtime/tests/configs diff。

## Stop Conditions

- 需要修改A02/A03/A03C01冻结正文或当前runtime才能确认本设计；
- 无法在Planner副作用前持久化policy、admission、identity、invalidation和checkpoint证据；
- 无法在Run root创建前通过独立durable transaction取得幂等key和target Run identity ownership，或必须把LangGraph checkpoint当作control-operation authority；
- 合法prefix continuation必须重放Agent/provider/tool副作用；
- 需要扩大Allowed Files、选择生产基础设施或引入dependency；
- A04/A06/A07要求另一套不兼容bootstrap identity、顺序或recovery policy。

## Required Documentation Updates

- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`；
- `docs/README.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`；
- `docs/tickets/completions/A02C01_COMPLETION.md`及completion index；
- stale-documentation和relative-link scan。
