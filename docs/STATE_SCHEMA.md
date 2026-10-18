# State Schema

2026-10-17 B04完成：现有schema0.4身份不变：initial/replan产生新Cycle，四层其余retry产生同Cycle新Attempt；capability只消费原producer committed result。普通失败保留真实outcome/Host receipt并单次settlement，unknown token/cost保持typed unknown。实际安全收尾才发布terminal，authority/停止不可信保留unsettled/recovery_required；Run terminal owner fence阻止旧capability写入。 见[完成记录](tickets/completions/B04_COMPLETION.md)。以下日期条目为历史记录。

2026-10-16 当前：**C27 completed；C26 经逐项独立复核 completed；B04 经独立入口复核恢复 ready**。显式 trace 0.12/proof 0.9 的四阶段故障来源、窄 CAS 记账和父恢复 Host fixture 已交付。固定输入完整 **4674/4674**（legacy325、新增96）、原 **18 boundaries/144 cases 各两份 fresh**、同 Session 独立 owned **B02 1410/B03 645**、fresh construction **15/11/30/28** 通过；final 原具体缺口仍为 **47/144/15**。B04 owned **0/144**，仍须原产品集成和正式47/144验收。131/84/47、2199cases/324boundaries/28post-claim、原owners、B05 draft与Phase B false保持。交付文档与实际验收输入分别存档，不重标Session，无commit/push。以下日期条目保留历史。 见[完成记录](tickets/completions/B00C27_COMPLETION.md)与[来源合同](tickets/corrections/B00C27_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_CONTRACT.md)。

2026-10-15 当前：**C27 blocked（完整验收容量不足）；C26/B04保持blocked**。第四轮原生来源验收133通过、1失败后停止；首次C22 prefix必要父目录的校验遗漏已在批准范围内修复，补跑12/12、C25–C27专项125/125通过。当前精确收集4674项（原4578+96新增），尚无修复后全量/同Session owned/全部144双fresh通过声明。可用约5.75GiB，完整重跑预估至少10.75GiB；3285候选临时目录无可安全清理项，全部旧native/sealed/反例保留。B04 owned0/144、原47construction/144owned/15exit、131/84/47及2199cases与owners保持。C27完成后仍须C26独立审计及B04入口；无需因本次局部修复新增纠偏票。下方日期条目保留历史。 见[本轮记录](tickets/completions/B00C27_COMPLETION.md)。

2026-10-14 C27实施接续：**C27 in_progress；C26/B04仍blocked**。显式trace0.12/proof0.9、原生四阶段/原调用来源、窄CAS记账和有界Host fixture已进入专项验证；原9组18份fresh来源及119项专项通过，补充control拒绝分支已复核。原144双fresh、完整当前输入full/独立owned/construction及交接尚待完成，不提前声明整票通过。B04 owned0/144、47construction、131/84/47、2199 cases、18/144与15exit及原owners保持。下方日期记录保留历史。 见[来源补充合同](tickets/corrections/B00C27_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_CONTRACT.md)与[执行记录](tickets/completions/B00C27_COMPLETION.md)。

2026-10-14 C26执行停止：**C26 blocked；[C27合并补充待审](tickets/phase-b-graph-harness/B00C27_B04_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_FIXTURE_HANDOFF.md) review；B04仍blocked；C23/C24/C25 completed保持**。已保留S0–S3捕获/私有来源候选并通过C25原29项回归，但原重复publication使capability revision真实增加，Human父恢复创建的后续Pause identity在双fresh不同；当前冻结“无新增业务写入”和旧identity规则不足以直接交付。新0.12尚未启用，完整144 source-bound/full/owned/construction未完成，不能声明C26已解决B04阻塞。C27拟合并窄CAS记账分类、显式测试Host fixture接续及C26全部剩余验收，尚未批准或实施；B04 owned0/144、47construction、131/84/47及2199/324/28/144/15与原owners保持，无commit/push。见[C26实际记录](tickets/completions/B00C26_COMPLETION.md)。下方日期条目保留历史。

2026-10-14 B04正式接线探针停止：**B04 blocked；C26 review；C23/C24/C25 completed保持**。原故障工厂双fresh诊断通过，但删除capability／损坏canonical member后，故障前Run来源在0.10与显式0.11重验仍严格拒绝；正式B04绑定还会使C25“必须未绑定”的meta断言失败。两类缺口已保存原生反例并合并待审，未改production/harness/registry/expected，未实施0.12。B04仍owned0/144、47construction未完成，131/84/47、2199/324/28/144/15和owners保持。当前没有新full/owned完成声明；下方日期条目保留历史。见[C26待审票](tickets/phase-b-graph-harness/B00C26_B04_FAULT_SOURCE_AND_OWNED_ACTIVATION_HANDOFF.md)。

