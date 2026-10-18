---
ticket_id: B00C10
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C06, B00C07, B00C08, B04]
---

# B04 普通资源调用的来源轨迹交接

## Goal

为 B04 ordinary LLM/tool reservation 与 settlement 提供可验证的 source-bound semantic trace。新增显式版本，不改变 trace 0.1–0.5、proof 0.1/0.2 或既有 sealed evidence 的解释。完成只解除 B04 的 B00 来源类型阻塞，不代替 B04 的产品图、47 项 construction、144 项独立 runtime 或 B05 验收。

`depends_on: B04` 表示纠偏目标，不要求已 blocked 的 B04 先完成。本票为待审方案，只有用户明确批准并提升为 `ready` 才能实施。

2026-10-01修订补齐identity fixture、来源闭包、异常分类、mixed入口和接续修复边界；状态仍为`review`。当前blocked票是B04，B03已completed。本票不把B04的Human、资源收尾或Agent字段隔离缺陷转移为B00实施职责；具体反例及接续检查见[B04接续审查](../corrections/B04_CONTINUATION_READINESS_REVIEW.md)。

## Why

真实 `run_canonical_graph -> compiled StateGraph -> InvocationLeases -> run_resource` 的 no-code 路径已经完成 `completed`，并持久化三项合法 `llm_call` reservation/settlement。用现有 ControlTrace 0.5 收集完整 execution/artifact/checkpoint authority 后，B00 normalization 报 `invalid_evidence:a05_reference:missing_source`。加入 Agent 实际收到的 scoped context 和实际返回的成功结果的 exact canonical preimages 后，错误变为 `invalid_evidence:a05_reference:kind`，不能靠补齐 collector 修复。

原因是 `harness/a05_trace.py` 对普通 `resource_settled.payload.evidence_digest` 仍只接受 `external_final | verification | failure_evidence | failure_identity | interrupt_evidence`。ordinary 成功结果属于 `canonical_json`，不属于这些 A05 profile；把它伪装成 verification 或 failure evidence 会改变证据含义。

可复现反例：[test_b04_trace_boundary.py](../../../tests/phase_b/test_b04_trace_boundary.py)。两个 fresh 根分别运行同一 production 产品入口，仅注入 structured outcomes 和 FakeClock，分别保存 `counterexample-trace.json` 与 `counterexample-summary.json`。初始完整 preimage 反例位于 `/private/tmp/lqcd-agent-b04-trace-preimages-4s2qjafr/trace-complete-resource-preimages.json`。这些是阻塞证明，不是 B04 owned case 通过证据。

B04 明确禁止修改 B00 validator、旧 normalizer 语义和 trace exclusions；故不能用 B04 maintenance 扩大来源类型或跳过 ordinary budget records。

## Read First

- `AGENTS.md`、`docs/README.md`、ticket workflow、verification guide；
- A01/A03/A05/A06/A07 和 frozen protocol/catalog；
- B00C06/C07/C08、冻结 B04 及 B04 completion/maintenance；
- `harness/{trace,trace_proof,a05_trace,inputs,report}.py`、`helpers/control_traces.py`；
- B04 ordinary resource journal、compiled product graph、上述反例及两根原始 bytes。
- `helpers/canonical_code.py`、B03真实prestart/dispatch/consume/Analysis fixtures；
- [B04接续审查](../corrections/B04_CONTINUATION_READINESS_REVIEW.md)、A07 exact identity/ephemeral合同及B04仅四类fixture注入边界。

## Scope

- 增加显式 `trace 0.6 / proof 0.3` 来源派生版本，复用并保留全部 0.5 A05 验证；
- 增加 ordinary resource 的 request/outcome source profile 与 ledger/owner/identity 绑定，不新增 runtime budget event 或 resource kind；
- 为 B04 scoped context、structured diagnosis、remediation packet 及它们的 registered ordinary domain members 明确来源投影，仅处理会影响 mixed canonical Code/ordinary trajectory 的现有引用；
- 在 B04 collector/bindings 中接入新版本，独立审定两根固定轨迹并验证旧版本兼容。
- 仅对新ordinary/mixed来源测试及后续B04 exact轨迹，增加下述Host identity fixture例外；不增加identity exclusion或production分配接口。

