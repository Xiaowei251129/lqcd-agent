# Security and Data Policy

2026-10-17 B04完成：canonical产品路径以Fake Agent/Backend及合成数据验收；该canonical路径的真实provider/Backend、raw data和code promotion继续deferred。风险优先于budget，Human授权/grant绑定原scope并单次消费；不会绕过absolute ceilings/terminal reserve。原authority无法证明时保留recovery_required，不重执行不确定effect、不伪造terminal。 见[完成记录](tickets/completions/B04_COMPLETION.md)。以下日期条目为历史记录。

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
- accepted results 与 human decisions 必须 append-only 或 versioned；Human Response payload 使用 exclusive-create immutable snapshot；
- verification 应优先使用 `/private/tmp/lqcd-agent-...`；
- curated baselines 属于 `evaluation/reference_outputs/`；
- expected behavior 属于 `evaluation/expected_behavior/`；
- canonical domain artifacts 写入并严格绑定`attempts/<attempt_id>/`且不得覆盖；只有registry-owned current projection可以替换或清除，跨owner collision必须在复制前失败；external ingress只豁免内容digest比较，路径、存在性和owner仍必须验证；
- unmanaged legacy outputs 不自动迁移、不覆盖、不删除；
- A04已确认resume/replay/fork/cancel与crash分类的目标合同；默认runtime未接入这些接口，已完成的显式B02 control入口见下节，force overwrite继续禁止。

## A04 控制操作安全政策（目标合同，尚未完整实现）

B02当前已验证Host scope、单一coordinator ownership、实际失败边界epoch/revision隔离、invocation fencing及持久化failure closure。旧worker错误不能借同worker新epoch终结操作；消费失败保留原external final并撤销能力/隔离binding；无法证明停止和可追加authority时只形成unavailable。0.2/0.3 source和拒绝的Resume均保持全部来源文件不变，checkpoint验证只打开完整main/WAL/SHM私有副本。`ActorContext`由可信Host建立，不是对任意同进程调用者的认证沙箱。B03 Backend/containment和B04产品admission仍由后续票据交付；见[B02完成记录](tickets/completions/B02_COMPLETION.md)。以下政策保持原批准含义。

- `start_run`、`resume_run`、`replay_run`、`fork_run`与`cancel_pause`只接受可信Host构造的`ActorContext`和allowlisted scope；Agent、graph node、model output或payload不能自签actor、路径、thread或checkpoint authority；
- 所有mutation必须在任何Run/Pause/child/checkpoint bytes或外部副作用前，由单一project-owned coordinator持久化canonical request digest、idempotency key、operation owner、phase revision与current `lease_epoch`；进程内lock或LangGraph metadata不能替代该authority；
- 外部接口不得暴露raw checkpoint ID，不接受arbitrary state patch、route override、force overwrite、provider/security policy override或调用方选择的output root；
- 只有latest exact opened/unclaimed Pause、stable `run_status: paused`、public paused checkpoint与matching runtime fingerprint可以resume。错误actor/scope/Run/Pause、stale owner、digest/fingerprint mismatch、unsupported schema或不确定副作用均fail closed，不自动rerun；
- `cancel_pause`只能处置latest opened cancelable Pause并与normal/cancel/interrupt共享single-winner CAS。stop proof不完整时隔离为`terminal_closure: unavailable`，不得伪造安全停止、Run failure或accepted artifact；
- Replay/Fork必须创建新Run并保持source与accepted evidence不可变；不得继承Human authorization、active Pause、accepted status或source写权限。Schema `0.2` source只能在root inputs完整验证后replay，不能fork或原地恢复。

## A05 Code Agent 安全政策（目标合同，尚未实现）

- 每个canonical `code_agent` Attempt使用新的Host-owned isolated workspace和immutable full-commit base；dirty control worktree、另一Attempt workspace、mutable provider session或旧result不能成为base；
- Host在任何workspace bytes前持久化`producer_operation_id`、managed workspace identity和external lease epoch，在immutable task/manifest/A06 reservation/core闭合且A04 public paused checkpoint完成后才可dispatch；crash、receipt缺失或backend `unknown`只能lookup原operation，不能redispatch；
- task的read/write/forbidden paths必须是normalized repository-relative POSIX paths。Forbidden规则优先；absolute、empty、`..`、normalization collision、symlink/hardlink/submodule/mount escape、Git metadata、device/socket及未授权binary/mode变化均拒绝；
- `.git`、control repository、Run output、raw data、accepted results、checkpoint/control records、Human responses、secrets和credential files永远不可写。Raw numeric data与accepted payload默认不进入context；扩展数据权限必须另开安全设计ticket；
- workspace、backend tool与trusted verification process默认断网，Agent/task不能打开network。Provider transport只可由sandbox外trusted Host按现有provider policy配置，credential不得挂载进workspace或写入task/artifact；
- backend工具使用Host allowlisted typed argv、cwd、environment keys与timeout，不执行task自由shell。Host wrapper生成连续、redacted、可验证的tool audit，Agent自报命令或tests不是authority；
- backend只能通过`dispatch | lookup | fetch_result | cancel`端口处理exact Host-owned operation，无权修改graph、ledger、registry、Pause、budget、authorization或route。Trusted Host必须对immutable delivery执行identity/digest/path/scope/policy检查，并在fresh workspace独立验证；
- 真实local backend必须由`ContainmentProvider`执行write fencing、lease revocation、graceful terminate、bounded grace、containment-level kill-all、bounded output drain、`verify_empty`与post-stop stability。仅process group不足以声明strict descendant containment；任一证明维度false/unknown时隔离workspace并返回`recovery_required/terminal_closure: unavailable`；
- `success` bundle只授权Run-local fresh Analysis execution，不授权修改control repository、patch promotion、commit、merge、push、PR、deployment、科学接受或accepted memory。执行中需要扩权时返回`needs_human`，新授权只能绑定新的Attempt/task；
- Phase B只使用同合同的deterministic Fake。Python Codex SDK或其他真实backend必须先通过独立C00对restart-safe lookup、完整audit、exact cancellation/containment、workspace/credential隔离、immutable result和fail-closed crash的全部门禁；不得因候选provider能力不足降低本政策。