2026-10-14 C23 接续完成：**C23/C24/C25 completed；B04 经 C23 A6 独立入口复核恢复 ready**。原未消费 normal final、ConsumptionFailure 来源和 child Session 接线阻塞已消除。C23 A1–A6 全部通过；本轮在已批准的共同冻结代码输入上重新执行原验证器与只读来源审计，未重跑全部测试、未重标 Session。B04 仍须完成原 47 construction／144 owned 及剩余产品验收，当前 owned 0/144、131 required/84 mapped/47 remaining，B05 draft、Phase B false。下方原日期记录保留历史。见[C23 独立完成记录](tickets/completions/B00C23_COMPLETION.md)。

2026-10-14 C24 接续完成：**C24/C25 completed；C23 经独立入口复核恢复 ready；B04 保持 blocked**。C24 原10项要求及C23 A1–A5/A4b均已独立核验：共同冻结输入的完整4578（legacy325）、同Session独立owned B02 1410/B03 645、90来源测试、16类双fresh、8个native四消费者188组拒绝、七类停止路由，以及fresh construction15/11/30/28与final具体47/144/15均通过。依据已批准C25 Requirements 12复核原始证据，不重标Session；本轮重新执行原validators和只读来源审计，未重跑effect或修改实现。C23尚须独立A6/B04入口与整票交付；B04owned0/144、131/84/47、2199/324/28/144/15、原owners、B05draft及PhaseBfalse保持。无commit/push。见[独立完成记录](tickets/completions/B00C24_COMPLETION.md)。以下日期条目保留历史。

2026-10-13 C23 执行停止：**C23 blocked；B04 blocked；[C24 待审](tickets/phase-b-graph-harness/B00C24_CONSUMPTION_FAILURE_SOURCE_HANDOFF.md) review**。新 0.11 来源及七类 B04 停止路由双 fresh 局部检查 7/7 通过；Resume-first ConsumptionFailure 的 active-time/失败身份来源另有真实阻塞，C23 整票及最终 Session 验收未完成。131/84/47、2199 cases、B04 owned0/144 保持；新版本尚未完成交付，旧合同不变，无 commit/push。见[实际记录](tickets/completions/B00C23_COMPLETION.md)。以下为保留的历史记录。

2026-10-11最新：**C21 completed；B04 ready**。历史Code科学leaf、Task protected Human reference与显式trace0.9/proof0.6原整票验收通过：固定输入full **4191/4191**（PhaseB3866、legacy325）、source/meta **49/49**、同Session独立owned **B02 1410/B03 645**、fresh原CLI construction **15/11/30/28**及final具体 **47/144/15**。独立B04入口审查后依原授权恢复ready，非自动整票完成；generic unsafe recovery及剩余产品集成/47 construction/144 owned仍待B04执行，owned0/144保持。原0.1–0.8/default/wire/预算/authority、131/84/47、2199/324/28/15与owners保持，B05draft、PhaseBfalse。验收输入与随后文档/YAML交付分别保存，不retag旧Session。见[完成与接续记录](tickets/completions/B00C21_COMPLETION.md)。无commit/push；以下日期条目保留历史。

## 当前合同

`AnalysisState` 是当前公开 graph-state contract。节点只能读取和写入已记录字段。下面的 schema 与当前默认runtime对齐；A02完成execution identity，A03完成bounded artifact-current control fields。B01另行实现显式0.4纯record/replay/projection基础，未向默认0.2 `AnalysisState`添加Pause、Code Agent或budget执行字段。

schema变化必须由独立implementation ticket批准，并同步runtime、tests、artifact contracts和相关Decision Log。A02/A03及B01纯0.4基础、B02独立durable control已落地；默认0.2 AnalysisState和B03/B04产品接线边界保持。

## B01 Execution 0.4 Foundation

显式入口为`control.records.validate_record/parse_record`、`control.execution.replay/parse_ledger/append_record_bytes`。仅接受canonical UTF-8 JSON、精确字段集合和0.4版本；拒绝duplicate key、非有限数值、超过exact JSON integer边界的数值、wrong scalar、未知/缺失字段和非canonical编码。返回的validation snapshot保存immutable bytes；解码结果是detached copy。Builders只构造数据，不能持久化或取得执行权限。

