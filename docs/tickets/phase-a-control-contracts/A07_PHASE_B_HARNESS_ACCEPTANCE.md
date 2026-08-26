---
ticket_id: A07
phase: phase-a-control-contracts
status: review
type: design
depends_on: [A01, A02, A03, A03C01, A04, A05, A06]
---

# 冻结 Phase B Harness 验收合同

## Goal

把A01–A06及A03C01已经冻结的控制合同转化为Phase B可以直接实施、机器检查且无法用局部happy-path测试替代的验收体系。

本ticket只确认测试分层、scenario coverage、machine-readable matrix、Phase B拆票和退出门槛，并同步验收类source-of-truth文档；不实现runtime、tests、Fake Code Agent或Phase B implementation tickets。

## Why

A02/A03已有的fallback harness证明identity与artifact invalidation primitives能够支持未来回退，但不表示A01 target product topology、A04 durable recovery、A05 canonical Code Agent或A06 budget manager已经接入。只运行当前full suite也无法证明所有目标edge、forbidden route、crash boundary和重复副作用都被覆盖。

A07必须冻结“什么证据才算Phase B完成”：control correctness使用network-free deterministic fixtures和exact semantic trajectory；Agent/provider能力评估留在独立层。Phase B实现者不得自行删减scenario、把legacy route计作canonical覆盖，或用一个end-to-end pass掩盖未验证的边界。

## Read First

