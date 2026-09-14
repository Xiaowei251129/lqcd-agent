# State Schema

## 当前合同

`AnalysisState` 是当前公开 graph-state contract。节点只能读取和写入已记录字段。下面的 schema 与当前 runtime 对齐；A02 完成 execution identity，A03 完成 bounded artifact-current control fields。A04已经冻结后继Pause/Resume state contract，A05已经冻结后继Code Agent bounded projection，A06已经冻结后继budget bounded projection，但这些目标字段都尚未加入当前runtime。

schema 变化必须由独立 implementation ticket 批准，并同步 runtime、tests、artifact contracts 和相关 Decision Log。A02 execution identity 与 A03 artifact-current schema 已落地并通过验收；reducer、具体恢复字段和 budgets 不属于当前正式 schema。

## 当前字段

```python
class AnalysisState(TypedDict):
    run_id: str
    case_id: str
    user_goal: str
    case_config_path: str
    output_dir: str
    current_node: str
    status: str  # running | success | failed | pending | halted
    llm_provider_config_path: str | None
    auto_codex_handoff: bool
    codex_bin: str
    codex_model: str | None
    codex_timeout_seconds: int
    verification_timeout_seconds: int
    force_codex_handoff: bool
    dry_run_codex: bool

    checkpoint_thread_id: str
    checkpoint_backend: str  # memory | sqlite
    checkpoint_db_path: str | None

    parent_run_id: str | None
    cycle_id: str
    cycle_index: int
    parent_cycle_id: str | None
    attempt_id: str | None
    attempt_index: int
    parent_attempt_id: str | None
    attempt_kind: str | None
    attempt_node: str | None
    attempt_trigger: str | None
    attempt_status: str | None  # scheduled | running | succeeded | failed | pending | abandoned
    inbound_transition_id: str | None
    committed_transition_id: str | None
    transition_index: int
    committed_route: str | None
    execution_history_path: str
    artifact_history_path: str
    artifact_index_path: str
    artifact_event_index: int
    current_artifacts: dict[str, dict | None]

    human_request_index: int
    human_response_index: int
    active_human_request_id: str | None
    human_requesting_attempt_id: str | None
    human_request_kind: str | None  # clarification | approval | external_action
    human_request_status: str | None  # open | satisfied
    human_request_authorization_scope: dict | None
    active_human_response_id: str | None
    human_response_status: str | None  # submitted | validated | invalid | consumed
    human_response_decision: str | None
    human_response_authorized_route: str | None
    human_response_authorized_transition_route: str | None
    human_response_authorized_transition_target: str | None
    human_response_validator_attempt_id: str | None
    human_response_consumer_attempt_id: str | None
    human_response_target_attempt_id: str | None

    context_policy_path: str | None
    context_summary_path: str | None
    event_log_summary: str | None
    context_window_status: str  # normal | near_limit | summarized | overflow_halt

    method_plan_path: str | None
    code_needed: bool
    coder_task_packet_path: str | None
    code_change_summary_path: str | None
    tests_status_path: str | None
    retry_count: int
    max_retry: int

    run_success: bool
    failure_type: str | None  # code | config_or_data | workflow | unknown
    run_result_path: str | None
    analysis_outputs_dir: str | None

    scientific_review_report_path: str | None
    decision_log_path: str | None
    risk_level: str  # unknown | low | medium | high | critical
    recommended_action: str | None
    rerun_requested: bool
    rerun_target: str | None
    code_fix_requested: bool

    human_approval_required: bool
    approval_packet_dir: str | None
    human_decision_path: str | None

    final_report_path: str | None
    memory_update_path: str | None
    errors: list[dict]
    warnings: list[dict]
    event_log: list[dict]
    route_decisions: list[dict]
```

## 当前 invariants