## Non-goals

- 不实现或完成 B04 route、Human、grant、stop、Code parent 或 47/144 验收；不交付 B05 adapter；
- 不改变 Phase A bytes、wire schema、A02 identity、A03 slots/invalidation、A04 operation phases、A05 trust、A06 limits/charging 或 case classification；
- 不增加 wildcard digest normalization，不删 evidence，不扩大 ephemeral exclusions；
- 不 commit/push/PR、调用真实 provider/Backend/network 或修改 raw/accepted/outputs。

## Requirements

1. 新版本必须显式选择；旧版本不得自动升级、改变 source kind union 或重新解释 arbitrary hex。0.5 对本票 ordinary success 反例的原拒绝行为保持。
2. Ordinary request profile 绑定真实 `resource_reserved` record、resource kind/operation ID、Run/Attempt、input/config digests、原 invocation capability、producer ControlOperation 及原 reservation 前 head。结果 profile 绑定同一 reservation 与唯一 settlement、实际返回 bytes/digest、exact publisher operation/epoch/revision及原actual/maximum计费语义；未结算分支按下述异常分类处理。
3. 只接受 `llm_call | tool_call` ordinary 分支；Code aggregate 和 verification 保持原 A05 profile。不得把普通结果标为 A05 failure、verification 或 Backend evidence，不得让 source proof 提供 runtime authority。
4. Collector 从真实 invocation/resource boundary 取得 preimages；不能按 digest 猜对象、调用另一条 Run、重跑 Agent 或用测试构造的 replacement result 填证据。来源缺失/篡改、foreign owner、重复 settlement、wrong resource kind仍严格拒绝；真实未结算prefix与source gap不得混淆，不发明成功settlement。
5. Scoped context、diagnosis 和 remediation 只能绑定现有 registered members、直接父 Attempt、Coordinator 选定的 evidence、原 budget policy、原 Human snapshot。已验证的 namespace、路径、member size 与内容摘要可以派生；问题、风险、candidate、constraints、success criteria、usage 和科学内容保持 material。无新 public domain slot 或 schema。
6. Ordinary domain member source 使用 exact registered pointer 与实际 canonical bytes；Host identity必须与原ledger逐字段相等且保留字面值，仅允许已证明的物理路径/size/hash派生。不能删除identity或把整个Agent payload当ephemeral；role/member超出下述闭合范围的输入拒绝。
7. Failure fingerprint、grant与stop-sequence按下述来源闭包验证；缺少实际生产路径时可使用明确标记的contract-level meta fixture验证现有算法和引用，不声称runtime authority已交付。真实证据缺source必须拒绝，不能为通过验收虚构record、settlement或Human授权。
8. fixed expected 只离线建立：保存 old/new raw、标准化差异、字段来源与两个 fresh 根独立结果；runtime 不按 actual 重写 expected。前置 goldens仅允许原批准的 fingerprint/derived-head 更新，不改变 owner/outcome/invariant。
9. B00 required IDs仍131；case0.4仍2199、B02/B03/B04仍1410/645/144、boundaries324、post-claim28；不修改 slice ownership、required checks、dispositions、B04正文或 B05。

### Host Identity Fixture Handoff

- 两fresh根使用同一stable scenario ID及各自从零开始的allocator。仅在测试context manager内替换`control.interfaces.uuid`、`control.coordinator.uuid`、`control.children.uuid`、`code_agent.external_operation.uuid`四个模块的UUID提供对象；不得修改共享`uuid.uuid4`、LangGraph/checkpointer、Backend或provider的全局随机源。
- `uuid4()`值固定派生为`uuid.UUID(bytes=SHA256(canonical_bytes({"scenario_id": scenario_id, "allocation_site": module_name, "ordinal": n})).digest()[:16], version=4)`，`n`从1连续增加。不同scenario/site/ordinal不得复用；在每个fresh测试结束及异常退出时恢复原模块对象。只有原Host分配函数调用此提供对象，原ID前缀、Run/local counters、reservation、CAS、capability和validator继续执行。
- Clock仍使用已有FakeClock；不得替换identity分配函数、返回已预制operation/capability、修改state/ledger/route/budget，或从actual生成expected。重启进程必须延续该scenario已消费的allocator序号，不能从1重置造成身份复用；仅测试exact replay、不发生新分配的子进程无需安装allocator。
- 原始Run/ControlOperation/ExternalOperation/capability身份及其关系均保留在exact trace，不投影成常量或ephemeral。foreign/duplicate identity负例必须仍失败。
- **治理例外仅此一项**：本票批准并完成后，B04冻结正文中四类fixture注入之外，允许上述Host identity fixture用于B04新exact来源轨迹；不回写B04正文，不扩展其他patch权限。旧B00–B03 helper和sealed evidence不因本例外而改写。

