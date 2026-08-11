---
ticket_id: A02
phase: phase-a-control-contracts
status: completed
type: implementation
depends_on: [A01]
---

# 实现 Run、Cycle 与 Attempt Execution Identity

## Goal

在 runtime control plane 中完整实现 Run / Cycle / Attempt execution identity，使每次当前可达的 graph node invocation、路线提交和 Human decision 都具有稳定 identity、明确 lineage、append-only lifecycle record 和确定性测试覆盖。

A02 只有在 runtime、schema、graph integration、tests 和 source-of-truth 文档全部验收后才能标记 completed；编写或修订本 ticket 不等于执行完成。

## Why

本次纠偏开始时，runtime 已经加入部分 Cycle/Attempt fields、node wrapper 和 execution_history.jsonl，但仍不满足 A02 合同：

1. 没有正式、唯一的 Run creation record；
2. Attempt 在目标 wrapper 开始时才分配，不是真正的 transition-time allocation；
3. Human request/response 没有独立 identity、validator/consumer lineage 和 single-use enforcement；
4. re-review、analysis rerun、code fix 和 replan 主要只有 helper tests，没有经过 graph control path；
5. attempt_kind 直接复用物理节点名，把 legacy codex_handoff 混同于未来 code_agent；
6. 部分核心文档在以上合同落地前提前宣布 A02 已实现。

本 ticket 是对上述 partial implementation 的纠偏实施合同。旧测试全部通过只能证明已覆盖部分没有回归，不能替代本 ticket 的完整 Acceptance Criteria。

## Read First

- AGENTS.md
- docs/README.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/ARCHITECTURE.md
- docs/tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md
- src/lqcd_agent/graph/state.py
- src/lqcd_agent/graph/analysis_graph.py
- src/lqcd_agent/graph/routing.py
- src/lqcd_agent/graph/nodes.py
- src/lqcd_agent/graph/run_graph.py
- src/lqcd_agent/graph/approval_packet.py
- src/lqcd_agent/demo/server.py
- 相关 state、routing、graph、approval、demo 和 legacy handoff tests

## Scope

- 保持 Run / Cycle / Attempt 三层身份模型；
- 建立正式的 Run、Cycle、Attempt、Transition、Human Request 和 Human Response ledger records；
- 在 runtime bootstrap 中预分配 initial Planner Attempt；
- 在来源节点 wrapper 内完成 route selection 与 transition commit，并在目标节点产生副作用前预分配目标 Attempt；
- 将 conditional router 改成只读取已提交路线的无副作用函数；
- 固定 canonical AttemptKind，并将当前外部 codex_handoff 映射为 legacy_codex_handoff；
- 为 Human request/response 建立 Run-local deterministic identity、validation lineage 和 single-use consumption；
- 把当前真实可达路线接入 identity control plane；
- 用最小 deterministic StateGraph integration harness 验证尚未开放的四层回退 identity protocol；
- 修正提前宣布完成或仍把 execution identity 写成未来工作的文档；
- 增加完整 unit、integration、compatibility 和 negative-path tests。

## Non-goals

- 不修改 A01 已确认的目标 Transition Matrix；
- 不在 A02 中开放尚未实现的产品回退路线；
- 不把当前 file-based / external codex_handoff 发展成未来 graph-managed Code Agent；
- 不实现 Fake 或 real Code Agent；
- 不决定 per-attempt artifact namespace、current-artifact index 或 invalidation；
- 不实现 durable interrupt/resume、checkpoint recovery、公开 replay/fork API；
- 不冻结预算数值、failure fingerprint 算法或 human-granted execution window；
- 不改变 Agent scientific logic、provider schema、安全策略或 canonical output root。

## Allowed Files

- 本 ticket 文件；
- src/lqcd_agent/graph/state.py；
- src/lqcd_agent/graph/analysis_graph.py；
- src/lqcd_agent/graph/routing.py；
- src/lqcd_agent/graph/nodes.py；
- src/lqcd_agent/graph/run_graph.py；
- src/lqcd_agent/graph/approval_packet.py；
- src/lqcd_agent/demo/server.py；
- src/lqcd_agent/memory/store.py；
- src/lqcd_agent/report/generate_report.py；
- 与 execution identity 直接相关的 tests/ 文件，包括 state、routing、graph smoke、approval、demo、legacy handoff compatibility 和最小 StateGraph harness tests；
- docs/STATE_SCHEMA.md；
- docs/ARTIFACT_CONTRACTS.md；
- docs/ARCHITECTURE.md；
- docs/REPO_CURRENT_STATE.md；
- docs/DECISION_LOG.md；
- docs/VERIFICATION_GUIDE.md；
- docs/README.md；
- docs/NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md；
- docs/tickets/phase-a-control-contracts/OVERVIEW.md；
- docs/tickets/phase-b-graph-harness/OVERVIEW.md。