- 每次 run 必须提供 `run_id`、`case_id`、`user_goal`、`case_config_path` 和 `output_dir`。
- `llm_provider_config_path` 可选；省略时三个 provider-capable Agent 走 deterministic path。
- local CLI 使用 `sqlite`，unit/smoke tests 使用 `memory`。
- 同一 `case_id` 与 `run_id` 的 `checkpoint_thread_id` 必须稳定。
- Run 初始化时创建 `cycle_0001`；Cycle 与 Attempt 使用显式 Run-local counters 分配 deterministic identity。
- 新 Run 的 ledger/bootstrap 顺序是 Run creation、initial Cycle creation、Planner Attempt `scheduled`、START Transition `committed`；Planner 在 `app.invoke()` 前已有 identity。
- 当前 compiled graph 的每条来源路线先完成 source Attempt，再由 `commit_transition` 在目标节点副作用前创建 target Attempt；conditional edge 只读取 `committed_route`。
- target wrapper 只能领取 committed inbound Transition 已分配给自己的 `scheduled` Attempt；terminal Attempt identity 不得复用，同一 source Attempt 最多一个 committed outbound Transition。
- `parent_run_id`、`parent_cycle_id` 和 `parent_attempt_id` 记录 control lineage。
- `execution_history_path` 指向 run-local append-only `execution_history.jsonl`。
- `artifact_history_path` 指向 append-only `artifact_history.jsonl`；`artifact_index_path` 指向 atomically replaced `artifact_index.json`，`artifact_event_index` 必须等于 registry head。
- `current_artifacts` 的 keys 固定为 `plan`、`code`、`analysis`、`review`、`decision`、`approval`、`terminal`。每个非 null pointer 记录 artifact/Attempt/Cycle identity、members、dependencies、status 和 state paths。
- convenience path fields 必须指向 current canonical Attempt member；slot invalidation 时同步清空。`human_decision_path` 是 approval slot 明确保留的 current external ingress path。
- `current_artifacts`、artifact counter、registry paths 和 convenience paths 是 control plane fields，Agent、provider payload 和 router 不得修改。
- event log 与 route decision 必须携带当时的 Run/Cycle/Attempt identity。
- `attempt_kind` 是 canonical contract，`attempt_node` 是 physical node；当前 `codex_handoff` 必须记录为 `legacy_codex_handoff`，不能记录为 `code_agent`。
- Human Request/Response 使用独立 Run-local counters 和 IDs；有效 response 必须由一个 `human_gate` Attempt 验证。验证会冻结 decision、logical authorized route 和精确 compatibility Transition route/target，commit 必须完全匹配这些字段，且只能消费一次。
- `retry_count` 不得超过 `max_retry`。
- `risk_level` 为 `high` 或 `critical` 时，`human_approval_required` 必须为 true。
- 没有 structured human approval record 时，high/critical outcome 不得写 accepted memory。
- routing 必须使用 structured fields，而不是 Markdown summary。
- `route_decisions` 记录 deterministic route、source node、reason 和所用字段。
- `event_log` 完整保存在 state；LLM-facing context 只使用选定字段和 `event_log_summary`。

## Context 边界

LLM-facing prompt 可以包含：

- selected Run/Cycle/Attempt identifiers 与 status fields；
- 与当前 Gate 操作直接相关的 active Human Request/Response identifiers；
- provider config path metadata，但不能包含 provider secrets；
- relevant artifact paths；
- method、run、review、decision 和 event-log 的 bounded summaries。

LLM-facing prompt 不得包含：

- full raw numeric data；
- secrets；
- unbounded long logs；
- 作为 routing 唯一依据的 truncated free-form text。

## 当前 runtime 行为

graph 默认使用 deterministic Agent path，并在重要节点完成和 route decision 后写 `graph_state.json`；完整 state 同时保存在 LangGraph checkpoint。`llm_provider_config_path` 可以启用 provider-backed Method Planner、Scientific Reviewer 和 Decision Coordinator，但 provider output 必须先通过结构验证。

所有 compiled graph nodes 通过 control-plane wrapper 执行。来源 transition 或 bootstrap 预先写 target Attempt `scheduled`；target wrapper 验证 committed inbound Transition，写 `started`，执行 physical node，再写 terminal `finished`。node exception 写 failed Attempt 后原样重新抛出，且不提交正常 outbound Transition。route selector 只返回结构化选择和显式 state updates；Transition commit 才能更新 control state、分配下一个 Attempt 并记录 route。完整 lifecycle 写入 `execution_history.jsonl`，但 Agent-facing context 只包含 current identity 和既有 bounded summaries。

high/critical outcome 进入 Human Approval Gate。Coordinator commit 同时创建独立 Human Request 和预分配 Gate Attempt；gate 写 identity-bound `approval_packet/`。外部 response 获得独立 identity，只能由新 Gate Attempt 验证并由已授权 compatibility transition 消费一次；没有有效决定时 request 保持 open，state 保持 `pending`。

Local CLI 使用 `SqliteSaver`。`--output-dir` 是 output root；解析后的 run directory 为 `<output_root>/<case_id>/<run_id>/`，并写入 `state["output_dir"]`。省略 `--run-id` 时，在 state 初始化前生成 timestamp run id。checkpoint database 位于：

```text
<output_root>/<case_id>/<run_id>/checkpoints/graph_checkpoints.sqlite
```