Record union覆盖A02 `run/cycle/attempt/transition/human_request/human_response`及A04/A06 `run_lifecycle/budget`。A02 identity/nesting格式不变；公共envelope使用连续`execution_event_NNNNNN`/`event_index`、`previous_execution_head`、append前`artifact_head/artifact_event_index`及typed `created_at`。Resulting execution head为该完整canonical record的SHA-256，包含previous head但不嵌入自身future digest。Run created使用`initializing`；Run lifecycle edges来自generated protocol。Budget events有独立连续`budget_event_NNNNNN`，但仍在同一execution ledger中。

`ExecutionReplay`可验证未完成的纯publication前缀；这不是可恢复/可运行证明。Stable-root adapter另行要求完整A03反向closure、grant/Transition闭合与exact checkpoint manifest；它不能创建或补齐任何suffix。B02已接入Pause records、coordinator proofs和capability activation；B03工作树已接入Fake Code消费、canonical Code pointer投影与fresh Analysis交接，完整runtime验收仍在进行。单独的合法Run lifecycle edge不能充当durable Pause或启动授权。

Bounded projection只保留当前Run lifecycle、A02当前identity/counters、latest execution/artifact heads、A03 current pointers及convenience paths、policy identity、budget counters/used/remaining、active fingerprint/occurrence、nullable grant和latest decision/stop summary，不复制完整history。`checkpoint_manifest`绑定Run/thread、checkpoint identity/content digest、写入时exact execution/artifact pair及pre-checkpoint state digest；最后把manifest摘要作为`checkpoint_head`附到projection，避免hash自引用。Manifest参数是显式checkpointer evidence，实际checkpoint写入与durable真实性由B02所有者负责；B01不操作checkpoint backend。

兼容边界不变：默认0.2由既有runtime处理，来源验证后仅可replay；0.3不原地resume/migrate，合格来源可replay/fork为0.4 child；0.4恢复仍需exact supported fingerprint及所有durable source proofs。B01不实现这些public入口，不从legacy state推断0.4 history，不迁移历史bytes。

## 当前字段

B02当前实现：显式`control`入口读取0.4 Pause、Human和child lineage records，由唯一coordinator维护operation revision、ownership及capability。Recovery/Human、normal external/timeout与失败收尾、0.2 Replay及合格0.3/0.4 child均通过完整B02验收；下面默认0.2 `AnalysisState`不变。内部错误上下文绑定实际operation/worker/epoch/revision，不新增公开状态。已持久化operation/result/error不可变；query顶层Run状态/closure是该Run实际唯一owner的当前投影，可随另一合法操作关闭Run变化，不能将其误当原operation重写。见[B02完成记录](tickets/completions/B02_COMPLETION.md)。

```python
class AnalysisState(TypedDict):
    run_id: str
    case_id: str
    user_goal: str
    case_config_path: str
    output_dir: str
    current_node: str
    status: str  # running | success | failed | pending | halted
    llm_provider_config_path: str | None
    auto_codex_handoff: bool
    codex_bin: str
    codex_model: str | None
    codex_timeout_seconds: int
    verification_timeout_seconds: int
    force_codex_handoff: bool
    dry_run_codex: bool

    checkpoint_thread_id: str
    checkpoint_backend: str  # memory | sqlite
    checkpoint_db_path: str | None

    parent_run_id: str | None
    cycle_id: str
    cycle_index: int
    parent_cycle_id: str | None
    attempt_id: str | None
    attempt_index: int
    parent_attempt_id: str | None
    attempt_kind: str | None
    attempt_node: str | None
    attempt_trigger: str | None
    attempt_status: str | None  # scheduled | running | succeeded | failed | pending | abandoned
    inbound_transition_id: str | None
    committed_transition_id: str | None
    transition_index: int
    committed_route: str | None
    execution_history_path: str
    artifact_history_path: str
    artifact_index_path: str
    artifact_event_index: int
    current_artifacts: dict[str, dict | None]

    human_request_index: int
    human_response_index: int
    active_human_request_id: str | None
    human_requesting_attempt_id: str | None
    human_request_kind: str | None  # clarification | approval | external_action
    human_request_status: str | None  # open | satisfied
    human_request_authorization_scope: dict | None
    active_human_response_id: str | None
    human_response_status: str | None  # submitted | validated | invalid | consumed
    human_response_decision: str | None
    human_response_authorized_route: str | None
    human_response_authorized_transition_route: str | None
    human_response_authorized_transition_target: str | None
    human_response_validator_attempt_id: str | None
    human_response_consumer_attempt_id: str | None
    human_response_target_attempt_id: str | None

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
    route_decisions: list[dict]
```

