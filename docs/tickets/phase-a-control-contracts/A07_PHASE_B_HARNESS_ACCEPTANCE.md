---
ticket_id: A07
phase: phase-a-control-contracts
status: review
type: design
depends_on: [A01, A02, A02C01, A03, A03C01, A04, A05, A06]
---

# 冻结 Phase B Harness 验收合同

## Goal

把A01–A03/A03C01已完成合同、A02C01 corrective contract及A04–A06待冻结合同转化为Phase B可以直接实施、机器检查且无法用局部happy-path测试替代的验收体系。

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
- [`A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md`](A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)
- [`A03_ARTIFACT_INVALIDATION.md`](A03_ARTIFACT_INVALIDATION.md)
- [`A03C01_EXECUTION_HEAD_INTEGRITY.md`](A03C01_EXECUTION_HEAD_INTEGRITY.md)
- [`A04_PAUSE_RESUME_SEMANTICS.md`](A04_PAUSE_RESUME_SEMANTICS.md)
- [`A05_CODE_AGENT_CONTRACT.md`](A05_CODE_AGENT_CONTRACT.md)
- [`A06_BUDGETS_AND_STOP_CONDITIONS.md`](A06_BUDGETS_AND_STOP_CONDITIONS.md)
- [`PHASE_B_REQUIREMENT_CATALOG.json`](PHASE_B_REQUIREMENT_CATALOG.json)
- [`Phase B Overview`](../phase-b-graph-harness/OVERVIEW.md)
- `tests/test_graph_smoke.py`
- `tests/test_execution_identity.py`
- `tests/test_artifact_registry.py`

## Scope

- 冻结Phase B的六层deterministic acceptance model；
- 冻结A01 target routes、forbidden behaviors及guard rejection的覆盖规则；
- 冻结A02/A03/A03C01 identity、invalidation、head和tamper evidence如何进入product graph验收；
- 冻结A04 Pause/Resume/Replay/Fork、A05 Graph-managed Fake Code Agent与fresh Analysis handoff、A06 Budget/Stop的required scenarios；
- 冻结normalized exact trajectory、process restart、independent-client concurrency和durability-boundary fault injection；
- 冻结machine-readable `PhaseBAcceptanceMatrix 0.1`及zero-gap gate；
- 冻结machine-readable `PhaseBRequirementCatalog 0.1`、stable requirement IDs及catalog-digest stale gate；
- 冻结legacy handoff compatibility、capability eval和parallel graph的边界；
- 冻结B01–B05 implementation ticket拆分与Phase B退出门槛。

## Non-goals

- 不实现或修改runtime、graph、state/schema validator、checkpoint、tests、fixtures、matrix或CLI；
- 不创建B01–B05 ticket文件，不提前执行Phase B；
- 不选择或引入LangSmith、Harbor、AgentEvals、其他第三方eval平台或新dependency；
- 不实现parallel reducer、fan-out/fan-in、并行Agent、并行artifact merge或相关race resolution；
- 不选择生产checkpoint backend、认证系统、distributed lock或跨存储事务；
- 不用live provider、真实sleep、历史`outputs/`或未批准raw numeric data证明control correctness；
- Phase B不安装或调用Codex SDK、不运行live provider，也不引入仍为beta的完整Agents SDK `SandboxAgent` runtime；`CodexSdkBackend`及其版本/模型/依赖属于Phase C；
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
- 与本ticket同一frozen snapshot中的`PHASE_B_REQUIREMENT_CATALOG.json` exact bytes；catalog变更必须使用新的acceptance corrective ticket和version；
- `src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`和accepted artifacts；
- `docs/ARCHITECTURE.md`、`docs/AGENT_ROLES_AND_BOUNDARIES.md`、`docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`和`docs/SECURITY_AND_DATA_POLICY.md`；
- graph topology、runtime schema、checkpoint backend、dependency versions、providers、认证与secrets；
- execution/artifact histories、现有Run、migration、repair或compatibility import；
- 已完成ticket、completion/correction history、milestone或tag。

## Acceptance Authority and Evidence Classes

