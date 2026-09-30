# 第二阶段文档索引

## 目的

本目录是 `v0.2-demo` 之后第二阶段开发的文档入口。它区分当前系统合同、未来方向、具体执行 ticket 和历史记录，避免旧计划、当前事实和未来设想互相混淆。

第二阶段文档以中文解释为主；代码标识、类型名、schema 字段、命令和代码块保持英文。代码注释继续遵守根目录 `AGENTS.md` 的全英文规则。

## 权威顺序

发生冲突时按以下顺序处理：

1. [`AGENTS.md`](../AGENTS.md)：仓库级行为与编码规则；
2. `status: ready` 的 ticket：本次任务的目标和允许范围；
3. 核心 source-of-truth 文档：当前系统合同；
4. [`DECISION_LOG.md`](DECISION_LOG.md)：架构和政策选择的理由；
5. [`REPO_CURRENT_STATE.md`](REPO_CURRENT_STATE.md)：代码实际实现状态；
6. Phase Overview 与方向文档：尚未全部落实的阶段目标；
7. milestone：冻结版本的历史事实。

Ready ticket 不能静默覆盖 `AGENTS.md`、安全策略或当前 public contract。出现冲突时必须停止并先形成明确的设计决定和合同更新。

## 核心 Source of Truth

- [`PROJECT_SPEC.md`](PROJECT_SPEC.md)：项目目标、当前基线、第二阶段目标和持续非目标；
- [`ARCHITECTURE.md`](ARCHITECTURE.md)：当前实际图结构、运行边界和已知缺口；
- [`AGENT_ROLES_AND_BOUNDARIES.md`](AGENT_ROLES_AND_BOUNDARIES.md)：Agent 当前职责和不可突破的边界；
- [`STATE_SCHEMA.md`](STATE_SCHEMA.md)：当前真实 `AnalysisState` 合同；
- [`ARTIFACT_CONTRACTS.md`](ARTIFACT_CONTRACTS.md)：当前运行 artifacts 的结构合同；
- [`SECURITY_AND_DATA_POLICY.md`](SECURITY_AND_DATA_POLICY.md)：数据、命令、secrets、provider 和审批策略；
- [`EVALS_AND_OBSERVABILITY.md`](EVALS_AND_OBSERVABILITY.md)：当前 benchmark、可观测性和下一阶段 eval 方向；
- [`VERIFICATION_GUIDE.md`](VERIFICATION_GUIDE.md)：当前验证入口和 ticket 完成检查；
- [`REPO_CURRENT_STATE.md`](REPO_CURRENT_STATE.md)：第二阶段实时状态；
- [`DECISION_LOG.md`](DECISION_LOG.md)：已确认设计决定。

核心文档同时区分当前runtime与已确认的目标合同。A02已完成Run/Cycle/Attempt/Transition/Human identity，A03已完成per-attempt artifact namespace、typed current index、compatibility projection和transition-time invalidation；四层fallback仍只是control harness evidence。A02C01已完成schema `0.4` bootstrap后继合同的治理同步，A04已完成Pause/Resume/Replay/Fork目标合同同步，A05已完成graph-managed Code Agent、replaceable backend、isolated workspace、trusted verification与fresh Analysis handoff目标合同同步，A06已完成immutable budget policy、admission/reservation、failure fingerprint、single-use grant、Pause deadline与fail-closed stop目标合同同步，A07已完成六层deterministic acceptance、exact trajectory、fault/concurrency、machine matrix与zero-gap exit目标合同同步；这些完成项都没有把相应目标能力接入当前schema `0.2` runtime。未来RAG设计也不能提前写成当前runtime能力。A02/A03冻结正文中的commit-order歧义使用独立correction records澄清，不回写历史ticket。

## 第二阶段方向与 Tickets

