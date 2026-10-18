# B00C12 Human request packet 与 Host receipt 来源补充合同

2026-10-02。由[冻结C12](../phase-b-graph-harness/B00C12_HUMAN_REQUEST_PACKET_TRACE_HANDOFF.md)批准，补充[C11基础合同](B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_CONTRACT.md)。实际状态与当前输入验收见[C12完成记录](../completions/B00C12_COMPLETION.md)。这是test-owned来源证明；production/wire、预算、authority、A03 slot、case/owner和旧sealed材料保持。

## 显式选择与原材料

仅trace0.7/proof0.4执行本补充，复用原closed proof、ordinary_members及A05完整DAG。没有新profile、proof字段或version。Trace0.1–0.6沿用原解释；合法0.6/proof0.3对直接异常和receipt maximum仍拒绝exception_settlement，对原Human snapshot仍拒绝human_owner。

原Human请求的requesting Attempt与packet publisher独立。当前真实来源为attempt_000003请求、attempt_000004 Human Gate发布；注册artifact为attempt_000004:approval。唯一member为approval_packet/request.json，canonical exact为attempts/<publisher>/approval_packet/request.json；原strict canonical JSON bytes exact为同request的created ledger record，packet_reference=null。后继packet_written不是请求文件内容。

## Owner、publication 与 locator

同case/run的created唯一、packet_written至多一次。Created未发布的原前缀不要求未来成员或completion。发布后核对原request ID/cycle/index/requester/scope/action，原Gate scheduled→started→packet_written→finished的顺序、Human Gate kind/physical node、父Attempt和cycle、approval output、实际registration execution head、packet_written artifact head/index。注册、成员或发布源缺失/重复/foreign均拒绝。

Root来自Session/owner和既有A05验证的Run output_root，不能从待验引用反推。Packet wire必须exact为root拼canonical member的原绝对路径；相对路径、额外分隔符、dot/traversal、foreign root/Attempt/member及同内容不同文件均拒绝。每个路径组件不得symlink；原文件须regular，实际bytes/SHA/size、declaration、registration和原created相等。

只读原.lqcd/control_operations.sqlite，定位Gate唯一原capability和advance_run committed producer。核对closed authorization、authorization_digest、identity/scope/terminal closure revision、producer operation/epoch/result revision、实际observer phase/result/owner与result heads、原execution prefix/manifest/bounded projection。当前canonical publisher由fresh epoch0 acquire后在epoch1执行，worker与该原graph producer一致；不能以请求Attempt或后来的resume owner代替。核对原published started_intent、持久化completion_intent、原execution bytes前缀、artifact publication previous/content/projections、base64 member bytes、index/current approval、projection及checkpoint/manifest摘要。核验没有执行lease、publish、resume或effect。

Packet的publisher是原Invocation completion。Human response snapshot独立来自原resume prestart_records_committed publication，保持C11的既有fencing检查；不要求packet出现在control_publications，也不要求整个后继resume completed。

## 来源DAG与material

仅在所有原bytes/关系校验后，已验证的typed execution packet_written.packet_reference编码为human_request_packet_locator：case/run、request ID、独立publisher Attempt、canonical member和原created member source引用。该引用沿现有完整DAG传播；原raw digest先校验，没有任意digest alias。

当前实际闭包只有typed原packet_written携带该根路径字面值；审计逐source/path记录，原producer/checkpoint的其他Host字段继续原规则。未知容器即使包含同名字段或完全相等的nested record也不获得此绑定，任意文本仍material。未来不能未经同源证明泛化重复位置；需要新来源合同时按原Stop处理。Owner/request/member/scope/action/bytes/producer变化被拒绝或改变normalized/exact，只有合法双fresh根的同一来源关系归一。

## Closed Host exception receipt

原直接异常evidence仍为closed {type,message}。补充receipt仅为既有maximum_evidence.content的closed {schema_version,resource_operation_id,exception}，version0.1，exception exact为真实callee的closed {type,message}。Resource ID exact为原reservation/settlement ID；额外字段、版本/shape不符、错误resource/exception或缺来源均拒绝。

Receipt在真实callee异常后，由持有原authority的Host meta收尾分支根据实际reservation生成canonical bytes，并经原ArtifactEffectPort.append_budget实际提交actual=null和该bytes的evidence_digest。Collector冻结当次实际提交材料；不包装已有直接异常、不重写ledger。原settlement唯一、capability/Run/Attempt/producer/epoch/revision、raw SHA和evidence_digest仍逐项核对。

原ordinary call必须raised、exception为实际值、outcome=null；end未执行、原clock观测、hard usage unknown/null保持。Receipt不能证明Agent返回、provider停止或授权。真实epoch变化仍优先clock_untrusted；没有异常的return/overrun/read failure不能使用此exception receipt。最大费用不退款，原直接Host overrun/clock evidence和typed token/cost unknown原义保持。

## 消费与交接

正式matrix仅新增原B00/A07-META-006与015的final来源meta：B00C11-MAXIMUM、B00C11-HUMAN、B00C12-MAXIMUM-HOST-RECEIPT；绑定真实observe nodeid，expected分别为原C11 maximum、新C12 Human与receipt。Fixture闭合，原scenarios/owners/refs/registry/cases不变。

三类来源分别进入collector、matrix、runtime validator和exit semantic digest，使用同一normalize/compare与Session绑定；missing/tampered/foreign及stale token/每个digest均拒绝，outer artifact hash重算不能绕过。Runtime/exit的isolated hook为contract meta，B04_owned=false，不是B05 adapter。

真实Human来源仍为recovery_required，真实submitted/validated保留，没有consumed/Grant/Work。重读不重新运行graph/resume/Agent/effect。C12须完成全部来源、C11逐项及当前Session验收后才completed；随后只接续C11独立完成交接和原B04入口复核。产品Human/guard/Host字段/ordinary收尾、Code/fallback/Analysis/fingerprint/grant及47/144仍归B04。
