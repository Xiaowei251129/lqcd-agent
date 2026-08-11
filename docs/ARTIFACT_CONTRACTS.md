# Artifact Contracts

## 第二阶段文档定位

本文记录当前 runtime 已经实现并由测试覆盖的 artifact contracts。下面保留英文 schema identifiers、field names、status values 和文件名，解释以这些精确合同为准。

A02 corrective implementation 已完成 Run/Cycle/Attempt/Transition/Human execution ledger 与 state-aware identity metadata 验收。per-attempt domain-artifact namespace、artifact supersession/invalidation、Code Agent patch/evidence bundle 和 physics RAG evidence bundle 尚未获批，不属于当前合同。它们只能先在 [A03](tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md)、[A05](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md) 及后续独立 ticket 中讨论。普通 ticket 不能仅通过修改 artifact writer 就隐式改变这里的 public contract。

## Execution Identity History

[A02 Run/Cycle/Attempt Model](tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md) 在每个 run root 写入：

```text
<output_root>/<case_id>/<run_id>/execution_history.jsonl
```

ledger schema version 是 `0.2`，`record_type` 固定为 `run`、`cycle`、`attempt`、`transition`、`human_request` 或 `human_response`。新 Run 的前四条 authoritative records 顺序固定为：

```text
Run created
-> initial Cycle created
-> Planner Attempt scheduled
-> START -> method_planner Transition committed
```

每个 Run 恰好一个 Run `created` record，记录 `parent_run_id`、`creation_reason`、root-goal reference/digest、input-snapshot reference/digest、canonical output root 和 Run-owned `checkpoint_thread_id`。Cycle `created` record 只记录自身 Run/Cycle lineage、trigger 和 creating Attempt，不混入旧 Attempt envelope。

每次 node invocation 的 Attempt 使用同一 ID 追加以下 lifecycle records：

```text
scheduled -> started -> finished (succeeded | failed | pending)
scheduled -> abandoned
```

Attempt record 分开记录 canonical `attempt_kind` 和 physical `node_name`、parent Attempt、inbound Transition、input/output references 与 optional error。当前 physical `codex_handoff` 的 canonical kind 是 `legacy_codex_handoff`；`code_agent` 只为 A05/Phase B protocol 预留，当前产品 graph 不执行它。

每条来源路线另外写一个 Transition `committed` record，包括 deterministic ID/index、source/target Cycle、source/target Attempt、physical target、canonical target kind、route/trigger/reason/evidence，以及 applied state-update keys/digest。END transition 的 target fields 为 null。target Attempt 在 Transition commit 中、目标节点任何副作用之前预分配；fixed 和 conditional routes 使用相同协议。

Human Request/Response 是独立 records，不是 Human Gate Attempt。Coordinator 进入 Gate 时创建 `human_request_*`，记录 request kind、requesting Coordinator Attempt、authorization scope 和 packet reference。外部提交创建 `human_response_*`；同一 response ID 依次追加 `submitted -> validated -> consumed` 或 `submitted -> invalid`，并记录 payload snapshot/digest、validated decision、logical authorized route、精确 authorized Transition route/target、validator Gate Attempt、consumer Gate Attempt 和 authorized target Attempt。validated response 只能消费一次。

文件只允许 append，不允许覆盖；legacy incomplete-Run re-entry 从已有 records 恢复 counters，不能复用旧 IDs，也不能被描述为 A04 durable resume。

event log、route decisions、approval packet、memory update 和 final report 记录 relevant current identity。JSON artifact writer 会附加 `cycle_id`、`attempt_id`、`parent_attempt_id`、`attempt_kind`、`attempt_node`、`inbound_transition_id` 和 `committed_transition_id`；其他现有 domain artifacts 通过 execution ledger 的 input/output references 追溯 producing Attempt。Run 继续拥有 `<output_root>/<case_id>/<run_id>/`；现有 domain-artifact fixed paths 保持不变，A03 决定 per-attempt namespace、versioning、current pointers 和 invalidation。

