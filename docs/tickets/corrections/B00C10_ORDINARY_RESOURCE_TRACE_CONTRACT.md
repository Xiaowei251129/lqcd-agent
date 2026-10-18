# B00C10 ordinary source trace 合同

2026-10-01。本合同由用户批准执行的[B00C10](../phase-b-graph-harness/B00C10_ORDINARY_RESOURCE_TRACE_HANDOFF.md)交付，实施和验收状态见[独立执行记录](../completions/B00C10_COMPLETION.md)。这是test-owned来源证明合同，不改变runtime journal、wire schema、authority、A03 slot、预算算法或case分类。旧trace0.1–0.5/proof0.1–0.2分支继续按原规则解释；普通成功结果在0.5的两个原拒绝反例继续保留。

## 显式版本与闭合声明

只有`trace.schema_version="0.6"`选择新增projector。`proof.schema_version="0.3"`的完整字段为`schema_version,binding,objects,output_roots,typed_sources,material_sources,workspace_roots,ordinary_calls,ordinary_members`；前七项交给原proof0.2/A05完整校验。`binding`继续要求当前Session token及全部输入digests exact相等。消费者不能提供exclusion、alias、reference path或投影算法。

`ordinary_calls[]`字段闭合为`schema_version,profile,reservation_head,capability_id,authorization,producer,input,config,outcome,exception`，version固定0.1，profile仅`primitive|scoped_llm|analysis_tool`。`exception`仅实际`{type,message}`，缺省为null；outcome缺省为null，不据此推断side effect未执行。

`input/config/outcome`及内部派生source声明字段固定为`{schema_version,profile,sha256,content}`，version0.1。Profile闭合为`input,config,outcome,member,report,reservation_payload,analysis_spec,analysis_manifest,fingerprint,causal_context,grant`。`content`是exact UTF-8 bytes的字符串；raw SHA-256先重算。JSON使用production严格parser，`canonical_bytes(parsed)==raw`才接受；报告正文和Human原始pretty JSON保留raw bytes，Human另以strict JSON解析并核对submitted snapshot。普通原始canonical digest与A05自描述checksum不可互换。

`ordinary_members[]`仅`{schema_version,registration_head,member,sha256,content}`，version0.1。每项必须有原A03 registered event或Human protected snapshot event；所有ordinary registered members必须exactly once声明，缺失、重复、额外和foreign registration均拒绝。source hash相同的合法诊断可以被两个Attempt注册，两个registration/owner绑定分别校验；不能因此丢失一个producer。

普通input/config/outcome不能再次作为旧canonical_json source声明并选择旧投影；同hash跨profile alias严格拒绝。只有原Human Request member复用其exact execution record，及failure causal context复用已声明且原A05校验的code_context/analysis_context允许共享原source；调用方不能增加其他alias。

## 原调用与producer闭包

`authorization`仅原InvocationLeases冻结字段：`producer_operation_id,activation_result_revision,identity,heads,manifest,projection,artifact_history_digest,producing_epoch,terminal_closure_revision,checkpoint_anchor_kind,scope`；fresh Analysis可另有原`target_preparation,preparation_receipt`，不得任意增减。校验器只读原`.lqcd/control_operations.sqlite`的capability row，要求captured authorization与原始持久化authorization完全相等，且原authorization_digest重算一致。原capability必须存在；不会创建、activate、lease或redispatch capability。

`producer`是实际ControlOperation完整snapshot，字段为`operation_id,idempotency_scope,idempotency_key,request_digest,operation_type,operation_variant,status,phase,phase_revision,worker_owner_id,lease_epoch,lease_expires,request,reservation,result,error,created_at,updated_at`。其operation ID、epoch、activation revision与authorization相等，capability ID为原`capability_<operation_id>`；原observer中的唯一对应phase/result digest必须相等。原身份字面值进入exact轨迹。

普通effect只使用已经committed的producer；校验器只读原ControlOperation row，严格重建完整producer snapshot并与捕获值相等。原coordinator禁止对terminal producer重新lease，因此此处不以新的owner/epoch替代原snapshot；同时要求observer的owner/status/phase及type/variant/event与原snapshot相等。联合篡改call与observer的worker字段也不能通过。

Request绑定原`resource_reserved` record的完整canonical digest。每项ordinary reservation恰有一个call；resource kind仅`llm_call|tool_call`，LLM profile只接受llm_call、Analysis profile只接受tool_call。校验原Attempt已started、原authorization execution prefix和checkpoint anchor、原scheduled身份及bounded projection；不把最终completed projection当作旧授权head。reservation之前的execution/artifact heads保持原record链关系。

