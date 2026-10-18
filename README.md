# LQCD Agent

2026-10-17：B04 canonical schema0.4产品图已交付。显式Python入口为`lqcd_agent.graph.run_graph.run_canonical_graph(coordinator=..., request=StartRunRequest(...), actor=..., agent_port=..., analysis_handoff=..., code_host=..., external_adapter=...)`，只创建new Run并返回run_locator/state/runtime；Code路径使用Fake Backend和原Host。原默认legacy0.2 CLI保留。验收full4749、owned1410/645/144及construction15/11/30/28/47通过；B05仍draft，Phase B未完成。见[完成记录](docs/tickets/completions/B04_COMPLETION.md)。以下日期条目保留历史。

2026-10-14 当前：**C25 completed；C24 经独立入口复核恢复 ready；C23/B04 保持 blocked**。四类原 spawn 入口使用真实 request 的 Session；144 个原用例各完成两份 fresh native 诊断，原 hook/receipt/raw 全部保留，正式 B04 owned 仍 0/144。共同固定输入完整 **4578/4578**（含 legacy325、新 C25 29）、同 Session 独立 owned **B02 1410/B03 645**、来源90项/16类双 fresh/8个四消费者188组拒绝、停止路由7项、fresh construction **15/11/30/28** 通过；final 精确仍 **47/144/15**。C24/C23 原整票交接及 B04 入口仍须独立完成；Phase B false。验收代码与随后文档/lifecycle交付分别存档，无 commit/push。见[完成与交接记录](docs/tickets/completions/B00C25_COMPLETION.md)。以下日期条目保留历史。

2026-10-14：**修订版C25获用户批准并进入in_progress；C24/C23/B04保持blocked**。本次同时处理真实child Session交接和独立native诊断hook隔离，原registry/validator/owners保持；专项与完整验收正在执行，尚无整票通过声明。见[执行记录](docs/tickets/completions/B00C25_COMPLETION.md)。无commit/push，以下历史保留。

2026-10-08最新：**C15/C16/C17/C18/C19/C20 completed；B04 ready**。C20补齐C10当前failure显式0.8入口，保留旧版本拒绝；C18与C15–C17各自原要求已独立复核，共同固定Session完整**4139/4139**、legacy325、同Sessionowned**B02 1410/B03 645**、construction**15/11/30/28**及final具体**47/144/15**通过。见[C20完成记录](docs/tickets/completions/B00C20_COMPLETION.md)、[C18完成记录](docs/tickets/completions/B00C18_COMPLETION.md)和[B04独立入口](docs/tickets/completions/B04_COMPLETION.md)。B04按原授权经独立入口核对恢复ready，尚未completed/owned0-of-144；Code parent/fallback/fresh Analysis/publication及47/144仍待执行，B05draft、PhaseBfalse、131/84/47、2199/15/owners保持。验证输入与随后文档交付manifest分开，无commit/push。下列日期条目保留历史。

2026-10-08当前接续：**C20/C18 in_progress；C15/C16/C17/B04 blocked**。C10显式来源入口修复及原测试/新专项通过，C18依原授权恢复最终验收；[C20记录](docs/tickets/completions/B00C20_COMPLETION.md)。尚未声明完整当前Session通过，旧版本/production/131/84/47/2199/15/owners保持，未commit/push；下列条目保留历史。

2026-10-08当前：用户批准执行[C20](docs/tickets/phase-b-graph-harness/B00C20_C10_CURRENT_FAILURE_SOURCE_VERSION_HANDOFF.md)，ready正文已冻结，现**in_progress**。仅交接C10当前failure显式来源入口，原0.6/0.7规则和production保持；实际结果见[C20记录](docs/tickets/completions/B00C20_COMPLETION.md)。C18/C17/C16/C15/B04仍blocked，C19completed；完整固定Session尚未重验，未commit/push。下列条目保留历史。

2026-10-08当前：**C19 completed；C18/C17/C16/C15/B04 blocked；C20 review**。C19可达性验收已交付，C18按原授权补齐专项；同Session实跑4122项，4120 passed、2项C10失败。mixed派生expected已审计同步并fresh复验；剩余C10当前失败入口仍走0.6，显式交接超出冻结清单，见[C20待审](docs/tickets/phase-b-graph-harness/B00C20_C10_CURRENT_FAILURE_SOURCE_VERSION_HANDOFF.md)与[C18实际记录](docs/tickets/completions/B00C18_COMPLETION.md)。owned B02 1410/B03 645、construction15/11/30/28及final具体47/144/15已在该执行输入核验；未声明新交付输入full通过。B04 owned0/144、131/84/47、2199/15/owners保持，未commit/push。下列条目保留历史。

