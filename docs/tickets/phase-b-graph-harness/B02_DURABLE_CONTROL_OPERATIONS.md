---
ticket_id: B02
phase: phase-b-graph-harness
status: draft
type: implementation
depends_on: [B00, B01]
---

# 实现 Durable Control Operations

## Goal

基于B00机器协议与B01 Execution `0.4` foundation，实现单一project-owned SQLite coordinator、`ControlOperation 0.1` guarded graph、lease/capability fencing、Run bootstrap、Pause/Resume/Replay/Fork/Cancel、internal advance/publish/close/interrupt、terminal ownership、child saga与process-restart recovery，并让B02拥有的30项requirements通过construction-mode验收。

B02完成后，B00–B02累计required映射覆盖必须为56项，`requirements.remaining=75`且`phase_b_complete=false`。B02只建立durable control authority与通用typed handoff；它不实现Code Agent backend或A01 target product graph。

所有construction数量仅对应本票`validation_stage=construction`证据。全局`requirements.passed/passed_ids=null`，`requirements_zero_gap=false`；原owner下新增的final scenarios和B00独立runtime obligations必须在final重新验证。

## Why

LangGraph checkpoint不能同时充当idempotency、mutation ownership、Pause claim、Run terminal owner和external side-effect fencing。A02C01/A04已冻结一个与per-Run checkpoint物理分离的coordinator transaction domain，以及每个operation的phase、guard、ownership、reservation overlay和terminal outcome。

B02把这套协议实现为可重启、可竞争、可fail closed的项目入口，供B03 ExternalOperation和B04产品拓扑复用；不允许后续子系统各自引入SQLite表、进程内lock或隐式checkpoint mutation authority。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/tickets/README.md`
- `docs/tickets/corrections/README.md`
- `docs/ARCHITECTURE.md`
- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/EVALS_AND_OBSERVABILITY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md`
- `docs/tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md`
- `docs/tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md`
- `docs/tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md`
- `docs/tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md`
- `docs/tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md`
- `docs/tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json`
- `docs/tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json`
- `docs/tickets/phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md`
- `docs/tickets/phase-b-graph-harness/B01_EXECUTION_0_4_CONTROL_FOUNDATION.md`
- `docs/tickets/completions/B00_COMPLETION.md`
- `docs/tickets/completions/B01_COMPLETION.md`
- B00/B01实际新增的`src/lqcd_agent/control/`与`tests/phase_b/`文件

## Frozen Inputs and Entry Conditions

- B00和B01必须为`completed`；B01 construction report必须exact显示11 owned passed、累计26 covered和105 remaining。
- Protocol/catalog versions与exact SHA-256保持B01所列值；B02不得从A04 prose重建operation phase graph。
- B01的record/clock/projection/integrity APIs、B00 failpoint IDs和generated protocol是实现输入；若实际API无法表达frozen protocol，停止并创建corrective ticket，不在B02新增隐式variant。
- 执行前记录full-suite、B00/B01 focused suites和B01 final expected-failure基线。

## Scope

- 在`<output_root>/.lqcd/control_operations.sqlite`实现唯一coordinator transaction domain、FULL durability profile、closed schema和deterministic migration-free initialization；
- 实现十二种frozen ControlOperation type/variant、reservation overlays、guarded phase transitions、canonical request/result replay和terminal tombstones；
- 实现idempotency key/request digest、monotonic phase revision、operation lease与invocation capability lease fencing；
- 实现public `start_run`、`resume_run`、`replay_run`、`fork_run`、`cancel_pause`以及internal `advance_run`、`publish_pause`、`close_run`、`resolve_external_interrupt` trusted APIs；
- 实现schema `0.4` bootstrap及其可信admission、Run lifecycle、Pause lifecycle、Human Response external control Transition、recovery decision和single Run terminal closure owner；
- 实现Replay/Fork source proof、source revision CAS、child lineage/root/policy/bootstrap saga；
- 实现generic typed target/resource/source preparation ports与capability activation fencing，供B03/B04插入真实Code/graph行为；
- 实现same-operation materialization、recovery-required、failed/unavailable closure分类和process-restart recovery；
- 增加two-client/two-process claim、owner、lease和same-key/different-payload tests；
- 增加B02 matrix slice、normalized traces、failpoint hook bindings和fresh pytest evidence。

## Non-goals