以上 stale-documentation files 已随本纠偏计划获得用户批准；实现阶段不需要再次扩大 scope。

## Do Not Touch

- configs/
- raw_data/
- outputs/
- src/lqcd_agent/coder/ 中的 legacy Codex 实现；
- Agent scientific logic、analysis programs、provider schemas 和 security policy；
- A01 ticket 内容或状态；
- A03–A07 ticket 状态；
- milestone 历史文档。

## Global Requirements

- identity 由 control plane 分配；Agent、router 和人类输入都不能创建、重写或复用自己的 identity；
- logical retry 和回退不能覆盖历史；
- Run-local ID 顺序必须来自显式 counters，不能依赖时间戳、随机 UUID 或解析 ID 字符串；
- control lineage、data provenance 和 human authorization 必须分别表达；
- graph state、route/transition record、event log 和 execution ledger 的 current identity 必须一致；
- 完整 history 保存在 run-local append-only JSONL ledger，但不能直接进入 Agent prompt；
- node exception 必须记录 failed Attempt 后原样重新抛出；
- 当前无 identity 参数的 runner/CLI 调用保持兼容；
- 所有新增代码注释必须使用英文；
- helper unit test 不能替代真实 runtime 或 StateGraph integration test。

## 1. Identity Hierarchy

| 层级 | 语义 | 创建条件 | 稳定范围 |
| --- | --- | --- | --- |
| Run | 一次完整用户科研任务 | 新 root goal、case identity 或原始输入快照；replay/fork 创建派生 Run | rerun、code fix、re-review、replan 和同 Run pause/resume 中不变 |
| Cycle | 同一方法合同下的 execution epoch | Run 初始化或 Coordinator 确认 replan | 同一方法合同下的 code、analysis、review 和 control attempts 中不变 |
| Attempt | 一次产生持久状态、artifact 或决策的 graph node invocation | initial target allocation 或每次 transition commit | 只覆盖一次语义执行；terminal 后不得复用 |

只有 initial 和 replan 创建 Cycle。re-review、analysis rerun、code fix、clarification 补值和同合同 semantic retry 保持当前 Cycle。

START、END 和人类 request/response 都不是 Agent Attempt。它们通过 Transition 或 Human records 与相关 Attempt 关联。

## 2. Canonical Identity Formats

Run 继续使用 caller 提供的现有 run_id。其他 identity 使用 Run-local counter，显示格式固定为：

~~~text
cycle_0001
attempt_000001
transition_000001
human_request_000001
human_response_000001
~~~

state 必须分别保存 Cycle、Attempt、Transition、Human Request 和 Human Response counters。显示 ID 只用于稳定引用；顺序判断必须读取 index/counter 字段，不能解析字符串。

## 3. Canonical AttemptKind 与 Physical Node Mapping

attempt_kind 是稳定合同，node_name 是当前物理实现。两者必须分别记录，并由 control-plane registry 验证。

| Physical node | Canonical attempt_kind | 说明 |
| --- | --- | --- |
| method_planner | method_planner | 当前工作节点 |
| codex_handoff | legacy_codex_handoff | 当前 file-based/external compatibility path |
| 未来 Fake/real Code Agent node | code_agent | A05/Phase B owner；A02 不实现 |
| analysis_engineer | analysis_engineer | 当前工作节点 |
| scientific_reviewer | scientific_reviewer | 当前工作节点 |
| decision_coordinator | decision_coordinator | 当前控制节点 |
| human_approval_gate | human_gate | 当前物理名称与 canonical kind 分离 |
| memory_report | memory_report | 当前 terminal/report 节点 |

允许的 canonical AttemptKind 集合固定为表中的八个值。未注册 kind、未注册 physical node 或 node/kind mismatch 必须在目标节点产生副作用前失败。