## A06 Budget 与 Stop 安全政策（目标合同，尚未实现）

- `budget_policy.json`在Run正式创建前由可信Host从固定allowlist选择并create-new发布；Agent、provider、tool、Backend、route payload、Human自由文本和resume payload都不能改写profile、policy、counter、remaining或terminal reserve；
- admission必须先验证execution/artifact/checkpoint heads、risk/security/data/accepted-result规则，再重放policy、usage、reservation和grant。Budget充足不能降低风险下限，也不能把policy/security/data或non-retryable scientific failure变成automatic retry；
- LLM/tool/verification与Code Backend aggregate在外部副作用前reservation，crash未结算按maximum charge且不退款、不redispatch。Backend只能消费exact envelope；reported usage、thread/job/session identity和自由文本都不是结算或扩容authority；
- failure fingerprint必须由稳定typed facts及material evidence digest生成，排除执行identity、时间、物理路径、summary和原始日志。新Attempt/workspace/job不能规避同一Run内第二次exact fingerprint升级；
- Human grant只能由validated `approve_budget_window` response派生，绑定exact actor、Pause/snapshot、route、fingerprint occurrence与target，且只增加一次对应route机会；不能突破Cycles、Work/Control Attempts、Transitions或resource global ceilings，也不能恢复terminal reserve；
- 每次普通admission后仍须保留5个Control Attempts和6个Transitions的完整terminal tail。Reserve只能由typed `stop_sequence_id`收尾链消费，不能返回Work Attempt或为无容量的invalid-response repause开新Pause；
- Pause deadline使用trusted Host clock。过期resume、clock回退或overflow必须无mutation fail closed；不得通过background timer自动cancel、halt、replay或fork；
- 只有完整证明termination、write-lease revocation、bounded drain与post-stop stability，才允许`halted`或已证明`failed` closure。任一证明维度缺失必须隔离为`recovery_required`/`terminal_closure: unavailable`，不得用maximum charge、可append ledger或bounded projection伪造安全停止或Run lifecycle。

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

## 第二阶段目标政策状态

[A04 Pause/Resume](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)、[A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)、[A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)与[A07 Harness Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)已完成目标政策/验收合同同步，但尚未实现。A07 completion不会改变当前runtime政策。当前runtime仍没有schema `0.4` coordinator、Pause/Resume、Code Agent、budget enforcement或Phase B acceptance harness。

## 相关文档

- [Project Specification](PROJECT_SPEC.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Tickets](tickets/README.md)

## B02C01 legacy reader边界（2026-09-18）

已批准的legacy fingerprint缺失值只描述0.2 replay来源事实，不授予resume、fork、target执行或source写权限。读取旧config前先验证历史reference、Run身份、路径及原bytes摘要；当前reader仅接受project-owned `configs/cases/`、`evaluation/cases/`及该output root下既有Host生成位置`_generated_case_configs/`中的JSON或既有flat YAML格式。路径必须canonical、无symlink/隐藏组件，文件为唯一regular file；不跟随config中的raw-data或其他payload引用。其他位置或格式在reservation前拒绝，不根据公共request扩大读取范围。此限制沿用可信case输入用途，不授权raw numeric data、secret或provider访问。见[B02C01执行记录](tickets/completions/B02C01_COMPLETION.md)。

2026-09-18 B02安全边界：normal external消费、timeout受限消费和准备端口均由coordinator/lease/terminal owner fencing约束；历史reader是可信Host端口，不接受公共caller给出的validated flag或自选文件根。原0.2/0.3来源保持只读，未使用真实Backend/provider、raw data、repository outputs或生产process kill。B02完整验收尚未完成；新的historical trace格式仅起草[B00C03](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)，未改动既有验收检查。
