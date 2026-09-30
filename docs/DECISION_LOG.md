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

## 2026-08-11: Adopt Run, Cycle, and Attempt Identity and Correct A02 Execution Scope

Decision:

- Use a three-level Run / Cycle / Attempt model instead of a two-level Run / Attempt model.
- Keep `run_id` as the complete user research-task identity and owner of the canonical output root and checkpoint thread.
- Treat Cycle as a method-contract epoch created only for initial execution or Coordinator-approved replan.
- Treat Attempt as one durable graph node invocation, using a shared identity envelope across worker Agents, Decision Coordinator, Human Gate, and Memory Report.
- Allocate Attempt identity during Run bootstrap or transition commit, before the target node performs side effects.
- Keep re-review, analysis rerun, and code fix in the same Run/Cycle with new Attempts; create a new Cycle for replan and a new parent-linked Run for replay/fork or root input identity changes.
- Separate canonical Attempt kind from physical node name. Map the current physical `codex_handoff` to `legacy_codex_handoff`; reserve `code_agent` for A05/Phase B.
- Give Human Request and Human Response independent deterministic identities and append-only lifecycle records; they are not Human Gate Attempts.

Confirmed:

- `START` is not an Attempt, and human request/response records use separate single-use identities linked to the Attempts that request, validate, and consume them.
- Parent Run/Cycle/Attempt identifiers express control lineage; typed remediation, evidence, and artifact references express data provenance.
- State retains bounded current identity pointers, allocation counters, and active control references; complete execution history remains append-only and is not injected directly into Agent prompts.
- The Run-owned `checkpoint_thread_id` remains stable across Cycle, Attempt, and pause/resume; Cycle and Attempt do not create checkpoint threads.
- Technical recovery may keep an Attempt only for the same checkpoint before semantic failure and with idempotent side effects. Every semantic retry or human-approved execution window creates a new Attempt.

Current Implementation Boundary:

- The initial design-only completion was invalidated and A02 was reopened as an implementation ticket after user correction. The corrective runtime, schema, graph, Human identity, tests, and source-of-truth verification are now complete; the ticket records the replacement completion evidence.
- A formal, unique Run creation record now precedes initial Cycle creation, Planner Attempt scheduling, and the committed START Transition in `execution_history.jsonl`.
- Current product-route source wrappers finish the pre-scheduled source Attempt, call a pure selector, and commit a Transition that preallocates the target Attempt. Conditional edge readers consume only `committed_route`; fixed and END routes use the same commit protocol.
- `AnalysisState` now carries bounded current Cycle/Attempt/Transition and Human pointers/counters. The append-only ledger records Run, Cycle, Attempt, Transition, Human Request, and Human Response lifecycle events.
- Human Gate packets and responses are identity-bound. A Gate Attempt validates a submitted response, and an authorized compatibility transition consumes it once while recording validator, consumer, and target lineage.
- Legacy incomplete-Run re-entry validates immutable Run identity and restores counters so it cannot reuse IDs. This is compatibility audit continuity, not A04 checkpoint resume.
- Re-review, analysis rerun, code fix, and replan pass through a minimal deterministic StateGraph identity harness only. Those tests do not open the A01 product fallback edges; the harness `code_agent` target is a protocol sink, not an implemented Agent.

Deferred:

- A03 owns per-attempt domain-artifact namespaces, current pointers, versioning, and invalidation.
- A04 owns durable PAUSE/resume, checkpoint recovery, and public replay/fork APIs.
- A05 owns Fake/real graph-managed Code Agent behavior, sandboxing, and diagnostic outcome contracts.
- A06 owns concrete budgets, failure fingerprints, repeated-failure policy, and human-granted finite windows.
- A07/Phase B owns the complete A01 target-route and forbidden-route product harness. A02 does not change the current compatibility topology.

Rejected Alternatives:

- A two-level Run / Attempt model: rejected because it cannot represent method-plan epochs and deterministic replan invalidation without reconstructing semantics from history.
- Agent-created Attempt identifiers: rejected because identity must exist before side effects and remain under graph control.
- A checkpoint thread per Cycle or Attempt: rejected because pause/resume belongs to the stable Run and thread proliferation would confuse product identity with checkpoint implementation details.
- Reusing a failed Attempt for semantic retry: rejected because it overwrites provenance and can bypass retry budgets.
- Storing the complete Attempt history in every Agent context: rejected because it weakens scoped responsibility and creates unbounded stale context.

Related Documents:

