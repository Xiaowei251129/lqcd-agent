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

当前B00–B02与已批准corrective均完成，B03–B05仍draft。2026-09-22的[完成核验与后续草案审查](tickets/corrections/B00_B05_READINESS_REVIEW.md)记录了交付证据、后续票据矛盾修订及B03执行前的ready门槛；Phase B整体尚未完成。

冻结机读合同为[Control Protocol 0.4](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)及[Phase B需求目录](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)；状态更新不得移除这两项权威引用。

- [`NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md`](NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md)：第二阶段三个改进方向和 A–E 阶段关系；
- [`tickets/README.md`](tickets/README.md)：ticket 生命周期、执行规则和目录说明；
- [`tickets/TEMPLATE.md`](tickets/TEMPLATE.md)：统一 ticket 合同。
- [`tickets/completions/README.md`](tickets/completions/README.md)：独立执行结果记录；
- [`tickets/corrections/README.md`](tickets/corrections/README.md)：maintenance与corrective历史记录。

Phase Overview 不是执行 prompt。只有经过用户确认并标记为 `status: ready` 的具体 ticket 才能执行；`ready`后ticket正文冻结，执行结果和后续纠偏不得回写原计划。

Phase A的A01–A07、A02C01及A03C01现均为`completed`。B00/B01/B02、B00C01–B00C04及B02C01已完成；B03–B05仍为`draft`。B00/B01/B02 construction分别为 **15/15、11/11、30/30**，累计映射 **56/131、remaining75**。B02的 **205个boundary、1410个独立case** 全部具有同一冻结输入、同一fresh session的通过证据；完整suite **2599 passed**。全局final仍仅报告 **75 coverage / 798 runtime / 15 exit** 缺口，`requirements.passed=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。执行事实见[B02完成记录](tickets/completions/B02_COMPLETION.md)及[Phase B Overview](tickets/phase-b-graph-harness/OVERVIEW.md)。B02交付独立0.4 durable control入口，默认产品runtime仍为schema `0.2`；B03 Backend/Code Bundle、B04产品图和B05全阶段验收仍由各自票据交付。以下日期条目保留当时的进展和阻塞事实，以本段和完成记录最后条目为当前状态。

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
