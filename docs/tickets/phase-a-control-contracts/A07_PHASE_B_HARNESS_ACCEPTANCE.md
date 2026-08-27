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
- [`Control Protocol 0.4`](CONTROL_PROTOCOL_0_4.json)
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
- 冻结machine-readable `ControlProtocol 0.4`作为ControlOperation、ExternalOperation、Run lifecycle、outcome partition与construction DAG的单一枚举，并把exact-byte digest绑定到catalog和matrix；
- 冻结legacy handoff compatibility、capability eval和parallel graph的边界；
- 冻结B00–B05 implementation ticket拆分与Phase B退出门槛。

## Non-goals

- 不实现或修改runtime、graph、runtime state/schema validator、checkpoint、tests、fixtures、matrix或CLI；本轮tracked标准库脚本只做design-time exact-byte协议审查，不是Phase B实现或runtime dependency；
- 不创建B00–B05 ticket文件，不提前执行Phase B；
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
- 与本ticket同一frozen snapshot中的`CONTROL_PROTOCOL_0_4.json` exact bytes；protocol变更必须同步catalog-bound SHA，并使用新的acceptance corrective ticket和version；
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

使用production canonical serializer和validator验证execution schema `0.4`、A03 registry、Pause、Code Agent、`ControlOperation` type/variant/phase allowed-edge maps、Run terminal closure ownership、`ExternalOperation` cancellation phases、`BackendDispatchReceipt`、`BackendOperationStatus`、`WorkspaceManifest`、`WorkspaceSeal`、`AnalysisExecutionSpec`、aggregate Backend reservation、BudgetPolicy/Decision/Fingerprint/Grant和bounded state。每个typed record至少覆盖valid round trip、required field缺失、unknown field/value、duplicate JSON key、identity/digest变化、counter gap/duplicate以及ledger/state/head不一致。

Layer 0必须复用A02/A03/A03C01现有完整性测试和实现入口；Phase B只增加新schema及跨合同关系，不复制第二套identity、current-selection或projection逻辑。

### Layer 1 — Node, Subgraph, Backend and Trusted Boundary

每个work/control node与`CodeAgentSubgraph` control stage使用deterministic fixture验证typed input、scoped context、structured outcome、artifact registration和禁止authority。Pre-start producer stub/task/unmaterialized manifest/reservation/core/workspace/Pause stages不能claim或启动target Attempt，也不能创建额外Work/Control Attempt或automatic route计数；`consume_code_agent_result`只能在A04 claim、A06唯一settlement、`pause_consumed`、paused-to-running lifecycle与resume checkpoint完成后，把同一scheduled target Attempt启动一次。

`FakeCodingBackend`与future `CodexSdkBackend`必须接收相同A05 task/result schema，经过同一`dispatch`/`lookup`/`fetch_result`/`cancel` port、production ingress validator、trusted verifier、artifact registry和fresh Analysis入口。Phase B只实例化Fake；Backend、provider job/thread或未来SandboxAgent不能写graph state、分配identity、推进head或拥有budget/retry/stop authority。

Fake fixture只能由trusted harness的stable scenario ID选择；Agent task或自由文本不能选择outcome。Agent/provider/tool payload不能分配identity、提交Transition、改写current pointer、policy/counter、Pause、grant或accepted memory。

### Layer 2 — Route, Guard and Transition

每条A01 target Transition Matrix row都必须在compiled target graph中至少有一个positive scenario。带guard的edge还必须具有至少一个negative或escalation scenario，证明guard失败不会先调度错误Attempt、清除current artifacts或产生目标side effect。

所有fixed与conditional edges统一经过A02 source-wrapper selection、Transition commit和scheduled target consumption；conditional reader保持纯读取。每个target transition同时验证A03 invalidation、input dependency、current projection和execution/artifact heads。

### Layer 3 — Trajectory, Cycle and Termination

使用完整compiled target graph验证normal forward、planned code、四层fallback、Human Gate、budget stop和terminal path。每个trajectory断言canonical semantic projection exact-equal，不只断言最终status或节点出现过。

Cycle/Attempt规则必须在真实trajectory中成立：initial/replan创建Cycle；re-review、analysis rerun和code fix保持Cycle并创建新Attempt；所有失败、Pause、grant和terminal tail遵守A02/A04/A06 counter与single-use规则。

### Layer 4 — Durable Recovery, Concurrency and Fault Injection

必须使用A02C01规定的`<output_root>/.lqcd/control_operations.sqlite`作为durable mutation/claim reference backend，并与per-Run LangGraph checkpoint database物理分离；在新的Python process中重新打开coordinator、Run与checkpoint。Memory checkpoint只能用于不声称跨进程durability的unit tests。生产分布式backend选择仍不属于Phase B。

Pause claim、Run terminal closure ownership、idempotency和grant竞争必须由两个独立control clients/processes验证，coordinator write path至少使用等价于`BEGIN IMMEDIATE`的single-writer transaction，不能只依赖同一对象、进程内lock或LangGraph checkpoint metadata。Fault injection只允许位于本ticket列出的durability boundaries，并必须证明恢复结果是exact same-operation continuation或typed fail-closed outcome。

### Layer 5 — Project Interface and Smoke

通过A04项目自有`start_run`、`resume_run`、`replay_run`、`fork_run`和`cancel_pause`入口执行deterministic tests及新的`/private/tmp/lqcd-agent-phase-b-*` CLI smoke。不得直接调用raw LangGraph checkpoint resume或提交arbitrary state/route patch。