Phase B control correctness的唯一完成证据是本ticket定义的required deterministic scenarios。每个scenario必须使用production route selector、validator、ledger builder、registry、Pause、budget、`CodeAgentSubgraph`与`CodingBackend` port入口；test-only fixture只能注入确定输入、clock、fault point和external outcome，不能直接patch成功state、伪造trusted evidence或跳过durable lifecycle。

证据分为三类：

- **Required control acceptance**：network-free、deterministic、exact semantic assertions；决定Phase B能否完成。
- **Compatibility regression**：当前legacy graph、CLI、demo与synthetic mock行为；必须继续通过，但不能替代target coverage。
- **Capability evaluation**：provider、RAG、科学质量、成本和路径质量；允许多个contract-conformant path class，不参与Phase B control completion。

任何live-provider pass、benchmark score、人工演示或单个full-graph happy path都不能填补required matrix缺口。

## Six Acceptance Layers

### Layer 0 — Schema, Replay and Invariants

使用production canonical serializer和validator验证execution schema `0.4`、A03 registry、Pause、Code Agent、`BackendDispatchReceipt`、`BackendOperationStatus`、`WorkspaceManifest`、`WorkspaceSeal`、`AnalysisExecutionSpec`、aggregate Backend reservation、BudgetPolicy/Decision/Fingerprint/Grant和bounded state。每个typed record至少覆盖valid round trip、required field缺失、unknown field/value、duplicate JSON key、identity/digest变化、counter gap/duplicate以及ledger/state/head不一致。

Layer 0必须复用A02/A03/A03C01现有完整性测试和实现入口；Phase B只增加新schema及跨合同关系，不复制第二套identity、current-selection或projection逻辑。

### Layer 1 — Node, Subgraph, Backend and Trusted Boundary

每个work/control node与`CodeAgentSubgraph` control stage使用deterministic fixture验证typed input、scoped context、structured outcome、artifact registration和禁止authority。Pre-start task/workspace/reservation/Pause stages不能claim或启动target Attempt，也不能创建额外Work/Control Attempt或automatic route计数；`consume_code_agent_result`只能在A04 claim与A06唯一settlement完成后，把同一scheduled target Attempt启动一次。

`FakeCodingBackend`与future `CodexSdkBackend`必须接收相同A05 task/result schema，经过同一`dispatch`/`lookup`/`fetch_result`/`cancel` port、production ingress validator、trusted verifier、artifact registry和fresh Analysis入口。Phase B只实例化Fake；Backend、provider job/thread或未来SandboxAgent不能写graph state、分配identity、推进head或拥有budget/retry/stop authority。

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

Smoke必须分别核对最终control `run_status`和领域`status`、execution/artifact/checkpoint heads、canonical/projection bytes、budget counters、Pause lifecycle、child lineage和accepted-result protection；CLI输出成功文本不能替代这些断言。

## `PhaseBAcceptanceMatrix 0.1`

后续B05必须创建tracked、test-owned文件：

```text
tests/phase_b/acceptance_matrix.json
```

该文件不是runtime config或Agent input。Top-level至少包含`schema_version = 0.1`、`phase = phase-b-graph-harness`、`requirement_catalog_version`、`requirement_catalog_sha256`和ordered `scenarios`。Catalog digest必须是A07冻结时tracked `PHASE_B_REQUIREMENT_CATALOG.json` exact bytes的SHA-256；不接受运行时重新解释ticket prose。

每个scenario至少包含：

- unique stable `scenario_id`；
- 一个或多个frozen `contract_refs`，每项必须是catalog中存在且`required: true`的stable `requirement_id`；
- `layer = schema | node | route | trajectory | recovery | interface`；
- deterministic `fixture_id`与project-owned `entrypoint`；
- nullable normalized `expected_trace_fixture`；
- typed `expected_result`与ordered `required_invariants`；
- 一个或多个collectable `pytest_nodeids`；
- `required: true | false`和typed evidence class。

Matrix、catalog及expected fixtures使用strict duplicate-key JSON读取。`requirement_id`和`scenario_id`分别全局唯一；每个scenario内部的`contract_refs`和`pytest_nodeids`不得重复。Contract ref和pytest nodeid可以跨scenario复用，`layer`必须属于固定enum，所有required fields不得缺失或指向不存在对象。Required scenario必须至少映射一个实际收集的test；同一test可以支持多个scenario，但必须分别报告每个scenario结果。