`payload.input_digest/config_digest`分别重算actual input/config。`scoped_llm` config必须是原`{node:<attempt_kind>,structured_output:true}`。`analysis_tool` config必须是原preparation引用的runtime policy。primitive meta仅允许actual scalar input/config，没有新增产品配置。原reservation timeout、policy_digest、maximum_charge、applicable_limits、remaining_before从实际policy和reservation前budget replay重新核对；普通分支的task/producer/workspace专用字段仍为原null。

Settlement必须与原resource operation ID在同Run唯一匹配，晚于reservation，publisher operation ID/epoch/revision与原producer相等。`evidence_digest`重算actual outcome bytes；已settled但没有actual返回源必须拒绝。原production replay继续校验actual/maximum disposition、usage和记录顺序；tokens/cost的unknown discriminator和值保留，不折为零。Code aggregate和verification沿用原A05 profiles，没有ordinary伪装。

## Scoped context、成员与材料

Scoped input字段仅`identity,direct_parent_attempt_id,root_goal,current_evidence,remediation,relevant_history,budget_summary`。身份与原capability/Run Cycle相等，直接父Attempt来自原scheduled record；root goal来自原文件；budget summary来自reservation前replay。根据原PRODUCT_CONTEXT_SLOTS、当时current_set/current_cleared和scheduled prior input IDs重建selected evidence；每项必须绑定同Run实际registered member。Relevant history按原selected slots/直接父或packet evidence取最后四项，不能把完整audit作为prompt。

成员allowlist固定如下；同时要求slot、kind、producing Attempt、registration/pointer、namespace全部相符：

| Attempt kind | 允许成员 |
| --- | --- |
| method_planner | method_plan.json、method_planner_diagnostic.json |
| analysis_engineer | run_result.json、analysis_outputs/result.json、analysis_engineer_diagnostic.json |
| scientific_reviewer | scientific_review_report.json、scientific_reviewer_diagnostic.json |
| decision_coordinator | decision_log.json、decision_coordinator_diagnostic.json |
| human_gate | approval_packet/request.json；Human response仅原protected snapshot |
| memory_report | memory_update.json、final_report.md |

普通成员canonical path必须为`attempts/<original attempt_id>/<logical_name>`、projection_path为原logical_name，actual raw size和SHA先验证。主JSON的schema0.1、顶层producer/attempt_kind/Case/Run/Attempt逐字段与原ledger相等且保留；diagnostic按production validator验证；Analysis result payload和Markdown正文保持材料。Host未定义的Agent嵌套identity/path/hex全部保持字面值。

唯一派生字段是已经证明的registered pointer成员SHA/size和明确state_paths。state_paths字段必须属于原slot、实际canonical namespace及对应member文件/目录；派生为source reference及validated size，不简单删字段。只在原registered envelope、schema0.4 current_artifacts及checkpoint.control.current_artifacts处理这些结构；不会泛化遍历Agent科学内容中的类似pointer对象。

实际LLM返回在Host修改前冻结。`diagnostic`的original bytes与最终registered diagnostic分别校验；仅当实际返回evidence为空时允许Host加入最终selected evidence，其他diagnostic字段必须相等。Actual content的每项必须与registered主JSON对应值相等；因此Agent覆盖Host identity被来源校验拒绝。Agent不能自行指派failure fingerprint，保持原production规则。

Remediation字段仅原`target_node,problem,evidence,constraints,success_criteria,parent_attempt_id,budget_policy_digest,human_authorization`。Target和父Attempt/预算policy按原生产validator及Coordinator registered decision member验证；packet evidence必须实际注册。Human authorization仅`human_request_id,human_response_id,response_digest,target_node`，与原唯一consumed response、authorized Coordinator Attempt、request scope和protected raw snapshot相等；packet target也必须相等。所有problem/risk/confidence/retryability/candidates、constraints/success criteria、usage与science仍影响semantic digest。

## Fingerprint、grant、stop与不确定状态

原`failure_observed.payload.fingerprint`必须通过`fingerprint()/validate_fingerprint()`及budget payload validator。其canonical preimage和causal context分别为独立source；causal_context_digest及内嵌context建立有向引用，fingerprint_digest仅在原算法验证后派生self checksum。Code/Analysis causal context digest必须有原A05 typed source；plan_digest/code_digest如非null，必须有发生failure之前同Run注册的实际MethodPlan/CodeResult preimage，不能接受任意digest猜对象。其余causal/diagnostic材料保持原值。

