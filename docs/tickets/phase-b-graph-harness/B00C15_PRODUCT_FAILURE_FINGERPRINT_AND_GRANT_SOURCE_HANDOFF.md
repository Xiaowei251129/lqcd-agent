---
ticket_id: B00C15
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C10, B00C11, B00C12, B00C13, B00C14, B04]
---

# B00C15：产品因果 fingerprint、Grant 来源与前置 meta 交接

## Goal

解除 B04 在真实普通领域失败中复现的来源阻塞：A06 合法的、排除执行身份的 Plan 因果摘要不能由当前 trace 0.7 表达。以显式 trace **0.8 / proof 0.5** 对实际 Host 因果投影、failure occurrence、validated Human BudgetGrant 和原 Transition 单次消费建立闭合来源，交接受影响的前置 Human meta，保留旧版本的解释、拒绝行为与 sealed evidence。

本票初始 `review`，创建不代表批准或实施。B04 是纠偏目标，`depends_on: B04` 不要求其先 completed；其余依赖必须 completed。B04 保持 blocked、owned 0/144。执行本票并完成原全部验收和独立阻塞复核后，才依原授权恢复 B04 ready。

2026-10-07按用户指令修订：本票明确冻结下面的新 proof 字段、因果投影及逐 occurrence owner 规则、Coordinator 阶段的 Grant 发行/权限来源和预算 publication 故障验收。修订不是批准，仍为 `review`；不实施 0.8，不新增 completion，不改变 B04 blocked。

## Why

2026-10-07 B04 已局部修复 Planner 早期 Coordinator 依赖和 ordinary exception/overrun 收尾，保留底层资源 primitive 及其 unsettled fixture。接续 fingerprint 时，在完整独立候选副本中，仅给原 `ProductNode` 增加 Host 派生与原 fenced `append_budget(failure_observed)`；没有替换 compiled graph、selector、operation、Agent effect 或 ledger。

两个 fresh 根分别由真实 Planner 和失败 Analysis 进入 Coordinator/Human Pause；原 replay 和 `validate_fingerprint` 接受。Plan 的唯一领域内容是实际 `code_needed=false`，排除原 Host identity 后的摘要同为 `390961ce00459cd2f24d43bc1918d5d10736a9221d5a83f07ae0e6ab03ae3624`，完整 fingerprint 同为 `ddd6afe91ce0e5136c613ec18744f7cd5925c1225f0c737f6da92f0d1da6deec`。不同真实 Run 的原 Plan member 摘要分别为 `d95745eef3dd99343adb977dbd0a79d488a4347ca740e687d7358a6bebaca028` 和 `47bfaa6351e50f998cd654e3dda0da966555947b7f54a2c67d47253f89fc622f`。实际 Human Request 已绑定 occurrence 1，effect 各仅 Planner/Analysis 一次，重读和 graph 重入没有新 effect。

原 `OrdinaryProjection.failure_and_grant_sources` 仅匹配原 member SHA 或 Code result checksum；两份完整 raw 均被原 0.7 normalizer 拒绝 `invalid_evidence:ordinary_trace:failure_member_source`。用原包含 Run/Attempt 的 member SHA 替换因果摘要会违反 A06；把摘要留 null、过滤 failure_observed 或排除 fingerprint 也不合法。新增真实 budget event 和 Human failure binding 还超出冻结 B04 允许的前置 expected runtime-fingerprint-only 同步，不能用覆盖 C13 固定 expected 来消除。

证据在 `/private/tmp/lqcd-agent-b04-execution-20261007-e90cbzz9/`：`fingerprint-stop-report.json`、两份 `fingerprint-stop-*-raw.json`/`facts.json`、`fingerprint-candidate/`、`fingerprint-candidate-helper.txt` 和原端口 driver。候选只在独立临时副本运行，当前仓库未纳入 fingerprint 候选。本材料是定位证据，不能算本票完成或 B04 owned runtime；执行时必须重新 fresh 构造。

另在当前保留源码的原 `invocation.attempt_finished` after 故障中，真实 completion 已冻结，但 graph 重入因 artifact index cross-head mismatch 拒绝，Run 保持 running、effect 1→1、没有假 closure；这是 B04 原范围的 publication 接续局部问题，恢复后仍须修复，不以本票声称已解决。原 budget.resource_settled after 故障则已可重入安全 failed，唯一 settlement/effect 保持。证据同执行根 `publication-fault-summary.json`。

## Read First