2026-10-07当前接续：**C19 completed，C18 in_progress**。C19交付输入/原冻结摘要已复核，依原授权恢复C18其余H1–V2；原生产候选保持，先补预算publication故障表及来源核验。见[C18记录](docs/tickets/completions/B00C18_COMPLETION.md)。C15/C16/C17/B04仍blocked，尚无当前完整Session/owned通过声明，B04 owned0/144及131/84/47、2199/15/owners保持；未commit/push。下列条目保留历史。

2026-10-07当前：**C19 completed**。不可达 Human transition 阈值的窄验收补充已交付：8项证明、72项 contract-only 及7项原端口/回归通过（含C18三组双fresh、六份新ledger见证）。生产/冻结正文/原验收集合保持。见[C19记录](docs/tickets/completions/B00C19_COMPLETION.md)。C18原授权可在输入复核后接续；C15/C16/C17/B04仍blocked，C18其余H1–V2及最终full Session尚未完成，B04 owned0/144、131/84/47、2199/15/owners保持。未commit/push；下列较早条目保留历史。

2026-10-07当前：**C18/C17/C16/C15/B04 blocked，C19 review**。C18 两项候选修复的三组双 fresh 和原 C13 两项通过；原固定 policy 下独立 transition 容量阈值不可达，冻结原端口验收条款需窄补充。见[C18记录](docs/tickets/completions/B00C18_COMPLETION.md)与[C19待审](docs/tickets/phase-b-graph-harness/B00C19_HUMAN_CAPACITY_REACHABILITY_ACCEPTANCE.md)；C19 未批准/实施。完整 C15–C17 验收及当前 full Session/owned 尚未完成，B04 owned0/144、131/84/47、2199/15/owners 保持，未 commit/push。下列较早条目保留历史。

2026-10-07 C18执行：用户授权修订版 C18，ready 正文冻结后进入 **in_progress**。普通/terminal repause 修复及 C15–C17 全部逐项验收正在执行；**C15/C16/C17/B04 仍 blocked**，尚无当前整票/full Session 通过声明，B04 owned0/144、131/84/47、2199/15/owners 保持。见[C18执行记录](docs/tickets/completions/B00C18_COMPLETION.md)。未 commit/push；下列较早条目保留历史。

2026-10-07当前：**C17/C16/C15/B04 blocked，C18 review**。C17原terminal路由修复及5项专项通过；普通invalid response后repause错用terminal容量，合法纠正被原Resume拒绝；terminal invalid→纠正双fresh另暴露repause proposal raw-head来源未规范绑定。越界修复依冻结Stop停止，反例见[C17记录](docs/tickets/completions/B00C17_COMPLETION.md)；[C18 修订待审](docs/tickets/phase-b-graph-harness/B00C18_ORDINARY_REPAUSE_CAPACITY_SOURCE_HANDOFF.md)现承接 C15–C17 全部冻结验收：补齐 Human 全链、FP/Grant、完整预算故障表与四消费者逐项证据，区分预期 recovery/拒绝与真正 Stop，使用稳定候选的同一最终 Session。此次仅文档修订，未批准/实施；C15–C17 冻结正文不改。无完整当前Session/owned验收通过声明，B04owned0/144、131/84/47、2199/15及owners保持，未commit/push。下列较早状态保留历史。

2026-10-07当前：用户授权修订并执行C17，已明确合法幂等重试与非法重复消费边界，ready正文冻结后进入 **in_progress**。原Human容量/terminal接续及C16全部验收正在执行；**C16/C15/B04仍blocked**，B04 owned0/144及131/84/47、2199/15/原owners保持，未commit/push。见[C17执行记录](docs/tickets/completions/B00C17_COMPLETION.md)；以下较早状态保留历史。