## 当前通用规则

以下通用 metadata 规则适用于 domain artifacts；`execution_history.jsonl` 使用上一节按 `record_type` 区分的 ledger contract，不要求把 domain artifact 的 `producer`、`summary`、`warnings` 和 `errors` 无差别复制到每条 identity record。

影响 routing 的 artifact 必须 machine-readable；支持人工 review 的内容应同时 human-readable。JSON/YAML 可以驱动 routing，Markdown 只用于 report 和 summary。

实际运行 artifacts 写入 `<output_root>/<case_id>/<run_id>/`。仓库内 `outputs/` 是 ignored actual-run storage，不是 reference-output storage。curated evaluation baseline 属于 `evaluation/reference_outputs/`，expected behavior 属于 `evaluation/expected_behavior/`。

所有影响 decision 的 artifact 必须包含：

- `schema_version`
- `run_id`
- `case_id`
- `created_at`
- `producer`
- `status`
- `summary`
- `warnings`
- `errors`

## LLM Call Traces

Provider-backed Method Planner, Scientific Reviewer, and Decision Coordinator calls write audit records under:

```text
<output_root>/<case_id>/<run_id>/llm_calls/<agent>.json
```

Each trace records the agent, timestamp, status, non-secret provider metadata, structured request, provider response when available, parsed artifact path, and structured errors. API keys and environment-variable values must never be written. Trace files may contain bounded prompt and response content, so they remain run artifacts under ignored output storage rather than curated source or reference outputs. The manifest records trace files, and the final report links the available traces for reproducibility.

## Method Plan

`method_plan.json` records:

- `physics_goal`
- `target_observables`
- `method_steps`
- `required_inputs`
- `required_outputs`
- `implementation_gaps`
- `code_needed`
- `coder_task_summary`

When critical planner inputs are missing, `method_plan.json` uses `status: needs_more_info`,
records the missing fields in `errors`, and leaves downstream planning lists empty. Critical
planner inputs are `user_goal`, `case_config`, `case_config.case_id`, and `repo_inventory`.

## Coder Task Packet

`coder_task_packet.yaml` is written only when `method_plan.json` has `status: success` and
`code_needed: true`. It records:

- general artifact metadata
- `task_summary`
- `physics_goal`
- `implementation_gaps`
- `allowed_files`
- `forbidden_paths`
- `requirements`
- `acceptance_criteria`
- `verification_commands`
- `context_artifacts`

The Phase 3 task-packet schema uses `schema_version: "0.1"` and `status: pending`.
Required string fields are `schema_version`, `run_id`, `case_id`, `created_at`,
`producer`, `status`, `summary`, `task_summary`, and `physics_goal`. Required list
fields are `warnings`, `errors`, `implementation_gaps`, `allowed_files`,
`forbidden_paths`, `requirements`, `acceptance_criteria`, `verification_commands`,
and `context_artifacts`. `allowed_files`, `forbidden_paths`, `requirements`,
`acceptance_criteria`, `verification_commands`, and `context_artifacts` must be
non-empty lists.

The packet is a file handoff contract by default. The graph runtime must not call
Codex programmatically unless the run has explicit automatic handoff opt-in. In
automatic handoff mode, the graph invokes the local Codex CLI worker, which must
still respect forbidden paths, allowed files, and verification commands.

## Codex Handoff Results

The Codex Handoff node reads external handoff result files from the run output
directory:

- `code_change_summary.md`
- `tests_status.json`

`code_change_summary.md` is a human-readable summary of the external code change.
It is required before a passing handoff can continue to analysis, but routing must
not be based on markdown content.

`tests_status.json` records:

- general artifact metadata
- `commands`

Each command record includes:

- `command`
- `working_directory`
- `timeout_seconds`
- `return_code`
- `stdout`
- `stderr`
- `produced_files`
- `status`