Smoke必须分别核对最终control `run_status`和领域`status`、execution/artifact/checkpoint heads、canonical/projection bytes、budget counters、Pause lifecycle、child lineage和accepted-result protection；CLI输出成功文本不能替代这些断言。

## `PhaseBAcceptanceMatrix 0.1`

后续B00必须创建并由B01–B05持续维护tracked、test-owned文件：

```text
tests/phase_b/acceptance_matrix.json
```

该文件不是runtime config或Agent input。Top-level至少包含`schema_version = 0.1`、`phase = phase-b-graph-harness`、`requirement_catalog_version`、`requirement_catalog_sha256`、`control_protocol_version`、`control_protocol_sha256`和ordered `scenarios`。初次冻结的catalog content version固定为`0.1.0`，与JSON schema version独立。两个digest必须分别是A07冻结时tracked `PHASE_B_REQUIREMENT_CATALOG.json`与`CONTROL_PROTOCOL_0_4.json` exact bytes的SHA-256；不接受运行时重新解释ticket prose或从测试实现反向发明phase graph。

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

Matrix validator提供严格分离的construction与final模式。Construction模式只验证schema、catalog identity、已存在scenario/nodeid和当前implementation ticket声明的owned requirement subset；它必须显式报告全局remaining IDs，不能输出zero-gap/pass或把尚未实现项写成placeholder、skip、xfail。Final模式从catalog构造ordered `required_requirement_ids`，从全部required scenarios构造`covered_requirement_ids`，要求两者set-equal并生成deterministic zero-gap report；B05和Phase B exit必须使用final模式。以下任一情况在适用模式中必须退出非零：

- catalog中的A01、A02、A02C01、A03、A03C01、A04、A05、A06或A07任一required ID没有required scenario，或required owner集合不与这九个ticket exact相等；
- matrix引用unknown/non-required ID，或catalog required ID重复、缺失、顺序漂移；
- matrix声明的catalog或control-protocol version/digest与tracked exact bytes不一致；
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

Catalog不是runtime config、Agent input或测试结果。它为A01–A03/A03C01冻结合同分配不回写原正文的stable IDs，逐项收录A02C01、A04、A05、A06正文中显式标记的required IDs，并为A07自身matrix/catalog/meta-validation/exit-gate合同分配stable IDs。每项至少包含`requirement_id`、`owner_ticket`、`source_locator`、`kind`、`summary`和`required`。Required owner集合固定为`A01 | A02 | A02C01 | A03 | A03C01 | A04 | A05 | A06 | A07`，缺少任一owner都使catalog无效。

Machine zero-gap只证明required matrix与已冻结catalog set-equal，不宣称机器可以从自然语言ticket正文自动推导全部规范。Catalog对ticket prose与correction registry的语义完整性由A07从`review`提升为`ready`前的人工交叉审核确认；冻结后catalog成为Phase B机器验收的唯一required-set输入。Validator必须独立检查owner集合、stable ID、source locator、required ordering和catalog digest，不能用一份手写matrix反向定义catalog expected set。

A07从`review`提升为`ready`时，其ticket正文、protocol与catalog exact bytes必须在同一frozen commit中；completion record记录protocol和catalog SHA-256。后续correction/corrective ticket改变任何required语义时，必须提升适用content version、更新受影响entry并由新的acceptance corrective ticket重新冻结，不能保留旧digest或只改自由文本label。

## `ControlProtocol 0.4`

Tracked machine contract固定为 [`CONTROL_PROTOCOL_0_4.json`](CONTROL_PROTOCOL_0_4.json)。它不是runtime config、Agent input、bounded state或LangGraph topology；它是Phase A在冻结前用于消除prose drift的单一机器枚举，B00必须原样消费并生成runtime enum/router/static assertions，不能从A04/A05自然语言重新推导另一张图。

Protocol至少冻结：七类ControlOperation及其variant、phase和success edges；每个phase的authority、effect class、continuation policy、required evidence与atomic ownership acquisition；ExternalOperation normal/cancellation联合图及phase/status mapping；Pause lifecycle的prepared/opened/claimed/consumed/cancelled edge、visibility与finality；Run lifecycle及唯一显式允许的`running <-> paused`循环与单调guards；四类互斥control outcomes；ExternalOperation pre-start/Pausing dependency DAG；identity/digest field的allocation/binding/immutability点；combined ownership、terminal closure、final-proof union和schema compatibility invariants。除显式声明且带单调guard的Run lifecycle循环外，ControlOperation、ExternalOperation、Pause lifecycle和construction success graph都必须无环。

Tracked [`scripts/validate_phase_a_control_protocol.py`](../../../scripts/validate_phase_a_control_protocol.py)使用Python标准库strict读取protocol和catalog，拒绝duplicate keys、unknown/missing type或variant、unknown phase/edge、unreachable/orphan/nonterminating phase、隐藏cycle、非原子combined ownership、nonterminal final proof、construction DAG循环、field先引用后分配、prose/catalog ID gap、stale protocol digest及required文档未引用protocol。该脚本只是pre-freeze design lint；B00仍必须把同一规则转为collectable tests、matrix coverage与fault traces。

A07从`review`提升为`ready`时，ticket、protocol和catalog exact bytes必须位于同一frozen commit；catalog保存protocol reference与SHA-256，completion同时记录protocol和catalog SHA-256。冻结后任何phase、edge、authority、evidence、outcome、DAG、field binding或compatibility变更都必须通过新的corrective ticket提升适用content version并重新绑定两个digest，不能只修改prose。