2026-10-07当前：**C16 blocked、C17 review、C15/B04 blocked**。C16来源候选与七组双fresh fixed expected已保存，生产源码保持；C13三项terminal收尾因重复失败先进入普通Human、control=5无sequence而被原Resume拒绝，需生产路由修复，超出C16冻结范围。[C17待审](docs/tickets/phase-b-graph-harness/B00C17_REPEAT_ESCALATION_TERMINAL_RESERVE_HANDOFF.md)未批准/实施，见[C16反例记录](docs/tickets/completions/B00C16_COMPLETION.md)。无完整当前Session/owned验收通过声明；B04 owned0/144、131/84/47、2199cases/15exit及原owners保持，未commit/push。下列较早状态保留历史。

2026-10-07 C16当前：**in_progress**，显式0.8 canonical audit/独立owner来源及当前Human入口交接已形成候选，双fresh七组固定expected与前置摘要审计已完成；当前四消费者、完整固定Session及owned/construction/final验收仍在进行。见[C16执行记录](docs/tickets/completions/B00C16_COMPLETION.md)与[候选来源合同](docs/tickets/corrections/B00C16_CANONICAL_CODE_AUDIT_SOURCE_CONTRACT.md)。**C15/B04仍blocked**，B04 owned0/144、131/84/47、2199cases/15exit及原owners保持，未commit/push。较早条目保留历史。

2026-10-07 C16批准登记：用户明确“批准C16”，[C16](docs/tickets/phase-b-graph-harness/B00C16_CANONICAL_CODE_AUDIT_SOURCE_HANDOFF.md)由review提升为 **ready**，正文冻结SHA256=`e7c10364d4dae3a982f36724f19c4db9cc57d2334d033a1473e259de8c8c7fc6`。本次仅登记批准，尚未启动实施；**C15/B04保持blocked**，来源缺口及整票验收尚未解除，B04 owned0/144、131/84/47、2199cases及15exit保持。冻结仅在当前worktree及私有审计副本，无committed snapshot，未commit/push；下列早前状态保留为历史检查点。

2026-10-07当前交接：C15按授权已执行部分Host fingerprint/Grant与0.8来源，部分18项专项通过；canonical Code audit/fresh Analysis来源触发未列profile的冻结Stop，**C15 blocked、C16 review、B04 blocked**。候选来源profile已撤回，整票当前Session/owned/construction尚未完成，B04owned0/144及131/84/47/15exit保持。见[C15实际记录](docs/tickets/completions/B00C15_COMPLETION.md)；以下历史检查点保留。

2026-10-07：B04 接续的 Planner/ordinary 主路径局部修复已验证，现因合法因果 fingerprint 的来源边界停止；[C15待审](docs/tickets/phase-b-graph-harness/B00C15_PRODUCT_FAILURE_FINGERPRINT_AND_GRANT_SOURCE_HANDOFF.md)仅review。B04 blocked、owned0/144，B05 draft、Phase B未完成。当前事实见[状态](docs/REPO_CURRENT_STATE.md)与[B04记录](docs/tickets/completions/B04_COMPLETION.md)，以下较早状态为历史检查点。

This repository contains a demo-ready, mock-first implementation of an AI-assisted, auditable LQCD meson distribution-amplitude workflow. The current stable baseline supports a synthetic pion quasi-DA case coordinated by a LangGraph multi-agent runtime.

The project does not make final physics claims, does not read real raw numeric data, and the graph runtime uses deterministic agents unless an LLM provider config is explicitly supplied. Human approval is required for high or critical risk outcomes before accepted memory can be written.

## Current Status

The repository has completed the source-of-truth documentation pass, the repository skeleton, the initial real LangGraph mock runtime skeleton, the standalone deterministic Method Planner module, Phase 2B Method Planner graph integration, Phase 3 Codex Handoff integration, Phase 4 Analysis Engineer integration, Phase 5 Scientific Reviewer diagnostics, Phase 6 Decision Coordinator risk rubric, Phase 7 Human Approval Gate integration, Phase 8 Memory, Final Report, and Synthetic Evaluation Harness implementation, Phase 9 Golden Example productization, Phase 10 provider abstraction with secure dry-run configuration, Phase 10B provider-backed agent wiring, Phase 10C advisor-demo synthetic benchmarks, and the Phase 10D demo-console and LLM-auditability milestone.