The Phase 3 test-status schema uses `schema_version: "0.1"` and `producer: test_runner`.
The top-level `status` must be `tests_passed` or `tests_failed`.
Command-level `status` must be `passed`, `failed`, `blocked`, or `timeout`.

Routing after Codex Handoff uses only the structured top-level `tests_status.json`
`status` field. `tests_passed` plus a present `code_change_summary.md` routes to
Analysis Engineer. `tests_failed`, missing result files, or invalid test status
stops safely before analysis with `pending` or `halted` graph state.

## Synthetic Matrix-Element Artifact

The mock golden example uses structured synthetic matrix elements:

- `z_values`
- `pz_values`
- `matrix_elements`
- `normalization`
- `uncertainties`
- `diagnostic_flags`
- `source_kind: synthetic`

Each matrix-element row should include `z`, `Pz`, `component`, `value`, `error`, and optional flags. MVP diagnostics focus on consistency versus `z` and `Pz`; Fourier transform and matching are documented as future slots, not MVP requirements.

The Phase 9 `l64c64a076_m140` demo may also include a `golden_example` provenance object. This metadata links the synthetic artifact to read-only sibling example files; it is not a claim that the mock artifact contains final physics results.

## Phase 10C Synthetic Benchmark Artifacts

Phase 10C advisor-demo benchmark artifacts were implemented on 2026-06-23 as
synthetic-only contracts. They remain separate from Phase 11 raw-data-backed
reference outputs and must not be treated as accepted physics results.

`evaluation/synthetic_benchmarks/scenarios/*.input.json` records:

- general scenario metadata, including `case_id`, scenario category, and user-facing goal
- synthetic input-data path or generator configuration
- fields that agents may read during the run

`evaluation/synthetic_benchmarks/expected/*.expected.json` records the
instructor-only hidden grading contract:

- expected qualitative conclusion
- numeric tolerances where applicable
- expected risk level and recommended action
- expected graph route and route branch
- required or forbidden reviewer warnings
- expected memory status
- Human Approval Gate expectations

Expected behavior must not be passed to agents as input and must not be used as
the main evidence in `final_report.md`.

`analysis_outputs/synthetic_benchmark_input.json` is the per-run copy of the
agent-visible scenario input. It must not contain instructor-only expected
behavior.

`analysis_outputs/synthetic_data.csv` is the per-run synthetic fixture consumed
by the Analysis Engineer.

`analysis_outputs/fit_summary.json` records case-specific analysis results
produced from the scenario synthetic data:

- general artifact metadata with `producer: analysis_engineer`
- input scenario and synthetic-data references
- model or fit method
- fitted parameters and uncertainties
- fit quality or residual diagnostics where applicable
- warnings and errors

`demonstration_checklist.json` records the per-scenario advisor-demo judgment:

- input understood
- method plan written
- Analysis Engineer consumed scenario-specific data
- analysis command recorded
- fit summary produced where applicable
- reviewer findings grounded in artifacts
- decision reasons structured
- expected conclusion observed
- expected route observed
- Human Approval Gate behavior correct when applicable
- memory status correct
- final report coherent
- actual-vs-expected status and notes

`synthetic_rehearsal_summary.md` is the run-level summary. It must list each
scenario, route path, key fit result, reviewer findings, decision/risk/action,
memory status, artifact inspection paths, advisor checklist status, and
actual-vs-expected status.

`advisor_demo_report.md` is the live-provider demonstration handoff. It must
compare each scenario question, hidden expected conclusion summary, actual
agent conclusion, expected and actual route, expected and actual risk/action,
required or forbidden warnings, memory status, Human Gate behavior, pass/fail
or review-needed status, and links to the supporting artifacts.

## Run Result and Manifest

`run_result.json` is written by the Analysis Engineer under the canonical run directory:

```text
<output_root>/<case_id>/<run_id>/run_result.json
```

It records:

- general artifact metadata
- `run_success`
- `failure_type`, using the existing state values `code`, `config_or_data`, `workflow`, `unknown`, or `null`
- `analysis_outputs_dir`
- `expected_outputs`
- `produced_outputs`
- `validation_results`
- `command_references`
- full command records
- `run_log_path`
- `manifest_path`