- 不实现`CodingBackend`、Fake Backend、workspace materialization、trusted code verifier、canonical Code Bundle或fresh Analysis subprocess；
- 不把generic external/resource binding伪装成A05 Code Agent evidence；
- 不接入A01产品edges、四层fallback、Human Gate产品return、memory/report terminal topology或后续产品route/resource/grant/stop admission；start/replay/fork bootstrap admission属于本票；
- 不修改A03 invalidation policy或注册B03/B04 domain artifacts；
- 不改变legacy schema `0.2` CLI/default graph，不原地resume或migrate`0.2/0.3` Run；
- 不选择distributed lock/production database、认证系统或远程checkpoint；
- 不运行live provider、Codex SDK、raw data或真实external process kill；
- 不让真实matrix通过final mode。

## Migration Boundary

- Coordinator数据库只为fresh Phase B output root建立，不扫描或升级existing database；schema/version mismatch、unknown table/column contract或partial bootstrap必须fail closed。
- Schema `0.2` source只允许经validated root inputs replay；不能resume或fork。Schema `0.3`不原地resume/migrate，来源验证通过且满足相应replay/fork资格时可创建`0.4` child。只有exact supported `0.4` runtime/policy fingerprint可resume。
- Replay/Fork总是创建新Run root和全新identities；source bytes、checkpoint、current pointers、Pause、authorization和accepted status不复制、不改写。
- B02 public interfaces接受project-owned Run locator和typed request，不接受raw checkpoint/thread ID、arbitrary state patch、route override、force overwrite或caller-selected filesystem root。
- Existing legacy CLI和Run artifacts保持byte-for-byte兼容；B02只新增versioned interface，不静默切换默认入口。

## Owned Requirement IDs

B02 slice固定为以下30项：

```text
A02-TRANSITION-001
A02-CONSUME-001
A02-HUMAN-001
A02C01-BOOTSTRAP-001
A02C01-BOOTSTRAP-002
A02C01-BOOTSTRAP-003
A02C01-BOOT-004
A04-PAUSE-001
A04-PAUSE-002
A04-PAUSE-003
A04-PAUSE-004
A04-PAUSE-005
A04-PAUSE-006
A04-PAUSE-007
A04-PAUSE-008
A04-PAUSE-009
A04-PAUSE-010
A04-PAUSE-011
A04-PAUSE-012
A04-PAUSE-013
A04-PAUSE-014
A04-PAUSE-015
A04-PAUSE-016
A04-PAUSE-017
A04-PAUSE-018
A04-PAUSE-019
A04-PAUSE-020
A04-PAUSE-021
A06-BUDGET-012
A06-BUDGET-014
```

- B02 scenarios可以使用generic deterministic target/resource/source adapters证明operation ordering，但不得声明A05 backend、A01 product route或B04 budget stop已经实现。
- Owned refs union必须set-equal为30项；B00–B02累计映射covered必须exact为56项，remaining为75项。
- Cross-contract scenario如果需要尚未实现的B03/B04 semantics，B02只证明本ticket拥有的control half，并在typed expected result中明确`external/domain adapter`; 不得用skip、placeholder或虚假canonical artifact填补后续ownership。

## Proposed File Layout

```text
src/lqcd_agent/control/
  coordinator.py
  operations.py
  leases.py
  capabilities.py
  checkpoints.py
  pause.py
  children.py
  interfaces.py
tests/phase_b/
  test_durable_control_operations.py
  test_control_operation_recovery.py
  helpers/process_client.py
  expected_traces/
```

只在现有B01模块职责明确适合时扩展该模块；不得复制generated phase graph或另建per-subsystem coordinator。

## Allowed Files

