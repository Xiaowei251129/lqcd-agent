# B04 Maintenance Record

## 2026-09-30：所有 ordinary target 的失效前来源绑定

- Ticket：[B04](../phase-b-graph-harness/B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)。
- Problem：已有 Analysis/Decision artifact 时再次调度 Analysis，原 `advance_run` 在 A03 反向校验中失败并产生 unavailable closure；执行前反例见 `/private/tmp/lqcd-agent-b04-readiness-current-ehcdfewr/rerun-probe.json`。
- Root cause：`AdvanceOperations._snapshot` 只为重复 canonical Code 绑定 `input_references.current_artifact_ids`，其他目标却仍执行非空 invalidation，因此 scheduled 来源与实际 clear 不一致。
- Change：复用原 invalidation set，为每个 ordinary target 冻结其 exact prior IDs。保持原 seven-slot policy、scheduled → invalidation → Transition 顺序、identity、operation phases 与恢复合同。
- Verification：新增 Analysis rerun、Coordinator 重入和 Planner replan 的 production advance/registration/history 正向检查，结果待补记。
- Scope：原 B04 Allowed Files 内的 contract-preserving 修复；不修改前置票据、schema 或冻结 case。

## 2026-09-30：失效来源修复验证补记

- 初次Analysis/Coordinator/Planner与相邻control回归25项通过；本轮产品/resource/来源反例及相邻advance/artifact合计19项通过，legacy325项通过，protocol生成字节和compileall通过。
- 修复没有改失效矩阵、slots、canonical历史、owner或case语义；新scheduled记录保存exact被清除IDs，canonical成员与原history前缀保留。
- B04后续发现的trace0.5 ordinary resource来源类型缺口需要修改B00验收边界，超出maintenance授权。未以本记录授权其实施；B04依冻结Stop Conditions转为blocked，待审[B00C10](../phase-b-graph-harness/B00C10_ORDINARY_RESOURCE_TRACE_HANDOFF.md)。

## 2026-10-05：Host字段隔离与前向风险检查

- Problem：Agent content可覆盖Host产物metadata；成功但high/critical或歧义诊断仍沿Planner/Analysis前向路径派发Work。
- Change：`ProductNode`在任何domain member写入前拒绝保留Host字段，包括同值覆盖；原resource effect只执行一次并已实际settle。`select_product_route`在原17 edges内把高风险、confidence不唯一、Human需求和硬安全/非retryable科学问题先交Coordinator，后者继续原Human guard。
- Verification：`test_b04_host_boundary.py`覆盖十种保留字段（同值/foreign）与十一种Analysis风险/歧义/安全分类，核对原ledger/registry、下一Work未scheduled、effect未发生及未接受memory。连同原product/invalidation/resource/trace专项**33 passed**；证据`/private/tmp/lqcd-agent-b04-resumed-nz8hjtnr/retained-b04-focused.txt`。初版测试十项误用了不存在的settlement字段，已改为检查原typed actual值；九项Planner正向升级测试暴露缺current Analysis dependency，定位材料保留在candidate中，不声称该完整路径通过。
- Limits：这只证明已验证的Host边界和Analysis guard；Planner到Coordinator的早期dependency、Code guard、terminal收尾及整票owned/final验收仍未完成。本轮旧Human固定expected有待审定的fingerprint差异，不能把33项或此前3742当作当前全量通过。
- Scope：只改本票`nodes.py`/`routing.py`和新B04专项；不改变schema、17 edges、owner、case、budget算法或原Agent返回事实。

## 2026-10-05：Human局部候选因来源Stop撤回

- Candidate：validator的finished output refs不再声称原publisher的approval；仅当前request的latest submitted response可校验；原physical human_approval_gate严格映射canonical kind。批准/拒绝各双fresh原端口确实完成，request packet/history保留，duplicate/reentry没有新effect。
- Stop：C11/C12原fixture固定recovery_required，与实际committed接续冲突；0.7对不同Coordinator相同诊断SHA保存单owner，完整来源被human_diagnostic_source拒绝。两项都超出B04的fingerprint-only前置golden/来源范围。
- Disposition：Human候选已撤回，完整代码/差异及raw保存在执行根；`analysis_graph.py`与入口字节相同。原Host/guard局部修复保留；旧harness/fixture/expected/前置断言未改。新[C13](../phase-b-graph-harness/B00C13_HUMAN_CONTINUATION_SOURCE_AND_PREFIX_HANDOFF.md)仅review，未以maintenance授权改B00或交付新来源合同。

## 2026-10-05：保留源码legacy验证补记

- 保留Host/guard源码后的legacy **325 passed**；证据`/private/tmp/lqcd-agent-b04-resumed-nz8hjtnr/retained-legacy.txt`。Human来源专项为1 passed/1 exact failed，固定expected差异尚未审定，未覆盖expected；当前完整suite/owned Session仍未完成，B04 blocked。


## 2026-10-05：C13 审定的最小 Human 接续修复