Unit/smoke tests 使用 `MemorySaver`。两种 backend 使用相同的 `checkpoint_thread_id` 格式：

```text
<case_id>:<run_id>
```

## A02 当前落地的 State Boundary

[A02](tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md) 的当前实现采用 Run / Cycle / Attempt 三层 identity。Run 继续使用现有 `run_id` 并拥有 canonical output root 与稳定 checkpoint thread；Cycle 表示 initial/replan 创建的方法合同 epoch；Attempt 表示一次产生持久状态、artifact 或 route decision 的 node invocation。每个 Run 另有 deterministic Transition、Human Request 和 Human Response identities。

State 保存 current Cycle/Attempt pointers、Run-local allocation counters、parent lineage、current artifact pointers、execution ledger path 和 Run-owned checkpoint metadata。完整 Attempt history append-only 保存，不能作为不断增长的 state-to-prompt context。

Attempt 由 graph control plane 在目标节点副作用之前分配。canonical Attempt kinds 当前固定为 `method_planner`、`legacy_codex_handoff`、`code_agent`、`analysis_engineer`、`scientific_reviewer`、`decision_coordinator`、`human_gate` 和 `memory_report`；其中 `code_agent` 只为 A05/Phase B 预留，当前产品 graph 没有该节点。legacy external Codex runner 仍保留原有重新进入主图的行为；重新初始化未完成 Run 时会从已有 ledger 恢复 counters，避免复用 identity。它不是未来 graph-managed Code Agent，也不满足A04已确认的通用checkpoint resume合同。

当前 product routes 已使用 transition-time allocation 与 target-layer artifact invalidation。re-review、analysis rerun、code fix 和 replan 只在最小 deterministic StateGraph harness 中验证 identity/invalidation protocol；它们尚未因此成为当前产品路线。A01 的完整线路改造与 forbidden-route coverage 仍由 A07/Phase B 承接。

## A04 已确认的目标 State Boundary（尚未实现）

[A04](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)冻结execution schema `0.3`的Pause/Run语义，供Phase B schema `0.4`实现复用。这里的版本是目标合同版本，不改变上方当前`AnalysisState`或runtime schema `0.2`。

权威状态与投影严格分离：

- append-only `run_lifecycle`记录是Run状态authority，`run_status = initializing | running | paused | completed | failed | halted`只是受限projection；`completed | failed | halted`均terminal且不可逆；
- 现有`status`保留为domain/workflow compatibility字段；正常`memory_report -> END`即使领域状态为`pending`，control `run_status`也必须为`completed`；
- Pause ledger status固定为`prepared | opened | claimed | consumed | cancelled | aborted | interrupted | quarantined`，event固定为相应`pause_*`类型；只有latest exact `opened`且unclaimed、public paused checkpoint完整的Pause可resume；
- bounded state未来只保存`run_status`、pause counter、nullable pending/active Pause identity/reason/status/requesting-target scope，以及nullable active ControlOperation ID/status/phase/revision/epoch；这些字段不能替代coordinator、execution ledger或artifact heads；
- ControlOperation的`operation_status`、Run terminal closure、Run lifecycle、Pause lifecycle和domain `status`互相正交；`operation_status: failed`不能推导`run_status: failed`。

`human_input`与不继续existing target的`recovery_decision`在opened时使用explicit null target；Human validator只在成功claim后、任何target副作用前分配一次。`external_result`必须绑定already-scheduled且未started的exact target、pre-existing reservation和ExternalOperation core digest。Resume继续分支固定经过claim、reason-specific pre-start、`pause_consumed`、`paused -> running` lifecycle及running checkpoint，随后才允许target start。`recovery_decision`只接受`continue_existing_target | abandon_and_halt`；null target只能halt，Code Agent/legacy handoff target不能continue，且该输入不能伪装成replay/fork。`abandon_and_halt`分支原子取得Pause和Run terminal ownership，不进入running。

无效Human Response不会重新打开或复用旧Pause：旧Pause保持consumed，validator Attempt先结束。A06容量决策为`allow`时，从新的running安全边界按`pause_prepared -> prepared checkpoint -> running-to-paused lifecycle -> pause_opened -> public paused checkpoint`发布新identity；决策为`halt`时不创建新Pause，而由`close_run`从running发布terminal closure。

每个Pause还冻结runtime compatibility fingerprint，至少覆盖control/app build、graph topology、state/artifact schema、LangGraph/checkpointer/serializer实现及版本。Schema `0.2`不resume/fork；显式支持`0.3`的原runtime可恢复自己创建的exact Pause，但Phase B `0.4`只原地resume exact supported `0.4`，对validated `0.3` source只允许replay/fork为新child。缺失或mismatch一律fail closed，不做state reinterpretation或原地迁移。

