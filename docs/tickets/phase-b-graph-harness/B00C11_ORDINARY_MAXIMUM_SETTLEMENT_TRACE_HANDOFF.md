---
ticket_id: B00C11
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C10, B04]
---

# 普通资源 maximum 结算与 Human snapshot 的来源轨迹交接

## Goal

为普通LLM/tool调用的真实异常、返回后overrun及不可信measurement提供显式`trace 0.7 / proof 0.4`来源证明，使原生产端口已合法提交的maximum settlement及failed/terminal closure能够通过strict semantic trace验证。同一新版本补齐原Human resume的protected snapshot定位及grant/consumed remediation授权来源关联；只校正同一真实成员的绝对/相对定位表达，不增加Human运行权限。保留trace0.1–0.6、proof0.1–0.3和既有sealed evidence的原解释与拒绝结果。

2026-10-01，用户确认采用“来源纠偏＋B04接续”，并要求创建本票。当前为`review`，创建不代表批准或实施；只有另行明确批准为`ready`后才能执行。`depends_on: B04`表示纠偏目标，不要求blocked B04先completed，也不形成等待B04交付的执行前置。B00与B00C10必须已completed，B04保持blocked，原执行授权保持。

本票完成只解除已证明的ordinary maximum与Human snapshot定位来源交接阻塞，不修复B04产品运行缺陷，不证明47 construction、144 owned runtime或B05通过。实施结果另记completion，不回写冻结正文。

## Why