- Authorization：按用户指令修订并执行[冻结 C13](../phase-b-graph-harness/B00C13_HUMAN_CONTINUATION_SOURCE_AND_PREFIX_HANDOFF.md)，来源/前缀边界由独立[C13合同](B00C13_HUMAN_CONTINUATION_SOURCE_CONTRACT.md)交接。本记录只描述该纠偏票审定的局部生产修复，不扩大原 B04 范围。
- Change：validator output 不占旧 approval ownership；当前 request/latest response 校验；physical/canonical kind 严格匹配；committed duplicate 即使尚未 graph advance 也只读；普通审批与真实 stop sequence 分开，原 validator/advance 传递真实停止链；已进入 tail 的 validation 使用剩余收尾容量，原 deterministic close 不返回 Work、不产生 accepted。
- Verification：原批准/拒绝各双 fresh 实际 accepted/rejected、submitted→validated→consumed、相同 diagnostic SHA 的独立注册与全 trace exact 通过。真实 phase_b_test 停止 Gate 剩余5 Control 可 halted、无新 Work；普通容量不足也走 typed halt/原 closure。当前输入 full Session 与扩展反例仍在验证，最终计数以 C13 completion 为准。
- Limits：Planner dependency、ordinary exception/overrun 收尾、Code parent/fallback/Analysis/fingerprint/grant 和 B04 47/144 尚未完成；B04 继续 blocked。


2026-10-05 C13执行收尾：Human最小接续/来源修复和29项专项通过；固定同Session全仓3791 passed/1 failed，B02 owned1410/1410、B03 owned645/645、legacy325及fresh construction15/11/30/28通过，final原47/144/15 exact缺口保持。唯一失败为C10旧Host identity测试仍要求completed后normalizer拒绝，而生产端口已在publication前拒绝；修改该测试不在冻结C13范围，故C13 **blocked，未completed**，B04继续blocked/0-of-144。新增C14仅review，创建不代表批准或实施。见 [C13 blocked记录](../completions/B00C13_COMPLETION.md) / [C14待审](../phase-b-graph-harness/B00C14_HOST_IDENTITY_REJECTION_ASSERTION_HANDOFF.md)。原131/84/47、2199 cases、324 boundaries、28 post-claim、15 exit与owners保持；Planner dependency、ordinary收尾、Code/fallback/Analysis/fingerprint/grant及B04 47/144仍待修。文档/lifecycle交付与固定验证输入分开，未commit/push。


## 2026-10-07：Planner 控制依赖和 ordinary 主路径收尾

- Authorization：用户批准实施冻结[B04](../phase-b-graph-harness/B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)接续计划；ready正文SHA256仍`3a1e273839579721e330c02fb430fcec615b6d5e7428e051a02255f2196134ca`，执行前完整bytes/manifest在`/private/tmp/lqcd-agent-b04-execution-20261007-e90cbzz9/before/`。
- Planner：schema0.4的decision在Review尚不存在时按实际upstream绑定至少Plan，registration preflight/history replay一致；Review存在时保留正常Plan/Analysis必需检查，legacy默认不变。memory_report要求真实成功Analysis/Review才能科学接受；早期Human批准只能pending、拒绝仍rejected。
- Ordinary：产品Host单独包裹原run_resource，实际同步callee结束且原owner有效才以原reservation/producer/capability最多结算一次maximum；实际callee exception用C12原Host receipt，返回后overrun/clock错误保留实际Agent return，不套exception receipt。原Invocation publication后由close_run关闭failed；有任何已冻结settlement不补第二次，没有结束/owner失效保持真实unsettled/显式恢复。token/cost unknown不换零、不触发maximum，底层primitive和旧unsettled fixture未改。
- Verification：新增控制失败10项、双fresh严格0.7来源4项通过；B04 control/resource/Host合计35通过；原product/invalidation/C11/C12/Host identity合计73通过；legacy registry106通过（包含在完整legacy325内），完整legacy325通过。上述组有重叠，不合计冒称全仓通过。
- Golden：C13三份固定expected仅同步实际application_build/graph_topology及派生引用；保存旧正式raw、两fresh新raw和完整digest preimage DAG，原hash计算/校验返回不变，仅独立只读审计剥除这两个已授权字段后全部材料exact。审计`C13-runtime-fingerprint-audit.json`、`human-prefix-runtime-fingerprint-audit.json`；审定后的C13完整29/29通过，包括四消费者及当前Session正式meta。
- Publication probe：原budget.resource_settled after故障可原failed completion并经重入安全failed closure，call1→1、settlement1→1；原invocation.attempt_finished after故障留下真实finished succeeded/未物化index前缀，graph重入被Artifact index cross-head mismatch拒绝、Run running、无closure、call1→1。后一项仍是B04原局部publication接续责任，不伪造终态，不声称本轮已修复全部fault路径。材料`publication-fault-summary.json`和各实际capability/closure事实。
- Stop：独立完整候选副本的Host稳定因果Plan fingerprint，两fresh真实不同Run得到相同合法fingerprint/occurrence1和Human binding；原0.7拒绝failure_member_source。候选只保存临时副本，未纳入当前生产源码。不能改用含执行身份的raw SHA、留null、改旧expected语义或放宽validator；按冻结Stop将B04 blocked并创建[C15待审](../phase-b-graph-harness/B00C15_PRODUCT_FAILURE_FINGERPRINT_AND_GRANT_SOURCE_HANDOFF.md)，本记录不授权其新版本或前置meta交接。
- Limits：Code parent、四层fallback、fresh Analysis、完整fingerprint/grant、ordinary publication后续修复及47/144仍未交付，B04 owned0/144；当前完整suite/同Session owned1410/645未重跑。原owner/inventory、Phase A、B00验证器/旧版本、旧sealed历史不变，无commit/push。


