# Artifact Contracts

## General Rules

Artifacts must be machine-readable where they affect routing and human-readable where they support review. JSON or YAML artifacts drive routing; Markdown is for reports and summaries only.

Actual run artifacts are written under `<output_root>/<case_id>/<run_id>/`. Repo-local `outputs/` is ignored actual-run storage, not reference-output storage. Future curated evaluation baselines belong under `evaluation/reference_outputs/`, with expected behavior under `evaluation/expected_behavior/`.

Every artifact that influences a decision must include:

- `schema_version`
- `run_id`
- `case_id`
- `created_at`
- `producer`
- `status`
- `summary`
- `warnings`
- `errors`

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

The packet is a file handoff contract only. The graph runtime must not call Codex
programmatically.

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
- requested decision
- human-readable summary
- method and run context
- available comparisons
- scientific review report reference
- AI recommendation
- risk rationale
- decision options
- human decision template path

The Phase 7 schema uses `schema_version: "0.1"` and `status: pending`.

`07_human_decision.yaml` is a flat YAML decision file with:

- `schema_version`
- `run_id`
- `case_id`
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
Approval Gate remains pending. Invalid decision files keep the run pending with
structured errors. Existing human decision files must not be rewritten by agents.
In Phase 7, `approve_rerun` records rerun route intent but does not implement a
new safe rerun output or resume mechanism.

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