legacy_codex_handoff 不得写成 code_agent。A02 harness 可以预分配 code_agent Attempt 来验证协议，但不得执行 legacy Codex、Fake Code Agent 或真实 Code Agent。

## 4. Append-only Execution Ledger

Run root 继续使用：

~~~text
<output_root>/<case_id>/<run_id>/
~~~

该目录中的 execution_history.jsonl 是 identity source of truth。ledger record 至少具有：

- schema_version
- record_type
- event
- relevant identity/index/lineage fields
- timestamp
- typed references 或 payload digest

record_type 固定为：

- run
- cycle
- attempt
- transition
- human_request
- human_response

不同 record 必须使用各自 builder。不能把 current state 的全部 identity fields 无差别展开到每种 record；例如 Cycle creation record 不能携带旧 Cycle 的 current Attempt，Run creation record 也不能伪造 Attempt identity。

### Formal Run creation record

每个 Run 恰好有一个 record_type: run、event: created record，至少包含：

- run_id
- nullable parent_run_id
- creation_reason
- case_id
- root goal reference 与 digest
- input config snapshot reference 与 digest
- canonical output root
- checkpoint_thread_id
- created_at
- status: running

goal 和 input snapshot digest 使用稳定 canonical bytes 计算。实现可以继续使用现有输入文件作为 reference，但相同 Run re-entry 必须比较保存的 digest，不能只比较 path 字符串。

Run 的正式 pause、terminal、replay 和 fork lifecycle API 由 A04 定义；A02 只实现可供后续扩展的 creation record 和可选 parent_run_id lineage。

### Cycle record

Cycle creation record 至少包含：

- cycle_id / cycle_index
- run_id
- nullable parent_cycle_id
- trigger_reason
- nullable creating control Attempt reference
- created_at

initial Cycle 的 creating Attempt 为 null。replan Cycle 引用提交 replan 的 Coordinator Attempt。

### Attempt lifecycle records

每个 Attempt 使用同一 identity 写 append-only lifecycle events：

~~~text
scheduled -> running -> succeeded | failed | pending
scheduled -> abandoned
~~~

Attempt record 至少包含：

- attempt_id / attempt_index
- run_id / cycle_id
- attempt_kind
- node_name
- nullable parent_attempt_id
- trigger_reason
- lifecycle status/timestamps
- input/output/evidence references
- failure summary/fingerprint reference（如存在）

pending、failed、succeeded 和 abandoned 都不得被当作新的语义执行再次 start。A04 后续只能在满足其 technical-resume 幂等合同的情况下继续同一尚未形成 semantic failure 的 execution。

## 5. Run Bootstrap

新 Run 初始化的 ledger 顺序固定为：

~~~text
Run created
-> initial Cycle created
-> Planner Attempt scheduled
-> START -> method_planner Transition committed
~~~

initial Planner Attempt 必须在 app.invoke() 或任何 Planner side effect 之前已经存在。START transition 的 source_attempt_id 为 null。

同一 incomplete Run 的 compatibility re-entry：

- 读取现有 Run creation record 和最新 counters；
- 不重复创建 Run、initial Cycle 或已存在 identity；
- 校验 run_id、case_id、goal digest、input snapshot digest、canonical output root、checkpoint thread ownership 和 parent lineage；
- 任一 immutable identity mismatch 都必须停止，不能静默覆盖；
- 只能恢复 counter 和 audit continuity，不能宣称已实现 A04 durable resume。

## 6. Source-wrapper Transition Commit

### RouteSelection

每个来源节点结束后，由与该节点绑定的纯 route selector 生成结构化 RouteSelection，至少包含：

- route key
- target physical node 或 END
- target canonical AttemptKind（END 时为 null）
- trigger reason
- human-readable reason
- structured evidence references
- explicit state updates
- Cycle action：keep 或 new_replan_cycle

route selector 不得修改 state、写文件、写 event、分配 identity 或保存 graph state。当前 retry_count += 1、code_fix_requested = true 等 scalar changes 必须作为 state_updates 返回。

### Commit order

来源 node wrapper 的控制顺序固定为：

~~~text
consume and validate pre-scheduled source Attempt
-> mark source Attempt running
-> execute physical node
-> mark source Attempt succeeded | pending | failed
-> call pure route selector
-> commit_transition
   -> apply explicit state updates
   -> create replan Cycle when requested
   -> preallocate target Attempt as scheduled, unless target is END
   -> append committed Transition record
   -> set committed_transition_id and committed_route in state