2026-10-07收尾补记：原construction初轮因A05/external/historical fixed expected exact失败，未过滤；从执行前完整字节快照和当前源码分别按原端口为13组来源各重建两fresh raw，旧raw exact等于执行前expected、两组各normalized一致，完整preimage DAG除application_build/graph_topology及其派生引用外exact。仅12组发生批准摘要变化，审定后连同此前3份C13总计15份fixed expected同步，无其他语义变化；审计`derived-goldens/reviewed-runtime-fingerprint-audit.json`及全部before/after raw/preimages。补充B02/recovery/重复Code原来源专项10/10通过。

审定后重新创建fresh Session，原CLI construction **15/11/30/28**全部通过；final具体ID负向集合exact为B04 **47 coverage /144 runtime binding**与B05 **15 exit adapter**，没有其他类别/对象。证据`retained-construction-reviewed/`、`exact-final-ID-audit.json`，初轮失败完整保留。原全仓exact collection **3806**（执行前3792+新增14），只是collect，不声称3806通过；B04 owned仍0/144，当前全量suite和同Session B02/B03 owned回归未执行。

冻结B04/C13/C14及全部既有phase-ticket正文、旧harness/Phase A/legacy tests/configs/case/owners均按执行前bytes核对不变；仅B04 lifecycle现blocked。全部历史保留，fingerprint候选不在当前src；C15模板/依赖/链接/scope/diff审查通过但仍review，未批准/实施。检查见`retained-scope-frozen-review.json`、`retained-vs-execution-entry.patch`。验证固定输入与随后收尾文档交付分开，不retag历史Session；无commit/push。

## 2026-10-07 — C15 authorized Host integration in progress

C15冻结授权范围内新增Host科学failure派生与Coordinator阶段validated BudgetGrant发行，复用原原子append_budget/capability/resume/advance，不增加runtime wire、权限或budget journal字段。Agent不能发行failure/Grant，Human validator不发行，消费仍由原Transition所有者执行。

实跑same-Cycle两次失败后，合法Grant消费使历史automatic_analysis_rerun_per_cycle used=2（原自动额度1）；下一正常Reviewer路由原_snapshot对未增加的历史route维度仍套base ceiling，错误拒绝Route decision disagrees with replayed capacity。最小接续校验只允许unchanged历史route用量且已由同Cycle（replan为Run）的已消费Grant及原committed target/Transition证明；任何新route增量仍走原额度/当前Grant，work/control/transitions/cycles等absolute ceilings与reserve不变，replay totals/limits/profiles/resource primitive不改。实跑success接续通过。C15尚未完成，须全量回归及故障/fencing审计，不代表B04整票完成。

2026-10-07 source scope stop：上述C15 Host与单次消费接续为部分实现，非完整validated交付。canonical Code audit新增profile试验已撤回原a05_trace.py；C15blocked/C16review，当前Human/matrix未验证接线已恢复执行前字节。详细反例和未完成验收见[C15实际记录](../completions/B00C15_COMPLETION.md)。

## 2026-10-07 — C17 authorized Coordinator Human admission candidate

在冻结C17授权内仅修改graph/routing.py：用原policy/reserve和replayed dimensions前置校验ordinary Human publisher+validator容量，不改变实际计费/计数。容量不足使用原budget_stop/sequence，terminal Request不开Work/Grant；route allowance单项耗尽但原Grant全局容量/tail可达时保留普通Human。原三项terminal、ordinary容量和原Grant共5passed。

随后实际ordinary invalid validator control6→5后，原repause统一按terminal3/4而发布无sequence普通Pause，纠正被原Resume拒绝；terminal invalid→纠正双fresh还暴露literal repause proposal_id依赖raw heads。保留两fresh反例/完整preimage，不改Resume、primitive、authority、输入或旧expected。修复超出C17范围，C17/C16/C15/B04blocked，C18review，见[C17记录](../completions/B00C17_COMPLETION.md)。候选不等于整票交付，完整suite/同Session owned及原47/144仍未验收，无commit/push。

## 2026-10-07 — C18 original repause candidate

按用户执行C18授权，仅修原invalid_response_admission内部来源与ProductRouteAdapter.repause的ordinary/terminal容量选择；trace0.8绑定原proposal recipe。原C13两项及新C18三组双fresh通过，未改Resume/预算primitive/收费/reserve/Grant权限。候选保留，C18因原端口不可达transition阈值验收矛盾blocked，待审C19；不宣布整票或B04验收通过。见[C18执行记录](../completions/B00C18_COMPLETION.md)。


## 2026-10-07 — C18预算publication被动采集候选

C19完成后按原授权接续C18。Grant advance结果发布后事务回滚，再由原operation补齐时，原ControlTrace重复记录两个同identity/revision/epoch的after回调，实际durable phase只有一次，0.8严格来源拒绝producer_phase。按C15/C18允许的helpers/control_traces.py被动交接范围，0.8输出只据原durable journal核对提交事件，保留所有原始observer回调，拒绝不一致重复；不改变生产、normalizer、旧版本或Session规则。专项/其余待验见[C18执行记录](../completions/B00C18_COMPLETION.md)；B04仍blocked、owned0/144。

