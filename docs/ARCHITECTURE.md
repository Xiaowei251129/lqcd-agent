# Architecture

## 文档用途

本文只描述当前代码已经实现的架构，并把尚未执行的 `route intent` 和第二阶段缺口单独标明。未来方向不能被理解为已经存在的 graph edge。

当前 runtime 是一个 LangGraph `StateGraph`，包含五个核心 Agent/节点和两个支持节点。它负责组织可审计工作，不是 notebook wrapper，也不是自主科学决策者。

## 当前节点

核心 Agent/节点：

- Method Planner Agent
- Codex Handoff Node
- Analysis Engineer Agent
- Scientific Reviewer Agent
- Decision Coordinator Agent

支持节点：

- Human Approval Gate
- Memory and Report Node

## 当前真实运行路径

当前实现已经把以下模块接入真实 `StateGraph`：

- Method Planner Agent
- Codex Handoff Node
- Analysis Engineer Agent
- Scientific Reviewer Agent
- Decision Coordinator Agent
- Human Approval Gate
- Memory and Report Node

Codex Handoff Node 默认是 file-based handoff：写入或读取 `coder_task_packet.yaml`、`tests_status.json` 和 `code_change_summary.md`。只有显式启用 automatic handoff 时，运行时才可以调用本地 Codex CLI worker。它目前还不是完整的图内 Code Agent。

Human Approval Gate 同样是 file-based：它写 approval packet、读取 `approval_packet/07_human_decision.yaml`，但绝不改写人类决定。默认 Agent 路径是 deterministic；只有传入显式 provider config 时，Method Planner、Scientific Reviewer 和 Decision Coordinator 才调用 provider。

A02 corrective implementation 没有改变下面的 logical route outcomes，但已经改变它们的执行协议：每个 source node 领取预先 `scheduled` 的 Attempt，完成后由纯 selector 产生结构化选择，再由 control plane commit Transition 并在 target side effect 前分配下一个 Attempt。LangGraph conditional edge 只读取已提交的 `committed_route`；fixed route 和 END 也写 Transition record。

当前入口与主要路线是：

```text
START
  -> Method Planner Agent
  -> if code_needed == true:
       Codex Handoff Node
       -> tests pass: Analysis Engineer Agent
       -> missing/failed handoff result: END with pending or halted status
     else if plan is complete:
       Analysis Engineer Agent
     else if needs_more_info:
       END with pending status
  -> if run_success:
       Scientific Reviewer Agent
       -> Decision Coordinator Agent
     else if failure_type == code:
       -> if retry_count < max_retry: Codex Handoff Node
       -> else: Decision Coordinator Agent
     else:
       Decision Coordinator Agent
  -> if risk_level in high, critical:
       Human Approval Gate
     else:
       Memory and Report Node
  -> END
```

Human Approval Gate 当前路线：

- `approve_with_conditions` -> Memory and Report Node
- `approve_rerun` -> 记录 Analysis Engineer rerun intent，并以 `pending` 停止；当前不会真正恢复执行
- `request_code_change` -> Codex Handoff Node
- `reject_or_hold` -> Memory and Report Node
- no decision -> Memory and Report Node 写 pending memory/report artifacts；accepted memory 继续被阻止

## 已记录但尚未执行的路线意图

以下内容可能出现在 `decision_log.json`、`rerun_target`、`code_fix_requested` 或文档描述中，但不等于完整 runtime transition 已存在：

- 从非 code analysis failure 返回 Method Planner；当前实际保守路线进入 Decision Coordinator。
- `approve_rerun` 后自动返回 Analysis Engineer；当前仅记录意图并停止为 `pending`。
- 通过同一个 checkpoint 自动恢复旧运行；普通 CLI 入口仍初始化新 state，未实现正式 resume protocol。
- reviewer/coordinator 触发任意多轮闭环；当前只存在有限的 code retry 与 human decision 路线。
- 多 Agent fan-out 或并行 reducer；当前没有正式实现。per-attempt artifact namespace 已由 A03 实现，但没有因此开放新产品路线。