`expected_trace_fixture`对`route`、`trajectory`、`recovery`和`interface`层为required；纯`schema`或`node` scenario可以为null，但仍必须提供typed `expected_result`和足以证明合同的`required_invariants`。

Matrix validator必须从catalog构造ordered `required_requirement_ids`，从全部required scenarios构造`covered_requirement_ids`，要求两者set-equal并生成deterministic zero-gap report。以下任一情况必须退出非零：

- catalog中的A01 route/forbidden、A02C01 bootstrap或A04–A06任一required ID没有required scenario；
- matrix引用unknown/non-required ID，或catalog required ID重复、缺失、顺序漂移；
- matrix声明的catalog version/digest与tracked exact bytes不一致；
- nodeid无法collect，或required test被skip、xfail、deselect或仅在live opt-in时运行；
- applicable expected trace、required invariant或其fixture缺失，或schema不合法；
- pass report包含unknown、uncovered或stale scenario；
- compatibility/capability test被错误计作required control acceptance。

Phase B completion record必须引用matrix digest、scenario totals和zero-gap report，不能只记录`pytest`总pass count。

## `PhaseBRequirementCatalog 0.1`

Tracked companion contract固定为：

```text
docs/tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json
```

Catalog不是runtime config、Agent input或测试结果。它为A01冻结rows/forbidden bullets分配不回写原正文的stable IDs，并逐项收录A02C01、A04、A05、A06正文中显式标记的required IDs。每项至少包含`requirement_id`、`owner_ticket`、`source_locator`、`kind`、`summary`和`required`。

A07从`review`提升为`ready`时，其ticket正文与catalog exact bytes必须在同一frozen commit中；completion record记录catalog SHA-256。后续correction/corrective ticket改变任何required语义时，必须提升catalog version、更新受影响entry并由新的acceptance corrective ticket重新冻结，不能保留旧digest或只改自由文本label。

## Normalized Exact Trajectory Contract

Deterministic required trajectory将以下字段投影为ordered canonical JSON并exact比较：

- physical node与canonical Attempt kind；
- `CodeAgentSubgraph` pre-start/consume control stage与零额外Attempt副作用；
- selected route key、source/target、trigger class和guard result；
- Run/Cycle/Attempt/Transition identity、index、lineage和lifecycle；
- Pause、Human Request/Response、budget event、aggregate Backend reservation和grant lifecycle；
- semantic Backend operation status、dispatch/lookup/fetch/cancel outcome与operation binding；
- WorkspaceManifest/lease/materialization/WorkspaceSeal、dispatch receipt、immutable external result、Code Bundle与AnalysisExecutionSpec的identity/digest projection；
- artifact registration、current set/clear、managed projection、fresh Analysis worktree/subprocess和protection events；
- 每个step后的bounded state heads、current artifact IDs、budget used/remaining、control `run_status`与领域`status`。

Projection排除timestamp、duration、临时output root、物理workspace path、process ID、opaque backend-generated checkpoint以及provider job/thread/session字面值。排除不表示忽略：测试仍必须验证timestamp顺序/clock policy、path containment、checkpoint binding、opaque identity唯一性、operation/workspace绑定和所有canonical digests。

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
- accept、reject/failed、hold/pending report正常收尾均产生`run_status = completed`并保留typed领域disposition；control failure与halted分别保持`failed | halted`，accepted memory仅在policy允许时产生。

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