-> return state to StateGraph
-> conditional edge reads committed_route only
~~~

如果 physical node 抛出 exception，wrapper 必须写 failed Attempt 并重新抛出；不得选择正常 outbound route 或预分配目标 Attempt。

fixed edge 与 conditional edge 使用同一 commit protocol。scientific_reviewer -> decision_coordinator、memory_report -> END 等 fixed routes 也必须产生 Transition record。

### Transition record

每次 commit 使用 deterministic transition_id，至少记录：

- transition_id / transition_index
- run_id
- source/target Cycle
- source Attempt 和 physical node；START 时 nullable
- target Attempt、physical node 和 canonical kind；END 时 nullable
- route key、trigger、reason 和 structured evidence references
- applied state update keys/digest
- status: committed
- committed_at

同一 source Attempt 最多有一个 committed outbound Transition。A02 对任何 duplicate outbound commit 都硬失败且不追加 target Attempt 或 Transition record；带幂等键的 crash-safe replay、partial-commit recovery 和 transaction recovery 统一由 A04 定义。

### Target consumption

目标 wrapper 只能领取 Transition 中已经 scheduled 给自己的 Attempt，并验证：

- target attempt_id 与 state current pointer 一致；
- Run/Cycle 一致；
- physical node 与 canonical kind registry 一致；
- Attempt status 是 scheduled；
- inbound Transition 已 committed。

缺失 allocation、node/kind mismatch、terminal Attempt reuse 或另一个节点领取同一 Attempt 都必须在 node side effect 前失败。

conditional edge 函数只调用 read_committed_route()；它不得再次运行业务 selector 或改变 state。

## 7. Human Request / Response Identity

Human request/response 是独立外部授权 records，不是 Human Gate Attempt 的别名。

### Human Request

Coordinator 提交进入 Human Gate 的 transition 时创建 request。request 至少包含：

- human_request_id / human_request_index
- run_id / cycle_id
- requesting Coordinator Attempt
- request_kind: clarification | approval | external_action
- authorization scope
- packet/template reference
- status: open | satisfied；`closed`、`expired`、`revoked` 等终态由 A04 定义
- timestamps

同一时刻 state 只保存 bounded active request pointer；完整 request history 只在 ledger。

### Human Response

外部 control plane 接收 response 时分配 human_response_id。response lifecycle 使用同一 ID 写 append-only events：

~~~text
submitted -> invalid
submitted -> validated -> consumed
~~~

response 至少包含：

- human_response_id / human_response_index
- referenced request ID
- run_id / cycle_id
- payload reference 与 digest
- validator Human Gate Attempt
- single-use consumer Attempt
- authorized target Attempt
- validated decision、logical authorized route，以及精确 authorized Transition route/target
- lifecycle status/timestamps

Agent 和人类文件都不能自行生成 request/response ID。

### Runtime flow

~~~text
Coordinator -> Human Gate transition commit
-> create Human Request
-> preallocate first Human Gate Attempt
-> Gate writes identity-bound packet/template
-> no valid input: keep request open and produce current compatibility pending audit/report behavior
-> external control plane submits identity-bound response
-> allocate a new Human Gate validation Attempt
-> validate run/cycle/request/response、decision 和 scope
-> freeze logical authorization and one exact compatibility Transition route/target
-> create and commit a transition that exactly matches the validated snapshot
-> bind validator, consumer, exact transition and authorized target
-> mark the accepted response consumed exactly once
~~~

A01 target graph requires valid Human Gate responses to return to Coordinator before a working Agent is chosen。A02 不新增或批准任何 product route；在 Phase B 改造前，当前 demo/legacy route 必须如实标记为 compatibility behavior，且不能被文档描述成已经满足 A01 target matrix。

### Single-use rules

- 一个 request 可以有多个 invalid response，但最多一个 response 被 consumed；
- accepted response 的第二次提交或消费必须在分配新 Attempt 或新目标 Attempt 前失败；
- 重复消费不能增加 Attempt counter，也不能重复写 memory/report artifacts；
- mismatched Run、Cycle、request、response 或 authorization scope 必须拒绝；
- 当前 control-plane API 不接受 caller 自行指定 response ID；重复提交或消费一律硬拒绝且不改变 counters、ledger、memory 或 report。带 idempotency key 的网络重放协议由 A04 定义；
- response 只能授权记录在其 scope 中的一次 transition/window，不能解释成无限循环批准。