这些差距必须由 [Phase A](tickets/phase-a-control-contracts/OVERVIEW.md) 逐项明确合同，再由 Phase B harness 验证。A01 已确认逻辑路线合同；A02 corrective implementation 已完成并把当前可达路线接入 execution identity control plane。A01 的目标回退边和循环仍不能被视为现有 runtime 能力。

## A01 已确认的目标控制合同（尚未实现）

[A01 Transition Matrix](tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md) 已确认第二阶段的逻辑路线白名单。它是 A02–A07 和 Phase B 的实现约束，不改变上一节所述当前真实运行路径。

目标控制原则是“分布式结构化诊断、Decision Coordinator 集中回退决策”：

- 正常成功路径仍可按 Planner -> Code/Analysis -> Reviewer -> Coordinator 前进；
- 普通 Agent 只报告结构化 outcome、诊断证据和候选修复，不直接控制 graph-level 回退；
- 所有 re-review、rerun、code fix 和 replan 由 Decision Coordinator 根据受影响层级派发；
- low/medium risk 只有在诊断唯一且预算可用时才能自动循环；
- high/critical、诊断歧义、重复相同 failure fingerprint 或预算耗尽必须进入 Human Gate；
- Human Gate 统一处理 clarification、approval 和 external action，进出只连接 Decision Coordinator；
- Memory and Report 保持 terminal sink，不能重新发起循环。

目标逻辑拓扑是：

```text
START -> Method Planner
Method Planner -> Analysis Engineer | Code Agent | Decision Coordinator
Code Agent -> Analysis Engineer | Decision Coordinator
Analysis Engineer -> Scientific Reviewer | Decision Coordinator
Scientific Reviewer -> Decision Coordinator
Decision Coordinator -> Scientific Reviewer | Analysis Engineer | Code Agent
                      | Method Planner | Human Gate | Memory and Report
Human Gate -> Decision Coordinator
Memory and Report -> END
```

四个回退目标分别表示：重新审查相同 analysis、在相同 plan/code 下重新分析、修复实现、重新规划方法。候选目标冲突或无法唯一归因时不得默认选择最深回退，必须进入 Human Gate。

这里的 `Code Agent` 是 A05 已确认的 graph-managed目标接口，不是把当前 Codex Handoff 直接改名。A02 已确认 Run/Cycle/Attempt identity，A03 已实现 artifact invalidation；A04已确认PAUSE/resume控制合同，A05已确认Code Agent wire contract，A06已确认具体budget/fingerprint/stop合同。在这些合同对应的 Phase B harness 完成前，目标闭环不得接入 runtime。

## A02 当前 Execution Identity

[A02 Run/Cycle/Attempt Model](tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md) 已完成三层 identity 验收：Run 表示完整用户科研任务，Cycle 表示同一方法合同下的 execution epoch，Attempt 表示一次产生持久状态、artifact 或决策的 graph node invocation。

- 新 Run 首先写唯一 formal Run record，再写 initial Cycle、预分配 Planner Attempt，最后 commit START Transition；Planner identity 在 `app.invoke()` 前存在；
- 每个 current-route source wrapper 只领取 inbound Transition 指定的 Attempt，执行并结束它；Transition commit 应用显式 state updates、可选创建 Cycle、预分配 target Attempt，再把已提交 route 交给 LangGraph edge reader；
- Run-local `execution_history.jsonl` append-only 记录 `run`、`cycle`、`attempt`、`transition`、`human_request` 和 `human_response`；state 只保存 bounded current pointers 和 counters；
- physical node 与 canonical Attempt kind 分开记录：当前 `codex_handoff` 是 `legacy_codex_handoff`，`human_approval_gate` 是 `human_gate`；canonical `code_agent` 只为 A05/Phase B 预留；
- Coordinator 进入 Gate 时创建独立 Human Request；外部 response 获得独立 identity，只能由 `human_gate` Attempt 验证，并由 scope 内的一次 compatibility transition 消费；
- Agent、router 和 human decision payload 都不能创建、改写或复用 control identity；`START`、`END` 与 Human Request/Response 都不是 Agent Attempt。

