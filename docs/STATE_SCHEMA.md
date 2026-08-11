# State Schema

## 当前合同

`AnalysisState` 是当前公开 graph-state contract。节点只能读取和写入已记录字段。下面的 schema 与当前 runtime 对齐；本次文档迁移不增加、不删除也不重命名任何字段。

schema 变化必须由独立 ticket 批准，并同步 runtime、tests、artifact contracts 和相关 Decision Log。未来的 Run/Cycle/Attempt、reducer 或 namespace 目前只是 draft 议题，不属于正式 schema。

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

    checkpoint_thread_id: str
    checkpoint_backend: str  # memory | sqlite
    checkpoint_db_path: str | None

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
- `retry_count` 不得超过 `max_retry`。
- `risk_level` 为 `high` 或 `critical` 时，`human_approval_required` 必须为 true。
- 没有 structured human approval record 时，high/critical outcome 不得写 accepted memory。
- routing 必须使用 structured fields，而不是 Markdown summary。
- `route_decisions` 记录 deterministic route、source node、reason 和所用字段。
- `event_log` 完整保存在 state；LLM-facing context 只使用选定字段和 `event_log_summary`。

## Context 边界

LLM-facing prompt 可以包含：

- selected identifiers 与 status fields；
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

high/critical outcome 进入 Human Approval Gate。gate 写 `approval_packet/` 时设置 `approval_packet_dir` 和 `human_decision_path`；没有有效决定时 state 保持 `pending`。

Local CLI 使用 `SqliteSaver`。`--output-dir` 是 output root；解析后的 run directory 为 `<output_root>/<case_id>/<run_id>/`，并写入 `state["output_dir"]`。省略 `--run-id` 时，在 state 初始化前生成 timestamp run id。checkpoint database 位于：

```text
<output_root>/<case_id>/<run_id>/checkpoints/graph_checkpoints.sqlite
```

Unit/smoke tests 使用 `MemorySaver`。两种 backend 使用相同的 `checkpoint_thread_id` 格式：

```text
<case_id>:<run_id>
```

## 第二阶段待决 schema 议题

以下内容尚未成为 `AnalysisState` 合同：

- [A02](tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md)：Run/Cycle/Attempt identity 与 lifecycle；
- [A03](tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md)：artifact validity、supersession 与 invalidation；
- [A04](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)：pause/resume 与 checkpoint compatibility；
- 正式 parallel reducer、per-branch namespace 或 merge semantics。

在这些 ticket 进入 `ready` 并完成前，任何实现或其他文档都不能假设这些字段已经存在。

## Related Documents

- [Architecture](ARCHITECTURE.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Phase A: Control Contracts](tickets/phase-a-control-contracts/OVERVIEW.md)
