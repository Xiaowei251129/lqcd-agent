# Prompt Playbook

## Purpose

This playbook defines the standard ticket and prompt formats for future implementation work. Prompts must keep work scoped, auditable, mock-first, and aligned with the source-of-truth docs.

## Global Rules for Every Codex Ticket

- Keep changes scoped to the ticket and preserve the mock-first default unless the ticket explicitly changes provider or data policy.
- Treat `outputs/` as local actual-run artifacts, not reference outputs or schema acceptance evidence.
- Use temporary output roots such as `/private/tmp/lqcd-agent-...` for verification unless the ticket explicitly asks to keep a repo-local run.
- Keep curated evaluation baselines under `evaluation/reference_outputs/` and expected behavior under `evaluation/expected_behavior/`, not under `outputs/`.
- Before the final response, perform a stale-documentation scan. Check whether `README.md`, `docs/ARCHITECTURE.md`, `docs/STATE_SCHEMA.md`, `docs/ARTIFACT_CONTRACTS.md`, `docs/TICKETS.md`, `docs/VERIFICATION_GUIDE.md`, `docs/REPO_CURRENT_STATE.md`, `docs/DECISION_LOG.md`, and TODO comments still accurately describe the implemented phase. Update only stale statements caused by this ticket; do not rewrite unrelated documentation.

## Standard Ticket Contract

````text
Task:
[One clear implementation or documentation task.]

Read First:
- AGENTS.md
- docs/PROMPT_PLAYBOOK.md
- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/SECURITY_AND_DATA_POLICY.md
- docs/VERIFICATION_GUIDE.md

Allowed Files:
- [Explicit file or directory list.]

Do Not Touch:
- [Explicit forbidden files or directories.]

Requirements:
- [Concrete behavior and constraints.]

Non-goals:
- [What must not be added.]

Acceptance Criteria:
- [Observable success conditions.]

Verification Commands:
```bash
[Commands to run, or "None" for pure documentation tasks.]
```

Stop Conditions:
- [Conditions that require stopping and asking.]

End-of-task Updates:
- Update docs/REPO_CURRENT_STATE.md.
- Update docs/DECISION_LOG.md if architecture or policy changed.
- Complete the stale-documentation scan from this playbook.

Final Response:
Changed / Why / Verified / Next
````

## Standard Phase Prompt Wrapper

Use this wrapper around every implementation ticket:

```text
You are working in the LQCD agent repository.

Assume:
- AGENTS.md is the root AI contract.
- docs/PROMPT_PLAYBOOK.md contains global ticket rules.
- The project is mock-first until a provider integration ticket explicitly changes that.
- raw_data/ and accepted_results/ are out of scope unless a future policy ticket explicitly allows them.
- Routing decisions must use structured state fields and artifacts, not free-form prose.

Execute only the ticket below. Keep changes surgical and verify before the final response.

[Paste the Standard Ticket Contract here.]
```

## Standard End-of-task Summary

Use this final response structure:

```text
Changed:
[Files and behavior changed.]

Why:
[Reason the change satisfies the ticket.]

Verified:
[Commands or checks run.]

Next:
[Immediate next step or known blocker.]
```

## Worked Example: Node Implementation Ticket

````text
Task:
Create the Method Planner mock node module that writes a deterministic method_plan.json artifact from the current AnalysisState.

Read First:
- AGENTS.md
- docs/PROMPT_PLAYBOOK.md
- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/VERIFICATION_GUIDE.md

Allowed Files:
- src/lqcd_agent/nodes/method_planner.py
- tests/test_method_planner.py
- docs/REPO_CURRENT_STATE.md

Do Not Touch:
- raw_data/
- accepted_results/
- external APIs
- real analysis scripts
- production deployment files
- secrets or credentials