## 2026-10-08 C18 原范围维护与 C10 当前入口停止

本轮接续未新增production修改。0.8被动collector仅按原durable producer history发布phase事实，保留原始中断callbacks及严格重复phase拒绝；真实Grant result_committed回滚/原suffix双fresh证据通过。新增B00 meta按原scenario_id排序，未修改矩阵验证器。

13组前置及7组current Code/Human expected已按原许可完成before/after raw、双fresh和完整preimage审计；另在完整suite发现C10 mixed runtime fingerprint遗漏并完成同类2+2 raw审计及fresh原nodeid复验。完整扫描的其他真实源码/测试失败只有C10 structured failure当前入口仍为0.6；未改该未授权入口，见 [C20 review](../phase-b-graph-harness/B00C20_C10_CURRENT_FAILURE_SOURCE_VERSION_HANDOFF.md)。所有失败日志、旧expected快照和后续验证输入分别保留；没有扩大exclusion、改owner/case或伪造全仓通过。

## 2026-10-08 C20当前来源入口修复

经用户批准C20，C10当前structured failure仅显式接到既有0.8/被动ProductFailureSources；no_code_trace默认0.6和primitive/mixed不改。新专用测试/fixture/expected与B00 meta验证原实际返回、actual结算、旧版本精确拒绝及四消费者；未改production、旧normalizer、case/owner或预算。C18按原授权接续最终固定输入验收，各票尚未宣称completed。

## 2026-10-08 C20交接与各纠偏票完成

C20未改production或旧projector；显式版本参数保持默认0.6，原C10nodeid只加0.8选择。75项focused和当前完整4139项通过；C15–C18原覆盖表逐项复核完成，共用同一nativeSession。所有旧expected、PhaseA、cases/owners及冻结正文保持。B04独立入口按具体47/144/15、construction15/11/30/28与owned1410/645核对后恢复ready，原产品集成和47/144不在本轮完成范围。记录/manifest区分验证输入与随后文档交付，未commit/push。

## 2026-10-08 产品Code parent接续候选

新增既有subgraph.py内的ProductCodeHost，组合原ExternalProducer、CodePrestart、Pause、ExternalDispatch、ExternalNormalFinal及CodeAgentSubgraph；产品Runtime默认接原consumer，并在普通Invocation启用原preparation复核。Task来源选当前Plan主成员及Coordinator明确packet证据，保留完整科学内容，不将诊断旁路/audit全量注入Code任务。总deadline与Backend aggregate timeout按原producer分段事实接线，未修改底层预算算法。

原产品图三类actual Code候选success/needs_input/failed已各实跑通过；验证单次dispatch、原Resume消费、后继由独立advance拥有、success fresh workspace/subprocess、非成功转Coordinator/Human和只读重入。开发期三次失败日志保留：首次总deadline误当aggregate timeout，第二次测试从value读取DB主键，第三次测试错误读取Transition owner且任务误携带完整诊断旁路；分别在新adapter/新测试内纠正，没有修改原来源profile。三项通过耗时40.82s，根`/private/tmp/lqcd-agent-b04-continuation-20261008-89ygr3t6`。来源trace、fallback及原47/144与全量验收仍待完成，不构成整票通过。


## 2026-10-08 — Product Code retry parent provenance / source stop

- 本轮 ProductCodeHost 从实际 Plan main 与原 typed packet 派生 Task，保留 packet 所有 evidence，不把广域 scoped context 的 ancillary diagnostics 自动变成科学 Task 输入。Task Human reference 使用原 consumed response 的 `payload_sha256` 和 Run-relative protected payload path；原 response 授权的 Coordinator 必须为本次 Code inbound parent，Task 不消费第二次 Human response。
- `CodePrestart.commit_task` 的 coordinator_code_fix historical source 集合仅追加原 advance snapshot 的 populated Code slot，与原 Analysis/Review/Decision 同样按原 tuple/SHA/bytes 检查。旧 Code 不恢复 current；不接受任意 history/latest source，不改变公开 Task schema、backend trust、budget、producer 或消费所有者。这是原 B04 parent integration 的来源遗漏修复，不授权新的科学投影。
- 当前保留输入 `test_b04_code_parent.py` 三项与原 `test_code_prestart.py` 二十四项合计 **27 passed in61.48s**。原 negative authority、rehashed evidence、expired/stale fencing 与 fresh-process frozen publication 均保留。log：`/private/tmp/lqcd-agent-b04-continuation-20261008-89ygr3t6/retained-code-prestart.log`。不是 full Session/owned 验收。
- 实际重试先在两个fresh根复现 prestart `Task evidence changed`（`repeat-code-fourth/`）；上述最小来源修复后，`repeat-code-fifth/` 与带被动采集的 `repeat-code-source/` 均两fresh完成第二次 Code dispatch/final/消费，随后第二次 Coordinator `product_failure_material` 拒绝 `Code evidence lacks a scientific profile`。原 Code producer/effects各一次，Run running/Coordinator未完成，没有发布第二次 failure/Grant、没有退款或制造终态。
- 首轮新 helper 的 capability 多余字段、Human payload 字段与relative路径错误分别保留在早期logs，已修正；不是来源合同阻塞。三条首轮 Code 0.8完整trace双fresh接受/相等在 `code-sources-second/`，该专项先于最后prestart源码修复，不冒称覆盖最后整个输入。
- **Stop**：C15生产Task科学leaf与原0.8 projector只接受Plan/Analysis/Review，无法表达packet实际要求的历史Code主结果。B04禁止改变B00 validator/已批准recipe；冻结Stop后仅保存完整两fresh raw、Run/Coordinator副本/manifest，并创建[C21 review](../phase-b-graph-harness/B00C21_PRIOR_CODE_EVIDENCE_CAUSAL_SOURCE_HANDOFF.md)。未实施0.9/0.6，未改旧expected/排除/owners，不回写已completed纠偏票。