### Closed Source Profiles and Collection

Proof0.3新增的ordinary declaration必须closed-schema、带显式profile与version；调用方不能指定忽略字段、受信任alias或任意投影算法。独立合同逐项列出字段路径、bytes/checksum算法、source kind、owner关系和依赖顺序。下表是必须交付的闭包，不允许仅实现success outcome引用。

| Profile | Exact source及绑定 | 必须保留的材料 |
| --- | --- | --- |
| ordinary request | 原reservation record/head、reservation前execution/artifact heads、resource ID/kind、原capability授权及producer operation的冻结owner/epoch/revision；实际input/config canonical bytes分别重算原digests | timeout、maximum charge、limits/remaining、policy、配置与输入内容 |
| ordinary outcome | 调用实际返回值的canonical bytes；原reservation及唯一settlement/evidence digest；实际publisher operation/epoch/revision | structured status/error、stdout/stderr/returncode、domain/science内容、actual、tokens/cost及unknown discriminator |
| scoped context | 原invocation identity、scheduled input refs、直接父Attempt、exact注册member preimages、root goal、bounded history与replayed budget summary | goal、选定证据、相关历史、policy/counters、scope，不接受完整audit作为prompt |
| diagnostic / remediation | actual Agent诊断与Host最终registered诊断分别绑定；packet绑定原Coordinator member、目标/父Attempt、policy、选定证据与nullable Human授权 | problem/risk/confidence/retryability/candidates、constraints/success criteria、科学内容 |
| ordinary member | exact A03 registration/pointer、logical/canonical path、size、raw member SHA；JSON Host identity与producing ledger逐字段相等 | Agent content及其科学字段；不把任意嵌套identity/path/hex当可排除值 |
| fingerprint / grant / stop | 下述现有算法与已冻结record/来源preimage，owner关系通过原validator | causal context、failure class/code、occurrence、授权范围、usage、reason、single-use与stop限制 |

Input/config/outcome的摘要为原`SHA256(canonical_bytes(actual_value))`，JSON必须严格parse并重序列化byte-equal；仅primitive meta的实际scalar input/config允许scalar，其余role payload按闭合结构验证。A03 member使用实际文件raw SHA和size；自描述checksum仅按原字段排除算法验证，不能与raw member SHA互换。Proof ownership declaration是独立校验关系，不嵌入actual input/outcome preimage制造自引用；先核对原ledger/owner，再按真实依赖DAG投影，orphan/cycle/duplicate source拒绝。

Ordinary member允许范围闭合为：Planner的`method_plan.json`/`method_planner_diagnostic.json`；Analysis的`run_result.json`/`analysis_outputs/result.json`/`analysis_engineer_diagnostic.json`；Reviewer的`scientific_review_report.json`/`scientific_reviewer_diagnostic.json`；Coordinator的`decision_log.json`/`decision_coordinator_diagnostic.json`；Human的`approval_packet/request.json`与原Human response snapshot；Memory的`memory_update.json`/`final_report.md`。Code成员继续原A05 profile。文件名相同不足以授权，slot/kind/producing Attempt/registration必须全部匹配。

JSON成员只对Host写入的顶层identity、明确的state-path字段和已注册evidence引用建立关系；identity保留原值。`analysis_outputs/result.json`的domain payload、其他Agent嵌套字段和report正文保持material。Markdown/report按exact bytes证明，不做字符串替换；同名foreign Run或越路径成员拒绝。