- [`AGENTS.md`](../../../AGENTS.md)
- [`docs/README.md`](../../README.md)
- [`docs/tickets/README.md`](../README.md)
- [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`docs/AGENT_ROLES_AND_BOUNDARIES.md`](../../AGENT_ROLES_AND_BOUNDARIES.md)
- [`docs/STATE_SCHEMA.md`](../../STATE_SCHEMA.md)
- [`docs/ARTIFACT_CONTRACTS.md`](../../ARTIFACT_CONTRACTS.md)
- [`docs/SECURITY_AND_DATA_POLICY.md`](../../SECURITY_AND_DATA_POLICY.md)
- [`docs/EVALS_AND_OBSERVABILITY.md`](../../EVALS_AND_OBSERVABILITY.md)
- [`docs/VERIFICATION_GUIDE.md`](../../VERIFICATION_GUIDE.md)
- [`docs/REPO_CURRENT_STATE.md`](../../REPO_CURRENT_STATE.md)
- [`A01_TRANSITION_MATRIX.md`](A01_TRANSITION_MATRIX.md)
- [`A02_RUN_CYCLE_ATTEMPT_MODEL.md`](A02_RUN_CYCLE_ATTEMPT_MODEL.md)
- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)
- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)
- [`A05_CODE_AGENT_CONTRACT.md`](A05_CODE_AGENT_CONTRACT.md)
- [`A06_BUDGETS_AND_STOP_CONDITIONS.md`](A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [`Phase B Overview`](../phase-b-graph-harness/OVERVIEW.md)
- `tests/test_graph_smoke.py`
- `tests/test_execution_identity.py`
- `tests/test_artifact_registry.py`

## Scope

- 冻结Phase B的六层deterministic acceptance model；
- 冻结A01 target routes、forbidden behaviors及guard rejection的覆盖规则；
- 冻结A02/A03/A03C01 identity、invalidation、head和tamper evidence如何进入product graph验收；
- 冻结A04 Pause/Resume/Replay/Fork、A05 Fake Code Agent和A06 Budget/Stop的required scenarios；
- 冻结normalized exact trajectory、process restart、independent-client concurrency和durability-boundary fault injection；
- 冻结machine-readable `PhaseBAcceptanceMatrix 0.1`及zero-gap gate；
- 冻结legacy handoff compatibility、capability eval和parallel graph的边界；
- 冻结B01–B05 implementation ticket拆分与Phase B退出门槛。

## Non-goals

- 不实现或修改runtime、graph、state/schema validator、checkpoint、tests、fixtures、matrix或CLI；
- 不创建B01–B05 ticket文件，不提前执行Phase B；
- 不选择或引入LangSmith、Harbor、AgentEvals、其他第三方eval平台或新dependency；
- 不实现parallel reducer、fan-out/fan-in、并行Agent、并行artifact merge或相关race resolution；
- 不选择生产checkpoint backend、认证系统、distributed lock或跨存储事务；
- 不用live provider、真实sleep、历史`outputs/`或未批准raw numeric data证明control correctness；
- 不改变A01 route authority、A02 identity、A03 artifact/accepted-result、A04 recovery、A05 Code Agent或A06 budget语义；
- 不把测试通过解释为scientific acceptance、production readiness或真实Code Agent完成。

## Allowed Files

本ticket提升为`ready`并执行时，只允许修改：

- `docs/tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md`：仅允许更新YAML lifecycle metadata，不向正文追加执行日志；
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`；
- `docs/tickets/completions/A07_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/EVALS_AND_OBSERVABILITY.md`；
- `docs/VERIFICATION_GUIDE.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

- A01–A06及A03C01 ticket正文；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`和accepted artifacts；
- `docs/ARCHITECTURE.md`、`docs/AGENT_ROLES_AND_BOUNDARIES.md`、`docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`和`docs/SECURITY_AND_DATA_POLICY.md`；
- graph topology、runtime schema、checkpoint backend、dependency versions、providers、认证与secrets；
- execution/artifact histories、现有Run、migration、repair或compatibility import；
- 已完成ticket、completion/correction history、milestone或tag。

## Acceptance Authority and Evidence Classes

Phase B control correctness的唯一完成证据是本ticket定义的required deterministic scenarios。每个scenario必须使用production route selector、validator、ledger builder、registry、Pause、budget和adapter入口；test-only fixture只能注入确定输入、clock、fault point和external outcome，不能直接patch成功state、伪造trusted evidence或跳过durable lifecycle。

证据分为三类：

- **Required control acceptance**：network-free、deterministic、exact semantic assertions；决定Phase B能否完成。
- **Compatibility regression**：当前legacy graph、CLI、demo与synthetic mock行为；必须继续通过，但不能替代target coverage。
- **Capability evaluation**：provider、RAG、科学质量、成本和路径质量；允许多个contract-conformant path class，不参与Phase B control completion。

任何live-provider pass、benchmark score、人工演示或单个full-graph happy path都不能填补required matrix缺口。

## Six Acceptance Layers

### Layer 0 — Schema, Replay and Invariants

使用production canonical serializer和validator验证execution schema `0.4`、A03 registry、Pause、Code Agent、BudgetPolicy/Decision/Fingerprint/Grant和bounded state。每个typed record至少覆盖valid round trip、required field缺失、unknown field/value、duplicate JSON key、identity/digest变化、counter gap/duplicate以及ledger/state/head不一致。

Layer 0必须复用A02/A03/A03C01现有完整性测试和实现入口；Phase B只增加新schema及跨合同关系，不复制第二套identity、current-selection或projection逻辑。

### Layer 1 — Node, Adapter and Trusted Boundary

每个work/control node使用deterministic fixture验证typed input、scoped context、structured outcome、artifact registration和禁止authority。Fake Code Agent与未来real adapter接收相同A05 task/result schema，并经过同一个production ingress validator、trusted verifier interface和artifact registration path。

Fake fixture只能由trusted harness的stable scenario ID选择；Agent task或自由文本不能选择outcome。Agent/provider/tool payload不能分配identity、提交Transition、改写current pointer、policy/counter、Pause、grant或accepted memory。

### Layer 2 — Route, Guard and Transition

每条A01 target Transition Matrix row都必须在compiled target graph中至少有一个positive scenario。带guard的edge还必须具有至少一个negative或escalation scenario，证明guard失败不会先调度错误Attempt、清除current artifacts或产生目标side effect。

所有fixed与conditional edges统一经过A02 source-wrapper selection、Transition commit和scheduled target consumption；conditional reader保持纯读取。每个target transition同时验证A03 invalidation、input dependency、current projection和execution/artifact heads。

### Layer 3 — Trajectory, Cycle and Termination

使用完整compiled target graph验证normal forward、planned code、四层fallback、Human Gate、budget stop和terminal path。每个trajectory断言canonical semantic projection exact-equal，不只断言最终status或节点出现过。

Cycle/Attempt规则必须在真实trajectory中成立：initial/replan创建Cycle；re-review、analysis rerun和code fix保持Cycle并创建新Attempt；所有失败、Pause、grant和terminal tail遵守A02/A04/A06 counter与single-use规则。

### Layer 4 — Durable Recovery, Concurrency and Fault Injection

至少使用现有SQLite能力作为durable test backend，并在新的Python process中重新打开Run；Memory checkpoint只能用于不声称跨进程durability的unit tests。生产backend选择仍不属于Phase B。

Pause claim、idempotency和grant竞争必须由两个独立control clients验证，不能只依赖同一对象或进程内lock。Fault injection只允许位于本ticket列出的durability boundaries，并必须证明恢复结果是exact resume once或typed fail-closed outcome。

### Layer 5 — Project Interface and Smoke

通过A04项目自有`start_run`、`resume_run`、`replay_run`、`fork_run`和`cancel_pause`入口执行deterministic tests及新的`/private/tmp/lqcd-agent-phase-b-*` CLI smoke。不得直接调用raw LangGraph checkpoint resume或提交arbitrary state/route patch。

Smoke必须核对最终Run status、execution/artifact/checkpoint heads、canonical/projection bytes、budget counters、Pause lifecycle、child lineage和accepted-result protection；CLI输出成功文本不能替代这些断言。

## `PhaseBAcceptanceMatrix 0.1`

后续B05必须创建tracked、test-owned文件：

```text
tests/phase_b/acceptance_matrix.json
```

该文件不是runtime config或Agent input。Top-level至少包含`schema_version = 0.1`、`phase = phase-b-graph-harness`和ordered `scenarios`。每个scenario至少包含：

- unique stable `scenario_id`；
- 一个或多个frozen `contract_refs`，格式为ticket ID加section/route/scenario label；
- `layer = schema | node | route | trajectory | recovery | interface`；
- deterministic `fixture_id`与project-owned `entrypoint`；
- nullable normalized `expected_trace_fixture`；
- typed `expected_result`与ordered `required_invariants`；
- 一个或多个collectable `pytest_nodeids`；
- `required: true | false`和typed evidence class。

Matrix及expected fixtures使用strict duplicate-key JSON读取。`scenario_id`必须全局唯一；每个scenario内部的`contract_refs`和`pytest_nodeids`不得重复。Contract ref和pytest nodeid可以跨scenario复用，`layer`必须属于固定enum，所有required fields不得缺失或指向不存在对象。Required scenario必须至少映射一个实际收集的test；同一test可以支持多个scenario，但必须分别报告每个scenario结果。

`expected_trace_fixture`对`route`、`trajectory`、`recovery`和`interface`层为required；纯`schema`或`node` scenario可以为null，但仍必须提供typed `expected_result`和足以证明合同的`required_invariants`。

Matrix validator必须生成deterministic zero-gap report，并在以下任一情况退出非零：

- A01 target row或forbidden behavior没有required scenario；
- A04–A06任一required scenario bullet没有contract mapping；
- nodeid无法collect，或required test被skip、xfail、deselect或仅在live opt-in时运行；
- applicable expected trace、required invariant或其fixture缺失，或schema不合法；
- pass report包含unknown、uncovered或stale scenario；
- compatibility/capability test被错误计作required control acceptance。

Phase B completion record必须引用matrix digest、scenario totals和zero-gap report，不能只记录`pytest`总pass count。

## Normalized Exact Trajectory Contract

Deterministic required trajectory将以下字段投影为ordered canonical JSON并exact比较：

- physical node与canonical Attempt kind；
- selected route key、source/target、trigger class和guard result；
- Run/Cycle/Attempt/Transition identity、index、lineage和lifecycle；
- Pause、Human Request/Response、budget event、reservation和grant lifecycle；
- artifact registration、current set/clear、managed projection和protection events；
- 每个step后的bounded state heads、current artifact IDs、budget used/remaining和Run status。

Projection排除timestamp、duration、临时output root、process ID及opaque backend-generated checkpoint字面值。排除不表示忽略：测试仍必须验证timestamp顺序/clock policy、path containment、checkpoint binding、opaque identity唯一性和所有canonical digests。

同一deterministic fixture只允许一个exact semantic trace。只有Capability evaluation可以声明多个contract-conformant path classes；required control test不能用宽松“包含这些节点”、unordered subset或只看final status替代exact trace。

## A01 Route and Forbidden Coverage

下列每个target edge都必须具有positive compiled-graph scenario：

- `START -> method_planner`；
- `method_planner -> analysis_engineer | code_agent | decision_coordinator`；
- `code_agent -> analysis_engineer | decision_coordinator`；
- `analysis_engineer -> scientific_reviewer | decision_coordinator`；
- `scientific_reviewer -> decision_coordinator`；
- `decision_coordinator -> scientific_reviewer | analysis_engineer | code_agent | method_planner | human_gate | memory_report`；
- `human_gate -> decision_coordinator`；
- `memory_report -> END`。

至少覆盖以下完整trajectory classes：

- 无代码normal forward；
- Planner识别implementation gap后通过Fake Code Agent再进入fresh Analysis；
- Planner needs-input/planning failure进入Coordinator；
- re-review、analysis rerun、code fix和replan四层fallback；
- high/critical、诊断歧义、第二次exact fingerprint和route/resource exhaustion进入Human Gate；
- valid Human response回Coordinator并只派发exact authorized target；
- accept、reject/failed、hold/pending和halted收尾，accepted memory仅在policy允许时产生。

下列A01 forbidden behaviors必须逐类具有negative compiled-graph scenario：

- Analysis直接进入Code Agent或Planner；
- Reviewer直接进入Analysis、Code Agent或Planner；
- Human Gate直接进入work Agent、Memory Report或自行修改response；
- Memory Report重新发起任一循环；
- 仅凭自由文本、source node、unvalidated provider建议或完整event log决定route；
- 无新Attempt/Cycle identity和A03 invalidation时覆盖旧结果；
- high/critical、诊断歧义、预算耗尽或重复failure继续automatic loop；
- Human decision重复消费或产生无限budget；
- Agent从未审核单次经历直接改写长期规则、skill或routing policy。

Forbidden scenario必须证明错误target未被scheduled、current artifacts未被提前清除、target side effect未发生且accepted state未变化；只检查router返回值不足以验收。

## A02/A03/A03C01 Product Integration Coverage

所有A01 target trajectories必须同时证明：

- Run/Cycle/Attempt/Transition/Human/budget IDs在Run内唯一、连续且bounded state指向global latest heads；
- nonterminal Transition保留exact target tuple并匹配唯一scheduled Attempt，terminal END使用显式nullable target fields；
- target Attempt在side effect前已分配，route reader不重复selection或写state；
- target-layer及downstream current artifacts在Transition边界正确clear，historical canonical bytes保持；
- finished Attempt output registration、dependency、projection owner和state convenience path与ledger exact匹配；
- Human snapshots和accepted terminal具有唯一protection，invalidation不删除protected evidence；
- current state、execution ledger、artifact registry和checkpoint任一identity/head/digest篡改都fail closed。

现有A02/A03/A03C01 focused suites继续作为Layer 0/2 regression，但A02/A03最小fallback harness不能单独计算A01 product edge coverage。

## Required A04 Recovery Scenarios

Matrix必须逐项映射：

- process退出后`human_input`、`external_result`和`recovery_decision` Pause准确恢复且最多消费一次；
- same key/same payload返回同一结果，same key/different payload拒绝，不同key竞争同一Pause只有一个claim成功；
- 错误actor/scope、Run/Pause、typed payload digest、expired Pause及runtime/policy fingerprint拒绝且无mutation；
- invalid Human Response消费旧Pause并创建新`pause_id`，旧authorization不继承；
- `success`、`failed`、`pending`、`halted`和pre-A04/A06 schema Run不能resume；
- cancel只作用于latest opened Pause并转`halted`；
- `external_result` 在`opened`前完成exact resource reservation，Pause期间dispatch/delivery不推进execution head，claim后settlement先于target `started`；
- replay/fork创建全新child identities，source及accepted bytes不变且不继承Pause、current pointer、authorization或accepted status；
- fork只接受latest validated paused/terminal head并拒绝旧checkpoint或被history否定的artifact。

## Required A05 Fake Code Agent Scenarios

Matrix必须逐项映射：

- Planner implementation gap与Coordinator code fix两种task origin；
- external operation的pre-open reservation、Pause期间zero execution-head drift、post-claim/pre-start settlement和claim后settlement crash fail-closed；
- valid scoped `success`进入fresh Analysis Attempt并注册canonical content-addressed code bundle；
- `no_change`、`failed`、`needs_input`、`needs_human`、`budget_exhausted`和safe `policy_blocked`全部进入Coordinator；
- adapter自报pass但trusted verification failed/blocked/timeout时拒绝Analysis；
- out-of-scope file、path/symlink escape、Git metadata、secret/raw/accepted/control target拒绝；
- wrong Run/Case/Cycle/Attempt/Transition/task/base/workspace/Pause/result/member digest及duplicate-key/malformed ingress拒绝；
- duplicate/conflicting dispatch、duplicate delivery、competing claim和claim后crash不得重复external operation；
- non-empty unverified/partial change不能作为success；
- Human authorization scope/digest错误、已消费授权或执行中扩权必须创建新请求/Attempt或fail closed；
- multiple code attempts使用独立workspace/artifact，旧code及downstream不再current但canonical bytes保留；
- Fake与future real fixture通过同一validator/verifier/registration入口；legacy artifact不能读取为canonical Code Agent result。

## Required A06 Budget and Stop Scenarios

Matrix必须逐项映射：

- initial forward不扣automatic route额度；每条automatic route在limit前允许、达到limit后Gate；
- Work/Control/Transition absolute ceilings及4 Control Attempt/5 Transition terminal reserve；
- LLM/tool/verification reservation、settlement、unsettled crash full charge和duplicate operation拒绝；
- `external_result` operation的pre-open reservation、Pause期间zero execution-head drift、post-claim/pre-start settlement和claim后settlement crash fail-closed；
- per-Attempt/per-Run active time、paused time排除、external operation计费及fake clock boundary；
- first retryable technical fingerprint允许，second exact fingerprint升级，material evidence变化生成新context/fingerprint；
- identity、timestamp、summary、temporary path或重复Human approval不构成新evidence；
- high/critical、ambiguous、policy/security/data及non-retryable scientific failure第一次即Gate；
- single-use grant的correct consumption，以及wrong actor/scope/route/fingerprint/target、competition、duplicate consumption和global ceiling拒绝；
- expired Pause返回`pause_expired`且无自动event/cancel，必须显式cancel/replay/fork；
- policy bytes/digest、ledger event identity/counter、reservation、fingerprint、grant和bounded projection tamper fail closed；
- start默认profile、resume exact policy、replay/fork计数清零、schema `0.3`不迁移；
- missing token/cost保持`unknown`且不参与hard gate；
- budget stop不绕过risk、Human Gate、A03 invalidation或accepted-result保护，resource exhaustion后不调用provider/tool或accepted memory。

## Fault Injection and Crash Outcomes

Required failpoints固定在以下durable publication boundaries：

- checkpoint写入前，以及checkpoint写入后但Pause `opened`前；
- Pause `opened`后、claim前，以及claim后但consume/result commit前；
- budget `decision_recorded`后但Transition或resource reservation前；
- `resource_reserved`后但`resource_settled`前；
- Transition/invalidation commit后但target Attempt `started`前；
- external dispatch前、dispatch后但delivery前，以及delivery claim后但canonical result registration前；
- artifact history/index/projection publication或bounded-state sync出现partial/corrupt head。

External-result fault scenarios还必须证明：`resource_reserved`先于Pause `opened`，Pause期间的dispatch/delivery evidence不推进execution head，`resource_settled`后于claim且先于target Attempt `started`。

每个failpoint必须记录预期类别：

- durable safe boundary允许相同idempotency request准确继续一次；
- 未完成Pause publication、claim后不确定性、unsettled reservation、partial Transition/result或head mismatch返回`recovery_required`或`halted`；
- 禁止自动退款、重复provider/tool/adapter operation、重新执行target Attempt、恢复旧current artifact或自动partial repair。

Fault harness使用injected deterministic hooks和fake clock，不通过kill timing race或真实sleep制造概率性结果。Process-restart场景仍必须真实启动新的Python process并重新打开durable store。

## Legacy Compatibility Boundary

Phase B canonical product graph在deterministic/mock profile下使用A05 Fake `code_agent`。当前`legacy_codex_handoff`只保留为显式命名的compatibility entrypoint：

- legacy继续使用`attempt_kind = legacy_codex_handoff`及现有artifact contract；
- canonical graph、matrix和A01 target edge coverage不能调用legacy node；
- legacy和canonical Code Agent不能共享result validator、route guard或current artifact identity；
- legacy regression必须继续通过，但pass count单独报告；
- 不自动迁移旧Run，不把legacy output转换为A05 bundle。

是否未来删除legacy entrypoint必须另开ticket；A07不授权删除或把它继续作为canonical默认路径。

## Sequential Boundary and Future Parallel Work

Phase B只验收A01–A06定义的顺序control graph。不得增加parallel reducer、并发work Agent、fan-out/fan-in、并行artifact merge或parallel budget semantics。

Harness必须拒绝不在A01 matrix中的并行branch或多target Transition，不能把“并行尚未实现”记录为Phase B uncovered item。未来需要并行时必须先创建独立design ticket，冻结identity、merge、invalidation、budget和failure semantics后再增加acceptance。

## Phase B Implementation Ticket Split

A07执行只把以下拆分同步到Phase B Overview，不创建ticket文件。Phase A全部completed后，按顺序起草并确认：

1. **B01 — Execution 0.4 Control Foundation**：BudgetPolicy/ledger、bounded projection、trusted clock、canonical validators及execution/artifact/checkpoint cross-head integrity。
2. **B02 — Durable Control Operations**：project-owned start/resume/replay/fork/cancel、Pause publication、SQLite durable test store、atomic claim、idempotency和process-restart recovery。
3. **B03 — Canonical Fake Code Agent**：A05 schemas、production ingress validator、deterministic Fake adapter、trusted verification、content-addressed bundle和external-result Pause integration。
4. **B04 — Target Product Topology and Budgeted Loops**：A01 edges、Coordinator四层fallback、Human Gate return、A03 invalidation、A06 admission/reserve/grant和terminal behavior。
5. **B05 — Acceptance Matrix and End-to-End Harness**：matrix/meta-validator、normalized traces、fault/concurrency tests、compatibility regression、CLI smoke和zero-gap evidence。

Dependency顺序固定为B01；B02 depends on B01；B03 depends on B01/B02；B04 depends on B01–B03；B05 depends on B01–B04。每份implementation ticket必须自行冻结Allowed Files、Do Not Touch、migration边界和focused verification，不得把五份工作合成未审查的大型ticket。

## Phase B Exit Gate

Phase B只有同时满足以下条件才能标记completed：

- machine-readable matrix schema有效、digest已记录且required coverage为zero-gap；
- 所有required deterministic scenarios通过，无skip、xfail、unknown、uncovered或live-only项；
- Layer 0–5 focused suites、完整`pytest -q`和`python -m compileall -q src tests evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py`通过；
- synthetic benchmark tests及full mock-provider benchmark通过，capability结果与control evidence分开报告；
- 新的`/private/tmp/lqcd-agent-phase-b-*` CLI smoke核对ledger/state/checkpoint/artifact/budget/Pause/child/accepted invariants；
- legacy compatibility suite继续通过且单独计数；
- Markdown links、ticket metadata、scope、stale docs和`git diff --check`通过；
- 没有读取raw numeric data、复用历史`outputs/`或运行live-provider测试。

Phase B completion record必须列出matrix digest、required/covered/passed totals、每层focused命令、full-suite结果、mock benchmark、CLI smoke root及所有明确deferred capability。只报告总pass数或“demo成功”不满足退出条件。

## Deliverables

- decision-complete的六层Phase B acceptance model；
- `PhaseBAcceptanceMatrix 0.1` schema与zero-gap规则；
- A01–A06及A03C01 required scenario inventory；
- exact trajectory、fault/concurrency、legacy和parallel边界；
- B01–B05拆分及Phase B exit gate；
- 受影响验收/阶段文档同步；
- 独立`docs/tickets/completions/A07_COMPLETION.md`及completion索引更新。

## Acceptance Criteria

- ticket内没有待确认架构问题、未决占位符或内嵌执行记录；
- A01每个target row、guard和forbidden behavior都有明确的required coverage rule；
- A04–A06的每个required downstream bullet都被本ticket保留，没有由实现者自行抽样；
- deterministic control test使用exact normalized trace，capability eval不能替代control acceptance；
- process restart、independent-client claim和每个durability boundary都有确定的success/fail-closed结果；
- legacy只能作为compatibility entrypoint，parallel明确不属于Phase B；
- machine-readable matrix能够机械拒绝missing/stale/uncollectable/skipped coverage；
- B01–B05可以直接起草而无需重新决定实施顺序或职责边界；
- 本ticket执行不产生runtime/tests/configs/Phase B ticket diff。

## Pre-freeze Review Gate

本ticket从`review`提升为`ready`前必须确认：

- YAML保持`status: review`，直到A04–A07完成交叉审查并获得用户统一确认；
- ticket内没有待确认架构问题、未决占位符或内嵌执行记录；
- A01每个target/forbidden route以及A04–A06每个required scenario都已映射到machine-checkable coverage rule；
- A04–A06之间没有需要改变Pause、Code Agent、budget或stop语义的未决冲突；
- dependency、Allowed Files与Do Not Touch无冲突，所有相对Markdown links和Read First仓库路径有效；
- Phase A Overview、Docs Index和Current State一致记录A04–A07为`review`；
- review diff不包含runtime、tests、evaluation、configs、dependency或provider改动，且B01–B05 ticket文件不存在。

## Verification

执行本design ticket时只运行静态、文档与scope检查：

```bash
git diff --check
```

还必须验证：

- ticket在`ready`之后只变更YAML lifecycle metadata，正文与执行前冻结commit一致；
- A01–A06及A03C01均已`completed`，它们的ticket正文未修改；
- Required Documentation Updates已同步，Phase A被一致标记为完成，Phase B Overview记录B01–B05的拆分、依赖与entry/exit gate；
- `docs/tickets/completions/A07_COMPLETION.md`已建立并加入completion index；
- B01–B05 ticket文件仍不存在，本ticket没有提前执行Phase B；
- Allowed Files/Do Not Touch与实际diff一致，所有现行Markdown relative links有效；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`和accepted artifacts没有本ticket产生的diff；
- 不运行pytest、benchmark或live-provider测试，因为本ticket只冻结验收合同。

## Stop Conditions

- A04–A06仍存在必须改变scenario语义才能形成matrix的未决冲突；
- 必须改变A01 route、A02 identity、A03 registry/accepted-result、A04 recovery、A05 Code Agent或A06 budget合同；
- 必须先选择第三方eval平台、生产checkpoint、认证、distributed lock或新dependency；
- acceptance必须依赖live provider、真实sleep、raw numeric data或历史outputs；
- Phase B无法将legacy与canonical Code Agent coverage分离，或必须实现parallel graph才能完成顺序合同；
- 需要扩大Allowed Files、触碰Do Not Touch或在本ticket中创建implementation ticket；
- A04–A07交叉审查发现会改变本ticket核心acceptance contract的冲突。

遇到以上任一条件时保持`review`并请求用户确认；如果ticket已冻结为`ready`，必须另开design/corrective ticket，不能修改本ticket正文。

## Required Documentation Updates

执行本ticket时同步：

- `docs/EVALS_AND_OBSERVABILITY.md`：control/capability证据分类、六层模型和matrix gate；
- `docs/VERIFICATION_GUIDE.md`：Phase B scenario、focused/full、fault/concurrency和exit commands；
- Phase A/Phase B Overview：A07 completion、B01–B05拆分与Phase B entry/exit；
- `docs/README.md`、`docs/REPO_CURRENT_STATE.md`和`docs/DECISION_LOG.md`；
- 独立completion record与completion index。