2026-10-08停止后只读来源补记：两fresh真实stopped prefix均被原0.8接受，但normalized有28个派生引用差异。独立记录原hash返回值的完整preimage审计定位到第二次Task的`human_authorization_ref.scope_digest`仍为literal raw SHA，未绑定原Request scope及其diagnostic来源；首次Task投影相同。原正常/needs_input/failed单次Code trace通过不覆盖这项Human retry接缝。反例`repeat-code-source/*-preimages.json`、`normalized-prefix-diff.json`与`repeat-preimage-audit.log`已保存；C21 review同步补齐闭合Task授权声明与专用scope/payload来源要求，未修改任何projector/旧expected。


2026-10-08完整preimage定位补充：前条scope遗漏成立，但不是唯一literal。第二次Task完整preimage exact仅两项差异：历史Code `evidence[].sha256` 与 `human_authorization_ref.scope_digest`；首次Task一致。仅在私有只读比较中标记这两项后，其余Task preimage exact相等，见`repeat-code-source/task-preimage-diff.json`和`scope-binding-audit.json`（true）。C21 review已同时写明原Code member引用与protected Request scope绑定；没有更改实际hash、生产或expected。

## 2026-10-08 — C21 authorized historical Code source repair

C21独立授权仅在product_failure_material读取真实packet/advance snapshot选择的历史Code主结果并复用C15科学preimage；ProductCodeHost._task补齐实际Human snapshot/Resume actor/Request work-target的parent provenance。没有修改A05 wire/A06 primitive或production reservation/dispatch/final/预算算法。显式0.9/0.6、被动来源及专项验收记入[C21独立记录](../completions/B00C21_COMPLETION.md)，本项不是B04 owned验收。

Unsafe原final保持recovery_required/unavailable、无canonical Code与新Work；直接graph重入读取null active_pause并TypeError，属于B04原generic recovery的局部修复责任。C21没有扩大Allowed Files去修analysis_graph。B04仍blocked，47/144及完整接续未完成。

## 2026-10-08 — C21 source implementation / resource gate

C21实际来源、Human parent与0.9/0.6修正已实施，本票source/meta49/49和对应输入construction15/11/30/28/final具体47/144/15通过；完整4191仅通过475后因磁盘约401MiB停止。C21blocked、A6/full/currentowned未完成，B04保持blocked/owned0-of-144，不能提前恢复ready。原generic unsafe recovery的null active_pause、全产品接续及47/144仍由B04完成；本次未修analysis_graph、未代填本票runtime。见[C21实际记录](../completions/B00C21_COMPLETION.md)。所有历史保留，无commit/push。

## 2026-10-11 — C21 handoff; no new B04 runtime repair

C21已独立完成历史Code科学evidence与Task Human来源完整交接，0.9/0.6仅显式开启，见[C21完成记录](../completions/B00C21_COMPLETION.md)。本轮只闭合前置验收并复核B04入口；未新增B04 production变化。generic unsafe recovery null active_pause及原47/144仍待B04局部维护/整票执行，禁止将C21 meta代计owned。源码范围变化或新来源解释仍按冻结Stop Conditions另审，历史条目保留。

## 2026-10-12 — Unsafe recovery graph reentry without an active Pause

真实ProductCodeHost normal final在kill_all、bounded_drain、post_stop_stability三种安全停止无法证明分支均保留原 `operation_status=recovery_required / terminal_closure=unavailable`，Run paused且active_pause=null；generic CanonicalProductRuntime.node重入原Code target时却无条件读取pause_id，三种路径都抛TypeError。反例、实际原Run/trace、effect次数及authority对比保存于 `/private/tmp/lqcd-agent-b04-continuation-20261012-g565kgdc/unsafe-before/`。

局部修复仅在已有paused interrupt payload选择中判别active_pause：存在时保留原pause_id；空值时采用既有run_status interrupt表示paused，不创建Pause、Transition、closure或新effect。没有更改wire/schema、public control contract、恢复策略或owner，文件在B04 Allowed Files内。新增三项实际Code端口回归各重复run两次，确认无新Code/Agent调用、无Code canonical pointer、原final/Run全部字节和invocation capabilities保持。连原Code parent、no-code graph、Planner/Human/ordinary failure专项19/19 passed（91.26s）；此为局部验证，不是47/144或整票完成。