- `docs/tickets/corrections/B02_MAINTENANCE.md`：仅在发生本票范围内的contract-preserving局部修复时新增；同票后续条目只追加，不改写已记录事实；
- `docs/tickets/corrections/README.md`：仅追加本票maintenance链接，不改写已有索引项；
- `docs/tickets/phase-b-graph-harness/B02_DURABLE_CONTROL_OPERATIONS.md`：进入`ready`后只允许更新YAML lifecycle metadata；
- B00/B01已建立的`src/lqcd_agent/control/`文件：仅限复用schema、record、clock、projection、integrity和generated protocol接口；
- `src/lqcd_agent/control/coordinator.py`；
- `src/lqcd_agent/control/operations.py`；
- `src/lqcd_agent/control/leases.py`；
- `src/lqcd_agent/control/capabilities.py`；
- `src/lqcd_agent/control/checkpoints.py`；
- `src/lqcd_agent/control/pause.py`；
- `src/lqcd_agent/control/children.py`；
- `src/lqcd_agent/control/interfaces.py`；
- `src/lqcd_agent/graph/state.py`：仅限schema `0.4` adapter与A02 target allocation/consumption复用；
- `src/lqcd_agent/artifacts/registry.py`：仅限operation-time cross-head/preflight adapter，不改变slot policy；
- `tests/phase_b/`：仅限B02 slice、operation/process fixtures、expected traces与failpoint bindings；不得削弱B00/B01 tests；
- `tests/phase_b/acceptance_matrix.json`及registry bindings：允许为本票实现对应的runtime义务追加`validation_stage=final`场景，引用本票或已存在前置slice的原owner（包括B00 meta IDs）；不改ownership、不预填后续slice、不修改B00冻结schemas/obligations/必需check清单；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`；
- `docs/tickets/completions/B02_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/ARCHITECTURE.md`；
- `docs/STATE_SCHEMA.md`；
- `docs/ARTIFACT_CONTRACTS.md`；
- `docs/SECURITY_AND_DATA_POLICY.md`；
- `docs/EVALS_AND_OBSERVABILITY.md`；
- `docs/VERIFICATION_GUIDE.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

已有completion/correction记录及其历史内容保持不变；Allowed Files仅为本票maintenance新记录/追加条目与corrections index追加链接保留例外，不授权修改前置票据的记录。

- Phase A frozen tickets/protocol/catalog、completed records、milestone和tag；
- B00/B01 frozen ticket bodies及B03–B05 ticket正文；
- B00 generator/validator contract和B01 owned requirement semantics；
- current product topology files`src/lqcd_agent/graph/analysis_graph.py`、`routing.py`、`nodes.py`和legacy runner；
- `src/lqcd_agent/agents/`、`src/lqcd_agent/coder/`、`src/lqcd_agent/llm/`、`src/lqcd_agent/memory/`、`src/lqcd_agent/report/`、`src/lqcd_agent/tools/`、`src/lqcd_agent/analysis/`和`src/lqcd_agent/analysis_programs/`；
- B02执行前已有的`tests/test_*.py`；
- `pyproject.toml`、dependency/config/provider/evaluation/raw data/repository outputs/accepted artifacts/human decision files；
- A05 canonical Code schemas、Backend/containment实现和A01/B04 graph routes；
- external services、remote databases、distributed locks或network。

## Requirements

本票继承B00的validation stages、final obligations和closed report。追加final runtime证据必须保留原requirement owner及独立case集合；对应production hook须有本次实际触发记录、passing nodeid和exact trace，不能以inventory或静态检查替代。

### 1. Coordinator Durability and Transaction Authority

- 所有public/internal mutation在任何Run/Pause/checkpoint/child bytes或外部 side effect前，先在唯一`coordinator_sqlite`域内reserve exact operation key/request digest/type/variant/overlay/owner/phase revision/lease epoch。
- SQLite write path使用`BEGIN IMMEDIATE`等价single-writer transaction、foreign keys/constraints及A02C01 FULL durability profile；database file、Run root exclusive-create、parent directory和published file sync边界必须可注入fault并验证。
- Coordinator与per-Run LangGraph checkpoint物理分离；checkpoint/history/state不能分配operation owner、lease或Run terminal owner。
- Same key/same canonical request只重放原phase/result；same key/different digest、different source/head/variant或unknown schema确定性冲突且无mutation。
- Operation phase/edge/guard/outcome/authority/effect/continuation/reservation overlay只能由generated Control Protocol驱动；unknown、skip、cross-variant、orphan和post-terminal mutation拒绝。

### 2. Bootstrap and Invocation Capability

- B02拥有start/replay/fork共享的可信bootstrap admission。它使用B01的allowlisted policy、canonical records和validator计算一条initial route的准入，证明一个initial Cycle、一个Planner Work Attempt、一条START Transition及完整terminal reserve符合absolute ceilings；结果绑定本次operation冻结的policy和Run/child输入，在identity allocation前持久化`decision_recorded(allow, action=bootstrap_initial_route)`。不满足条件按冻结合同拒绝/失败，不默认allow。
- Caller、Agent、Backend或test adapter不能直接传入`allow`作为准入authority；测试只能提供经可信入口验证的输入与clock/fault。Replay/Fork复用同一admission入口，计数来自全新child而非source或调用方自报。