## 当前 invariants

- 每次 run 必须提供 `run_id`、`case_id`、`user_goal`、`case_config_path` 和 `output_dir`。
- `llm_provider_config_path` 可选；省略时三个 provider-capable Agent 走 deterministic path。
- local CLI 使用 `sqlite`，unit/smoke tests 使用 `memory`。
- 同一 `case_id` 与 `run_id` 的 `checkpoint_thread_id` 必须稳定。
- Run 初始化时创建 `cycle_0001`；Cycle 与 Attempt 使用显式 Run-local counters 分配 deterministic identity。
- 新 Run 的 ledger/bootstrap 顺序是 Run creation、initial Cycle creation、Planner Attempt `scheduled`、START Transition `committed`；Planner 在 `app.invoke()` 前已有 identity。
- 当前 compiled graph 的每条来源路线先完成 source Attempt，再由 `commit_transition` 在目标节点副作用前创建 target Attempt；conditional edge 只读取 `committed_route`。
- target wrapper 只能领取 committed inbound Transition 已分配给自己的 `scheduled` Attempt；terminal Attempt identity 不得复用，同一 source Attempt 最多一个 committed outbound Transition。
- `parent_run_id`、`parent_cycle_id` 和 `parent_attempt_id` 记录 control lineage。
- `execution_history_path` 指向 run-local append-only `execution_history.jsonl`。
- `artifact_history_path` 指向 append-only `artifact_history.jsonl`；`artifact_index_path` 指向 atomically replaced `artifact_index.json`，`artifact_event_index` 必须等于 registry head。
- `current_artifacts` 的 keys 固定为 `plan`、`code`、`analysis`、`review`、`decision`、`approval`、`terminal`。每个非 null pointer 记录 artifact/Attempt/Cycle identity、members、dependencies、status 和 state paths。
- convenience path fields 必须指向 current canonical Attempt member；slot invalidation 时同步清空。`human_decision_path` 是 approval slot 明确保留的 current external ingress path。
- `current_artifacts`、artifact counter、registry paths 和 convenience paths 是 control plane fields，Agent、provider payload 和 router 不得修改。
- event log 与 route decision 必须携带当时的 Run/Cycle/Attempt identity。
- `attempt_kind` 是 canonical contract，`attempt_node` 是 physical node；当前 `codex_handoff` 必须记录为 `legacy_codex_handoff`，不能记录为 `code_agent`。
- Human Request/Response 使用独立 Run-local counters 和 IDs；有效 response 必须由一个 `human_gate` Attempt 验证。验证会冻结 decision、logical authorized route 和精确 compatibility Transition route/target，commit 必须完全匹配这些字段，且只能消费一次。
- `retry_count` 不得超过 `max_retry`。
- `risk_level` 为 `high` 或 `critical` 时，`human_approval_required` 必须为 true。
- 没有 structured human approval record 时，high/critical outcome 不得写 accepted memory。
- routing 必须使用 structured fields，而不是 Markdown summary。
- `route_decisions` 记录 deterministic route、source node、reason 和所用字段。
- `event_log` 完整保存在 state；LLM-facing context 只使用选定字段和 `event_log_summary`。

## Context 边界

LLM-facing prompt 可以包含：

- selected Run/Cycle/Attempt identifiers 与 status fields；
- 与当前 Gate 操作直接相关的 active Human Request/Response identifiers；
- provider config path metadata，但不能包含 provider secrets；
- relevant artifact paths；
- method、run、review、decision 和 event-log 的 bounded summaries。

LLM-facing prompt 不得包含：

- full raw numeric data；
- secrets；
- unbounded long logs；
- 作为 routing 唯一依据的 truncated free-form text。

## 当前 runtime 行为

graph 默认使用 deterministic Agent path，并在重要节点完成和 route decision 后写 `graph_state.json`；完整 state 同时保存在 LangGraph checkpoint。`llm_provider_config_path` 可以启用 provider-backed Method Planner、Scientific Reviewer 和 Decision Coordinator，但 provider output 必须先通过结构验证。

所有 compiled graph nodes 通过 control-plane wrapper 执行。来源 transition 或 bootstrap 预先写 target Attempt `scheduled`；target wrapper 验证 committed inbound Transition，写 `started`，执行 physical node，再写 terminal `finished`。node exception 写 failed Attempt 后原样重新抛出，且不提交正常 outbound Transition。route selector 只返回结构化选择和显式 state updates；Transition commit 才能更新 control state、分配下一个 Attempt 并记录 route。完整 lifecycle 写入 `execution_history.jsonl`，但 Agent-facing context 只包含 current identity 和既有 bounded summaries。