A02/A04为Human Response validation使用的external control Transition不是A01 product edge：它必须单独进入identity/Pause coverage，不能计作任一A01 positive route，也不能伪装成`human_gate -> human_gate`。真正的Human Gate validation Attempt完成后仍只能按A01提交`human_gate -> decision_coordinator`。

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
- invalid Human Response消费旧Pause；A06容量仍能保留下一次validation及其后续收尾合计所需的3个Control Attempts/4条Transitions时，严格按decision → old consumed → checkpoint → new opened创建新`pause_id`，否则安全`halted`，旧authorization不继承；
- `human_input` Pause使用null target，成功claim后才按A02 external control Transition恰好分配一个scheduled Human Gate validation Attempt；invalid response终结该validator，并在A06容量允许时打开下一个null-target Pause、否则安全`halted`，claim前不预分配下一Attempt，且不产生`human_gate -> human_gate`产品Transition；
- null-target `human_input` claim后、external control Transition/target Attempt完整commit前后的崩溃返回`recovery_required`，同key重试不重复分配；`recovery_decision`只允许exact existing target的`continue_existing_target`或existing/null target的`abandon_and_halt`，null target不得分配Attempt；
- recovery continue必须证明target从未started、无side effect/unsettled resource并只启动一次；recovery halt按A02 abandon existing target并转`halted`；wrong target/action、route/state patch、side-effect retry以及用recovery Pause代替replay/fork全部拒绝；
- 只有exact `run_status: paused`且有active opened Pause可以resume；`running | completed | failed | halted`、缺少exact active Pause的伪`paused`和pre-A04/A06 schema Run不能resume，领域`status: pending`在正常END后对应`run_status: completed`；
- cancel只作用于latest opened Pause并转`halted`；existing scheduled target必须写`abandoned`，null target不得创建Attempt；cancelled与abandoned之间崩溃返回`recovery_required`且target永不启动；
- `external_result` cancel先证明未dispatch或停止exact Backend operation并撤销lease，再提交A04 `cancelled`、abandon scheduled code target，最后actual-or-maximum settle aggregate；cancelled后abandonment/settlement前崩溃保持`halted`且按maximum计费；
- `external_result` 在`opened`前完成exact aggregate Backend reservation，Pause期间dispatch/lookup/fetch/result/delivery不推进budget或execution head，claim后唯一settlement先于target `started`；
- replay/fork创建全新child identities，source及accepted bytes不变且不继承Pause、current pointer、authorization或accepted status；
- fork只接受latest validated paused/terminal head并拒绝旧checkpoint或被history否定的artifact。

## Required A05 Graph-managed Fake Code Agent Scenarios

Matrix必须逐项映射：

- Planner implementation gap与Coordinator code fix两种task origin；
- pre-start task冻结、WorkspaceManifest创建、aggregate reservation和Pause publication在重放时幂等，且不claim/start target Attempt、不启动Backend、不注册code artifact、不创建额外Attempt/Transition或增加automatic route计数；
- aggregate Backend operation的pre-open reservation、Pause期间zero budget/execution-head drift、post-claim/pre-start唯一settlement和claim后settlement crash fail-closed；
- `dispatch`使用`producer_operation_id`幂等：duplicate返回同一receipt，conflicting payload拒绝；`lookup = running | completed | unknown`都只能描述原operation且不得启动第二个operation，known status返回同一receipt reference/digest以恢复receipt-publication crash，unknown使用null receipt；`fetch_result`不得刷新预算或退款；
- aggregate hard limit、operation timeout与operator cancellation通过`cancel`停止exact operation、撤销write lease且不创建替代operation；duplicate cancel幂等，wrong operation拒绝，停止失败或停止后activity fail closed；
- dispatch前、receipt publication前后、Backend完成前后、immutable result/seal publication前后、delivery snapshot前后、claim前后与consume前后的全部crash窗口不得重复Backend operation或target Attempt；
- result重复投递same bytes幂等，conflicting bytes拒绝；competing claim只有一个consumer成功；
- valid scoped `success`经过trusted verification后注册canonical content-addressed Code Bundle，且bundle包含`backend_dispatch_receipt.json`与`workspace_seal.json`；
- `no_change`、`failed`、`needs_input`、`needs_human`、`budget_exhausted`和safe `policy_blocked`全部进入Coordinator；
- Backend自报pass但trusted verification failed/blocked/timeout时拒绝Analysis；
- out-of-scope file、path/symlink escape、Git metadata、secret/raw/accepted/control target拒绝；
- `WorkspaceManifest`或`WorkspaceSeal`缺失、digest篡改、跨Attempt复用、foreign lease、base revision/tree drift、workspace path swap及seal后filesystem变化全部fail closed；
- wrong Run/Case/Cycle/Attempt/Transition/task/operation/base/workspace/Pause/result/member digest及duplicate-key/malformed ingress拒绝；
- non-empty unverified/partial change不能作为success；
- Human authorization scope/digest错误、已消费授权或执行中扩权必须创建新请求/Attempt或fail closed；
- multiple code attempts使用独立workspace/artifact，旧code及downstream不再current但canonical bytes保留；
- Code Bundle注册并成为current后，source wrapper才能让`commit_transition`先分配new scheduled Analysis Attempt、再提交绑定该exact target的`code_agent -> analysis_engineer` Transition，并发布绑定bundle/base/patch/effective-tree/target/Transition/runtime的`AnalysisExecutionSpec`；
- Analysis必须在fresh worktree与fresh subprocess从exact base应用verified change，并成功注册Analysis artifact；不得读取主控制仓库、复用Code Agent workspace或以module reload加载新代码；
- bundle已注册但Transition未提交时可幂等继续交接；Transition已提交但Analysis workspace未创建时可按同一spec幂等materialize；
- spec、patch、effective tree、runtime fingerprint或code/artifact head mismatch时旧Analysis target不得`started`、不得自动abandon或retarget，同一source不得提交第二条outbound Transition；原Run返回`recovery_required`/`halted`，只有通过A04 source validation后才可显式replay/fork；
- Fake与future Codex fixture通过同一`dispatch`/`lookup`/`fetch_result`/`cancel` port、validator、verifier、registration及fresh Analysis入口；legacy artifact不能读取为canonical Code Agent result。