- `start_run`严格按coordinator reservation → root/policy/Run bytes → initializing lifecycle → policy initialization/admission decision → initial Cycle/Planner Attempt/invalidation/START Transition → running lifecycle/checkpoint → Planner capability preparation → same-operation committed result activation顺序执行。
- Empty-root、policy-only、partial JSONL和每个publication prefix必须分类为same-operation materializable、recovery-required、failed closure或unavailable closure；operation failure不能直接冒充Run lifecycle。
- Worker mutation lease与target invocation capability lease分离，均使用monotonic epoch；committed authorization在producer worker lease expiry后仍有效，started intent或side-effect uncertainty后不得被新worker自动接管重跑。
- Query/lookup不得续租、写head或激活capability；旧epoch、foreign head、terminal revision变化和double acquire必须fail closed。

### 3. Transition, Pause and Resume

- Every ordinary noninitial Transition由`advance_run`拥有，按target scheduled allocation → exact invalidation → Transition commit → optional target preparation → committed result → capability activation执行；target side effect前不允许started。
- Human input使用null target Pause；claim后由A02 external control Transition恰好分配一个Human Gate validator Attempt，随后按frozen consumed/running checkpoint/start order执行。该external transition不计A01 product edge。
- Pause publication严格形成`pause_prepared -> prepared checkpoint -> running-to-paused lifecycle -> pause_opened -> public paused checkpoint`非对称closure；prepared/opened/claimed/consumed/cancelled/aborted/interrupted/quarantined shapes均closed且head-exact。
- `resume_run`只接受stable exact paused+opened+public checkpoint+runtime/policy fingerprint；reason-specific actor/scope/Run/Pause/payload/deadline mismatch无mutation失败。
- Resume在reservation冻结`continue_execution | abandon_and_halt`。Continue只取得Pause owner；abandon原子取得Pause与Run owner并使用embedded terminal tail，不进入running或启动target。
- `RecoveryDecision.continue_existing_target`仅限冻结允许列表中的existing scheduled ordinary target，并须满足从未`started`、唯一committed inbound Transition、完整current heads、无业务副作用、无unsettled resource或external operation，以及适用的原preparation proof。`code_agent`和`legacy_codex_handoff`始终在claim前拒绝，不因B03实现而放宽；拒绝本身不改变Pause或自动停止。Null target仅允许`abandon_and_halt`，不分配Attempt。B03正常Code Agent结果恢复使用`external_result`路径，不扩展`recovery_decision`权限；既有timeout/interrupt合同保持不变。
- Invalid Human Response在B04 budget capacity接入前，只通过generic decision input验证frozen repause/halt operation ordering；B02不得自行决定容量或grant。

### 4. Cancellation, Interrupt and Terminal Ownership

- 每个Run只有一个fenced terminal closure owner。`close_run`、cancel、interrupt、abandon和post-claim consumption failure共享同一owner/revision域；没有可观察half-owner、owner operation terminal后pending closure或第二terminal operation。
- `cancel_pause`只处理latest opened cancelable Pause；typed-null/cancel/normal/preexisting winner tuple与machine guard exact一致。Preexisting cancel/interrupt winner只读观察且不修改领域owner。
- `resolve_external_interrupt`在B02实现protocol-owned generic arbitration、Pause/Run owner acquisition和terminal disposition total function；B03才实现ExternalOperation backend evidence。Typed absent/present external/resource/source unions不得cross-wire。
- `close_run`必须证明ExternalOperation absent、safely terminal/detached或frozen normal attached case；unresolved live external trigger只允许derive exact interrupt operation。
- Safe+appendable integrity failure才可发布failed lifecycle；safe proven policy/operator stop可halted；stop/authority proof不完整只能same-owner unavailable tombstone，不伪造lifecycle/artifact。
- Normal END、non-Pause failure与independent stop使用`close_run`；cancel/interrupt/abandon/post-claim failure只用原operation embedded tail。

### 5. Replay, Fork and Child Saga