- [A02 Run/Cycle/Attempt Model](tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md)
- [Architecture](ARCHITECTURE.md)
- [State Schema](STATE_SCHEMA.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-08-11: Make Attempt Artifacts Immutable and Current Selection Explicit

Decision:

- Store every graph-managed domain bundle under `<run_root>/attempts/<attempt_id>/` and identify it as `<attempt_id>:<slot>`.
- Use append-only `artifact_history.jsonl` for audit and atomically replaced `artifact_index.json` as the only normal current-selection authority.
- Fix current slots as `plan`, `code`, `analysis`, `review`, `decision`, `approval`, and `terminal`; keep bounded state paths synchronized with the typed index.
- Clear the target layer and all downstream current slots during Transition commit, after target Attempt allocation and before target-node side effects.
- Preserve v0.2 run-root fixed paths as registry-owned copy projections, not canonical history; refuse to manage legacy output trees without an A03 index.
- Store Human Response payloads under versioned `human_responses/<human_response_id>/` snapshots and append protection events for accepted terminal bundles.
- Allow benchmark code-fix checks to read invalidated analysis evidence only through validated artifact history, never by restoring a stale current pointer.

Confirmed:

- Invalidation removes current pointers and owned projections but never deletes canonical Attempt members, artifact history, Human Response snapshots, or accepted-result evidence.
- Each registered artifact event freezes its complete typed pointer and cross-checks the producing Attempt against the execution ledger. Registry validation replays current-set/current-cleared events and requires the replayed current map to exactly match the mutable index before restoration or use.
- Producing Attempt identity is the exact six-field Run, Case, Cycle, Attempt, Kind, and Node tuple. Missing or inconsistent fields in either the registered event or execution ledger fail closed.
- The managed projection owner map is derived uniquely from replayed current members and must exactly match the index. Escaping, protected/control, duplicate, extra, missing, unknown-owner, or wrong-owner entries fail closed.
- External code-result and Human-decision ingress may differ from canonical bytes, but this exception skips only projection digest comparison and never path or owner validation.
- Each ordinary registration is immediately followed by its only current-set event. Once cleared, the same artifact cannot become current again.
- Replay recomputes the registration-time dependency chain from current slots, and ordinary members must remain inside the producing Attempt with canonical, logical, and projection paths in exact correspondence.
- Projection publication preflights the complete bundle before copying. Ownership collisions fail without changing history, index, or existing projection bytes; external ingress exemptions still require the owned projection to exist.
- Every current-clear is bound to the exact target Attempt and its unique committed inbound Transition, including Run, Case, Cycle, Attempt, Kind, Node, transition identity, reason, and target-slot policy.
- Human Response protection is bound to one submitted ledger record and its exact response/request identity, canonical snapshot path, and digest. Accepted-result protection is valid only for the current accepted terminal pointer; unsupported protection requests fail before any history write.
- Initialization may hydrate only an explicitly empty reconstructed artifact state. A populated state must validate exactly and is never silently repaired from the index; duplicate JSON object keys in registry or execution ledgers fail closed.
- Replay completeness is bidirectional: scheduled Attempt inputs plus target policy derive the exact required clear set; finished Attempt outputs derive required registrations; submitted Human Responses and accepted terminals derive required protections. Validating only events that remain in history is insufficient because coordinated deletion could otherwise produce a self-consistent but incomplete head.
- Every committed Transition with a target reverse-requires that target's exact Attempt lifecycle, and populated current-Attempt state must equal the latest lifecycle record. Removing a target lifecycle together with its artifact cannot turn the Transition into a valid incomplete history.
- Human Response lifecycle identity is stable and ordered across submitted, validated or invalid, and optional consumed records. Populated active-response state reverse-requires the matching latest ledger record and immutable snapshot protection; the only exception is the bounded preflight inside initial snapshot publication.
- The write path permits narrowly scoped preflight incompleteness only for the target Attempt currently entering invalidation and the producing terminal Attempt currently adding accepted protection. Normal reads, restoration, and state persistence always require the complete reverse-derived event set.
- Initial and legacy incomplete-Run Planner scheduling use the same A03 invalidation entry point as ordinary committed Transitions.
- Failed or pending target Attempts do not restore the previous current chain.
- Fixed-path handoff/Human files remain explicit compatibility ingress; graph outputs and consumed evidence are canonicalized in producing bundles or protected snapshots.
- Four-layer re-review, analysis-rerun, code-fix, and replan tests are fallback infrastructure harnesses only. A03 does not open A01 product routes.
- A04 still owns cross-process crash recovery, durable resume, replay/fork, and partial-commit repair; A05 owns the graph-managed Code Agent bundle; A06 owns budgets and failure fingerprints.

Rejected Alternatives:

- Versioned filenames in the Run root: rejected because Attempt identity already supplies a deterministic namespace and root filenames remain compatibility projections.
- Selecting current artifacts by directory scan, timestamp, mtime, or filename suffix: rejected because these methods cannot provide typed dependency or invalidation guarantees.
- Symlink-based compatibility projections: rejected because moved or packaged output trees would break the public contract.
- Restoring an invalidated failed-analysis pointer to satisfy legacy benchmarks: rejected because historical evidence and current validity are different semantics.
- Automatically migrating unmanaged v0.2 output trees: rejected because ownership cannot be proven safely.

Related Documents:

- [A03 Artifact Invalidation](tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md)
- [Architecture](ARCHITECTURE.md)
- [State Schema](STATE_SCHEMA.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)

## 2026-08-22: Freeze Ready Tickets and Separate Execution Records

Decision:

- Treat the body of a user-approved `status: ready` ticket as an immutable execution contract.
- Permit later changes only to YAML lifecycle metadata; do not append completion evidence or corrective requirements to the frozen body.
- Store actual execution results in `docs/tickets/completions/` and contract-preserving maintenance history in `docs/tickets/corrections/`.
- Require a separately reviewed and approved corrective ticket whenever a fix changes schema, architecture, public contract, Allowed Files, recovery policy, or acceptance boundaries.

Confirmed:

- A01 and A02 retain their historical embedded Completion Records and are not rewritten retroactively.
- A03's initial completion evidence and six pre-governance corrective passes are preserved in separate records. The detailed A03 implementation ticket was not committed before execution, so the repository does not claim that an uncommitted intermediate version can be reconstructed exactly.
- Future execution should commit the frozen ticket before implementation when authorized. If no commit is created, the completion record must disclose that limitation.

Rejected Alternatives:

- Continuing to append corrective passes to the original ticket: rejected because it obscures the approved plan and weakens scope auditing.
- Rewriting A01 and A02 into the new format: rejected because they are complete and have no known issue requiring historical surgery.
- Treating a large integrity-policy change as an undocumented bug fix: rejected because the changed contract must be independently reviewable.

Related Documents:

- [Ticket Workflow](tickets/README.md)
- [Ticket Template](tickets/TEMPLATE.md)
- [Completion Records](tickets/completions/README.md)
- [Correction Records](tickets/corrections/README.md)
- [G01 Governance Ticket](tickets/G01_TICKET_RECORD_IMMUTABILITY.md)

## 2026-08-22: Bind the Artifact Registry to Execution Ledger Heads

Decision:

- Require A03 registry validation to bind bounded state to the Run-local global heads of Cycle, Attempt, Transition, Human Request, and Human Response records.
- Require deterministic IDs and positive indexes to be unique and contiguous from 1 through the current maximum for each execution identity type.
- Treat Transition target shape as an integrity boundary: only terminal `end`/`__end__` routes may have an explicitly present null target tuple, while every nonterminal route must retain a complete target tuple that exactly matches its target Attempt. A missing nullable identity field is not equivalent to an explicit null.

Confirmed:

- A locally valid old Attempt or Human Response lifecycle is not a valid current state when a newer ledger identity exists.
- The active Human Response is the maximum response index associated with the latest Human Request; the global response counter cannot roll back across requests or retries.
- Human Request lifecycle validation preserves the existing optional `packet_written` event between creation and satisfaction.
- Initial Human Response snapshot publication retains one narrow preflight for the deterministic next response identity with empty outcome fields. Normal restoration, reads, and state persistence do not receive that exception.
- Coordinated deletion of a target Attempt/artifact plus state rollback and conversion of a nonterminal Transition to a null target fails closed.
- This correction does not change artifact schema `0.1`, execution schema `0.2`, `AnalysisState`, graph topology, provider behavior, Human approval policy, or A04 recovery boundaries.

Rejected Alternatives:

- Accepting any state identity that has an internally valid lifecycle: rejected because it permits rollback from the actual ledger head.
- Treating a null target as terminal without checking the route and all target fields: rejected because a nonterminal transition could be rewritten into an apparently self-consistent truncated history.
- Repairing or migrating inconsistent experimental registries automatically: rejected because ownership and current-head intent cannot be recovered safely.

Related Documents:

- [A03C01 Execution Head Integrity](tickets/phase-a-control-contracts/A03C01_EXECUTION_HEAD_INTEGRITY.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Repository Current State](REPO_CURRENT_STATE.md)

## 2026-08-26: Resolve Cross-contract Gaps Before Freezing Phase A

Decision:

- Keep A01–A03 completed ticket bodies immutable and use separate correction/corrective records for later clarification or schema-versioned supersession.
- Add A02C01 as the schema `0.4+` bootstrap corrective contract so policy initialization and admission evidence precede initial Cycle, Planner Attempt, and START Transition creation.
- Standardize composite Transition publication as optional Human Request creation, scheduled target allocation, A03 target invalidation, committed Transition append, head validation, and only then target start.
- Separate the authoritative control `run_status = running | paused | completed | failed | halted` from the existing domain/workflow `status`; a pending report may terminate with `run_status = completed` and is never a resumable lifecycle state.
- Publish a replacement Human-input Pause after an invalid response only through budget decision, old Pause consumption, checkpoint persistence, and new Pause opened; insufficient terminal-tail capacity halts without opening another Pause.
- Treat Python Codex SDK as a conditional preferred backend that must pass an independent Phase C C00 capability gate; preserve a Host-owned producer operation identity and provider-independent `CodingBackend` port.
- Add a tracked Phase B requirement catalog with stable IDs for every A01 route/forbidden behavior, A02C01 bootstrap requirement, and A04–A06 required scenario; future acceptance matrices must cover the required ID set exactly and bind the catalog byte digest.

Confirmed:

- A02 schema `0.2` runtime and historical bootstrap bytes are unchanged. A02C01 applies only to schema `0.4+` and allows deterministic continuation only for an exact, side-effect-free bootstrap prefix.
- A03's phrase “Transition commit” denotes entry into the composite control operation, not that the committed Transition record is appended before invalidation.
- Partial allocation, invalidation, Transition, Pause publication, grant, settlement, or bootstrap sequences remain fail closed and do not gain general automatic repair authority.
- A04–A07 and A02C01 remain `review` target contracts until their final text, companion catalog, links, and frozen Git snapshots are confirmed. None of these decisions claims that the current runtime already implements schema `0.4`, durable resume, Code Agent, budgets, or the Phase B product graph.
- Phase B remains deterministic and Fake-backed. Phase C starts with `C00_CODEX_SDK_BACKEND_FEASIBILITY`; a failed capability gate requires a new backend-selection design rather than weakening audit, cancellation, workspace, result, or recovery contracts.

Rejected Alternatives:

- Exempting bootstrap from budget admission: rejected because it would leave the initial Cycle, Attempt, and Transition outside the authoritative accounting contract.
- Rewriting completed A02/A03 bodies: rejected because correction and corrective-ticket governance preserves the approved historical contract.
- Appending the Transition record before A03 invalidation: rejected because it conflicts with target preallocation, current implementation, and cross-head validation.
- Treating domain `pending` as neither terminal nor resumable: rejected because it creates an unreachable lifecycle dead end after a valid report.
- Free-form acceptance `contract_refs`: rejected because a validator cannot prove zero-gap or stale coverage from prose labels.
- Locking Codex SDK before verifying durable lookup, exact cancellation, tool audit, workspace containment, immutable result extraction, and restart behavior: rejected because documented thread and sandbox support does not prove the stronger A05 backend contract.

Related Documents:

- [A02C01 Execution 0.4 Bootstrap Order](tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [A03 Transition Publication-order Clarification](tickets/corrections/A03_TRANSITION_PUBLICATION_ORDER_CLARIFICATION.md)
- [A04 Pause and Resume Semantics](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [A07 Phase B Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)
- [Phase B Requirement Catalog](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)

## 2026-08-27: Make the Phase A Control Protocol a Single Machine-readable Authority

Decision:

- Add tracked `CONTROL_PROTOCOL_0_4.json` as the only machine-readable enumeration of ControlOperation type/variant phases and success edges, phase authority/evidence/ownership contracts, ExternalOperation normal/cancellation edges and statuses, Pause and Run lifecycle edges, control outcome classes, pre-start dependency order, field binding, cross-machine invariants and schema compatibility.
- Keep explanatory prose in A02C01 and A04–A07, but remove duplicate exact phase graphs from A02C01, A04 and A05. Prose may explain semantics and evidence but cannot add a type, variant, phase, edge or exception that is absent from the protocol.
- Add a Python-standard-library design-time validator that rejects duplicate JSON keys, incomplete type/variant sets, unreachable or nonterminating phases, hidden cycles, non-atomic combined ownership, nonterminal cancellation proof, circular construction, field binding before allocation, catalog/prose ID drift, stale protocol digest and missing protocol references.
- Bind the exact protocol SHA-256 into the requirement catalog and require the future Phase B acceptance matrix and completion evidence to bind both protocol and catalog digests.
- Keep the only intentional lifecycle cycle explicit as `running <-> paused`, guarded by a new Pause identity, a new ControlOperation identity and budget admission or terminal reserve. ControlOperation, ExternalOperation and construction success graphs remain acyclic.
- Remove the stale prose-only `paused -> completed` lifecycle edge. Normal completion requires a committed `memory_report -> END` while the Run is running; a paused Run has no executor that can produce that trigger and may only resume or close as halted/failed.
- Keep `REPO_CURRENT_STATE.md` limited to the latest verified facts. Historical catalog counts and digests remain recoverable from Git and this log instead of appearing beside current evidence. The superseded 2026-08-26 review snapshot had 80 required catalog entries and SHA-256 `f66a96f9c488c3f9571e398b8381b2d037bd32f56dc7b3a951717e10fda2ceac`.

Confirmed:

- This is a pre-freeze specification-engineering correction, not a runtime, test, graph, provider or Phase B implementation change.
- Coordinator remains the sole product route and mutation authority; LangGraph continues to own graph execution and checkpoint mechanics only.
- A01–A03, A03C01 and their completion/correction history remain frozen. A02C01 and A04–A07 remain `review`.
- B00 must consume the frozen protocol rather than re-derive a state machine from Markdown, and must convert the same validations into collectable acceptance tests and exact traces.

Rejected Alternatives:

- Keeping exact phase lists independently in A02C01, A04, A05, A07 and implementation code: rejected because local edits repeatedly created cross-document drift and stale audits.
- Treating every graph cycle as invalid: rejected because Pause/resume is an intentional product lifecycle cycle, but it must carry explicit monotonic identity and budget guards.
- Copying TradingAgents' application-level checkpoint design as the control authority: rejected because explicit conditional path maps and graph fingerprints are useful patterns, but node checkpoints do not provide mutation idempotency, fencing, external-operation cancellation or Run terminal closure ownership.

Related Documents:

- [Control Protocol 0.4](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)
- [Protocol Validator](../scripts/validate_phase_a_control_protocol.py)
- [A02C01 Execution 0.4 Bootstrap Order](tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [A04 Pause and Resume Semantics](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [A07 Phase B Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)
- [Phase B Requirement Catalog](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)

## 2026-08-26: Add a Durable Control-operation Coordinator and Exact Termination Boundary

Decision:

- Add `ControlOperation 0.1` as the durable authority for public mutation idempotency, ownership, monotonic phase, worker lease, and result replay.
- Place the Phase B SQLite reference coordinator at `<output_root>/.lqcd/control_operations.sqlite`, outside every per-Run root and separate from LangGraph checkpoint databases.
- Require `start_run` to reserve the idempotency key, operation identity, and target Run locator in one single-writer transaction before creating policy, Run-root, ledger, or checkpoint bytes.
- Reuse the same coordinator for `resume_run`, `replay_run`, `fork_run`, and `cancel_pause`; a Pause claim is owned by one stable operation even if its processing worker lease expires.
- Keep four state dimensions orthogonal: operation status/phase, Run `run_status`, Pause lifecycle, and domain/workflow `status`.
- Require a local real backend to cancel the exact complete process tree through graceful termination, a bounded grace period, forced termination of survivors, bounded output-reader shutdown, write-lease revocation, and post-stop activity checks.
- Preserve A04 terminal semantics: a successfully enforced policy/security/operator stop is `halted`; unverified heads/counters, termination failure, lease-revocation failure, or post-stop activity is a control/runtime failure with `run_status = failed`.

Confirmed:

- `execution_history.jsonl` remains the append-only authority for Run history after Run creation. The coordinator owns mutation admission and processing ownership; LangGraph checkpoints own graph recovery state; immutable artifacts and manifests own scientific result bytes.
- Cross-store phases must exact-match, but no store may silently become a second mutable authority for another store's facts.
- Only the original same-key/same-digest operation may materialize a precomputed side-effect-free record after a crash. A worker lease never authorizes a second operation or replay of an uncertain external effect.
- OpenAI Codex source at comparative review commit `7c3747941a6b664c30f1e6aa72a917fd74dc22d2` and local CLI `0.134.0` informed the transaction, event projection, exact interrupt, and process-tree termination design. This is implementation evidence, not a normative dependency or a passed C00 capability result.
- Phase B must verify SQLite transaction/claim behavior with independent processes and deterministic failpoints. Phase C must pin and black-box test the actual SDK/CLI/app-server build rather than infer capabilities from a moving source branch.

Rejected Alternatives:

- Recording the idempotency key first inside the new Run ledger: rejected because the ledger does not exist before the first Run-root mutation.
- Reusing the LangGraph checkpoint database as the operation journal: rejected because checkpoint recovery and public mutation ownership have different authority and lifecycle boundaries.
- Letting an expired worker lease release a Pause claim: rejected because it could create two consumers for one recovery window.
- Treating provider thread/job identity as the product operation identity: rejected because provider identity may be absent, unstable, or backend-specific.
- Marking failed cancellation or post-stop activity as a normal `halted` outcome: rejected because it hides loss of runtime containment.
- Automatically repairing malformed control-ledger tails: rejected because audit integrity must fail closed when exact bytes and heads cannot be proven.

Related Documents:

- [A02C01 Execution 0.4 Bootstrap Order](tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [A04 Pause and Resume Semantics](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [A07 Phase B Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)

## 2026-08-27: Close Operation Recovery, External Bootstrap, and Terminal Publication Contracts

Decision:

- Make `ControlOperation.recovery_required` an irreversible terminal tombstone. Exact, precomputed, side-effect-free publication prefixes remain `in_progress/materialization_pending` and may be materialized only by the same operation under the current fenced lease epoch.
- Freeze operation-specific phase graphs for `publish_pause`, `resume_run`, `cancel_pause`, `replay_run`, `fork_run`, and `close_run`, while retaining A02C01's existing `start_run` phases.
- Remove the ExternalOperation construction cycle by reserving producer/workspace identity and initial epoch first, then publishing task, unmaterialized WorkspaceManifest, aggregate reservation, immutable core, and finally the physical workspace.
- Require normal END, ordinary runtime failure, confirmed stop, and uncloseable integrity failure to follow the authoritative terminal publication protocol. Standalone closure uses `close_run`; `cancel_pause` embeds the same terminal tail under its existing unique ownership.
- Define the version boundary explicitly: schema `0.2` retains its legacy creation bytes, schema `0.3` is the A04 Pause semantic predecessor, and the Phase B `0.4` runtime performs no in-place resume or migration of older Runs.
- Keep A02C01 classified as the repository-supported `corrective-implementation` ticket type even though the present review changes only design contracts and does not implement runtime.

Confirmed:

- Coordinator remains the sole product routing and fallback authority; canonical Code Agent non-success outcomes still return to Coordinator, while invalid ingress remains outside the graph.
- A01–A03 and A03C01 frozen bodies and their completion/correction histories are unchanged.
- Materializing already authorized canonical bytes is not a new route decision, grant consumption, domain action, or general partial-commit repair.
- `failed`, `halted`, terminal `recovery_required`, and nonterminal `in_progress/materialization_pending` are mutually exclusive outcomes.
- A02C01 and A04–A07 remain `review`; this decision does not create Phase B tickets or claim runtime support.

Rejected Alternatives:

- Letting `recovery_required` both continue automatically and act as a terminal operator-recovery state: rejected because operation replay and acceptance traces would be ambiguous.
- Creating Task, WorkspaceManifest, or workspace bytes before a durable producer identity and epoch exist: rejected because ownership and stale-writer fencing would be circular.
- Treating graph END, an exception, or bounded terminal state as sufficient Run closure: rejected because lifecycle, checkpoint, and public result could diverge after a crash.
- Reinterpreting legacy `status: running` as schema `0.4` `run_status: initializing`: rejected because it would silently migrate immutable historical bytes.

Related Documents:

- [A02C01 Execution 0.4 Bootstrap Order](tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [A04 Pause and Resume Semantics](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [A07 Phase B Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)
- [Phase B Requirement Catalog](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)

## 2026-08-27: Make Control Branches Exhaustive and Run Closure Single-owner

Decision:

- Replace prose exceptions to a linear ControlOperation phase list with type/variant-specific exhaustive allowed-edge graphs. `resume_run` freezes `continue_execution | abandon_and_halt` at reservation; only the continue branch enters `running`, while abandon owns and completes an embedded terminal tail.
- Require cancel and abandon to atomically acquire their Pause ownership and the Run terminal closure ownership in one coordinator transaction represented by one combined-ownership phase. There is no durable state in which one of those two owners has changed and the other has not.
- Give every Run a single-assignment terminal closure owner, monotonic closure revision and deterministic trigger-bound request identity. Ownership fences stale invocation capabilities and non-owner Run writes. Normal END, ordinary failure, budget/policy/operator stop and invalid-response capacity stop use `close_run`; cancel and abandon use the same ownership and eligibility contract in their embedded tails.
- Treat `termination_evidence_committed` as a nonterminal cancellation observation. Pause cancellation accepts exactly one final ExternalOperation proof: active/non-dispatched cancellation uses `cancellation_evidence_committed`; an operation already normal-terminal before Pause cancellation keeps its immutable `terminal_evidence_committed`. Both require termination, write-lease revocation, containment verify-empty, bounded drain and post-stop stability.
- Separate ControlOperation failure from authoritative Run closure. If Run authority is intact and appendable, the owner can publish `run_status: failed`; if the authority itself cannot be verified or appended, the operation reports `terminal_closure: unavailable` and must not fabricate a failed lifecycle.
- Freeze cancel disposition and pre-close resolution contracts before side effects, then resolve final disposition and heads exactly once from terminal cancellation/settlement evidence. Freeze Pause compatibility against the source Run's actual execution schema, and assign B02 explicit ownership of `close_run` plus the combined-ownership/fencing protocol. B00 must statically reject unreachable, unterminated, cross-variant, skipped, half-ownership or terminal-owner-pending phase paths.

Confirmed:

- This is a medium contract closure within the existing Coordinator/control-plane architecture. It does not change A01 routing, grant product-route authority to LangGraph, create Phase B tickets, or implement runtime.
- A01–A03, A03C01 and their existing completion/correction history remain frozen. A02C01 and A04–A07 remain `review` pending an independent cross-audit and final confirmation.
- TradingAgents' explicit LangGraph conditional-edge maps and graph-construction checks at comparative source commit `a33fd4c0f134485a43553a2c23a63cb14adbd88f` support making branch coverage executable. Its application-level graph pattern does not replace this project's stronger coordinator, fencing, durability, cancellation or authority contracts.
- OpenAI Codex invocation-lifetime capabilities, typed approval identities and bounded process cleanup remain design references rather than normative dependencies or evidence that a production backend has passed C00.

Rejected Alternatives:

- Keeping a mandatory linear resume path with a prose-only abandon exception: rejected because a validator and implementation cannot derive one legal trajectory.
- Acquiring Pause ownership and terminal closure ownership in separate committed phases: rejected because a competing close can strand a half-owned Pause or terminal Run.
- Letting termination observation close an ExternalOperation or Pause: rejected because termination alone does not prove lease revocation, containment emptiness or post-stop stability.
- Mapping every control-integrity failure to `run_status: failed`: rejected because a corrupted authoritative head may make an append-only failed lifecycle impossible.
- Appending `halted` directly from END, capacity, policy or operator code and constructing a close operation afterward: rejected because restart and competing triggers can create duplicate terminal publication.

Related Documents:

- [A02C01 Execution 0.4 Bootstrap Order](tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [A04 Pause and Resume Semantics](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [A07 Phase B Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)
- [Phase B Requirement Catalog](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)

## 2026-08-27: Linearize External Resolution and Quarantine Unprovable Stops

Decision:

- Place ControlOperation rows, Pause ownership, Run terminal ownership and ExternalOperation rows in one physical `coordinator_sqlite` transaction domain. Their logical authorities and lease epochs remain distinct, but cancel arbitration does not cross a database boundary.
- Replace the earlier cancel sequence with one `cancel_arbitrated` transaction. It CAS-compares the exact Pause/opened head, empty Pause and Run owners, and ExternalOperation identity, phase revision, lease epoch and empty resolution owner before recording `cancel_won`, `normal_terminal_won`, `preexisting_stop_resolution` or `no_external_operation`.
- Make `normal`, `cancel` and `interrupt` one-time ExternalOperation resolution owners. Normal terminal and cancel/interrupt intent CAS operations use the same empty-owner predicate; the first commit wins and every later writer can only follow the winner's persisted path.
- Converge all ExternalOperation resolutions on the single terminal phase `external_final_evidence_committed`. A complete stop proof is `safe_stop`; missing termination, write-lease revocation, containment, bounded-drain or post-stop proof is `unavailable` and maps to `recovery_required`.
- Add terminal Pause state `quarantined`. An unavailable ExternalOperation proof quarantines the Pause and records the already-owned Run terminal closure as unavailable without appending a fabricated `halted` or `failed` lifecycle.
- Add an exact `operation_reserved` evidence overlay for each of the eight ControlOperation type/variant combinations. The effective reservation contract is the shared phase contract plus its one variant overlay; missing or conflicting evidence is invalid.
- Upgrade the Control Protocol machine schema to `0.2` and the requirement catalog content version to `0.2.0`. Keep execution schema and protocol version at `0.4`.

Confirmed:

- Coordinator remains the only product route and fallback authority. LangGraph remains responsible only for graph execution, checkpoint and interrupt behavior.
- Provider cancellation occurs only after local cancel intent commits and never redispatches work. A watchdog takeover monitors, cancels or recovers the original producer operation under a newer fenced lease epoch.
- A `quarantined` Pause is never resumable, claimable, consumable, cancellable or reopenable. `recovery_required` is terminal and cannot advance another phase.
- The revised design changes control-plane protocol closure, not A01 routing or the frozen A01–A03/A03C01 contracts. A02C01 and A04–A07 remain in review and no Phase B ticket or runtime implementation is created.
- TradingAgents remains useful as a reference for explicit graph branches and construction checks, but it does not provide the durable multi-authority arbitration required here.

Rejected Alternatives:

- Acquiring Pause and Run owners before deciding ExternalOperation resolution: rejected because normal completion can win between the two decisions and leave no legal proof path.
- Allowing a nonterminal ExternalOperation phase to carry a terminal status: rejected because the state cannot be resumed or consumed by a total terminal-proof union.
- Publishing `run_status: failed` when containment or stop completion is unprovable: rejected because uncertainty is not proof of a failed authoritative lifecycle and may coexist with continuing side effects.
- Using one generic `operation_reserved` evidence list for every variant: rejected because B00 could validate a request while omitting the exact policy, Pause head, source revision or closure key needed for idempotency and fencing.

Related Documents:

- [Control Protocol 0.4](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)
- [Protocol Validator](../scripts/validate_phase_a_control_protocol.py)
- [A02C01 Execution 0.4 Bootstrap Order](tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [A04 Pause and Resume Semantics](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [A07 Phase B Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)
- [Phase B Requirement Catalog](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)

## 2026-08-27: Give External Interrupts an Independent Guarded Closure

Decision:

- Add internal `resolve_external_interrupt` variants `recoverable_timeout`, `controlled_halt` and `integrity_failure`. Interrupt resolution no longer depends on phases that exist only in `cancel_pause`.
- A safe Backend operation timeout consumes the exact opened `external_result` Pause, forms a canonical failed Code Agent outcome and returns graph execution to Coordinator. Safe hard-limit, policy and terminal operator stops close the Run. Safely contained, proven integrity violations may publish `run_status: failed` only when Run authority remains appendable.
- Treat any false or unknown termination, write-lease revocation, containment emptiness, bounded drain or post-stop stability dimension as `recovery_required` with an unavailable Run closure. Appendability of the Run ledger does not turn missing stop proof into a failed lifecycle.
- Model Pause snapshots as `absent | prepared | opened`. Safe terminal interrupt maps them to N/A, `aborted` or `interrupted`; unavailable proof maps prepared/opened to `quarantined` and absent to N/A. All terminal Pause states are irreversible.
- Make cancel branching explicit. A preexisting interrupt winner yields `resolution_winner_observed` and no cancel Pause/Run ownership. Typed-null cancellation uses a `PauseCancelProof/no_external_operation` variant and never invents ExternalOperation final evidence.
- Upgrade the Control Protocol machine schema to `0.3` and catalog content version to `0.3.0`. Every multi-successor phase has a finite disjoint exhaustive guard, and polymorphic proof fields use tagged evidence unions whose incoming-edge bindings are validated.

Confirmed:

- Coordinator remains the sole product route, fallback and terminal-closure authority. LangGraph remains limited to graph execution, checkpoint and interrupt mechanics.
- Backend dispatch remains after public Pause publication. A pre-Pause ordinary operation timeout is invalid; a pre-Pause hard-limit or policy stop uses a terminal interrupt variant with typed `not_dispatched` evidence.
- This is a Phase A review-contract correction only. It does not alter frozen A01–A03/A03C01 content, create Phase B tickets or implement runtime.

Rejected Alternatives:

- Letting timeout or hard-limit callbacks call `cancel_pause`: rejected because system stop may occur without an operator cancel request and cancellation ownership semantics do not represent recoverable timeout.
- Allowing cancel to acquire Pause/Run owners after observing an interrupt winner: rejected because it creates two consumers for one ExternalOperation final proof.
- Mapping post-stop activity or missing containment evidence to appendable `run_status: failed`: rejected because ongoing or unproved side effects make authoritative closure unavailable, not proven failed.
- Leaving branch selection in prose: rejected because B00 cannot prove guard coverage, evidence shape or a unique successor from an allowed-edge list alone.

Related Documents:

- [Control Protocol 0.4](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)
- [Protocol Validator](../scripts/validate_phase_a_control_protocol.py)
- [A04 Pause and Resume Semantics](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [A07 Phase B Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)
- [Phase B Requirement Catalog](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)

## 2026-08-27: Close Winner Observation and Make Stop Routing Unique

Decision:

- Make `cancel_arbitrated` ownership outcome-conditioned. Typed-null, cancel-won and normal-won require empty Pause and Run owners and may acquire them; preexisting cancel and interrupt winners use a read-only observation guard that accepts exact winner-owned state, verifies winner operation/revision/epoch coherence and mutates no domain owner.
- Distinguish same-key replay from observing another winner. Same-key replay resumes the existing ControlOperation; a different cancel operation can only return the persisted winner identity, resolution revision and current state.
- Classify normal final proof before the resolution CAS. `external_normal_terminal_cas` accepts only preclassified `safe_stop` and atomically publishes normal final evidence. A false, unknown or missing proof dimension deterministically creates or reuses `resolve_external_interrupt/integrity_failure` with reason `normal_finalization_unavailable`; `normal + unavailable` is not a legal terminal tuple.
- Add one machine-readable stop-route authority selected before operation reservation. Explicit Pause cancellation uses `cancel_pause`; dispatched operation timeout uses recoverable interrupt; live-operation hard-limit, policy or terminal operator stop uses controlled-halt interrupt; integrity or unavailable normal finalization uses integrity interrupt; `close_run` is legal only when ExternalOperation is absent or safely terminal and detached.
- Require `close_run` reservation to freeze the ExternalOperation precondition and proof digest. An interrupt terminal owner excludes a later `close_run`, so one trigger cannot produce two terminal operations.
- Upgrade the Control Protocol machine schema to `0.4` and the requirement catalog content version to `0.4.0`. Extend the design validator from graph adjacency to composite resolution/Pause/Run owner states and exact stop-route mutations.

Confirmed:

- This closes two protocol-model gaps: a phantom winner-observation edge blocked by unconditional empty-owner guards, and an unowned `normal_resolution_recovery` string outside any ControlOperation graph.
- Coordinator remains the sole product route and terminal authority. LangGraph remains responsible only for graph execution, checkpoints and interrupts.
- A01 routing and frozen A01–A03/A03C01 content remain unchanged. A02C01 and A04–A07 remain in review; no Phase B ticket or runtime implementation is created.

Rejected Alternatives:

- Requiring empty Pause and Run owners for every cancel outcome: rejected because an interrupt or prior cancel winner may already own those fields, making the declared observation edge unreachable.
- Letting normal resolution commit before stop-proof classification: rejected because unavailable evidence would then require a second owner or an unowned recovery flow.
- Treating prose as stop-route authority: rejected because B00 could choose `cancel_pause`, `resolve_external_interrupt` or `close_run` differently for the same trigger and still pass a graph-only validator.
- Creating `close_run` after an interrupt tail: rejected because it duplicates Run terminal ownership and makes same-trigger replay ambiguous.

Related Documents:

- [Control Protocol 0.4](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)
- [Protocol Validator](../scripts/validate_phase_a_control_protocol.py)
- [A04 Pause and Resume Semantics](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [A07 Phase B Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)
- [Phase B Requirement Catalog](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)

## 2026-09-03 — Close A01–A07 cross-contract linearization gaps

- Add `advance_run/not_applicable` as the single ControlOperation for every ordinary post-Attempt Transition outside START bootstrap and Human Response resume. It freezes admission, route prerequisites, target identity, invalidation, canonical Transition bytes, expected heads and terminal revision before publication; only a verified Attempt target receives an invocation capability.
- Keep normal final proof candidates on the normal finalization request. The shared ExternalOperation stores only the winning resolution and final evidence; an unavailable normal candidate creates or reuses the integrity interrupt contender without first becoming normal owner.
- Model resource reservation state and replay/fork source state as field-disjoint tagged unions. Dispatch-before-reservation interruption uses a proven absence value, while replay and fork consume disjoint source proofs and freeze child policy before any child bytes. Fork accepts only stable paused or terminal source heads.
- Resolve recoverable, halted, failed and unavailable interrupt outcomes inside the same winning interrupt operation after stop, usage, settlement and integrity evidence. Late overage, tamper or policy violation upgrades a safe stop to failed closure without a second terminal operation.
- Select explicit Pause cancellation by trigger before inspecting ExternalOperation context, so an opened cancelable Pause remains cancellable when no ExternalOperation exists. System stops continue through the unique context-specific interrupt route.
- Prepare START and ordinary-Transition invocation capabilities as inactive envelopes and activate them only when the same producer operation result commits. Bind interrupt, cancel and direct terminal outcomes to exact Run lifecycle dispositions.
- Require every noninitial ControlOperation phase to declare a producer that dominates it on every success path. An independent graph/dependency seal and 38 negative mutations reject coupled ordering edits and contract weakening.
- Keep protocol `0.4`, catalog `0.4.0`, and A02C01/A04–A07 in `review` because these artifacts remain pre-freeze. The catalog now contains 131 requirements and the protocol contains nine operation types with twelve variants.
- Bind this review snapshot to Control Protocol SHA-256 `55109ce7dc63abf0bd5d790282e561e0a7ca53e1d394a09c45b90c00c185d0e9` and requirement catalog SHA-256 `2182a1bef548d6eb2f2590266ca931878177be6a760b5d56ed391b078ab71c57`.

## 2026-09-03 — Close follow-up cross-contract relation gaps

- Replace Cancel's conflicting branch and terminal-resolution inputs with one shared tuple domain. Each tuple now declares its own reachable resolution phase: owner-bearing safe or typed-null paths use terminal eligibility, unavailable uses the closure tombstone, and preexisting winners use read-only winner observation.
- Model stop selection as finite trigger classes with required ExternalOperation contexts. Hard-limit, policy and terminal-operator stops route to interrupt while an ExternalOperation is live and to `close_run` when no unresolved ExternalOperation exists.
- Extend commit-gated initial Planner capability production to Replay and Fork child bootstrap. Both operations freeze capability inputs, prepare the envelope after the child checkpoint and activate it only with their exact committed result revision.
- Bind both source snapshot variants to the requested source Run and lineage digest. Replay additionally freezes a trusted source-policy classification proof derived from authoritative presence or absence, canonical policy identity and the runtime-supported policy set.
- Bind every interrupt resource snapshot to the same ExternalOperation identity, phase revision and lease epoch frozen in the resolution tuple. Present snapshots also bind the reservation identity and digest to that ExternalOperation.
- Add relational validation and negative mutations for Cancel tuple/phase reachability, trigger-class route totality, child capability producers, source identity and policy classification, and resource-to-ExternalOperation correlation. Keep protocol `0.4`, catalog `0.4.0`, 131 requirements and all review statuses unchanged.
- Bind the updated review snapshot to Control Protocol SHA-256 `acdd90277d8006c3323c58427244817f6fa9d6104d770eafb7b52f9b54c7e883` and requirement catalog SHA-256 `a0bc4afe236aabb7cd84c4e6aaab47aa3734b4339c1484afc6fc0954d9390654`.

Related Documents:

- [Control Protocol 0.4](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)
- [Protocol Validator](../scripts/validate_phase_a_control_protocol.py)
- [A02C01 Bootstrap Order](tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [A04 Pause and Resume Semantics](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [A07 Phase B Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)
- [Phase B Requirement Catalog](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)

## 2026-09-10 — Close normal-result handoff and invocation lease gaps

- Keep nine operation types and twelve variants. Extend close_run to atomically own an opened Pause and Run after normal safe finalization, settle the original reservation, abandon the scheduled target, interrupt the Pause and persist detachment evidence without rewriting the ExternalOperation resolution.
- Separate ExternalOperation pre-start authority from Attempt execution authorization. Scope the inbound Code Agent authorization to external preparation; only resume authorizes result consumption and verification.
- Keep committed authorization immutable and use a separate fenced invocation lease. Allow replacement only before started intent or effects; never reopen a producer tombstone, replay uncertain effects, or reset the budget through renewal.
- Settle Cancel unavailable conservatively before quarantine and closure. Share reservation identity and owner fencing across resume, cancel, interrupt and close; preserve observed overage.
- Keep A02C01 and A04–A07 in review. Add relation checks and sixteen negative mutations; independent review remains required before freezing.

- Updated review SHA-256: protocol `49abad0298d19f17f5a79ff8fd754e21deb324488a4810960e67804151d4646b`; catalog `b4a59a59f723a7a31fabc199fc051a78c90690e11ce9ce32b38e43ffeb8e84dc`.
- Validation: protocol/catalog and 63 negative mutations passed; 41 Markdown files / 391 relative links, temporary-bytecode compile and diff checks passed. Full pytest: 324 passed, one missing sibling golden-data failure; excluding that case: 324 passed, one deselected. Independent cross-review and the external golden-data rerun remain pending.

## 2026-09-10 — Complete timeout consumption and fresh Analysis preparation

- Supersede the earlier resume-only result-consumption restriction for trusted recoverable timeout. The same interrupt winner completes the original scheduled Code Agent Attempt through started, failed artifact registration, failed lifecycle and a final checkpoint before committing its result. A subsequent advance_run owns the Coordinator Transition.
- Freeze host_timeout failed result bytes from complete trusted safe-stop and usage/integrity evidence. Define its exact bundle member set and typed absence for missing Backend receipt/seal/audit; do not fabricate Backend output or run verification, dispatch or settlement again. Normal Backend delivery keeps its full evidence checks.
- Consolidate fresh Analysis preparation into advance_run. Reservation freezes exact spec/manifest bytes, target/Transition, base/change/effective-tree/runtime bindings; target_preparation_committed materializes and verifies the workspace before capability preparation. Other targets use explicit N/A, END issues no capability, and recovery only materializes the same frozen prefix under current authority.
- Remove the delivery-only interrupt handoff and unowned Analysis preparation path. Keep 9 operation types, 12 variants, 131 requirements, protocol 0.4/catalog 0.4.0 and review lifecycle unchanged. No Phase B runtime or completed tickets are changed.
- Add thirteen negative mutations, bringing the suite to 76. Independently enumerate the affected guarded paths and exercise existing A02 lifecycle functions: a scheduled source cannot transition; its started/failed completion can transition to Coordinator. Phase B fixtures must still validate real artifact and workspace effects at each failpoint.
- Review snapshot: protocol SHA-256 `67a6704692f3c9c351ed84f1324455b53b99043ad32bac475d89c49acdc99fe6`; catalog SHA-256 `13a78f9330409793a36bc55703062c03dc4e677ab96ed60038e79c92ebc1416a`.

## 2026-09-10 — Release consumed External bindings and constrain recovery scope

- Fix the review's one P1 and two P2 findings within Phase A. Add one shared external_consumption_released phase to normal resume and recoverable interrupt, after Code Attempt/artifact completion and before final checkpoint/outbound Transition. An immutable tagged proof binds safe final evidence, the original settlement, consumed Pause, terminal Attempt/artifact heads and consumption owner/epoch to an exact active-binding CAS.
- Keep ExternalOperation terminal history, resolution and original Pause identity unchanged. Create the active-binding projection with the original one-time Pause binding; release that projection only. Later close admission consumes the proof, and later ExternalOperations cannot reuse it. Restrict the second-close prohibition to Run terminal owners; a recoverable External resolution owner does not itself own Run closure.
- Reject RecoveryDecision continue for code_agent and legacy_codex_handoff before Pause claim. Other target kinds keep their original preparation requirements and attempt-execution scope. Explicit abandon-and-halt remains available, without automatic action on rejection. This replaces the ambiguous generic-target permission rather than introducing another Backend entry point.
- Reject nonstandard and non-finite JSON numbers, duplicate keys, and unknown/missing object fields or changed scalar types. Freeze recursive protocol/catalog object-layout digests alongside the graph seal, while retaining semantic ownership and producer/consumer checks. Keep 9 operation types, 12 variants, 131 requirements and review status; no Phase B runtime or completed ticket changes.
- Validation includes 89 protocol mutations and 6 JSON/catalog rejection checks. Independent probes also call semantic checks without relying on graph/layout seals, covering both release paths, bypass rejection, target-scope escalation and strict parsing. Full pytest: 324 passed; the only failure is the missing sibling golden reference data. The rerun excluding that external-data case passed with 324 passed and 1 deselected; tests and runtime were not modified.
- Review snapshot: protocol SHA-256 `b54d1b11181f46f9e1238ccdec3d1e92e762efcfca6c2a93f4afad97f23ad6b6`; catalog SHA-256 `92a184d3ffd93a1b81050ebefab912a270c76247f6505f4e1b750e209732f487`.

## 2026-09-10 — Close post-claim external consumption integrity failures

- Resolve the P1 where normal result consumption could neither register a Code artifact nor release its active binding for close admission. Keep cleanup inside the original resume_run/continue_execution owner; do not create close_run or another External interrupt and do not rewrite normal final evidence.
- Add guarded failure entries at all seven post-claim/pre-release boundaries. Commit the normal verdict together with its successor phase revision; a failure intent can win only against the current source revision. The failure ownership transaction reserves Run closure, increments closure revision, revokes invocation authority and freezes the exact snapshot and consumer stop intent.
- Stop and verify consumers/verifiers independently of the already terminal Backend. Safe consumer stop plus appendable Run authority produces a failed Run through the existing terminal eligibility/lifecycle/checkpoint phases. Any unavailable stop proof or authority produces a same-owner unavailable tombstone with conservative resource evidence and no fabricated Run lifecycle.
- Use trusted artifact-registration prohibition or an existing audit-only snapshot for failure disposition. Preserve consumed Pause and terminal Attempt records; allow claimed Pause interruption only under the same claim and Run owner. Reuse settled aggregate identity and settle outstanding consumer resources exactly once. Failure binding release does not masquerade as normal artifact-backed release.
- Consolidate the former linear-only resume expectation into the guarded graph validator and share existing terminal publication phases. Keep 9 operation types, 12 variants, 131 requirements, protocol 0.4/catalog 0.4.0 and review statuses. Runtime, completed tickets and historical completion records remain unchanged.
- Validation: 100 protocol mutations, 6 JSON/catalog rejections, and independent semantic probes for 28 failure-entry/stop/authority paths without relying on graph/layout seals. Strict JSON, 391 relative links across 41 tracked Markdown files, temporary-directory bytecode compilation and diff whitespace checks passed. Full pytest: 324 passed and one missing sibling golden-reference failure. Excluding that external-data case: 324 passed, 1 deselected; no test changes or fallback.
- Review snapshot: protocol SHA-256 `0398a709e4f99b17a3b15dce2b13ca3d0743589978d9b3d5c5ab8b0151a1293d`; catalog SHA-256 `0ead1e478270d09aaed6c570188a119fa72ec95d4e70d2ccc27db1f8d4f213fb`.


## 2026-09-10 — Unify invalid-response repause budget decisions

- Keep the existing `allow | human_gate | halt` BudgetDecision enum. Repause is the proposed action, not a separate decision value. Sufficient capacity authorizes `publish_pause`; insufficient capacity authorizes `close_run`.
- Freeze both cases and their exact proposal/capacity/head bindings in `budget_decision_contract`; validate producer/consumer agreement and A04/A06 prose. Preserve consumed Pause finality and allocate the next Pause only at `pause_prepared_recorded`.
- Review-only correction; no runtime or completed-ticket changes. Protocol mutations: 104; JSON/catalog negative checks: 6.
- Review snapshot: protocol SHA-256 `7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`; catalog SHA-256 `ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726`.
- Validation: protocol validator (104 protocol mutations and 6 JSON/catalog checks), both capacity outcomes, four direct semantic mutations without layout seals, and rejection of the original prose regression passed. Strict JSON, 391 relative links, Python compilation to a temporary directory and `git diff --check` passed. Full pytest: 324 passed, one failure caused by missing sibling golden-reference files; excluding that external-data case: 324 passed, 1 deselected.


## 2026-09-10 — Separate semantic validation from freeze checks

- Keep the closed-layout and graph freeze seals in normal validation, but separate them from semantic rules. Each negative mutation now names its validator and includes a positive control; 101 semantic cases cannot pass through a seal mismatch, and 3 structural cases remain explicit.
- Replace the duplicate complete linear phase/edge/dependency tables with independent publication milestones checked for dominance. Relate consumption-failure metadata to its graph and replace the copied classification table with the stop/authority total function and 28 reachable publication paths. Preserve independent ownership, fencing, evidence and disposition safety expectations.
- Remove fixed Chinese fragments, line-level language heuristics and English catalog-summary keyword gates. Keep stable IDs, references and explicit budget-decision enum checks; prose meaning remains a review responsibility.
- Protocol/catalog bytes, digests, versions, requirement count and review lifecycle are unchanged. No Phase B runtime, completed tickets or existing historical records changed.
- Validation: 101 direct semantic mutations, 3 structural mutations and 6 JSON/catalog checks passed. With the freeze checker disabled, semantic cases still pass independently; disabling the stop-proof checker makes its designated mutation fail. Equivalent prose passes while an undeclared decision enum is rejected. Bootstrap bypass is independently rejected by the milestone rule and freeze seal. The 28 failure paths, strict JSON, 391 relative links, temporary bytecode compilation and diff checks passed. Full pytest: 324 passed, one missing sibling golden-reference failure; excluding that case: 324 passed, 1 deselected. Validator size decreased by 91 lines.


## 2026-09-10 — Restore complete publication-order semantic coverage

- The milestone simplification omitted required lifecycle, claim and eligibility boundaries. Restore one independent safety-phase sequence per linear operation, sharing the child-bootstrap sequence for Replay/Fork, without duplicating edge/dependency tables. Require matching endpoints, present/reachable milestones and producer dominance.
- Add 178 direct order mutations derived from actual protocol graphs: adjacent internal swaps with dependencies changed together, phase bypass, removal and unreachability. All six linear variants must remain covered. Use the same rejection assertion as the existing mutation suite; no layout or graph seal may satisfy these semantic cases.
- Existing protocol/catalog bytes, digests, versions, 131 requirements and review status are unchanged. No runtime, completed tickets or historical records were modified.
- Validation: all 178 order mutations pass with structure/freeze checks unavailable; disabling the order rule makes the suite fail. All 40 coordinated adjacent inversions are independently rejected by the full semantic validator, including the 16 previously accepted cases. Existing 101 semantic, 3 structural and 6 JSON/catalog checks, 28 failure paths, strict JSON, 391 links, temporary bytecode compilation and diff checks passed. Full pytest: 324 passed, one missing sibling golden-reference failure; excluding that external-data case: 324 passed, 1 deselected.

## 2026-09-10: User-approved Phase A Design Freeze

- 用户最终确认`f4f0eaa`设计，将A02C01、A04–A07从`review`提升为`ready`；仅修改票据YAML lifecycle状态，正文保持批准版本原样。
- 本次Git冻结提交同时保存票据、protocol与catalog。两份JSON字节不变，原有protocol `status: review`保留为批准快照内容；执行资格由票据YAML和本次冻结决定确定。
- Protocol SHA-256：`7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`；catalog SHA-256：`ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726`。
- 后续按A02C01 → A04 → A05 → A06 → A07执行，结果写入独立completion records；本次不标记completed、不实现Phase B runtime。
- 静态协议验证与文档检查通过；此前缺少sibling golden数据的测试仍待环境补齐后复跑，不计为通过。

## 2026-09-14: Complete A02C01 Contract Execution

- Execute A02C01 within its frozen documentation-only scope and mark it completed after verification. This closes the schema `0.4+` bootstrap corrective contract as Phase A governance and downstream implementation input; it does not implement the coordinator, bootstrap runtime, graph, checkpoint, budget ledger, or tests.
- Preserve the A02 schema `0.2` runtime and historical four-record bootstrap contract. Preserve the frozen A02/A03/A03C01 ticket bodies, A04–A07 bodies, Control Protocol `0.4`, requirement catalog `0.4.0`, and their approved digests.
- Record execution facts in `docs/tickets/completions/A02C01_COMPLETION.md`, update the completion index and Phase A lifecycle documents, and make A04 the next executable ticket. Runtime and fault-injection implementation remains assigned to Phase B B00–B02.
- No architecture, schema, public contract, provider, security policy, dependency, runtime, test, evaluation, data, artifact, milestone, tag, or historical Run is changed by this execution.
- Verification passed: the tracked protocol validator confirmed 131 requirements, 101 semantic mutations, 3 structural mutations, 178 publication-order mutations and 6 JSON/catalog checks; the full deterministic suite passed 325 tests; 41 Markdown files contained 400 valid relative links; scope, frozen hashes and `git diff --check` passed.

## 2026-09-14: Complete A04 Pause/Resume Contract

- Execute A04 within its frozen design-only scope and mark it completed. The project now treats durable Pause/Resume/Replay/Fork, explicit cancellation, terminal publication, compatibility and child isolation as an approved target contract, not as an implemented runtime capability.
- Keep current `AnalysisState`, execution schema `0.2`, graph topology, LangGraph checkpoint handling and demo Human-decision re-entry unchanged. Target execution schema `0.3` introduces append-only `run_lifecycle`, orthogonal `run_status`, typed two-checkpoint Pause publication and runtime fingerprints; Phase B schema `0.4` reuses those semantics with A02C01/A06 coordinator contracts.
- Require every public mutation and internal publication to use the single A02C01 coordinator before Run/Pause/child/checkpoint bytes or side effects. Preserve single-use Pause claim, one terminal closure owner, original-operation cancel/interrupt/abandon tails, fail-closed uncertain effects and non-fabricated `terminal_closure: unavailable`.
- Replay only validated immutable root inputs; Fork only a coordinator-CAS-accepted latest stable paused/terminal head. Both create isolated child identities from `START` and never inherit source checkpoint/current pointers, active Pause, Human authorization or accepted status.
- Preserve the frozen A01–A03/A02C01/A03C01 and A05–A07 ticket bodies plus Control Protocol `0.4` and catalog `0.4.0` exact bytes. No runtime, graph, checkpoint backend, test, config, evaluation, provider, data, accepted artifact, milestone, tag or historical Run is changed.
- Verification passed with the tracked protocol validator, 43 current Markdown files/402 valid relative links, scope and frozen-hash audits, ticket metadata and `git diff --check`. Per A04, runtime, benchmark and live-provider tests were not run; A04 completion is not evidence that the target API exists.

## 2026-09-14: Complete A05 Code Agent Contract

- Execute A05 within its frozen design-only scope and mark it completed. The approved target exposes one canonical `code_agent` Attempt through a stable `CodeAgentSubgraph`; a replaceable `CodingBackend` performs external coding through Host-owned `dispatch`, `lookup`, `fetch_result` and `cancel` semantics without acquiring graph, Pause, budget, artifact or route authority.
- Keep the current `legacy_codex_handoff`, execution schema `0.2`, graph topology, dependencies, provider configuration, runtime and tests unchanged. Phase B uses a deterministic Fake through the same port, ingress validator, trusted verifier, registry and fresh Analysis handoff. A real Python Codex SDK backend remains conditional on a separate pinned C00 capability gate; current official SDK and sandbox documentation does not replace restart, audit, cancellation, containment and immutable-evidence tests.
- Require a durable two-stage ExternalOperation, one Attempt-isolated immutable-base workspace, manifest/seal and Host-owned containment. Dispatch follows A04 public Pause publication; normal, cancel and interrupt share one coordinator CAS domain and one final-evidence boundary. Unknown provider state never authorizes redispatch, and incomplete stop proof yields quarantine with `recovery_required` or `terminal_closure: unavailable` rather than fabricated failure evidence.
- Freeze schema `0.1` task, external result, canonical result, dispatch receipt, workspace evidence, change and verification artifacts. Valid canonical outcomes may register an A03 current code bundle with their exact status, but only `success` with `usable=true` may pass A01/A06 guards into Analysis; every other canonical status returns to the Coordinator, while malformed or policy-violating ingress remains outside artifact registration and product routing.
- Require a Host-owned `AnalysisExecutionSpec` and a fresh worktree/subprocess from the exact base plus verified change. The mutable coding workspace and current control repository are never Analysis execution sources. Code-bundle consumption does not authorize patch promotion, commit, merge, push, deployment, scientific acceptance or accepted memory.
- Preserve the frozen A01–A04/A02C01/A03C01 and A06–A07 ticket bodies plus Control Protocol `0.4` and catalog `0.4.0` exact bytes. Record execution facts in [A05 Completion Record](tickets/completions/A05_COMPLETION.md), and make A06 the next executable ticket.
- A05 is verified only by its prescribed static protocol, documentation, link, scope, metadata and freeze checks. Runtime, benchmark and live-provider tests are intentionally not run, and completion does not claim that the subgraph, backend, workspace, containment, resume or fresh Analysis runtime exists.

## 2026-09-14: Complete A06 Budget and Stop Contract

- Execute A06 within its frozen design-only scope and mark it completed. The approved target makes the trusted control plane the sole authority for immutable allowlisted `BudgetPolicy 0.1`, exact `BudgetDecision 0.1`, semantic `FailureFingerprint 0.1`, single-use `BudgetGrant 0.1`, resource accounting and deterministic stop admission.
- Keep the current execution schema `0.2`, `AnalysisState`, `retry_count/max_retry`, graph topology, runtime, tests, provider traces and historical Runs unchanged. Phase B schema `0.4` adds `budget_policy.json`, append-only budget records in the existing execution ledger and an exact bounded projection; no separate mutable budget history or Backend-owned counter is allowed.
- Count Cycles, Attempts, Transitions and automatic routes from authoritative lifecycle records. Reserve LLM, tool and verification resources before side effects, charge an unsettled crash at its maximum and give each scheduled Code Agent Attempt exactly one aggregate Backend envelope. Token and normalized cost remain audit-only, with missing usage represented as `unknown` rather than zero.
- Exclude execution identities, timestamps, physical paths, free text and raw logs from repeated-failure context. The second exact fingerprint in one Run cannot receive automatic fallback. A validated Human response may grant exactly one route opportunity for one fingerprint occurrence and target, but cannot raise global ceilings, reset history or restore terminal reserve.
- Reserve 5 Control Attempts and 6 Transitions for one typed terminal tail. Expired Pause resume is mutation-free; insufficient invalid-response capacity closes rather than opening a new Pause. Safe `halted` or proven `failed` closure requires complete stop and authority evidence, while uncertain stop proof quarantines the operation as `recovery_required`/`terminal_closure: unavailable` without fabricating Run lifecycle.
- Preserve A04 as the sole Pause/Run terminal owner, A05 as the sole Code Agent/backend contract, A03 as the artifact/accepted-result authority and Control Protocol `0.4` as the machine state authority. Preserve the frozen A01–A05/A02C01/A03C01 and A07 ticket bodies plus protocol/catalog exact bytes.
- Record execution facts in [A06 Completion Record](tickets/completions/A06_COMPLETION.md), and make A07 the next executable ticket. Runtime, benchmark and live-provider tests are intentionally not run; completion is governance evidence, not proof that budget enforcement, trusted clock, grant, deadline or stop runtime exists.

## 2026-09-14: Complete A07 Phase B Harness Acceptance Contract

- Execute A07 within its frozen design-only scope and mark it completed. Phase A is now complete as a contract-design stage; this does not mean the Phase B runtime or deterministic acceptance harness has been implemented.
- Freeze three evidence classes: required control acceptance for release claims, compatibility regression for preserved behavior and capability evaluation for non-gating quality observations. Required acceptance spans six layers: schema; node/subgraph/backend; route/guard; trajectory/cycle; recovery/concurrency/fault; and project interface/smoke.
- Bind Phase B acceptance to Control Protocol `0.4` SHA-256 `7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`, requirement catalog `0.4.0` SHA-256 `ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726` and all 131 required IDs. A machine-readable acceptance matrix must map every requirement to deterministic nodeids and expected traces; final mode permits zero missing, duplicate, placeholder, skipped or xfailed required coverage.
- Require normalized exact trajectories, real process restart, two independent clients and durable fault-boundary evidence. In-memory re-entry, single-process substitutes or asserted final state alone cannot establish restart, ownership, fencing or exactly-once publication guarantees.
- Divide implementation into B00 Acceptance Foundation, B01 Execution Foundation, B02 Durable Control Operations, B03 Fake Code Agent, B04 Topology and Budgeted Loops and B05 Integration/E2E/Zero-Gap. Each remains a separate ticket that must pass `draft -> review -> ready`; only B00 may be drafted next.
- Keep runtime, graph, checkpoint backend, dependencies, tests, configs, evaluation, providers, data, accepted artifacts and historical Runs unchanged. Do not create B00–B05 files or claim that any Phase B acceptance command currently passes.
- Record execution facts in [A07 Completion Record](tickets/completions/A07_COMPLETION.md). Per A07, verification is static and documentation-scoped; runtime, benchmark and live-provider tests are intentionally not run.

## 2026-09-15: Execute B00 Acceptance Foundation

- Freeze the user-approved B00 ready ticket in `f654f44` before implementation. Preserve its body, Phase A exact bytes and B01–B05 draft bodies; only B00 lifecycle metadata may change. The approval commit also preserves the preceding draft/planning changes. Implementation remains uncommitted for review; no push or second commit is implied.
- Generate a recursively immutable runtime-facing projection from exact Control Protocol/catalog bytes; provide pure lookup without runtime reads of documentation, test fixtures, environment, clock or provider state. The existing graph and schema `0.2` remain unchanged.
- Add strict closed acceptance inputs, the 15-item B00 construction slice, independently sealed registry/final obligations and a single fresh-session final driver. Coverage is a mapping count, not a pass count; construction global passed remains null. Runtime triggers and recovered case results are separate evidence joined to fresh passing nodeids and exact traces.
- Keep `requirements_zero_gap` independent from exit checks, and require both requirements and every fixed exit check for `phase_b_complete`. Reject stale tokens/contracts/worktrees, incomplete collection/results and benchmark exit-zero false positives. Compute normalized evidence hashes from verified semantic content rather than hashes of token-bearing raw files.
- Exercise the complete final mechanism only with isolated adapters in B00. Production exit adapters remain explicitly absent for B05; the real project final gate must fail on 116 mapping gaps, 2286 runtime cases and 15 exit checks, with no Phase B completion claim. All production hook bindings remain empty.
- Record implementation and verification in [B00 Completion Record](tickets/completions/B00_COMPLETION.md). B01–B05 remain draft and require independent user approval; no durable coordinator, Pause/Resume, Code Agent, budget runtime, new graph edge, dependency or external system was implemented.

## 2026-09-16: Execute B01 Pure Execution 0.4 Foundation

- Follow the user's explicit approval: freeze B01 ready and the preceding B00 implementation/maintenance in local commit `537d10ceda203fdea5c20266f994a20641cfc5ab`, then execute B01. Preserve the frozen body; subsequent changes are YAML lifecycle only. Do not push or create a second implementation commit.
- Keep the single execution ledger and reuse A02 formatters/node identity plus A03 lifecycle, index, invalidation and protected-evidence validators. Add pure canonical record/replay functions, immutable validation snapshots and an explicit read-only cross-head adapter, not a durable writer or alternative artifact authority.
- Consume generated machine definitions without overrides. Keep prose-only record/policy/fingerprint definitions sourced to frozen A02/A04/A06; exact policy values and semantic boundaries have construction tests. Host/Fake clock ports classify setup, backend, waiting and verification without granting invocation or settlement authority.
- Bind execution records through previous-head canonical hashes. Bind the artifact envelope to execution history, and bind an explicit checkpoint manifest to the exact pair and pre-checkpoint state digest; attach the manifest hash only afterward to avoid self-reference. Retain A03C01's limitation against arbitrary fully coordinated history rewriting without an external immutable anchor.
- Do not change the legacy 0.2 initializer, product graph, providers, dependencies or existing tests. B02 owns trusted bootstrap admission and durable operations; B03 owns external/backend integration; B04 owns route/resource/grant/stop enforcement. Pure record validation never substitutes for those authorities.
- Add only the B01 construction slice: 11 requirements, cumulative mapping 26/131, remaining 105, global passing counts null. Preserve all 2286 runtime obligations and 15 exit gaps, both completion flags false. See [B01 Completion Record](tickets/completions/B01_COMPLETION.md) for verification and follow-ups; B02–B05 remain draft.

## 2026-09-16: Approve B00C01 and Stop at an Omitted Exit Call Site

- The user approved the source-bound semantic trace correction. Freeze only its ready ticket in `d9af4e8`, preserving all existing uncommitted B02 work; do not push.
- Implement explicit trace `0.2` raw proof and semantic expected representations without changing runtime hashes, Phase A bytes, ownership or trace `0.1`. Verify canonical source digests, reference DAGs, production replay, root bindings and fresh-session evidence before narrow path/clock projection.
- Keep B00C01 incomplete: the existing exit evidence normalizer also calls the trace codec, but its file was omitted from the frozen Allowed Files. A valid new trace is rejected there for missing trusted binding. Do not bypass verification or silently expand the frozen scope.
- Propose [B00C02](tickets/phase-b-graph-harness/B00C02_SEMANTIC_TRACE_EXIT_BINDING.md) as a draft for those two binding calls and complete exit-path regression. Await independent approval; B00C01 and B02 remain blocked. Record actual progress in [B00C01 execution record](tickets/completions/B00C01_COMPLETION.md); passing construction and partial suites do not establish completion.

## 2026-09-16: Complete B00C02 and Unblock the B02 Prerequisite

- The user independently approved B00C02. Freeze only its ready snapshot in `10db77c`; keep its body unchanged, preserve existing uncommitted work and do not push.
- Pass the already session-validated pytest envelope explicitly into both trace normalization calls in the exit evidence normalizer. Preserve validation order, raw source proof, old trace semantics, schemas, ownership and fixed exit checks.
- Extend the existing isolated subprocess scenario through the actual exit validator. Two fresh invocations with different tokens and roots produce identical semantic evidence digests; stale or tampered evidence is rejected even with a recomputed outer checksum or internally consistent stale bindings.
- Complete B00C02 and close B00C01 after full verification. Restore B02 to ready without modifying its frozen body or implementing its remaining runtime under this corrective ticket. Actual project coverage stays 26/131 with 105 mapping, 2286 runtime and 15 exit gaps; both completion flags remain false.
- See [B00C02 Completion Record](tickets/completions/B00C02_COMPLETION.md). Historical B00C01/B02 stop records receive append-only resolution notes; B03–B05 remain draft.

## 2026-09-18 — 批准B02C01历史fingerprint缺失表示

用户批准[B02C01](tickets/phase-b-graph-harness/B02C01_LEGACY_SOURCE_FINGERPRINT.md)，在`5e753d6`单独冻结ready快照。真实0.2历史创建器未保存runtime fingerprint；将当前build补成source事实或拒绝所有合法0.2 replay均不合适。因此在既有Replay source字段内部允许唯一closed `not_recorded/legacy_schema_0_2`值，与source proof及child lineage绑定；0.3/0.4、Pause、target与resume规则保持严格，不修改Phase A协议/catalog字节。该决定只关闭source兼容表示缺口，B02其余控制分支与验收仍按原票执行。

## 2026-09-18 — Preserve historical Fork evidence and stop at the frozen trace boundary

B02C01 completed, then original B02 control implementation continued within its approved scope. The historical 0.3 source reader is a trusted Host port; core control verifies bytes, source identity/head, checkpoint and the existing shared revision before child reservation. Checkpoint source verification uses a private copy of the whole durability unit under that coordinator transaction, because SQLite read-only opens may create sidecars and immutable-mode reads can omit live WAL content. Neither path migrates or rewrites the source.

Close/resume competition now terminalizes a losing close without touching the winner. An owned preparation integrity failure derives the existing close-run failure path and preserves the scheduled target; verified control authority permits failed closure, otherwise the closure is unavailable.

A separate acceptance prerequisite remains: trace 0.2 can only resolve execution-head references through 0.4 replay, while a legitimate historical Fork lineage references 0.3 records. All three attempted old-version representations reject deterministically. Do not relabel historical data, omit heads or weaken B00. B02 is blocked under its Stop Conditions; [B00C03](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md) is a review proposal for an explicit new test-owned trace version, not an approved contract or implementation. B02's original body and all Phase A digests/ownership/obligations remain unchanged. B02C01 approval does not silently authorize changing the frozen B00 evidence format.

## 2026-09-21 — 验证历史来源轨迹并恢复B02

用户明确批准B00C03并单独冻结ready快照`3c53a41`。采用显式test-owned trace0.3，按固定原格式validator证明historical execution/checkpoint及真实source revision/reservation，不把历史记录交给0.4 replayer。新版本从lineage/CAS/request的真实preimage计算semantic DAG；身份、material、fingerprint与revision保持精确，旧版本不升级。原来源的SQLite durability unit只在私有副本打开。未知历史格式或非空artifact编码拒绝，不放宽runtime reader资格。

完整1063项回归和fresh B00/B01通过后完成B00C03、恢复原B02；不修改Phase A、production、ownership或独立验收义务。B02尚须交付自身30项construction和205/1488 runtime绑定。结果见[B00C03 completion](tickets/completions/B00C03_COMPLETION.md)。

## 2026-09-21 — Preserve reservation authority while reviewing impossible fault contexts

B00C03 completed, and resumed B02 fixed lost-plan terminalization and granted replan validation within the frozen contract. A new-process hard exit before the initial reservation transaction commits leaves no operation or Run authority. Do not fabricate an operation tombstone or reclassify an immutable committed result to satisfy the current cartesian fault inventory. B02 stops at its explicit acceptance-scope boundary; [B00C04](tickets/phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md) is an unimplemented review proposal for versioned case semantics and auditable replacements. No Phase A/runtime contract, inventory seal, ownership or completion gate changed. Original B02 authorization remains valid after the prerequisite is resolved; this does not authorize the new corrective ticket or B03/B04.

## 2026-09-21 B00C04 integrated correction

用户明确批准实施B02统一修复计划，并选择扩充尚未冻结的B00C04，统一处理case可达性、trace资源预留来源及进程证据前置；运行bug保留在原B02 maintenance。新版本仅改变test-owned验收表示，不放宽runtime schema、authority、状态机、source保护或B03/B04边界。首次SQL写入前后仍在COMMIT之前，不能补造可恢复operation。Ready正文按用户不commit/push要求只冻结于worktree，独立副本及正文SHA见B00C04 completion。

2026-09-21 B00C04完成：case0.2、trace0.4、直接production进程回执及严格分批验证落地；旧1488个B02 case为1370 retained/118 replaced，现行B02 **1416**、总数 **2214**，全部324 boundary及B03/B04集合不变。完整pytest **1118 passed**、新增定向 **32 passed**，fresh B00/B01 **15/15、11/11**，coverage26/remaining105。Global passed null、phase_b_complete false。B02验收前置阻塞已解除，接续原票处理已审定的runtime缺陷及完整验收；本修正票不代表B02完成。证据见[B00C04完成记录](tickets/completions/B00C04_COMPLETION.md)。

2026-09-21 C04补充审查：Fork `child.source_revision_cas`在首次reservation提交前，两项独立进程反例均完整回滚。沿用原票已批准的全boundary审查范围补齐这一遗漏；C04重新in_progress，B02暂为blocked。旧1488个B02 case现为1362 retained/126 replaced，现行总数 **2208**、B02 **1410**，减少78均有提交前反例；324 boundary、B03/B04及28 post-claim保持。之前2214/1416及C04完成报告保留为当时验证事实。coverage仍26/105；尚无B02 slice。

## 2026-09-21 — B02失败authority与验收闭合

已批准B00C04现已完成：case0.2区分SQL写入与真正COMMIT，旧1488个B02 case为1362 retained/126 replaced，现行1410；全部205个B02 boundary及B03/B04独立义务保持。Trace0.4只规范化已经证明的资源预留引用；进程回执由production boundary直接持久化，并绑定同session/case/nodeid。旧trace版本不变。

B02运行修复保持原public schema/phase graph：错误必须携带实际失败边界operation、worker、epoch和revision，失败handler不得新读epoch代旧调用取得权限。已取得Run owner的失败原子关闭为已有failed/unavailable类别；外部normal final不可变，Human后续终态向原父resume传递。Query的Run closure投影与原operation持久化结果是不同读取对象，测试分别校验其真实来源。

B02 construction30/30及1410/1410独立case、完整2599测试通过后才完成原票。Expected traces在验收前审查固定，实际运行禁止重写；全部批次共用一个冻结输入/session并验证无遗漏或重复。全局final继续保留后续75/798/15缺口，不放宽门槛；B03–B05仍须分别审定。执行结果见[B02完成记录](tickets/completions/B02_COMPLETION.md)。

## 2026-09-24 — B00C05初始ExternalOperation故障上下文与B03版本衔接

用户批准按审阅建议补齐并实施B00C05，ready正文在`52c508b`冻结。Case0.3明确限定三个pre-COMMIT side为合法新producer首次事务；无durable producer时只证明完整回滚与重新准入，不伪造原operation恢复或Run failure。原16项逐项记录12 replaced/4 retained；提交后的四类durable保护及全部后继边界保留，完整canonical runtime证据仍由B03负责。由独立规则得到2199/B03 645，计数不作为反向裁剪目标。

Host初始reserve/lookup复用现有external_operations和coordinator，不引入第二authority、表或public control API。真实进程与双client验证通过；完整2617项及同Session B02-owned 1410项通过后才关闭本修正。Case0.1/0.2、trace0.1–0.4、protocol/catalog、requirements/owners和exit门槛保持。Case0.3显式窄范围替代B03的旧case0.2入口，原B03正文仍冻结；B03的canonical Backend、28项construction与645项runtime不因本修正而宣称完成。

## 2026-09-24 — B00C06 A05 digest provenance（实施中）

用户批准补强、冻结并执行 B00C06，ready 正文提交为 `cd29d9f`。新增显式 trace 0.5 / proof 0.2，旧版本和旧 goldens 不重新解释。完整 raw checksum/identity/dependency 验证先于 semantic projection；self digest、完整 canonical digest 与 A03 byte digest 不可混用。嵌套 Code pointer、Pause、settlement/failure evidence 纳入闭包，材料与权威状态变化继续可区分。具体规则见 Verification Guide 的 derivation 表。

本票不修改 src、A05/A06 runtime 合同、case0.3、2199 cases、131 requirements 或 exit 门槛。Contract fixtures 不计 B03 canonical evidence；集成完成后才解除 trace 前置。原 B03 授权保持，其预算事务与状态迁移问题须按原冻结范围处理。

B00C06最终验证完成后关闭。新版本与旧版本隔离，原required/owner/case集合不变。B03接续发现的null projection造成真实语义变化，即使runtime fingerprint相同也存在；不将其归入原fingerprint-only golden例外，不通过忽略null或全局扩展legacy表规避。先形成窄范围补充授权，B03因此保持blocked。

2026-09-24：已形成待审 [B00C07 状态投影与 golden 窄范围补充](tickets/phase-b-graph-harness/B00C07_A05_STATE_PROJECTION_GOLDEN_HANDOFF.md)。该票为 review，尚未批准或执行；只提出 B03 的版本隔离、已知 nullable projection 派生同步与兼容核验边界，不预先交付 runtime。原 B03 授权保留，但依其冻结 Stop Conditions 暂保持 blocked，待本补充批准后继续。

2026-09-24：B00C07已按用户同意补强，ready冻结于`7ab58ce`并完成文档交接。B03恢复ready；四个canonical paths来源修复与B02 needs_input fixture窄替换获得明确授权，尚未实现。先推进B03预算事务/失败恢复，再完成canonical实现与28/645验收；当前mapped56/remaining75、Phase B未完成。

2026-09-24 B03接续：B00C07已完成治理交接，但新注册member反例确认其B02 fixture替换与禁止trace0.5的限制冲突，B03再次blocked，待审B00C08。未修改production或golden；15项定向反例/回归通过。当前mapped56/remaining75，预算事务与canonical B03仍未实现。 见[B00C08待审票](tickets/phase-b-graph-harness/B00C08_B02_CANONICAL_EVIDENCE_TRACE_HANDOFF.md)。

2026-09-24：B00C08在13f3b74冻结并完成治理交接；B03恢复ready。Normal/timeout完整来源、source trace0.5、独立Analysis success前置及其golden审计范围已批准，尚待B03实现。预算事务与canonical交付未完成，mapped56/remaining75、Phase B未完成。

## 2026-09-24 — B00C09 canonical Code 活动时间仍由单一ledger裁决

用户批准B00C09，ready快照单独冻结于`47bd0f6`。A06七类旧budget event和Phase A protocol/catalog保持原字节；仅B03 canonical Code path新增`active_time_0.1`的setup/Attempt closed事件，复用原B02 execution ledger/head与checkpoint authority。Setup只扣Run，Backend aggregate及Attempt区间同时扣Run/Attempt；verification保留正timeout、实测秒数与command audit，但在可信parent区间内不重复扣active。旧B02 synthetic事件和Pause proof不套用新marker。

首次producer事务冻结setup record，COMMIT后exact发布；过期时原producer通过内部`recovery_only`新lease epoch仅补发同一record，旧epoch拒绝且不准新增pre-start效果。Pause以最后frozen suffix结算setup，normal/timeout及可安全关闭的失败收尾沿原owner和phase结算Attempt。跨epoch与不确定effect保留maximum；可信overage记录原观测值并进入原A06失败/不可用终态。独立合同见[B00C09](tickets/corrections/B00C09_ACTIVE_TIME_LEDGER_CONTRACT.md)。此决定只解除B03活动时间前置，完整Backend、Bundle、Analysis和28/645仍归B03，Phase B全局门槛不变。

## 2026-09-28 — B03C02未启动consumer的post-claim runtime语义

用户批准[B03C02](tickets/phase-b-graph-harness/B03C02_POST_CLAIM_UNSTARTED_CASE_SEMANTICS.md)后，case0.4仅将`invocation_authorized`前六个entry phase各两项无法触发的`consumer_stop=unavailable` runtime case替换为同phase、同Run authority的`unstarted_recovery` case。未启动时冻结的`started_intent=null`给出可信`not_dispatched`，不调用stop adapter；appendable对应`failed_closure`，unavailable对应`unavailable_closure`。同一原owner的failure intent必须先在SQLite事务提交，再由新进程恢复；事务内phase `after`本身不构成持久化证据。旧case0.3、A07设计时7×4分类、全部其他2187项case、协议/catalog/required IDs/owners/exit门槛保持原义；case0.4仍为2199/B03 645/post-claim 28。B03C02不替代B03其余626项独立runtime验收，Phase B完成条件不变。审定与双fresh根证据见[独立记录](tickets/completions/B03C02_COMPLETION.md)。