Collector为实际Agent port及实际tool/effect delegate增加被动wrapper：记录收到的input与实际返回值，在返回给Host前deep-copy并冻结canonical bytes；异常仅保存真实观察，不构造返回值。不得改变调用次数、超时参数、返回对象、错误传播或control authority。测试collector观察不是新的runtime journal/schema。

Config使用实际调用前的Host配置preimage：LLM为production节点当次使用的`{"node": node, "structured_output": true}`；fresh Analysis tool为原`runtime_policy_digest`所引用的实际policy。Primitive meta fixture可显式传入其实际input/config bytes。所有preimage必须重算匹配当次reservation；不能从最终artifact、digest字典或另一Run倒推。Capture保存`before-effect input/config -> original reservation -> actual return/exception -> original settlement或真实未结算prefix`的链，重启审查只读取此链，不重跑side effect。

### Ordinary Failure and Uncertainty Classification

| 真实分支 | 本票验证结果 | 禁止声称 |
| --- | --- | --- |
| 返回success或structured domain failure，原ledger已settled | 验证actual返回bytes、唯一settlement及原actual或已存在的maximum disposition；unknown tokens/cost仍为unknown | domain failed等于provider异常，或unknown等于0 |
| side effect异常、进程退出、clock/overrun拒绝，原ledger未settled | 验证request/owner及实际持久化prefix，budget replay保留maximum、无退款/redispatch；exact轨迹记录uncertain/unsettled事实 | settled/completed、已证明未执行，或已完成B04 recovery/closure |
| ledger声称已settled，却缺actual返回/可信maximum evidence preimage | source gap，严格拒绝 | 通过构造replacement result补齐成功 |
| forged/duplicate/foreign settlement或不可信usage | 严格拒绝原证据 | collector获得结算或恢复authority |

当前ordinary overrun无法完成收尾是B04待修缺陷；C10只对其真实prefix建立来源证明，不改变Run状态或补发settlement。尚无生产maximum settlement的分支以原production builder/validator的contract-level fixture验证算法，不能当作runtime正向证据。

### Mixed Evidence and Derived References

- C10的mixed正向是**来源meta验收**：在同一个fresh Run内调用原B02/InvocationLeases ordinary资源入口及原B03 prestart、Fake dispatch、可信consume、canonical Bundle/fresh Analysis ports，收集实际records和preimages。可以新增专用test driver组合现有ports，不能拼接两Run、导入历史Run、伪造已提交Code Bundle或编写第二套authority。此driver不接管或代替B04 production routing。
- Mixed不得要求尚未实现的B04 `code_host`、Human rerun或完整四层fallback先成功；它也不计B04 positive edge/47/144通过证据。现有B03 helper若必须扩展，新增driver复用其底层ports，不改旧fixture/expected行为。另以真实compiled no-code产品入口验证完整ordinary来源。
- Fingerprint从原`fingerprint()/validate_fingerprint()`及其actual causal context/diagnostic preimages闭合；grant从原`grant_issued/grant_consumed`、受保护的Human snapshot、exact response digest/scope/target/occurrence及原single-use验证闭合。没有实际grant生产路径的新增fixture明确标contract-level，仅证明格式/引用算法；不写B04 runtime binding。
- Stop sequence只在原Transition确有该字段时建立来源：原Run/source Attempt与同一来源diagnostic category，或原`budget_stop` reason的canonical preimage，重算当前Host算法并验证相关Transition/decision。不得把所有Human审批都判成terminal stop，不让来源proof授予Work dispatch权限。B04后续须区分普通审批与真正terminal reserve；若接续改变已审定算法，必须重新核对来源合同，不静默改expected。
- 已知前置golden为`a05_normal/timeout/failed/unavailable`和`b03_repeat_code`；当前两根normalized一致，旧raw能重建现有expected，差异为`application_build`、`graph_topology`及派生heads/references。保存五份旧/新raw及字段diff，按原fingerprint-only授权逐项审定后同步；其他前置golden仍逐份检查，不能推断全部仅此五份。合法材料变化应改变normalized并使fixed exact comparison失败；不要求normalizer拒绝所有合法的新材料。