- Replay/Fork在任何child bytes前冻结field-disjoint source proof、exact source Run/lineage、policy selection和initial Planner inputs。
- Replay source policy由authoritative presence/absence/support evidence分类；caller不能把versioned source伪装legacy或选择任意child policy。
- Fork只接受latest validated stable paused/terminal head与source control revision CAS；running、legacy `0.2`、stale checkpoint、invalidated evidence和competing source mutation拒绝。
- Child使用fresh Run/Cycle/Attempt/Transition/ledger/registry/checkpoint/current identities，从START bootstrap并执行本票可信admission；source immutable bytes保持不变，不继承Pause、authorization、accepted state或budget counts。
- Child checkpoint后prepare Planner capability，且只有创建child的same-operation committed result可激活。

### 6. Recovery, Concurrency and Evidence

- 所有B00 registry中归属B02的publication boundaries必须有真实hook；fault outcome只允许exact same-operation continuation或frozen typed fail-closed class。
- Process restart必须启动新Python process并重新打开coordinator、Run和checkpoint；不得复用同一对象或MemorySaver宣称durability。
- Pause claim、idempotency、lease takeover、source CAS和Run terminal ownership至少使用两个independent clients/processes验证唯一winner及所有loser状态。
- Normalized traces保留operation phase/revision/epoch、owner、Pause/Run lifecycle、heads、capability、child lineage与exact branch tuple；不能只断言exit code/final status。
- Construction report使用B00的`PhaseBAcceptanceReport 0.1`：`construction.required/covered/passed=30`，`requirements.required=131`、`requirements.covered=56`、`requirements.remaining=75`、`requirements.passed/passed_ids=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。累计covered只表示映射，不能从前置ticket历史结果推断本次全局passed。

## Deliverables

- single-domain durable SQLite coordinator及schema/init/durability checks；
- frozen ControlOperation router/phase executor、lease和capability fencing；
- public/internal project-owned control APIs；
- schema `0.4` bootstrap、Pause/Resume/Cancel、Replay/Fork child saga和terminal ownership；
- restart/concurrency/fault harness与B02 30项matrix slice；
- construction/final expected-failure reports；
- B02 completion record与必要核心文档更新。

## Acceptance Criteria

- Coordinator先于任何Run bytes或external effect取得authority，且与checkpoint物理/语义分离；
- 十二variant、allowed edges、branch guards、effective overlays、owner acquisition、terminal outcomes和tombstones与generated protocol exact一致；
- same-key replay、different-payload conflict、lease takeover/stale owner、capability expiry与double-consume均确定性通过；
- 三种Pause reason、continue/abandon、cancel、close、interrupt generic branches及Replay/Fork在fresh process restart后exact once；
- 两个process竞争Pause/Run/source/operation owner恰有一个winner，没有half ownership或duplicate terminal lifecycle；
- Existing schema `0.2` runtime与A02/A03 behavior不变，未实现的B03/B04能力没有被B02 evidence声称；
- B02 construction owned/covered/passed exact为30项，累计映射covered 56项，remaining exact 75项；construction pass、final expected-fail且`phase_b_complete=false`；
- Phase B focused、A02/A03 regression、完整pytest、compileall、links、metadata、scope、stale docs和diff checks通过；
- 没有live provider、network、Codex SDK、raw data、repository outputs或production external process side effect。

## Verification

```bash
B02_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b02-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest --collect-only -q tests/phase_b
pytest -q tests/phase_b/test_durable_control_operations.py
pytest -q tests/phase_b/test_control_operation_recovery.py
python scripts/validate_phase_b_acceptance.py \
  --mode construction \
  --ticket B02 \
  --evidence-dir "$B02_EVIDENCE_DIR/construction" \
  --report "$B02_EVIDENCE_DIR/construction-report.json"
! python scripts/validate_phase_b_acceptance.py \
  --mode final \
  --evidence-dir "$B02_EVIDENCE_DIR/final" \
  --report "$B02_EVIDENCE_DIR/final-negative-report.json"
pytest -q tests/test_execution_identity.py tests/test_artifact_registry.py tests/test_state_schema.py
pytest -q
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

此外必须单独运行并记录：

