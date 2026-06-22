# Repository Current State

## Date

2026-06-22

## Current Status

The project has completed source-of-truth documentation, the repository skeleton, the initial real LangGraph mock runtime skeleton, a standalone deterministic Method Planner module, Phase 2B Method Planner graph integration, Phase 3 Codex Handoff integration, Phase 4 Analysis Engineer integration, Phase 5 Scientific Reviewer diagnostics, Phase 6 Decision Coordinator risk rubric, Phase 6 maintenance for output policy, timestamp default run ids, and stale-documentation discipline, Phase 7 Human Approval Gate integration, Phase 8 Memory, Final Report, and Synthetic Evaluation Harness implementation, Phase 9 Golden Example productization, Phase 7-9 maintenance for decision-route audit fields, approved-decision report text, evaluation cleanup guarding, and documentation synchronization, Phase 9 GitHub-ready cleanup of ignored local artifacts, and independent GitHub repository initialization for the Phase 9 baseline. The package is installable in editable mode, and focused tests cover state initialization, routing, context summarization, graph execution, standalone method planning, integrated planner graph outcomes, task-packet validation, the handoff test runner, Codex Handoff routing, safe analysis command execution, golden mock command execution, output validation, provenance manifest generation, evidence-backed scientific review diagnostics, structured decision coordination, approval packet generation and parsing, risk-safe memory behavior, final report generation, synthetic evaluation summary reporting, automatic CLI run ids, protected-artifact run reuse refusal, guarded evaluation cleanup, and the conservative golden demo path.

Existing source:

- `AGENTS.md` defines repository behavior expectations.
- `docs/` contains the source-of-truth project documentation.
- `pyproject.toml` declares LangGraph and the SQLite checkpoint package.
- `src/lqcd_agent/__init__.py` provides the initial package marker.
- `src/lqcd_agent/agents/analysis_engineer.py` provides the standalone deterministic Analysis Engineer module.
- `src/lqcd_agent/agents/decision_coordinator.py` provides the standalone deterministic Decision Coordinator module and risk rubric.
- `src/lqcd_agent/agents/method_planner.py` provides a standalone deterministic structured-output Method Planner module.
- `src/lqcd_agent/agents/scientific_reviewer.py` provides the standalone deterministic Scientific Reviewer module.
- `src/lqcd_agent/analysis/` contains correlator, fit, and matrix-element diagnostic helpers for the Scientific Reviewer.
- `src/lqcd_agent/coder/task_packet.py` validates and reads/writes mock coder handoff packets when code is needed.
- `src/lqcd_agent/coder/codex_handoff.py` reads file-based handoff results without calling Codex programmatically.
- `src/lqcd_agent/coder/test_runner.py` runs allowlisted verification commands and writes `tests_status.json`.
- `src/lqcd_agent/tools/command_runner.py` runs internal mock analysis commands, including the Phase 9 golden mock writer, and exact-allowlisted local analysis commands.
- `src/lqcd_agent/tools/output_validator.py` validates expected mock analysis outputs.
- `src/lqcd_agent/tools/manifest.py` writes provenance manifests with config hashes, file records, command records, git summary, tool versions, and environment summary.
- `src/lqcd_agent/tools/repo_inventory.py` provides a small repository inventory helper for planner inputs.
- `src/lqcd_agent/graph/approval_packet.py` writes approval packets and parses flat human decision YAML files.
- `src/lqcd_agent/memory/` classifies and writes accepted, pending, or rejected memory updates.
- `src/lqcd_agent/report/` generates human-readable final reports.
- `src/lqcd_agent/graph/` contains the mock `StateGraph`, state schema helpers, deterministic nodes, routing, and CLI runner. The graph method planner node calls the standalone Method Planner module, the Codex Handoff node is wired into `code_needed=true` and code-failure retry paths, the Analysis Engineer node calls the standalone Analysis Engineer module, the Scientific Reviewer node calls the standalone Scientific Reviewer module, the Decision Coordinator node calls the standalone Decision Coordinator module, the Human Approval Gate writes `approval_packet/` artifacts for high and critical risk outcomes, and the Memory and Report node calls the dedicated memory and report modules. The CLI generates a timestamp run id when `--run-id` is omitted and refuses to reuse a run directory that already contains protected completed or decision artifacts.
- `evaluation/cases/` contains synthetic good, ambiguous, and bad Phase 8 evaluation cases.
- `evaluation/run_evaluation.py` runs the synthetic evaluation cases and writes `evaluation_summary.csv`; it refuses to delete existing evaluation run directories unless explicit force-clean behavior is requested.
- `configs/cases/mock_lqcd_goal.yaml` and `configs/runtime/mock_llm.yaml` are placeholders only.
- `configs/cases/l64c64a076_m140.yaml` is the Phase 9 golden mock demo case; it references the sibling golden example as read-only provenance and keeps analysis output synthetic.
- `scripts/run_langgraph_demo.sh` runs the one-command Phase 9 golden mock demo.
- `outputs/.gitkeep` keeps the output root present without committing run artifacts; Phase 9 GitHub-ready cleanup removed ignored historical run artifacts and local caches.
- `tests/test_import.py` verifies that the package imports.
- `tests/test_state_schema.py`, `tests/test_routing.py`, and `tests/test_graph_smoke.py` verify runtime behavior, including no-code, `needs_more_info`, missing handoff results, structured handoff pass-through paths, and the golden mock demo path.
- `tests/test_approval_packet.py` verifies approval packet generation, human decision parsing, pending behavior, and decision route fields.
- `tests/test_coder_task_packet.py` verifies task-packet validation and read/write behavior.
- `tests/test_decision_coordinator.py` verifies low, medium, high, and critical risk decisions.
- `tests/test_test_runner.py` verifies `tests_status.json` records passing, failing, and blocked verification commands.
- `tests/test_method_planner_mock.py` verifies standalone method-plan generation, coder task packet generation, and missing-input handling.
- `tests/test_analysis_engineer.py` verifies Phase 4 success, missing-output failure classification, command failure recording, and overwrite refusal.
- `tests/test_command_runner.py` verifies mock command execution, golden mock command execution, blocked unapproved local commands, and exact-allowlisted local command execution.
- `tests/test_manifest.py` verifies required provenance fields.
- `tests/test_scientific_reviewer.py` verifies good, ambiguous, and bad mock matrix-element diagnostics and severe warning evidence flags.
- `tests/test_memory.py` verifies accepted, pending, rejected, and overwrite-guard memory behavior.
- `tests/test_report.py` verifies final report sections and missing-artifact warnings.
- `tests/test_evaluation.py` verifies synthetic evaluation case loading and summary generation.

