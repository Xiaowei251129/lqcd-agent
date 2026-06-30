# LQCD Agent

This repository contains an initial mock-first implementation of an AI-assisted, auditable LQCD meson distribution-amplitude workflow. The MVP target is a mock-only pion quasi-DA case coordinated by a LangGraph multi-agent runtime.

The project does not make final physics claims, does not read real raw numeric data, and the graph runtime uses deterministic agents unless an LLM provider config is explicitly supplied. Human approval is required for high or critical risk outcomes before accepted memory can be written.

## Current Status

The repository has completed the source-of-truth documentation pass, the repository skeleton, the initial real LangGraph mock runtime skeleton, the standalone deterministic Method Planner module, Phase 2B Method Planner graph integration, Phase 3 Codex Handoff integration, Phase 4 Analysis Engineer integration, Phase 5 Scientific Reviewer diagnostics, Phase 6 Decision Coordinator risk rubric, Phase 7 Human Approval Gate integration, Phase 8 Memory, Final Report, and Synthetic Evaluation Harness implementation, Phase 9 Golden Example productization, Phase 10 provider abstraction with secure dry-run configuration, Phase 10B provider-backed agent wiring, and Phase 10C advisor-demo synthetic benchmarks.

The graph method planner node calls the standalone Method Planner, the graph analysis node calls the standalone Analysis Engineer, the graph reviewer node calls the standalone Scientific Reviewer, the graph decision node calls the standalone Decision Coordinator, the graph approval node writes file-based approval packets, and the graph memory/report node calls dedicated memory and final-report modules. Method Planner, Scientific Reviewer, and Decision Coordinator remain deterministic by default, but can use provider-backed structured output when `--llm-provider-config` is supplied. The no-code low-risk path writes `run_result.json`, `manifest.json`, `run.log`, synthetic mock analysis outputs, `scientific_review_report.json`, `decision_log.json`, `memory_update.json`, and `final_report.md` under the canonical run path. Planner `needs_more_info` outcomes stop safely as `pending` before analysis; `code_needed=true` writes `coder_task_packet.yaml` and routes to Codex Handoff. Medium outcomes remain pending memory; high and critical outcomes generate `approval_packet/` artifacts and can write pending `memory_update.json` plus `final_report.md` while waiting for a structured human decision. The synthetic Phase 8 evaluation harness covers good, ambiguous, and bad cases without reading real raw numeric data. The Phase 9 golden demo links to the sibling `l64c64a076_m140` example as read-only provenance while keeping analysis output synthetic. The Phase 10C benchmark runs separate advisor-demo scenarios under `evaluation/synthetic_benchmarks/`, keeps instructor-only expected behavior out of agent inputs, and writes per-scenario checklists plus `synthetic_rehearsal_summary.md`; optional live-provider runs also write `advisor_demo_report.md`. Real raw-data-backed evaluation, databases, and production deployment remain deferred.

The canonical run result path is `<output_root>/<case_id>/<run_id>/`. Repo-local `outputs/` is for ignored actual-run artifacts only; future curated evaluation baselines belong under `evaluation/reference_outputs/`, not under `outputs/`. For verification, prefer a temporary output root such as `/private/tmp/lqcd-agent-smoke`. If `--run-id` is omitted, the CLI generates a timestamped run id.

## Directory Structure

```text
.
├── AGENTS.md                      # Root AI coding contract
├── configs/
│   ├── cases/
│   │   ├── mock_lqcd_goal.yaml    # Placeholder synthetic case config
│   │   └── l64c64a076_m140.yaml   # Conservative golden demo case config
│   └── runtime/
│       ├── mock_llm.yaml          # Placeholder deterministic mock provider config
│       ├── openai.yaml            # OpenAI provider config with env-var placeholders
│       └── deepseek.yaml          # DeepSeek provider config with env-var placeholders
├── docs/                          # Source-of-truth project documentation
├── evaluation/                    # Synthetic Phase 8 and Phase 10C evaluation runners
├── outputs/
│   └── .gitkeep                   # Keeps the future output root in version control
├── scripts/
│   └── run_langgraph_demo.sh      # One-command Phase 9 golden mock demo
├── src/
│   └── lqcd_agent/
│       ├── agents/                # Standalone deterministic agent modules
│       ├── analysis/              # Scientific Reviewer diagnostic helpers
│       ├── coder/                 # File-based handoff artifact helpers
│       ├── graph/                 # LangGraph mock runtime, routing, and CLI
│       ├── llm/                   # Provider abstraction, mock provider, and dry-run config loader
│       ├── memory/                # Memory update classification and query helpers
│       ├── report/                # Final Markdown report generation
│       ├── tools/                 # Repository inventory, command, validation, and manifest helpers
│       └── __init__.py            # Package marker
├── tests/
│   ├── test_graph_smoke.py
│   ├── test_import.py
│   ├── test_llm_config.py
│   ├── test_llm_mock_provider.py
│   ├── test_synthetic_benchmarks.py
│   ├── test_analysis_engineer.py
│   ├── test_approval_packet.py
│   ├── test_command_runner.py
│   ├── test_coder_task_packet.py
│   ├── test_decision_coordinator.py
│   ├── test_manifest.py
│   ├── test_method_planner_mock.py
│   ├── test_evaluation.py
│   ├── test_memory.py
│   ├── test_report.py
│   ├── test_routing.py
│   ├── test_scientific_reviewer.py
│   ├── test_state_schema.py
│   └── test_test_runner.py
├── pyproject.toml                 # Packaging metadata
└── README.md
```