## Normalized Exact Trajectory Contract

Deterministic required trajectory将以下字段投影为ordered canonical JSON并exact比较：

- physical node与canonical Attempt kind；
- `CodeAgentSubgraph` pre-start/consume control stage与零额外Attempt副作用；
- selected route key、source/target、trigger class和guard result；
- Run/Cycle/Attempt/Transition identity、index、lineage和lifecycle；
- ControlOperation与ExternalOperation status/phase/lease/result、Pause、Human Request/Response、budget event、aggregate Backend reservation和grant lifecycle；
- semantic Backend operation status、dispatch/lookup/fetch/cancel outcome与operation binding；
- WorkspaceManifest/lease/materialization/WorkspaceSeal、dispatch receipt、immutable external result、Code Bundle与AnalysisExecutionSpec的identity/digest projection；
- artifact registration、current set/clear、managed projection、fresh Analysis worktree/subprocess和protection events；
- 每个step后的bounded state heads、current artifact IDs、budget used/remaining、nullable active ControlOperation projection、control `run_status`与领域`status`。

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
- Schema `0.4` bootstrap完整覆盖A02C01 coordinator/durability/fencing phases；bootstrap integrity failure必须区分authoritative heads仍可append的deterministic failed closure与authority不可append的`terminal_closure: unavailable`，不能把`start_run` operation failure直接当作Run status。

现有A02/A03/A03C01 focused suites继续作为Layer 0/2 regression，但A02/A03最小fallback harness不能单独计算A01 product edge coverage。

## Required A04 Recovery Scenarios

Matrix必须逐项映射：

- process退出后`human_input`、`external_result`和`recovery_decision` Pause准确恢复且最多消费一次；
- same key/same payload返回同一结果，same key/different payload拒绝，不同key竞争同一Pause只有一个claim成功；
- 错误actor/scope、Run/Pause、typed payload digest、expired Pause及runtime/policy fingerprint拒绝且无mutation；
- Human Response按claim → target allocation → old `pause_consumed` → `run_lifecycle(paused -> running)` → resume checkpoint → validator start消费旧Pause；invalid result后若A06容量仍能保留下一次validation及其后续收尾合计所需的3个Control Attempts/4条Transitions，则严格按decision → new `pause_prepared` → prepared checkpoint → `run_lifecycle(running -> paused)` → new `pause_opened` → public paused checkpoint创建新`pause_id`，否则以exact halt decision派生唯一`close_run`并从running发布`halted`，旧authorization不继承；
- `human_input` Pause使用null target，成功claim后才按A02 external control Transition恰好分配一个scheduled Human Gate validation Attempt；invalid response终结该validator，并在A06容量允许时打开下一个null-target Pause、否则安全`halted`，claim前不预分配下一Attempt，且不产生`human_gate -> human_gate`产品Transition；
- null-target `human_input` claim后、external control Transition/target Attempt完整commit前后的崩溃，若target/invalidation/Transition identity/digest已预计算且existing heads exact则保持`in_progress/materialization_pending`；缺少预授权或validator副作用结果不确定时为terminal `recovery_required`，同key重试不重复分配；`recovery_decision`只允许exact existing target的`continue_existing_target`或existing/null target的`abandon_and_halt`，null target不得分配Attempt；
- recovery continue必须证明target从未started、无side effect/unsettled resource并只启动一次；`resume_run`在reservation时冻结`continue_execution | abandon_and_halt` variant，recovery halt通过单一combined-ownership phase原子占用Pause claim与Run terminal closure owner，并按consumed → target/resource disposition → terminal eligibility → embedded terminal tail转`halted`，绝不进入running或启动target；wrong target/action、跨variant edge、route/state patch、side-effect retry以及用recovery Pause代替replay/fork全部拒绝；
- 只有stable exact `run_status: paused`、active opened Pause与包含其resulting head的public paused checkpoint可以resume；claim/cancel-owned transitional paused query、`initializing | running | completed | failed | halted`、prepared-only、缺少exact active Pause的伪`paused`和pre-A04/A06 schema Run不能resume，领域`status: pending`在正常END后对应`run_status: completed`；
- cancel只作用于latest opened Pause，并通过单一combined-ownership phase原子占用Pause cancel owner与Run terminal closure owner；existing scheduled target必须写`abandoned`，null target不得创建Attempt；`final ExternalOperation proof -> pause_cancelled -> target disposition -> resource disposition -> terminal eligibility -> run_lifecycle -> terminal checkpoint`的预计算exact side-effect-free partial保持`in_progress/materialization_pending`，停止副作用结果不确定为terminal `recovery_required`，实际head/evidence conflict进入integrity outcome，且target永不启动；
- `external_result` cancel对仍nonterminal的ExternalOperation先证明未dispatch，或持久化cancel intent并由current-epoch watchdog停止exact Backend operation、撤销lease、完成containment verify-empty；`termination_evidence_committed`仍为`cancel_requested`，只有聚合termination、lease、verify-empty、bounded drain和post-stop stability的`cancellation_evidence_committed`进入terminal `cancelled | failed`。Ownership前已经normal terminal的operation不切换branch，只允许引用包含同等级final closure的`terminal_evidence_committed`；A04只接受这两种final proof；
- `external_result`在`pause_prepared`前严格完成ExternalOperation identity stub、task、unmaterialized WorkspaceManifest、aggregate reservation、immutable core与workspace materialization，Pause期间dispatch/lookup/fetch/result/delivery不推进budget或execution head，claim后唯一settlement、`pause_consumed`、paused-to-running lifecycle和resume checkpoint全部先于target `started`；
- replay/fork通过A02C01 child bootstrap创建全新child identities，source及accepted bytes不变且不继承Pause、current pointer、authorization或accepted status；
- fork只接受coordinator对latest validated paused/terminal head与source control revision的成功CAS，并拒绝旧checkpoint、被history否定的artifact或竞争source mutation；
- append-only run lifecycle可从`initializing`完整重放到running/paused/terminal；normal `memory_report -> END`、普通non-Pause runtime failure和independent confirmed halt使用A04唯一`close_run` closure，cancel/abandon只使用其同一Run owner下的embedded tail；uncloseable integrity failure仍创建并终止deterministic `close_run` operation但返回`terminal_closure = unavailable`且不伪造failed lifecycle；terminal不可逆且bounded projection不能伪造authority；
- `start_run`、`publish_pause`、`resume_run`、`replay_run`、`fork_run`、`cancel_pause`和`close_run`在任何Run/child/Pause/checkpoint mutation前进入独立ControlOperation coordinator；逐项exact比较A02C01/A04冻结的operation variant、phase enum、穷尽allowed-edge graph、evidence与status mapping，两个process验证same-key replay、changed-payload conflict、single Pause owner、single Run terminal closure owner、lease takeover递增epoch、stale-owner写拒绝、terminal tombstone以及operation/run/domain/Pause状态不互相覆盖；还必须证明cancel ownership时只冻结resolution contracts而不伪造未来usage/head，final evidence后resolved disposition/pre-close heads只赋值一次，owner operation在closure前terminal会原子设置`terminal_closure = unavailable`；
- 每种ControlOperation type/variant的router output必须是其declared allowed-edge map的子集，所有phase可达、所有nonterminal successor穷尽且所有合法路径到达一个committed result或typed terminal tombstone；未声明branch、跨variant edge、phase skip和orphan terminal phase在B00静态验证时失败；
- END Transition、runtime failure evidence、budget/policy stop decision与operator evidence分别确定性派生exact `close_run` key/request digest；internal close、cancel embedded tail与abandon embedded tail竞争同一Run closure owner，same trigger exact replay，different trigger/contract/head conflict；ownership递增closure revision后，非owner与旧invocation capability即使原lease未过期也不能追加Run bytes，invalid-response capacity halt不得直接append terminal lifecycle。