[B04最新核验](../completions/B04_COMPLETION.md#2026-10-01b00c10完成后的新阻塞核验)用原`start_run -> InvocationLeases.invoke -> ArtifactEffectPort.append_budget -> close_run`复现：同步effect真实抛异常且已退出，same-owner/lease有效；Host以实际异常canonical bytes为evidence完成`resource_settled(actual=null,tokens=unknown,cost=unknown)`，maximum未退款，Attempt/Run均failed，原close_run committed，effect调用exact为1。

该真实trace在0.6报`invalid_evidence:ordinary_trace:exception_settlement`。当前projector要求有exception时不存在settlement，已settled时又必须有actual return且没有exception；unsettled分支只能验证最终Run/Attempt仍running。原Invocation completion和Terminal close同时拒绝未结算ordinary资源，不能用永远保留running前缀替代合法收尾的来源验收。

原始反例位于`/private/tmp/lqcd-agent-b04-post-c10-review-8ox7u8nr/actual-exception-maximum-settlement-valid-actor/`，包含真实exception、running prefix、closed maximum trace和closure result；该历史证据仅用于定位，验收必须fresh重建。它是原生产primitives的source meta反例，不是B04 compiled route通过，也不证明远程provider停止。

2026-10-01待审复核在两个fresh根分别重现真实exception、返回后overrun和clock epoch变化，共六次原端口探针；effect均exact一次，原maximum settlement与failed closure均成功，0.6分别拒绝`exception_settlement`或`outcome_digest`。原`run_resource`在callee抛异常后没有执行结束Clock读取，不能把该正常展开形成的null误认成时钟故障；可信返回路径按原规则形成四维hard usage，没有独立的ordinary usage-unknown触发端口。本次修订据此区分未执行读数与实际读失败，将hard usage不确定作为实际异常/clock场景的material属性。审查证据见`/private/tmp/lqcd-agent-b00c11-readiness-review-083g7ni6/review-findings.json`；这些探针不表示0.7或B04验收通过。

2026-10-01再次复核：两个fresh根均由原resume提交真实Human protected snapshot；`human_response.payload_reference`为原Run下绝对路径，注册member的`canonical_path`为`human_responses/<response_id>/payload.json`。两者指向同一实际文件，bytes/SHA/size及submitted snapshot一致，但`ordinary_trace.human_snapshot`以字符串直接比较而报`human_owner`。`grant_source`和`human_scope`又使用该snapshot保存的相对路径与原response引用比较，必须一并校正来源关联。当前实际resume仍为recovery_required，本反例不证明Human validator/消费或grant产品路径成功；后两项关联是静态来源检查发现，不宣称已复现端到端grant失败。证据见`/private/tmp/lqcd-agent-b00c11-rereview-09heogff/review-findings.json`，验收仍须fresh重建。

[B00C10来源合同](../corrections/B00C10_ORDINARY_RESOURCE_TRACE_CONTRACT.md)及其成功/structured failure/unsettled prefix能力保持有效；新票不重新解释C10已completed的事实。B04禁止修改B00 validator、放宽trace或扩大Allowed Files，因此不能在B04 maintenance中解决此来源边界。

## Read First

- [AGENTS.md](../../../AGENTS.md)、[docs入口](../../README.md)、[ticket工作流](../README.md)、[模板](../TEMPLATE.md)及安全/验证文档；
- [A03](../phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md)、[A04](../phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)、[A06](../phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)、[A07](../phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)、[Control Protocol 0.4](../phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)及[需求目录](../phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)；
- [B00C10](B00C10_ORDINARY_RESOURCE_TRACE_HANDOFF.md)、[C10来源合同](../corrections/B00C10_ORDINARY_RESOURCE_TRACE_CONTRACT.md)和[完成记录](../completions/B00C10_COMPLETION.md)；
- 冻结[B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[最新核验](../completions/B04_COMPLETION.md)、[较早接续审查](../corrections/B04_CONTINUATION_READINESS_REVIEW.md)和[maintenance](../corrections/B04_MAINTENANCE.md)；
- `tests/phase_b/harness/{trace,ordinary_trace,a05_trace,pytest_evidence,failpoints,exit_checks}.py`、`helpers/{ordinary_sources,control_traces,ordinary_mixed,host_identity_fixture}.py`及C10 source/consumer测试；
- `src/lqcd_agent/control/{budget,capabilities,operations,clock}.py`：只读核对reservation、maximum、fencing与原closure关系，不修改production；B00C04与B02/B03完成记录中的同Session有界分批机制。
- `src/lqcd_agent/control/{pause,execution}.py`与`artifacts/registry.py`：只读核对实际Human snapshot发布、response引用、grant及消费关系；C10 Human/grant contract-only测试不能代替原resume来源正向。

## Scope

- 新显式版本的closed maximum来源声明、版本隔离投影与共用消费者接线；
- 新版本中Human protected snapshot的owner/root/member定位校验、限定字段的来源绑定投影及grant/consumed remediation关联；不增加proof顶层字段，复用原ordinary_members、output_roots与实际注册/ledger来源；
- 实际Agent/effect/resource边界的被动return/exception/clock/usage观测，原settlement证据preimage和原owner关联；
- 原生产primitives的LLM/tool maximum结算与收尾meta、scoped LLM来源交接、真实unsettled和不可安全收尾的反例；
- 双fresh根fixed expected、material sensitivity、旧版本兼容、四条消费路径及当前输入前置/全仓回归；
- 独立来源合同、completion及B04恢复依据/必修项的文档交接。

## Non-goals

- 不实现B04 route、Human validator/approval publication/Resume接续、Code parent、fallback、fingerprint/grant issuance/consumption或ordinary recovery/stop功能；Human范围仅为已经存在的snapshot/授权材料来源校验，不创建第二张产品修复纠偏票，不交付B05 adapters；
- 不修改production runtime/wire schema、ledger event/resource kind、A02 identity、A03 slot/invalidation、A04 owner/phases、A05 trust、A06 charging/ceilings或A07 acceptance；
- 不以maximum accounting推断provider未执行、effect已停止或Run可以关闭；不自动退款、重新调用或切换operation ID绕过uncertain资源；
- 不增加exclusion、wildcard digest、identity alias、任意路径别名或新的fixture patch权限，不改默认legacy CLI；仅下述经原owner/member证明的Human locator可以作来源绑定投影；
- 不commit/merge/push/PR/deploy，不访问真实provider/Backend/network、raw/accepted/repository outputs，不引入依赖。

## Allowed Files

- 本票ready后仅YAML lifecycle；B04仅在本票completed且复核阻塞解除后将lifecycle恢复原授权ready，不改正文；
- `tests/phase_b/harness/trace.py`、`ordinary_trace.py`：仅显式0.7 dispatch、version-gated maximum与Human snapshot locator/关联校验及来源绑定投影；允许新增专用`ordinary_maximum_trace.py`以隔离maximum分支。`a05_trace.py`仅在复用完整DAG及传递已验证Human locator所需的version-gated接线处改动，不扩大旧source kind union或通用路径投影范围；
- `tests/phase_b/helpers/control_traces.py`、`ordinary_sources.py`：仅显式新版本、被动maximum观测及原Human snapshot成员/来源采集；新增`ordinary_maximum.py`组合原ports及承载下述被动FakeClock port wrapper，通过原`Coordinator(clock=...)`注入；允许新增`ordinary_human.py`组合原ports产生snapshot来源meta，不实现生产Human/grant流程。旧0.6默认行为保持，其他既有helpers不改；
- 新`tests/phase_b/test_b00c11_ordinary_maximum.py`、`test_b00c11_human_snapshot.py`、`test_b00c11_trace_consumers.py`，新`fixtures/b00c11/`与`expected_traces/b00c11/`；
- `tests/phase_b/acceptance_matrix.json`仅追加原B00 requirement refs下的final source meta，不改owner、原场景、required refs或B04 bindings；`harness/{inputs,matrix,pytest_evidence,failpoints,exit_checks}.py`仅在共用normalize/compare确需新版本接线时调整，不改session/exact/report/selection/case/exit判定；
- 新`docs/tickets/corrections/B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_CONTRACT.md`和`docs/tickets/completions/B00C11_COMPLETION.md`，完成后分别记录生效合同和实际结果；两目录README只追加链接/事实；
- `docs/tickets/completions/B04_COMPLETION.md`仅追加交接事实，`docs/tickets/phase-b-graph-harness/OVERVIEW.md`、`docs/README.md`、`docs/REPO_CURRENT_STATE.md`、`docs/ARCHITECTURE.md`、`docs/VERIFICATION_GUIDE.md`、`docs/EVALS_AND_OBSERVABILITY.md`及`docs/DECISION_LOG.md`仅本票导致的当前事实/合同与决定同步；`README.md`仅canonical入口执行就绪说明的必要更新。

## Do Not Touch

所有`src/`、Phase A frozen files、B00–B05及既有纠偏票冻结正文、C10合同/完成历史、旧completion/correction历史、既有fixtures/expected/seals、`tests/test_*.py`、registry cases/dispositions/owners、131 required IDs和15 exit清单、legacy合同、依赖/config/evaluation、数据、outputs、accepted/Human decision文件、secrets、Git publication与外部系统。Allowed Files中的旧harness/helper只允许显式新分支；旧版本的合法/拒绝结果均须保持。B04 completion与索引例外只允许追加，不覆盖历史。

## Requirements

### 1. Explicit Version and Closed Sources

- 仅`trace.schema_version="0.7"`配对`proof.schema_version="0.4"`选择新分支；不隐式升级旧raw/expected。除本票明定的maximum来源及Human locator校验/投影外，沿用0.6全部ordinary request/context/member、A05 DAG、原SQLite capability/committed producer、Session binding与严格JSON检查；两个新分支均不得影响旧版本。
- Proof0.4保留proof0.3所有字段，并新增`ordinary_maximum_settlements`数组。每个declaration字段闭合为`schema_version,reservation_head,settlement_head,capability_id,reason_code,evidence,observation`，version为0.1；非maximum或尚未settled的call不声明此项。数组与实际ordinary `actual=null` settlements逐项set-equal，不允许orphan、duplicate或补声明替代缺失record。
- `evidence`和`observation`沿用`{schema_version,profile,sha256,content}`closed source envelope，version为0.1，profile分别为`maximum_evidence`和`maximum_observation`。保存实际canonical bytes，先核对raw SHA/strict parse/re-serialization，再验证关系；不修改原runtime payload或evidence bytes以适配proof。
- Reservation/settlement heads必须来自同Run/Attempt实际ledger，同一resource ID及原capability授权；settlement唯一且在reservation之后，publisher operation/epoch/revision与原owner一致。`evidence.sha256`必须等于原settlement的`evidence_digest`，其preimage来自实际Host/callee观察，不能按digest猜对象。
- 已settled但缺真实evidence/observation是source gap，严格拒绝；ordinary结果不能标成A05 failure/verification/Backend evidence。有效actual settlement仍走既有return/member校验，新声明不能绕过这些规则。

### 2. Actual Observation and Maximum Classification

Observation的content字段闭合为`schema_version,resource_operation_id,call_disposition,clock_read_state,clock_epoch_before,clock_epoch_after,start_at,end_at,hard_usage,host_error`，version为0.1。`call_disposition`仅`returned|raised`且与原ordinary call的actual outcome/exception一致；没有terminal observation的真实prefix不生成maximum settlement声明。Clock epochs为原Clock在实际调用边界观测到的string或实际缺失的null；timestamps为原Host该次resource start/end读取返回的Timestamp `{source,wall_seconds,monotonic_seconds}`或null。`host_error`为实际resource wrapper观察到的`{type,message}`或null，与callee exception分别保留。

`clock_read_state`仅允许以下三种，必须与实际读取/展开顺序及call/Host事实一致；它与全部measurement字段参与normalized语义：

- `complete`：callee实际返回，call_disposition=returned、call.exception=null，原resource start/end读取均成功，两个Timestamp都非null。可信与否仍须逐项验证epoch/source及非回退条件；完成读取不证明时钟可信。
- `callee_raised_before_end`：原start读取成功，callee实际抛异常，原`run_resource`未执行end读取；`start_at`非null、`end_at=null`、`call_disposition=raised`、call.exception非null且outcome=null。此项只说明结束读取未执行，不单独证明clock不可信或可信。
- `read_failed`：原start读取成功、callee实际返回后，原Host确实尝试读取end Clock/Timestamp或epoch并实际失败；start_at非null、call_disposition=returned、call.exception=null，保留已成功的值，未取得的值为null，`host_error`保留该次原读取失败的实际type/message。不能把collector未采集到读数、callee展开未执行读取或任意null声明成此状态。原start读取失败且effect未进入时没有terminal call，不生成maximum声明，保持真实前缀。

Clock观测必须来自原调用。允许新helper的被动FakeClock port wrapper记录原Host实际调用的读取、返回或读取异常及对应的资源调用边界；每次原`now()`只委托原FakeClock一次，原样返回同一个Timestamp或重新抛出同一实际异常，不额外调用`now()`，不advance/reset时钟或epoch。按真实resource调用边界关联原start/end，保留可复核读取记录；其他Host/lease/settlement/closure读数不能替代resource end。Collector可冻结原epoch在实际callee入/出边界的观测值，不将其伪装为未执行的Host读取。需要patch production Clock方法、增加读取或借用其他阶段时间才能补齐时停止。

| reason_code | 必须验证的实际来源与含义 |
| --- | --- |
| `callee_exception` | 实际call_disposition=raised、call.exception为真实type/message、outcome=null、clock_read_state=callee_raised_before_end；未观察到优先的实际clock违规。evidence保留实际异常或含该异常的实际Host receipt，不构造返回值或end读数 |
| `duration_overrun` | 实际call_disposition=returned、call.exception=null、actual outcome保留、clock_read_state=complete；同epoch/source、非回退的原start/end间隔确实超过reservation timeout。Host duration rejection保持，不能把actual大于maximum的payload当合法actual settlement |
| `clock_untrusted` | 观察到真实epoch/source变化、clock回退或read_failed及其实际原读取错误；不能据此声称可信actual duration。callee_raised_before_end的end_at=null本身不触发此项；collector漏采已有读数属于source gap。原maximum payload保留，是否能停止/关闭另按原authority判断 |

`reason_code`闭合为上表三项。多个已证明事实同时出现时，reason按`clock_untrusted -> duration_overrun -> callee_exception`确定；clock优先必须有独立的实际clock变化/违规/读取失败证据，不能由异常的未执行end读取或hard_usage unknown推导。异常同时确有epoch变化时仍保留真实exception/outcome=null并选择clock_untrusted；单纯异常展开必须可达callee_exception。所有实际return/exception/measurement均material保留。Observed overage/违规仍按原失败矩阵解释，不因maximum结算降级为成功。三个原因均无法证明的maximum声明严格拒绝，不补造理由。

`hard_usage`是closed `{state,value}` material属性，不是独立reason或maximum触发条件。known值须按原resource kind、实际一次调用与可信原Clock间隔核对原四维vector；可信overrun的实际测量可保留，但不能充当合法actual settlement。异常未执行end读取或实际clock不可信导致无法可靠确定完整vector时，state=unknown、value=null，其原因由clock_read_state及真实exception/clock事实核对；已证明的调用次数仍由reservation/call保留，不因整个vector unknown而改写为零。本票不增加或要求独立`hard_usage_unknown`正向分支；也不新增production usage API。可信正常返回时token/cost保持unknown必须仍走原actual结算，不能因此进入maximum。

- Collector只能被动观察实际边界、deep-copy并冻结收到/返回/抛出的值、上述原Clock读取和usage事实；不改变调用次数、timeout、返回对象、错误传播、state、route或control authority。不补读异常路径end，不将Host读取错误改记为callee exception；已有读数/读取状态缺失仍按source gap拒绝，旧raw不能凭空升级为0.7证据。
- `actual=null`由原replayer保持reserved maximum，全额消耗且不退款；tokens/cost继续原typed known/unknown，不等同hard usage，也不允许unknown转0。
- 新maximum分支不得要求存在没有实际发布的domain artifact：实际return即使因overrun被discard也须保留来源，但不冒充已注册成功结果。Finished output refs、真实注册成员、Host identity与原A03完整性继续exact；没有domain输出时复用原合法no-output合同，不能用假artifact补齐。

### 3. Source Proof Is Not Stop Authority

- 新声明证明原maximum record的来源，不授予结算、lease接管、effect重派发或closure权限。原invoke/close必须实际完成其fencing、heads、output、terminal ownership检查。
- 实际同步effect已退出、原owner/lease有效且原合同允许时，可在source meta driver中由原port完成maximum结算及原failed/terminal closure；这不是新增production recovery，也不证明远程provider或Backend stop。
- 未知effect状态、缺停止证据、stale/nonowner或未完成原publication时，保持原unsettled/recovery_required与最大费用，不制造settled/completed/failed/halted。Source formatter不能把这些分支改为成功收尾；重读/恢复来源只读取原证据，不执行effect。
- 至少验证真实exception closure及scoped LLM缺actual return的交接。LLM/tool resource kinds都覆盖；Code aggregate/verification继续原A05来源和owner，无新resource kind/ledger event/domain slot。

### 4. Human Protected Snapshot Locator and Authorization Sources

- 复用ordinary_members的closed declaration及原protected_snapshot_registered记录，不新增Human proof数组/profile或改runtime wire。注册必须属于已校验的同case/run，protected_kind=human_response、唯一member为payload.json、artifact_id与human_response_id对应，canonical_path exact为`human_responses/<response_id>/payload.json`。原提交operation/epoch/revision、发布阶段fencing、注册顺序、Human request/response owner及严格JSON/原bytes/SHA/size/snapshot关系继续校验，缺失、重复或foreign注册不得补造；证明原snapshot阶段已持久化不要求整个resume operation已completed/committed，未完成阶段保持原状态。
- Root只能来自既有可信Session与原producer绑定并经A05校验的该Run output_root，不能从待验证的payload_reference反推。原response locator仅接受上述canonical相对路径，或exact为该可信root拼接canonical_path的原绝对路径。先验证字面规范、root边界、各路径组件无symlink且为原regular file，再核对实际文件与已注册成员及declaration bytes/SHA/size；拒绝`..`、非canonical表达、其他root/Run/member及同内容不同文件。不得仅比较basename、仅以SHA相同认owner，或调用resolve后接受任意别名。
- 同一response的submitted/validated/consumed实际记录，必须保持原request/response IDs、原ledger locator一致性及snapshot SHA关系，已validated/consumed决策须与真实snapshot action一致；未发生的事件不要求存在，也不能补造。来源校验不使当前recovery_required前缀变成成功Human接续，不将snapshot注册等同validator通过、scope批准或Work执行。
- 在原bytes及关系校验之后，仅对已证明的`human_response.payload_reference`、实际`grant_issued.payload.response_reference`及其原grant source的response_reference作来源绑定投影：使用原Run identity、response ID、canonical member与snapshot source引用编码，不能将根路径直接丢弃或把字段排除。这些字段在producer/journal来源闭包中的重复位置须逐项证明与原记录同源后再绑定；未经证明的字符串仍material保留，不按字段名全局替换。跨fresh根的locator差异只在同一真实绑定成立时归一，response/member/bytes/owner/scope变化必须改变normalized或被拒绝。
- grant_source须核对原issued response_reference与原validated response的字面关联、同一已注册snapshot/source head、approve_budget_window决策、request scope、fingerprint/occurrence和原single-use关系。human_scope须核对实际consumed response、authorized target Attempt、action/target scope及同一snapshot；不得将“文件相同”替代消费/授权证明。两处复用同一经校验的locator绑定，不能继续以注册相对路径与原绝对引用直接比较。
- 两fresh根正向必须由原resume实际提交protected snapshot，以该真实前缀经过0.7完整normalize；0.6使用原proof0.3保留human_owner拒绝。无需先修B04 Human validator：实际resume仍recovery_required时完整保留该状态和原记录，不宣称继续成功。Grant/remediation关联函数可用绑定该真实snapshot的closed contract-only正负meta检验，但不得手填human_snapshots缓存绕过locator入口；合成的授权链必须标记contract_only，不冒充原端口实际dispatch或计B04 runtime。实际来源trace中的grant/消费只能来自原真实事件，不存在时不得注入；完整产品issuance/consumption仍由B04验收。
- Collector只读取原成员、注册与ledger，来源重读不得重新resume、调用Agent/effect、issued grant或消费Human response。需要先实施B04产品能力、修改production路径表示/Phase A、改写ledger或修改旧golden才能通过来源正向时停止。

### 5. Fixed Evidence, Consumers and Compatibility

- 用原production ports组合source meta；仅注入原允许的effect/structured outcomes、FakeClock及上述被动port wrapper、failpoint和C10四模块Host identity fixture。Wrapper仅记录原读取，不产生新时钟行为或增加fixture patch权限。Human来源使用原resume已提交的snapshot前缀，不依赖尚未完成的B04 Code parent、Human validator/后续Resume成功或stop功能，不patch graph/selector/state/allocator或第二套authority。
- 两fresh根独立产生raw/normalized、同stable scenario allocator序列和固定expected。Expected只离线审定，新0.7expected只写b00c11目录，旧0.6反例及所有旧goldens保持。
- 原exception maximum反例：0.7应接受完整真实证据，0.6仍拒绝`exception_settlement`。两版本各使用其closed proof；不能把0.4proof直接交0.6后因schema mismatch而冒充语义兼容验证。
- Collector/pytest envelope、matrix observation/expected、runtime case validator、exit semantic digest共用同一normalize/compare新分支；每条分别覆盖真实maximum与Human snapshot来源正向、missing/tampered/foreign source和stale Session/token/digest反例。合成consumer hook仅用于隔离meta，不加入production registry或B04 bindings，不交付B05 adapter。
- 合法异常message、实际return/domain内容、measurement、usage unknown事实变化须影响normalized并使fixed exact comparison失败；foreign/missing/duplicate/伪造来源严格拒绝。所有新material字段参与语义，不扩大ephemeral/exclusion。
- 不新增requirement ID/owner或修改case分类：131 required、84 mapped/47 remaining、case0.4共2199（B02 1410/B03 645/B04 144）、324 boundaries、28 post-claim与15 exits保持；global passed=null、phase_b_complete=false。

### 6. B04 Continuation Handoff

C11全部验收completed后，保存冻结B04正文摘要、fresh来源交接证据及入口复核；必须分别确认ordinary maximum和Human snapshot locator/授权来源关联两项缺口解除且没有新的Stop Condition，才按原授权仅更新B04 lifecycle为ready。Creating/review/ready C11均不足以恢复B04；只通过maximum或合同级grant测试也不足以恢复。即使C11 source meta通过，B04下列production问题也不能标为已修复：

1. Human validator output/approval registration、physical `human_approval_gate`与canonical `human_gate`衔接；原resume验证/消费后由新的advance进入Coordinator，普通审批不得附加真正terminal stop sequence。
2. Agent content与Host顶层identity/status隔离；高风险/critical、ambiguous及approval需要不能被后续low/unique结果覆盖。通过原17-edge和bounded global summary处理，禁止的Work须在schedule/clear/side effect前拒绝，accepted不得变化。
3. Ordinary exception/overrun在原authority下完成typed failed/recovery/stop；不能自动退款、重执行或把maximum等同停止证明。其新来源遵守本票closed contract，实际修复另记B04 maintenance。
4. 原B03 Code parent/Fake接入、四层fallback、fresh Analysis、failure fingerprint/second exact occurrence、Human scope/action/snapshot、single-use grant、terminal reserve及interrupt/recovery。
5. B04完整47 construction、18 boundaries下144 owned runtime、前置/current full suite及exact trajectories；B05仍独立负责退出验收。

上述责任全部保留原B04 Scope/Allowed Files；新票不预授权改变产品架构/schema/authority/risk policy。若后续修复需要扩大这些边界，再按原Stop Conditions独立审定。

## Deliverables

- 新显式trace/proof、closed maximum声明/measurement来源与DAG关系、被动collector及新版本consumer接线；
- Human protected snapshot严格locator校验/来源绑定投影、grant与consumed remediation的关联检查及actual-source/contract-only边界；
- source meta正负测试、新fixtures/固定expected、双fresh raw/normalized及逐字段审定记录；
- 独立C11来源合同与实际completion，包含command/results、Session/token/digests、effect次数、兼容/冻结/范围审计和B04未完成清单；
- 全部fresh前置/同Session runtime/全仓结果，以及本项解除后B04仅lifecycle恢复的交接记录。

## Acceptance Criteria

- 两fresh根的真实`exception -> maximum settlement -> failed closure`完整来源通过0.7，0.6保留原拒绝；无实际clock违规时reason=callee_exception、clock_read_state=callee_raised_before_end、end_at=null、hard_usage=unknown/null、actual outcome为null，effect调用exact一次、原close_run committed、最大费用不退款。读取记录证明原end未执行且collector没有补读。
- 实际返回后overrun验证returned/complete及真实outcome；实际epoch变化或clock回退验证clock_untrusted。异常同时发生实际epoch变化的反例验证clock优先且exception/outcome=null完整保留；不能仅因end_at=null误归clock_untrusted。原读失败若用于正向maximum证据，必须另有实际原读取失败记录，不用漏采伪造。
- Hard usage未知在真实exception及clock不可信场景中作为material属性验证；正常可信返回即使tokens/cost unknown仍使用原actual settlement。无实际原因的maximum、仅因audit unknown触发maximum、unknown转零、缺失/伪造clock_read_state或把未执行读取改成read_failed均拒绝；不要求不存在的独立usage-unknown路径。
- 正常actual/structured failure、真实unsettled及无法安全收尾分支继续覆盖；至少覆盖llm_call/tool_call和scoped LLM maximum，无假domain artifact或实际return替换。
- 原capability/publisher/heads/Run/Attempt与settlement exactly-once通过；篡改bytes、wrong owner/epoch/revision/resource、duplicate/orphan declaration、伪造return/停止、missing observation、stale Session均拒绝。
- 两fresh根各由原resume提交真实Human snapshot，原绝对locator与注册相对member实际同文件/bytes/SHA/size/snapshot；0.7完整normalize通过且两根一致，0.6保留human_owner拒绝，proof版本分别合法。实际recovery_required状态保持，重读不再resume/调用effect/消费响应，不把该正向计入B04 Human路径通过。
- Human missing/duplicate注册或member、foreign root/Run/response/member、同内容不同路径、path traversal/symlink、bytes/SHA/size/snapshot篡改及stale Session拒绝。合法snapshot内容变化须改变normalized；root变化仅在同一有效source binding成立时归一，不新增ephemeral/exclusion。
- 以真实snapshot locator入口结果检验grant_source/human_scope：合法来源关联通过，foreign request/response/snapshot/target/action、缺validated/consumed证明、错误scope/fingerprint/occurrence及重复grant消费拒绝。合同级meta与实际事件明确分开，不直接预填snapshot缓存代替来源校验，不宣称B04 grant或Work执行成功。
- 四消费路径通过新版本正负/session检查；双根normalized一致，合法material变化造成exact失败；旧版本测试、old normalized/goldens和sealed bytes不变。
- Fresh B00/B01/B02/B03 construction分别15/11/30/28；当前同一fresh输入Session按C04有界分批独立验证B02 1410与B03 645及完整suite（含legacy），保留exact nodeid/hook/outcome/case集合，不拼接历史输入或Session。
- Protocol/generator、compileall、links、metadata、scope、stale docs及diff检查通过；final负向探针仍exact47 coverage/144 binding/15 adapter缺口，无额外错误，不声称全局runtime或B04通过。
- 本票completed只证明来源交接；B04其余问题仍待原票修复，B05 draft及phase_b_complete=false保持。没有production、Phase A、owner/case/old format、依赖或外部系统变化。

## Verification

以下为本票另行批准ready后的实施验收，创建review票据时不运行不存在的新测试或声称这些结果已通过：

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b00c11_ordinary_maximum.py tests/phase_b/test_b00c11_human_snapshot.py tests/phase_b/test_b00c11_trace_consumers.py
pytest -q tests/phase_b/test_b00c10_ordinary_trace.py tests/phase_b/test_b00c10_host_identity.py tests/phase_b/test_b00c10_trace_consumers.py tests/phase_b/test_b04_trace_boundary.py
python -m compileall -q src tests scripts
git diff --check
```

Fresh证据根固定使用新`/private/tmp/lqcd-agent-b00c11-*`。按原`validate_phase_b_acceptance.py --mode construction --ticket B00|B01|B02|B03 --evidence-dir <fresh-dir> --report <report>`分别核验15/11/30/28，final入口作exact47/144/15负向检查。B02/B03 owned及完整pytest使用原Session、collect_roots、run_pytest_batches和独立validators在同一固定输入完成；不能用普通pytest或静态binding数量替代owned验收。保存0.6/0.7两版本语义反例、双根、actual call/原Clock逐次读取与state/usage属性、original closure/unavailable、allocation序列及全仓实际总数；独立核对原读取次数、未执行end与实际读失败的区别，以及三项reason的真实可达性。

Human证据另保存原resume result、committed snapshot注册、submitted ledger与operation/owner关系、可信Run root、原locator/member及实际bytes/SHA/size/snapshot的核对结果；保留0.6语义拒绝、双根0.7来源投影、四消费者及path/owner/scope负例。Grant/remediation报告注明actual-source或contract-only及work_dispatched状态，不能混入144 owned结果；本票不修产品Human/Grant流程。

创建及review修订阶段只核对模板/YAML、依赖与纠偏目标、local links、Allowed Files/Stop Conditions、分类/观测的一致性、冻结正文/历史前缀与diff；不创建C11 completion/source-contract实现记录，不提升ready，不实施harness或production，不commit/push。

## Stop Conditions

- 需要修改production、Phase A、旧trace/proof语义、sealed input/golden、case/owner/required/exit集合或扩大Allowed Files；
- 要虚构callee return、Host measurement、settlement/停止/closure，或靠重跑effect、跳过source、放宽exact/exclusion通过；
- Human locator需要任意路径别名、从待验证引用反推root、按字段名去根、改变原ledger/production路径表示、跳过真实snapshot入口或补造validated/consumed/grant/dispatch才能通过；
- 需要补读异常路径的end、以其他阶段的Clock读数替代resource measurement、patch生产Clock、用source gap伪造clock不可信，或新增usage端口/编造独立usage-unknown路径才能验收；
- 原maximum/owner/stop行为无法用已存在production ports证明，需要本票实现B04 recovery/Human/Code/grant或新增runtime evidence/schema/authority；
- 无法区分maximum accounting与安全停止，或要把unavailable/stale writer伪装成合法终态；
- 正向meta必须依赖未完成的B04产品能力或test-only graph/selector/state patch；
- 旧golden发生非派生/行为差异、原语义被新版本影响，或当前前置/全仓回归无法在本票范围内保持；
- 无法完成双fresh根、material sensitivity、四消费者及同Session独立集合核验。

任一条件触发时本票blocked，B04继续blocked；不能通过维护记录扩范围或把未验证边界留给B05。

## Required Documentation Updates

创建及review修订时在Overview、docs入口、纠偏索引、Current State及B04 completion同步待审范围/责任边界；保留历史条目，只更新当前摘要与追加新事实。0.7/0.4及Human locator校正此时是待审设计，不是当前可用格式；不改C10合同/完成历史或B04冻结正文。

批准实施后，独立C11合同列出version/profile字段、raw/checksum/DAG/owner算法、measurement/unknown、Human locator/授权关联和stop边界；completion记录actual changed files、verification、冻结摘要、无commit状态、两项来源缺口分别解除的B04恢复依据及未修复事项。同步受影响source-of-truth和REPO_CURRENT_STATE，新增test-owned来源版本生效时向DECISION_LOG追加决定，不声称production控制合同变化。完成stale-documentation scan，仅修正本票造成过时的当前说明，不改历史内容。