re-review、analysis rerun、code fix 和 replan 目前只在最小 deterministic StateGraph integration harness 中经过真实 selection/commit/target-consumption protocol；这只能证明 identity protocol，不代表产品 graph 已开放四层回退。特别是 harness 中的 `code_agent` 只是 protocol sink，不是 Fake/real Code Agent。

legacy incomplete-Run re-entry 会校验 formal Run immutable fields，并从 ledger 恢复 counters，但这只是 compatibility audit continuity，不是 checkpoint resume。Run-owned `checkpoint_thread_id` 与 canonical output root 未改变；A04已冻结PAUSE/resume与replay/fork目标API，A05已冻结Fake/real graph-managed Code Agent的共同合同，A06决定budgets/failure fingerprint，A07/Phase B才负责A01完整产品线路和禁止路线harness。

## A03 当前 Artifact Control Plane

每个 graph-managed domain bundle 写入 `<run_root>/attempts/<attempt_id>/`，随后注册到 append-only `artifact_history.jsonl`。`artifact_index.json` 是唯一 current-selection authority，固定 slots 为 `plan`、`code`、`analysis`、`review`、`decision`、`approval`、`terminal`；state 中的 `current_artifacts` 与 convenience paths 必须与 index 一致。

Transition commit 在目标 Attempt 分配后、目标节点副作用前按 target layer 清除 current pointer：re-review 清除 review 及下游，analysis rerun 清除 analysis 及下游，code fix 清除 code 及下游，replan 清除全部 slots。Decision、Human Gate 与 Memory Report 使用相同的 target-layer规则。清除只修改 current index、bounded state 和 managed projection，不删除 canonical bytes 或 history。

run-root 的 v0.2 fixed paths 现在是 registry-managed copy projections，不是 canonical history。只有带有效 A03 index 且记录 owner 的 projection 才能替换或清除；unmanaged legacy trees 不迁移、不覆盖。Human Response payload 以 `<run_root>/human_responses/<human_response_id>/payload.json` 保存，accepted terminal bundle追加保护事件。A03 没有实现 crash recovery、并发提交或 replay；A04已确认相关目标合同，runtime仍由Phase B实现。

## Checkpoint 与上下文边界

Checkpointing 与 LLM context 是两个不同问题：

- local CLI 使用 SQLite checkpoint，unit/smoke tests 使用 `MemorySaver`；
- checkpoint database 位于 `<output_root>/<case_id>/<run_id>/checkpoints/`；
- 同一 `case_id` 和 `run_id` 的 `checkpoint_thread_id` 必须稳定；
- `graph_state.json` 在重要节点完成和 route decision 后写出；
- LLM 只能收到挑选后的 state fields 与 bounded artifact summaries；
- routing 不能依赖被截断或概括后的自由文本。

A01 进一步确认：完整 `event_log`、route trace 和 checkpoint state 只用于 runtime、审计和 UI，不直接注入 Agent prompt。目标工作 Agent 只读取 scoped current context、typed remediation packet、直接父 attempt 和与当前问题相关的 bounded attempt history；Decision Coordinator 读取 bounded global execution summary。跨 Run 经验必须经过测试或人类确认后才能进入 curated knowledge，Agent 不能从单次经历直接改写长期规则或 routing policy。

当前 checkpoint persistence 不应被误称为完整 pause/resume。正式恢复的目标语义已由 [A04](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md) 冻结，但尚未由Phase B实现。

## A04 已确认的 Pause/Resume 控制架构（尚未实现）

A04冻结项目自有的`start_run`、`resume_run`、`replay_run`、`fork_run`与`cancel_pause`外部合同；`advance_run`、`publish_pause`、`close_run`和`resolve_external_interrupt`仅供可信control plane内部调用。START bootstrap与Human Response resume之外的每个普通Transition都由`advance_run`持有，committed result之前不得激活target invocation capability。客户端不接收raw LangGraph checkpoint、thread ID、任意state patch或route override。所有mutation在写Run、Pause、checkpoint、child bytes或外部副作用前，必须先进入A02C01定义的单一project-owned SQLite coordinator，绑定canonical request digest、durable operation ownership、monotonic phase revision和`lease_epoch`。