### Execution Order and B04 Continuation

1. 冻结并检查新版本/profile/identity例外范围；保留0.5反例；记录当前已知失败与B04冻结摘要。
2. 先完成ordinary LLM/tool返回、structured failure、unknown usage、真实未结算prefix和negative闭包，再完成compiled no-code及同Run B03 mixed来源；四条消费路径共用同一normalizer并验证session/exact约束。
3. 完成离线双根golden审定、fresh construction和当前同Session B02/B03/full regression，明确已发现的B04缺陷仍待修。
4. C10全部验收通过并completed后，B04依原授权恢复执行：先修Human validator artifact/physical-node衔接/普通授权与terminal sequence隔离、ordinary overrun/uncertain收尾、Agent保留字段隔离；修复和验证另记B04 maintenance/completion，再完成其余Code/fallback/fingerprint/grant/47/144。

第4步不属于C10 Deliverables，不以记录待办冒充代码已修复。上述三项局部修复按B04原Scope/Allowed Files执行；若实际方案改变schema/authority/public contract或验收边界，仍依AGENTS另建纠偏，不由本票预授权。

## Allowed Files

- 本票 ready 后仅 YAML lifecycle；B04仅 YAML lifecycle，完成纠偏且复核后恢复其原授权执行；
- `tests/phase_b/harness/{trace,trace_proof,a05_trace,inputs}.py`仅新版本dispatch、来源校验及version-gated投影接线；新增`ordinary_trace.py`。旧分支语义保持，不能全局扩大A05 union。`matrix.py`、`pytest_evidence.py`、`failpoints.py`、`exit_checks.py`仅在共用normalize/compare确需版本接线时调整，不改session、owner、selection、exact、report、exit或case判定；
- `tests/phase_b/helpers/control_traces.py`、新增`ordinary_sources.py`/`host_identity_fixture.py`/`ordinary_mixed.py`；`test_b04_trace_boundary.py`保留0.5反例；新增`test_b00c10_ordinary_trace.py`、`test_b00c10_host_identity.py`、`test_b00c10_trace_consumers.py`。被动port wrapper和identity provider仅限上述范围，不改旧helpers；
- 新profile/schema定义仅在`ordinary_trace.py`及新合同中，若使用独立JSON schema仅新增`tests/phase_b/fixtures/b00c10/{trace_0_6,proof_0_3}.schema.json`；新meta fixtures仅`fixtures/b00c10/`，不覆盖旧sealed inputs；
- `tests/phase_b/acceptance_matrix.json`：仅追加原 B00 owner 的 meta 场景，不重分配 requirement；B04 bindings 仅版本交接，不提前填未执行144项；
- 新`expected_traces/b00c10/`，以及受影响的既有source-bound expected仅经上述离线审定；不改旧trace版本或非派生event材料；
- 新`docs/tickets/completions/B00C10_COMPLETION.md`和`docs/tickets/corrections/B00C10_ORDINARY_RESOURCE_TRACE_CONTRACT.md`；`completions/README.md`、`corrections/README.md`仅追加对应索引/关闭事实，B04 completion仅追加交接事实；
- `README.md`、`docs/{README,REPO_CURRENT_STATE,ARCHITECTURE,DECISION_LOG,EVALS_AND_OBSERVABILITY,VERIFICATION_GUIDE}.md`及Phase B Overview：仅同步当前source版本/fixture例外/生命周期/已验证结果的摘要及追加交接事实；有日期的历史正文不改写，不扩展CLI、runtime或架构合同。

## Do Not Touch

所有production `src/`、Phase A frozen files、B00–B05正文、旧completion/correction历史、旧trace/proof/schema/seals、case/requirement ownership、exit check清单、legacy测试、依赖配置、Git publication与外部系统。Allowed Files明确的旧harness文件只允许新增版本接线、既有expected只允许获准派生同步，不允许修改旧格式实现语义或放宽校验；B04 completion仅追加交接事实。

## Deliverables

