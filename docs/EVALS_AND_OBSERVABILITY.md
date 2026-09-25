# Evals and Observability

## 当前定位

评估体系必须分别回答“控制流程是否正确”和“Agent 是否足够聪明”。deterministic harness 负责验证 graph contract；provider/RAG benchmark 负责比较能力、成本与稳定性。两类证据不能互相替代。

当前所有自动评估仍是 synthetic-only，不读取 real raw numeric data。实际运行 artifacts 属于 `<output_root>/<case_id>/<run_id>/`，不是 curated baseline。

## `v0.2-demo` 验证基线

第一阶段封版时已经验证：

- full deterministic suite：`162 passed`；
- Phase 8 good/ambiguous/bad synthetic evaluation；
- Phase 9 `l64c64a076_m140` Golden Demo；
- Phase 10C 9-case full mock-provider benchmark；
- 5-case live-provider advisor demo；
- provider safety floor、Human Gate 与 accepted-memory protection。

完整封版证据与复现命令见 [V0_2_DEMO_BASELINE.md](milestones/V0_2_DEMO_BASELINE.md)。

## 当前评估集合

### Phase 8 synthetic cases

`evaluation/run_evaluation.py` 验证三类基础行为：

- good：low risk，直接进入 Memory and Report，memory accepted；
- ambiguous：medium risk，生成 report，memory pending；
- bad：high risk，进入 Human Approval Gate，未批准时 memory pending。

### Phase 10C advisor-demo benchmark

`evaluation/synthetic_benchmarks/` 将 agent-visible input 与 instructor-only expected sidecar 分离。

- demo set：clean fit、noisy valid fit、fit-window contamination、normalization violation、targeted rerun；
- full set 额外包含 plateau instability、invalid uncertainty、missing input 与 controlled code-fix branch；
- mock-provider mode 是普通开发和 CI-style regression；
- live-provider mode 只用于显式 opt-in rehearsal。

mock full benchmark：

```bash
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py \
  --provider mock \
  --case-set full \
  --output-dir /private/tmp/lqcd-agent-phase10c-mock
```

live demo 不是普通验收要求：

```bash
RUN_LIVE_LLM_TESTS=1 python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py \
  --provider-config configs/runtime/openai.yaml \
  --case-set demo \
  --output-dir /private/tmp/lqcd-agent-phase10c-live
```

hidden expected behavior 不得进入 Agent input、provider prompt 或 final-report evidence。

## 当前 Observability Contract

每次 run 应能定位：

- `graph_state.json` 与 checkpoint metadata；
- node/event log 和 `route_decisions`；
- command provenance、manifest、warnings 与 errors；
- method、analysis、review、decision、approval、memory 和 final-report paths；
- provider-backed run 的 `llm_calls/<agent>.json`。

`llm_calls/` 记录 agent、timestamp、status、non-secret provider metadata、structured request、response/parse status、artifact path 与 errors。它可能包含 bounded prompt/response content，因此只能保存在 ignored run output 中，不能进入 tracked baseline。

## 当前指标

现有可观测指标包括：

- case status、risk level、recommended action 与 approval required；
- retry count、command success 与 artifact validation；
- warnings by severity；
- context-window status；
- actual-vs-expected route、memory 与 warning checks。

这些指标描述 `v0.2-demo` 当前能力，不等于第二阶段最终 trajectory metric。

## A06 已确认的 Budget/Stop Observability 目标（durable接入待实现）

A06要求Phase B normalized trace与acceptance matrix能够从权威policy和ledger重建，而不是相信Agent summary或mutable state。每个Run至少可观察：

- policy version/profile/reference/digest，以及每个hard dimension和automatic route的used、remaining与projected-after；
- `BudgetDecision allow | human_gate | halt`、reason、exact proposed action、validated heads、failure fingerprint occurrence和nullable grant；
- resource reservation/settlement identity、maximum/actual vector、timeout、Attempt/Run active-time归属，以及unsettled crash的conservative charge；
- Code Agent唯一aggregate envelope与ExternalOperation/task/workspace/Pause binding，确保dispatch/lookup/fetch期间budget和execution heads零漂移；
- grant issued/consumed、exact Human Response snapshot/actor/scope/target及duplicate或mismatch拒绝；
- Pause opened/deadline/claim边界、terminal reserve余额、typed stop trigger、safe-stop proof、settlement disposition、Pause quarantine与terminal closure outcome。

