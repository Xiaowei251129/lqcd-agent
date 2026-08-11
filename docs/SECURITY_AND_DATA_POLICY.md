# Security and Data Policy

## 政策权威

本文记录当前持续有效的数据、安全、执行与审批边界。普通 ticket 可以在这些边界内实现功能，但不能静默放宽边界。若 ticket 与本文、根目录 `AGENTS.md` 或现有 schema 冲突，执行者必须停止并请求明确决策；政策变化还必须写入 [Decision Log](DECISION_LOG.md)。

## Raw Data Policy

`raw_data/` immutable 且 read-only。Agent、command runner 和 implementation task 均不得写入。

在正式 raw-data access policy 获批前：

- runtime 不得读取 real raw numeric data；
- 可以读取 raw-data manifest、description 与 checksum；
- synthetic evaluation data 不得放入 `raw_data/`；
- raw-data-backed evaluation 必须由独立 ticket 与政策决策明确批准。

## Output 与历史保护

实际运行 artifacts 必须写入 `<output_root>/<case_id>/<run_id>/`。仓库内 `outputs/` 是 ignored actual-run root，不是 reference-output location。

- 默认不得覆盖已有 run directory；
- accepted results 与 human decisions 必须 append-only 或 versioned；
- verification 应优先使用 `/private/tmp/lqcd-agent-...`；
- curated baselines 属于 `evaluation/reference_outputs/`；
- expected behavior 属于 `evaluation/expected_behavior/`；
- resume、force overwrite、attempt namespace 和 artifact invalidation 尚未形成正式合同，必须等待对应 Phase A ticket。

## Command Policy

Analysis Engineer 只能通过 `src/lqcd_agent/tools/command_runner.py` 运行受限命令：

- runner 内置的 `mock:` commands；
- case allowlist 中 exact-matched 的 `analysis:run_synthetic_benchmark:<scenario_path>`；
- case/task allowlist 中 exact-matched 的 local command。

runner 必须阻止 shell control operators、非 exact-allowlisted commands，以及引用 `raw_data/` 或 `accepted_results/` 的路径；subprocess 必须使用 `shell=False`。

每次执行必须记录：

- command、working directory 与 timeout；
- return code 与 stdout/stderr summary；
- produced files；
- warnings 与 errors。

命令不得修改 raw data、accepted results、human decision files、secrets 或 dependency files，除非未来的明确政策与 ticket 同时允许。

## Secrets Policy

真实 provider credentials 只能保存在本地，禁止 commit、print、log 或写入 artifact。

- `.env`、`.env.*` 等 secret files 必须被 git ignore，`.env.example` 只保存 placeholder names；
- repo-local `.env` 可以被读取，但不得覆盖已经 export 的 environment values；
- dry-run 只能报告 readiness、opt-in status、缺少的 variable name 和 non-secret metadata；
- live provider 默认关闭，只有 `RUN_LIVE_LLM_TESTS=1` 与对应 key/model variables 同时存在时才允许；
- `llm_calls/` 不得包含 API key 或 environment-variable value。

## LLM Provider Policy

默认路径必须 deterministic 且 network-free。只有显式提供 `--llm-provider-config` 或测试注入 provider 时，Method Planner、Scientific Reviewer 与 Decision Coordinator 才能调用 provider。

- provider output 必须通过 strict structured validation 后才能影响 artifact 或 routing；
- invalid JSON/schema failure 必须写 structured error artifact，不能退回自由文本路由；
- prompt 只使用 bounded artifact summaries，不使用 raw numeric data 或 unbounded logs；
- reviewer warning 必须 structured 且 evidence-grounded；
- provider 不能降低 deterministic local risk floor；
- unsupported provider escalation 不能绕过 local evidence policy；
- provider 或 RAG 增强不得扩大 Agent 的文件权限、科学裁决权或审批权。

## Human Approval Policy

- high/critical outcome 在 accepted memory 或 accepted-result promotion 前必须有人类批准；
- medium outcome 可以生成 report，但保持 pending/review-recommended；
- Human Approval Gate 不得改写 decision file；
- 没有有效 decision 时可以写 pending audit artifacts，但 `accepted_result` 必须保持 false；
- ticket 不得把 Human Gate 变成形式上的自动批准步骤。

## 第二阶段相关待决事项

以下内容仍是 draft，不改变当前政策：

- [A03 Artifact Invalidation](tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md)
- [A04 Pause/Resume](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)
- [A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)
- [A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)

## 相关文档

- [Project Specification](PROJECT_SPEC.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Tickets](tickets/README.md)