high/critical outcome 进入 Human Approval Gate。Coordinator commit 同时创建独立 Human Request 和预分配 Gate Attempt；gate 写 identity-bound `approval_packet/`。外部 response 获得独立 identity，只能由新 Gate Attempt 验证并由已授权 compatibility transition 消费一次；没有有效决定时 request 保持 open，state 保持 `pending`。

Local CLI 使用 `SqliteSaver`。`--output-dir` 是 output root；解析后的 run directory 为 `<output_root>/<case_id>/<run_id>/`，并写入 `state["output_dir"]`。省略 `--run-id` 时，在 state 初始化前生成 timestamp run id。checkpoint database 位于：

```text
<output_root>/<case_id>/<run_id>/checkpoints/graph_checkpoints.sqlite
```

Unit/smoke tests 使用 `MemorySaver`。两种 backend 使用相同的 `checkpoint_thread_id` 格式：

```text
<case_id>:<run_id>
```

## A02 当前落地的 State Boundary

[A02](tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md) 的当前实现采用 Run / Cycle / Attempt 三层 identity。Run 继续使用现有 `run_id` 并拥有 canonical output root 与稳定 checkpoint thread；Cycle 表示 initial/replan 创建的方法合同 epoch；Attempt 表示一次产生持久状态、artifact 或 route decision 的 node invocation。每个 Run 另有 deterministic Transition、Human Request 和 Human Response identities。

State 保存 current Cycle/Attempt pointers、Run-local allocation counters、parent lineage、current artifact pointers、execution ledger path 和 Run-owned checkpoint metadata。完整 Attempt history append-only 保存，不能作为不断增长的 state-to-prompt context。

Attempt 由 graph control plane 在目标节点副作用之前分配。canonical Attempt kinds 当前固定为 `method_planner`、`legacy_codex_handoff`、`code_agent`、`analysis_engineer`、`scientific_reviewer`、`decision_coordinator`、`human_gate` 和 `memory_report`；其中 `code_agent` 只为 A05/Phase B 预留，当前产品 graph 没有该节点。legacy external Codex runner 仍保留原有重新进入主图的行为；重新初始化未完成 Run 时会从已有 ledger 恢复 counters，避免复用 identity。它不是未来 graph-managed Code Agent，也不满足A04已确认的通用checkpoint resume合同。

当前 product routes 已使用 transition-time allocation 与 target-layer artifact invalidation。re-review、analysis rerun、code fix 和 replan 只在最小 deterministic StateGraph harness 中验证 identity/invalidation protocol；它们尚未因此成为当前产品路线。A01 的完整线路改造与 forbidden-route coverage 仍由 A07/Phase B 承接。

## A04 已确认的目标 State Boundary（尚未实现）

[A04](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)冻结execution schema `0.3`的Pause/Run语义，供Phase B schema `0.4`实现复用。这里的版本是目标合同版本，不改变上方当前`AnalysisState`或runtime schema `0.2`。

权威状态与投影严格分离：

- append-only `run_lifecycle`记录是Run状态authority，`run_status = initializing | running | paused | completed | failed | halted`只是受限projection；`completed | failed | halted`均terminal且不可逆；
- 现有`status`保留为domain/workflow compatibility字段；正常`memory_report -> END`即使领域状态为`pending`，control `run_status`也必须为`completed`；
- Pause ledger status固定为`prepared | opened | claimed | consumed | cancelled | aborted | interrupted | quarantined`，event固定为相应`pause_*`类型；只有latest exact `opened`且unclaimed、public paused checkpoint完整的Pause可resume；
- bounded state未来只保存`run_status`、pause counter、nullable pending/active Pause identity/reason/status/requesting-target scope，以及nullable active ControlOperation ID/status/phase/revision/epoch；这些字段不能替代coordinator、execution ledger或artifact heads；
- ControlOperation的`operation_status`、Run terminal closure、Run lifecycle、Pause lifecycle和domain `status`互相正交；`operation_status: failed`不能推导`run_status: failed`。

`human_input`与不继续existing target的`recovery_decision`在opened时使用explicit null target；Human validator只在成功claim后、任何target副作用前分配一次。`external_result`必须绑定already-scheduled且未started的exact target、pre-existing reservation和ExternalOperation core digest。Resume继续分支固定经过claim、reason-specific pre-start、`pause_consumed`、`paused -> running` lifecycle及running checkpoint，随后才允许target start。`recovery_decision`只接受`continue_existing_target | abandon_and_halt`；null target只能halt，Code Agent/legacy handoff target不能continue，且该输入不能伪装成replay/fork。`abandon_and_halt`分支原子取得Pause和Run terminal ownership，不进入running。