The graph method planner node calls the standalone Method Planner, the graph analysis node calls the standalone Analysis Engineer, the graph reviewer node calls the standalone Scientific Reviewer, the graph decision node calls the standalone Decision Coordinator, the graph approval node writes file-based approval packets, and the graph memory/report node calls dedicated memory and final-report modules. Method Planner, Scientific Reviewer, and Decision Coordinator remain deterministic by default, but can use provider-backed structured output when `--llm-provider-config` is supplied. The no-code low-risk path writes `run_result.json`, `manifest.json`, `run.log`, synthetic mock analysis outputs, `scientific_review_report.json`, `decision_log.json`, `memory_update.json`, and `final_report.md` under the canonical run path. Provider-backed runs also write request/response audit records under `llm_calls/`, record them in the manifest, and link them from the final report. Planner `needs_more_info` outcomes stop safely as `pending` before analysis; `code_needed=true` writes `coder_task_packet.yaml` and routes to Codex Handoff. Medium outcomes remain pending memory; high and critical outcomes generate `approval_packet/` artifacts and can write pending `memory_update.json` plus `final_report.md` while waiting for a structured human decision. The synthetic Phase 8 evaluation harness covers good, ambiguous, and bad cases without reading real raw numeric data. The Phase 9 golden demo links to the sibling `l64c64a076_m140` example as read-only provenance while keeping analysis output synthetic. The Phase 10C benchmark runs separate advisor-demo scenarios under `evaluation/synthetic_benchmarks/`, keeps instructor-only expected behavior out of agent inputs, and writes per-scenario checklists plus `synthetic_rehearsal_summary.md`; optional live-provider runs also write `advisor_demo_report.md`. Phase 10D adds YAML/JSON case discovery, runtime-provider selection, live-provider guards, command previews, richer artifact links, and run-level LLM audit visibility to the local console. Real raw-data-backed evaluation, databases, and production deployment remain deferred.

The canonical run result path is `<output_root>/<case_id>/<run_id>/`. Repo-local `outputs/` is for ignored actual-run artifacts only; future curated evaluation baselines belong under `evaluation/reference_outputs/`, not under `outputs/`. For verification, prefer a temporary output root such as `/private/tmp/lqcd-agent-smoke`. If `--run-id` is omitted, the CLI generates a timestamped run id.

Historical B04 checkpoint (2026-10-05; superseded by the canonical delivery note above): Phase B04 adds the explicit Python entry point `lqcd_agent.graph.run_graph.run_canonical_graph` for a new schema 0.4 Run and remains under construction. B00C11 and B00C12 completed the trace 0.7 / proof 0.4 source handoff; see [the C11 contract](docs/tickets/corrections/B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_CONTRACT.md) and [the C12 supplement](docs/tickets/corrections/B00C12_HUMAN_REQUEST_PACKET_TRACE_CONTRACT.md). C13 implemented the Human continuation, distinct diagnostic owners and publication-prefix corrections. [C14](docs/tickets/phase-b-graph-harness/B00C14_HOST_IDENTITY_REJECTION_ASSERTION_HANDOFF.md) is now completed: the original Host identity negative test verifies production rejection before domain publication, and independent member identity negatives preserve the source validator rejection. Its fixed-input Session passed all 3,792 repository tests, B02 1,410/1,410 and B03 645/645 exact owned cases, all 29 C13 checks and 325 legacy tests. Fresh construction passed 15/11/30/28; final diagnostics retain exactly B04's 47 coverage, 144 binding and 15 exit adapter gaps. C13 has resumed in progress to complete its original acceptance review; B04 remains blocked and owns 0/144 runtime cases. See [the C14 completion record](docs/tickets/completions/B00C14_COMPLETION.md), [the C13 record](docs/tickets/completions/B00C13_COMPLETION.md) and [the B04 record](docs/tickets/completions/B04_COMPLETION.md). Planner dependency paths, ordinary exception closure, Code and fallback routes, and B04's 47 construction requirements and 144 owned runtime cases remain pending. Completion documentation is audited separately from the fixed verification input. Phase B remains incomplete; the default CLI continues to use the legacy graph.

The `v0.2-demo` milestone captures the stable demo-ready research MVP. Second-stage work is organized as control-contract clarification, graph-harness verification, graph-managed Code Agent integration, Agent capability improvement, and an integrated benchmark. The tag is a reproducible source snapshot, not a production-readiness claim.

## Directory Structure

