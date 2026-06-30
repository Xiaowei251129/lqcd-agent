# Verification Guide

## Current Skeleton Checks

Use these checks during the initial repository skeleton phase:

```bash
test -f AGENTS.md
test -f pyproject.toml
test -f README.md
test -f .gitignore
test -f .env.example
test -f src/lqcd_agent/__init__.py
test -f configs/cases/mock_lqcd_goal.yaml
test -f configs/runtime/mock_llm.yaml
test -f outputs/.gitkeep
test -f tests/test_import.py
test -f docs/PROJECT_SPEC.md
test -f docs/ARCHITECTURE.md
test -f docs/AGENT_ROLES_AND_BOUNDARIES.md
test -f docs/STATE_SCHEMA.md
test -f docs/ARTIFACT_CONTRACTS.md
test -f docs/TICKETS.md
test -f docs/VERIFICATION_GUIDE.md
test -f docs/PROMPT_PLAYBOOK.md
test -f docs/SECURITY_AND_DATA_POLICY.md
test -f docs/EVALS_AND_OBSERVABILITY.md
test -f docs/REPO_CURRENT_STATE.md
test -f docs/DECISION_LOG.md
```

Also verify:

- Required docs cross-reference only existing docs.
- No forbidden paths were modified.
- `docs/PROMPT_PLAYBOOK.md` contains the standard ticket contract.
- `docs/PROMPT_PLAYBOOK.md` contains the standard phase prompt wrapper.
- `docs/PROMPT_PLAYBOOK.md` contains at least two worked examples.
- TODOs include owner and reason.

## Packaging and Smoke Checks

```bash
pip install -e .
pytest tests/test_import.py -q
```

## Current Runtime Checks

Use these checks after the Phase 9 Golden Example and Productization integration:

```bash
pytest tests/test_llm_config.py -q
pytest tests/test_llm_mock_provider.py -q
python -m lqcd_agent.llm.provider_factory --config configs/runtime/openai.yaml --dry-run
python -m lqcd_agent.llm.provider_factory --config configs/runtime/deepseek.yaml --dry-run
pytest tests/test_memory.py tests/test_report.py tests/test_evaluation.py tests/test_graph_smoke.py -q
python evaluation/run_evaluation.py
pytest tests/test_approval_packet.py tests/test_routing.py tests/test_graph_smoke.py -q
pytest tests/test_decision_coordinator.py tests/test_routing.py tests/test_graph_smoke.py -q
pytest tests/test_scientific_reviewer.py tests/test_graph_smoke.py -q
pytest tests/test_analysis_engineer.py tests/test_command_runner.py tests/test_manifest.py tests/test_routing.py tests/test_graph_smoke.py -q
pytest tests/test_coder_task_packet.py tests/test_test_runner.py tests/test_routing.py tests/test_graph_smoke.py -q
pytest tests/test_state_schema.py tests/test_routing.py tests/test_graph_smoke.py -q
pytest tests/test_method_planner_mock.py -q
python -m lqcd_agent.graph.run_graph --case configs/cases/mock_lqcd_goal.yaml --output-dir /private/tmp/lqcd-agent-smoke
bash scripts/run_langgraph_demo.sh
```

The graph smoke tests cover:

- no-code planner output continuing through Analysis Engineer to the final report
- planner `needs_more_info` stopping safely as `pending` before analysis with structured state `errors`
- planner `code_needed=true` routing to Codex Handoff, writing or validating `coder_task_packet.yaml`, and stopping as `pending` before analysis when handoff results are missing
- Codex Handoff continuing to Analysis Engineer only when `tests_status.json` reports `tests_passed` and `code_change_summary.md` exists
- Analysis Engineer writing `run_result.json`, `manifest.json`, and `run.log` under the canonical run result path
- Scientific Reviewer writing `scientific_review_report.json` with correlator, fit, and matrix-element diagnostic field names
- Decision Coordinator writing `decision_log.json` with structured risk, action, evidence, next-action, and route-intent fields
- Human Approval Gate writing `approval_packet/approval_packet.json`, `approval_summary.md`, and `07_human_decision.yaml` for high and critical risk outcomes
- Memory and Report writing accepted, pending, or rejected `memory_update.json` records through the dedicated memory implementation; medium outcomes remain pending, while high and critical outcomes write pending memory/report artifacts and keep accepted memory blocked when no valid decision is present
- final report generation through the dedicated report implementation with metadata, method, run, review, warning, decision, approval, memory, next-action, and reproducibility sections
- the `l64c64a076_m140` golden mock demo linking read-only sibling golden example provenance to synthetic outputs and producing high-risk pending approval artifacts
- CLI timestamp run-id generation when `--run-id` is omitted
- CLI refusal to reuse a run directory that already contains completed or decision artifacts
- handoff pass-through when only `tests_status.json` and `code_change_summary.md` pre-exist in the run directory