无效Human Response不会重新打开或复用旧Pause：旧Pause保持consumed，validator Attempt先结束。A06容量决策为`allow`时，从新的running安全边界按`pause_prepared -> prepared checkpoint -> running-to-paused lifecycle -> pause_opened -> public paused checkpoint`发布新identity；决策为`halt`时不创建新Pause，而由`close_run`从running发布terminal closure。

每个Pause还冻结runtime compatibility fingerprint，至少覆盖control/app build、graph topology、state/artifact schema、LangGraph/checkpointer/serializer实现及版本。Schema `0.2`不resume/fork；显式支持`0.3`的原runtime可恢复自己创建的exact Pause，但Phase B `0.4`只原地resume exact supported `0.4`，对validated `0.3` source只允许replay/fork为新child。缺失或mismatch一律fail closed，不做state reinterpretation或原地迁移。

## A05 已确认的 Code Agent 目标 State Boundary（尚未实现）

[A05](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)为Phase B canonical Code Agent冻结以下bounded nullable projection：

```text
code_agent_task_path
code_agent_result_path
code_change_manifest_path
code_verification_results_path
code_agent_status
code_agent_usable
```

这些字段只在A03 `code` bundle完成注册后设置，并必须与current pointer、canonical member paths及validated `CodeAgentResult` exact-match。`code_agent_status`只允许`success | no_change | failed | needs_input | needs_human | budget_exhausted | policy_blocked`，`code_agent_usable`只有满足non-empty scoped change、全部required trusted verification及其他route guards的`success`才可为true。Code invalidation必须与A03 current pointer一起原子清空全部canonical字段。

Legacy `code_change_summary_path`和`tests_status_path`保持独立。Future code-slot state path对`legacy_codex_handoff`与`code_agent`使用同一个完整nullable key集合：legacy producer只填legacy paths，canonical producer只填上述新paths和scalars，另一组必须显式为null；没有current code pointer时两组都为空。两类producer不能从字段组合或artifact内容互相解释。

Mutable workspace path、patch bytes、tool transcript、完整verification logs、backend/provider session和ExternalOperation authority不得进入bounded graph state。State/checkpoint至多保存受限identity/reference projection；`producer_operation_id`、phase/revision/lease、Pause binding、workspace lifecycle、receipt/seal/delivery与final evidence继续由project-owned coordinator及immutable control/audit records拥有，不能由Agent、resume payload或model output改写。

上述字段属于Phase B execution schema `0.4`实现目标，不是当前schema `0.2`字段。A05没有修改`AnalysisState`、graph、checkpoint backend或legacy re-entry行为。

## A06 已确认的 Budget 目标 State Boundary（B01纯投影已实现，产品接入待实现）

[A06](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)把budget authority放在immutable policy与append-only execution ledger，而不是graph state。Phase B execution schema `0.4`在现有`execution_history.jsonl`增加`record_type: budget`，Run-local `budget_event_id/index`连续且唯一；A06原七类event为`policy_initialized`、`resource_reserved`、`resource_settled`、`failure_observed`、`grant_issued`、`grant_consumed`和`decision_recorded`。B00C09仅为B03 canonical Code path追加版本化`active_interval_reserved`/`active_interval_settled`，旧七类payload不重解释。Cycle、Attempt、Transition与automatic-route用量继续从其A02权威记录重放，不建立第二份mutable counter history。

活动区间reservation在未结算前按maximum进入bounded `active_seconds_per_run`，`host_setup`不扣Attempt；`attempt_active`同时扣Run与所属Code Attempt。结算后仅可信同epoch actual可替代maximum，其他情形保留maximum。已证明嵌套在同一Attempt区间内的verification resource仅保留command计数及实测audit秒数，不能重复扣active。完整字段、邻接顺序和旧B02 synthetic兼容见[B00C09合同](tickets/corrections/B00C09_ACTIVE_TIME_LEDGER_CONTRACT.md)。默认schema `0.2` AnalysisState字段没有变化。

Bounded state只保存可从validated policy与ledger确定性派生的projection，至少包括：

- policy version、profile ID、reference与digest；
- latest budget event/grant counters；
- 每个hard dimension及automatic route scope的used/remaining；
- active failure fingerprint、Run-local occurrence与causal evidence digests；
- nullable active grant identity、scope与consumption state；
- latest `BudgetDecision` summary、exhausted dimensions与typed stop reason。