```text
.
├── AGENTS.md                      # Root AI coding contract
├── configs/
│   ├── cases/
│   │   ├── mock_lqcd_goal.yaml    # Placeholder synthetic case config
│   │   ├── l64c64a076_m140.yaml   # Conservative golden demo case config
│   │   └── *.input.json           # Registered-program demo case configs
│   └── runtime/
│       ├── mock_llm.yaml          # Placeholder deterministic mock provider config
│       ├── openai.yaml            # OpenAI provider config with env-var placeholders
│       └── deepseek.yaml          # DeepSeek provider config with env-var placeholders
├── docs/                          # Source-of-truth project documentation
├── evaluation/                    # Synthetic Phase 8 and Phase 10C evaluation runners
├── outputs/
│   └── .gitkeep                   # Keeps the future output root in version control
├── raw_data/                      # Small tracked demo fixtures for registered analysis programs
├── scripts/
│   └── run_langgraph_demo.sh      # One-command Phase 9 golden mock demo
├── src/
│   └── lqcd_agent/
│       ├── agents/                # Standalone deterministic agent modules
│       ├── analysis/              # Scientific Reviewer diagnostic helpers
│       ├── coder/                 # File-based handoff artifact helpers
│       ├── graph/                 # LangGraph mock runtime, routing, and CLI
│       ├── llm/                   # Provider abstraction, secure configuration, and LLM call traces
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
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py --provider mock --case-set full --output-dir /private/tmp/lqcd-agent-phase10c-full
python -m lqcd_agent.demo.server --once-smoke --output-root /private/tmp/lqcd-agent-demo-smoke
python -m lqcd_agent.demo.server --host 127.0.0.1 --port 8765
bash scripts/run_langgraph_demo.sh
```

With `--output-dir outputs --run-id phase8_smoke`, the mock case writes to `outputs/mock_lqcd_goal/phase8_smoke/`. `bash scripts/run_langgraph_demo.sh` writes the golden mock demo to `outputs/l64c64a076_m140/<run_id>/` by default and accepts `LQCD_AGENT_OUTPUT_DIR` and `LQCD_AGENT_RUN_ID` overrides. The golden demo intentionally produces high-risk pending artifacts: `approval_packet/`, `memory_update.json` with `accepted_result: false`, and `final_report.md`. Choose an unused explicit `--run-id`; the CLI refuses to reuse a run directory that already contains completed or decision artifacts. `python evaluation/run_evaluation.py` writes actual run artifacts and `evaluation_summary.csv` under `/private/tmp/lqcd-agent-phase8-evaluation` by default, and it refuses to delete existing evaluation run directories unless `--force-clean` is passed. The Phase 10C mock benchmark is network-free and writes run artifacts plus `synthetic_rehearsal_summary.md` under the selected output root; live-provider rehearsal requires `RUN_LIVE_LLM_TESTS=1` and `--provider-config`. Resume and force-overwrite modes for graph runs are deferred to future explicit tickets.

## Local Multi-Agent Console

Run the local scientific multi-agent console with:

```bash
python -m lqcd_agent.demo.server --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

The console discovers YAML and JSON cases under `configs/cases/`, accepts pasted or uploaded configs, previews the analysis route and input status, and exposes the configured deterministic or live runtime providers. It validates the selection, shows the equivalent CLI command, starts a real local LangGraph run, polls the graph path, and displays the final risk/action, memory status, report summary, LLM audit records, and artifact links. Live providers remain blocked unless their configured opt-in environment variable is enabled. If a run reaches Human Approval Gate, the UI opens a decision modal backed by `approval_packet/07_human_decision.yaml`; `approve_with_conditions` and `reject_or_hold` continue to the Memory/Report node, while rerun/code-change decisions remain pending intents in this mock-first phase. If `--llm-provider-config` is omitted, the graph uses deterministic local agents and does not call an external model API. By default, local-console run artifacts are written under the ignored repo-local `outputs/` directory.

## Documentation Map

- [Second-stage Docs Index](docs/README.md)
- [Repository Current State](docs/REPO_CURRENT_STATE.md)
- [`v0.2-demo` Milestone](docs/milestones/V0_2_DEMO_BASELINE.md)
- [Next-stage Improvement Directions](docs/NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md)
- [Project Specification](docs/PROJECT_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [State Schema](docs/STATE_SCHEMA.md)
- [Artifact Contracts](docs/ARTIFACT_CONTRACTS.md)
- [Verification Guide](docs/VERIFICATION_GUIDE.md)