## Required A05 Graph-managed Fake Code Agent Scenarios

Matrix必须逐项映射：

- Planner implementation gap与Coordinator code fix两种task origin；
- pre-start严格按ExternalOperation identity stub → task → unmaterialized WorkspaceManifest → aggregate reservation → immutable core → workspace materialization → Pause publication执行并在重放时幂等，且不claim/start target Attempt、不启动Backend、不注册code artifact、不创建额外Attempt/Transition或增加automatic route计数；
- aggregate Backend operation与ExternalOperation两阶段identity/core、Pause期间zero budget/execution-head drift、post-claim/pre-start唯一settlement和claim后settlement crash按materializable/in-progress、terminal recovery-required与failed三类fail-closed；
- `dispatch`使用`producer_operation_id`幂等：duplicate返回同一receipt，conflicting payload拒绝；`lookup = running | completed | unknown`都只能描述原operation且不得启动第二个operation，known status返回同一receipt reference/digest以恢复receipt-publication crash，unknown使用null receipt；`fetch_result`不得刷新预算或退款；
- aggregate hard limit、operation timeout与active operator cancellation严格经过`cancel_intent_committed -> termination_evidence_committed -> cancellation_evidence_committed`；durable watchdog通过`cancel`和ContainmentProvider执行revoke/fence → graceful terminate → bounded grace → containment kill-all → bounded output drain → verify-empty，前两个phase保持`cancel_requested`，只有final phase进入terminal `cancelled | failed`。若Pause取消开始前operation已normal terminal，则保持`terminal_evidence_committed`并验证同等级final stop-integrity closure；两类proof都允许A04推进Pause，duplicate cancel幂等，wrong operation拒绝；
- Host crash后watchdog以新`lease_epoch`只lookup/fetch/cancel原operation，旧worker的dispatch/receipt/result/workspace写入全部拒绝，unknown provider status绝不redispatch；
- dispatch前、receipt publication前后、Backend完成前后、immutable result/seal publication前后、delivery snapshot前后、claim前后与consume前后的全部crash窗口不得重复Backend operation或target Attempt；
- result重复投递same bytes幂等，conflicting bytes拒绝；competing claim只有一个consumer成功；
- valid scoped `success`经过trusted verification后注册canonical content-addressed Code Bundle，且bundle包含`backend_dispatch_receipt.json`与`workspace_seal.json`；
- `no_change`、`failed`、`needs_input`、`needs_human`、`budget_exhausted`和safe `policy_blocked`全部进入Coordinator；
- Backend自报pass但trusted verification failed/blocked/timeout时拒绝Analysis；
- out-of-scope file、path/symlink escape、Git metadata、secret/raw/accepted/control target拒绝；
- `WorkspaceManifest`或`WorkspaceSeal`缺失、digest篡改、跨Attempt复用、foreign lease、base revision/tree drift、workspace path swap及seal后filesystem变化全部fail closed；
- wrong Run/Case/Cycle/Attempt/Transition/task/operation/base/workspace/Pause/result/member digest及duplicate-key/malformed ingress在图外拒绝且不产生产品Transition；claim后预计算exact side-effect-free publication partial保持`in_progress/materialization_pending`，不可继续的不确定性为terminal `recovery_required`，实际tamper/mismatch进入integrity outcome；authority仍可验证/append时由唯一terminal owner发布`run_status = failed`，否则`terminal_closure = unavailable`；schema-valid、Attempt-attributable`failed/result_invalid`经Host验证后形成canonical failed bundle并进入Coordinator；
- non-empty unverified/partial change不能作为success；
- Human authorization scope/digest错误、已消费授权或执行中扩权必须创建新请求/Attempt或fail closed；
- multiple code attempts使用独立workspace/artifact，旧code及downstream不再current但canonical bytes保留；
- Code Bundle注册并成为current后，source wrapper才能让`commit_transition`先分配new scheduled Analysis Attempt、再提交绑定该exact target的`code_agent -> analysis_engineer` Transition，并发布绑定bundle/base/patch/effective-tree/target/Transition/runtime的`AnalysisExecutionSpec`；
- Analysis必须在fresh worktree与fresh subprocess从exact base应用verified change，并成功注册Analysis artifact；不得读取主控制仓库、复用Code Agent workspace或以module reload加载新代码；
- bundle已注册但Transition未提交时可幂等继续交接；Transition已提交但Analysis workspace未创建时可按同一spec幂等materialize；
- 预计算exact且side-effect-free的Analysis handoff partial publication保持`in_progress/materialization_pending`，target execution结果不确定时为terminal `recovery_required`；spec、patch、effective tree、runtime fingerprint或code/artifact head mismatch进入A04/A06 integrity outcome，只有authority仍可验证/append时发布`run_status = failed`，否则`terminal_closure = unavailable`；旧Analysis target不得重复`started`、不得自动abandon或retarget，同一source不得提交第二条outbound Transition；只有通过A04 source validation后才可显式replay/fork；
- Fake与future Codex fixture通过同一`dispatch`/`lookup`/`fetch_result`/`cancel` port、validator、verifier、registration及fresh Analysis入口；legacy artifact不能读取为canonical Code Agent result。