初始化、恢复、读取、route admission与artifact registration前必须重放authority，并要求projection exact-equal。完整reservation、settlement、fingerprint和grant history不能复制进state或Agent prompt；缺失或篡改已populated projection不能由initialize静默修复。Resource reservation在side effect前写入，crash后未结算项按maximum charge；Code Agent pre-start Backend interval可计入target Attempt与Run active dimensions，但不把scheduled Attempt提前改为`started`。

每个Run还绑定immutable `budget_policy.json`的version/profile/reference/digest及Pause deadline派生输入。Resume必须exact-match同一schema `0.4` policy/runtime；Replay/Fork创建新child并从0计数，不继承reservation、failure occurrence、grant、deadline、counter、current pointer、Human authorization或accepted state。完整durable流程仍是目标合同；B01的纯policy/record/replay/projection已实现，但不改变当前`AnalysisState.status`、`retry_count/max_retry`、graph topology或schema `0.2` ledger。

## 第二阶段待实现 schema 议题

以下内容仍未成为当前 `AnalysisState` 合同：

- A04已确认的`run_status`、Pause、ControlOperation和compatibility projections；
- A05已确认的canonical Code Agent bounded fields及其与ExternalOperation、workspace和code bundle的交叉验证；
- A06已确认的budget policy binding、budget ledger events、trusted usage与bounded projection；
- 正式 parallel reducer、per-branch namespace 或 merge semantics。

在后续implementation tickets完成前，不能假设这些字段已经接入默认`AnalysisState`、public operations或产品图；B01独立纯0.4基础类型不构成该接入。

## Related Documents

- [Architecture](ARCHITECTURE.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Phase A: Control Contracts](tickets/phase-a-control-contracts/OVERVIEW.md)

## B02C01：Legacy source fingerprint（2026-09-18）

已批准的B02C01为既有`SourceSnapshotProof/replay_root.runtime_fingerprint`补充唯一source-only值`{"availability":"not_recorded","reason":"legacy_schema_0_2"}`。它仅适用于真实schema `0.2`创建格式、root inputs完整验证的replay；与source identity/schema/inputs共同进入lineage digest，child的`source_runtime_fingerprint`必须与proof相等。`0.3/0.4`仍要求真实完整source fingerprint且execution schema匹配；target始终为当前`0.4`完整fingerprint。Pause/resume不接受该值，旧schema不能原地恢复，source build不必等于新child build。

实现使用独立source validator，不改Pause fingerprint规则、Phase A协议外层字段或generated graph。运行验证及当前完成状态见[B02C01执行记录](tickets/completions/B02C01_COMPLETION.md)。

2026-09-18 B02补充实现：normal external的claim/settlement/running checkpoint先于Code消费权限；消费完成/资源释放先于final checkpoint。消费失败沿原resume terminal owner收尾。Analysis preparation冲突在控制前缀可验证时关闭failed，否则unavailable，保留原scheduled target。0.3 historical source proof保存原fingerprint和真实revision/head，不赋予来源resume权限。这些control行为仍待B02完整矩阵验收；historical trace前置缺口见[B00C03 review](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)。

## B00C07 approved implementation handoff

2026-09-24：B00C07已按用户同意补强，ready冻结于`7ab58ce`并完成文档交接。B03恢复ready；四个canonical paths来源修复与B02 needs_input fixture窄替换获得明确授权，尚未实现。先推进B03预算事务/失败恢复，再完成canonical实现与28/645验收；当前mapped56/remaining75、Phase B未完成。

详见[B00C07冻结补充票](tickets/phase-b-graph-harness/B00C07_A05_STATE_PROJECTION_GOLDEN_HANDOFF.md)。旧0.2/0.3格式保持原字节，新0.4使用完整nullable path集合与独立status/usable；trace0.5仅修复受来源约束的四个canonical paths，旧trace版本保持。B02材料适配保留原控制断言并使用相同canonical validator；不得将文档交接当作已实现能力。

## B00C08 approved handoff

2026-09-24：B00C08在13f3b74冻结并完成治理交接；B03恢复ready。Normal/timeout完整来源、source trace0.5、独立Analysis success前置及其golden审计范围已批准，尚待B03实现。预算事务与canonical交付未完成，mapped56/remaining75、Phase B未完成。

[B00C08](tickets/phase-b-graph-harness/B00C08_B02_CANONICAL_EVIDENCE_TRACE_HANDOFF.md)明确替代C07受影响source证据不得升级0.5的限制，补齐upstream与safe-timeout材料。迁移source轨迹另存0.5 expected；无成员摘要的phase-only证据仍为0.1。Analysis前置使用独立success/usable bundle，normal needs_input不计canonical Analysis成功。以上为待实施边界。