Phase 4 validates expected outputs before setting `run_success=true`. Missing expected outputs produce `failure_type: config_or_data`. Failed or timed-out configured commands produce `failure_type: code`; blocked unsafe or unapproved commands produce `failure_type: config_or_data`.

`manifest.json` records provenance:

- `run_id`
- `case_id`
- `created_at` and timestamp
- git commit and bounded status summary
- config hash
- input files
- output files
- commands
- tool versions
- environment summary
- warnings and errors

`run.log` is a plain-text execution log written beside `run_result.json` and `manifest.json`.

Phase 4 analysis outputs are written under:

```text
<output_root>/<case_id>/<run_id>/analysis_outputs/
```

The default mock output is:

```text
analysis_outputs/synthetic_matrix_elements.json
```

The Analysis Engineer refuses to overwrite existing `run_result.json`, `manifest.json`, or `run.log` unless explicit force behavior is enabled by the caller.

## Scientific Review Report

`scientific_review_report.json` records:

- `correlator_diagnostics`
- `fit_diagnostics`
- `matrix_element_diagnostics`
- `findings`
- evidence
- warnings
- recommended checks
- confidence

The Phase 5 schema uses `schema_version: "0.1"` and `producer: scientific_reviewer`.
The report is written under the canonical run directory:

```text
<output_root>/<case_id>/<run_id>/scientific_review_report.json
```

Each diagnostic section records:

- `status`
- `summary`
- `evidence`
- `findings`
- `warnings`
- `recommended_checks`

`correlator_diagnostics` and `fit_diagnostics` remain present for every review. When the
mock MVP has no correlator or fit summary artifacts, these sections use
`status: not_populated_mvp` without creating a warning. `matrix_element_diagnostics`
reviews the synthetic matrix-element artifact for source kind, required fields, finite
values, positive errors, diagnostic flags, simple consistency versus `z` and `Pz`, and
`mock_unit` normalization at `z=0`.

Every warning must include concrete evidence fields:

- `section`
- `code`
- `severity`
- `decision_coordinator_flag`
- `message`
- `path`
- `field`
- `value`

Severe warnings use `severity: severe` and `decision_coordinator_flag: true` so the
Decision Coordinator can treat them as high-risk evidence in Phase 6. Non-severe warnings
use `severity: warning` and `decision_coordinator_flag: false`.

## Decision Log

`decision_log.json` records:

- general artifact metadata with `producer: decision_coordinator`
- `risk_rubric`
- `risk_level`
- `recommended_action`
- `human_approval_required`
- structured `reasons`
- structured `evidence`
- `next_actions`
- structured `routing_decision`

The Phase 6 schema uses `schema_version: "0.1"`. `risk_level` uses the existing
state values `low`, `medium`, `high`, or `critical` after the decision is made.
`recommended_action` is one of the Phase 6 deterministic actions:

- `accept_mock_result`
- `human_review_recommended`
- `pending_human_approval`
- `targeted_rerun`
- `code_fix`

Exactly one `next_actions` entry must use `primary: true`. The route fields in
`routing_decision` are structured and include `actual_route`, `requested_route`,
`proposed_follow_up_route`, and the state fields used for routing intent:
`risk_level`, `recommended_action`, `human_approval_required`,
`rerun_requested`, `rerun_target`, and `code_fix_requested`.
`actual_route` records the Decision Coordinator's immediate graph route:
`human_approval_gate` when human approval is required, otherwise `memory_report`.

Phase 6 risk policy:

- `critical`: required artifacts are missing or unreadable, artifact schema or
  run identity conflicts with the active run, or the method plan is not usable.
- `high`: the run failed and needs a code fix or targeted rerun, or the
  Scientific Reviewer produced a severe or Decision-Coordinator-flagged warning.
- `medium`: the run succeeded, but non-severe warnings, medium review
  confidence, or missing review evidence prevent low-risk acceptance.