## 2026-10-12 — Finished ledger precedes completion publication

原compiled graph在invocation.attempt_finished.after发生真实Python boundary interruption后，Planner effect次数1→1，却跳过尚在started且持有冻结completion_intent的原Invocation，直接advance导致Artifact index cross-head mismatch。反例与原trace保存于 `/private/tmp/lqcd-agent-b04-continuation-20261012-g565kgdc/publication-before/`。局部修复只在实际finished ledger且发现唯一普通completion owner时，调用原InvocationLeases.publish_completion完成预授权suffix，再由原advance推进；保留原fence/lease/epoch/member校验，排除external_consumption，其release与checkpoint仍由原Resume owner处理，不重调Agent。

实际Planner、Analysis、Reviewer三层、before/after、normal/expired lease/tampered member共18/18通过（67.71s）：合法原suffix补完后继续完成graph且重复readonly；无有效authority或成员篡改时拒绝、原Run字节/effect次数保持。新的正常publication trace通过显式0.9/proof0.6原normalizer；范围/public contract/恢复策略保持。未将该局部专项计为B04 owned runtime，47/144及full尚未完成。

## 2026-10-12 — Source-contract stop after local repairs

上述两项局部修复在同一最终源码下共同专项37/37通过，12种产品轨迹各双fresh严格0.9相等。新的actual settled/no-domain publication prefix由旧agent_registered_diagnostic规则拒绝，超出本票旧规则摘要同步权限；按冻结Stop创建[C22 review](../phase-b-graph-harness/B00C22_ORDINARY_SETTLED_PUBLICATION_PREFIX_SOURCE_HANDOFF.md)。本条不是新合同/normalizer实施授权，也不计B04 owned；详细实际事实见[B04 completion](../completions/B04_COMPLETION.md)，反例在 `/private/tmp/lqcd-agent-b04-continuation-20261012-g565kgdc`。


## 2026-10-13 — C22 source handoff and independent entry

[C22](../phase-b-graph-harness/B00C22_ORDINARY_SETTLED_PUBLICATION_PREFIX_SOURCE_HANDOFF.md)显式trace0.10/proof0.7来源交接completed，保留实际return/actual settlement、原capability/producer/journal/frozen plan和public prefix；旧0.9反例仍按原规则拒绝。当前固定Session full4273/legacy325、同Session owned1410/645、fresh15/11/30/28及final具体47/144/15通过，独立B04入口复核通过后依原授权恢复ready。原active_pause=null与原completion publication局部修复经完整集合回归；C22没有修改production或扩大恢复行为。

B04仍须在原Allowed Files内显式消费已批准0.10来源、完成剩余普通/Code/fallback/fresh Analysis/Human/Grant/terminal/recovery集成和原17routes/9forbidden、18boundaries/144owned、47construction。局部contract-preserving修复继续另记maintenance；出现新来源或scope问题仍按冻结Stop保存反例。B04owned0/144、131/84/47、原case/owners、B05draft与PhaseBfalse保持，不保证未来零阻塞，不自动完成B04。见[C22实际记录](../completions/B00C22_COMPLETION.md)。

## 2026-10-13 C24 来源实施与原生验收停止

C24 专用90项、16类双fresh来源、8个fresh native四消费者及188组拒绝、construction15/11/30/28与final原47/144/15已验证。完整4549集合仅4261节点取得合格批次证据（含legacy325）；同Session独立owned未完成。两个B04 publication/control工厂的spawn child来源binding为unit-only而父进程为真实Session，独立原生反例均失败；文件与C24执行前一致，超出其Allowed Files。C24/C23/B04保持blocked，C25仅review，原始失败与未完成清单保留。B04仍owned0/144，不把局部测试当作整票完成。见[C24实际记录](../completions/B00C24_COMPLETION.md)及[C25待审](../phase-b-graph-harness/B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md)。无commit/push。

## 2026-10-14 C25 交接说明

本轮B04相关测试接线由已批准的[C25](../phase-b-graph-harness/B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md)实施并完成，不属于额外production维护。四类spawn显式binding、144双fresh诊断隔离、原36条factory断言及正式owned0/144已审计；没有新增B04运行时修复。C24ready、C23/B04blocked；独立接续责任见[C25完成记录](../completions/B00C25_COMPLETION.md)。

## 2026-10-14 C24 完成交接

本轮未追加B04生产修复。[C24](../completions/B00C24_COMPLETION.md)已完成独立来源验收，七类停止route双fresh证据及旧默认/原assert保持已复核；C23 ready、B04 blocked。B04后续维护和47/144执行须经C23原A6入口，不由本段扩展scope或所有权。

## 2026-10-14 C23 完成与 B04 接续责任

本轮没有新增B04代码修复。[C23](../completions/B00C23_COMPLETION.md)完成全部独立验收，A6确认已复现来源和native Session阻塞消除，B04按原授权恢复ready。原18边界/144case工厂目前返回phase-only诊断，后续必须把真实Run source proof接入主runtime evidence并建立原registry/matrix绑定，再完成47construction/144owned/full；该B04 slice工作在原Allowed Files内，但本记录不授权改变旧validator、schema或验收边界。七停止、post-claim/unsafe/fencing与packet/context四层负例仍须正式验收，owned0/144保持。