## A05 已确认的 Code Agent 目标 State Boundary（尚未实现）

[A05](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)为Phase B canonical Code Agent冻结以下bounded nullable projection：

```text
code_agent_task_path
code_agent_result_path
code_change_manifest_path
code_verification_results_path
code_agent_status
code_agent_usable
```

这些字段只在A03 `code` bundle完成注册后设置，并必须与current pointer、canonical member paths及validated `CodeAgentResult` exact-match。`code_agent_status`只允许`success | no_change | failed | needs_input | needs_human | budget_exhausted | policy_blocked`，`code_agent_usable`只有满足non-empty scoped change、全部required trusted verification及其他route guards的`success`才可为true。Code invalidation必须与A03 current pointer一起原子清空全部canonical字段。

Legacy `code_change_summary_path`和`tests_status_path`保持独立。Future code-slot state path对`legacy_codex_handoff`与`code_agent`使用同一个完整nullable key集合：legacy producer只填legacy paths，canonical producer只填上述新paths和scalars，另一组必须显式为null；没有current code pointer时两组都为空。两类producer不能从字段组合或artifact内容互相解释。

Mutable workspace path、patch bytes、tool transcript、完整verification logs、backend/provider session和ExternalOperation authority不得进入bounded graph state。State/checkpoint至多保存受限identity/reference projection；`producer_operation_id`、phase/revision/lease、Pause binding、workspace lifecycle、receipt/seal/delivery与final evidence继续由project-owned coordinator及immutable control/audit records拥有，不能由Agent、resume payload或model output改写。

上述字段属于Phase B execution schema `0.4`实现目标，不是当前schema `0.2`字段。A05没有修改`AnalysisState`、graph、checkpoint backend或legacy re-entry行为。

## A06 已确认的 Budget 目标 State Boundary（尚未实现）

[A06](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)把budget authority放在immutable policy与append-only execution ledger，而不是graph state。Phase B execution schema `0.4`在现有`execution_history.jsonl`增加`record_type: budget`，Run-local `budget_event_id/index`连续且唯一；允许的event固定为`policy_initialized`、`resource_reserved`、`resource_settled`、`failure_observed`、`grant_issued`、`grant_consumed`和`decision_recorded`。Cycle、Attempt、Transition与automatic-route用量继续从其A02权威记录重放，不建立第二份mutable counter history。

Bounded state只保存可从validated policy与ledger确定性派生的projection，至少包括：

- policy version、profile ID、reference与digest；
- latest budget event/grant counters；
- 每个hard dimension及automatic route scope的used/remaining；
- active failure fingerprint、Run-local occurrence与causal evidence digests；
- nullable active grant identity、scope与consumption state；
- latest `BudgetDecision` summary、exhausted dimensions与typed stop reason。

初始化、恢复、读取、route admission与artifact registration前必须重放authority，并要求projection exact-equal。完整reservation、settlement、fingerprint和grant history不能复制进state或Agent prompt；缺失或篡改已populated projection不能由initialize静默修复。Resource reservation在side effect前写入，crash后未结算项按maximum charge；Code Agent pre-start Backend interval可计入target Attempt与Run active dimensions，但不把scheduled Attempt提前改为`started`。

每个Run还绑定immutable `budget_policy.json`的version/profile/reference/digest及Pause deadline派生输入。Resume必须exact-match同一schema `0.4` policy/runtime；Replay/Fork创建新child并从0计数，不继承reservation、failure occurrence、grant、deadline、counter、current pointer、Human authorization或accepted state。以上均是目标schema，不改变当前`AnalysisState.status`、`retry_count/max_retry`、graph topology或schema `0.2` ledger。

## 第二阶段待实现 schema 议题

以下内容仍未成为当前 `AnalysisState` 合同：

- A04已确认的`run_status`、Pause、ControlOperation和compatibility projections；
- A05已确认的canonical Code Agent bounded fields及其与ExternalOperation、workspace和code bundle的交叉验证；
- A06已确认的budget policy binding、budget ledger events、trusted usage与bounded projection；
- 正式 parallel reducer、per-branch namespace 或 merge semantics。

在相应 implementation tickets 完成前，任何实现或其他文档都不能假设这些字段已经存在。

## Related Documents

- [Architecture](ARCHITECTURE.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Phase A: Control Contracts](tickets/phase-a-control-contracts/OVERVIEW.md)