## Required A06 Budget and Stop Scenarios

Matrix必须逐项映射：

- initial forward不扣automatic route额度；每条automatic route在limit前允许、达到limit后Gate；
- Work/Control/Transition absolute ceilings及5 Control Attempt/6 Transition terminal reserve；Human Gate request与response validation分别计数，invalid retry后仍须保留下一次validation及后续收尾合计3 Control/4 Transition；
- LLM/tool/verification reservation、settlement、unsettled crash full charge和duplicate operation拒绝；
- 每个`code_agent` Attempt恰有一个`code_backend_operation` aggregate，绑定operation/task/backend/WorkspaceManifest/Pause并统一预留现有LLM/tool/active dimensions；第二份aggregate或Backend-owned counter拒绝；
- aggregate与ExternalOperation无环两阶段publication、Pause期间dispatch/lookup/fetch/result zero budget/execution-head drift、post-claim/pre-start settlement、可信actual缺失时maximum settlement和claim后settlement crash三分类fail-closed；
- aggregate maximum/timeout由durable watchdog在side effect边界强制执行并停止完整process tree；termination confirmed且usage known按actual，confirmed但usage unknown按maximum且terminal stop经唯一closure owner发布`halted`，actual超额、termination/cancel/lease revocation失败或停止后activity为control failure；Run authority仍可验证/append时发布`run_status = failed`，authority自身不可验证时`terminal_closure = unavailable`；materializable publication prefix保持`in_progress/materialization_pending`，non-materializable domain gap为terminal `recovery_required`；
- Fake fixture提供deterministic usage并与future Codex Backend走同一lifecycle；Backend receipt/tool audit/seal矛盾时按maximum结算且fail closed；
- pre-start Host setup只计Run、Backend operation结算到aggregate预留的target-Attempt与Run active dimensions但不启动Attempt、result后delivery等待不计active time、post-start trusted verification计Attempt与Run，以及所有fake clock boundary；
- first retryable technical fingerprint允许，second exact fingerprint升级；新Attempt/workspace/job/thread/operation identity不改变`code_task_context_digest`或`analysis_execution_context_digest`；
- backend版本/runtime、base、policy、verified patch/effective tree或material input evidence变化会生成新context/fingerprint；timestamp、summary、physical path或重复Human approval不会；
- `lookup`/`fetch_result`不能创建operation、刷新预算或退款；Backend、Codex thread/job与未来SandboxAgent没有独立budget、retry或stop authority；
- high/critical、ambiguous、policy/security/data及non-retryable scientific failure第一次即Gate；
- single-use grant的correct consumption，以及wrong actor/scope/route/fingerprint/target、competition、duplicate consumption和global ceiling拒绝；
- expired Pause返回`pause_expired`且无自动event/cancel，必须显式cancel/replay/fork；
- policy bytes/digest、ledger event identity/counter、reservation、fingerprint、grant和bounded projection tamper作为control integrity failure；Run authority仍可验证/append时由唯一terminal owner发布`run_status = failed`，authority自身不可验证时只允许coordinator quarantine evidence与`terminal_closure = unavailable`；
- start默认profile、resume exact policy、replay/fork计数清零，并验证A02 schema `0.2` legacy status、A04 schema `0.3`语义支持与Phase B `0.4`禁止原地迁移的兼容矩阵；
- missing token/cost保持`unknown`且不参与hard gate；
- budget stop不绕过risk、Human Gate、A03 invalidation或accepted-result保护，resource exhaustion后不调用provider/tool或accepted memory。