- 新的严格source proof版本、closed derivation表、被动collector与Host identity fixture；ordinary/mixed正负来源、异常分类及四条消费路径测试；
- 两 fresh 根 raw/normalized diff、固定 trace、兼容和前置验收报告；
- 独立合同、completion及B04恢复依据，未完成项明确保留。

## Acceptance Criteria

- 真实ordinary LLM/tool success、已settled structured failure及unknown usage严格验证；实际unsettled/overrun prefix按maximum与uncertain事实验证，不计settled/completed。Missing settled-source等负例严格拒绝；原0.5反例保持原拒绝；
- 真实compiled no-code与同Run原B03 ports的mixed来源meta通过同一新版本，不跳过ordinary记录、不依赖未实现B04 parent、不冒充B04 route/runtime通过；
- Collector证明实际input/config/return冻结在正确边界，Host后续添加diagnostic evidence或Analysis execution不会替换原返回preimage；重启只读捕获证据，不发生新调用；
- Host identity fixture在两fresh根得到同一allocation序列；不同scenario/site/ordinal可区分，异常退出恢复模块对象，未使用process-global UUID patch；完整identity值/owner关系保留，foreign/duplicate仍拒绝；
- 篡改request/outcome bytes、wrong owner/Attempt/epoch/head、伪装profile、缺失preimage、duplicate settlement、foreign packet/evidence/Human snapshot及Agent覆盖Host identity均严格失败。保持来源合法的risk/problem/usage/science变化必须改变normalized并使固定expected exact比较失败；
- 两fresh根在明确物理派生和相同Host identity fixture下normalized相等；member size/hash不是简单删除，raw字节和原算法先验证；
- Collector、matrix expected/observation、runtime case validator及exit semantic digest均调用同一新版本投影，四条路径有正负/session binding检查；不交付B05 adapter，不修改exit清单；
- fresh B00/B01/B02/B03 construction为15/11/30/28；B02 1410与B03 645在同一当前输入Session回归通过；完整pytest、compileall、协议生成、冻结字节、链接、scope和diff checks通过；
- mapped仍84/131、remaining47，B04仍未完成；本票仅解除source evidence和对应fixture前置，B04三项已复现缺陷及47/144不得标已修复/已通过。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b04_trace_boundary.py tests/phase_b/test_b00c10_ordinary_trace.py tests/phase_b/test_b00c10_host_identity.py tests/phase_b/test_b00c10_trace_consumers.py
pytest -q tests/phase_b
pytest -q
python -m compileall -q src tests scripts
git diff --check
```

所有新证据保存在fresh `/private/tmp/lqcd-agent-b00c10-*`，按现行C04同Session有界分批规则验证B02 1410/B03 645及完整pytest，逐项保留passing nodeid、production hook、原outcome与fixed exact trace；不得拼接不同输入/Session。记录0.5反例、两根新raw/normalized、allocator序列、原call次数、contract-only与runtime证据区分、五份已知golden及其他前置逐字段审定、B04冻结body摘要。只有实际交付这些检查才可completed，不以反例通过或B04局部产品测试替代。

## Stop Conditions

- 需要改变 production runtime/wire schema、Phase A bytes、旧格式语义、frozen case、requirement/check/owner或扩大Allowed Files；
- 缺少真实 preimage/owner 链，或要虚构 outcome、重跑 side effect、扩大 exclusion 才能归一化；
- 需要重新设计 B04 packet、budget/grant/stop或科学权限；
- 无法以两个fresh根及 material sensitivity证明派生边界。
- 必须依赖未实现的B04 Code parent/Human/stop才能完成本票mixed来源meta，或必须patch route/state/生产allocator函数才能得到exact fixture；
- 前置golden差异超出源码fingerprint/可证明派生heads，或需要把B04未修缺陷计作成功才能通过全量验收。

## Required Documentation Updates

批准后冻结正文，实施结果另记。完成时追加新版本合同、identity fixture窄例外及其恢复依据，明确B04三项接续缺陷、其余原票义务和B05未完成，不回写任何冻结历史。不以本次review修订宣称新版本、fixture例外或代码修复已经生效。