## 2026-10-14 正式来源接线前的 Stop

本轮没有新增B04代码修复。三个原case各双fresh native诊断通过；原capability删除和canonical member损坏后，严格0.10/0.11来源重验分别publication_prefix_journal_revision/frozen_member拒绝。正式B04绑定亦使C25原“未绑定hook必须拒绝”测试失败（原validator实际正确返回空owned集合）。前次入口漏查这两项正式接续关系；详见[B04实际记录](../completions/B04_COMPLETION.md)。

处理需要显式新来源及前置meta生命周期修订，不能以maintenance扩大合同；B04 blocked，[C26](../phase-b-graph-harness/B00C26_B04_FAULT_SOURCE_AND_OWNED_ACTIVATION_HANDOFF.md)仅review。未改production/harness/registry/expected/owners，未代填47/144，C23/C24/C25 completed保持。


## 2026-10-14 C26来源候选停止

本轮没有B04 production局部修复。C26真实来源预检显示原publish_budget/publish_started幂等调用仍有精确CAS revision增长，Human followup的parent恢复未被child Host UUID fixture覆盖；这两项不能靠放宽旧normalizer、忽略完整业务行或修改原primitive处理。反例、局部候选及未完成项见[C26记录](../completions/B00C26_COMPLETION.md)；[C27合并补充](../phase-b-graph-harness/B00C27_B04_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_FIXTURE_HANDOFF.md)仅review，尚未授权。B04继续blocked/owned0-of-144，原47/144任务保持。

## 2026-10-14 C27来源接续事实

C27在批准范围内补齐测试来源层的原恢复CAS、parent Host身份与四阶段证明，未改本轮production。B04仍blocked；原47construction/144owned需在C27、C26和独立入口完成后执行。本条不代替B04产品修复或完成声明。见[C27记录](../completions/B00C27_COMPLETION.md)。


## 2026-10-15 C27 已批准来源范围内的局部遗漏修复

本轮未改B04 production。C27新verifier补齐原atomic index临时文件的精确消费；新collector在生成派生prefix前用原parser读取index，并保留损坏index后态null/原parser拒绝；原Grant advance冲突的关联close_run按parent/冻结heads和policy/trigger/reservation/实际Host分配/完整unavailable closure逐字段验证，禁止伪造终态。原工厂动作、断言和旧normalizer保持。专项前两项2 passed、Grant close双fresh1 passed，完整当前输入尚待验收。第三轮72个通过/1个失败及2个不完整outer批次全部保留于`/private/tmp/lqcd-agent-b00c27-execution-20261014-4tnw5c0n/acceptance-v3`；不将这些局部结果计入B04 owned。C27 in_progress，C26/B04 blocked。

## 2026-10-15 C27局部修复通过，完整验收等待容量

C27第四轮source验收133通过/1失败，必要prefix父目录遗漏已在其批准的新verifier范围内修复；原失败及剩余分支补跑12/12，C25–C27专项125/125通过。当前精确收集4674，全量重跑因可用5.75GiB低于10.75GiB预估而未启动，安全候选审计0可清理。C27/C26/B04保持blocked；没有B04 production修改或owned登记，不将不同输入结果拼接。C27完成后仍须C26逐项独立复核和B04入口。原47/144/15、131/84/47及owners保持。证据`/private/tmp/lqcd-agent-b00c27-execution-20261014-4tnw5c0n`，无commit/push。

## 2026-10-16 C27来源交接事实（本轮未改B04生产实现）

C27承接C26来源修复：显式0.12独立原生anchor/完整S0–S3、窄重复CAS和父恢复Host fixture、原atomic index临时文件精确消费；被动collector先验证损坏index，保留原parser拒绝且不新增无效prefix。原production/工厂动作及断言/旧规则未改，全部变更受C26/C27范围约束。原144双fresh通过仍属B00来源meta，B04正式owned仍0/144。

验证：full4674/4674（legacy325、新增96）、原18/144双fresh共288native、同Session独立B02 1410/B03 645、fresh15/11/30/28、final原具体47/144/15；131/84/47、2199/324/28、15exit与原owners保持。原失败和反例完整保留，无commit/push。证据：`/private/tmp/lqcd-agent-b00c27-execution-20261014-4tnw5c0n/acceptance-v6`；Session `d2d6bb33792d3bebbc2753543210efc7b5ff4fbe6869356b38949a103903d187`，固定输入 `ffb712c5f3acdeda20302de658ed18689a26bf8ab8f93678d844dbbfa146ec89`。文档/lifecycle交付另存manifest，不声明修改文档后重跑全量。


## 2026-10-16 C28完成后的独立接续入口

C28修订获用户批准后完成C26一项meta生命周期修正，未改本轮B04 production。真实probe身份、未绑定拒绝、完整代表结果/诊断隔离、原144来源双fresh只读审计及C25–C27兼容扫描通过；full4678/4678（legacy325）、同Session独立B02 1410/B03 645、fresh15/11/30/28、final原具体47/144/15通过。原失败/超时/索引冲突均保留，未放宽validator、旧拒绝、case/owners或正式owned规则。