2026-09-29 B03完成：canonical Fake Backend、Host stop/unavailable、trusted Code消费/资源结算/Bundle、按producer/version的0.4状态投影和fresh Analysis交接通过验收。最终construction **15/11/30/28**，同一fresh Session的B03 **645/645**、B02 **1410/1410**，全仓 **3514 passed**（Phase B **3189 passed**）。Mapped **84/131、remaining47**；全局 `phase_b_complete=false`，B04/B05仍draft，默认产品runtime仍schema0.2。协议/catalog、case/owner/exit门槛与legacy合同保持。详见[B03完成记录](tickets/completions/B03_COMPLETION.md)；较早in_progress及219/379等条目保留为历史事实。未提交或推送。


## 2026-10-12 — C22普通publication prefix状态证据

显式trace `0.10` / proof `0.7` 的执行候选见[C22独立来源合同](tickets/corrections/B00C22_ORDINARY_PUBLICATION_PREFIX_SOURCE_CONTRACT.md)。实际settled、domain registered、Invocation finished和Run closure分别核验；原frozen completion、真实published prefix及实际checkpoint不得混淆。被动采集快照不是runtime journal，不赋予effect或收尾权限；原authority有效时只用原端口补exact suffix，无法安全收尾仍保持原recovery分类。旧0.1–0.9/default/wire/hash和预算不变。

新来源专项61/61通过，完整当前native Session、独立B02 1410/B03 645、fresh construction15/11/30/28及final具体47/144/15仍待验收；B04 blocked/owned0-of-144、B05 draft、Phase B false。旧expected仅允许实际runtime fingerprint及证明完整的派生引用离线同步，不改变outcome、owners或exclusion。实际结果持续记录在[C22 completion](tickets/completions/B00C22_COMPLETION.md)，验证输入和后续文档交付分开保存。


2026-10-13 C22完成补记：显式0.10/0.7来源合同现已完整验收通过，full4273/legacy325、同Session owned1410/645、fresh15/11/30/28及final具体47/144/15；settled/registered/finished/closure及原suffix authority边界保持。B04仅经独立入口恢复ready，原47/144及产品集成仍待完成，B05draft/PhaseBfalse。见[C22完成记录](tickets/completions/B00C22_COMPLETION.md)；上方候选及旧日期记录保留历史。

## C24 显式来源补充实施中（2026-10-13）

仅 trace0.11/proof0.8 的 harness provenance 候选新增原 ConsumptionFailure 和未接纳 Backend 原文交接；proof 顶层/声明字段、production schema0.4、Run 状态与 authority 不变。原 external safe_stop 不证明 Resume consumer 安全。完整验收待执行，C23/B04 blocked。见[来源合同](tickets/corrections/B00C24_CONSUMPTION_FAILURE_SOURCE_CONTRACT.md)。

## 2026-10-13 C24 候选验收状态

C24来源候选的90项原生专项、16类双fresh和8个native四消费者已验证；完整集合发现既存B04 spawn child Session接线问题，C24/C23/B04保持blocked，C25仅review。没有production/schema/authority变更或整票交付声明；旧版本/default和原验收集合保持。当前完整验收及同Session独立owned未完成，不能以早前unit-only工厂通过替代。见[C24实际记录](tickets/completions/B00C24_COMPLETION.md)和[C25待审](tickets/phase-b-graph-harness/B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md)。

## 2026-10-14 C24 来源状态验收完成

显式trace0.11/proof0.8的ConsumptionFailure来源已完成独立验收。external normal/safe_stop、Resume consumer stop和Run append authority分别验证；真实unavailable分支保留running/recovery_required及无结算/终态后缀，不能从external停止推导consumer成功。原production schema0.4、proof声明字段、预算与authority均未改。C23仅ready，B04blocked；见[C24完成记录](tickets/completions/B00C24_COMPLETION.md)。

## 2026-10-14 C23 未消费 final 来源交付

C23完成显式trace0.11/proof0.8的独立验收；normal_final_unconsumed、closed_without_consumption、unavailable_without_consumption继续分别由实际持久状态证明。external normal owner、安全停止、Resume consumer和Run authority不能相互替代，真实unavailable保持原状态。production schema0.4和状态机未改。B04经独立入口恢复ready，剩余47/144由B04完成；见[C23来源合同](tickets/corrections/B00C23_UNCONSUMED_CODE_FINAL_SOURCE_CONTRACT.md)。