- `low`: the method plan, run result, and scientific review all succeeded with
  no warnings and structured review evidence.

Severe warnings must never produce low risk. High and critical risk always set
`human_approval_required: true`. Medium risk must remain pending or
human-review-recommended and must not be written as accepted memory.

## Approval Packet

An approval packet is generated only when `human_approval_required` is true. It is
written under:

```text
<output_root>/<case_id>/<run_id>/approval_packet/
```

The directory contains:

- `approval_packet.json`
- `approval_summary.md`
- `07_human_decision.yaml`

`approval_packet.json` records:

- general artifact metadata with `producer: human_approval_gate`
- `cycle_id`, `human_request_id`, `requesting_attempt_id`, current `attempt_id`, and `parent_attempt_id`
- the request `authorization_scope`
- requested decision
- human-readable summary
- method and run context
- available comparisons
- scientific review report reference
- AI recommendation
- risk rationale
- decision options
- human decision template path

The current approval projection uses `schema_version: "0.2"` and `status: pending`.

`07_human_decision.yaml` is a flat YAML decision file with:

- `schema_version`
- `run_id`
- `case_id`
- `cycle_id`
- `human_request_id`
- `requesting_attempt_id`
- `human_response_id`
- `decision`
- `conditions`
- `reason`
- `decided_by`
- `decided_at`

Supported `decision` values are:

- `approve_with_conditions`
- `approve_rerun`
- `request_code_change`
- `reject_or_hold`

If `07_human_decision.yaml` is missing or has `decision: null`, the Human
Approval Gate remains pending and the request remains open. A non-empty 0.2
decision must match the active Run, Cycle, request, requesting Attempt, and
control-plane-assigned response ID. Invalid decision files append an invalid
response lifecycle record and leave the request open. A worker Agent does not
rewrite an identity-bound human decision. The control plane refreshes the fixed
current template to `decision: null` when a new request replaces the previous
request, and the external submission path writes the response projection.

Schema 0.1 is not auto-bound to the active request. It can only be parsed by an
explicit legacy-import caller that supplies the missing identity bindings and
proves that the ledger has exactly one matching open request. A validated 0.2
response is single-use: its frozen decision, logical route, exact Transition
route/target, validation Attempt, consuming Gate Attempt, authorized target
Attempt, and satisfied request are recorded in `execution_history.jsonl`.
Duplicate submission or consumption is rejected and must not change counters,
append ledger records, create a new target Attempt, or rewrite memory/report
artifacts. Network-delivery idempotency keys and replay semantics remain an A04
responsibility.

The current demo still follows the Phase 7 compatibility topology:
`request_code_change` transitions directly to legacy Codex Handoff,
approve/reject reporting decisions transition directly to Memory Report, and
`approve_rerun` consumes the response but records intent and ends pending rather
than executing Analysis Engineer. The graph still declares an Analysis Engineer
compatibility target for the Gate, but the current selector does not execute that
target for `approve_rerun`. None of this is the A01 target contract, where a
valid Human response must return to Decision Coordinator. A04 owns durable
PAUSE/resume and A07/Phase B owns the product-route migration.

## Final Report and Memory Update

`final_report.md` contains metadata, method summary, run summary, scientific review, warnings, decision status, approval status, next actions, and reproducibility notes.

Memory updates are categorized as accepted, pending, or rejected. High and critical risk outcomes require human approval before accepted memory can be written.

In Phase 8, low-risk `recommended_action: accept_mock_result` writes accepted
memory when no human approval is required. Medium outcomes write pending memory.
High and critical outcomes write an approval packet and may continue to the
Memory and Report Node only to write pending `memory_update.json` and
`final_report.md` artifacts. They must not write accepted memory until a valid
human decision permits it. A valid `approve_with_conditions` decision can write
accepted memory, while a valid `reject_or_hold` decision writes rejected memory.

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [State Schema](STATE_SCHEMA.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
