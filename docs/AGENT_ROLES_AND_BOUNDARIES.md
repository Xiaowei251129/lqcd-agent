# Agent Roles and Boundaries

## Global Boundary

Agents may support planning, checking, reporting, and risk classification. They must not make final scientific decisions, promote accepted results without approval, modify raw data, fabricate evidence, or route based on free-form text.

## Method Planner Agent

Allowed:

- Convert a user goal into a structured physics goal.
- Identify target observables, required inputs, expected outputs, and method steps.
- Decide whether a code handoff is needed through a structured `code_needed` field.
- Produce `method_plan.json`.

Forbidden:

- Write implementation code.
- Decide central fits or final systematic uncertainties.
- Invent literature or data evidence.

## Codex Handoff Node

Allowed:

- Produce a structured `coder_task_packet.yaml`.
- Read `code_change_summary.md` and `tests_status.json` once a human or external coding step has produced them.
- Invoke the local Codex CLI worker only when the graph is run with explicit automatic handoff enabled.
- Route based on structured test status and retry count.

Forbidden:

- Programmatically invoke Codex by default or without explicit automatic handoff opt-in.
- Modify raw data.
- Modify accepted results, secrets, or files outside the task packet scope.
- Decide physics acceptance.

## Analysis Engineer Agent

Allowed:

- Run allowlisted mock/test/smoke commands.
- Validate expected synthetic artifacts.
- Produce run results, manifest records, and failure classifications.

Forbidden:

- Run arbitrary shell commands.
- Read real raw numeric data during MVP.
- Overwrite previous runs or accepted results.
- Accept or reject physics results.

## Scientific Reviewer Agent

Allowed:

- Review structured outputs for matrix-element consistency versus `z` and `Pz`.
- Produce evidence-based warnings, diagnostics, and recommended checks.
- Cover correlator, fit, and matrix-element sections, even if MVP data only populates matrix-element diagnostics.

Forbidden:

- Select final central fits.
- Delete or mutate data.
- Promote high-risk results.
- Make paper-level claims.

## Decision Coordinator Agent

Allowed:

- Combine method, run, and review artifacts.
- Assign `risk_level`, `recommended_action`, and `human_approval_required`.
- Produce `decision_log.json` with structured reasons, evidence, next actions, and route intent.
- Route low and medium risk to reporting, while recording high or critical risk as requiring approval.
- Represent targeted rerun and code-fix recommendations through existing structured state fields.

Forbidden:

- Ignore severe warnings.
- Promote high or critical risk without human approval.
- Mark medium risk as accepted memory.
- Rewrite human decisions.

## Human Approval Gate

Allowed:

- Generate an approval packet when `human_approval_required` is true.
- Pause for human decision.
- Route according to structured human decision files.

Forbidden:

- Act as an always-on gate for every routine step.
- Modify the content of human decisions.

## Memory and Report Node

Allowed:

- Write accepted, pending, or rejected memory updates according to risk and approval state.
- Produce final reports and evaluation summaries.

Forbidden:

- Delete historical cases.
- Overwrite human approval records.
- Store medium, high, or critical risk outcomes as accepted during Phase 6.
- Store high or critical risk outcomes as accepted without approval.

## Related Documents

- [Architecture](ARCHITECTURE.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