approval schema 升级为 0.2，显式包含 request/response identity。旧 0.1 文件只有在 caller 明确选择 compatibility import、且当前 Run 恰好存在唯一 open request 时才能绑定；不得自动绑定到后续 request。

A04 继续负责真正的 PAUSE/resume、response expiry/revocation、并发提交和 checkpoint durability；A06 负责 human-granted finite execution window。

## 8. State Boundary

AnalysisState 只保存 control plane 当前执行所需的 bounded snapshot：

- Run identity、parent Run 和 immutable Run metadata references；
- current Cycle/Attempt/Transition pointers；
- Cycle/Attempt/Transition allocation counters；
- active Human Request/Response pointers 与 counters；
- current committed route、既有 remediation/routing fields，以及 compatibility `retry_count/max_retry`；A06 budget snapshot 尚未定义；
- execution ledger path；
- Run-owned checkpoint metadata；
- current artifact pointers。

完整 Run/Cycle/Attempt/Transition/Human history 不进入不断增长的 Agent context。Agent-facing context 继续遵守 A01 scoped-history boundary。

event log、route projection、approval packet、memory/report metadata 必须引用相关 identity，但 ledger 是 identity source of truth。A03 仍决定 per-attempt artifact namespace、current pointers 和 invalidation。

checkpoint_thread_id 由 Run 拥有并在同一 Run 的 Cycle/Attempt 中稳定；Cycle/Attempt 不创建新 thread。replay/fork 创建新 Run 和新 thread，但公开 API 由 A04 实现。

## 9. Runtime、Harness 与 Deferred Scenarios

### 必须接入当前真实 runtime

以下场景必须经过实际 runner / compiled graph / demo continuation，不能只调用 helper：

- Run bootstrap、initial Cycle、initial Planner allocation 和 START transition；
- 当前所有 normal forward routes；
- 当前所有 fixed routes；
- END transition；
- node exception/failure lifecycle；
- 当前 legacy Codex Handoff compatibility path；
- Demo human-decision submission、validation、single-use consumption 和后续 target allocation；
- incomplete Run compatibility re-entry 与 immutable mismatch rejection。

这些测试只描述当前真实可达路线；不得把 current legacy routes 写成 A01 target routes。

### 必须经过最小 deterministic StateGraph integration harness

以下目标路线尚未全部开放，因此使用最小 harness 经过真实 route selection、transition commit、scheduled target consumption，而不是直接调用 allocator helper：

| 场景 | Identity expectation |
| --- | --- |
| re-review | 同 Run/Cycle，新 Reviewer Attempt |
| analysis rerun | 同 Run/Cycle，新 Analysis Attempt |
| code fix | 同 Run/Cycle，预分配 canonical code_agent Attempt；使用 protocol sink 验证后停止，不执行任何 Code Agent |
| replan | 同 Run，新 Cycle，新 Planner Attempt |

harness 只能证明 identity protocol 准备完成，不能在 current architecture 文档中宣称产品 graph 已开放这些路线。它不是 A05 Fake Code Agent，也不替代 A07 full harness。

### 明确延期

| Owner | Deferred work |
| --- | --- |
| A03 | artifact namespace、versioning、current pointer、四层 invalidation |
| A04 | durable PAUSE/resume、technical recovery、checkpoint compatibility、公开 replay/fork API |
| A05 | Fake/real graph-managed Code Agent contract、sandbox、diagnostic outcome |
| A06 | budgets、failure fingerprint、repeated-failure rule、human-granted finite window |
| A07 / Phase B | A01 所有 target/forbidden routes 的完整产品 harness 与线路改造 |

## 10. Identity Scenario Matrix