## Required A07 Meta-validation Scenarios

- `A07-META-001`：matrix、catalog与trace fixtures全部使用strict duplicate-key JSON，required fields、enum、stable ID和内部去重规则均fail closed；
- `A07-META-002`：catalog schema/content version独立，owner集合exact等于A01、A02、A02C01、A03、A03C01、A04、A05、A06、A07，tracked exact-byte digest与matrix声明一致；
- `A07-META-003`：catalog required IDs与required scenarios的coverage set-equal，unknown、non-required、duplicate、missing、stale或uncovered均产生deterministic nonzero report；
- `A07-META-004`：required scenario全部映射可collect且passing的pytest node IDs，skip、xfail、deselect、unknown与live-only均拒绝；
- `A07-META-005`：route、trajectory、recovery与interface层都有适用normalized expected trace及typed invariants，并执行exact semantic comparison；
- `A07-META-006`：本ticket冻结的bootstrap、Pause、fencing、watchdog、child-run、budget、artifact与Analysis publication边界全部可以通过deterministic hooks注入并得到唯一分类；
- `A07-META-007`：compatibility、capability、live-provider、benchmark与单一happy-path结果单独报告且不能计入required control acceptance；
- `A07-META-008`：B00先建立验收基础，B01–B04分别拥有并转绿其subsystem requirements，B05只在全部前置scenario已通过后生成最终zero-gap与exit evidence。
- `A07-META-009`：B00静态验证每个ControlOperation type/variant的router outputs、phase enum与allowed-edge map互相穷尽，所有phase可达、所有合法路径终结、无跨variant/skip/orphan edge；验证cancel/abandon combined-ownership不存在可观察half-owner状态、owner operation terminal不遗留pending closure，并交叉验证A04引用的A05 active-cancellation或already-normal-terminal proof确为terminal及B02拥有`close_run`实现。
- `A07-META-010`：tracked Control Protocol exact bytes是ControlOperation、ExternalOperation、Pause/Run lifecycle的phase/status/edge/authority/evidence/ownership/outcome/dependency/field-binding/compatibility唯一机器枚举；strict design validator与catalog-bound SHA必须拒绝prose drift、stale snapshot、unknown branch、Pause reopen、hidden cycle、circular construction和先引用后分配。

## Fault Injection and Crash Outcomes

Required failpoints固定在以下durable publication boundaries：

- A02C01 coordinator `BEGIN IMMEDIATE`前、key/operation/target locator/policy digest/initial `lease_epoch` transaction提交后但Run root创建前，以及每个operation phase/result compare-and-set前后；
- Run root exclusive-create与parent sync、policy file publication与sync、`Run created(initializing)`、`policy_initialized`、bootstrap `decision_recorded`、initial Cycle、Planner Attempt、A03 initial invalidation、START Transition、`run_lifecycle(initializing -> running)`和checkpoint前后；
- worker lease takeover/epoch递增前后，以及旧owner尝试phase、ledger、workspace、receipt/result publication；
- ExternalOperation identity stub/initial epoch、task publication、unmaterialized WorkspaceManifest publication、aggregate reservation、immutable core CAS、workspace materialization/lease前后；
- internal `publish_pause`的每个exact phase：operation reservation/lease、`pause_prepared`、dependency/ExternalOperation one-time binding、prepared checkpoint、running-to-paused `run_lifecycle`、`pause_opened`、public paused checkpoint和operation result前后；
- Pause `opened`后、external-operation dispatch authorization、Backend dispatch、`BackendDispatchReceipt` publication、Backend completion、WorkspaceSeal与immutable result publication前后；
- watchdog lease takeover、`cancel_intent_committed`、Backend cancel、write-lease revocation、containment kill-all、verify-empty、`termination_evidence_committed`与final `cancellation_evidence_committed`前后，以及normal `terminal_evidence_committed`已先于Pause cancel完成的边界；
- delivery snapshot前后，以及`resume_run`的`resume_disposition_committed`和两条variant：continue的Pause ownership、`pause_claimed`、prestart allocation/invalidation/Transition/settlement、`pause_consumed`、paused-to-running lifecycle、resume checkpoint、invocation authorization、stable boundary与result，以及abandon的Pause/Run combined ownership、`pause_claimed`、`pause_consumed`、target/resource disposition、terminal eligibility/lifecycle/checkpoint/result每个phase前后；
- budget `decision_recorded`后但Transition或resource reservation前；
- `grant_consumed`前后以及其后target Attempt allocation/A03 invalidation/Transition append完整commit前；预计算exact partial保持`in_progress/materialization_pending`，缺少预授权时为terminal `recovery_required`，grant不退款且target不启动；
- invalid Human Response的repause `decision_recorded`、new `pause_prepared`、prepared checkpoint、running-to-paused lifecycle、new `pause_opened`和public paused checkpoint前后，以及capacity halt decision、deterministic `close_run` reservation/closure ownership前后；
- replay/fork的source snapshot、source-control-revision CAS及每个child root/policy/ledger/lineage/bootstrap/lifecycle/checkpoint/result phase前后；
- `close_run` deterministic key/request、Run terminal closure ownership/revision、旧invocation与非owner stale-write拒绝、terminal eligibility、normal END或failure/stop evidence、terminal lifecycle、terminal checkpoint与result phase前后，different-trigger competition，以及损坏head无法append lifecycle的边界；
- `resource_reserved`后但`resource_settled`前；
- Transition/invalidation commit后但target Attempt `started`前；
- Code Bundle member/registry/current publication前后，以及bundle current后但Analysis Transition提交前；
- Analysis Transition提交后但`AnalysisExecutionSpec` publication、fresh workspace materialization、fresh subprocess启动或Analysis artifact publication前后；
- artifact history/index/projection publication或bounded-state sync出现partial/corrupt head。

