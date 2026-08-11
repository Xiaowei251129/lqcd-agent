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
- `docs/TICKETS.md`（已归档于 `v0.2-demo`）
- [Verification Guide](VERIFICATION_GUIDE.md)

## 2026-06-22: Add Secure LLM Provider Abstraction

Decision:

- Add a Phase 10 LLM provider abstraction with deterministic mock defaults and secure dry-run configuration for OpenAI and DeepSeek.

Confirmed:

- Mock provider behavior remains the default test path.
- Provider configuration may load a repo-local `.env` file without overriding exported environment variables.
- `.env` and `.env.*` are ignored, while `.env.example` remains tracked with placeholder names only.
- Live provider calls require `RUN_LIVE_LLM_TESTS=1` and provider-specific key/model environment variables.
- Dry-run readiness output may include missing environment variable names but must not print loaded values.
- Provider output must be parsed as structured JSON before it can affect future routing or agent artifacts.

Rejected Alternatives:

- Adding a dotenv dependency: rejected because Phase 10 can safely parse simple local `.env` files without a new dependency.
- Wiring live providers into graph agents in Phase 10: rejected because Phase 10B is the dedicated provider-backed agent wiring ticket.
- Requiring live API calls for verification: rejected because normal tests must pass without network access or secrets.

Related Documents:

- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-06-22: Wire Provider-backed Agents Through Explicit Graph Config

Decision:

- Add Phase 10B provider-backed Method Planner, Scientific Reviewer, and Decision Coordinator execution behind explicit runner/provider injection and graph `--llm-provider-config`.

Confirmed:

- Deterministic agent paths remain the default when no provider config is supplied.
- `AnalysisState` carries `llm_provider_config_path` so graph nodes can select provider-backed execution without changing graph topology.
- Provider-backed output must be valid JSON and pass strict artifact schema checks before it can affect artifacts or routing.
- Invalid provider output writes structured failed artifacts and routes only through conservative structured fields.
- Normal tests and mock-provider graph smoke checks do not require network access or secrets.

Rejected Alternatives:

- Environment-only provider selection: rejected because it is less explicit and less auditable than a state-carried config path.
- Free-form provider text for routing: rejected because routing must use validated structured fields.
- Requiring live provider calls for Phase 10B verification: rejected because ordinary verification must remain network-free.

Related Documents:

- [Architecture](ARCHITECTURE.md)
- [State Schema](STATE_SCHEMA.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)

## 2026-06-23: Preserve Local Risk Floor for Provider-backed Decisions

Decision:

- Provider-backed Scientific Reviewer and Decision Coordinator paths must preserve deterministic local safety evidence. A provider may raise risk or add structured reasoning, but it must not lower severe warnings, severe diagnostic flags, failed runs, unusable artifacts, or high/critical local evidence into low-risk accepted memory.

Confirmed:

- Provider prompts use bounded artifact summaries instead of raw numeric data or unbounded logs.
- Decision Coordinator computes a local deterministic safety floor before accepting provider output.
- If provider output proposes a lower risk than the local floor, `decision_log.json` records `provider_safety_floor` and routes through the conservative local risk path.
- The `l64c64a076_m140` golden demo remains pending and Human-Gate-routed even when run through `configs/runtime/mock_llm.yaml`.

Rejected Alternatives:

- Trusting schema-valid provider output alone: rejected because schema validity does not prove that high-risk local evidence was preserved.
- Letting mock provider always return low risk: rejected because mock-provider graph checks must exercise provider-backed safety semantics, not only provider plumbing.
- Passing full raw data to providers: rejected because Phase 10B must preserve the no-raw-numeric-data prompt boundary.

Related Documents:

- [Architecture](ARCHITECTURE.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-06-23: Strengthen Phase 10C into an Advisor-demo Benchmark

Decision:

- Define Phase 10C as an advisor-demo benchmark over controlled synthetic scientific scenarios, not only a provider-backed infrastructure rehearsal.

Confirmed:

- Phase 10C remains synthetic-only and does not read real raw numeric data.
- Phase 10C does not produce accepted physics results, accepted real-data results, paper-level claims, or final LQCD physics conclusions.
- Analysis Engineer must consume scenario-provided synthetic data or generated fixtures and produce case-specific analysis and fit artifacts.
- Each scenario must include instructor-only expected behavior with expected conclusions, tolerances where applicable, risk/action/route expectations, warning expectations, memory status, and Human Approval Gate expectations.
- Instructor-only expected behavior must not be passed to agents as input.
- Live-provider rehearsal must produce an advisor-facing report comparing actual agent conclusions and routes against expected behavior.

Rejected Alternatives:

- Treating Phase 10C as a generic LLM question-answer benchmark: rejected because it would test the provider model more than the multi-agent artifact workflow.
- Letting the existing fixed mock matrix-element payload satisfy all Phase 10C cases unchanged: rejected because the advisor demo must show scenario-specific analysis behavior.
- Moving raw-data-backed evidence chains into Phase 10C: rejected because Phase 11 is the dedicated phase for raw-data-backed evaluation and deeper physics capability.

Related Documents:

- `docs/CODEX_BUILD_PLAN.md`（已归档于 `v0.2-demo`）
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
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

- `docs/TICKETS.md`（已归档于 `v0.2-demo`）
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
- `docs/TICKETS.md`（已归档于 `v0.2-demo`）
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
- `docs/TICKETS.md`（已归档于 `v0.2-demo`）
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

- `docs/CODEX_BUILD_PLAN.md`（已归档于 `v0.2-demo`）
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
- `docs/TICKETS.md`（已归档于 `v0.2-demo`）

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
- `docs/TICKETS.md`（已归档于 `v0.2-demo`）

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
- At cleanup-ticket time, before the later independent-repository setup, the Git top-level remained `/Users/chengxiaowei`; the cleanup ticket did not initialize or push a GitHub repository.

Rejected Alternatives:

- Initializing an independent repository during cleanup: rejected because Git setup and GitHub remote choices require explicit user confirmation.
- Preserving historical `outputs/` runs in the repository: rejected because verification should use `/private/tmp/...` or fresh explicit run ids, and reference outputs are deferred to future `evaluation/reference_outputs/`.

Related Documents:

- `docs/TICKETS.md`（已归档于 `v0.2-demo`）
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-06-30: Verify Phase 10C with Live Provider and Evidence-grounded Provider Risk

Decision:

- Use `analysis:run_synthetic_benchmark:<scenario_path>` as the Phase 10C statistical Analysis Engineer command for generated benchmark cases.
- Keep `synthetic_benchmark_input.json`, `synthetic_data.csv`, and `fit_summary.json` as audit support files, while only `synthetic_matrix_elements.json` enters the Phase 4 expected-output acceptance contract.
- Constrain provider-backed reviewer warnings to structured, evidence-grounded warnings; context-only or ungrounded non-severe cautions do not affect routing.
- Constrain provider-backed Decision Coordinator output with local evidence policy: provider output cannot downgrade deterministic severe/high evidence, and unsupported Human Gate escalation is reduced to the local low/medium policy route.

Confirmed:

- The live OpenAI-compatible Phase 10C demo case set completed with all five demo cases passing expected risk, route, memory, warning, and Human Gate checks.
- Deterministic and mock-provider paths remain network-free and continue to pass the full test suite.
- No raw numeric production data is read; Phase 10C remains synthetic-only.

Rejected Alternatives:

- Treating every provider caution as route-changing warning evidence: rejected because it allowed ungrounded synthetic-context warnings to block low-risk accepted memory.
- Letting provider decisions force Human Gate for non-severe evidence: rejected because Human Gate should require deterministic severe/high evidence or valid local policy support.

Related Documents:

- [Architecture](ARCHITECTURE.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-06-23: Implement Phase 10C Synthetic Advisor-demo Contracts

Decision:

- Add `evaluation/synthetic_benchmarks/` as a separate Phase 10C rehearsal area with agent-visible scenario inputs, instructor-only expected sidecars, synthetic CSV fixtures, demo/full case sets, and a dedicated runner.
- Use the existing graph topology and provider-backed agent wiring; the runner generates temporary case YAML files and performs actual-vs-expected checks after graph completion.
- Add `fit_summary.json`, `synthetic_benchmark_input.json`, `synthetic_data.csv`, `demonstration_checklist.json`, `synthetic_rehearsal_summary.md`, and live-only `advisor_demo_report.md` as synthetic benchmark artifacts.
- Treat `targeted_rerun_recommended` as a structured medium-risk rerun intent and keep invalid synthetic uncertainty as severe provider-backed evidence.

Confirmed:

- Phase 10C remains synthetic-only and does not read real raw numeric data.
- Hidden expected behavior is never passed to agents and must not appear as final-report evidence.
- Mock-provider regression is network-free; live-provider rehearsal requires `RUN_LIVE_LLM_TESTS=1`.
- No `AnalysisState` fields, graph topology, status values, or dependencies changed.

Rejected Alternatives:

- Reusing the Phase 8 good/ambiguous/bad harness for advisor-demo scenarios: rejected because Phase 10C needs separate actual-vs-expected checklist and advisor report artifacts.
- Passing expected behavior into provider prompts: rejected because it would grade against leaked answers rather than agent conclusions.
- Adding a numerical dependency for the first synthetic fits: rejected because standard-library log-linear fitting is sufficient for controlled demo fixtures.

Related Documents:

- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Repository Current State](REPO_CURRENT_STATE.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)

## 2026-06-22: Initialize Independent Git Repository and Push Phase 9 Baseline

Decision:

- Initialize `/Users/chengxiaowei/Desktop/LQCD/lqcd-agent` as its own Git repository after cleanup verification and explicit user confirmation.
- Commit the cleaned Phase 9 baseline and push `main` to the user-provided GitHub remote.
- Keep all future `lqcd-agent` staging, commits, and pushes inside the `lqcd-agent` repository boundary.

Confirmed:

- The Git repository root is `/Users/chengxiaowei/Desktop/LQCD/lqcd-agent`.
- The initial baseline commit is `4d0dbac` with message `Phase 9 baseline mock agent system`.
- `origin` is `git@github.com:Xiaowei251129/lqcd-agent.git`.
- `main` tracks `origin/main`.
- The parent repository under `/Users/chengxiaowei` is not used for `lqcd-agent` commits or pushes.

Rejected Alternatives:

- Committing `lqcd-agent` through the parent repository: rejected because this project now has its own GitHub repository and repo-local generated artifact policy.
- Reusing cleanup-only documentation as current status: rejected because the repository boundary changed after explicit GitHub setup.

Related Documents:

- `docs/TICKETS.md`（已归档于 `v0.2-demo`）
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-08-10: Freeze the `v0.2-demo` Milestone Baseline

Decision:

- Treat annotated tag `v0.2-demo`, peeled to commit `e73e4d3b967008f290259851caf05f28e087cd5b`, as the immutable first-stage demo baseline.
- Move the cumulative Phase 0–10D history, verification evidence, safety boundaries, and known limitations into `milestones/V0_2_DEMO_BASELINE.md`.
- Keep `REPO_CURRENT_STATE.md` focused on the active branch, current phase, verification status, next work, and blockers.

Confirmed:

- The milestone records the `162 passed` deterministic baseline, Golden Demo, 9-case full mock benchmark, and live-provider demo evidence.
- The milestone is a reproducible research MVP snapshot, not a production-readiness claim.
- The milestone document may receive factual corrections only; second-stage progress must not rewrite it.

Rejected Alternatives:

- Continuing to append all first-stage history to `REPO_CURRENT_STATE.md`: rejected because historical accomplishments obscure the current work state.
- Treating the tag as a separate code partition or active branch: rejected because a tag is an immutable reference; second-stage work continues on a branch from that baseline.

Related Documents:

- [Milestone Baseline](milestones/V0_2_DEMO_BASELINE.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-08-10: Establish Second-stage Documentation and Ticket Governance

Decision:

- Use `docs/README.md` as the second-stage documentation index and authority map.
- Replace the first-stage monolithic execution workflow with phase folders and single-goal tickets under `docs/tickets/`.
- Permit execution only for tickets whose YAML front matter is explicitly set to `status: ready` after user confirmation.
- Create Phase A–E overview folders now, but create specific draft tickets only for Phase A control-contract discussions.
- Retain first-stage documents non-destructively and mark `CODEX_BUILD_PLAN.md`, `TICKETS.md`, and `PROMPT_PLAYBOOK.md` as Legacy.

Confirmed:

- A ready ticket cannot silently override `AGENTS.md`, security policy, or an existing public contract.
- Completed tickets are work records, not the sole source of current architecture; corresponding core documents must be updated.
- Architecture or policy changes require a Decision Log entry.
- This migration does not approve a graph edge, state field, artifact schema, RAG implementation, or Code Agent runtime.

Rejected Alternatives:

- Deleting first-stage documents during initial migration: rejected until the new system is validated and a separate cleanup ticket confirms no unique rule remains.
- Generating executable tickets for all phases immediately: rejected because Phase B–E details depend on unresolved Phase A contracts.
- Using phase Overview files as execution prompts: rejected because they intentionally describe direction rather than a bounded, verifiable change.

Related Documents:

- [Docs Index](README.md)
- [Ticket Workflow](tickets/README.md)
- [Next-stage Improvement Directions](NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md)

## 2026-08-10: Remove Superseded First-stage Legacy Documents

Decision:

- Remove `docs/CODEX_BUILD_PLAN.md`, `docs/TICKETS.md`, and `docs/PROMPT_PLAYBOOK.md` from the active worktree after completing a rule and dependency audit.
- Keep the original files recoverable through Git tag `v0.2-demo`.
- Use `docs/README.md`, `docs/tickets/README.md`, and `docs/tickets/TEMPLATE.md` as the only current documentation and ticket-governance entry points.

Confirmed:

- Project, architecture, Agent ownership, state, artifact, data/security, provider, Human Gate, evaluation, observability, verification, milestone, and current-state contracts all have dedicated current documents.
- First-stage cumulative implementation history is preserved in the milestone and Decision Log.
- Still-useful ticket rules for stale-documentation scans, graph integration, schema/dependency changes, deterministic defaults, and temporary verification outputs were migrated into the new Ticket Workflow and Template.
- No runtime code, graph edge, state field, artifact schema, configuration, test, raw data, output artifact, or milestone tag changed as part of this cleanup.

Rejected Alternatives:

- Keeping the files indefinitely with Legacy banners: rejected because their old phase prompts and route descriptions could be mistaken for current contracts.
- Copying all historical phase prompts into the new ticket tree: rejected because completed prompts are historical records, not second-stage execution inputs.
- Deleting the files before migrating unique global rules: rejected because documentation cleanup must not silently remove active safety or execution constraints.

Related Documents:

- [Docs Index](README.md)
- [Ticket Workflow](tickets/README.md)
- [Ticket Template](tickets/TEMPLATE.md)
- [Milestone Baseline](milestones/V0_2_DEMO_BASELINE.md)

## 2026-08-11: Centralize Graph-level Fallbacks in the Decision Coordinator

Decision:

- Adopt the A01 target transition contract with distributed structured diagnosis and centralized graph-level fallback control.
- Keep successful forward flow direct, while routing every re-review, analysis rerun, code fix, and replan through the Decision Coordinator.
- Allow the Coordinator to target Scientific Reviewer, Analysis Engineer, future graph-managed Code Agent, or Method Planner according to the affected layer.
- Permit automatic fallback only for low/medium risk when diagnosis is unique and the relevant finite budget remains available.
- Escalate high/critical risk, ambiguous diagnosis, repeated failure fingerprints, and budget exhaustion to the Human Gate.
- Make the Human Gate the unified clarification, approval, and external-action boundary, with all valid responses returning only to the Coordinator.

Confirmed:

- Worker Agents produce structured outcome evidence and candidate remediation but do not own graph-level fallback transitions.
- A Human Gate response authorizes only one new finite execution window, is single-use, and cannot grant unlimited looping.
- Full event logs remain available for runtime, audit, and UI, but are not injected directly into Agent prompts.
- Worker Agents receive scoped context, typed remediation, and relevant append-only attempt history; cross-Run knowledge is curated only after test or human confirmation.
- `code_agent` in A01 is a target interface placeholder. The current Codex Handoff remains unchanged until A05 and later implementation tickets define and connect the graph-managed Code Agent.
- A01 approves logical transition ownership and guards only. A02–A06 still own execution identity, artifact invalidation, pause/resume, Code Agent wire contracts, failure fingerprints, and concrete budgets.
- No runtime edge, `AnalysisState` field, artifact schema, test, configuration, raw data, or output artifact changed in A01.

Rejected Alternatives:

- Letting Analysis Engineer or Scientific Reviewer directly select code-fix, rerun, or replan targets: rejected because it fragments control authority and makes cycle budgets harder to audit.
- Letting Human Gate route directly to worker Agents: rejected because approvals and clarifications must return through the Coordinator for validation and single-use dispatch.
- Defaulting ambiguous failures to the deepest Method Planner rollback: rejected because it invalidates more evidence without a unique diagnosis.
- Giving every Agent the complete event log or autonomous writable long-term memory: rejected because it weakens role boundaries, introduces stale context, and allows unreviewed experience to affect policy.
- Making every fallback require human approval: rejected because bounded low/medium remediation should remain automatable when deterministic guards are satisfied.

Related Documents:

- [A01 Transition Matrix](tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md)
- [Architecture](ARCHITECTURE.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [Repository Current State](REPO_CURRENT_STATE.md)