Requirements:
- Implement a deterministic mock Method Planner node only.
- Read and write only documented AnalysisState fields.
- Write method_plan.json with the required general artifact fields and Method Plan fields.
- Set code_needed from structured mock configuration, not free-form prose.
- Add focused tests for a no-code mock plan and a code-needed mock plan.
- Keep all code comments in English.

Non-goals:
- No real LangGraph graph wiring.
- No real LLM call.
- No real physics-analysis implementation.
- No new schema fields.

Acceptance Criteria:
- The node returns updated state with method_plan_path and code_needed populated.
- method_plan.json includes schema_version, run_id, case_id, created_at, producer, status, summary, warnings, and errors.
- Tests cover both code_needed values.
- Existing import smoke test still passes.

Verification Commands:
```bash
pytest tests/test_import.py tests/test_method_planner.py -q
```

Stop Conditions:
- Stop if a new state field appears necessary.
- Stop if the implementation would need live provider access.
- Stop if raw numeric data would be read.
- Stop if artifact contracts are insufficient for the required method_plan.json fields.

End-of-task Updates:
- Update docs/REPO_CURRENT_STATE.md with the new mock node status.
- Update docs/DECISION_LOG.md only if the architecture or state contract changes.

End-of-task Updates Format:
- Changed: [files and behavior changed]
- Why: [how this satisfies the ticket]
- Verified: [commands run and results]
- Next: [next ticket or blocker]
````

## Worked Example: Diagnostic Module Ticket

````text
Task:
Create a mock matrix-element diagnostic module for synthetic pion quasi-DA artifacts.

Read First:
- AGENTS.md
- docs/PROMPT_PLAYBOOK.md
- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/VERIFICATION_GUIDE.md

Allowed Files:
- src/lqcd_agent/diagnostics/matrix_elements.py
- tests/test_matrix_element_diagnostics.py
- docs/REPO_CURRENT_STATE.md

Do Not Touch:
- raw_data/
- accepted_results/
- external APIs
- real analysis scripts
- production deployment files
- secrets or credentials

Requirements:
- Accept only synthetic matrix-element artifact dictionaries.
- Validate required row fields: z, Pz, component, value, error.
- Return structured diagnostic flags and warnings.
- Detect missing components, negative uncertainties, and non-synthetic source_kind.
- Keep diagnostics deterministic and independent of LLM providers.
- Keep all code comments in English.

Non-goals:
- No Fourier transform implementation.
- No perturbative matching implementation.
- No central fit or systematic uncertainty decisions.
- No raw-data-backed evaluation cases.
- No graph routing changes.

Acceptance Criteria:
- Good synthetic input returns status success with no high-risk flags.
- Negative uncertainty input returns a structured warning or failure.
- Non-synthetic source_kind is rejected.
- Tests document the expected diagnostic outputs.

Verification Commands:
```bash
pytest tests/test_import.py tests/test_matrix_element_diagnostics.py -q
```

Stop Conditions:
- Stop if real raw data is needed to define the diagnostic.
- Stop if the artifact contract lacks a required field and would need a schema change.
- Stop if a diagnostic would imply a final physics claim.
- Stop if implementation requires dependencies beyond packaging/test basics.

End-of-task Updates:
- Update docs/REPO_CURRENT_STATE.md with the diagnostic module status.
- Update docs/DECISION_LOG.md only if the architecture, policy, or artifact contract changes.

End-of-task Updates Format:
- Changed: [files and behavior changed]
- Why: [how this satisfies the ticket]
- Verified: [commands run and results]
- Next: [next ticket or blocker]
````

## Prompt Rules

- Keep documentation and implementation tickets separate.
- Keep mock provider as the default until provider integration is explicitly approved.
- Do not ask for or print real API keys.
- Do not include raw numeric data in prompts.
- Do not route on free-form model prose.
- Include stop conditions for data, approval, checkpointing, and schema ambiguity.
- Mark unresolved documentation items as `TODO(owner:name, reason:reason)`.

## Related Documents

- [Tickets](TICKETS.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