目标execution schema `0.3`引入append-only `run_lifecycle` authority及其受限`run_status = initializing | running | paused | completed | failed | halted` projection；现有`AnalysisState.status`继续表达领域结果，不决定Run是否terminal或可恢复。只有latest lifecycle为stable `paused`、latest active Pause为unclaimed `opened`、public paused checkpoint与execution/artifact heads exact闭合且Run没有terminal owner时，`resume_run`才可claim。`human_input`、`external_result`和`recovery_decision`三类Pause均single-use，固定经历`prepared -> opened -> claimed -> consumed`或显式取消/中断终态。

Pause publication使用非对称两checkpoint边界：`pause_prepared`首次分配identity，prepared checkpoint引用其resulting head；随后提交`run_lifecycle(running -> paused)`和`pause_opened`，public paused checkpoint再引用opened resulting head。Resume必须先原子取得Pause owner，再完成reason-specific pre-start记录、`pause_consumed`、`run_lifecycle(paused -> running)`和running checkpoint，最后才允许target `started`或任何副作用。exact且预计算的无副作用suffix只由原operation materialize；缺少预授权或副作用结果不确定时terminal为`recovery_required`，实际head/digest矛盾进入integrity failure，二者都不得自动重跑Attempt。

每个Run只有一个fenced terminal closure owner。普通END、non-Pause failure和没有unresolved ExternalOperation的独立stop使用`close_run`；`cancel_pause`、`resume_run(abandon_and_halt)`和terminal external interrupt在原operation内嵌terminal tail，不能再创建第二个close。显式取消只处置latest opened cancelable Pause：existing scheduled target在完整处置中变为`abandoned`，null target保持null，partial cancel不能启动target或自动repair。authority不能安全验证或append时只报告`terminal_closure: unavailable`并隔离，不伪造`run_status: failed`。显式取消、normal/cancel/interrupt仲裁及ExternalOperation stopping都复用Control Protocol `0.4`的单一CAS域和唯一winner。

Replay只从source immutable root inputs创建新child并从`START`执行；Fork只对source latest validated stable paused/terminal head和`source_control_revision`完成CAS后选择eligible immutable evidence，同样创建全新Run/Cycle/Attempt/Transition identities并从`START`执行。两者都不复制source checkpoint/current pointers/Pause/Human authorization/accepted status，也不修改source artifacts。Schema `0.2` source只可验证后replay；Phase B `0.4`不原地resume或迁移schema `0.3`，只resume exact supported `0.4` fingerprint。

以上是Phase B实现约束，不是当前架构能力：当前CLI、demo server、LangGraph checkpointer、`graph_state.json`和legacy Human decision re-entry均未改动，仍不能调用这些A04接口。

## A05 已确认的 Code Agent 控制架构（尚未实现）

[A05 Code Agent Contract](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)冻结一个稳定的`CodeAgentSubgraph`边界和可替换的`CodingBackend`语义端口。Parent LangGraph只看见一个canonical `code_agent` Attempt及其structured outcome；subgraph负责task、workspace identity、A06 reservation、A04 Pause/Resume、trusted verification、artifact registration和route outcome，外部backend只执行受限编码工具循环，无权修改graph state、ledger、registry、budget或route。

目标调用关系为：

```text
Parent LangGraph
└── CodeAgentSubgraph
    ├── prepare_external_operation   trusted pre-start control
    ├── wait_external_result         A04 external_result Pause
    │   └── trusted Host -> CodingBackend outside replayable graph
    └── consume_code_agent_result    the only code_agent Attempt work stage
```

Inbound Transition先分配尚未started的`code_agent` Attempt。可信Host随后按Control Protocol `0.4`先持久化Host-owned`producer_operation_id`与workspace identity，再冻结`CodeAgentTask`、未物化的`WorkspaceManifest`、A06 reservation及immutable ExternalOperation core；physical workspace只在current external lease epoch下物化。Run发布完整public paused checkpoint后，Host才可调用`dispatch`。`lookup`只能查询原operation，`fetch_result`只返回immutable result reference，`cancel`只能停止exact operation；Host重启、receipt缺失或backend `unknown`都不能触发第二次dispatch。