The Phase 7 Human Approval Gate acceptance command is:

```bash
pytest tests/test_approval_packet.py tests/test_routing.py tests/test_graph_smoke.py -q
```

The Phase 8 Memory, Final Report, and Synthetic Evaluation Harness acceptance commands are:

```bash
pytest tests/test_memory.py tests/test_report.py tests/test_evaluation.py tests/test_graph_smoke.py -q
python evaluation/run_evaluation.py
```

The Phase 9 Golden Example and Productization acceptance command is:

```bash
bash scripts/run_langgraph_demo.sh
```

The Phase 10 provider abstraction and secure configuration acceptance commands are:

```bash
pytest tests/test_llm_config.py -q
pytest tests/test_llm_mock_provider.py -q
python -m lqcd_agent.llm.provider_factory --config configs/runtime/openai.yaml --dry-run
python -m lqcd_agent.llm.provider_factory --config configs/runtime/deepseek.yaml --dry-run
```

The provider factory may load a repo-local `.env` file without overriding already-exported variables. Dry-run output includes only non-secret readiness metadata. Optional live-provider tests or calls require `RUN_LIVE_LLM_TESTS=1` plus the provider-specific key and model variables from `.env.example`; they are disabled by default and are not required for normal verification.

The Phase 10B provider-backed agent wiring acceptance commands are:

```bash
pytest tests/test_method_planner_mock.py tests/test_scientific_reviewer.py tests/test_decision_coordinator.py tests/test_llm_mock_provider.py tests/test_graph_smoke.py tests/test_state_schema.py -q
python -m lqcd_agent.graph.run_graph --case configs/cases/mock_lqcd_goal.yaml --output-dir /private/tmp/lqcd-agent-provider-smoke --run-id provider_mock --llm-provider-config configs/runtime/mock_llm.yaml
python -m lqcd_agent.graph.run_graph --case configs/cases/l64c64a076_m140.yaml --output-dir /private/tmp/lqcd-agent-provider-golden-guard --run-id provider_golden --llm-provider-config configs/runtime/mock_llm.yaml
```

The graph remains deterministic when `--llm-provider-config` is omitted. The mock provider config exercises provider-backed Method Planner, Scientific Reviewer, and Decision Coordinator wiring without network access or secrets. Invalid provider output must write a structured failed artifact and must not route from free-form text.

Provider-backed decisions must also preserve the local safety floor. The golden guard command above should leave `memory_update.json` pending with `accepted_result: false`, write `approval_packet/`, and keep `decision_log.json` routed to `human_approval_gate` because the synthetic golden artifact carries a severe diagnostic flag.

The Phase 10C advisor-demo benchmark was implemented on 2026-06-23 and live
provider demo verification was completed on 2026-06-30. Its
verification commands are:

```bash
pytest tests/test_synthetic_benchmarks.py -q
pytest tests/test_evaluation.py tests/test_graph_smoke.py tests/test_scientific_reviewer.py tests/test_decision_coordinator.py tests/test_analysis_engineer.py -q
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py --provider mock --case-set demo --output-dir /private/tmp/lqcd-agent-phase10c-mock
pytest -q
git diff --check
```

The mock-provider benchmark is required to remain network-free. It should verify
that each advisor-demo scenario has instructor-only expected behavior, that the
Analysis Engineer consumes scenario-specific synthetic data rather than reusing
the fixed mock output unchanged, and that the rehearsal infrastructure writes
case-specific analysis, fit, review, decision, memory, report, route, and
checklist artifacts. Generated benchmark cases use the exact-allowlisted
`analysis:run_synthetic_benchmark:<scenario_path>` command. The command writes
weighted log-linear fit support artifacts under `analysis_outputs/`, while the
validated `synthetic_matrix_elements.json` remains the only Phase 4 expected
output for acceptance.

The full mock-provider suite can be run with:

```bash
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py --provider mock --case-set full --output-dir /private/tmp/lqcd-agent-phase10c-full
```

The optional live-provider Phase 10C advisor-demo command is:

```bash
RUN_LIVE_LLM_TESTS=1 python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py \
  --provider-config configs/runtime/openai.yaml \
  --case-set demo \
  --output-dir /private/tmp/lqcd-agent-real-analysis-live \
  --run-id-prefix live_real_analysis_check \
  --force-clean
```

The live command must be explicitly enabled and must not run during ordinary
tests. Its output should include `synthetic_rehearsal_summary.md` and
`advisor_demo_report.md`. The advisor report should compare each scenario's
question, hidden expected conclusion summary, actual agent conclusion, expected
and actual route, expected and actual risk/action, required or forbidden
warnings, memory status, Human Gate behavior, pass/fail or review-needed status,
and links to the underlying artifacts. Per-scenario outputs should include a
demonstration checklist, a fit summary when applicable, a route trace, and an
actual-vs-expected comparison.

The verified live demo outcomes are:

- `phase10c_clean_fit`: low risk, `accept_mock_result`, accepted memory.
- `phase10c_noisy_valid_fit`: low risk, `accept_mock_result`, accepted memory.
- `phase10c_fit_window_contamination`: medium risk, `human_review_recommended`, pending memory.
- `phase10c_normalization_violation`: high risk, `pending_human_approval`, Human Gate, pending memory.
- `phase10c_targeted_rerun`: medium risk, `targeted_rerun`, rerun target `analysis_engineer`, pending memory.

By default, the demo writes to `outputs/l64c64a076_m140/<run_id>/`. Set
`LQCD_AGENT_OUTPUT_DIR` and `LQCD_AGENT_RUN_ID` to override the output root or
run id. The demo intentionally remains synthetic and high risk, so accepted
memory must remain false without a valid human decision.

Canonical run result path:

```text
<output_root>/<case_id>/<run_id>/
```

Repository examples should use:

```bash
--output-dir outputs
```

which yields:

```text
outputs/<case_id>/<run_id>/
```

`outputs/` is the repo-local actual-run output root. Existing historical files under `outputs/` are ignored generated artifacts, not reference outputs and not schema acceptance evidence.

For verification that should not write repo outputs, use a temporary output root such as `/private/tmp/lqcd-agent-smoke`. If `--run-id` is omitted, the CLI generates a timestamped run id. If `--run-id` is explicit, choose an unused value unless the run directory contains only handoff setup files.

The CLI refuses to reuse a run directory that already contains completed or decision artifacts such as `run_result.json`, `manifest.json`, `scientific_review_report.json`, `decision_log.json`, `final_report.md`, or `memory_update.json`. It does not currently implement `--resume` or `--force`.

The Phase 8 synthetic evaluation runner writes actual run artifacts and `evaluation_summary.csv` under `/private/tmp/lqcd-agent-phase8-evaluation` by default. Future curated evaluation baselines belong under `evaluation/reference_outputs/`, with expected risk/action/warning behavior under `evaluation/expected_behavior/`; neither belongs under `outputs/`.

The evaluation runner refuses to delete existing per-case run directories by
default. Use a fresh generated prefix, pass a unique run id prefix from Python,
or use `python evaluation/run_evaluation.py --force-clean` only when replacing
synthetic evaluation artifacts is intentional.

Before final response on any implementation ticket, perform the stale-documentation scan described in [Prompt Playbook](PROMPT_PLAYBOOK.md).

## MVP Output Classes

Expected output classes:

- method plan
- synthetic matrix-element outputs
- run result
- manifest
- scientific review report
- decision log
- approval packet for high and critical cases
- checkpoint metadata
- final report
- pending memory for medium outcomes
- pending approval packet plus pending memory/report artifacts for high and critical outcomes until a valid human decision is present
- evaluation summary for synthetic good, ambiguous, and bad cases

## Future Test Categories

- Unit tests for state initialization, routing, checkpoint metadata, and context summarization.
- Artifact schema validation for method, run, review, decision, approval, memory, and report outputs.
- Smoke tests for good, ambiguous, and bad synthetic cases.
- Provider tests that use deterministic mock output by default and optional explicit mock-provider graph wiring.
- Optional live-provider tests only when `RUN_LIVE_LLM_TESTS=1` and local provider environment variables are present.

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