| 场景 | Run | Cycle | Attempt / Transition / Human behavior | 本 ticket 验证方式 |
| --- | --- | --- | --- | --- |
| initial start | 新 | 新 initial | 先 scheduled Planner，再 commit START transition | real runtime |
| normal forward | 不变 | 不变 | 来源 commit 预分配目标 Attempt | real graph |
| fixed route | 不变 | 不变 | 与 conditional route 相同地写 Transition | real graph |
| END | 不变 | 不变 | 写 Transition，不创建虚假 target Attempt | real graph |
| re-review | 不变 | 不变 | 新 Reviewer Attempt | StateGraph harness |
| analysis rerun | 不变 | 不变 | 新 Analysis Attempt | StateGraph harness |
| code fix | 不变 | 不变 | 新 canonical code_agent Attempt | StateGraph protocol sink |
| replan | 不变 | 新 Cycle | Cycle record 后创建 Planner Attempt | StateGraph harness |
| clarification 补齐既有输入 | 不变 | 不变 | 独立 response；返回时新 Attempt | Human identity integration |
| clarification 改变方法合同 | 不变 | 新 Cycle | Coordinator 以 replan commit | StateGraph harness |
| clarification 改变 root goal/case/input snapshot | 新 Run | 新 initial | 新 Run creation record/thread；parent lineage 可表达 | constructor unit/integration；公开 API deferred |
| no human response | 不变 | 通常不变 | request 保持 open；不得伪造 response | real demo compatibility |
| valid human response | 不变 | 通常不变 | 新 response 和 validator Attempt；只消费一次 | real demo integration |
| invalid human response | 不变 | 不变 | response 标记 invalid；request 仍 open | real demo integration |
| technical recovery | 不变 | 不变 | 仅恢复 counters/audit continuity，不宣称完整 resume | compatibility re-entry |
| semantic retry after failure | 不变 | 按回退层级 | terminal Attempt 不复用，必须新 Attempt | unit + harness |
| replay/fork | 新派生 Run | 新 initial | parent_run_id 可记录；新 thread/API deferred | identity constructor test |
| terminal report | 不变 | 不变 | Memory Report 独立 Attempt，随后 END Transition | real graph |

## Deliverables

- formal Run/Cycle/Attempt/Transition/Human ledger builders 与 bounded state pointers；
- source-wrapper transition commit 和 pure committed-route readers；
- canonical AttemptKind registry 与 legacy mapping；
- deterministic Human request/response allocation、validation 和 single-use enforcement；
- current runtime integration 与未来回退 protocol harness；
- identity-aware event、route、approval、memory 和 report metadata；
- 修正后的 source-of-truth、phase overview 和 verification 文档；
- 通过的 targeted 与 full test suites。

## Acceptance Criteria

### Formal records and bootstrap

- 每个新 Run 恰好一个正式 Run creation record，字段完整；
- ledger 初始化顺序为 Run、Cycle、scheduled Planner、committed START transition；
- re-entry 不重复 Run/Cycle，且 immutable identity mismatch 必须拒绝；
- Cycle record 不携带旧 Attempt 或不可能的 current identity；
- deterministic counters 在 re-entry 后继续递增且不碰撞。

### Transition-time allocation

- initial Planner 在 app.invoke() 前已 scheduled；
- 当前每条 fixed/conditional transition 都记录 source/target Attempt；
- 目标节点实际领取的 Attempt 与来源 commit 的 target Attempt 完全一致；
- conditional route reader 无 state/file side effects；
- router scalar updates 通过显式 RouteSelection.state_updates 传给目标；
- END transition 不创建 target Attempt；
- missing allocation、wrong node/kind、terminal reuse 和 duplicate outbound commit 均硬失败；
- exception 写 failed Attempt 后重新抛出，不预分配正常 target。

### Canonical kinds

- physical codex_handoff 只记录为 legacy_codex_handoff；
- human_approval_gate 记录为 human_gate；
- 未注册 kind 和 node/kind mismatch 被拒绝；
- A02 runtime 不包含 Fake/real Code Agent。

### Human identity

- request/response 使用独立 deterministic IDs，而不是 Attempt ID；
- packet/template 和 response 都绑定 Run/Cycle/request identity；
- validator、consumer、validated decision、logical route、精确 Transition route/target 和 authorized target Attempt 可从 ledger 追踪；
- invalid/mismatched response 不关闭 request；
- accepted response 最多 consumed 一次；
- 重复提交/消费不增加 Attempt counter，不重复生成 memory/report；
- 0.1 compatibility import 只有显式、唯一 open request 时允许；
- current compatibility route 与 A01 target route 在 docs/tests 中清楚区分。

### Runtime versus harness

- initial、current forward/fixed/END、exception、legacy handoff、demo human continuation 和 re-entry 通过真实 runtime integration test；
- re-review、analysis rerun、code-fix allocation 和 replan 通过真实 StateGraph transition harness；
- harness 没有被描述为 product route 已开放，也没有伪装成 A05 Code Agent；
- helper-only tests 只验证 primitive，不作为场景验收的唯一证据。