C28 completed后独立入口通过，依据原授权仅B04 YAML恢复ready，正文冻结；C26/C27 completed保持，未登记正式B04 owned。131/84/47、2199/324/28、18/144、15exit及原owners保持，B04仍需原47construction/144owned和剩余产品验收，B05draft/PhaseBfalse。执行与独立入口证据`/private/tmp/lqcd-agent-b00c28-execution-20261016-dzlh452h`，详见[C28实际记录](../completions/B00C28_COMPLETION.md)。无commit/push。

## 2026-10-17 容量恢复后的 B04 正式接续

用户授权继续 B04。当前 5240 个输入文件与 C28 delivery manifest exact 一致，原前置均 completed、原47要求/144case与owners一致；可用32.25GiB通过12.75GiB入口预留，执行前manifest/文件快照/git diff/冻结正文保存在 `/private/tmp/lqcd-agent-b04-execution-20261017-vnz2rk_k`。仅B04 YAML ready → in_progress，冻结正文保持。复用C28已通过的前置证据，不重标其Session。

本轮将原18个边界/144个case接入真实production hook、正式observation和case result；保留C25/C26 native诊断的原身份和空owned语义。代表case双fresh exact、7组协议stop class/context双fresh及同一Session/批次两个正式case通过。B04 S0取证文件按case唯一命名，旧native诊断文件名保持。construction原47要求现已由生产场景映射，累计131mapped/0remaining只表示映射，尚无本轮整票通过或144owned声明。

当前B04 in_progress；当前冻结输入完整suite、同Session独立B02 1410/B03 645/B04 144、fresh15/11/30/28/47、full exact与15exit-only final仍待实际验收。C28 completed、2199cases/324boundaries/28post-claim、原owners、B05draft及PhaseBfalse保持。无commit/push。

### 2026-10-17 construction 选择有界化

首轮CLI construction将62个重叠生产场景纳入同一原300秒pytest进程，触及上限后报告driver internal_error；原request/report保留于本轮执行根construction-first。未取得完整通过，不能据此声称任何未提交case通过；进程盘点确认原pytest/spawn均已退出。

仅将重复覆盖的B04 construction场景保留为required final，construction采用覆盖原47项的25个生产场景；所有scenario、nodeid、expected、invariant、case result、原full/final必验集合均保留。没有排除失败断言、改变timeout、扩大exclusion或改B00规则。选择/47集合审计保存在construction-selection-audit.json；重新固定输入后从fresh CLI重跑。首轮与后续Session分别保存，不拼接。

### 2026-10-17 construction 单次构建与双fresh回归分离

第二次25场景CLI同样触及原300秒pytest上限；request/report保留于construction-second，进程盘点无遗留pytest/spawn。尚无construction通过，不复用两轮未提交结果。

发现construction仍重复运行每场景的双fresh及重复normalization。新增B04专用single-run construction节点：每项从fresh生产Run生成原严格source trace，由原observation/exact-trace校验；原24个对应双fresh场景及全部其他required场景继续保留为final/full必验，144case及其正式节点/分类/owner保持。construction仍25节点exact覆盖原47要求，原300秒和所有expected/拒绝/验收规则不变。新单次构建不声称替代双fresh一致性，整票仍须完整当前输入全量验收。

### 2026-10-17 原时限诊断及验收覆盖补齐

第三次construction与独立verbose诊断均保留；诊断在原300秒明确报TimeoutExpired，已逐项通过的前13个节点不能代替完整envelope。没有产品断言失败被过滤。复核发现Human/rerun、旧结果/re-review、单次授权/grant的expected源字节分别exact相同；依据真实长轨迹覆盖的共同要求，将construction合并为14个生产Run、exact47要求。全部旧场景及单实例/双fresh节点继续required final/full，没有删除case、expected、invariant或放宽300秒。源合并理由见construction-source-union-audit.json，新增联合断言直接检查Human只回Coordinator、terminal无Agent调用及policy不变。

补齐四层fallback的28个生产node负例：原committed advance边界停止，先读真实有效context，再篡改实际登记的Coordinator member；target/parent/evidence/budget scope/Human authorization/full audit/member均须在新target effect前拒绝，重复进入不重执行、不制造terminal。保存原/受损bytes、context、Transition、实际异常、effect计数及Session索引。node层按原matrix合同不声明trace或owned case；不把它们冒充0.12或原144 runtime来源，原route/trajectory/external的严格source与双fresh门槛保持。

当前仍B04 in_progress，construction/完整suite/同Session2199owned与最终交付未通过；本轮不创建完成声明，不重标历史Session，无commit/push。

## 2026-10-17 B04 整票验收完成

正式18/144接入原生产factory、hook/observation/case result及matrix；只在正式模式显式使用已批准0.12，原C25/C26诊断分支保持。S0文件名按case隔离，防止同batch输出父目录冲突。原47映射和14条真实construction来源闭合，所有原双fresh及其余场景仍在完整4749中。新增Code/external/capacity与28个fallback实际member篡改负例，不改production、harness、旧golden、case分类、owners或预算算法。本轮完整4749、原CLI15/11/30/28/47、同Session1410/645/144及final具体15exit通过；golden来源、超时重分批和本地socket环境限制留痕见[完成记录](../completions/B04_COMPLETION.md)。验收与交付manifest分离，不重标、不commit/push。