当前B00–B03、B00C01–B00C09、B02C01、B03C01及B03C02已完成。B03 construction **28/28**，同一fresh Session的B03 runtime **645/645**、B02 **1410/1410**通过；完整全仓 **3514 passed**（Phase B **3189 passed**）。累计mapped **84/131、remaining47**，Phase B整体未完成，B04/B05仍draft；默认产品runtime仍schema0.2。见[B03完成记录](tickets/completions/B03_COMPLETION.md)。

冻结机读合同为[Control Protocol 0.4](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)及[Phase B需求目录](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)；状态更新不得移除这两项权威引用。

- [`NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md`](NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md)：第二阶段三个改进方向和 A–E 阶段关系；
- [`tickets/README.md`](tickets/README.md)：ticket 生命周期、执行规则和目录说明；
- [`tickets/TEMPLATE.md`](tickets/TEMPLATE.md)：统一 ticket 合同。
- [`tickets/completions/README.md`](tickets/completions/README.md)：独立执行结果记录；
- [`tickets/corrections/README.md`](tickets/corrections/README.md)：maintenance与corrective历史记录。

Phase Overview 不是执行 prompt。只有经过用户确认并标记为 `status: ready` 的具体 ticket 才能执行；`ready`后ticket正文冻结，执行结果和后续纠偏不得回写原计划。