## Confirmed Scope

- Scientific MVP: pion quasi-DA.
- First golden example: mock-only structured synthetic matrix elements versus `z` and `Pz`.
- Data boundary: read manifests/checksums only; do not read real raw numeric data in MVP.
- Command boundary: allowlisted mock/test/smoke commands only; Phase 4 analysis commands are internal `mock:` commands or exact-allowlisted local commands with `shell=False`.
- LLM provider: deterministic mock default; real providers deferred.
- Graph shape: LangGraph with five core agents and two support nodes.
- Checkpoint policy: SQLite full graph state plus summarized LLM-facing context.
- Human approval: high and critical risk gated.
- Evaluation cases: synthetic good, ambiguous, and bad cases.
- Current runtime done: one-command mock run creates deterministic mock artifacts, `run_result.json`, `manifest.json`, `run.log`, `scientific_review_report.json`, `decision_log.json`, `memory_update.json`, `final_report.md`, `graph_state.json`, and checkpoint metadata.
- Current planner integration done: no-code planner output routes to Analysis Engineer; `needs_more_info` stops safely as `pending` before analysis.
- Current Codex Handoff integration done: `code_needed=true` and code-failure retry paths route to Codex Handoff; missing result files stop as `pending`; invalid result files stop as `halted`; structured `tests_passed` plus `code_change_summary.md` routes to Analysis Engineer.
- Current Analysis Engineer integration done: the graph analysis node writes `run_result.json`, `manifest.json`, `run.log`, and `analysis_outputs/synthetic_matrix_elements.json` through the standalone Analysis Engineer module.
- Current Scientific Reviewer integration done: the graph reviewer node writes `scientific_review_report.json` through the standalone Scientific Reviewer module, with correlator, fit, and matrix-element diagnostic sections.
- Current Decision Coordinator integration done: the graph decision node writes `decision_log.json` through the standalone Decision Coordinator module, using structured Method Planner, Analysis Engineer, and Scientific Reviewer artifacts.
- Current Human Approval Gate integration done: high and critical risk outcomes write `approval_packet/approval_packet.json`, `approval_packet/approval_summary.md`, and `approval_packet/07_human_decision.yaml`; no decision or invalid decision leaves the run pending at the gate.
- Current risk policy done: low risk can write accepted mock memory; medium risk remains pending or human-review-recommended; high and critical risk require human approval before accepted memory can be written. High and critical no-decision states may still write pending memory and final-report artifacts for audit and demo visibility.
- Current golden demo done: `bash scripts/run_langgraph_demo.sh` runs `configs/cases/l64c64a076_m140.yaml`, writes under `outputs/l64c64a076_m140/<run_id>/`, includes selected read-only sibling golden files in provenance, produces synthetic matrix-element output with a severe demo flag, writes `approval_packet/`, and leaves `memory_update.json` pending with `accepted_result: false`.
- Canonical output policy: actual run artifacts live under `<output_root>/<case_id>/<run_id>/`. `outputs/` is the repo-local actual-run output root and is ignored except for `.gitkeep`; existing historical files under `outputs/` are generated artifacts, not reference outputs or schema acceptance evidence.
- Verification output policy: Codex and automated checks should prefer a temporary output root such as `/private/tmp/lqcd-agent-...` or a unique `--run-id`. If `--run-id` is omitted, the CLI generates a timestamp run id. Explicit repeated run ids are refused once protected completed or decision artifacts exist.
- Evaluation output policy: Phase 8 synthetic evaluation actual-run artifacts and `evaluation_summary.csv` default to `/private/tmp/lqcd-agent-phase8-evaluation`. Future curated reference outputs belong under `evaluation/reference_outputs/`, and expected risk/action/warning behavior belongs under `evaluation/expected_behavior/`; neither should be mixed into `outputs/`.
- Repository boundary: `lqcd-agent` is now an independent Git repository rooted at `/Users/chengxiaowei/Desktop/LQCD/lqcd-agent`. The `main` branch tracks `origin/main` at `git@github.com:Xiaowei251129/lqcd-agent.git`; parent-repo commits under `/Users/chengxiaowei` are not used for this project.
- Deferred MVP work: provider integration, raw-data-backed evaluation cases, and real approval-node follow-through beyond Phase 7 route intent.

