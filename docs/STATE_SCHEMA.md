# State Schema

## Contract

`AnalysisState` is the public graph-state contract. Nodes may only read and write documented fields. Schema changes require an explicit ticket, updated artifact contracts where relevant, and a decision-log entry when the change affects architecture or policy.

## Fields

```python
class AnalysisState(TypedDict):
    run_id: str
    case_id: str
    user_goal: str
    case_config_path: str
    output_dir: str
    current_node: str
    status: str  # running | success | failed | pending | halted

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

## Invariants

- `run_id`, `case_id`, `user_goal`, `case_config_path`, and `output_dir` are required for every run.
- `checkpoint_backend` is `sqlite` for local CLI MVP runs and `memory` for unit and smoke tests.
- `checkpoint_thread_id` is stable for a given `case_id` and `run_id`.
- `retry_count` must never exceed `max_retry`.
- `human_approval_required` must be true when `risk_level` is `high` or `critical`.
- High and critical outcomes cannot produce accepted memory without a structured human approval record.
- Routing decisions must use structured fields, not markdown summaries.
- `route_decisions` records deterministic route choices, source nodes, reasons, and the structured fields used for routing.
- `event_log` is persisted in full state; LLM-facing context uses selected fields and `event_log_summary`.

## Context Boundary

LLM-facing prompts may include:

- Selected identifiers and status fields.
- Paths to relevant artifacts.
- Bounded summaries of method, run, review, decision, and event-log artifacts.

LLM-facing prompts must not include:

- Full raw numeric data.
- Secrets.
- Long unbounded logs.
- Truncated free-form text as the only source for a routing decision.

## Current Mock Runtime Behavior

The initial graph runtime uses deterministic mock nodes and persists `graph_state.json` after meaningful node completions and route decisions. The full state is also persisted in LangGraph checkpoints.

High and critical risk outcomes route to the Human Approval Gate. The gate sets
`approval_packet_dir` and `human_decision_path` when it writes
`approval_packet/` artifacts. If no valid human decision is present, the state
remains `pending`.

Local CLI runs use `SqliteSaver`. The CLI `--output-dir` argument is an output root; the resolved run output directory is `<output_root>/<case_id>/<run_id>/` and is stored in `state["output_dir"]`. If the CLI is invoked without `--run-id`, it generates a timestamped run id before state initialization. The checkpoint database is written under that run output directory:

```text
<output_root>/<case_id>/<run_id>/checkpoints/graph_checkpoints.sqlite
```

Unit and smoke tests use `MemorySaver`. Both backends use the same stable `checkpoint_thread_id` format:

```text
<case_id>:<run_id>
```

## Related Documents

- [Architecture](ARCHITECTURE.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