- fresh-process restart fixtures；
- two-process same-key/different-payload、Pause claim、terminal owner、source revision和capability lease races；
- SQLite FULL/file+directory sync fault suite及partial JSONL rejection；
- B02 construction owned/covered/passed exact set、累计56项coverage和75项ordered remaining；
- all B02 failpoint registry bindings与每个expected outcome class；
- schema compatibility：合法`0.3` source replay/fork生成`0.4` child、`0.2` fork和`0.3`原地resume拒绝，source bytes不变；
- bootstrap admission负向测试：绕过可信准入、caller/test注入allow、policy/head/binding不一致均拒绝；start/replay/fork均证明decision先于initial identity allocation；
- no-migration、Allowed Files/Do Not Touch和stale-documentation audit。

所有evidence、database、Run root和checkpoint必须位于新的`/private/tmp/lqcd-agent-b02-*`。

Final negative report必须分别列出exact 75项`requirements.remaining`、`runtime_evidence`缺口和`exit_checks`缺口；缺失后续scenario/adapter是预期缺口，已有检查的解析、collection或证据错误不能被忽略。Final preflight未具备时不提前运行B05全套检查。

## Stop Conditions

既有合同及Allowed Files内的局部bug允许修复，但必须使用本票maintenance路径留痕；缺失前置功能、需要扩大范围或改变架构/schema/public contract/验收边界时停止，先创建并批准corrective ticket，不用maintenance授权新功能。

- B00/B01未完成或其exact contract/evidence不满足入口；
- 需要改变Control Protocol phase/edge/owner/overlay/branch/outcome、A02C01 bootstrap、A04 Pause/terminal或A06 compatibility semantics；
- bootstrap admission必须等待B04或依赖caller/test注入allow，而不能由B02可信入口独立产生；
- frozen protocol无法由单一SQLite transaction domain实现，或必须依赖LangGraph checkpoint/进程内lock作为mutation authority；
- 需要实现B03 backend/workspace或B04 product topology/budget decision才能通过B02 owned scenario，而generic typed adapter不足以诚实证明control half；
- 需要自动迁移、改写source Run、暴露raw checkpoint/state patch/force overwrite或新增外部system/dependency；
- 需要扩大Allowed Files、触碰Do Not Touch或修改B03–B05 ticket正文；
- recovery/concurrency只能用真实sleep、概率race、same-process object或skip/xfail证明；
- baseline/full regression无法在Allowed Files内以contract-preserving local fix解决。

触发任一条件时停止B02并保留证据；合同/架构改变必须另开corrective ticket。

## Required Documentation Updates

- 若执行中发生既有边界内的局部修复，新增本票`docs/tickets/corrections/B02_MAINTENANCE.md`并向corrections index追加链接，记录问题、根因、改动、验证及关联ticket；
- `docs/ARCHITECTURE.md`：记录coordinator/checkpoint authority分离、versioned control interface和仍未接入的product graph；
- `docs/STATE_SCHEMA.md`：记录ControlOperation、Pause/Run lifecycle、capability和child projections；
- `docs/ARTIFACT_CONTRACTS.md`：记录control/child/source proof与domain artifact边界；
- `docs/SECURITY_AND_DATA_POLICY.md`：把已实现接口与仍为目标的B03/B04政策分开；
- `docs/EVALS_AND_OBSERVABILITY.md`和`docs/VERIFICATION_GUIDE.md`：记录B02 matrix totals、restart/concurrency/fault命令；
- Phase B Overview、Docs Index、Current State和Decision Log；
- `docs/tickets/completions/B02_COMPLETION.md`及completion index；
- 完成stale-documentation scan。

## Review Gate Before `ready`

- 确认本票maintenance路径和corrections index追加在Allowed Files内，已有历史不可改写；缺失前置功能或任何架构/schema/public contract/Allowed Files/验收边界变化必须停止并经corrective ticket批准；
- 确认B02 exact owned set为30项、累计56项、remaining 75项；
- 确认A04跨Code语义只由generic typed adapter证明control half，B03仍负责真实ExternalOperation/backend evidence；
- 确认public/internal接口、single SQLite domain、lease/capability、terminal ownership和migration边界均无第二套authority；
- 确认start/replay/fork bootstrap admission由B02复用B01基础实现，B04只接后续产品admission；
- 确认所有recovery/concurrency verification使用fresh process而非概率race；
- 确认Allowed Files、Do Not Touch和verification没有未决placeholder。

只有用户完成review并明确批准后，才能把B02 YAML提升为`ready`；起草本文件不授权执行。