## Install and Verify

```bash
pip install -e .
pytest tests/test_approval_packet.py tests/test_routing.py tests/test_graph_smoke.py -q
pytest tests/test_memory.py tests/test_report.py tests/test_evaluation.py tests/test_graph_smoke.py -q
pytest tests/test_llm_config.py tests/test_llm_mock_provider.py -q
pytest tests/test_method_planner_mock.py tests/test_scientific_reviewer.py tests/test_decision_coordinator.py tests/test_graph_smoke.py tests/test_state_schema.py -q
python -m lqcd_agent.llm.provider_factory --config configs/runtime/openai.yaml --dry-run
python -m lqcd_agent.llm.provider_factory --config configs/runtime/deepseek.yaml --dry-run
python -m lqcd_agent.graph.run_graph --case configs/cases/mock_lqcd_goal.yaml --output-dir /private/tmp/lqcd-agent-provider-smoke --run-id provider_mock --llm-provider-config configs/runtime/mock_llm.yaml
python -m lqcd_agent.graph.run_graph --case configs/cases/mock_lqcd_goal.yaml --output-dir /private/tmp/lqcd-agent-smoke
python evaluation/run_evaluation.py
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py --provider mock --case-set demo --output-dir /private/tmp/lqcd-agent-phase10c-mock
python -m lqcd_agent.demo.server --once-smoke --output-root /private/tmp/lqcd-agent-demo-smoke
python -m lqcd_agent.demo.server --host 127.0.0.1 --port 8765
bash scripts/run_langgraph_demo.sh
```

With `--output-dir outputs --run-id phase8_smoke`, the mock case writes to `outputs/mock_lqcd_goal/phase8_smoke/`. `bash scripts/run_langgraph_demo.sh` writes the golden mock demo to `outputs/l64c64a076_m140/<run_id>/` by default and accepts `LQCD_AGENT_OUTPUT_DIR` and `LQCD_AGENT_RUN_ID` overrides. The golden demo intentionally produces high-risk pending artifacts: `approval_packet/`, `memory_update.json` with `accepted_result: false`, and `final_report.md`. Choose an unused explicit `--run-id`; the CLI refuses to reuse a run directory that already contains completed or decision artifacts. `python evaluation/run_evaluation.py` writes actual run artifacts and `evaluation_summary.csv` under `/private/tmp/lqcd-agent-phase8-evaluation` by default, and it refuses to delete existing evaluation run directories unless `--force-clean` is passed. The Phase 10C mock benchmark is network-free and writes run artifacts plus `synthetic_rehearsal_summary.md` under the selected output root; live-provider rehearsal requires `RUN_LIVE_LLM_TESTS=1` and `--provider-config`. Resume and force-overwrite modes for graph runs are deferred to future explicit tickets.

## Local Chat Demo

Run the local scientific chat demo with:

```bash
python -m lqcd_agent.demo.server --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

The chat UI asks for a question plus a case config selected from `configs/cases/*.yaml`. The server writes the question into a generated copy of that config as the graph `physics_goal`, runs the existing LangGraph multi-agent system, and answers from the resulting artifacts. If `--llm-provider-config` is omitted, the graph uses deterministic local agents and does not call an external model API. Pass `--llm-provider-config configs/runtime/openai.yaml` or another provider config only after the required API environment variables are available. Actual run artifacts are written under `/private/tmp/lqcd-agent-demo-ui`, with route, risk/action, Human Approval Gate status, memory status, and artifact links shown in a compact evidence panel.

## Documentation Map

- [Project Specification](docs/PROJECT_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [State Schema](docs/STATE_SCHEMA.md)
- [Artifact Contracts](docs/ARTIFACT_CONTRACTS.md)
- [Verification Guide](docs/VERIFICATION_GUIDE.md)
- [Prompt Playbook](docs/PROMPT_PLAYBOOK.md)
- [Repository Current State](docs/REPO_CURRENT_STATE.md)
- [Tickets](docs/TICKETS.md)
