# AI-assisted LQCD Meson DA Analysis Agent

## 用 Codex 构建多 Agent LangGraph 架构的总体实施计划

本版按“先澄清、先冻结规格、再小步实现”的方式重构，加入 pre-phase0、AI 边界、项目化 AGENTS.md、统一 Codex ticket/prompt 合同，并将 Codex Coder Agent 改名为 Codex Handoff Node。

# 0. 本版执行结论

本版计划保留原始方案中最有价值的主干：5 个核心 agent + 2 个支撑节点，但把执行顺序和 Codex 交互方式重构为“先苏格拉底式澄清、再创建 source-of-truth docs、再用真实 LangGraph StateGraph 做最小 skeleton、最后逐 phase 扩展”。

- AGENTS.md：由本次修订直接提供项目化版本，作为 repo 根目录的首要 AI 合同。

- CLAUDE.md：删除，不再维护第二套规则。若未来使用 Claude Code，也应直接遵循 AGENTS.md。

- docs/*.md：不要由本文一次性替你写死。应在 pre-phase0 由 Codex 先采访、再按你的回答生成和更新，避免在需求未确认前过早冻结。

- Phase 1：不再写 LangGraph-style 自制状态机，而是从一开始使用真实 LangGraph StateGraph；节点内部可以先 mock。

- Codex Coder Agent：改名为 Codex Handoff Node，避免误实现为运行时程序化调用 Codex。

- 所有 Codex prompt：统一改成 ticket contract，包括 Read First、Allowed Files、Do Not Touch、Requirements、Non-goals、Acceptance Criteria、Verification Commands、Stop Conditions、End-of-task Updates。

- Phase 10/11：前九个 phase 跑通后，再接入真实 LLM provider 和 raw_data/evaluation case library；真实密钥只通过本地 .env，raw data 只读。

# 1. 第一原则：不要先写代码，先冻结可审查规格

大项目中最危险的做法是让 Codex 直接“搭一个多 agent 系统”。正确顺序是：先让 AI 采访你，追问不清楚的科研目标、数据边界、审批边界和 MVP 范围；然后生成 source-of-truth docs；你确认后再进入 repo skeleton 和代码实现。

| 原则 | 具体要求 | 落地方式 |
| --- | --- | --- |
| 先问后写 | pre-phase0 只做苏格拉底式对话，不创建代码。 | Codex 先提问、总结 confirmed / unresolved / risk / MVP / non-goals。 |
| 文档先于实现 | 架构、状态、artifact、agent 边界先进入 docs。 | docs/PROJECT_SPEC.md、ARCHITECTURE.md、STATE_SCHEMA.md 等。 |
| 小 ticket 实现 | 每个 phase 只改允许范围，不做顺手重构。 | Allowed Files / Do Not Touch / Acceptance Criteria。 |
| 验证优先 | 每个任务必须有可运行的 verification commands。 | pytest、smoke run、schema validation、demo command。 |
| AI 有边界 | Codex 和 LLM agents 不能做最终科学决策。 | high/critical risk 必须进入 Human Approval Gate。 |

# 2. AI 可反复读取的项目文件策略

本版采用“两层文件策略”：根目录 AGENTS.md 现在就由人工确认并放入 repo；docs/*.md 由 Codex 在 pre-phase0 采访后生成，因为这些文档依赖你对科研目标、数据、MVP 和审批边界的回答。这样既能先固定 AI 行为规则，又不会让项目文档在需求未确认前变成错误的权威。

| 文件 | 创建时机 | 谁创建 / 维护 | 用途 |
| --- | --- | --- | --- |
| AGENTS.md | 现在 | 本次修订直接提供；以后人工批准后再改 | Codex 的 repo-level 工程合同。 |
| CLAUDE.md | 不创建 | 删除 | 避免维护第二套规则。 |
| docs/PROJECT_SPEC.md | pre-phase0 | Codex 根据访谈生成，你确认 | 目标、MVP、非目标、golden example。 |
| docs/ARCHITECTURE.md | pre-phase0 | Codex 生成，你确认 | LangGraph 拓扑、节点、边、循环、终止条件。 |
| docs/AGENT_ROLES_AND_BOUNDARIES.md | pre-phase0 | Codex 生成，你确认 | 各 agent/node 能做什么、不能做什么。 |
| docs/STATE_SCHEMA.md | pre-phase0 + Phase 1 | Codex 初稿，Phase 1 实现时同步 | AnalysisState 字段、含义、不变量。 |
| docs/ARTIFACT_CONTRACTS.md | pre-phase0 + Phase 0 | Codex 初稿，后续维护 | JSON/YAML/Markdown artifact schema。 |
| docs/TICKETS.md | pre-phase0 + Phase 0 | Codex 生成并逐 phase 更新 | 分阶段 ticket、允许范围、验收标准。 |
| docs/VERIFICATION_GUIDE.md | Phase 0 | Codex 创建，后续维护 | 测试、smoke run、demo、eval 命令。 |
| docs/REPO_CURRENT_STATE.md | Phase 0 | Codex 创建，每次任务更新 | 当前 repo 状态、已完成、未完成、阻塞点。 |
| docs/DECISION_LOG.md | Phase 0 | Codex 创建，架构变更时更新 | 为什么采用某设计，为什么拒绝替代方案。 |
| docs/PROMPT_PLAYBOOK.md | Phase 0 | Codex 创建初版，后续随 tickets 维护 | 标准 ticket contract、phase prompt wrapper、end-of-task summary；至少包含 node implementation 与 diagnostic module 两个 worked examples。 |
| docs/SECURITY_AND_DATA_POLICY.md | Phase 0 | Codex 创建，后续维护 | raw data、secrets、外部命令、覆盖策略。 |
| docs/EVALS_AND_OBSERVABILITY.md | Phase 8 前至少有 skeleton；Phase 11 扩展真实/半真实 cases | Codex 创建，后续扩展 | synthetic good/ambiguous/bad cases、trace、metrics；Phase 11 加入 raw_data-backed evaluation library。 |

# 3. 总目标与系统边界

系统输入是一个 physics goal 和一个 case config。例如：分析某个 ensemble 的 pion quasi-DA matrix elements，检查不同 Pz 下的 bare/normalized matrix elements，并准备后续 Fourier transform 或 matching。系统输出不是单一答案，而是一组可追踪 artifacts：method_plan.json、analysis outputs、scientific_review_report.json、decision_log.json、approval_packet、memory update、final_report.md。

系统不是简单 chatbot，不是 notebook wrapper，也不是让 AI 无监督决定论文结果。系统要做的是：把 routine labor、代码生成、数据检查、诊断报告、风险分级和可复现记录尽量交给 agents；把 central fit、final systematic uncertainty、accepted result promotion、paper-level claim 等高风险决策保留给 Human Approval Gate。

| 设计目标 | 具体含义 | 落地 artifact |
| --- | --- | --- |
| 可复现 | 所有运行由 config、schema、workflow、graph state 驱动。 | configs/*.yaml, manifest.json, graph_state.json |
| 可审计 | 保存每个 agent 的输入、输出、理由、evidence、routing。 | llm_calls/, agent_reports/, decision_log.json |
| AI-first | routine work 优先交给 AI/Codex/工具，但不越过科学边界。 | CLI, tests, graph nodes, reports |
| Risk-based | low 自动推进；medium 标记 pending；high/critical 触发审批或 halt。 | risk_level, approval_packet/ |
| 科研可用 | 从 mock 到 golden example，再逐步接入真实 meson DA workflow。 | evaluation cases + golden example + raw_data manifest |

# 4. AI Boundary Policy

AI 边界应写入 AGENTS.md 和 docs/AGENT_ROLES_AND_BOUNDARIES.md。它不是附加说明，而是系统安全和科研可信度的一部分。

| 对象 | 允许做什么 | 禁止做什么 |
| --- | --- | --- |
| Codex | 实现 repo skeleton、schema、LangGraph runtime、测试、CLI、artifact generator、文档更新。 | 不决定 central fit；不写 final physics conclusion；不修改 raw data；不引入未授权依赖；不在未授权 phase 调用真实外部 API；不请求、打印、存储或提交真实 API key；不做大范围无关重构。 |
| LLM Agents | 结构化理解目标、给出诊断、提出 warning、建议下一步。 | 不伪造文献或数据；不把自由文本作为 route 依据；不自动 promotion high/critical risk；不输出未审批 paper-level claim。 |
| Human Approval Gate | 审批 high/critical risk、final promotion、paper-level claim、关键 rerun/code change。 | 不作为每一步 always-on gate；不由 agent 改写人类决定。 |
| Analysis Runtime | 读取 config、执行安全命令、写 `<output_root>/<case_id>/<run_id>/` 下的结果和 manifest。 | 不覆盖 raw_data；不覆盖 accepted results；不隐藏失败；不丢弃 provenance。 |

# 5. Raw Data、Overwrite 与 Provenance Policy

- raw_data/ 是只读目录；任何 agent、Codex 或命令 runner 都不得写入。

- 所有派生结果必须写入 `<output_root>/<case_id>/<run_id>/`，不得直接覆盖旧 run。

- accepted results 和 human decisions 必须 append-only 或 versioned。

- 除非 ticket 明确允许 --force，否则不得覆盖已有输出目录。

- `outputs/` 是本地 actual-run output root。其下历史 run artifacts 是 ignored generated artifacts，不是 schema 验收证据，也不是 reference outputs。

- Codex/agent 验证命令应优先使用临时 output root，例如 `/private/tmp/lqcd-agent-...`，或使用唯一 `--run-id`，避免旧 `outputs/` 内容误导检查。用户显式 demo 或想保留本地 run 记录时可以使用 `--output-dir outputs`。

- CLI 未显式传入 `--run-id` 时应生成时间戳 run id；显式传入时必须按原值使用。如果目标 run directory 已含完成态或决策态 artifacts，应拒绝复用并提示选择新 run id。默认不得 resume 或 overwrite；`--resume` 和 `--force` 必须由未来 ticket 明确定义。

- 所有外部命令必须通过安全 command_runner 运行，记录 command、return code、stdout/stderr、timeout、working directory。

- manifest.json 至少包含 run_id、case_id、timestamp、git commit/status、config hash、input files、output files、commands、tool versions、environment summary、warnings/errors。

- Phase 11 才正式引入 raw_data/ case library；Phase 0–10 可以预留路径和 policy，但不得创建或修改真实 raw data。

- good/ambiguous/bad 的标签和 expected behavior 应保存在 evaluation/ 下，不应混入 raw_data/；raw_data/ 只保存 immutable input data、manifest 和 checksums。

- 未来 curated evaluation baselines 应保存在 `evaluation/reference_outputs/`，expected risk/action/warning/human-gate behavior 应保存在 `evaluation/expected_behavior/`。二者不得混入 `outputs/`。

# 6. 推荐保留的 Agent 与支撑节点

本版保留 5 个核心 agent，并加入 2 个必要支撑节点。第一版不要拆成十几个 LLM agent；Scientific Reviewer 先用三个 section 覆盖 correlator、fit、matrix element 诊断，系统稳定后再考虑拆分。

| 类别 | 正式名称 | 主要职责 | 不能做什么 |
| --- | --- | --- | --- |
| 主干 1 | Method Planner Agent | 把用户目标转成 physics goal、observables、method steps、required inputs/outputs，并判断是否需要 implementation handoff。 | 不写代码；不做最终 physics conclusion；不伪造文献证据。 |
| 主干 2 | Codex Handoff Node | 生成 coder_task_packet.yaml；读取 code_change_summary.md 和 tests_status.json；按测试结果路由。 | 不在运行时程序化调用 Codex；不决定 central fit；不修改 raw data。 |
| 主干 3 | Analysis Engineer Agent | 运行已有或新实现的 analysis workflow，检查输入输出、日志、失败原因，生成 run_result/manifest。 | 不做 fit strategy 决策；不接受/拒绝物理结果；不覆盖 accepted results。 |
| 主干 4 | Scientific Reviewer Agent | 合并 correlator、fit、matrix element 诊断，输出 evidence-based warnings 和 recommended checks。 | 不最终选择 central fit；不删除数据；不自动 promotion high-risk 结果。 |
| 主干 5 | Decision Coordinator Agent | 综合各报告，输出 risk_level、recommended_action、human_approval_required、decision_log。 | 不忽略 severe warning；不把 high risk 自动 promotion；不写代码。 |
| 支撑 1 | Human Approval Gate | high/critical risk 或 final promotion 时生成 approval packet，暂停等待人类 decision。 | 不是 always-on gate；不改写人类决定。 |
| 支撑 2 | Memory & Report Node | 写 accepted/pending/rejected memory、final_report.md、evaluation summary。 | 不删除历史 case；不覆盖人类审批。 |

# 7. LangGraph 总图与 Conditional Edge

Phase 1 开始即使用真实 LangGraph StateGraph。早期可以使用 deterministic mock nodes，但节点接口、state 字段和 routing 条件必须与最终架构一致。

```text
START
  -> Method Planner
  -> Code needed?
       yes -> Codex Handoff Node -> Tests
              -> tests_failed and retry<N -> Codex Handoff Node
              -> tests_passed -> Analysis Engineer
       no  -> Analysis Engineer
  -> Run status?
       failed_due_to_code   -> Codex Handoff Node
       failed_due_to_config -> Method Planner or Human Hold
       success              -> Scientific Reviewer
  -> Decision Coordinator
  -> Decision route
       needs_more_method      -> Method Planner
       code_fix_needed        -> Codex Handoff Node
       targeted_rerun_needed  -> Analysis Engineer
       risk=high/critical     -> Human Approval Gate
       risk=low/medium        -> Memory & Report -> END

Human Approval Gate
  -> approve_with_conditions -> Memory & Report -> END
  -> approve_rerun           -> Analysis Engineer
  -> request_code_change     -> Codex Handoff Node
  -> reject_or_hold          -> Memory & Report -> END
  -> no_response             -> pending state + reminder metadata -> END
```

| From | Condition | To | State 字段 |
| --- | --- | --- | --- |
| Method Planner | code_needed=true | Codex Handoff Node | method_plan_path, coder_task_packet_path, code_needed=true |
| Method Planner | code_needed=false | Analysis Engineer | method_plan_path, code_needed=false |
| Codex Handoff Node | tests_failed and retry_count < max_retry | Codex Handoff Node | tests_status_path, retry_count, errors |
| Codex Handoff Node | tests_passed | Analysis Engineer | code_change_summary_path, tests_status_path |
| Analysis Engineer | run_success=true | Scientific Reviewer | run_result_path, analysis_outputs_dir |
| Analysis Engineer | failed_due_to_code=true | Codex Handoff Node | coder_task_packet_path, errors, failure_type=code |
| Analysis Engineer | failed_due_to_config_or_data=true | Method Planner or Human Hold | errors, failure_type=config_or_data |
| Scientific Reviewer | review_done=true | Decision Coordinator | scientific_review_report_path |
| Decision Coordinator | targeted_rerun_requested=true | Analysis Engineer | decision_log_path, rerun_target |
| Decision Coordinator | code_fix_requested=true | Codex Handoff Node | decision_log_path, coder_task_packet_path |
| Decision Coordinator | risk_level in high/critical | Human Approval Gate | approval_packet_dir, human_approval_required=true |
| Decision Coordinator | risk_level in low/medium | Memory & Report | risk_level, decision_log_path |
| Human Approval Gate | human_decision=approve_rerun | Analysis Engineer | human_decision_path, rerun_target |
| Human Approval Gate | human_decision=reject_or_hold | Memory & Report | final_status=pending_or_rejected |

# 8. AnalysisState 与统一输出规范

AnalysisState 是 graph contract。所有节点只能通过已记录字段读取/更新状态；public schema 改动必须有明确 ticket 和迁移说明。

```python
class AnalysisState(TypedDict):
    run_id: str
    case_id: str
    user_goal: str
    case_config_path: str
    output_dir: str
    current_node: str
    status: str  # running | success | failed | pending | halted

    checkpoint_thread_id: str
    checkpoint_backend: str  # memory | sqlite
    checkpoint_db_path: str | None

    context_policy_path: str | None
    context_summary_path: str | None
    event_log_summary: str | None
    context_window_status: str  # normal | near_limit | summarized | overflow_halt

    method_plan_path: str | None
    code_needed: bool
    coder_task_packet_path: str | None
    code_change_summary_path: str | None
    tests_status_path: str | None
    retry_count: int
    max_retry: int

    run_success: bool
    failure_type: str | None  # code | config_or_data | workflow | unknown
    run_result_path: str | None
    analysis_outputs_dir: str | None

    scientific_review_report_path: str | None
    decision_log_path: str | None
    risk_level: str  # unknown | low | medium | high | critical
    recommended_action: str | None
    rerun_requested: bool
    rerun_target: str | None
    code_fix_requested: bool

    human_approval_required: bool
    approval_packet_dir: str | None
    human_decision_path: str | None

    final_report_path: str | None
    memory_update_path: str | None
    errors: list[dict]
    warnings: list[dict]
    event_log: list[dict]
```

说明：checkpointing 与 LLM context 不是同一件事。checkpoint 保存完整 graph state，用于恢复、回放和审计；LLM 节点只接收经过选择或摘要的 state fields 与 artifact summaries。graph routing 不得依赖被截断或摘要后的自由文本。

所有 LLM agent 必须输出 JSON/YAML 结构化字段。Markdown 可以作为人类可读报告，但 graph routing 不得依赖自由文本摘要。

```json
{
  "agent_name": "method_planner | scientific_reviewer | decision_coordinator",
  "status": "success | needs_more_evidence | failed",
  "summary": "...",
  "findings": [],
  "evidence": [],
  "warnings": [],
  "recommended_actions": [],
  "confidence": "low | medium | high"
}
```

# 9. 推荐 Repository 结构

```text
lqcd-agent/
  AGENTS.md
  pyproject.toml
  README.md
  .gitignore
  .env.example
  configs/
    cases/
      mock_lqcd_goal.yaml
      l64c64a076_m140.yaml
    runtime/
      default_llm.yaml
      openai.yaml
      deepseek.yaml
  docs/
    PROJECT_SPEC.md
    ARCHITECTURE.md
    AGENT_ROLES_AND_BOUNDARIES.md
    STATE_SCHEMA.md
    ARTIFACT_CONTRACTS.md
    TICKETS.md
    VERIFICATION_GUIDE.md
    REPO_CURRENT_STATE.md
    DECISION_LOG.md
    PROMPT_PLAYBOOK.md
    SECURITY_AND_DATA_POLICY.md
    EVALS_AND_OBSERVABILITY.md
  src/lqcd_agent/
    graph/
      state.py
      nodes.py
      analysis_graph.py
      routing.py
      run_graph.py
      approval_packet.py
    llm/
      base.py
      mock_provider.py
      openai_client.py
      deepseek_client.py
      provider_factory.py
      prompts.py
      schemas.py
      structured_output.py
    agents/
      method_planner.py
      analysis_engineer.py
      scientific_reviewer.py
      decision_coordinator.py
    coder/
      task_packet.py
      codex_handoff.py
      test_runner.py
    tools/
      command_runner.py
      output_validator.py
      manifest.py
      repo_inventory.py
    analysis/
      correlator_diagnostics.py
      fit_diagnostics.py
      matrix_element_diagnostics.py
    memory/
      store.py
      query.py
    report/
      generate_report.py
```

```text
workflow/
    Snakefile
    rules/
  raw_data/                         # Phase 11; read-only, manifest/checksum driven
    README.md
    data/
      <dataset_id>/
        manifest.yaml
        input_files/
        checksums.txt
  evaluation/
    cases/
      good_example.yaml
      ambiguous_example.yaml
      bad_example.yaml
    reference_outputs/
      good_example/
      ambiguous_example/
      bad_example/
    expected_behavior/
      good_example_expected.yaml
      ambiguous_example_expected.yaml
      bad_example_expected.yaml
    run_evaluation.py
  tests/
    test_import.py
    test_graph_smoke.py
    test_state_schema.py
    test_routing.py
    test_approval_packet.py
    test_memory.py
    test_llm_config.py
    test_llm_mock_provider.py
  outputs/
    .gitkeep
    <case_id>/<run_id>/
      graph_state.json
      checkpoints/
        checkpoint.sqlite
      llm_calls/
      agent_reports/
      code_tasks/
      analysis_outputs/
      approval_packet/
      decision_log.json
      final_report.md
```

# 10. Standard Codex Ticket Contract

每个 phase 的 prompt 都必须遵循同一结构。这样 Codex 不会随意扩大范围，也能在失败时清楚知道何时停止。

````markdown
# Ticket LG-XXX: [Title]

## Goal
[One concrete goal.]

## Read First
- AGENTS.md
- docs/PROMPT_PLAYBOOK.md
- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/VERIFICATION_GUIDE.md

## Allowed Files
- [exact files or directories]

## Do Not Touch
- raw_data/
- accepted_results/
- production deployment files
- secrets or credentials
- unrelated modules
- public schemas unless explicitly required

## Requirements
- [implementation requirements]
- [schema/artifact requirements]
- [safety requirements]

## Non-goals
- [explicitly out of scope]

## Acceptance Criteria
- [observable completion criteria]

## Verification Commands
```bash
pytest ...
python -m ...
```

## Stop Conditions
Stop and ask if:
- required context is missing
- implementation would require changing a public schema not listed above
- a new dependency is needed but not allowed
- raw data or accepted results would be modified
- verification commands cannot be run

## End-of-task Updates
- Update docs/REPO_CURRENT_STATE.md
- Update docs/DECISION_LOG.md if architecture or policy changed
- Perform the stale-documentation scan from docs/PROMPT_PLAYBOOK.md
- Final response: Changed / Why / Verified / Next
````

# 11. 分阶段执行计划：统一 prompt 版本

以下采用 pre-phase0 + Phase 0–11 的统一 prompt 合同。建议每个 phase 单独执行、单独 review、单独 commit。不要让 Codex 一次性实现整个系统。Phase 10 和 Phase 11 是后置阶段：只有 Phase 0–9 的 mock/golden path 跑通后，才接入真实 LLM provider 与 raw_data-backed evaluation library。

Global phase rules:

- Documentation sync: every phase must reconcile `README.md`, `docs/TICKETS.md`, `docs/VERIFICATION_GUIDE.md`, and `docs/REPO_CURRENT_STATE.md` when behavior, commands, output paths, public artifact contracts, phase status, or verification commands change. Update `docs/DECISION_LOG.md` only when architecture, policy, phase sequencing, or schema decisions change.
- Stale-documentation scan: before the final response, check whether `README.md`, `docs/ARCHITECTURE.md`, `docs/STATE_SCHEMA.md`, `docs/ARTIFACT_CONTRACTS.md`, `docs/TICKETS.md`, `docs/VERIFICATION_GUIDE.md`, `docs/REPO_CURRENT_STATE.md`, `docs/DECISION_LOG.md`, and TODO comments still accurately describe the implemented phase. Update only stale statements caused by the ticket; do not rewrite unrelated documentation.
- Graph integration rule: after Phase 2B, any ticket that implements an Agent or Node must either wire it into the LangGraph runtime and smoke path, or explicitly state that it is standalone and name the follow-up integration ticket.
- State schema rule: phase prompts must use existing `AnalysisState` fields and existing allowed status values unless the phase explicitly allows updating `docs/STATE_SCHEMA.md` and tests.
- Canonical run result path:

```text
<output_root>/<case_id>/<run_id>/
```

- Repository examples should use:

```bash
--output-dir outputs
```

which yields:

```text
outputs/<case_id>/<run_id>/
```

- Existing generated output directories are not reference outputs and should not be deleted or reorganized unless a ticket explicitly allows output cleanup.

### Pre-phase0：Socratic Discovery, Scope Lock, and Source-of-Truth Docs

```text
Task:
Before writing code, run a Socratic discovery interview for the AI-assisted LQCD meson DA multi-agent LangGraph project.

Read First:
- AGENTS.md
- the current high-level project plan, if available

Allowed Files:
- No files in interview step A.
- After I explicitly approve the summarized scope, you may create or update only docs/*.md source-of-truth files.

Do Not Touch:
- src/
- tests/
- configs/
- raw_data/
- outputs/
- pyproject.toml
- dependency files

Requirements:
- Ask high-value clarification questions before proposing final architecture.
- Cover scientific goal, first golden example, available data, mock strategy, observables, agent roles, human approval boundaries, raw data policy, external command permissions, LLM provider assumptions, checkpointing/context-boundary policy, evaluation cases, MVP definition of done.
- Challenge overcomplicated assumptions and propose simpler alternatives.
- Separate confirmed decisions from unresolved questions.
- After my answers, produce drafts for PROJECT_SPEC.md, ARCHITECTURE.md, AGENT_ROLES_AND_BOUNDARIES.md, STATE_SCHEMA.md, ARTIFACT_CONTRACTS.md, TICKETS.md, VERIFICATION_GUIDE.md, PROMPT_PLAYBOOK.md, SECURITY_AND_DATA_POLICY.md, and EVALS_AND_OBSERVABILITY.md.

Non-goals:
- Do not write implementation code.
- Do not create repo skeleton.
- Do not install dependencies.
- Do not call external APIs.

Acceptance Criteria:
- You ask clarification questions first.
- You summarize confirmed decisions, unresolved questions, risks, proposed MVP, and proposed non-goals.
- You do not proceed to file creation until I explicitly approve.
- Approved docs are internally consistent and contain TODOs only where information is genuinely missing.
- PROMPT_PLAYBOOK.md has a clear placeholder for the standard ticket template and worked examples to be completed in Phase 0.

Verification Commands:
- None for interview step.
- If docs are created, verify that all required docs exist and cross-reference each other consistently.

Stop Conditions:
Stop if the scientific scope, data boundary, checkpoint/context strategy, human approval rule, or first golden example remains ambiguous after the interview.

End-of-task Updates:
- If docs are created, update docs/REPO_CURRENT_STATE.md and docs/DECISION_LOG.md.
- Final response: Changed / Why / Verified / Next
```

### Phase 0：Project Documentation Skeleton + Repo Skeleton

````text
Task:
Create the initial repository and documentation skeleton for the AI-assisted LQCD meson DA multi-agent LangGraph system.

Read First:
- AGENTS.md
- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/VERIFICATION_GUIDE.md

Allowed Files:
- pyproject.toml
- README.md
- .gitignore
- .env.example
- docs/*.md
- src/lqcd_agent/__init__.py
- configs/cases/mock_lqcd_goal.yaml
- configs/runtime/mock_llm.yaml
- outputs/.gitkeep
- tests/test_import.py

Do Not Touch:
- raw_data/
- accepted_results/
- real analysis scripts
- external APIs
- production deployment files
- secrets or credentials

Requirements:
- Keep the package installable with pip install -e .
- Create docs skeletons if they do not exist.
- Create docs/PROMPT_PLAYBOOK.md with the standard ticket contract, the standard phase prompt wrapper, the standard end-of-task summary format, and at least two worked examples: one node implementation ticket and one diagnostic module ticket.
- The worked examples must include Read First, Allowed Files, Do Not Touch, Requirements, Non-goals, Acceptance Criteria, Verification Commands, Stop Conditions, and End-of-task Updates.
- Create only a minimal .env.example with placeholder names; Phase 10 will expand provider-specific OpenAI/DeepSeek variables.
- Do not implement real agents.
- Do not call DeepSeek, OpenAI, Codex, or any external API.
- Mark unresolved documentation items as TODO with owner and reason.
- Delete or omit CLAUDE.md; use AGENTS.md as the single root AI contract.

Non-goals:
- No real LangGraph runtime yet.
- No real LLM integration.
- No database or production deployment.
- No real raw_data or raw_data-backed evaluation cases.

Acceptance Criteria:
- pip install -e . succeeds.
- pytest tests/test_import.py -q passes.
- README explains project goal and directory structure.
- docs/REPO_CURRENT_STATE.md records current status.
- docs/TICKETS.md records Phase 0 as the repository skeleton phase and contains the next Phase 1 ticket.
- docs/PROMPT_PLAYBOOK.md contains the standard ticket template and at least two worked examples.

Verification Commands:
```bash
pip install -e .
pytest tests/test_import.py -q
```

Stop Conditions:
Stop if a dependency beyond packaging/test basics is needed, if the repo layout conflicts with docs/ARCHITECTURE.md, or if any raw data or real analysis result would be modified.

End-of-task Updates:
- Update README.md if user-facing structure or verification commands changed.
- Update docs/TICKETS.md with Phase 0 status and the next Phase 1 ticket.
- Update docs/VERIFICATION_GUIDE.md if verification commands changed.
- Update docs/REPO_CURRENT_STATE.md.
- Update docs/DECISION_LOG.md if the repo layout decision changes.
- Final response: Changed / Why / Verified / Next
````

### Phase 1：Real LangGraph StateGraph Runtime Skeleton

````text
Task:
Implement the initial graph runtime using real LangGraph StateGraph with deterministic mock nodes.

Read First:
- AGENTS.md
- docs/ARCHITECTURE.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/VERIFICATION_GUIDE.md
- docs/PROMPT_PLAYBOOK.md

Allowed Files:
- pyproject.toml only if LangGraph dependency is not yet declared
- src/lqcd_agent/graph/state.py
- src/lqcd_agent/graph/nodes.py
- src/lqcd_agent/graph/routing.py
- src/lqcd_agent/graph/analysis_graph.py
- src/lqcd_agent/graph/run_graph.py
- tests/test_state_schema.py
- tests/test_routing.py
- tests/test_graph_smoke.py
- README.md
- docs/STATE_SCHEMA.md
- docs/ARCHITECTURE.md
- docs/TICKETS.md
- docs/VERIFICATION_GUIDE.md
- docs/REPO_CURRENT_STATE.md
- docs/DECISION_LOG.md

Do Not Touch:
- real agent implementation files
- raw_data/
- accepted_results/
- LLM provider files
- production deployment files

Requirements:
- Use LangGraph StateGraph, not a custom replacement runtime.
- Compile the StateGraph with a configurable checkpointer.
- Use MemorySaver for unit tests and smoke tests.
- Use SqliteSaver for local CLI runs, writing the SQLite checkpoint database under `<output_root>/<case_id>/<run_id>/checkpoints/`.
- Treat `--output-dir` as an output root. Repository demos may use `--output-dir outputs --run-id mock_run`, yielding `outputs/<case_id>/<run_id>/`; verification commands should prefer a temporary output root.
- Require a stable checkpoint_thread_id, preferably derived from case_id and run_id.
- Implement mock nodes for Method Planner, Analysis Engineer, Scientific Reviewer, Decision Coordinator, and Memory & Report.
- Implement routing with deterministic structured fields.
- Save graph_state.json after meaningful state transitions.
- Add retry_count/max_retry fields and halt/pending behavior where needed.
- Define a context boundary policy: full graph state is persisted in checkpoints; LLM nodes receive only selected state fields and artifact summaries; long event_log entries must be summarized before being passed to the next LLM node; routing must never depend on truncated free-form context.

Non-goals:
- Do not call DeepSeek, OpenAI, Codex, or external APIs.
- Do not implement real scientific diagnostics.
- Do not implement long-term memory persistence beyond mock output.
- Do not implement real LLM summarization yet; use deterministic mock summarization for long event_log tests.

Acceptance Criteria:
- The graph can run from START to END with the mock case.
- graph_state.json records node transitions, route decisions, checkpoint_backend, checkpoint_thread_id, and checkpoint_db_path.
- Smoke test verifies that a graph run can be resumed or inspected through checkpoint metadata.
- A mock long event_log case triggers event_log_summary or context_window_status=summarized.
- Unit tests cover state initialization, routing, checkpoint metadata, context summarization behavior, and smoke execution.

Verification Commands:
```bash
pytest tests/test_state_schema.py tests/test_routing.py tests/test_graph_smoke.py -q
python -m lqcd_agent.graph.run_graph --case configs/cases/mock_lqcd_goal.yaml --output-dir /private/tmp/lqcd-agent-phase1 --run-id mock_run
```

Stop Conditions:
Stop if LangGraph dependency cannot be installed, if AnalysisState requires undocumented schema changes, if checkpointer APIs are ambiguous, or if routing would depend on free-form text.

End-of-task Updates:
- Update README.md with the new runtime and CLI usage.
- Update docs/TICKETS.md with Phase 1 status and the next Phase 2 ticket.
- Update docs/STATE_SCHEMA.md.
- Update docs/ARCHITECTURE.md with checkpointing and context-boundary policy.
- Update docs/VERIFICATION_GUIDE.md with the current smoke command.
- Update docs/REPO_CURRENT_STATE.md.
- Update docs/DECISION_LOG.md if runtime or graph topology changes.
- Final response: Changed / Why / Verified / Next
````

### Phase 2：Method Planner Agent

````text
Task:
Implement Method Planner Agent as a structured-output module with mock LLM behavior.

Read First:
- AGENTS.md
- docs/PROJECT_SPEC.md
- docs/AGENT_ROLES_AND_BOUNDARIES.md
- docs/ARTIFACT_CONTRACTS.md
- docs/STATE_SCHEMA.md

Allowed Files:
- src/lqcd_agent/agents/method_planner.py
- src/lqcd_agent/tools/repo_inventory.py
- src/lqcd_agent/coder/task_packet.py if needed for packet schema reuse
- tests/test_method_planner_mock.py
- docs/ARTIFACT_CONTRACTS.md
- docs/TICKETS.md
- docs/VERIFICATION_GUIDE.md
- docs/REPO_CURRENT_STATE.md

Do Not Touch:
- LangGraph topology unless the ticket explicitly requires integration
- raw_data/
- accepted_results/
- real LLM provider files

Requirements:
- Input: user_goal, case_config, repo_inventory.
- Output method_plan.json with physics_goal, target_observables, method_steps, required_inputs, required_outputs, implementation_gaps, code_needed, coder_task_summary.
- If code_needed=true, write coder_task_packet.yaml using documented schema.
- Return status=needs_more_info when key inputs are missing.
- Keep mock LLM behavior deterministic and replaceable later.
- This phase implements a standalone Method Planner module only. Graph integration is deferred to Phase 2B.

Non-goals:
- Do not call real LLMs.
- Do not write implementation code for analysis.
- Do not decide final physics conclusions.

Acceptance Criteria:
- Mock goal generates a valid method_plan.json.
- code_needed=true generates a valid task packet.
- Missing critical fields produce needs_more_info.
- docs/TICKETS.md records Phase 2 as standalone and identifies Phase 2B as the next graph-integration ticket.

Verification Commands:
```bash
pytest tests/test_method_planner_mock.py -q
```

Stop Conditions:
Stop if artifact schemas are missing or conflict with docs/ARTIFACT_CONTRACTS.md.

End-of-task Updates:
- Update docs/ARTIFACT_CONTRACTS.md if artifact schema is clarified.
- Update docs/TICKETS.md with Phase 2 status and the Phase 2B ticket.
- Update docs/VERIFICATION_GUIDE.md if planner verification commands changed.
- Update docs/REPO_CURRENT_STATE.md.
- Final response: Changed / Why / Verified / Next
````

### Phase 2B：Method Planner Graph Integration

````text
Task:
Wire the standalone deterministic Method Planner module into the LangGraph method planner node.

Read First:
- AGENTS.md
- docs/ARCHITECTURE.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/VERIFICATION_GUIDE.md
- docs/TICKETS.md

Allowed Files:
- src/lqcd_agent/graph/nodes.py
- src/lqcd_agent/graph/routing.py
- src/lqcd_agent/graph/analysis_graph.py only if graph edges need a safe terminal route
- src/lqcd_agent/agents/method_planner.py only for integration-facing bug fixes
- tests/test_graph_smoke.py
- tests/test_routing.py
- tests/test_method_planner_mock.py only if integration reveals a planner-contract mismatch
- README.md
- docs/ARCHITECTURE.md
- docs/TICKETS.md
- docs/VERIFICATION_GUIDE.md
- docs/REPO_CURRENT_STATE.md
- docs/DECISION_LOG.md if the graph integration decision is clarified
- docs/STATE_SCHEMA.md only if the ticket explicitly chooses to change the public state schema

Do Not Touch:
- Codex Handoff implementation files except existing task-packet helpers already used by the planner
- raw_data/
- accepted_results/
- real LLM provider files
- production deployment files
- secrets or credentials

Requirements:
- Replace the graph's simplified mock planner body with the standalone deterministic Method Planner module.
- Preserve the no-code path: code_needed=false routes to Analysis Engineer.
- For needs_more_info, write method_plan.json, record structured errors, and stop safely with an existing status value such as pending or halted. Do not continue to Analysis Engineer.
- For code_needed=true before Phase 3 exists, write coder_task_packet.yaml, set coder_task_packet_path, and stop safely with an existing status value such as pending or halted. Do not route to Analysis Engineer and do not implement Codex Handoff in this phase.
- Use existing AnalysisState fields and existing allowed status values unless this ticket explicitly updates docs/STATE_SCHEMA.md and tests.
- Keep routing based on structured fields only.
- Keep the canonical output path policy: <output_root>/<case_id>/<run_id>/.

Non-goals:
- Do not implement Codex Handoff.
- Do not call real LLMs.
- Do not add new state fields or status values unless this ticket explicitly updates the schema and tests.
- Do not implement real analysis or scientific diagnostics.

Acceptance Criteria:
- The normal mock case still runs from START to final report.
- A planner needs_more_info case stops safely and records errors without analysis execution.
- A planner code_needed=true case writes coder_task_packet.yaml, sets coder_task_packet_path, and stops safely before analysis.
- Tests cover no-code, needs-more-info, and code-needed planner outcomes in the graph path.
- README, docs/TICKETS.md, docs/VERIFICATION_GUIDE.md, and docs/REPO_CURRENT_STATE.md accurately describe the integration status.

Verification Commands:
```bash
pytest tests/test_state_schema.py tests/test_routing.py tests/test_graph_smoke.py tests/test_method_planner_mock.py -q
python -m lqcd_agent.graph.run_graph --case configs/cases/mock_lqcd_goal.yaml --output-dir /private/tmp/lqcd-agent-phase2b --run-id mock_run
```

Stop Conditions:
Stop if safe routing for needs_more_info or code_needed=true requires a new AnalysisState field or status value not allowed by this ticket, if graph integration would require implementing Codex Handoff, or if routing would depend on free-form text.

End-of-task Updates:
- Update README.md with Method Planner graph-integration status.
- Update docs/TICKETS.md with Phase 2B status and the next Phase 3 ticket.
- Update docs/ARCHITECTURE.md if graph integration behavior changes.
- Update docs/VERIFICATION_GUIDE.md with graph-integration checks.
- Update docs/REPO_CURRENT_STATE.md.
- Update docs/DECISION_LOG.md if the integration decision or state policy changes.
- Final response: Changed / Why / Verified / Next
````

### Phase 3：Codex Handoff Node and Coder Task Packet

````text
Task:
Implement file-based Codex handoff support. Do not call Codex programmatically from the runtime graph.

Read First:
- AGENTS.md
- docs/AGENT_ROLES_AND_BOUNDARIES.md
- docs/ARTIFACT_CONTRACTS.md
- docs/VERIFICATION_GUIDE.md

Allowed Files:
- src/lqcd_agent/coder/task_packet.py
- src/lqcd_agent/coder/codex_handoff.py
- src/lqcd_agent/coder/test_runner.py
- src/lqcd_agent/graph/nodes.py
- src/lqcd_agent/graph/routing.py
- src/lqcd_agent/graph/analysis_graph.py
- tests/test_coder_task_packet.py
- tests/test_test_runner.py
- tests/test_routing.py
- tests/test_graph_smoke.py
- docs/ARTIFACT_CONTRACTS.md
- docs/TICKETS.md
- docs/VERIFICATION_GUIDE.md
- docs/REPO_CURRENT_STATE.md

Do Not Touch:
- real agent implementations outside coder/
- raw_data/
- accepted_results/
- external APIs
- production deployment files

Requirements:
- Define and validate coder_task_packet.yaml schema.
- Implement utilities to write/read task packets.
- Implement test_runner.py to run configured verification commands and write tests_status.json.
- Read code_change_summary.md and tests_status.json as handoff results.
- Route tests_failed / tests_passed based on structured status.
- Wire Codex Handoff into the graph route for code_needed=true and code-failure retry paths.
- If no handoff result exists yet, stop safely with structured pending or halted state rather than continuing to analysis.

Non-goals:
- Do not call Codex programmatically.
- Do not implement actual code changes requested by task packets in this phase.
- Do not broaden graph topology beyond handoff integration points.

Acceptance Criteria:
- Valid task packet passes validation.
- Invalid packet fails with clear errors.
- test_runner records command, return code, stdout/stderr, and status.
- Graph routing reaches Codex Handoff when code_needed=true and reaches Analysis Engineer only after structured tests_passed status.

Verification Commands:
```bash
pytest tests/test_coder_task_packet.py tests/test_test_runner.py tests/test_routing.py tests/test_graph_smoke.py -q
```

Stop Conditions:
Stop if safe command execution policy is missing or if the handoff would require storing secrets.

End-of-task Updates:
- Update docs/ARTIFACT_CONTRACTS.md.
- Update docs/TICKETS.md with Phase 3 status and the next Phase 4 ticket.
- Update docs/VERIFICATION_GUIDE.md if handoff verification commands changed.
- Update docs/REPO_CURRENT_STATE.md.
- Final response: Changed / Why / Verified / Next
````

### Phase 4：Analysis Engineer Agent, Command Runner, Manifest

````text
Task:
Implement Analysis Engineer Agent, safe command runner, output validator, and provenance manifest.

Read First:
- AGENTS.md
- docs/SECURITY_AND_DATA_POLICY.md
- docs/ARTIFACT_CONTRACTS.md
- docs/STATE_SCHEMA.md
- docs/VERIFICATION_GUIDE.md

Allowed Files:
- src/lqcd_agent/agents/analysis_engineer.py
- src/lqcd_agent/graph/nodes.py
- src/lqcd_agent/graph/routing.py
- src/lqcd_agent/tools/command_runner.py
- src/lqcd_agent/tools/output_validator.py
- src/lqcd_agent/tools/manifest.py
- tests/test_analysis_engineer.py
- tests/test_command_runner.py
- tests/test_manifest.py
- tests/test_routing.py
- tests/test_graph_smoke.py
- docs/SECURITY_AND_DATA_POLICY.md
- docs/ARTIFACT_CONTRACTS.md
- docs/TICKETS.md
- docs/VERIFICATION_GUIDE.md
- docs/REPO_CURRENT_STATE.md

Do Not Touch:
- raw_data/
- accepted_results/
- real physics algorithms unless explicitly allowed
- production deployment files

Requirements:
- Read case/task config.
- Run only safe mock or configured local commands through command_runner.
- Validate expected outputs.
- Write run_result.json, manifest.json, and run.log.
- Enforce the `<output_root>/<case_id>/<run_id>/` output policy.
- Do not overwrite existing runs without explicit force behavior.
- Wire the Analysis Engineer module into the graph analysis node so the smoke path uses the same implementation.

Non-goals:
- Do not decide central fits or physics conclusions.
- Do not run unapproved external commands.
- Do not connect real raw data unless a separate ticket authorizes it.

Acceptance Criteria:
- Success command returns run_success=true.
- Missing output returns failure_type=config_or_data.
- Command failure records return code and stderr.
- Manifest includes required provenance fields.
- Graph smoke run writes run_result.json and manifest.json under the canonical run result path.

Verification Commands:
```bash
pytest tests/test_analysis_engineer.py tests/test_command_runner.py tests/test_manifest.py tests/test_routing.py tests/test_graph_smoke.py -q
```

Stop Conditions:
Stop if a command would modify raw_data, overwrite accepted results, or require secrets.

End-of-task Updates:
- Update docs/SECURITY_AND_DATA_POLICY.md if command policy changes.
- Update docs/ARTIFACT_CONTRACTS.md.
- Update docs/TICKETS.md with Phase 4 status and the next Phase 5 ticket.
- Update docs/VERIFICATION_GUIDE.md if runtime or manifest verification commands changed.
- Update docs/REPO_CURRENT_STATE.md.
- Final response: Changed / Why / Verified / Next
````

### Phase 5：Scientific Reviewer Agent

````text
Task:
Implement Scientific Reviewer Agent with three internal diagnostic sections: correlator, fit strategy, and matrix element.

Read First:
- AGENTS.md
- docs/AGENT_ROLES_AND_BOUNDARIES.md
- docs/ARTIFACT_CONTRACTS.md
- docs/PROJECT_SPEC.md
- docs/VERIFICATION_GUIDE.md

Allowed Files:
- src/lqcd_agent/agents/scientific_reviewer.py
- src/lqcd_agent/graph/nodes.py
- src/lqcd_agent/graph/routing.py
- src/lqcd_agent/analysis/correlator_diagnostics.py
- src/lqcd_agent/analysis/fit_diagnostics.py
- src/lqcd_agent/analysis/matrix_element_diagnostics.py
- tests/test_scientific_reviewer.py
- tests/test_graph_smoke.py
- tests/fixtures/ if needed for mock summary tables
- docs/ARTIFACT_CONTRACTS.md
- docs/TICKETS.md
- docs/VERIFICATION_GUIDE.md
- docs/REPO_CURRENT_STATE.md

Do Not Touch:
- raw_data/
- accepted_results/
- Decision Coordinator logic unless explicitly required
- real fit algorithms unless a separate ticket authorizes it

Requirements:
- Input: analysis outputs, summary tables, optional plots, method_plan.json.
- Output scientific_review_report.json with correlator_diagnostics, fit_diagnostics, matrix_element_diagnostics, findings, evidence, warnings, recommended_checks, confidence.
- Every warning must cite concrete file/field/value evidence.
- Mark severe warnings explicitly for Decision Coordinator.
- Wire the Scientific Reviewer module into the graph reviewer node so the smoke path uses the same implementation.

Non-goals:
- Do not choose the final central fit.
- Do not delete or rewrite data.
- Do not promote results to accepted memory.
- Do not invent literature evidence.

Acceptance Criteria:
- Report contains all three diagnostic sections.
- Mock good/ambiguous/bad tables produce different warnings.
- Severe warning appears when mock evidence requires it.
- Graph smoke run writes scientific_review_report.json using the documented diagnostic field names.

Verification Commands:
```bash
pytest tests/test_scientific_reviewer.py tests/test_graph_smoke.py -q
```

Stop Conditions:
Stop if required mock data format is undefined or if review would require final physics decisions.

End-of-task Updates:
- Update docs/ARTIFACT_CONTRACTS.md.
- Update docs/TICKETS.md with Phase 5 status and the next Phase 6 ticket.
- Update docs/VERIFICATION_GUIDE.md if reviewer verification commands changed.
- Update docs/REPO_CURRENT_STATE.md.
- Final response: Changed / Why / Verified / Next
````

### Phase 6：Decision Coordinator and Risk Rubric

````text
Task:
Implement Decision Coordinator Agent and risk rubric.

Read First:
- AGENTS.md
- docs/AGENT_ROLES_AND_BOUNDARIES.md
- docs/ARTIFACT_CONTRACTS.md
- docs/STATE_SCHEMA.md
- docs/PROJECT_SPEC.md

Allowed Files:
- src/lqcd_agent/agents/decision_coordinator.py
- src/lqcd_agent/graph/nodes.py
- src/lqcd_agent/graph/routing.py
- tests/test_decision_coordinator.py
- tests/test_routing.py
- tests/test_graph_smoke.py
- docs/AGENT_ROLES_AND_BOUNDARIES.md
- docs/ARTIFACT_CONTRACTS.md
- docs/TICKETS.md
- docs/VERIFICATION_GUIDE.md
- docs/REPO_CURRENT_STATE.md
- docs/DECISION_LOG.md if risk policy changes

Do Not Touch:
- raw_data/
- accepted_results/
- Scientific Reviewer implementation unless explicitly required
- Human Approval Gate implementation unless explicitly required

Requirements:
- Input method_plan.json, run_result.json, scientific_review_report.json, and risk rubric.
- Output decision_log.json with recommended_action, risk_level, human_approval_required, reasons, evidence, next_actions.
- Assign exactly one primary next action.
- Severe warnings must prevent low risk.
- Medium risk must not be written as accepted memory; it must produce pending or human-review-recommended status/action.
- high/critical must set human_approval_required=true.
- Route fields must be structured.
- Wire the Decision Coordinator module into the graph decision node so graph routing uses the same risk policy.

Non-goals:
- Do not make final paper-level claims.
- Do not override scientific warnings without evidence.
- Do not write code changes.

Acceptance Criteria:
- Tests cover low, medium, high, and critical cases.
- targeted_rerun/code_fix routes are represented in state.
- medium risk does not enter accepted memory.
- high/critical cannot enter accepted memory without approval.

Verification Commands:
```bash
pytest tests/test_decision_coordinator.py tests/test_routing.py tests/test_graph_smoke.py -q
```

Stop Conditions:
Stop if risk rubric conflicts with human approval policy or structured output schema.

End-of-task Updates:
- Update docs/DECISION_LOG.md if risk policy is clarified.
- Update docs/TICKETS.md with Phase 6 status and the next Phase 7 ticket.
- Update docs/VERIFICATION_GUIDE.md if decision verification commands changed.
- Update docs/REPO_CURRENT_STATE.md.
- Final response: Changed / Why / Verified / Next
````

### Phase 7：Human Approval Gate

````text
Task:
Implement risk-based Human Approval Gate and approval packet generator.

Read First:
- AGENTS.md
- docs/PROMPT_PLAYBOOK.md
- docs/AGENT_ROLES_AND_BOUNDARIES.md
- docs/ARTIFACT_CONTRACTS.md
- docs/SECURITY_AND_DATA_POLICY.md
- docs/STATE_SCHEMA.md

Allowed Files:
- src/lqcd_agent/graph/approval_packet.py
- src/lqcd_agent/graph/nodes.py
- src/lqcd_agent/graph/routing.py
- src/lqcd_agent/graph/analysis_graph.py
- tests/test_approval_packet.py
- tests/test_routing.py
- tests/test_graph_smoke.py
- docs/ARTIFACT_CONTRACTS.md
- docs/ARCHITECTURE.md
- docs/TICKETS.md
- docs/VERIFICATION_GUIDE.md
- docs/REPO_CURRENT_STATE.md

Do Not Touch:
- raw_data/
- accepted_results/
- Decision Coordinator risk policy unless explicitly required
- production deployment files

Requirements:
- Generate approval_packet only when human_approval_required=true.
- Include requested decision, human summary, available comparisons, scientific review report, AI recommendation, decision options, and human decision template.
- Parse 07_human_decision.yaml.
- no human decision -> pending state.
- approve_rerun / request_code_change / reject_or_hold must have clear route fields.
- Wire Human Approval Gate into the graph for high and critical risk routes.

Non-goals:
- Do not make Human Approval Gate always-on for low/medium cases.
- Do not rewrite human decisions.
- Do not mark high/critical as accepted without approval.

Acceptance Criteria:
- high risk generates approval packet.
- medium risk does not require approval packet unless explicitly configured.
- no decision produces pending state.
- each supported decision option routes correctly.
- graph routing sends high and critical risk to Human Approval Gate instead of Memory and Report.

Verification Commands:
```bash
pytest tests/test_approval_packet.py tests/test_routing.py tests/test_graph_smoke.py -q
```

Stop Conditions:
Stop if approval packet schema is undefined or if implementation would overwrite human decisions.

End-of-task Updates:
- Update docs/ARTIFACT_CONTRACTS.md.
- Update docs/ARCHITECTURE.md if approval routing changes.
- Update docs/TICKETS.md with Phase 7 status and the next Phase 8 ticket.
- Update docs/VERIFICATION_GUIDE.md if approval verification commands changed.
- Update docs/REPO_CURRENT_STATE.md.
- Final response: Changed / Why / Verified / Next
````

### Phase 8：Memory, Final Report, Evaluation Harness

````text
Task:
Implement Memory & Report node and evaluation harness.

Read First:
- AGENTS.md
- docs/ARTIFACT_CONTRACTS.md
- docs/EVALS_AND_OBSERVABILITY.md
- docs/SECURITY_AND_DATA_POLICY.md
- docs/VERIFICATION_GUIDE.md
- docs/PROMPT_PLAYBOOK.md

Allowed Files:
- src/lqcd_agent/memory/store.py
- src/lqcd_agent/memory/query.py
- src/lqcd_agent/report/generate_report.py
- src/lqcd_agent/graph/nodes.py
- src/lqcd_agent/graph/routing.py
- evaluation/cases/*.yaml
- evaluation/run_evaluation.py
- tests/test_memory.py
- tests/test_report.py
- tests/test_evaluation.py
- tests/test_graph_smoke.py
- README.md
- docs/EVALS_AND_OBSERVABILITY.md
- docs/TICKETS.md
- docs/VERIFICATION_GUIDE.md
- docs/REPO_CURRENT_STATE.md

Do Not Touch:
- raw_data/
- accepted_results/ unless explicitly using append-only/versioned test fixtures
- human decision files
- production deployment files

Requirements:
- Update accepted/pending/rejected memory according to risk and approval state.
- Generate final_report.md with metadata, method plan, run summary, scientific review, warnings, coordinator decision, approval status, next actions, reproducibility.
- Add synthetic/minimal good, ambiguous, and bad evaluation cases that do not require real raw_data.
- Write evaluation_summary.csv comparing expected vs actual risk/action.
- Document that Phase 11 will extend the evaluation library with raw_data-backed or reference-output-backed cases.
- Wire Memory and Report into the graph final node so graph smoke runs use the same report and memory implementation.

Non-goals:
- Do not use memory as a source of final scientific truth.
- Do not overwrite accepted memory without versioning.
- Do not require external services.
- Do not create real raw_data-backed examples in this phase.

Acceptance Criteria:
- Each case ends with correct memory category.
- final_report.md is generated and readable.
- Evaluation harness runs synthetic good/ambiguous/bad cases.
- EVALS_AND_OBSERVABILITY.md clearly separates Phase 8 synthetic cases from Phase 11 raw_data-backed cases.
- graph smoke run writes memory_update and final_report using the Memory and Report implementation.

Verification Commands:
```bash
pytest tests/test_memory.py tests/test_report.py tests/test_evaluation.py tests/test_graph_smoke.py -q
python evaluation/run_evaluation.py
```

Stop Conditions:
Stop if memory policy is ambiguous, if accepted memory would be overwritten, or if implementation would require real raw data.

End-of-task Updates:
- Update docs/EVALS_AND_OBSERVABILITY.md.
- Update README.md if evaluation or report commands become user-facing.
- Update docs/TICKETS.md with Phase 8 status and the next Phase 9 ticket.
- Update docs/VERIFICATION_GUIDE.md with evaluation commands.
- Update docs/REPO_CURRENT_STATE.md.
- Final response: Changed / Why / Verified / Next
````

### Phase 9：Golden Example and Productization

````text
Task:
Connect the mock graph to the l64c64a076_m140 golden example conservatively and finalize developer-facing documentation.

Read First:
- AGENTS.md
- docs/PROMPT_PLAYBOOK.md
- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/VERIFICATION_GUIDE.md
- docs/SECURITY_AND_DATA_POLICY.md
- docs/EVALS_AND_OBSERVABILITY.md

Allowed Files:
- configs/cases/l64c64a076_m140.yaml
- scripts/run_langgraph_demo.sh
- docs/ARCHITECTURE.md
- docs/VERIFICATION_GUIDE.md
- docs/TICKETS.md
- docs/REPO_CURRENT_STATE.md
- README.md
- tests/integration/ if needed

Do Not Touch:
- raw_data/
- accepted_results/
- physics algorithms unless a separate task packet requires it
- secrets or credentials
- production deployment files unless explicitly authorized

Requirements:
- First use existing outputs or mock analysis files if raw data is not available.
- Connect real CLI steps one by one only after mock path is stable.
- Provide one command that runs the demo.
- Demo commands must treat --output-dir as an output root and write under <output_root>/<case_id>/<run_id>/.
- Ensure overwrite protection, manifest, graph_state, decision_log, approval packet for high-risk demo case, memory update, and final_report.md.
- README must allow another developer to reproduce the demo.

Non-goals:
- Do not change physics algorithms in this phase.
- Do not claim final physics results.
- Do not require private data or secrets.

Acceptance Criteria:
- One command runs a complete mock or golden example case.
- Every node input/output is traceable.
- pytest passes.
- final_report.md and decision_log.json are readable.
- high-risk demo does not enter accepted memory without human decision.

Verification Commands:
```bash
pytest -q
bash scripts/run_langgraph_demo.sh
```

Stop Conditions:
Stop if raw data access, private credentials, or algorithm changes are required.

End-of-task Updates:
- Update README.md.
- Update docs/ARCHITECTURE.md and docs/VERIFICATION_GUIDE.md.
- Update docs/TICKETS.md with Phase 9 status and the next Phase 10 ticket.
- Update docs/REPO_CURRENT_STATE.md.
- Final response: Changed / Why / Verified / Next
````

### Phase 10：Real LLM Provider Integration with Secure Environment Configuration

````text
Task:
Implement Phase 10 only: real LLM provider integration with secure environment configuration.

Read First:
- AGENTS.md
- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/AGENT_ROLES_AND_BOUNDARIES.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/SECURITY_AND_DATA_POLICY.md
- docs/VERIFICATION_GUIDE.md
- docs/PROMPT_PLAYBOOK.md

Allowed Files:
- .env.example
- .gitignore
- configs/runtime/openai.yaml
- configs/runtime/deepseek.yaml
- src/lqcd_agent/llm/base.py
- src/lqcd_agent/llm/mock_provider.py
- src/lqcd_agent/llm/openai_client.py
- src/lqcd_agent/llm/deepseek_client.py
- src/lqcd_agent/llm/structured_output.py
- src/lqcd_agent/llm/provider_factory.py
- tests/test_llm_config.py
- tests/test_llm_mock_provider.py
- docs/SECURITY_AND_DATA_POLICY.md
- docs/VERIFICATION_GUIDE.md
- docs/TICKETS.md
- docs/REPO_CURRENT_STATE.md
- docs/DECISION_LOG.md, only if an architecture decision is made

Do Not Touch:
- raw_data/
- outputs/
- accepted_results/
- existing graph routing logic
- existing scientific decision logic
- real .env files containing secrets
- human decision files
- production deployment files

Requirements:
- Create or update .env.example with placeholder variable names only.
- Do not create, print, commit, or request actual API keys.
- Add .env and .env.* to .gitignore, except .env.example.
- Support two provider configs: configs/runtime/openai.yaml and configs/runtime/deepseek.yaml.
- Implement a provider abstraction so Method Planner, Scientific Reviewer, and Decision Coordinator can later switch between mock, OpenAI, and DeepSeek providers.
- Keep mock provider as the default in tests.
- Live API calls must be disabled by default.
- Live API calls may run only when RUN_LIVE_LLM_TESTS=1 and the required environment variables are present.
- Never log full prompts containing secrets, API keys, or authorization headers.
- Structured outputs must still be validated against existing JSON schemas.
- If provider output is invalid JSON, write a structured error artifact rather than silently continuing.

Non-goals:
- Do not replace all mock agents with real LLM calls in this phase.
- Do not change graph topology.
- Do not change risk rubric.
- Do not modify raw data or golden example data.
- Do not introduce cloud deployment.
- Do not implement retry/cost optimization beyond minimal safe defaults.

Acceptance Criteria:
- .env.example documents required variables for OpenAI and DeepSeek without real values.
- .gitignore prevents real .env files from being committed.
- Provider factory can load openai.yaml and deepseek.yaml in dry-run mode.
- Mock provider tests pass without network access.
- Live test is skipped unless RUN_LIVE_LLM_TESTS=1.
- No test output prints API keys or secrets.
- docs/SECURITY_AND_DATA_POLICY.md explains how the user should create a local .env safely.
- docs/VERIFICATION_GUIDE.md documents dry-run and optional live-test commands.

Verification Commands:
```bash
pytest tests/test_llm_config.py -q
pytest tests/test_llm_mock_provider.py -q
python -m lqcd_agent.llm.provider_factory --config configs/runtime/openai.yaml --dry-run
python -m lqcd_agent.llm.provider_factory --config configs/runtime/deepseek.yaml --dry-run
git diff --check
```

Stop Conditions:
Stop and ask if a real API key is needed to proceed, a dependency must be added, existing graph state schema must change, provider API behavior is ambiguous, any code would print or store secrets, or live API calls are required for tests to pass.

End-of-task Updates:
- Update docs/REPO_CURRENT_STATE.md.
- Update docs/TICKETS.md with Phase 10 status and the next Phase 10B ticket.
- Update docs/DECISION_LOG.md if the provider abstraction changes architecture.
- Final response: Changed / Why / Verified / Next
````

### Phase 10B：Provider-backed Agent Wiring

````text
Task:
Wire the provider abstraction into Method Planner, Scientific Reviewer, and Decision Coordinator while keeping deterministic mock behavior as the default.

Read First:
- AGENTS.md
- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/AGENT_ROLES_AND_BOUNDARIES.md
- docs/STATE_SCHEMA.md
- docs/ARTIFACT_CONTRACTS.md
- docs/SECURITY_AND_DATA_POLICY.md
- docs/VERIFICATION_GUIDE.md
- docs/PROMPT_PLAYBOOK.md

Allowed Files:
- src/lqcd_agent/agents/method_planner.py
- src/lqcd_agent/agents/scientific_reviewer.py
- src/lqcd_agent/agents/decision_coordinator.py
- src/lqcd_agent/llm/provider_factory.py
- src/lqcd_agent/llm/prompts.py
- src/lqcd_agent/llm/schemas.py
- src/lqcd_agent/llm/structured_output.py
- tests/test_method_planner_mock.py
- tests/test_scientific_reviewer.py
- tests/test_decision_coordinator.py
- tests/test_llm_mock_provider.py
- docs/SECURITY_AND_DATA_POLICY.md
- docs/VERIFICATION_GUIDE.md
- docs/TICKETS.md
- docs/REPO_CURRENT_STATE.md
- docs/DECISION_LOG.md if agent-provider wiring changes architecture

Do Not Touch:
- raw_data/
- outputs/
- accepted_results/
- human decision files
- production deployment files
- real .env files containing secrets

Requirements:
- Keep mock provider as the default for all tests and smoke runs.
- Allow agents to use provider-backed structured output only through explicit config.
- Validate provider outputs before they affect routing.
- If provider output is invalid, write a structured error artifact and stop safely instead of routing on free-form text.
- Live provider calls remain disabled unless explicitly enabled by the provider policy.

Non-goals:
- Do not make live LLM calls required for tests.
- Do not change graph topology unless explicitly needed for provider selection.
- Do not change risk policy.
- Do not read raw numeric data.

Acceptance Criteria:
- Existing mock tests pass without network access.
- Provider-backed code paths can be exercised in dry-run or mock mode.
- Invalid provider output cannot influence graph routing.
- docs/VERIFICATION_GUIDE.md documents mock-default and optional provider-backed checks.

Verification Commands:
```bash
pytest tests/test_method_planner_mock.py tests/test_scientific_reviewer.py tests/test_decision_coordinator.py tests/test_llm_mock_provider.py -q
```

Stop Conditions:
Stop if live API access is required, if a real API key is needed, if provider output cannot be validated structurally, or if graph routing would depend on free-form text.

End-of-task Updates:
- Update docs/SECURITY_AND_DATA_POLICY.md if provider usage policy changes.
- Update docs/VERIFICATION_GUIDE.md with provider-backed dry-run checks.
- Update docs/TICKETS.md with Phase 10B status and the Phase 11 readiness criteria.
- Update docs/REPO_CURRENT_STATE.md.
- Update docs/DECISION_LOG.md if agent-provider wiring changes architecture.
- Final response: Changed / Why / Verified / Next
````

### Phase 11：Raw Data and Evaluation Case Library（后续构想）

```text
Purpose:
After the core graph, golden example, and real LLM provider integration are stable, create a read-only raw_data/ library and curated evaluation case library. Because the real data and examples are not prepared yet, this phase should remain a concrete concept for now, not an immediate implementation ticket.

Recommended Directory Concept:
raw_data/
  README.md
  data/
    <dataset_id>/
      manifest.yaml
      input_files/
      checksums.txt

evaluation/
  cases/
    good_example.yaml
    ambiguous_example.yaml
    bad_example.yaml
  reference_outputs/
    good_example/
    ambiguous_example/
    bad_example/
  expected_behavior/
    good_example_expected.yaml
    ambiguous_example_expected.yaml
    bad_example_expected.yaml

Each evaluation case should eventually define:
- case_id
- dataset_id
- input_data_manifest
- case_config_path
- expected_risk_level
- expected_recommended_action
- expected_required_warnings
- expected_human_gate_behavior
- notes_for_human_review

Expected behavior:
- good example: agents should not over-warn; expected low or low/medium risk; should enter Memory & Report; should not trigger Human Approval Gate.
- ambiguous example: agents should request targeted rerun or additional checks; expected medium or high risk; should not enter accepted memory directly; warnings must cite evidence.
- bad example: agents should detect severe warning; expected high or critical risk; should enter Human Approval Gate or HALT; must not enter accepted memory.

Implementation principles for the future ticket:
- raw_data/ is read-only.
- Keep labels and expected behavior under evaluation/, not inside raw_data/.
- Do not duplicate large data files unnecessarily.
- Use manifest.yaml and checksums.txt to track provenance.
- Never overwrite raw_data or reference outputs.
- If data is too large, store pointers, checksums, and small synthetic/minimal examples in the repo.

Future Codex instruction:
When the data and examples are ready, create a dedicated Phase 11 ticket with Allowed Files, Do Not Touch, Acceptance Criteria, and Verification Commands. Do not let Codex infer the physics labels or fabricate good/bad examples.
```

# 12. 风险等级与 Human Gate 规则

| Risk level | 触发条件示例 | 系统行为 | 是否需要人类 |
| --- | --- | --- | --- |
| low | run success；无 severe warning；diagnostics 稳定；证据充分。 | 写 decision_log，进入 accepted candidate memory，生成 final report。 | 不需要。 |
| medium | 有 minor warning；model dependence 可见但不阻塞；需要后续人工看一下。 | 继续生成 report，但标记 pending candidate / human_review_recommended。 | 建议复核。 |
| high | 有 severe warning；fit failed 较多；tmin/model dependence 明显；normalization 有疑问但可修复。 | 生成 approval packet 或 targeted rerun；promotion 前暂停。 | 必须审批。 |
| critical | 基础假设冲突；normalization 严重异常；关键输入缺失；结果不可解释。 | HALT 或进入 Human Approval Gate；不允许 AI 推进科学结论。 | 必须 PI/advisor 决定。 |

# 13. 第一版不要做什么

- 不要一开始实现十几个 agents。先保留 5 个主干 + Human Gate + Memory/Report。

- 不要让 Codex 直接决定 physics。Codex 只负责实现、测试和文档。

- 不要把 Codex Handoff Node 实现成运行时程序化调用 Codex。

- 不要把 Snakemake 和 LangGraph 职责混在一起。

- 不要让 Human Approval Gate 成为每步都打断人的 always-on gate。

- 不要让 route 依赖自由文本。所有 route-relevant 信息必须是 JSON/YAML 字段。

- 不要在 Phase 10 之前接真实外部 API；不要在 Phase 11 之前接真实 raw_data-backed examples；不要在任何阶段绕过 security/data policy。

# 14. 最终 Demo 验收标准

- 一条命令运行一个 mock 或 golden example case，从 config 到 final_report。

- graph_state.json 显示每个 node 的状态变化和 route 选择。

- Method Planner 生成 method_plan.json；code_needed 时生成 coder_task_packet.yaml。

- Codex Handoff Node 能读取 tests_status.json 并按测试结果路由。

- Analysis Engineer 能写 manifest、run.log、run_result 并解释失败原因。

- Scientific Reviewer 产生 correlator、fit、matrix element 三类诊断与 evidence-based warning。

- Decision Coordinator 输出 risk_level、recommended_action 和 human_approval_required。

- high-risk case 生成 approval_packet，且无 human decision 时不会进入 accepted。

- Memory & Report 节点正确写 accepted/pending/rejected memory 和 final_report.md。

- evaluation harness 至少覆盖 synthetic/mock good、ambiguous、bad 三类 case；Phase 11 后可扩展 raw-data-backed evaluation library。

- Phase 10 以后，真实 LLM provider 通过 .env.example / 本地 .env 安全配置；live tests 默认跳过，除非显式启用。

- Phase 11 以后，raw_data/ 与 evaluation/ 明确分离；good/ambiguous/bad cases 能用 expected_behavior 校验 agent 行为。