### Documentation and scope

- 核心文档只宣布实际通过验收的功能；
- stale docs 不再把 A02 execution identity 写成未批准未来概念，也不提前宣布 A03/A04/A05/A06 已实现；
- A03/A04/A05/A06 owner 边界保持明确；
- 所有变更都在 Allowed Files 内；
- A02 只在全部验证通过并填写真实 Completion Record 后改为 completed。

## Verification

~~~bash
pytest -q \
  tests/test_execution_identity.py \
  tests/test_state_schema.py \
  tests/test_routing.py \
  tests/test_graph_smoke.py \
  tests/test_approval_packet.py \
  tests/test_demo_server.py \
  tests/test_memory.py \
  tests/test_report.py \
  tests/test_run_graph_with_codex_handoff.py

pytest -q
python -m compileall -q src/lqcd_agent
git diff --check
~~~

如果 integration harness 使用新的测试文件，必须把它加入 targeted verification。

完成前还必须执行：

- Allowed Files scope audit；
- ticket metadata 检查；
- Markdown relative-link 检查；
- stale-documentation scan；
- 文档最终修改后的第二次 link 和 git diff --check；
- 对照本 ticket 的 Acceptance Criteria 逐项记录证据，不能只引用 full-suite pass count。

## Stop Conditions

- 实现需要改变 canonical output root 时停止；
- 需要引入数据库或外部 identity service 时停止；
- 需要修改 A01 target route decision 时停止；
- 需要在 A02 中实现或伪装 Fake/real Code Agent 时停止；
- checkpoint 与 artifact ownership 无法保持一致时停止；
- 需要提前冻结 A03 namespace、A04 resume API 或 A06 budget/fingerprint 时停止；
- 当前 public contract 与本 ticket 无法在 Allowed Files 内一致更新时停止。

## Required Documentation Updates

- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/ARCHITECTURE.md
- docs/REPO_CURRENT_STATE.md
- docs/DECISION_LOG.md
- docs/VERIFICATION_GUIDE.md
- docs/README.md
- docs/NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md
- docs/tickets/phase-a-control-contracts/OVERVIEW.md
- docs/tickets/phase-b-graph-harness/OVERVIEW.md

Milestone 和 A01 historical Completion Record 不随本 ticket 改写。

## Completion Record

- Status：`completed`；纠偏 implementation 已完成 runtime、schema、graph、Human continuation、tests 和 source-of-truth 验收。
- Changed：新增 formal Run/Cycle/Attempt/Transition/Human ledger 和 Run-local counters；将 current product routes 接入 source-wrapper Transition commit 与 target preallocation；固定 canonical AttemptKind/physical-node mapping；实现 identity-bound approval 0.2、exact authorization、single-use response consumption、legacy re-entry validation 和 fallback identity StateGraph harness；Memory/Report 只读取 consumed validated decision snapshot。
- Verified：A02 targeted suite `125 passed in 2.52s`；full suite `218 passed in 5.16s`；`python -m compileall -q src/lqcd_agent`、`git diff --check`、29-file Markdown relative-link check、ticket metadata、Allowed Files scope audit 和 stale-documentation scan 均通过。未运行 live-provider 测试，因为它不属于本 ticket 验收范围。
- Commit：未提交。
- Follow-ups：A03 定义 artifact namespace/invalidation；A04 定义 durable PAUSE/resume、checkpoint/crash recovery 和 delivery idempotency；A05 定义 Fake/real graph-managed Code Agent；A06 定义 budgets/failure fingerprint；A07/Phase B 完成 A01 product topology 和 forbidden-route harness。

## Correction Record

- 2026-08-11 曾错误地把 A02 作为纯设计 ticket 标记 completed；该完成结论无效，因为当时没有修改 runtime、schema、graph 或 tests。
- 随后的 partial implementation 通过了其已有测试，但缺少 formal Run record、真正 transition-time allocation、Human request/response identity、完整 runtime/harness paths、canonical AttemptKind mapping，并造成核心文档提前宣布完成。
- 用户已批准并执行本 corrective implementation plan；上述代码、集成测试、文档和 scope verification 全部完成后，A02 于 2026-08-11 正式关闭。