## Verification Status

- `pip install -e .` succeeds.
- `pytest tests/test_import.py -q` succeeds.
- `pytest tests/test_state_schema.py tests/test_routing.py tests/test_graph_smoke.py -q` succeeds.
- `pytest tests/test_method_planner_mock.py -q` succeeds.
- `pytest tests/test_coder_task_packet.py tests/test_test_runner.py tests/test_routing.py tests/test_graph_smoke.py -q` succeeds.
- `pytest tests/test_analysis_engineer.py tests/test_command_runner.py tests/test_manifest.py tests/test_routing.py tests/test_graph_smoke.py -q` succeeds.
- `pytest tests/test_scientific_reviewer.py tests/test_graph_smoke.py -q` succeeds.
- `pytest tests/test_decision_coordinator.py tests/test_routing.py tests/test_graph_smoke.py -q` succeeds.
- `pytest tests/test_approval_packet.py tests/test_routing.py tests/test_graph_smoke.py -q` succeeds.
- `pytest -q` succeeds.
- `pytest tests/test_state_schema.py tests/test_routing.py tests/test_graph_smoke.py tests/test_method_planner_mock.py -q` succeeds.
- `python -m lqcd_agent.graph.run_graph --case configs/cases/mock_lqcd_goal.yaml --output-dir /private/tmp/lqcd-agent-phase6-cli --run-id phase6_verify` succeeds and writes `run_result.json`, `manifest.json`, `run.log`, `scientific_review_report.json`, `decision_log.json`, `memory_update.json`, and SQLite checkpoints under `/private/tmp/lqcd-agent-phase6-cli/mock_lqcd_goal/phase6_verify/`.
- `pytest tests/test_graph_smoke.py tests/test_routing.py -q` succeeds after the Phase 6 maintenance run-id guard tests.
- `pytest tests/test_decision_coordinator.py tests/test_analysis_engineer.py tests/test_scientific_reviewer.py -q` succeeds after the Phase 6 maintenance docs and CLI policy changes.
- `python -m lqcd_agent.graph.run_graph --case configs/cases/mock_lqcd_goal.yaml --output-dir /private/tmp/lqcd-agent-maintenance` succeeds with an automatically generated timestamp run id.
- `python -m lqcd_agent.graph.run_graph --case configs/cases/mock_lqcd_goal.yaml --output-dir /private/tmp/lqcd-agent-maintenance --run-id phase6_maintenance` succeeds on first use and fails cleanly on reuse after protected artifacts exist.
- `pytest tests/test_memory.py tests/test_report.py tests/test_evaluation.py tests/test_graph_smoke.py -q` succeeds.
- `python evaluation/run_evaluation.py` succeeds and writes `/private/tmp/lqcd-agent-phase8-evaluation/evaluation_summary.csv`.
- `bash scripts/run_langgraph_demo.sh` succeeds and writes a high-risk pending golden mock demo under `outputs/l64c64a076_m140/<run_id>/`.
- Phase 9 GitHub-ready cleanup dry-runs and removes ignored generated artifacts; after cleanup, `outputs/` contains only `.gitkeep`, `.DS_Store`, `__pycache__/`, `.pytest_cache/`, and `src/lqcd_agent.egg-info/` are absent before verification commands regenerate local caches.
- Independent Git setup completed: `git rev-parse --show-toplevel` resolves to `/Users/chengxiaowei/Desktop/LQCD/lqcd-agent`, `git remote -v` points to `git@github.com:Xiaowei251129/lqcd-agent.git`, and `git status --short --branch` shows `main` tracking `origin/main`.

## Next Work

The repository-management setup for the Phase 9 baseline is complete. The next implementation step is Phase 10: add the provider abstraction and secure dry-run configuration while preserving deterministic mock defaults. Later tickets add Phase 10B provider-backed agent wiring, Phase 10C scenario-based end-to-end rehearsal, and then Phase 11 raw-data library work after explicit authorization and data readiness.

## Blockers and TODOs

- TODO(owner:provider-integration, reason:provider-specific OpenAI/DeepSeek environment variables are deferred until the provider phase).

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [Tickets](TICKETS.md)
- [Decision Log](DECISION_LOG.md)