## Required A06 Budget and Stop Scenarios

Matrix必须逐项映射：

- initial forward不扣automatic route额度；每条automatic route在limit前允许、达到limit后Gate；
- Work/Control/Transition absolute ceilings及5 Control Attempt/6 Transition terminal reserve；Human Gate request与response validation分别计数，invalid retry后仍须保留下一次validation及后续收尾合计3 Control/4 Transition；
- LLM/tool/verification reservation、settlement、unsettled crash full charge和duplicate operation拒绝；
- 每个`code_agent` Attempt恰有一个`code_backend_operation` aggregate，绑定operation/task/backend/WorkspaceManifest/Pause并统一预留现有LLM/tool/active dimensions；第二份aggregate或Backend-owned counter拒绝；
- aggregate的pre-open reservation、Pause期间dispatch/lookup/fetch/result zero budget/execution-head drift、post-claim/pre-start settlement、可信actual缺失时maximum settlement和claim后settlement crash fail-closed；
- aggregate maximum/timeout由可信Host在side effect前强制执行；actual超额、cancel/lease revocation失败或停止后activity不能通过maximum accounting掩盖，必须fail closed；
- Fake fixture提供deterministic usage并与future Codex Backend走同一lifecycle；Backend receipt/tool audit/seal矛盾时按maximum结算且fail closed；
- pre-start Host setup只计Run、Backend operation结算到aggregate预留的target-Attempt与Run active dimensions但不启动Attempt、result后delivery等待不计active time、post-start trusted verification计Attempt与Run，以及所有fake clock boundary；
- first retryable technical fingerprint允许，second exact fingerprint升级；新Attempt/workspace/job/thread/operation identity不改变`code_task_context_digest`或`analysis_execution_context_digest`；
- backend版本/runtime、base、policy、verified patch/effective tree或material input evidence变化会生成新context/fingerprint；timestamp、summary、physical path或重复Human approval不会；
- `lookup`/`fetch_result`不能创建operation、刷新预算或退款；Backend、Codex thread/job与未来SandboxAgent没有独立budget、retry或stop authority；
- high/critical、ambiguous、policy/security/data及non-retryable scientific failure第一次即Gate；
- single-use grant的correct consumption，以及wrong actor/scope/route/fingerprint/target、competition、duplicate consumption和global ceiling拒绝；
- expired Pause返回`pause_expired`且无自动event/cancel，必须显式cancel/replay/fork；
- policy bytes/digest、ledger event identity/counter、reservation、fingerprint、grant和bounded projection tamper fail closed；
- start默认profile、resume exact policy、replay/fork计数清零、schema `0.3`不迁移；
- missing token/cost保持`unknown`且不参与hard gate；
- budget stop不绕过risk、Human Gate、A03 invalidation或accepted-result保护，resource exhaustion后不调用provider/tool或accepted memory。