Bootstrap fault scenarios必须证明coordinator transaction先于任何Run root bytes，且empty-root、policy-only、ledger、lifecycle和checkpoint prefix只有同一operation/current epoch可以确定性继续，任何冲突或side-effect prefix均fail closed。Pause publication scenarios必须证明prepared checkpoint不会引用未来opened head、opened不会引用未来public checkpoint，并按非对称closure形成唯一active Pause。Pause claim scenarios必须证明initial reservation不修改Pause/Run closure owner，continue只取得Pause owner，cancel/abandon则在一个事务和一个combined-ownership phase中同时取得Pause与Run closure owner，任一CAS失败不留下半个owner；ownership提交后只有原operation/current epoch可materialize exact预计算claim record，且claim后的不确定副作用不能自动重跑。Resume variant在reservation后不可改变，abandon branch不进入running。Transition fault scenarios必须证明scheduled target allocation先于A03 invalidation、invalidation先于committed Transition append。Invalid-response scenarios必须证明旧Pause一经`consumed`不再打开，prepared-only或未完成public checkpoint的新Pause不接收输入，capacity halt只能经deterministic `close_run`。External-result scenarios还必须证明：ExternalOperation stub先于task/manifest/reservation/workspace bytes，immutable core先于workspace materialization，全部在Pause `prepared`前完成；Pause期间dispatch/lookup/fetch/result/delivery evidence不推进budget或execution head，唯一`resource_settled`后于claim且先于target Attempt `started`；hard limit/timeout/cancellation由current-epoch watchdog和strict containment停止完整process tree且绝不redispatch，A04在active cancellation的final `cancellation_evidence_committed`或ownership前已存在的normal `terminal_evidence_committed`通过完整验证前不能取消Pause。Fresh Analysis fault scenarios必须证明exact side-effect-free spec publication可幂等materialize，但任何spec/head/digest冲突都不启动旧target、不retarget、不从同一source提交第二条outbound Transition，并按A04/A06区分appendable failed closure与`terminal_closure = unavailable`。Standalone terminal scenarios必须证明END/failure/independent-stop evidence先于Run closure ownership和`close_run` lifecycle；cancel embedded terminal scenarios则证明cancel request与resolution contracts先于combined ownership，final stop/usage/settlement evidence先于terminal eligibility和lifecycle。两者都必须证明terminal checkpoint先于result、different trigger不能创建第二owner、closure revision阻止非owner写，且损坏authority不伪造ledger closure。

每个failpoint必须记录预期类别：

- durable safe boundary与`materializable_publication_prefix`允许相同idempotency request保持`in_progress`并准确继续一次；
- `non_materializable_domain_gap`或副作用结果不确定为terminal `recovery_required`；未持有Run closure时closure为`not_applicable`，已持有terminal owner时必须同步变为`unavailable`而非遗留pending；已证明完成的policy/operator stop经唯一closure owner为`halted`；termination/lease/post-stop或integrity failure在Run authority仍可验证/append时发布`run_status = failed`，authority自身不可验证时ControlOperation `failed`且`terminal_closure = unavailable`；
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

1. **B00 — Acceptance Foundation**：先消费frozen `CONTROL_PROTOCOL_0_4.json`并实现protocol/catalog/matrix strict schemas、type/variant/edge与dependency-DAG validator、owner/version/digest validator、pytest node collection、normalized trace codec与failpoint registry skeleton；创建只包含已经collectable meta tests的matrix骨架，并分离construction/owned/final validation modes，不得从prose重建另一份状态图，也不得用placeholder、skip或xfail伪造已覆盖。
2. **B01 — Execution 0.4 Control Foundation**：BudgetPolicy/ledger、append-only run lifecycle、bounded projection、trusted clock、canonical validators及execution/artifact/checkpoint cross-head integrity，并增加及转绿B01-owned scenarios。
3. **B02 — Durable Control Operations**：实现`<output_root>/.lqcd/control_operations.sqlite`的FULL durability profile、`ControlOperation 0.1` type/variant allowed-edge graph、`lease_epoch` fencing、project-owned start/resume/replay/fork/cancel、internal `publish_pause`与`close_run`、single Run terminal closure ownership/revision及cancel/abandon的atomic combined-ownership phase、invocation capability fencing、`pause_prepared`/`pause_opened`双checkpoint Pause publication、child saga、tombstone、result replay和process-restart recovery，并增加及转绿B02-owned scenarios。
4. **B03 — Graph-managed Fake Code Agent**：`CodeAgentSubgraph`、`CodingBackend` port、coordinator-owned`ExternalOperation 0.1`、durable watchdog、deterministic ContainmentProvider fixture、`FakeCodingBackend`、图外ingress validator、trusted verification、content-addressed bundle和fresh Analysis handoff，并增加及转绿B03-owned scenarios。
5. **B04 — Target Product Topology and Budgeted Loops**：把B03接入A01 edges、Coordinator四层fallback、Human Gate return、A03 invalidation、A06 aggregate Backend reservation/admission/grant和统一stop/outcome matrix；所有initial/Transition/resume target start必须消费B02签发并验证closure revision的invocation-lifetime capability，并增加及转绿B04-owned scenarios。
6. **B05 — Acceptance Integration and End-to-End Harness**：完成normalized traces、跨子系统fault/concurrency tests、compatibility regression、CLI smoke和最终zero-gap evidence；不得把B01–B04遗留的未实现required scenario延后用一个happy-path替代。

