---
ticket_id: B00C12
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C10, B00C11]
---

# C11 剩余来源阻塞与完整验收交接

## Goal

在显式`trace 0.7 / proof 0.4`中关闭当前已确认的C11全部来源阻塞并完成其剩余验收：原Human请求packet的严格来源绑定、真实Host exception receipt支持、maximum/Human正式matrix接线，以及C11全部来源正负/四消费者、当前Session前置与完整suite。完成本票时，不得把上述来源修复或验收留给C11继续补做。

2026-10-01，用户同意创建请求packet补充纠偏票；2026-10-02，用户要求扩大本票，使其关闭本轮确认的C11全部剩余阻塞。本票保持`review`，修订不代表批准ready或实施。B00与B00C10须已completed；`depends_on: B00C11`表示被纠偏的冻结执行票，C11已批准、实施局部候选但blocked，不要求其先completed。本票不形成等待C11完成的执行前置，不批准B04产品修复。

本票补充[C11 Requirement 4](B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_HANDOFF.md#4-human-protected-snapshot-locator-and-authorization-sources)的限定packet投影，并落实C11已允许但候选尚未支持的Host receipt分支；不重定义maximum原因、计费、停止或授权语义。保留C11冻结正文及其独立完成责任，以逐项证据表核验C11全部Requirements/Acceptance Criteria。C12完成后只需完成C11原授权下的独立证据复核和生命周期/记录交接；C12 completed本身不自动等于C11 completed，也不足以直接恢复B04 ready。未知的新合同缺口仍触发Stop Conditions，不能承诺未审查场景永不阻塞。

## Why

[C11执行记录](../completions/B00C11_COMPLETION.md)确认：两个原compiled canonical graph分别进入Human Pause，再由原resume提交真实protected response snapshot；各自完整0.7 normalize通过，但双根exact失败。

最早差异为normalized事件下标72的`human_request:packet_written`，对应原execution ledger `event_index=31`。其`packet_reference`分别为原可信Run根下的绝对路径`attempts/attempt_000004/approval_packet/request.json`；该字段未在C11限定的response/grant locator投影中，仍作为material影响execution及后继source heads。原文件已由`attempt_000004:approval`注册，唯一request member bytes/SHA/size可核对；不是新Human response snapshot或新的artifact slot。

实际请求的`requesting_attempt_id=attempt_000003`，发布packet的是独立Human Gate `attempt_000004`。二者不可合并。原packet发布来自Invocation completion；不能错误地要求请求文件出现在resume的`control_publications`表，或把后来的response snapshot发布阶段当作请求packet的producer。必须读取原capability、completion intent及真实artifact/ledger关系。

原失败证据为`/private/tmp/lqcd-agent-b00c11-execution-anf2gxmb/stop-condition.json`及其双根raw/normalized和pytest失败记录。该证据只定位问题，实施验收必须fresh重建。C11局部148项通过及maximum四消费专项1项通过不替代本项或C11全量验收。

2026-10-02独立审查再次确认：唯一未绑定的根路径字面值位于原packet_written，后继差异由该来源沿DAG传播；另有含真实异常的Host receipt经原端口完成maximum结算与failed closure，effect一次，0.7却拒绝`maximum_actual_error`。当前`B00C11-MAXIMUM`/`B00C11-HUMAN`也未登记正式matrix，前者交原matrix observation validator报`observation:identity`。专项为2 passed/2 failed，Human双根及缺expected仍失败。见`/private/tmp/lqcd-agent-b00c12-review-bc45v3j0/{facts,projection-audit,review-audit}.json`和`focused-pytest.txt`；这些是定位证据，不能代替本票fresh验收。全仓分批的validate_pytest不要求全局matrix登记，故登记缺口属于本票须补齐的来源验收责任，不伪称原全仓必然因此失败。

## Read First

- [AGENTS.md](../../../AGENTS.md)、[docs入口](../../README.md)、[ticket工作流](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)和[验证指南](../../VERIFICATION_GUIDE.md)；
- [C11冻结票](B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_HANDOFF.md)、[实际执行记录](../completions/B00C11_COMPLETION.md)、[B04冻结票](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)及[最新记录](../completions/B04_COMPLETION.md)；
- [C10来源合同](../corrections/B00C10_ORDINARY_RESOURCE_TRACE_CONTRACT.md)及[完成记录](../completions/B00C10_COMPLETION.md)，[A03](../phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md)、[A04](../phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)、[A07](../phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)、[Control Protocol 0.4](../phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)及[需求目录](../phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)；
- `tests/phase_b/harness/{ordinary_maximum_trace,ordinary_trace,a05_trace,trace,inputs,matrix,pytest_evidence,failpoints,exit_checks,session}.py`、`helpers/{ordinary_maximum,ordinary_human,ordinary_sources,control_traces}.py`及C11候选测试；
- 只读`src/lqcd_agent/control/{capabilities,coordinator,execution,pause}.py`、`artifacts/registry.py`及`graph/nodes.py`，核对原Human Gate request member、Invocation publication、request/response身份和实际recovery_required；
- B00C04及B02/B03完成记录的fresh Session、有界分批和独立owned集合核验机制。

## Scope

- 在现有0.7/0.4候选中新增请求packet来源校验及限定字段投影，不增加版本或proof顶层数组/profile；
- 复用原ordinary_members、artifact/ledger sources、可信Run root、原SQLite capability/producer/completion intent和既有A05 DAG；
- 被动采集实际请求packet及原producer/journal中可证明的重复位置，双fresh完整Human来源、固定expected、敏感性、严格拒绝与四消费者验收；
- 支持原Host在真实callee异常收尾时写入的closed receipt，保留直接异常原分支与maximum分类、unknown、authority和closure合同；
- 补齐Human expected引用、maximum/Human/receipt正式B00 final meta与四消费者接线，完成C11所有冻结来源验收和同一当前输入Session回归；
- 独立来源合同、completion、C11逐项验收证据表及无剩余来源阻塞的完成交接。

## Non-goals

- 不实现Human validator输出/approval注册、physical node接续、普通审批/terminal区分、grant产品发行或Work dispatch，不修改B04 graph/guard/Code/fallback/recovery；
- 不改production/wire、原ledger路径表示、artifact成员或slot、budget算法、风险policy、authority或原closure；
- 不自动升级旧raw/proof，不增加ephemeral/exclusion、任意路径别名、按字段名去根、字符串替换或基于同SHA的owner合并；
- 不将请求packet、response snapshot、validated或consumed证明相互替代；不把合法来源变成成功Human续执行；
- 不commit/push/PR/deploy、访问真实provider/Backend/network、repository outputs/raw/accepted、secrets或新增依赖。

## Allowed Files

- 本票ready后只改YAML lifecycle。C11仅在本票completed且逐项复核其全部冻结验收和所有来源Stop解除后，按原授权更新YAML lifecycle，完成ready/in_progress/completed交接，不改正文；不能先completed再补验收。本票不允许更新B04为ready；C11 completed后B04入口复核和恢复由原C11授权单独记录。
- `tests/phase_b/harness/ordinary_maximum_trace.py`：仅0.7请求packet来源绑定、closed exception receipt核验及C11冻结来源要求内的局部缺陷修复；`ordinary_trace.py`仅必要的显式新版本接口，不改变0.6及以下；`a05_trace.py`、`trace.py`仅共用DAG传递经核验绑定所需的version-gated接线，不扩大旧kind union、通用path/exclusion范围。
- `tests/phase_b/helpers/{ordinary_maximum,ordinary_human,ordinary_sources,control_traces}.py`：仅原ports来源meta、真实Host exception receipt收尾场景、被动采集及原publication材料；不更改默认0.6、fixture patch权限、effect次数或实际结果，不patch生产端口。
- 新`tests/phase_b/test_b00c12_human_request_packet.py`、`test_b00c12_maximum_host_receipt.py`、`test_b00c12_trace_consumers.py`、`fixtures/b00c12/`与`expected_traces/b00c12/`。正式matrix所需closed fixture写新b00c12目录，不覆盖已有b00c11定位材料。
- `tests/phase_b/test_b00c11_ordinary_maximum.py`、`test_b00c11_human_snapshot.py`、`test_b00c11_trace_consumers.py`：仅本票来源接线及C11冻结范围内的验收补齐；Human接入`expected_traces/b00c12/human.json`，maximum保留原固定expected，receipt另用新expected。原observe ID、断言/Session/exact边界不得跳过或降级。
- `tests/phase_b/acceptance_matrix.json`仅追加原B00 `A07-META-006`/`A07-META-015`下的final maximum、Human packet/snapshot和Host receipt来源meta；不改原场景、owner/case、required refs或B04 binding。`harness/{inputs,matrix,pytest_evidence,failpoints,exit_checks}.py`仅共用normalize/compare确需的0.7接线，不改selection/report/session/runtime/exit判定。
- 新`docs/tickets/corrections/B00C12_HUMAN_REQUEST_PACKET_TRACE_CONTRACT.md`与`completions/B00C12_COMPLETION.md`，只在批准实施后记录实际合同/结果；两目录README只追加。
- 新`docs/tickets/corrections/B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_CONTRACT.md`：只在C11/C12全部来源验收和逐项复核实际完成后交付C11基础合同，并明确引用C12的packet/receipt补充，不能提前声称新版本生效。
- `docs/tickets/completions/{B00C11,B04}_COMPLETION.md`只追加交接事实；`docs/tickets/phase-b-graph-harness/OVERVIEW.md`、`docs/README.md`、`docs/REPO_CURRENT_STATE.md`仅必要当前摘要/入口；生效后`README.md`、`docs/{ARCHITECTURE,VERIFICATION_GUIDE,EVALS_AND_OBSERVABILITY,DECISION_LOG}.md`仅本票造成的合同/状态与决定同步。

## Do Not Touch

所有`src/`、Phase A、冻结C11/B04/C10及其他ready/completed ticket正文、C10合同/完成历史、旧sealed evidence/fixtures/expected（含已存在的C11 maximum expected）、原registry/case/disposition/owner/required/exit集合、`tests/test_*.py`、依赖/config/evaluation、真实数据、outputs/accepted/Human decision、secrets、外部系统及Git publication。旧helper/harness仅允许新版本分支。Maximum的原因分类、计费、停止和authority语义保持；本票只落实已批准的exception receipt、原C11来源校验与剩余验收，不增加新maximum理由/usage API或receipt profile。发现本票packet/receipt补充及C11冻结要求之外的独立合同缺口须停止另行审定。

## Requirements

### 1. Version and Correction Boundary

- 请求packet绑定和Host exception receipt核验仅选中`trace 0.7 / proof 0.4`；复用现有closed declaration/source envelope与ordinary_members，不新增版本、proof字段/profile或production/wire schema，不把旧raw按0.7解释。
- 本票批准实施后，仅在C11 Requirement 4的限定集合中增加原`human_request.packet_reference`及其经逐项核验的同源重复位置。Response/grant snapshot既有规则全部保持，未知字段/字符串继续material；不把`packet_reference`加入通用RUN_PATH_FIELDS或按名称自动处理任意对象。
- 原trace0.1–0.6、proof0.1–0.3的接受/拒绝及normalized结果保持。合法trace0.6/proof0.3的exception maximum与Human response snapshot反例分别仍拒绝`exception_settlement`/`human_owner`，不得用proof schema mismatch代替语义兼容检查。

### 2. Original Request, Gate, Registration and Publication

- 从已验证的同case/run原ledger定位唯一`human_request.created`及实际`packet_written`。请求ID、cycle、request_index、requesting_attempt_id、scope/action等原字段持续一致，原创建与发布顺序正确；若只存在created/null locator而尚未发布packet，不要求未来文件或补造packet_written。
- 分别证明requesting Attempt和发布Gate Attempt。发布者必须是原同Run/cycle的Human Gate、实际scheduled/started/completion关系，原route/parent/request association符合原合同；不得拿requesting_attempt_id直接拼发布路径或假定两者相同。物理human_approval_gate与canonical human_gate按既有合同核对，不重新定义topology。
- 定位该Gate实际`registered`的approval artifact与唯一`logical_name=approval_packet/request.json`成员，pointer/owner/slot与注册记录一致；canonical member exact为`attempts/<producer_attempt_id>/approval_packet/request.json`。原member严格JSON内容须exact为同request的原created record，不能把后继packet_written整条记录或response snapshot当作请求文档。
- 原registration绑定的execution head/事件顺序、packet_written的artifact head/index、Gate completion及original publication必须相符。通过可信Run root下只读原SQLite记录核对该Gate的capability授权、producer operation/epoch/result revision、原invocation epoch/worker及持久化completion intent的artifact/ledger publication、published状态与原真实记录/字节。不凭本票declaration、同hash或新meta断言认owner；不要求该Run后来resume/所有后继operation已完成。
- 请求packet来自原Invocation publication；response snapshot来自原resume prestart publication。分别核验，不能强求前者存在后者的control_publications条目或挪用其fencing。关联需要原系统不存在的新authority或producer schema时停止。
- registration、packet_written或成员缺失/重复/foreign、publisher/epoch/revision不符、非原created bytes、declared content/实际文件不一致一律拒绝；合法未发布前缀保留原状态。

### 3. Exact Locator and Source DAG

- Root仅取可信Session与原owner绑定、既有A05已验证的Run output_root；不能从packet_reference反推。原端口packet引用须exact为该root拼上述canonical member的原绝对路径；不新增相对wire许可。
- 校验字面规范、root/Attempt/member边界、各路径组件无symlink、原regular file及真实bytes/SHA/size与注册/ordinary_members内容相等。拒绝`..`、`.`别名、额外分隔符、其他Run/Attempt/member、同内容不同文件或仅basename/SHA匹配；不能resolve后接受任意别名。
- 仅完成上述核验后，将已证明的packet_reference编码为带case/run、request ID、独立producer Attempt、canonical member及原member source引用的绑定；所需原publisher身份/fencing依既有source关系持续material。使用既有source heads传播语义，checksum/raw bytes先校验，再执行来源绑定；注册、记录、后继heads均保持完整DAG，不增加任意digest alias。
- 在原producer/journal、projection/checkpoint及其他来源闭包中的重复request记录，必须逐项证明与原已验证记录同源，再传递同一绑定。未知对象中同名字段及任意文本仍material；不做全文搜索替换或去根。若材料是序列化来源，须沿既有strict解析、原字节及source head关系处理，不能重新序列化原publication以适配expected。
- request ID/owner、producer Attempt、member、bytes、scope/action或材料变化须改变normalized或被拒绝；不同fresh根只在同一真实source binding成立时归一。

### 4. Passive Capture, Actual Prefix and Compatibility

- 使用C11既有原compiled canonical graph及原resume来源driver、原allowed structured outcomes/FakeClock和C10 Host identity fixture；collector仅读取/冻结实际材料，不patch graph/selector/生产Clock、不改effect/Agent次数、timeout、返回、异常、state/route或authority。
- 两fresh根均实际发布原请求packet并由原resume提交response snapshot，完成整条0.7 normalize和fixed exact。实际resume仍recovery_required时保留此事实；允许已有真实validated记录，不能要求其不存在，也不能补造consumed/Grant/Work来通过。
- 来源重读/consumer验证不得再次运行graph、resume、Agent/effect、发布或消费Human响应；另一个fresh根必须独立执行原scenario，不以复制第一根目录充数。
- fixed expected只离线审定并写新b00c12目录，保存两根raw/normalized及allocator序列、原bytes/owner/publisher关系审计；不得在测试运行中从actual生成expected，不修改旧golden。
- 原created/packet未发布前缀、C11 maximum/scoped/unsettled与grant/remediation合同级关联均保持。合同级授权meta只能复用真实snapshot locator入口，标明contract_only、work_dispatched=false、B04_owned=false，不注入原实际来源trace。

### 5. Actual Host Exception Receipt

- 落实C11 Requirement 2已经允许的真实Host receipt。直接异常evidence的原closed `{type,message}`分支保留；新增receipt content闭合为`{schema_version,resource_operation_id,exception}`，version=0.1，exception闭合为实际callee的`{type,message}`。这只是既有`maximum_evidence.content`内的test-owned来源变体，不新增source profile、declaration字段或原settlement payload字段。未知/额外receipt字段和其他shape严格拒绝，不按任意嵌套字段搜索异常。
- Receipt必须由原来源meta中持有实际authority的Host收尾分支，在观察到真实callee异常后按真实reservation的resource ID生成canonical bytes，并经原`ArtifactEffectPort.append_budget`提交`actual=null`和该receipt的evidence_digest；collector仅冻结当次实际提交的同一bytes，不能在采集/normalize阶段把直接异常包装成receipt或改写ledger。不同fresh场景可以选择直接异常或receipt收尾，callee/Clock/effect/closure行为与原场景保持，禁止patch生产端口。
- 原source SHA/canonical bytes、settlement evidence_digest、唯一reservation/settlement、Run/Attempt/capability、producer operation/epoch/revision及Host有效authority逐项核对。Receipt的resource_operation_id须exact等于原reservation/settlement；exception须exact等于实际ordinary call.exception，实际call_disposition=raised、outcome=null、未执行end读取等观测继续按C11检查。Host receipt不是Agent返回值，不能填入outcome或制造返回/停止证明。
- Receipt只承载真实callee异常。存在实际epoch变化等已证明clock违规时仍按C11的`clock_untrusted -> duration_overrun -> callee_exception`优先级分类，不因receipt改变原因；没有异常的return、overrun或end读取失败不能伪造此exception receipt。原overrun/clock的Host error直接来源、typed unknown、hard usage及计费/closure规则不变。
- 两fresh根分别由原ports复现真实exception→receipt maximum settlement→failed closure，完整0.7 normalize与新固定expected通过，effect每根exact一次；覆盖llm_call/tool_call及scoped LLM无返回/无domain artifact情形。原直接异常轨迹仍与既有C11 maximum expected exact；合法0.6/proof0.3分别拒绝两种真实maximum轨迹的exception_settlement。
- Missing/tampered receipt、异常/resource不匹配、foreign owner/producer、wrong epoch/revision、duplicate settlement、extra字段、伪造return/stop和stale Session拒绝；重算outer hash或声明SHA不得绕过原ledger/producer来源。Receipt全部内容参与normalized语义，合法实际异常message变化影响normalized/exact；重读不重执行effect或重新结算。

### 6. Formal Matrix and Four Consumers

- Collector/pytest envelope、matrix observation/expected、runtime case validator及exit semantic digest共用同一0.7 normalize/compare。每条分别验证真实直接异常maximum、Host exception receipt maximum、Human packet+response snapshot的正向、missing/tampered/foreign source及stale Session/token/每个digest反例；outer artifact hash重算后仍须拒绝，不能只验证坏checksum。原C11 isolated测试保留，并补齐其未覆盖边界。
- 正式`acceptance_matrix.json`至少登记现有实际observe ID `B00C11-MAXIMUM`、`B00C11-HUMAN`及新`B00C12-MAXIMUM-HOST-RECEIPT`，各自精确绑定真正执行并observe该ID的nodeid。使用原B00 owner、A07-META-006/A07-META-015与validation_stage=final，不新增requirement/owner；expected分别为原C11 maximum、新b00c12 human及新b00c12 receipt。所需matrix fixture按原closed schema写入b00c12；既有b00c11/maximum.json定位材料不能直接当作合格matrix fixture，也不得覆盖。
- 通过原validate_matrix/selected_scenarios核验字段、fixture/entrypoint/exact/nodeid关联；在当前固定输入Session实际执行来源meta，使用完整正式matrix的all_scenarios调用原validate_observations，验证观察ID和expected，不过滤未知observation、不虚构临时known集合。隔离合成matrix通过不能替代这项正式接线验收。
- synthetic hook仅用于隔离meta四消费者，不能进production registry或B04 case bindings；新增来源meta不计B04 owned runtime，不交付B05 adapter。

### 7. Complete C11 Evidence and Continuation

- 本票实施阶段须核验C11冻结Requirements 1–6及每条Acceptance Criteria，形成逐项表，列出实际command/nodeid、fresh根、Session/token/digests、raw/normalized/fixed expected和结果。分别标明原标准、本票明确的packet/receipt/新expected补充及完成后生命周期门禁；Requirement 6须交付来源解除与B04入口复核/责任交接依据，C11 completed之后的B04恢复动作仍另行记录，不能在本票内预称已发生，也不形成等待B04 ready的验收循环。明确actual-source与contract_only的不同证据角色；不得以packet专项、receipt专项、局部pass或静态inventory替代其他项。
- 完成原直接异常/actual/overrun/clock/unknown/scoped/unsettled/unsafe来源、全部owner/duplicate/伪造/兼容/敏感性、Human双fresh及grant_source/human_scope合同级关联、三类来源的四消费者和正式matrix。原callee异常未执行end、实际clock优先、无实际原因maximum拒绝和正常返回token/cost unknown走actual等要求全部保持；原读失败若用作正向必须来自实际读取失败，不能漏采伪造。
- 完成fresh construction15/11/30/28；在同一当前固定输入fresh Session按原C04机制完成来源meta、B02 1410/B03 645独立owned及完整repository suite，保留exact nodeid/hook/outcome/case集合。完成protocol/generator、compileall、metadata/links、scope/冻结/历史/stale docs检查以及final exact47 coverage/144 binding/15 adapter负向入口；没有额外错误。历史C10/C11证据不替代当前验收。
- 保持131 required、84 mapped、47 remaining、2199 cases（B02 1410/B03 645/B04 144）、324 boundaries、28 post-claim、15 exit IDs及原owner集合；global passed=null、phase_b_complete=false，B05仍draft。
- C12自身completed门禁为本票全部标准和C11逐项表全部通过、已知来源阻塞逐项解除且无新Stop；不允许将Host receipt、maximum/Human正式matrix、Human expected/四消费者或当前输入回归留给C11补做。若仍需来源代码、fixture、expected、matrix或合同修订，本票继续in_progress或按Stop blocked，不能先交付再修。
- 在同一固定输入验收阶段完成上述C11逐项复核，准备独立C11完成依据；C12实际completed后，按C11原授权恢复ready/in_progress并仅作独立证据复核与完成记录/lifecycle交接，全部满足才completed，不产生第二轮实现或补验收计划。事实收尾注明验收时manifest与验收后lifecycle/记录追加；不能在输入变动后重读旧Session并伪称新输入通过。若收尾又改变source/expected/matrix/合同或需新的执行验收，必须重新固定输入并完成所需当前验证，不能拼接旧Session。
- C11未completed之前B04保持blocked；C11 completed后仍须独立复核原B04入口，才按原C11授权恢复B04 ready。Human validator/approval注册、physical-node接续、普通审批与terminal sequence、Host字段隔离、高风险/歧义guard、ordinary实际收尾及Code/fallback/fresh Analysis/fingerprint/grant和47/144仍归原B04，不作为本票来源正向的前置，不标为已修复。

## Deliverables

- 新版本请求packet的owner/root/member/publication校验、限定来源绑定与既有DAG接线；
- Closed Host exception receipt来源支持、原maximum语义保持及正式maximum/Human/receipt matrix接线；
- 专用actual-source正负测试、固定expected及双fresh逐字段审定证据、四消费者/session反例、C11完整逐项验收证据表和当前Session回归；
- C11基础来源合同、C12补充合同及独立真实completion，列出commands/results、Session/token/digests、source/effect次数、冻结/scope/旧版本审计、全部已知来源阻塞解除与C11完成交接依据；
- 同步状态/索引和C11/B04追加交接记录，不产生虚假的产品完成或B05交付。

## Acceptance Criteria

- 两fresh根由原graph/ports各自发布request packet及resume snapshot，完整0.7 normalized一致、固定expected exact通过、allocator序列一致；原requesting Attempt与packet producer分别核验，实际recovery_required及全部原事件保留。
- 原请求created/null locator的未发布前缀合法，实际packet_written后缺registration/member/原publication拒绝。重复/foreign request、producer/Run/Attempt/member、wrong epoch/revision、missing/tampered来源、path alias/traversal/symlink、同内容不同文件、bytes/SHA/size/严格JSON变更或假publisher全部拒绝。
- 原合法scope/action/成员内容变化影响normalized并使exact不匹配；unknown对象同名路径未获绑定而仍material。Root差异仅在合法owner/source binding下归一，未新增ephemeral/exclusion。
- 原bytes/SHA先核验、闭包重复位置同源逐项检查、DAG完整且无orphan/cycle/任意digest alias；重读不重新Agent/effect/resume/consume。
- Closed receipt经真实Host原端口实际提交；resource/exception/bytes/SHA/evidence_digest/owner/fencing逐项匹配，两fresh根exception→receipt maximum→failed closure及fixed exact通过，effect每根一次、outcome=null；llm/tool/scoped、clock优先及真实unsettled/unsafe保持。Receipt缺失/篡改/foreign/extra字段/错误resource或异常/重复结算/伪造返回或停止/stale均拒绝；原直接异常maximum expected不变，两种0.6语义拒绝保持。
- 四消费路径分别对直接异常maximum、receipt maximum及Human packet/snapshot的真实正向和missing/tampered/foreign/stale token/每个digest反例通过；meta不计B04 owned runtime。
- 正式matrix及新closed fixtures通过原validator，原B00/既有refs/final身份与真实observe nodeid/expected对应；B00C11-MAXIMUM、B00C11-HUMAN及B00C12-MAXIMUM-HOST-RECEIPT均由当前Session实际产生并经原validate_observations核验，无unknown/duplicate/missing observation，不靠过滤或隔离matrix代替。
- C11新专用suite（含先前失败的Human双根与Human消费者）、C12 suite及C10/B04来源边界通过；原0.6两种语义拒绝和所有旧golden/fixtures/seals字节保持。
- C11冻结Requirements 1–6及全部Acceptance Criteria在本票内形成逐项全部通过的证据表，包括原maximum全部分类/unknown/closure、Human/grant/human_scope、兼容/敏感性/四消费者和文档交接；没有留给C11的来源修复或待跑验收。完成后lifecycle门禁按Requirement 7单列交接依据，不预执行B04恢复或把其ready作为C12完成前置。
- fresh construction B00/B01/B02/B03 **15/11/30/28**；同一当前固定输入fresh Session按C04有界分批独立核验正式来源meta、B02 **1410**、B03 **645**及完整repository suite（含legacy），保存exact nodeid/hook/outcome/case集合。所有C11要求实际核验，不拼接历史输入/Session；验收后事实/lifecycle追加与冻结manifest分别记录，不把之后的docs/source变化称为旧Session已验证的新输入。报告实际完整总数，B04仍0/144。
- Protocol/generator、compileall、metadata/local links、冻结历史/scope/stale docs/diff检查通过；final负向仍exact **47 coverage/144 runtime binding/15 adapter**，无额外错误，不声称全局通过。
- C12 completed记录packet、receipt、正式matrix及C11完整验收的解除依据；按原授权只接续C11独立证据复核与生命周期/完成交接，不留下补实现/补验收项。C11 completed和B04入口复核之前B04继续blocked、B05 draft；B04原产品未完成清单真实保留。新格式未完全验收前不得更新成正式交付合同。

## Verification

以下为本票另行获准ready后的实施验收；创建review票据时不运行尚不存在的新测试、不实施新绑定或宣称当前通过：

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b00c12_human_request_packet.py tests/phase_b/test_b00c12_maximum_host_receipt.py tests/phase_b/test_b00c12_trace_consumers.py
pytest -q tests/phase_b/test_b00c11_ordinary_maximum.py tests/phase_b/test_b00c11_human_snapshot.py tests/phase_b/test_b00c11_trace_consumers.py
pytest -q tests/phase_b/test_b00c10_ordinary_trace.py tests/phase_b/test_b00c10_host_identity.py tests/phase_b/test_b00c10_trace_consumers.py tests/phase_b/test_b04_trace_boundary.py
python -m compileall -q src tests scripts
git diff --check
```

使用新`/private/tmp/lqcd-agent-b00c12-*`根，保存actual raw/normalized、request/packet注册与capability/producer/completion证据、原requesting与producer身份区别、成员bytes/SHA/size、原resume result；保存真实Host receipt实际提交bytes与原settlement evidence_digest及每根effect次数。直接异常、receipt、Human分别双fresh，离线固定expected，旧C11失败/审查根只作定位，不复用其Session/token为新验收。

使用原`validate_phase_b_acceptance.py --mode construction --ticket B00|B01|B02|B03 --evidence-dir <fresh-dir> --report <report>`核验15/11/30/28；final作exact47/144/15负向检查。正式来源meta、B02/B03 owned及全仓使用原Session、collect_roots、run_pytest_batches和独立validators在同一固定输入完成；来源meta以正式matrix运行原validate_observations，owned按原registry/specs运行validate_runtime，不以普通pytest计数或静态bindings替代。Session开始后不改inputs；C11逐项表和全部验收在本阶段完成，之后只作明确的事实/lifecycle交接，不沿用旧Session声称变更后输入通过。

创建阶段只检查模板/YAML、依赖、链接、scope、冻结正文/原history前缀与新增diff。新票review、C11/B04 blocked；不创建C12实施completion/生效合同，不commit/push。

## Stop Conditions

- 需要改production、Phase A、旧trace/proof/expected/seals、case/owner/required/exit集合、预算或authority，或扩大Allowed Files；
- 不能由原requesting/Gate/capability/completion/registration/ledger证明source owner，需要新runtime evidence/schema或把resume发布阶段当成packet producer；
- 需要按字段名或文本去根、依同SHA/basename接受其他文件、反推可信root、允许任意别名、跳过bytes/注册/原publication或扩大通用路径投影；
- 需要重派发effect/resume、补造Human validated/consumed/Grant/Work、修改真实状态或先实施B04产品能力才能完成来源正向；
- 发现本票packet/closed exception receipt补充及C11冻结来源要求之外的独立合同缺口，需要新绑定字段/格式/profile/receipt shape或重新定义maximum/计费/停止/授权语义；
- 必须修改旧golden或无法保持旧接受/拒绝、metadata/冻结/history、前置/全仓回归；
- 在本票范围/既有合同内无法完成三类来源双fresh exact、material sensitivity、正式matrix、四消费者及同Session独立集合验证，或必须将C11逐项表的未通过/待修/待验项留给C11补做。

任一条件触发时本票blocked，C11和B04继续blocked；不得把未验证边界留给C11/B05或靠maintenance扩范围。C12创建/review/ready均不足以恢复C11或B04。

## Required Documentation Updates

创建/待审修订时在Overview、docs入口、纠偏索引、Current State及C11/B04 completion同步本票覆盖packet/receipt/matrix及C11全部剩余验收的范围和交接门禁；保留已有历史前缀及所有冻结正文。C12当前是补充设计，不是生效来源合同；不新建实施completion或变更原runtime事实。

批准实施后独立C12合同记录请求packet限定字段/owner/root/member/raw、实际publisher/fencing、DAG重复绑定，以及closed receipt的真实Host生成/提交/采集边界、字段关联、material和旧版本拒绝；C11基础合同与其补充引用一并核验。Completion记录实际结果、当前Session、逐项C11证据表及所有已知来源阻塞解除；C11 completion只追加独立完成依据及冻结正文摘要，不重写历史。更新受影响source-of-truth和Current State；全部验收生效后向Decision Log追加只涉及test-owned来源合同的决定。完成stale-documentation/TODO scan，不声称B04 Human/guard/ordinary/Code或47/144产品能力已交付。