## Fault Injection and Crash Outcomes

Required failpoints固定在以下durable publication boundaries：

- A02C01 schema `0.4`的Run creation、`policy_initialized`、bootstrap `decision_recorded`、initial Cycle、Planner Attempt、A03 initial invalidation、START Transition和checkpoint前后；
- WorkspaceManifest publication、workspace materialization/lease以及aggregate reservation前后；
- checkpoint写入前，以及checkpoint写入后但Pause `opened`前；
- Pause `opened`后、Backend dispatch前、`BackendDispatchReceipt` publication前后、Backend completion前后、WorkspaceSeal与immutable result publication前后；
- delivery snapshot前后、claim前后、settlement前后，以及settlement后但`consume_code_agent_result`/Attempt `started`前；
- budget `decision_recorded`后但Transition或resource reservation前；
- `grant_consumed`前后以及其后target Attempt allocation/A03 invalidation/Transition append完整commit前；无跨record transaction时partial sequence必须`recovery_required`、grant不退款且target不启动；
- invalid Human Response的repause `decision_recorded`、old Pause `consumed`、new checkpoint和new Pause `opened`前后；
- `resource_reserved`后但`resource_settled`前；
- Transition/invalidation commit后但target Attempt `started`前；
- Code Bundle member/registry/current publication前后，以及bundle current后但Analysis Transition提交前；
- Analysis Transition提交后但`AnalysisExecutionSpec` publication、fresh workspace materialization、fresh subprocess启动或Analysis artifact publication前后；
- artifact history/index/projection publication或bounded-state sync出现partial/corrupt head。

Bootstrap fault scenarios必须证明只有同一start operation的严格合法、无副作用prefix可以确定性继续，任何冲突或side-effect prefix均fail closed。Transition fault scenarios必须证明scheduled target allocation先于A03 invalidation、invalidation先于committed Transition append。Invalid-response fault scenarios必须证明旧Pause一经`consumed`不再打开，未完成`opened`的新Pause不接收输入。External-result fault scenarios还必须证明：aggregate `resource_reserved`先于Pause `opened`，Pause期间的dispatch/lookup/fetch/result/delivery evidence不推进budget或execution head，唯一`resource_settled`后于claim且先于target Attempt `started`；hard limit/timeout/cancellation通过exact `cancel`停止operation。Fresh Analysis fault scenarios必须证明exact spec可幂等materialize，但任何spec/head/digest冲突都不启动旧target、不retarget、不从同一source提交第二条outbound Transition，并进入A04允许的显式replay/fork或halt边界。

每个failpoint必须记录预期类别：

- durable safe boundary允许相同idempotency request准确继续一次；
- 未完成Pause publication、claim后不确定性、unsettled reservation、partial Transition/result或head mismatch返回`recovery_required`或`halted`；
- 禁止自动退款、重复provider/tool/Backend operation、重新执行target Attempt、恢复旧current artifact、复用workspace或自动partial repair。

Fault harness使用injected deterministic hooks和fake clock，不通过kill timing race或真实sleep制造概率性结果。Process-restart场景仍必须真实启动新的Python process并重新打开durable store。

## Legacy Compatibility Boundary

Phase B canonical product graph在deterministic/mock profile下使用A05 `CodeAgentSubgraph + FakeCodingBackend`。当前`legacy_codex_handoff`只保留为显式命名的compatibility entrypoint：

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
3. **B03 — Graph-managed Fake Code Agent**：`CodeAgentSubgraph`、`CodingBackend` port、`FakeCodingBackend`、A05 task/result与workspace contracts、production ingress validator、trusted verification、content-addressed bundle、external-result Pause integration和fresh Analysis handoff service。
4. **B04 — Target Product Topology and Budgeted Loops**：把B03接入A01 edges、Coordinator四层fallback、Human Gate return、A03 invalidation、A06 aggregate Backend reservation/admission/grant和terminal behavior。
5. **B05 — Acceptance Matrix and End-to-End Harness**：为本ticket全部新增scenario建立matrix/meta-validator、normalized traces、workspace/Backend/Analysis fault与concurrency tests、compatibility regression、CLI smoke和zero-gap evidence。