Normal、cancel和interrupt通过与A04 ControlOperation同一`coordinator_sqlite`事务域内的single-owner CAS仲裁，并统一收敛到机器协议规定的唯一final evidence。真实local backend还必须由Host-owned containment完成write-lease revocation、完整descendant process停止、bounded output drain、`verify_empty`与post-stop stability；证明不完整时只能`recovery_required`并隔离，不能伪造failed Run或canonical bundle。

Backend delivery先作为不可信入口由Host验证task、Attempt、base、workspace、receipt、seal、member digests、scope、policy和authorization。随后trusted verifier在exact base加validated change的fresh workspace执行typed required specs。通过Host归属与schema验证的canonical outcome可按其status注册content-addressed `code` bundle；只有`success + usable=true`且全部A01/A06 guards通过，才可由新的`advance_run`提交到Analysis，其他合法status全部进入Decision Coordinator。Malformed或越权ingress不注册bundle，也不形成产品Transition。

Analysis不加载mutable coding workspace，也不执行当前control repository。Host为新的scheduled Analysis Attempt冻结`AnalysisExecutionSpec 0.1`，从相同immutable base和verified change materialize新的worktree，以新subprocess执行。该交接与patch promotion分离；A05不批准写回control repository、commit、merge、push、PR或deployment。

Phase B只使用遵守相同端口、validator、verifier、registry和fresh Analysis路径的`FakeCodingBackend`。Python Codex SDK只是Phase C候选；独立C00必须先用pinned build证明restart-safe lookup、完整tool audit、exact process-tree cancellation、workspace/credential containment、immutable evidence与fail-closed crash行为，才能由C01选择真实backend。当前legacy handoff、runtime graph、dependencies和provider配置均未改变。

## B00 Acceptance Foundation（已实现，非 Runtime Authority）

`src/lqcd_agent/control/_generated_protocol.py`由tracked generator消费冻结protocol/catalog exact bytes生成，递归使用只读mapping和tuple；`control/protocol.py`只提供纯lookup。Import和lookup不读取docs、fixtures、环境、clock或provider。当前graph没有接入该模块，不改变现有schema `0.2`。

`tests/phase_b/`持有strict matrix、normalized trace、pytest evidence writer、typed failpoint registry与独立final obligations。B00只映射15项construction requirements；324项inventory和2286条final cases（含7×4 post-claim paths）不等于已实现production hooks。Registry binding可由后续票追加，但inventory/case清单由独立seal保护。

`scripts/validate_phase_b_acceptance.py`拥有fresh session、实际工作树摘要、pytest subprocess和最终closed report。Construction只验当前slice；final同时验两个stage、实际hook/trace及15项必需退出检查。B05在既定typed adapter入口接入真实检查，不能从CLI注入runner或旧结果。测试用隔离runner不属于project验收。

这套foundation不创建Run、SQLite coordinator、Pause、budget、Backend、workspace或产品Transition。`requirements_zero_gap`与`phase_b_complete`仍为false；实现和验收事实见[B00 Completion](tickets/completions/B00_COMPLETION.md)。

## A06 已确认的 Budget 与 Stop 控制架构（尚未实现）

[A06 Budgets and Stop Conditions](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)冻结可信控制层的`BudgetPolicy 0.1`、`BudgetDecision 0.1`、`FailureFingerprint 0.1`和single-use `BudgetGrant 0.1`。每个schema `0.4` Run在正式creation前选择allowlisted immutable policy；`balanced_v1`是保守默认，`phase_b_test`只供deterministic harness。Agent、router、provider、Backend和Human自由文本均不能选择profile、修改policy/counter、退款或决定retry/stop。

