# Decision Log

## 2026-05-27: Freeze Source-of-truth Documentation Scope

Decision:

- Freeze the documentation input scope for the AI-assisted LQCD meson DA LangGraph project.

Confirmed:

- MVP targets pion quasi-DA.
- First golden example is mock-only and uses structured synthetic matrix elements versus `z` and `Pz`.
- Phase 0 through MVP may read raw-data manifests and checksums only, not real raw numeric data.
- Analysis commands are restricted to allowlisted mock, test, and smoke commands.
- Deterministic mock provider is the default through MVP.
- Real providers are deferred until the provider integration phase.
- The graph uses five core agents plus Human Approval Gate and Memory and Report Node.
- SQLite checkpointing persists full graph state.
- LLM-facing context receives selected fields and artifact summaries only.
- High and critical risk outcomes require human approval.
- Low risk may proceed automatically.
- Medium risk may produce a report but remains pending or review-recommended.
- MVP evaluation uses good, ambiguous, and bad synthetic cases.
- MVP done means one command creates report, manifest, decision log, and checkpoint metadata for the mock run.

Rejected Alternatives:

- Generic meson DA before pion quasi-DA focus: rejected to keep MVP scientifically concrete.
- Real raw-data-backed golden example in MVP: rejected to preserve data boundaries.
- No shell execution at all: rejected because allowlisted mock/test/smoke commands are needed for useful verification.
- Memory-only checkpointing: rejected because recoverability and auditability are core requirements.
- Medium risk always gated: rejected to avoid making the human gate always-on for routine review.
- Collapsing the graph to fewer nodes: rejected because the 5+2 architecture cleanly separates planning, execution, review, decision, approval, and reporting.

Open Items:

- Resolved: concrete implementation file paths were established during Phase 0 and later tickets.
- Resolved: the runtime CLI command is `python -m lqcd_agent.graph.run_graph --case ... --output-dir ...`.

Related Documents:

- [Project Specification](PROJECT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)

## 2026-06-01: Create Minimal Repository Skeleton

Decision:

- Create a minimal `src/`-layout Python package with placeholder mock configuration files, an output root placeholder, and an import smoke test.

Confirmed:

- `AGENTS.md` remains the single root AI contract.
- The package has no runtime dependencies in this phase.
- Mock case and runtime config files are placeholders only and contain no raw numeric LQCD data.
- `outputs/` is present only through `.gitkeep`; generated run artifacts remain ignored by default.
- Real LangGraph runtime, live LLM providers, databases, production deployment, and raw-data-backed evaluation cases remain deferred.

Rejected Alternatives:

- Implementing real agents during the skeleton phase: rejected because the current ticket explicitly excludes real agents and real LangGraph runtime.
- Adding provider-specific environment variables now: rejected because provider configuration is deferred to the provider integration phase.

Open Items:

- Resolved: exact MVP CLI command exists through `lqcd_agent.graph.run_graph`.
- Resolved in Phase 8: synthetic good, ambiguous, and bad case definitions exist under `evaluation/cases/`.

Related Documents:

- [Repository Current State](REPO_CURRENT_STATE.md)
- [Tickets](TICKETS.md)
- [Verification Guide](VERIFICATION_GUIDE.md)

## 2026-06-01: Implement Initial Mock LangGraph Runtime

Decision:

- Implement the first runtime as a real LangGraph `StateGraph` with deterministic mock nodes and configurable checkpointing.

Confirmed:

- Unit and smoke tests use `MemorySaver`.
- Local CLI runs use `SqliteSaver`.
- The checkpoint thread id is stable as `<case_id>:<run_id>`.
- CLI checkpoint databases are written under `<output_root>/<case_id>/<run_id>/checkpoints/`.
- Mock nodes write deterministic artifacts and `graph_state.json`.
- Routing records structured route decisions and does not depend on truncated free-form text.
- LLM-facing context is represented by selected state fields and deterministic mock event-log summaries.

Rejected Alternatives:

- A custom replacement graph runtime: rejected because the runtime must exercise LangGraph `StateGraph`.
- Routing on markdown summaries or event-log text: rejected because routing must use structured state fields.
- Real provider calls in the initial runtime: rejected because the project remains mock-first.

Open Items:

- Resolved: Codex Handoff is implemented as a file-based graph node, and the Human Approval Gate was implemented in Phase 7.
- Resolved: manifest generation was implemented in Phase 4.
- Resolved in Phase 8: good, ambiguous, and bad synthetic case configs exist under `evaluation/cases/`.

Related Documents:

- [Architecture](ARCHITECTURE.md)
- [State Schema](STATE_SCHEMA.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-06-10: Add Phase 2B and Canonical Output Root Policy

Decision:

- Add Phase 2B as the required bridge between the standalone Phase 2 Method Planner and the runtime graph.
- Standardize repository examples so `--output-dir` means output root, with run artifacts under `<output_root>/<case_id>/<run_id>/`.

Confirmed:

- Phase 2 remains a standalone deterministic Method Planner implementation.
- Phase 2B will wire that planner into the graph method planner node before Phase 3 Codex Handoff work.
- Phase 2B must use existing `AnalysisState` fields and existing allowed status values unless its ticket explicitly updates the state schema and tests.
- If the integrated planner returns `needs_more_info`, the graph must stop safely with structured errors instead of continuing to analysis.
- If the integrated planner returns `code_needed=true` before Phase 3 exists, the graph must write `coder_task_packet.yaml`, set `coder_task_packet_path`, and stop safely as pending or halted.
- Repository command examples should use `--output-dir outputs`, yielding `outputs/<case_id>/<run_id>/`.
- Existing generated output directories are left untouched and are not treated as reference outputs.

Rejected Alternatives:

- Folding Method Planner graph integration into Phase 3: rejected to keep Codex Handoff work separate from planner integration.
- Treating a mock-specific output directory as the canonical output root in examples: rejected because it obscures the `<output_root>/<case_id>/<run_id>/` policy.

Related Documents:

- [Tickets](TICKETS.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-06-10: Complete Phase 2B Planner Graph Integration

Decision:

- Wire the standalone deterministic Method Planner into the graph method planner node.
- Use existing `AnalysisState` fields and existing status values for planner-safe stops.

Confirmed:

- Planner `code_needed=false` continues to Analysis Engineer.
- Planner `needs_more_info` writes `method_plan.json`, records structured state `errors`, and stops at `END` with `status=pending`.
- Planner `code_needed=true` writes `coder_task_packet.yaml`, sets `coder_task_packet_path`, and stops at `END` with `status=pending` until Phase 3 implements Codex Handoff.
- Routing uses structured fields such as `status`, `code_needed`, `coder_task_packet_path`, and error count.
- No new state fields or status values are required.

Rejected Alternatives:

- Routing `code_needed=true` to Analysis Engineer before Codex Handoff exists: rejected because it would pretend analysis can proceed without the required code handoff.
- Adding a new planner status field in Phase 2B: rejected because existing state fields are sufficient for safe stops.

Related Documents:

- [Architecture](ARCHITECTURE.md)
- [Tickets](TICKETS.md)
- [State Schema](STATE_SCHEMA.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-06-10: Clarify Phase 6 Decision Coordinator Risk Policy

Decision:

- Implement the Decision Coordinator as a deterministic artifact-driven risk rubric over `method_plan.json`, `run_result.json`, and `scientific_review_report.json`.

Confirmed:

- Low risk requires successful structured artifacts, no review warnings, and structured review evidence.
- Medium risk may proceed to report generation but must remain pending or `human_review_recommended`; it must not be written as accepted memory.
- Severe or Decision-Coordinator-flagged Scientific Reviewer warnings force high risk or above.
- High and critical risk always set `human_approval_required=true`.
- Critical risk is reserved for missing, unreadable, identity-mismatched, or otherwise unusable required decision artifacts.
- Phase 6 records targeted rerun and code-fix intent through existing state fields; Phase 7 added the Human Approval Gate, while loop-back execution remains deferred.

Rejected Alternatives:

- Treating medium risk as accepted memory: rejected because the standing policy requires pending or review-recommended handling.
- Routing high and critical outcomes directly to a new approval node in Phase 6: rejected because the Human Approval Gate is the next ticket.
- Adding new `AnalysisState` fields for route intent: rejected because existing `rerun_requested`, `rerun_target`, and `code_fix_requested` fields are sufficient.

Related Documents:

- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [Tickets](TICKETS.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-06-11: Clarify Output Lifecycle and Run Reuse Policy

Decision:

- Treat `outputs/` as a repo-local actual-run output root, not as reference-output storage or schema acceptance evidence.
- Keep future curated evaluation baselines under `evaluation/reference_outputs/` and expected behavior under `evaluation/expected_behavior/`.
- Generate a timestamped run id when the CLI is invoked without `--run-id`.
- Refuse to reuse an explicit run directory that already contains completed or decision artifacts.
- Defer making `lqcd-agent` an independent Git repository to a cleanup/policy ticket.

Confirmed:

- Actual run artifacts continue to use `<output_root>/<case_id>/<run_id>/`.
- Historical ignored files under `outputs/` are generated artifacts and should not be used as current schema evidence.
- Verification should prefer temporary output roots such as `/private/tmp/lqcd-agent-...`.
- A non-empty run directory guard would be too strict because Phase 3 file-based handoff may require pre-existing `tests_status.json` and `code_change_summary.md`.
- Protected-artifact reuse refusal preserves handoff workflows while preventing accidental overwrite of completed runs.
- `--resume` and `--force` remain future explicit policies.

Rejected Alternatives:

- Deleting or reorganizing existing `outputs/` during this maintenance pass: rejected because cleanup requires a dedicated ticket.
- Using `outputs/` for future reference outputs: rejected because actual run artifacts and curated baselines need different lifecycles.
- Blocking any non-empty run directory: rejected because it would break file-based handoff setup.
- Creating an independent Git repository immediately: rejected because current Phase 6/7 work is not blocked by repo boundaries.

Related Documents:

- [Code Build Plan](CODEX_BUILD_PLAN.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
- [Tickets](TICKETS.md)

## 2026-06-22: Productize Conservative Golden Mock Demo

Decision:

- Add a one-command `l64c64a076_m140` golden mock demo that links to sibling golden example files as read-only provenance while keeping generated analysis evidence synthetic.
- Let high and critical no-decision states write pending `memory_update.json` and `final_report.md` after the Human Approval Gate writes its approval packet, while keeping accepted memory blocked.

Confirmed:

- The demo command is `bash scripts/run_langgraph_demo.sh`.
- The demo writes under `outputs/l64c64a076_m140/<run_id>/` by default and supports `LQCD_AGENT_OUTPUT_DIR` and `LQCD_AGENT_RUN_ID`.
- The golden example path is read-only provenance; Phase 9 does not run notebooks, HDF5 analysis, or physics algorithms.
- The generated matrix-element artifact keeps `source_kind: synthetic` and carries a severe demo diagnostic flag so the approval path is exercised.
- `AnalysisState` fields and status values remain unchanged.
- Accepted memory remains impossible for high or critical risk without a valid human decision.

Rejected Alternatives:

- Running the sibling golden example notebooks in Phase 9: rejected because this phase is productization of the mock graph, not physics algorithm execution.
- Treating the synthetic golden demo as final physics output: rejected because the current data boundary forbids final raw-data-backed claims.
- Stopping before final-report generation for high-risk no-decision demos: rejected because developer-facing demo runs need readable pending artifacts while preserving accepted-memory safety.

Related Documents:

- [Architecture](ARCHITECTURE.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Tickets](TICKETS.md)

## 2026-06-22: Tighten Phase 7-9 Audit and Evaluation Cleanup Semantics

Decision:

- Make `decision_log.json` route audit fields reflect the Decision Coordinator's immediate graph route.
- Require explicit force-clean behavior before the synthetic evaluation runner deletes existing per-case run directories.
- Keep high and critical no-decision behavior unchanged: pending audit artifacts may be written, but accepted memory remains blocked.

Confirmed:

- `routing_decision.actual_route` is `human_approval_gate` when human approval is required and `memory_report` otherwise.
- Final reports name approved human decisions from `07_human_decision.yaml`.
- Synthetic evaluation runs refuse to delete an existing run directory unless `--force-clean` or the matching Python flag is used.
- No `AnalysisState` fields, provider behavior, raw-data policy, or Phase 9 golden-demo physics boundaries changed.

Rejected Alternatives:

- Leaving `actual_route` as `memory_report` for high-risk decision logs: rejected because it made audit records ambiguous even though graph routing was safe.
- Always deleting existing evaluation run directories: rejected because actual-run artifacts should not be overwritten or removed implicitly.

Related Documents:

- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-06-22: Complete GitHub-ready Local Artifact Cleanup

Decision:

- Remove ignored generated artifacts before GitHub packaging while preserving source, tests, configs, scripts, docs, and `outputs/.gitkeep`.
- Keep independent Git repository initialization as a separate user-confirmed step after cleanup verification.

Confirmed:

- Historical `outputs/` run artifacts are local actual-run outputs, not reference outputs or schema acceptance evidence.
- `outputs/.gitkeep` is the only file that should remain under repo-local `outputs/` after cleanup.
- `.DS_Store`, `__pycache__/`, `.pytest_cache/`, and `*.egg-info/` are local/generated artifacts and should not be committed.
- The current Git top-level remains `/Users/chengxiaowei`; this ticket does not initialize or push a GitHub repository.

Rejected Alternatives:

- Initializing an independent Git repository during cleanup: rejected because Git setup and GitHub remote choices require explicit user confirmation.
- Preserving historical `outputs/` runs in the repository: rejected because verification should use `/private/tmp/...` or fresh explicit run ids, and reference outputs are deferred to future `evaluation/reference_outputs/`.

Related Documents:

- [Tickets](TICKETS.md)
- [Repository Current State](REPO_CURRENT_STATE.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