Grant来源是原`grant_issued/grant_consumed`，要求同Run原failure/occurrence、`approve_budget_window`原Human request scope、exact protected snapshot/reference/response digest、原target kind/node一致；grant的fingerprint_digest和response_digest分别引用真实source。消费必须唯一，grant_digest重算issued payload，target Attempt/Transition与原issuance相等；原replayer继续校验single-use和admission authority。Decision的failure digest和Human request的diagnostic digest绑定对应原source，不能成为新的dispatch permit。

Stop只对原Transition已经存在的`fields.stop_sequence_id`验证。以原Run/source Attempt及原diagnostic category，或原budget_stop reason，重算`digest({run_id,source_attempt_id,reason})`；后续continuation必须引用已经commit的同一sequence。普通Human审批不由proof推断为terminal stop。B04若修复导致算法/来源变化，必须按本合同重新审定，不可静默改golden。

实际exception/overrun未settled prefix仅在原Run/Attempt仍running时接受；原budget replay保持maximum，不退款。Exact semantic source附上真实`exception`或`unsettled_return`观察，不能报settled/completed。重新读取原raw只重算证明，不执行effect。Source gap与真正unsettled的判定不同：已settled缺actual返回严格拒绝。

尚无生产路径的maximum disposition与fingerprint/grant新增测试明确标`contract_only`，使用原production builder/validator/replayer检查格式/引用算法；不写runtime case binding或B04 passing证据。这些合同级fixture不授予runtime权限，也不声称B04 overrun已恢复。

## DAG、collector与identity fixture

依赖顺序为原ledger/授权/pointer验证 → actual input/config及成员bytes → scoped refs/原A05 typed sources → ordinary outcome/settlement → 独立reservation payload、Analysis spec/manifest、fingerprint/context、grant依赖 → 原record/head → observer event。Self checksum按明确字段验证后标记；没有递归自引用。沿用原A05完整DAG的orphan/cycle/duplicate校验。新ordinary sources不经过旧A05任意key union，也不扩展旧全局ephemeral集合。

`OrdinarySources`在实际Agent/effect port记录收到的preimages，在delegate返回给Host前deep-copy并canonical冻结actual return；异常只记录实际type/message再原样传播。它不改变调用次数、timeout、返回对象、error、journal或authority。ControlTrace0.6在结束时被动读取真实末尾prefix，并收集actual registered members。Code verification的per-command result来自实际registered verification_results；原Task.spec和实际trusted verification workspace tree分别重算reservation config/input，继续使用原A05 verification类型。

Host identity fixture仅替换四个模块的UUID提供对象：`control.interfaces`、`control.coordinator`、`control.children`、`code_agent.external_operation`。每次原Host allocation调用原前缀规则，UUID为`UUID(bytes=SHA256(canonical_bytes({scenario_id,allocation_site,ordinal})).digest()[:16],version=4)`；ordinal每site从1递增并可持久化续用。Different scenario/site/ordinal、正常及异常退出恢复均验证；共享uuid.uuid4及LangGraph/provider/Backend随机源不变。不得替换allocator函数、capability、route或state。B04仅获得此新exact来源测试的窄fixture例外，冻结正文不回写。

## Fixed expected与消费者交接

真实compiled no-code路径及同一fresh Run的ordinary + 原B03 prestart/Fake dispatch/trusted consume/canonical Bundle/fresh Analysis ports各有两个独立根审定。Mixed driver是B00 source meta，不代替B04 production route，Backend empty audit fixture不声称验证非空Backend tool audit；trusted verification和fresh Analysis仍产生实际tool记录。

Expected只离线固定，runtime绝不根据actual更新。旧raw必须重建原expected；新两根相等且差异只能是原批准application_build/graph_topology及其派生DAG摘要。Field diff、旧/新raw和独立semantic preimages均留在执行记录所指fresh审计目录；其他旧golden逐份检查，不推断只影响最初五份。合法材料变化应通过来源校验但改变normalized并使fixed exact comparison失败。

Collector、matrix observation/expected、runtime case validator、exit semantic digest共用trace.normalize/compare；每条路径保持当前Session约束。新增四消费者meta使用明确隔离的合成hook，只证明validator接线，不进入production registry/owned cases；没有B05 adapter。

全局维持131 required、84 covered/47 remaining、case0.4总2199（B02 1410/B03 645/B04 144）、324 boundaries与28 post-claim。C10完成仅解除来源及fixture前置；B04仍须修复Human validator/ordinary overrun/Agent保留字段，并履行原47/144、Code/fallback/grant/stop和B05义务。