Token和normalized cost只作audit metric；provider未报告时必须显示`unknown`，不能计作0或影响hard-gate通过率。Stop telemetry必须区分`halted`、已证明且可发布的`failed`、`recovery_required`、`terminal_closure: unavailable`和非terminal`materialization_pending`，不得只报告“任务失败”。B01已有pure construction traces覆盖execution order/heads、policy/fingerprint、clock归属和typed integrity rejection；默认产品trace仍是普通`llm_calls/`和schema `0.2` execution records，durable stop telemetry尚未接入。

B00C09使B03 canonical Code path的Host setup、Backend aggregate与Attempt active在同一ledger中可独立重放；观测必须分别报告Run-only setup、Run/Attempt共同收费、未结算maximum、跨epoch conservative disposition、nested verification的command与实测audit秒数。旧B02 synthetic路径不得因缺少新版marker而被当成canonical计费。B00C09定向与兼容测试不代替B03的28项construction或645项runtime，完整验收仍按原owner集合执行。

## Phase B Acceptance Foundation 与待实现的 Runtime Evidence

A07把评估证据分成required control acceptance、compatibility regression和capability evaluation。只有第一类计入required control coverage：它必须network-free、deterministic、使用production selector/validator/ledger/registry/Pause/budget/CodeAgentSubgraph入口，并对exact normalized semantic trace和typed invariants断言。Legacy、live provider、benchmark score、人工演示或单一happy path必须单独报告，不能填补required coverage。

六层模型覆盖schema/replay/invariants，node/subgraph/backend/trusted boundary，route/guard/Transition，trajectory/Cycle/termination，durable recovery/concurrency/fault injection，以及project interface/CLI smoke。Normalized trace纳入control与domain identity/lifecycle、route/guard、artifact current/invalidation/protection、budget/grant、Pause/Run、ExternalOperation/workspace/backend、fresh Analysis和每步bounded heads；只排除timestamp duration、临时物理路径、process ID及opaque provider/checkpoint字面值，同时仍单独验证其顺序、containment、binding和唯一性。

Phase B matrix必须绑定tracked protocol/catalog exact digests，并以九个owner的131项required IDs为唯一required set。B00已批准合同定义`PhaseBAcceptanceReport 0.1`：construction只报告当前slice/stage通过数及全局映射缺口，全局`requirements.passed/passed_ids=null`且两个完成标志为false；final同时验证construction/final scenarios与独立runtime obligations，全部适用证据通过才有`requirements_zero_gap=true`，所有exit checks也有效通过才有`phase_b_complete=true`。Required nodeid不可skip、xfail、deselect、live-only或uncollectable，route/trajectory/recovery/interface场景必须具有exact expected trace。Process restart必须真正重启Python并重新打开durable store；Pause claim、terminal owner、grant和idempotency竞争必须使用两个独立client/process，fault outcome只能是exact same-operation continuation或冻结的typed fail-closed分类。

B00 final driver由同一次调用创建session并驱动Layer 0–5、cross-system fault/concurrency、Phase B suite、full pytest、compileall、synthetic tests、full mock benchmark、legacy regression、CLI smoke及文档/scope检查。证据绑定本次token、实际工作树输入和protocol/catalog/matrix/registry等摘要；旧证据、未触发hook、缺META-015 publication/fresh Analysis/consumption release或28条post-claim case均不能通过。Benchmark退出0但某case/checklist失败仍为exit失败；compatibility/capability不能填补required control数量，但规定的legacy/mock检查是独立必需退出条件。闭合字段与完整义务以[B00冻结合同](tickets/phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md)为准；执行机制已实现并通过隔离适配器验证，B05仍须接入真实exit adapters。