Dependency顺序固定为B01；B02 depends on B01；B03 depends on B01/B02；B04 depends on B01–B03；B05 depends on B01–B04。每份implementation ticket必须自行冻结Allowed Files、Do Not Touch、migration边界和focused verification，不得把五份工作合成未审查的大型ticket。

## Phase B Exit Gate

Phase B只有同时满足以下条件才能标记completed：

- machine-readable matrix schema有效、digest已记录且required coverage为zero-gap；
- 所有required deterministic scenarios通过，无skip、xfail、unknown、uncovered或live-only项；
- Layer 0–5 focused suites、完整`pytest -q`和`python -m compileall -q src tests evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py`通过；
- synthetic benchmark tests及full mock-provider benchmark通过，capability结果与control evidence分开报告；
- 新的`/private/tmp/lqcd-agent-phase-b-*` CLI smoke核对ledger/state/checkpoint/artifact/budget/Pause/child/accepted invariants；
- legacy compatibility suite继续通过且单独计数；
- Phase B没有安装或调用Codex SDK、运行live provider或引入完整Agents SDK SandboxAgent；Phase C Backend工作没有被Fake pass替代；
- Markdown links、ticket metadata、scope、stale docs和`git diff --check`通过；
- 没有读取raw numeric data、复用历史`outputs/`或运行live-provider测试。

Phase B completion record必须列出matrix digest、required/covered/passed totals、每层focused命令、full-suite结果、mock benchmark、CLI smoke root及所有明确deferred capability。只报告总pass数或“demo成功”不满足退出条件。

## Deliverables

- decision-complete的六层Phase B acceptance model；
- `PhaseBAcceptanceMatrix 0.1` schema与zero-gap规则；
- `PhaseBRequirementCatalog 0.1`、stable IDs、required-set equality和catalog SHA-256 stale gate；
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
- Fake Code Agent完整经过graph-managed pre-start、A04 Pause、A06 aggregate settlement、trusted verification、Code Bundle与fresh Analysis handoff，且不调用Codex SDK或完整SandboxAgent；
- legacy只能作为compatibility entrypoint，parallel明确不属于Phase B；
- machine-readable matrix能够机械拒绝missing/stale/uncollectable/skipped coverage；
- B01–B05可以直接起草而无需重新决定实施顺序或职责边界；
- 本ticket执行不产生runtime/tests/configs/Phase B ticket diff。

## Pre-freeze Review Gate

本ticket从`review`提升为`ready`前必须确认：

- YAML保持`status: review`，直到A02C01与A04–A07完成交叉审查、catalog核验并获得用户最终确认；
- ticket内没有待确认架构问题、未决占位符或内嵌执行记录；
- `PHASE_B_REQUIREMENT_CATALOG.json`通过strict JSON、unique ID、owner/source和required-set验证；A01全部17条route、9条forbidden behavior、A02C01 bootstrap以及A04/A05/A06每个显式required ID均恰有一个catalog entry；
- A01每个route/forbidden behavior、A02C01 bootstrap以及A04–A06每个required scenario都已映射到machine-checkable coverage rule，matrix只能引用catalog ID；
- A07 ticket正文与catalog exact bytes将在同一frozen commit中，completion记录catalog version与SHA-256；
- A04–A06之间没有需要改变Pause、Code Agent、budget或stop语义的未决冲突；
- A05要求的Backend/workspace/fresh Analysis scenarios和A06要求的aggregate/active-time/semantic fingerprint scenarios均逐项进入matrix coverage；
- dependency、Allowed Files与Do Not Touch无冲突，所有相对Markdown links和Read First仓库路径有效；
- Phase A Overview、Docs Index和Current State一致记录A02C01与A04–A07为`review`；
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
- Phase B必须安装/调用Codex SDK、运行live provider、引入完整SandboxAgent，或必须让Backend拥有第二套budget/retry/stop authority才能完成required control acceptance；
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