所有Cycle、Attempt、Transition和automatic-route用量从`execution_history.jsonl`的权威记录重放；LLM/tool/verification及每个Code Agent Attempt唯一的`code_backend_operation` aggregate必须在副作用前reservation并exactly-once settlement，未结算crash按maximum charge且不自动重试或退款。完整budget history不进入graph state或prompt；state只保存与validated policy/ledger exact-equal的bounded projection。Token和cost usage仅供审计，缺失时保留`unknown`，不作为第一版hard gate。

Admission固定在target allocation、A03 invalidation、Transition commit和任何副作用之前产生并持久化exact decision。Failure fingerprint排除Run/Attempt/workspace/job等执行identity和自由文本，只对base、policy、runtime、verified change、material inputs与稳定诊断敏感；同一Run内第二次exact fingerprint不能自动fallback。Human只能通过validated `approve_budget_window`为exact route/fingerprint/target增加一次机会，不能突破Cycle、Work/Control Attempt、Transition或资源全局上限。

每个Run从绝对上限中保留5个Control Attempts和6个Transitions，只用于typed `stop_sequence_id`安全收尾链；普通路线不能消费。Pause deadline由trusted Host clock派生，过期resume不产生任何mutation。资源停止只有在termination、write-lease revocation、bounded drain与post-stop stability均证明后才能形成受控`halted`或已证明的`failed` closure；证明缺失必须隔离为`recovery_required`/`terminal_closure: unavailable`，不得伪造Run lifecycle。完整route、resolution与Pause/Run owner仍以Control Protocol `0.4`为唯一机器权威，A06不建立第二套状态机。

以上是Phase B schema `0.4`实现约束，不是当前架构能力。当前runtime仍使用schema `0.2`、`retry_count/max_retry`和普通LLM trace，没有budget policy artifact、budget ledger、resource reservation、semantic failure fingerprint、grant、trusted clock或terminal reserve执行器。

## Command 边界

运行时只允许 allowlisted mock、test、smoke 和 internal statistical benchmark commands。Golden Demo 使用 `mock:write_golden_example_matrix_elements`；Phase 10C generated cases 使用 exact-allowlisted `analysis:run_synthetic_benchmark:<scenario_path>`。每次执行必须在 manifest 中记录 command、working directory、return code、timeout、stdout/stderr summary 和 output paths。

## Output 边界

实际 Run root 是 `<output_root>/<case_id>/<run_id>/`；canonical graph-managed domain artifacts 位于其 `attempts/<attempt_id>/` 子目录，run-root fixed paths 仅是 current compatibility projections。仓库内 `outputs/` 是被忽略的实际运行目录，不是 reference-output 目录。curated evaluation baseline 位于 `evaluation/reference_outputs/`，expected behavior 位于 `evaluation/expected_behavior/`。

没有 `--run-id` 时 CLI 生成 timestamp run id；显式 run id 指向已有完成/决策 artifacts 时，CLI 拒绝复用目录。A04 resume目标合同已获批准但当前CLI尚未实现；force overwrite仍未获批准。

## Provider 边界

默认 provider 行为 deterministic 且不联网。显式 `llm_provider_config_path` 或 CLI `--llm-provider-config` 才启用 provider-backed structured output。输出必须通过 strict JSON schema validation 后才能写 artifact 或影响 routing；失败时只允许通过保守结构化字段路由。Phase 10D 会把非 secret request/response audit records 写到 run-local `llm_calls/`，并登记在 manifest 和 final report。

Scientific Reviewer 和 Decision Coordinator 只向 provider 发送 bounded artifact summaries，不发送 raw numeric data。Decision Coordinator 先计算 local deterministic risk；provider 可以增加 structured reasoning，但不能把 high/critical local evidence、severe warning、failed run 或 unusable artifact 降为 low-risk accepted memory。若 provider 低于 local floor，`decision_log.json` 记录 `provider_safety_floor`，并走保守路线。

Local console 可发现 YAML/JSON cases、预览分析路线、选择已配置 provider，并在没有显式 opt-in 环境变量时阻止 live provider。默认 output root 是仓库内被忽略的 `outputs/`。

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [State Schema](STATE_SCHEMA.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