当前matrix已有B00/B01/B02三个slice。B00/B01/B02 construction分别为 **15/15、11/11、30/30**，累计映射 **56/131、remaining75**。B02的 **205个boundary、1410个独立case** 全部具有同一冻结输入、同一fresh session的通过证据；完整suite **2617 passed**。全局final仍仅报告 **75 coverage / 789 runtime / 15 exit** 缺口，`requirements.passed=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。现行独立清单为case语义0.3的2199项；205个B02 boundary已完整绑定，剩余789项属于其他票据。B02-owned fresh证明通过全部实际production hook、passing nodeid、invariants和固定trace，但不能把它改写为全局final通过；全局preflight仍要求其余bindings及B05适配器。

2026-09-17 B02续执行回归为Phase B **453 passed**、禁用live provider的完整pytest **778 passed**、A02/A03/state **139 passed**。Fresh B00/B01为15/15和11/11，final仅报告105 coverage、2286 runtime与15 exit缺口。这些测试数量不是B02的30项requirement pass计数；尚未追加B02 slice或宣称累计56 covered，详细边界见[B02执行记录](tickets/completions/B02_COMPLETION.md)。

## 第二阶段 Harness 方向

第二阶段按以下层次扩展，但本轮不提前批准具体 metric 或实现：

1. Phase A 已明确 transition、attempt、invalidation、resume、Code Agent、budget 和 harness acceptance contracts；
2. Phase B 用 deterministic fake nodes 做 transition/trajectory、cycle、checkpoint 与 termination tests；
3. Phase C 验证真实 Code Agent 的 scope、tests、budget 和回环；
4. Phase D 对 physics/RAG 能力做有来源、可比较、支持 abstention 的评估；
5. Phase E 形成 integrated benchmark 与下一 milestone。

具体 Phase B acceptance 已由`completed`的 [A07](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)、tracked [`Control Protocol 0.4`](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json) machine schema 0.4和catalog version 0.4.0共同冻结。B00静态meta tests已消费其中的transaction domain、resolution CAS、guarded branches、tagged evidence unions、winner-observation组合状态、request-owned normal safe-stop candidate classification、完整trigger-class/context stop route、interrupt disposition、interrupt late-integrity outcome、Cancel branch-to-resolution tuple/phase闭包、START/Replay/Fork/ordinary Transition的commit-gated capability、exact terminal lifecycle、reservation到ExternalOperation tuple及source proof到request Run/lineage的绑定、Replay source-policy classifier、stable fork、variant overlay与phase dominance及其exact digests，而不是从自然语言或实现反向定义验收范围。A06已经冻结具体policy、accounting和stop metrics，但这些仍是目标合同，不能写成当前runtime要求。

B00C01/B00C02已完成source-bound trace `0.2`与exit evidence接线：保留raw完整性及fresh session验证后，仅投影已证明的physical root和Execution绝对clock，identity、owner、phase、route、budget及material内容仍参与exact比较。双fresh subprocess的完整exit校验产生一致semantic摘要，旧token/摘要和篡改source被拒绝；旧trace `0.1`保持原义。见[B00C02完成记录](tickets/completions/B00C02_COMPLETION.md)。B02前置阻塞解除，但上述测试不构成B02/runtime/final通过证据。

## Raw-data-backed Evals 的前置条件

只有同时满足以下条件，才可增加 raw-data/reference-output-backed evaluation：

- raw-data manifest 与 checksum 已定义；
- raw numeric data access 有明确批准；
- reference outputs versioned 或 append-only；
- expected behavior 位于 `raw_data/` 之外；
- reference outputs 与 actual-run `outputs/` 严格分离。

## 相关文档

- [Project Specification](PROJECT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Phase B Overview](tickets/phase-b-graph-harness/OVERVIEW.md)

2026-09-18验收状态：B02 runtime定向测试继续扩展，但construction仍只有B00/B01两slice，covered26/remaining105。0.3 Fork runtime成功而trace 0.2拒绝其historical source kinds的三条诊断不计passing evidence；B02已blocked，待[B00C03 review](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)。205个B02边界/1488个case仍未绑定，不能用pytest总数替代30项construction或final runtime证据。

2026-09-21：[B00C03](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)已批准并完成。显式trace `0.3`验证原格式historical source、真实Fork reservation及0.4 child引用；旧0.1/0.2语义保持。源checkpoint完整main/WAL/SHM只读副本校验与逐文件不变测试通过。完整pytest **1063 passed**，Phase B **738项可收集**；fresh B00/B01仍15/15、11/11，mapped26/remaining105，final仅105/2286/15缺口。B02恢复原票执行，30项construction和205/1488 runtime bindings仍待完成；见[B00C03完成记录](tickets/completions/B00C03_COMPLETION.md)。这替代上述“B00C03待审批、B02因historical trace阻塞”的当前状态，不改写历史审查事实。

2026-09-21 reservation边界审查：B00C03已completed，其历史证明阻塞已解除；B02随后修复快照丢失卡住和合法grant replan被拒绝，两组回归101/45 passed。真实进程在首次reservation事务COMMIT前退出会完整回滚、没有可恢复的原operation；冻结B00 case笛卡尔展开却要求该边界产生原operation的materialization/domain-gap状态。六项复现及不可变重放对照通过，详见[B02记录](tickets/completions/B02_COMPLETION.md#2026-09-21--reservation-fault-case-executability-audit)。B02现为blocked，待审[B00C04](tickets/phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)，未实施该草案。当前mapped26/remaining105及原2286 runtime/15 exit缺口不变；此前“B02恢复执行”是发现此新缺口前的记录。

2026-09-21本轮验证完成：完整pytest **1086 passed**，Phase B可收集 **761项**；fresh B00/B01 **15/15、11/11**，final仅 **105 coverage / 2286 runtime / 15 exit** 缺口。冻结摘要、生成字节、scope及链接检查通过。B02因[B00C04](tickets/phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)待审仍blocked，详见[B02最终记录](tickets/completions/B02_COMPLETION.md#current-tree-final-verification-2026-09-21)。

## 2026-09-21 B00C04 integrated correction

B00C04已批准实施：case语义0.2及disposition不改变requirements/owner，只修正首次COMMIT前无operation的真实结果；trace0.4增加typed资源预留来源引用，旧版本不变。Runtime证据必须包含真实production hook（含同session子进程回执）、passing nodeid及fixed expected trace；回执本身不算runtime通过。当前2214个独立case尚未接齐B02/B03/B04，覆盖仍26、剩余105。

B00C04逐项审查补充：11个仅能到达unavailable的phase不可能产生committed result；其22个case改为严格terminal_tombstone_replay，保留真实recovery_required及原owner unavailable，不改runtime状态。旧→新表为1370 retained/118 replaced，现行2214/B02 1416不变。

2026-09-21 B00C04完成：case0.2、trace0.4、直接production进程回执及严格分批验证落地；旧1488个B02 case为1370 retained/118 replaced，现行B02 **1416**、总数 **2214**，全部324 boundary及B03/B04集合不变。完整pytest **1118 passed**、新增定向 **32 passed**，fresh B00/B01 **15/15、11/11**，coverage26/remaining105。Global passed null、phase_b_complete false。B02验收前置阻塞已解除，接续原票处理已审定的runtime缺陷及完整验收；本修正票不代表B02完成。证据见[B00C04完成记录](tickets/completions/B00C04_COMPLETION.md)。

2026-09-21 C04补充审查：Fork `child.source_revision_cas`在首次reservation提交前，两项独立进程反例均完整回滚。沿用原票已批准的全boundary审查范围补齐这一遗漏；C04重新in_progress，B02暂为blocked。旧1488个B02 case现为1362 retained/126 replaced，现行总数 **2208**、B02 **1410**，减少78均有提交前反例；324 boundary、B03/B04及28 post-claim保持。之前2214/1416及C04完成报告保留为当时验证事实。coverage仍26/105；尚无B02 slice。

2026-09-21 C04集成补验完成：完整pytest1158 passed，fresh B00/B01 15/15、11/11；C04现completed，B02继续in_progress。现行独立case2208/B02 1410，covered26/remaining105，尚无B02 slice；此前blocked及补验in_progress为历史过程。详见[B00C04完成记录](tickets/completions/B00C04_COMPLETION.md)。

## 2026-09-24 B00C05 case0.3

B00C05已完成并解除B03首次ExternalOperation reservation分类阻塞：真实初始producer与case0.3已验证，独立集合2199（B02 1410、B03 645、B04 144），324 boundaries和28 post-claim不变。Fresh B00/B01/B02为15/11/30，完整2617 passed、同Session B02-owned 1410/1410；mapped56/remaining75，final仅75 coverage / 789 runtime binding / 15 exit，global passed=null、Phase B未完成。B03恢复ready，canonical Backend与其28项验收仍待交付。 本次case版本保留0.1/0.2封存规则与摘要，旧trace0.1–0.4语义不变；B03的case版本入口由已批准B00C05显式替代，其冻结正文不改写。前置2599项通过为B02交付时的历史基线，2617项为本次C05 fresh完整验证。

2026-09-24 B00C06：用户批准补强、冻结提交并执行，ready commit `cd29d9f`。显式 trace 0.5 / proof 0.2 及 A05 全链 contract/meta 证据正在集成验证，旧 trace、旧 goldens、src、case0.3 不变。B03 暂保持 blocked；通过后仅解除来源轨迹前置，预算事务和状态投影兼容仍须独立核验。

2026-09-24 B00C06完成：trace0.5/proof0.2 全链来源与四条验收路径通过，2677 passed、同 Session B02 runtime1410/1410，fresh B00/B01/B02为15/11/30；mapped56/remaining75，final仅75/789/15。旧trace、旧goldens、src、case0.3保持。B03来源阻塞已解除，但接续实证确认A05空字段投影超出原fingerprint-only golden授权，因该独立边界继续blocked，待窄范围补充审阅。