- [AGENTS](../../../AGENTS.md)、[Docs](../../README.md)、[工作流](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)、[验证指南](../../VERIFICATION_GUIDE.md)；
- [冻结 B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[completion](../completions/B04_COMPLETION.md)、[maintenance](../corrections/B04_MAINTENANCE.md)；
- [A01](../phase-a-control-contracts/A01_TRANSITION_MATRIX.md)、[A03](../phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md)、[A04](../phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)、[A06](../phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)、[A07](../phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)、Protocol/catalog 和现行独立 case0.4；
- [C10](B00C10_ORDINARY_RESOURCE_TRACE_HANDOFF.md)、[C11](B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_HANDOFF.md)、[C12](B00C12_HUMAN_REQUEST_PACKET_TRACE_HANDOFF.md)、[C13](B00C13_HUMAN_CONTINUATION_SOURCE_AND_PREFIX_HANDOFF.md)、[C14](B00C14_HOST_IDENTITY_REJECTION_ASSERTION_HANDOFF.md)及独立来源合同/completion；
- `src/lqcd_agent/control/{budget,capabilities,execution,operations,pause}.py`、`graph/{nodes,routing,state,analysis_graph}.py`、`artifacts/registry.py` 和 B03 semantic context/preparation；
- `tests/phase_b/harness/{trace,ordinary_trace,ordinary_maximum_trace,a05_trace,trace_proof,pytest_evidence,matrix,exit_checks,session}.py`、`helpers/{ordinary_sources,ordinary_maximum,ordinary_human,control_traces,trace_sources}.py` 和 C11/C12/C13/C14 专项。

## Scope

- 新显式版本的 dispatch、projector 和被动 collector，复用既有源对象校验，不重新解释 0.1–0.7；
- Host 因果投影的闭合证明：原注册 owner/member、真实 bytes、实际读取输入、允许的字段投影、相关 policy/config/base 与适用 Code/Analysis semantic context；
- failure_observed 的真实 occurrence、Human Request 的 exact failure binding、validated/consumed snapshot、grant issuance 与原 Transition 单次消费来源；
- 专用 B00 meta tests/fixtures/expected 和必要四条消费路径接线；显式交接受影响的 C11/C12/C13 当前产品 Human fixture/meta，而不倒改历史 sealed evidence；
- 为来源验收所需的最小产品 Host fingerprint/Grant 发行集成，仍复用原 BudgetPolicy/FailureFingerprint/BudgetGrant 0.1、capability fence、原 publication 和原 Transition；包含本票预算事件的 original-owner suffix/recovery 证明，不要求完成 B04 的通用 graph publication 接续修复。实际生产修改追加 B04 maintenance。

## Non-goals

- 不改变 A01 17 edges、风险 floor、科学接受权限、A03 seven slots、A04/A05 authority/stop、A06 budgets/absolute ceilings/reserve 或 runtime wire schema；
- 不把本票 meta 计作 B04 owned，不完成 Code parent、四层 fallback、fresh Analysis 和 B04 47/144 整票；
- 不实现 real provider/backend、并行、迁移、依赖升级、B05 exit adapter，不 commit/push。

## Allowed Files

- 新 `tests/phase_b/harness/product_failure_trace.py`；`harness/{trace,ordinary_trace,ordinary_maximum_trace,a05_trace,pytest_evidence,matrix,exit_checks}.py` 仅新版本 dispatch、封闭来源和必要消费接线，旧 dispatch/规则不变；
- `helpers/{ordinary_sources,ordinary_maximum,ordinary_human,control_traces,trace_sources}.py` 和新 `helpers/product_failure_sources.py`：仅被动抓取原 Host 投影与已验证原对象，不构造 effect/返回/停止/批准事实；
- 新 `test_b00c15_product_failure_sources.py`、`test_b00c15_trace_consumers.py`、`test_b00c15_budget_publication.py`、`fixtures/b00c15/`、`expected_traces/b00c15/`；
- `test_b00c11_human_snapshot.py`、`test_b00c11_trace_consumers.py`、`test_b00c12_human_request_packet.py`、`test_b00c12_trace_consumers.py`、`test_b00c13_human_continuation.py`、`test_b00c13_trace_consumers.py` 和对应 Human 专用 fixture：仅显式新版本交接实际新增 fingerprint/grant 前缀与负向断言，保留 observe IDs、owner/outcome 和全部原实质不变量；原 0.7 固定 expected 保留，用新路径固定新版本 expected，不按 actual 动态生成；
- `acceptance_matrix.json`：仅原 B00 `A07-META-006`/`A07-META-015` 新来源 meta 与上述当前入口交接，不改变 scenario owner/case/required/exit；
- 其他 expected/关联 fixture 只允许审定实际 runtime fingerprint 及可证明派生 head/reference；保存 before/after raw、逐项差异，双 fresh 验证，不能借此改变其他语义；
- `src/lqcd_agent/graph/{nodes,routing,state,analysis_graph}.py` 和已有 `control/{budget,capabilities,operations,pause}.py`：仅来源验收必需的最小 Host fingerprint/validated Grant 发行、exact failure snapshot/response scope 与原 publication/单次消费集成。资源 primitive、budget 算法、operations/protocol/schema/owner 不变；
- 本票 YAML lifecycle、新 `corrections/B00C15_PRODUCT_FAILURE_SOURCE_CONTRACT.md`、`completions/B00C15_COMPLETION.md`（仅执行后）；B04 maintenance/completion 只追加；相关 README、Phase B Overview、Current State、`ARCHITECTURE`/`VERIFICATION_GUIDE`/`EVALS_AND_OBSERVABILITY`/`DECISION_LOG` 仅实际交接文档。

## Do Not Touch

- Phase A、B00 schemas/catalog/cases/runtime obligations、131 requirements、2199 cases/owners、legacy tests、冻结正文、旧 sealed evidence 和已完成历史；
- `session.py`、`failpoints.py` 的选择/Session/回执/分类/判定、B02/B03 owned fixture/expected 的语义、exclusion allowlist；
- 底层 `run_resource` 的 unsettled 语义、现有 maximum receipt/停止校验、预算 profile/算法/limits/reserve、Provider/Fake Backend/A05 schemas；
- configs/dependencies/Phase A/legacy runtime/raw/outputs/accepted artifacts/secrets、外部系统和 B05 ticket。

## Requirements

1. **显式闭合版本。** 只由 0.8/proof0.5 选择下列新分支；旧版本保留原接受/拒绝行为，0.7 必须按其闭合 proof 原规则拒绝本次因果来源反例。复用完整 registration/capability/producer/ledger/Host bytes 校验，不接受任意自报 digest、未列明 profile、隐藏字段或宽松摘要别名。
2. **真实因果投影。** 按下列固定 profile、字段路径与独立重算规则绑定每个实际 read 的 canonical member、独立注册 owner、source digest 和 Host 原始投影。来源以 failure record 为单位，不能以相同 fingerprint/causal SHA 合并不同 occurrence 的 owner。科学配置/内容默认保留；仅 `code_needed` 的反例不是通用白名单。
3. **适用上下文。** ordinary Plan/Analysis/Review、Code task、verified change/effective tree、fresh Analysis spec 按适用字段证明。FailureFingerprint 的两个因果 context 使用原 A06 semantic context primitive 和本票已绑定的科学材料；原 B03 task/preparation/aggregate 的 wire context、checksum 与校验算法保持，不把两类摘要互相别名或重解释。None 仅在实际不适用时允许，不能隐藏已读取材料。
4. **重复与无失败。** 只对实际引起 route 的 typed failure/diagnosis 记录 failure_observed；连续 occurrence 来自原 replay。首次/第二次 exact 的控制规则依 A06，Human 重入同一失败 snapshot 不能重复观察，实际新 Work 失败必须增加 occurrence。正常成功不能沿用旧失败来伪造重复升级；仅 identity/summary/path 变化不能建立新 context，真实材料变化必须建立新 context。
5. **真实 Grant。** 严格按下列 Coordinator 阶段、authenticated actor 来源及完整 preflight 发行；绑定原 validated/consumed `approve_budget_window` snapshot、Request/Pause、failure occurrence、最终 Work target/Transition 和 policy。非 budget action、free text、旧/foreign snapshot、无适用 failure、duplicate issuance/consumption、失配 target 或突破 ceilings/reserve 均拒绝。发行前必须证明完整目标可 admission；发行后真实故障保留不可退款的 journal/grant，并按原 prefix/recovery 规则处理，不能重发、改目标或让未消费 grant 被无关 terminal route 使用。
6. **生产与 fixture 交接。** 最小 Host 集成经原端口和 fence 实跑。当前 C13 批准/拒绝及 Human publication-pending/started-recovery 的前置 meta 改为专门 0.8 来源与固定新 expected；原 0.7 raw/expected 归档字节保持，legacy 版本断言显式保留。业务终态、单次 effect、独立 owner、packet 不变、合法 suffix/recovery 分类不能为满足新预算事件而改变。不得通过 fake failure event、state/selector/ledger patch、feature flag 绕过或过滤运行失败完成交接。
7. **接续职责。** 完成本票只解除已验证来源/前置 meta 阻塞；B04 继续负责 ordinary finished/publication 前缀接续、Code parent、四层 fallback、fresh Analysis、全 route/forbidden/terminal/recovery/fencing 和原 47/144。实际新增预算前缀与 source recipe 的授权以本票独立合同为准，不回写冻结 B04 正文。

### 0.8 / proof 0.5 的闭合声明

- Proof0.5 顶层字段 exact 为 `schema_version,binding,objects,output_roots,typed_sources,material_sources,workspace_roots,ordinary_calls,ordinary_members,ordinary_maximum_settlements,product_failure_sources,product_grant_sources`。前十项保留原0.4的字段、bytes、member/call/maximum/Human/authority校验；failure/Grant的因果引用仅在0.8分支按本票替换旧raw-member匹配，不先执行旧failure_member_source再放行，也不修改旧分支。原0.1 budget/fingerprint payload验证仍完整执行。仅新增后两个数组，不新增runtime ledger字段、event、slot、status或authority。
- 每项 `product_failure_sources` 字段 exact 为 `schema_version,failure_head,capability_id,producer_operation_id,issuer,source_attempt_id,source_registration_head,diagnostic_binding,derivation`，version 为 0.1。`failure_head` 是实际已发布 `failure_observed` 的 raw record digest；capability/producer 是实际发行此 event 的当前 Coordinator Invocation 与原 producing operation，不冒用失败 Work 的 capability。`source_attempt_id`/registration 则指向实际导致本次诊断的 Work；两种 owner 分别校验。
- `diagnostic_binding` 字段 exact 为 `kind,registration_head,member,sha256`；kind 仅 `ordinary_diagnostic|canonical_code_result`，分别绑定原 registered Work diagnostic member 或经原 A05 Host 验证的 canonical Code result。注册须在 event 的原 artifact head/revision 前已存在，并与实际 parent/scoped input 来源一致，不能从最新 current 或全 history 猜一个相同内容的 owner。
- `derivation` 使用原 closed source envelope `{schema_version,profile,sha256,content}`，version 0.1、profile 仅 `product_failure_derivation`。content exact 为 `schema_version,layer,failure_class,code,diagnostics,context_bindings`；分类按下面规则重算，`diagnostics` 沿用 A06 stable schema，只有实际 typed exit/signal/failing IDs/structured validator errors可填，无事实为原nullable/空列表，不从自由文本猜。`context_bindings` 的 keys exact 等于现有 A06 `CAUSE_FIELDS` 十二项；逐项独立重算后必须与实际 event 的 fingerprint context、causal_context_digest、fingerprint_digest exact。
- ordinary 的 failure_class/code 分别为原 diagnostic.status/category；layer按category的 `security|policy|data|scientific|provider|verification|tool` 完整名称或其 `.`/`_` 前缀映射，`analysis_execution` 为 tool，其余为 control。canonical Code 的 failure_class/code 分别取原 result.failure_class/status；layer对 `scope_violation|policy_violation|verification_failed|tool_error|timeout|external_interruption` 分别为 `security|policy|verification|tool|control|control`，其余为code。这里只固定因果分类，不改risk/route权限；没有实际 ordinary failure/diagnosis 的正常成功、纯terminal budget stop及无法产生domain来源的Host/control failure不伪造该event。
- 每项 `product_grant_sources` 字段 exact 为 `schema_version,grant_head,capability_id,producer_operation_id,issuer,human_request_head,response_submitted_head,response_validated_head,response_consumed_head,snapshot_registration_head,pause_consumed_head,resume_operation_id,failure_head,admission`，version 0.1。所有 head 均绑定同一真实 Run 的原 records；resume producer 和 issuer producer 独立证明。`failure_head` 精确指向该 Request 授权的 occurrence，不能只找最后一个相同 fingerprint SHA。
- 两种声明的 `issuer` 字段 exact 为 `worker_id,invocation_epoch,producer_epoch,producer_revision`；均取原调用/fenced journal的实际值，交叉校验原capability授权、started/completion intent及coordinator producer phase/epoch历史。不是从当前latest任取epoch，错误/缺失/foreign issuer必须拒绝；新来源声明本身不授予writer或takeover权限。
- `admission` 为 version0.1、profile `product_grant_admission` 的 closed source envelope；content exact 为 `schema_version,coordinator_attempt_id,pre_execution_head,pre_artifact_head,pre_checkpoint_head,grant_payload,budget_decision`。payload/decision 沿原 0.1 schema；这是实际 Host 在原 fence 下作出的、尚未 append Grant 的 preflight 事实，被动捕获其原 bytes/参数，不能由 collector 事后造出一个 allow。
- 两数组分别与当前真实 published ledger 的 `failure_observed`/`grant_issued` records set-equal，按该 Run 的 event_index 排序；缺失、重复、orphan、foreign owner、错误次序及未知字段/profile 均拒绝。未发布 intent 只保留原 journal 来源，不声明成 public event；已发布但未消费的合法 Grant 前缀仍必须声明，不能过滤。`grant_consumed` 复用原 ledger/snapshot/Transition 绑定；只有实际存在消费 record 才证明 consumed，不能要求中断前缀补造未来 target/Transition。
- 同一因果 digest 在不同 Attempt/Cycle/occurrence 中可重复；绑定表 key 为 `(case_id,run_id,failure_head)` 或 `(case_id,run_id,grant_head)`，每项保留各自 raw registration、capability 与 producer。稳定科学投影可以内容共享，关联到原 owner 的证明不能被 SHA-keyed map 覆盖。
- 0.7 兼容测试使用原 0.7/proof0.4 字段集合与相同实际 public records/members，去掉仅 0.8 的声明，而不改 FP/ledger/owner bytes；必须复现因果来源拒绝，不能以 proof schema mismatch 冒充。旧 raw/expected 用原 binding 只做旧格式兼容复核，不 retag 为当前 Session 或当前 runtime evidence。

### 固定投影 profile 与材料边界

- `context_bindings` 每个 value 字段 exact 为 `profile,inputs,projection,value,not_applicable_reason`。`projection` 是 version0.1/profile `failure_projection` 的原 canonical bytes envelope；collector 只捕获实际 Host 派生输入/结果。projector 从下列 inputs 独立重算，校验 envelope SHA 与最终 context `value`，不能把任意 self-reported semantic SHA 当来源。
- `inputs` 每项 exact 为 `kind,head,registration_head,member,path`。kind 仅 `member|root_input|typed_source|execution_record|ordinary_call`；head 为原已验证 source raw SHA，path 为该 source 内的字段路径（仅按下面 recipe 使用，不能作为任意删除/转换指令）。registered member 必须同时给 exact registration/member；其余 registration_head 为 null。root_input 的 member 仅 `root_goal.json|input_snapshot.json`，绑定原 creation input reference、真实 Run root 与原 file bytes；typed_source 绑定既有 A05/profile 验证。ordinary_call.head精确为原call reservation_head，再解析该call的实际input/config，不以无归属SHA猜callee。无 member 的 source 使用 member=null；每项inputs按canonical bytes排序、无重复，集合须覆盖该字段实际读取的全部材料，不能为同digest任选一个owner。

| profile | 适用与固定计算 |
| --- | --- |
| `domain_v1` | 仅原 Host 写入的 Planner/Analysis/Reviewer 0.1 domain member。先验证原 owner/metadata；只剥离顶层 `schema_version,case_id,run_id,attempt_id,attempt_kind,producer,status`，其余所有字段及嵌套值完整保留。digest-valued context 使用该 canonical 科学 body 的 digest；input_members 使用 stable slot/logical member ID 和同一科学 digest，不含 per-Attempt 路径。 |
| `root_v1` | 完整 root_goal/input_snapshot bytes 经原创建引用校验后作 canonical digest；不按字段名删除其科学内容。 |
| `input_members_v1` | 对实际读取的科学input逐个按root/domain/Code/Analysis的上述专用规则校验leaf；projection/value为原A06 `member_id,content_digest`列表，按stable slot/logical member ID排序、无重复。root/ordinary member leaf分别用root/domain规则，Code/Analysis leaf用其已证明科学preimage；不能把authorization/log/未知profile伪装成科学leaf，也不能只保留其中一项来满足hash。 |
| `policy_v1` | 绑定真实 policy_initialized/immutable policy bytes，使用原 policy digest；不生成新 policy。 |
| `host_config_v1` | 绑定实际 ordinary call config 或原 Host runtime/policy config；structured config 全部保留。Code/Analysis相关verification_specs、environment、allowed_command和expected_outputs等科学配置，不能因A06专用context字段集合较小而丢失，须在config科学preimage中完整绑定。物理workspace locator只能通过原typed workspace/spec规则验证后由专用profile分离，不能对任意config字符串去根。 |
| `host_ids_v1` | program/tool/verification IDs、base revision/tree 来自原 scheduled/source kind、实际 resource/config、Task/spec/verification 声明的 stable ID 与 validated immutable base。列表依原 A06 sorted/unique 规则；不使用 capability/Attempt/job/workspace ID 或 artifact canonical path 充当 stable ID。 |
| `code_causal_v1` | 先原 A05 校验 task/result/change/verification/base。`code_digest` 的科学 preimage exact 为 `base_revision,base_tree_digest,final_tree_digest,changes,patch_digest`；change科学preimage exact为 `base_tree_digest,final_tree_digest,changes`。changes为原change manifest完整ENTRY_FIELDS，repo-relative path/mode/blob与before/after内容SHA均material。`code_task_context_digest`使用原A06 `semantic_context("code", ...)` 的CODE_CONTEXT_FIELDS；要求/acceptance、backend版本/runtime、base及各policy完整保留，input_evidence_digests为逐项已绑定的科学leaf digest，不用含执行身份的原member SHA替代。没有patch时保留原nullable事实，不造zero/empty patch。 |
| `analysis_causal_v1` | 从原已验证preparation/spec、Code科学preimage、selected inputs、immutable base、runtime/environment/allowed_command/expected_outputs重算原A06 `semantic_context("analysis", ...)` 的ANALYSIS_CONTEXT_FIELDS。verified_change_digest使用上述change科学preimage的digest，input_code/input_artifact使用绑定leaf digest；runtime与policy完整保留。完整spec/manifest/checksum只作独立provenance，不能直接成为repeated key。 |
| `not_applicable_v1` | 只适用于原CAUSE_FIELDS允许nullable且真实不适用的字段；inputs=[]、projection为canonical null、value=null，reason仅为 `no_code`、`no_fresh_analysis`、`no_immutable_base`、`no_plan`，须与失败时实际来源一致。非nullable字段、已读取材料或缺失应有证据不能用此profile。 |

- 上表是新 FailureFingerprint 因果来源的 recipe，不改 B03 原 `task_context`、preparation/aggregate context/checksum 或 A05 trust。相同名称的原 wire digest 与新科学投影分别校验，不能直接改原 receipt/reservation 或赋予新的全局 digest alias。Code/Analysis 科学 preimage 与 leaf 计算必须按表重算；原 A06 primitive 的字段集合、hash 算法、schema不改。
- 字段/profile配对也闭合：`program_ids,tool_ids,verification_ids,base_revision,base_tree_digest`用host_ids；`input_members`用input_members；`plan_digest`用domain且必须是实际selected Planner member；`code_digest,code_task_context_digest`用code_causal；`analysis_execution_context_digest`用analysis_causal；`config_digest`用host_config；`policy_digest`用policy。上述名字均带表中 `_v1` 后缀；root仅用于科学leaf。除有实际不适用证据的nullable字段可用not_applicable外，不能用其他配对/空inputs替代应有材料。非not_applicable的not_applicable_reason必须为null。
- 各binding.value须与相应CAUSE_FIELDS字段的类型exact：domain/root的科学digest、Code/Analysis semantic digest用独立重算结果；policy/base等既有材料digest保留经原校验的值；stable IDs列表保留列表；input_members每项保持原 `member_id,content_digest` schema，以slot/logical member ID排序；nullable只走not_applicable。projection保留计算这些value的原preimage，不把其SHA盲目填进所有字段。FP constructor必须实际使用同样的value，不能只在normalizer改写因果意义。
- 对当前 no-Code 反例，Plan 投影 exact 为 `{"code_needed":false}`；任何额外科学字段会原样参与 hash，不能只挑 code_needed。无法按已列 profile证明科学/身份边界的输入必须停止，不能另加未批准 recipe、递归删 key、遮掩任意 hex 或用 None 兜底。
- 所谓“仅 summary/path 变化不改变 repeated key”只指原 diagnostic 的自由叙述、Human approval reason 和已证明的 execution/workspace locator。科学目标、method描述、任务要求、配置、repo-relative code路径及任何未被证明是 incidental 的 domain字段均是材料，哪怕字段名为 summary/path/run_id 也不能递归删除。diagnostic 的 stable classification/exit/signal/failing IDs/structured validator errors参与实际 failure body。
- incidental 数据从因果 preimage 剥离不等于从 trace 排除：所有原 raw bytes、metadata、owner 与 Human reason仍依原 0.7/A05 来源参与 normalized 轨迹；科学变化必须改变 context/normalized，身份/授权/来源变化须影响完整 normalized 或拒绝，不能通过新 profile 放宽旧 exclusion。
- Code/Analysis 来源 meta 可组合原 B03生产端口和真实产品 scheduled target 构造，保持本票不交付 Code parent graph adapter；不能用 patched selector/state/ledger 冒充实跑。原明确 contract-only 的低层 unit fixture 可保留原标签，仅用于其原规则，不计实际发行/消费或 B04 owned。

### Grant 的发行阶段、权限与顺序

1. 原 resume 先 claim/consume Pause，提交 Human validator 与真实 `validated`；原新的 `advance_run` 提交 `human_gate -> decision_coordinator`、response `consumed` 及当前 Coordinator allocation/capability。**validator、paused Run 或该 inbound Transition 之前均不得发行 Grant**。普通 approve_rerun/approve_with_conditions/reject_or_hold 不发行 Grant。
2. issuer 必须是上述 exact Coordinator 已 started 的原 Invocation；consumed response 的 authorized_target_attempt_id 等于其 identity，Request/Pause/snapshot 与当前 Run/Cycle及实际授权 failure occurrence相符。原 authority/fence、heads、policy/counters、clock及无 terminal owner 都须有效；同一 response 已发行 Grant 时只读原事实，绝不重发。
3. 权限取自原 resume producing operation 的已认证 `request.actor`，经原 request_digest/phase/ProtectedSnapshot publication 证明；校验 actor_type和scopes满足原 Pause authorization，snapshot decided_by与实际 actor_id一致，Request明确允许 approve_budget_window 和唯一 work_target，实际 validated/consumed action为该值。Grant `actor_scope=["approve_budget_window"]` 只表示上述已证明授权的 typed action，不从输入自报的scope/free text派生，也不新增ActorContext公开权限枚举或把“resume”单独当预算授权。
4. 在 original replayed state 上确定最终四层 Work target/route，再作完整 integrity → risk/scientific/security/data/protection → policy/absolute ceilings/terminal reserve preflight；预算机会只允许该 route allowance额外一次。可以校验尚未发行的 proposed Grant 参数，但不能 patch state、提前写 active_grant、伪造已发行/已消费事实或把失败 preflight写成allow。进入真实 stop_sequence 或只能使用 reserve收尾时不发行。
5. preflight同时冻结原0.1完整Grant payload、admission事实及 next `stable_attempt_id(attempt_index+1)`/`stable_transition_id(transition_index+1)`；**计数取当前已分配 Coordinator后的真实 replay**。cycle_id保持原response/approval Cycle；replan的新Cycle由原advance在消费后创建。冻结事实使用原支持的journal/snapshot/publication机制，不新增runtime wire/journal字段或用test-owned来源授予authority。
6. 原fenced `append_budget(grant_issued)`完成后，Coordinator只完成原domain/publication，不自行scheduled Work；由新的原 `advance_run`在已冻结目标上执行 `grant_consumed -> target scheduled -> A03 invalidation -> Transition committed -> head validation`，全部闭合后才激活Work。消费不能放在validator或Coordinator调用Agent内部；实际target/heads发生冲突时停止，不能换target、退款或重算新Grant来修复。

### 预算事件 publication 的故障边界

必须在两个fresh根分别实际触发下表 before/after边界；使用原observer/journal/operation接口，不改registry/case分类，不把这些meta算B04 owned。Python异常与真实进程中断分别标识，按原合同分类，不把捕获异常当进程已死的证明。

| 原边界/真实前缀 | 必须验证的恢复/限制 |
| --- | --- |
| failure_observed 或 grant_issued 的 budget intent已冻结、ledger/index尚未完整发布 | 原owner/fence和exact journal存在时只调用原suffix物化既有bytes；不能重算fingerprint、增加occurrence、重新做grant授权或重复append。尚无完整Target completion事实时，预算suffix完成也不授权重新invoke started target；保留显式recovery/unavailable。 |
| failure/grant已发布，Coordinator completion尚未冻结 | 保留原event/charge/Grant和实际不可重派发状态；重读/duplicate不能重新观察、发行或运行Work。按原合同记录可证明failed或recovery_required/unavailable，不能为了恢复自动造一个completion/terminal。 |
| Coordinator completion已冻结，attempt_finished/index/checkpoint publication部分完成 | 只有原owner、完整completion与前缀exact时走原publish_completion suffix，不能再运行Coordinator/Agent、再发Grant或new advance；authority/事实缺失保留recovery或原完整性failed。当前B04 graph自动重入缺口不算已修复；本票须用原owner端口证明suffix可达或保留真实恢复状态，不能用state patch制造成功。 |
| 原advance的grant_consumed已冻结/已发布，target、invalidation或Transition尚未闭合 | 按原A06 materializable prefix只由原operation补齐同facts；target未启动、Work effect=0、grant不退款。缺少预计算事实或owner不可证明则recovery_required/unavailable；真实conflict按原failed，不能重新消费/新建Transition。 |
| 完整消费/Transition/capability已提交，duplicate/reentry/重读 | Grant issuer/consumer/event/target都保持唯一，occurrence与effect次数不增加；wrong owner/epoch/head/response/target/重发重消费均拒绝。原Run terminal之后不恢复Work。 |

原泛化 Invocation/graph自动前缀接续继续属于B04；本票不得同时要求未授权修复该问题且声称当前源码已修复。本表原端口suffix、真实unavailable及单次性证据是C15必需验收，不能因“留给B04”跳过。

## Deliverables

- 显式新版本实现、被动 collector、按上述字段/profile/阶段落实的封闭来源合同及专用 meta；
- 当前受影响前置入口的逐项 impact 清单、before/after raw、固定新 expected、双 fresh 与四消费者证据；
- 实际Coordinator阶段发行并由原 Transition 单次消费的 validated Grant、authenticated actor关联，以及预算事件故障表的before/after raw、journal/operation事实、单次性与无法安全恢复材料；
- completion、maintenance 追加、当前状态和独立 B04 阻塞复核；未批准阶段只交付本 review 票和索引。

## Acceptance Criteria

- 两 fresh 根原生产端口重建本次 `Plan -> failed Analysis -> Coordinator -> Human`；新版本通过、0.7 原规则拒绝，实际不同 execution IDs 不改变因果 fingerprint，effect 只执行一次，重读不执行 effect；
- Plan 科学字段（含额外method/config与嵌套字段）、root input、policy/config、Code causal leaf/context、verified change、fresh Analysis runtime 的合法变化改变normalized和适用context；仅已证明incidental变化不改变repeated key。覆盖same-Cycle retry和真实replan后的同科学材料不同Plan owner/不同occurrence、missing/duplicate/orphan/错误次序、未知字段/profile、篡改/foreign/stale Session拒绝，不能用跨fresh Run各occurrence1代替Run内第二次失败；
- 原生产端口验证第一次/第二次失败、Human 同一 snapshot 重入及成功后旧失败处理；C13 批准/拒绝保持实际 accepted/rejected 与 single-use response，publication-pending 可原 suffix 补齐，started/no-completion 保留 recovery_required，无额外 effect；
- 至少两个fresh根实际 `validated -> human_gate/Coordinator Transition+consumed -> Coordinator started -> preflight -> grant_issued -> 原advance grant_consumed`；next target/Transition按该Coordinator后的计数exact、replan保留approval Cycle并创建新Cycle。必须拒绝validator提前发行、错actor/decided_by/scope/Request/Pause/failure occurrence、hard ceiling/reserve、foreign/duplicate/错误action。合同fixture不能替代生产发行，Source envelope不可替代原authority；
- 预算故障表每行before/after双fresh实跑：冻结/未发布和已发布/未completion分别保留真实前缀，suffix只补同bytes，事实不足保持原recovery/failed/unavailable；重复进入不重算FP、不增加occurrence、不重发/重消费、不执行未激活Work。原full Transition/target闭合前effect=0，正常执行后累计单次；同时覆盖lost owner/epoch、tampered intent/completion/heads与Grant消费中断；
- collector、matrix exact、runtime validator、exit digest 四路径及同当前 Session 的新/受影响 meta 实跑；meta owner 为 B00、不计 B04 owned；
- 执行时 current fresh construction **15/11/30/28**、同 Session B02 **1410**/B03 **645** 和完整 exact collection/suite；无旧 expected 语义覆盖或新增 exclusion。具体 original final 缺口仍为 B04 **47 coverage /144 binding** 与 B05 **15 adapter**；
- **131 required、84 mapped、47 remaining、2199 cases、324 boundaries、28 post-claim、B04 144 cases、15 exits** 和原 owner 集合保持；全部源合同及受影响前置回归闭合后再独立复核是否可以恢复 B04 ready，不直接 completed。

## Verification

批准执行后从实际新增 nodeids 建立当前 Session，使用仓库原入口（不得以本票文本代替真实回执）：

```bash
/opt/anaconda3/bin/python -m pytest tests/phase_b/test_b00c15_product_failure_sources.py tests/phase_b/test_b00c15_trace_consumers.py tests/phase_b/test_b00c15_budget_publication.py -q
/opt/anaconda3/bin/python -m pytest tests/phase_b/test_b00c11_human_snapshot.py tests/phase_b/test_b00c11_trace_consumers.py tests/phase_b/test_b00c12_human_request_packet.py tests/phase_b/test_b00c12_trace_consumers.py tests/phase_b/test_b00c13_human_continuation.py tests/phase_b/test_b00c13_trace_consumers.py -q
/opt/anaconda3/bin/python -m pytest --collect-only -q
/opt/anaconda3/bin/python scripts/validate_phase_b_acceptance.py --help
```

随后依 B00 原 Session/native verifier、有界分批机制与 construction CLI 实跑完整 suite、owned 1410/645 和具体 final ID 集合。版本 dispatch、四消费者、bytes/recipe/owner 拒绝测试及 full Session 不能以普通 pytest 总数替代。初始 review 只检查模板、依赖、链接、scope、冻结正文与 diff，不实施上述命令或新版本。

## Stop Conditions

- 依赖或 fresh 当前输入证据不满足入口；
- 需要改变 Phase A/runtime wire schema、风险/科学权限、budget/owner/case/exclusion/Session 或扩大 Allowed Files；
- 因果 projection 不能证明真实读取与完整材料、Grant 只能由伪造 snapshot/ledger 构造或 primitive bypass 通过；
- 需要未列profile、逐字段任意排除、SHA单owner覆盖、变更B03原wire context/原A06primitive，或validator提前发行/修改Grant目标以规避原next-target规则；
- 旧版本拒绝行为不能保留，或前置回归出现超出本票明确交接的语义变化；
- 真实安全停止/authority/publication 不可证明却需制造终态；
- 预算故障验收只有重算/重发/退款/重复effect、新owner接管started Invocation或未授权的新journal/schema才能通过；
- required 验收只能 skip/xfail/过滤/历史证据通过。触发即 blocked，保存反例并另审，不扩大本票。

## Required Documentation Updates

批准执行后建立独立来源合同和 completion，追加 B04 maintenance/completion、源文档实际合同、Current State/Overview/索引及必要 Decision Log。创建阶段只追加本 review 入口与当前 B04 blocked 原因，保留全部历史，不虚构实现/完成记录、批准、Session 通过或 commit。