Phase A的A01–A07、A02C01及A03C01现均为`completed`。B03已`completed`，B04/B05仍`draft`。最终输入fresh construction **15/11/30/28**，B03 **645/645**及B02 **1410/1410**独立runtime在同一fresh Session通过；case0.4保持 **2199**（1410/645/144）与28个post-claim路径。全仓 **3514 passed**（Phase B **3189 passed**）；protocol/catalog及生成字节、legacy/A03、编译、链接、范围和冻结正文均核验。累计mapped **84/131、remaining47**，`requirements.passed=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。后续B04产品图与B05全阶段验收待交付。以下日期条目保留当时事实，以本段和B03完成记录最后条目为当前状态。

2026-09-16更新：[B00C01](tickets/phase-b-graph-harness/B00C01_SOURCE_BOUND_SEMANTIC_TRACES.md)与[B00C02](tickets/phase-b-graph-harness/B00C02_SEMANTIC_TRACE_EXIT_BINDING.md)均已completed。来源绑定的trace0.2及完整exit摘要接线通过验证，旧trace0.1不变；见[B00C02完成记录](tickets/completions/B00C02_COMPLETION.md)。B02前置阻塞解除后已恢复执行，剩余control runtime和30项验收仍须按原冻结票完成。

2026-09-17续执行已扩展B02的Recovery/Human、0.4 child、advance/close及部分external控制路径，修复启动fencing和bootstrap故障收尾；完整验收仍未完成。Legacy source fingerprint缺失表示待确认，新增实现与测试边界见[B02最新执行记录](tickets/completions/B02_COMPLETION.md#external-control-continuation--in-progress)，不要将较早的bootstrap-only记录当作当前全部能力，也不要将本次局部进展当作B02完成。

## Milestones

- [`milestones/V0_2_DEMO_BASELINE.md`](milestones/V0_2_DEMO_BASELINE.md)：第一阶段 `v0.2-demo` 冻结基线。

Milestone 文档只允许事实纠正，不随当前开发持续改写。可变状态只写入 `REPO_CURRENT_STATE.md`。

## 第一阶段历史资料

第一阶段的累计成果、验证基线、持续边界和已知限制已归档到 [`milestones/V0_2_DEMO_BASELINE.md`](milestones/V0_2_DEMO_BASELINE.md)。旧的单体 build plan、ticket ledger 和 prompt playbook 已在规则迁移及依赖审计通过后从当前工作树删除，不再参与第二阶段文档解析。

如需核对原始历史内容，可从 Git tag `v0.2-demo` 查看：

```bash
git show v0.2-demo:docs/CODEX_BUILD_PLAN.md
git show v0.2-demo:docs/TICKETS.md
git show v0.2-demo:docs/PROMPT_PLAYBOOK.md
```

2026-09-18后续：用户已批准[B02C01](tickets/phase-b-graph-harness/B02C01_LEGACY_SOURCE_FINGERPRINT.md)，真实0.2 source只读replay及source-only fingerprint缺失规则进入实施验证；见[执行记录](tickets/completions/B02C01_COMPLETION.md)。原B02其余控制分支、0.3兼容和完整验收仍未完成。

2026-09-18验证完成：B02C01已completed，真实0.2 source只读Replay及历史fingerprint缺失证明通过78项定向、833项全量测试；B00/B01 fresh construction仍15/15、11/11。原B02继续in_progress，coverage仍26/remaining105，不能将本次兼容修正当作整票完成。

2026-09-18后续执行：B02C01已完成，B02新增normal external consumption、原resume失败收尾、timeout完成、preparation与historical reader控制路径。历史0.3 Fork实际成功，但B00 trace 0.2不能验证其真实source head，故B02现为`blocked`，待审[B00C03](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)。coverage仍26/remaining105；执行事实和未完成范围见[B02 completion](tickets/completions/B02_COMPLETION.md)。

2026-09-21：[B00C03](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)已批准并完成。显式trace `0.3`验证原格式historical source、真实Fork reservation及0.4 child引用；旧0.1/0.2语义保持。源checkpoint完整main/WAL/SHM只读副本校验与逐文件不变测试通过。完整pytest **1063 passed**，Phase B **738项可收集**；fresh B00/B01仍15/15、11/11，mapped26/remaining105，final仅105/2286/15缺口。B02恢复原票执行，30项construction和205/1488 runtime bindings仍待完成；见[B00C03完成记录](tickets/completions/B00C03_COMPLETION.md)。这替代上述“B00C03待审批、B02因historical trace阻塞”的当前状态，不改写历史审查事实。

2026-09-21 reservation边界审查：B00C03已completed，其历史证明阻塞已解除；B02随后修复快照丢失卡住和合法grant replan被拒绝，两组回归101/45 passed。真实进程在首次reservation事务COMMIT前退出会完整回滚、没有可恢复的原operation；冻结B00 case笛卡尔展开却要求该边界产生原operation的materialization/domain-gap状态。六项复现及不可变重放对照通过，详见[B02记录](tickets/completions/B02_COMPLETION.md#2026-09-21--reservation-fault-case-executability-audit)。B02现为blocked，待审[B00C04](tickets/phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)，未实施该草案。当前mapped26/remaining105及原2286 runtime/15 exit缺口不变；此前“B02恢复执行”是发现此新缺口前的记录。

2026-09-21本轮验证完成：完整pytest **1086 passed**，Phase B可收集 **761项**；fresh B00/B01 **15/15、11/11**，final仅 **105 coverage / 2286 runtime / 15 exit** 缺口。冻结摘要、生成字节、scope及链接检查通过。B02因[B00C04](tickets/phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)待审仍blocked，详见[B02最终记录](tickets/completions/B02_COMPLETION.md#current-tree-final-verification-2026-09-21)。

## 2026-09-21 B00C04 integrated correction

B00C04已按用户明确批准扩充并进入in_progress：独立case语义0.2已将首次提交前故障改为真实reservation_rolled_back；现行独立case为2214（B02为1416），全部324 boundary及B03/B04 case保持。显式trace0.4补齐external Pause的资源预留来源引用，真实子进程回执与有界分批验证已实现，完整验证进行中。B02仍blocked，covered26/remaining105，无B02 slice。

2026-09-21 B00C04完成：case0.2、trace0.4、直接production进程回执及严格分批验证落地；旧1488个B02 case为1370 retained/118 replaced，现行B02 **1416**、总数 **2214**，全部324 boundary及B03/B04集合不变。完整pytest **1118 passed**、新增定向 **32 passed**，fresh B00/B01 **15/15、11/11**，coverage26/remaining105。Global passed null、phase_b_complete false。B02验收前置阻塞已解除，接续原票处理已审定的runtime缺陷及完整验收；本修正票不代表B02完成。证据见[B00C04完成记录](tickets/completions/B00C04_COMPLETION.md)。

2026-09-21 C04补充审查：Fork `child.source_revision_cas`在首次reservation提交前，两项独立进程反例均完整回滚。沿用原票已批准的全boundary审查范围补齐这一遗漏；C04重新in_progress，B02暂为blocked。旧1488个B02 case现为1362 retained/126 replaced，现行总数 **2208**、B02 **1410**，减少78均有提交前反例；324 boundary、B03/B04及28 post-claim保持。之前2214/1416及C04完成报告保留为当时验证事实。coverage仍26/105；尚无B02 slice。

2026-09-21 C04集成补验完成：完整pytest1158 passed，fresh B00/B01 15/15、11/11；C04现completed，B02继续in_progress。现行独立case2208/B02 1410，covered26/remaining105，尚无B02 slice；此前blocked及补验in_progress为历史过程。详见[B00C04完成记录](tickets/completions/B00C04_COMPLETION.md)。

2026-09-21 B02验收接线：C04已completed后，新增B02完整30项slice、5条完整来源轨迹及1410个独立runtime case绑定。初始reservation的两项C04进程反例作为并列必需final证据保留，没有移除旧正负检查；历史trace回归只隔离其B00/B01前置slice，完整matrix另行验证。现行映射56/131、remaining75；B02仍in_progress，正执行fresh验收，不能将接线或离线通过当作完成。全局final规则未改变，其他票据798个runtime binding及15项exit仍未交付。

2026-09-24 B00C05续执行：用户批准补齐审阅建议并执行，ready冻结于`52c508b`；真实初始producer入口与case0.3修正已实现，70项定向检查通过，完整集成验证尚未完成。工作树独立集合为2199/B03 645，前置B02 1410、B04 144及28 post-claim保持；B03仍blocked，不能把此项修正计为canonical Backend完成。此前2208/654/798计数为case0.2冻结基线。

2026-09-24 B00C05完成：B00C05已完成并解除B03首次ExternalOperation reservation分类阻塞：真实初始producer与case0.3已验证，独立集合2199（B02 1410、B03 645、B04 144），324 boundaries和28 post-claim不变。Fresh B00/B01/B02为15/11/30，完整2617 passed、同Session B02-owned 1410/1410；mapped56/remaining75，final仅75 coverage / 789 runtime binding / 15 exit，global passed=null、Phase B未完成。B03恢复ready，canonical Backend与其28项验收仍待交付。

2026-09-24 B03接续审查：B00C05已completed并提交为`7af288c`；真实B02 Code target/C05 producer及A05/A06 contract-shaped数据反例确认trace0.4存在派生摘要投影缺口，B03现blocked，待审B00C06。反例不计canonical Backend验收；case0.3、2199/645及mapped56/remaining75不变。详见B03执行记录最后条目。

2026-09-24 B00C06：用户批准补强、冻结提交并执行，ready commit `cd29d9f`。显式 trace 0.5 / proof 0.2 及 A05 全链 contract/meta 证据正在集成验证，旧 trace、旧 goldens、src、case0.3 不变。B03 暂保持 blocked；通过后仅解除来源轨迹前置，预算事务和状态投影兼容仍须独立核验。

2026-09-24 B00C06完成：trace0.5/proof0.2 全链来源与四条验收路径通过，2677 passed、同 Session B02 runtime1410/1410，fresh B00/B01/B02为15/11/30；mapped56/remaining75，final仅75/789/15。旧trace、旧goldens、src、case0.3保持。B03来源阻塞已解除，但接续实证确认A05空字段投影超出原fingerprint-only golden授权，因该独立边界继续blocked，待窄范围补充审阅。

2026-09-24：已形成待审 [B00C07 状态投影与 golden 窄范围补充](tickets/phase-b-graph-harness/B00C07_A05_STATE_PROJECTION_GOLDEN_HANDOFF.md)。该票为 review，尚未批准或执行；只提出 B03 的版本隔离、已知 nullable projection 派生同步与兼容核验边界，不预先交付 runtime。原 B03 授权保留，但依其冻结 Stop Conditions 暂保持 blocked，待本补充批准后继续。

2026-09-24：B00C07已按用户同意补强，ready冻结于`7ab58ce`并完成文档交接。B03恢复ready；四个canonical paths来源修复与B02 needs_input fixture窄替换获得明确授权，尚未实现。先推进B03预算事务/失败恢复，再完成canonical实现与28/645验收；当前mapped56/remaining75、Phase B未完成。

2026-09-24 B03接续：B00C07已完成治理交接，但新注册member反例确认其B02 fixture替换与禁止trace0.5的限制冲突，B03再次blocked，待审B00C08。未修改production或golden；15项定向反例/回归通过。当前mapped56/remaining75，预算事务与canonical B03仍未实现。 见[B00C08待审票](tickets/phase-b-graph-harness/B00C08_B02_CANONICAL_EVIDENCE_TRACE_HANDOFF.md)。

2026-09-24：B00C08在13f3b74冻结并完成治理交接；B03恢复ready。Normal/timeout完整来源、source trace0.5、独立Analysis success前置及其golden审计范围已批准，尚待B03实现。预算事务与canonical交付未完成，mapped56/remaining75、Phase B未完成。

2026-09-24 B03接续：prestart/workspace基础已验证，真实public Pause反例确认Host setup的Run-only时间未进入预算回放。新增6项反例通过；依B03 Stop Conditions暂停依赖实现，等待[B00C09纠偏实施票审阅](tickets/phase-b-graph-harness/B00C09_ACTIVE_TIME_LEDGER_HANDOFF.md)。该票已修订但仍为`review`，未获准执行；C08治理仍completed，B03仍未交付28/645验收；上述历史2677/1410不代表当前未完成工作树的fresh全量结果。

2026-09-25：B00C09已完成，B03继续后新增Fake/Host stop、Code消费与fresh Analysis基础，首批3个B03 runtime case取得独立进程hook及exact trace证据。真实重复Code Attempt反例显示第二个scheduled记录未冻结被A03清除的prior Code ID，原advance在Transition后转为unavailable。修复需越过B03对通用Advance的Allowed Files，故B03现blocked；[B03C01](tickets/phase-b-graph-harness/B03C01_REPEAT_CODE_ATTEMPT_INVALIDATION.md)为review，未批准或实施。Mapped仍56/131、remaining75；28项construction、其余642项B03 runtime、双根golden和本轮全量回归仍待完成。

2026-09-25 B03续执行：获批准的[B03C01](tickets/phase-b-graph-harness/B03C01_REPEAT_CODE_ATTEMPT_INVALIDATION.md)已修复重复canonical Code的scheduled prior IDs；B03 maintenance已恢复10项B02 unavailable失败尾部及B02间接调用时的B03观察归属。十二份来源golden按旧/新raw、字段差异和双fresh根审定，A05/B02/external来源定向79项、B00来源定向85项通过。独立fresh construction为 **15/11/30/28**、累计映射 **84/131、remaining47**；B03独立runtime **7/645**有hook、passing nodeid及exact trace，其余638项未绑定，B03/B03C01仍in_progress，Phase B全局未完成。本轮完整回归及B02 1410项同Session复验待执行；未提交或推送。见[B03执行记录](tickets/completions/B03_COMPLETION.md)。

2026-09-28最终复核：Phase B **2531 passed**、全仓 **2856 passed**，fresh同Session construction **15/11/30/28**、B02 runtime **1410/1410**、B03已绑定 **7/7**；mapped **84/131、remaining47**，全局仍未完成。B03C01已completed；B03因冻结case0.3有12项未启动consumer阶段的不可达stop分类而blocked，待审[B03C02](tickets/phase-b-graph-harness/B03C02_POST_CLAIM_UNSTARTED_CASE_SEMANTICS.md)仍为review、未改验收清单。B03另有638项独立runtime待绑定。结果见[B03执行记录](tickets/completions/B03_COMPLETION.md)，未提交或推送。

2026-09-29 B03恢复执行：B03C02已完成，B03 YAML按原授权恢复`in_progress`，正文保持冻结。新增Backend dispatch不确定窗口的lookup-only恢复、post-claim原分类16项、首次ExternalOperation已提交stub的四类后继、pre-start 60项事务/完整性/deadline反例，以及receipt/result发布、CAS重放和来源冲突16项；116/645项已静态绑定，529项仍待独立runtime及整票验收。aggregate reservation的3个部分发布窗口已由原冻结后缀的过期恢复局部修复。最近一次完整Phase B/全仓2552/2877仍属当前源码更改前输入；全局`phase_b_complete=false`，未提交或推送。

2026-09-29 B03继续：receipt/result发布窗口新增8项持久化containment停止证明不足的不可物化收尾反例，124/645项静态绑定，521项待绑定。8项定向通过；同Session、construction、前置B02及全量复验仍待当前输入完成。Phase B探索性运行的5项A05 golden差异尚待生产源码稳定后依授权审定，不能直接覆盖expected。无提交或推送。

2026-09-29 B03进一步接线：前124项在同一fresh Session严格通过；B03 construction在允许本地Unix socket的环境为28/28。再补四项receipt/result已提交重放、20项pre-start互补publication与两项Backend dispatch前切点的safe/unavailable Watchdog收尾，现150/645静态绑定，余495项。新26项定向通过，当前输入的整组同Session与前置全量仍待复核。无提交或推送。

2026-09-29 B03局部修复：前150项同Session及28/28 construction已通过；Backend dispatch前/后来源损坏时的Watchdog stop proof分类与final不一致，已在原B03范围内修复并追加maintenance。三项新独立case定向通过，153/645静态绑定、492项未绑定；当前输入同Session与全量仍待复验。无提交或推送。

2026-09-29 B03继续：153项在同一fresh Session严格通过，construction仍28/28。Backend terminal completion的Host lookup前后增加八项真实恢复、冲突和不可用case，定向8项与双根固定trace通过；161/645静态绑定，余484项。当前输入的同Session、B02与全量最终验收待复核，A05来源golden仍未覆盖。无提交或推送。

2026-09-29 B03进一步接线：161项在同一fresh Session严格通过，construction为28/28。dispatch authorization的事务更新和commit前后新增14项真实进程恢复、来源冲突与Backend lookup不可用case，定向14项及双根固定trace通过；175/645静态绑定，余470项。当前输入的同Session、B02与全量最终验收待复核。无提交或推送。

2026-09-29 B03 Backend cancel补证：175项同Session、construction28/28及指定legacy/A03与专项回归通过；Backend cancel前后新增六项真实恢复、来源冲突与不可物化停止case，定向6项及双根固定trace通过；181/645静态绑定，余464项。当前输入整组同Session及前置最终回归待复核。无提交或推送。

2026-09-29 B03验收检查点：181项同Session严格通过，construction28/28，相邻外部停止/timeout/消费回归120项通过。repeat-Code旧golden与当前双根标准化轨迹有22处head/digest差异，旧raw来源及production最终状态尚待核验，expected未覆盖；其余464项和全量最终回归仍未完成。无提交或推送。

2026-09-29 B03补充回归：剔除已由同Session验收的runtime重复项后，其余B03专项在排除单个repeat-Code旧golden的条件下 **68 passed、1 deselected**；未发现另一项功能失败。该结果不替代剩余464项runtime及B02/Phase B/全仓最终验收。无提交或推送。

2026-09-29 B03停止边界复核：38项containment stop切点经双fresh根与独立分类审定，219/645项已绑定并同Session严格通过，construction28/28；另426项、6项golden失败及前置/全量最终回归未完成。repeat-Code旧raw preimage已找到且分别验证exact还原当前expected，未覆盖expected。无新增合同硬阻塞，B03继续in_progress；无提交或推送。