Dependency顺序固定为B00；B01 depends on B00；B02 depends on B00/B01；B03 depends on B00–B02；B04 depends on B00–B03；B05 depends on B00–B04。每份implementation ticket必须自行冻结Allowed Files、Do Not Touch、migration边界、owned requirement IDs和focused verification，不得把六份工作合成未审查的大型ticket。

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
- `ControlProtocol 0.4`、strict design validator、catalog-bound protocol SHA-256及B00消费边界；
- A01、A02、A02C01、A03、A03C01、A04–A07 required scenario inventory；
- exact trajectory、fault/concurrency、legacy和parallel边界；
- B00–B05拆分及Phase B exit gate；
- 受影响验收/阶段文档同步；
- 独立`docs/tickets/completions/A07_COMPLETION.md`及completion索引更新。

## Acceptance Criteria

- ticket内没有待确认架构问题、未决占位符或内嵌执行记录；
- A01每个target row、guard和forbidden behavior都有明确的required coverage rule；
- A02/A03/A03C01冻结合同以及A02C01/A04–A07的每个required downstream/meta requirement都被catalog保留，没有由实现者自行抽样；
- deterministic control test使用exact normalized trace，capability eval不能替代control acceptance；
- process restart、independent-client claim和每个durability boundary都有确定的success/fail-closed结果；
- mutation coordinator与LangGraph checkpoint物理及authority分离，FULL durability profile、same-key/different-payload、lease epoch takeover/stale-owner拒绝和operation result replay均由两个独立process确定性验证；
- Fake Code Agent完整经过graph-managed pre-start、A04 Pause、A06 aggregate settlement、trusted verification、Code Bundle与fresh Analysis handoff，且不调用Codex SDK或完整SandboxAgent；
- legacy只能作为compatibility entrypoint，parallel明确不属于Phase B；
- machine-readable protocol和matrix能够机械拒绝unknown/unreachable/nonterminating/cyclic phase graph及missing/stale/uncollectable/skipped coverage；
- B00–B05可以直接起草而无需重新决定实施顺序或职责边界；
- 本ticket执行不产生runtime/tests/configs/Phase B ticket diff。

## Pre-freeze Review Gate

本ticket从`review`提升为`ready`前必须确认：

- YAML保持`status: review`，直到A02C01与A04–A07完成交叉审查、catalog核验并获得用户最终确认；
- ticket内没有待确认架构问题、未决占位符或内嵌执行记录；
- `PHASE_B_REQUIREMENT_CATALOG.json`通过strict JSON、content version、unique ID、owner/source和required-set验证；owner集合exact等于A01、A02、A02C01、A03、A03C01、A04、A05、A06、A07，且每个冻结/显式required ID恰有一个catalog entry；
- `CONTROL_PROTOCOL_0_4.json`通过strict JSON、type/variant/phase/edge穷尽、reachability/termination、declared-cycle、ownership、final-proof、dependency DAG、field-binding和compatibility验证；catalog中的protocol reference/digest与exact bytes一致；
- A01 route/forbidden、A02 identity/lifecycle、A03 registry/invalidation、A03C01 heads、A02C01 bootstrap/durability/fencing、A04–A06 scenarios与A07 meta requirements都已映射到machine-checkable coverage rule，matrix只能引用catalog ID；
- A07 ticket正文、protocol与catalog exact bytes将在同一frozen commit中，completion记录protocol/catalog version与SHA-256；
- A02C01与A04–A06之间没有需要改变bootstrap、run lifecycle、Pause、lease fencing、ExternalOperation、Code Agent、budget或stop matrix语义的未决冲突；
- A05要求的Backend/workspace/fresh Analysis scenarios和A06要求的aggregate/active-time/semantic fingerprint scenarios均逐项进入matrix coverage；
- dependency、Allowed Files与Do Not Touch无冲突，所有相对Markdown links和Read First仓库路径有效；
- Phase A Overview、Docs Index和Current State一致记录A02C01与A04–A07为`review`；
- review diff不包含runtime、tests、evaluation、configs、dependency或provider改动，且B00–B05 ticket文件不存在。

## Verification

执行本design ticket时只运行静态、文档与scope检查：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

还必须验证：

- ticket在`ready`之后只变更YAML lifecycle metadata，正文与执行前冻结commit一致；
- A01–A06及A03C01均已`completed`，它们的ticket正文未修改；
- Required Documentation Updates已同步，Phase A被一致标记为完成，Phase B Overview记录B00–B05的拆分、依赖与entry/exit gate；
- `docs/tickets/completions/A07_COMPLETION.md`已建立并加入completion index；
- B00–B05 ticket文件仍不存在，本ticket没有提前执行Phase B；
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
- Phase A/Phase B Overview：A07 completion、B00–B05拆分与Phase B entry/exit；
- `docs/README.md`、`docs/REPO_CURRENT_STATE.md`和`docs/DECISION_LOG.md`；
- 独立completion record与completion index。
