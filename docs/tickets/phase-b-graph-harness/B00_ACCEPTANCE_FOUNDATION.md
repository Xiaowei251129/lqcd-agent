---
ticket_id: B00
phase: phase-b-graph-harness
status: completed
type: implementation
depends_on: [A07]
---

# 建立 Phase B Acceptance Foundation

## Goal

在任何Phase B control runtime实现之前，建立可执行、可收集、可复现且fail-closed的验收基础：严格读取并绑定Phase A冻结的Control Protocol与requirement catalog，生成runtime-facing immutable protocol declarations，建立`PhaseBAcceptanceMatrix 0.1`、pytest evidence、normalized trace codec和failpoint registry，并让B00拥有的15项`A07-META-*` requirements对应的construction证据通过验证，同时定义其完整final验收义务。

B00完成时必须明确报告全局仍有116项subsystem requirements未覆盖；真实project matrix的final mode必须非零，并分别报告需求映射缺口、runtime证据缺口和退出检查缺口。B00完成只证明验收机制能够发现缺口，不证明schema `0.4` runtime、durable coordinator、Pause/Resume、Code Agent、budget enforcement、产品graph或Phase B zero-gap已经实现。

## Why

Phase A已经冻结九个owner的131项required requirements，但当前只有design-time validator，没有Phase B matrix、collectable meta tests、pytest result evidence、normalized trace工具或durable failpoint registry。如果先实现B01–B04，再由实现反向定义测试范围，遗漏的route、crash boundary、owner race或forbidden behavior可能被一个happy-path pass掩盖。

B00必须先把“哪些合同存在、测试是否真正被收集并通过、证据属于哪一类、哪些requirements仍缺失”变成机器可判定结果。后续ticket只能向这套foundation增加owned slices和真实scenario evidence，不能降低validator规则或把compatibility/capability结果计入required control acceptance。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/tickets/README.md`
- `docs/tickets/corrections/README.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/EVALS_AND_OBSERVABILITY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md`
- `docs/tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json`
- `docs/tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json`
- `docs/tickets/completions/A07_COMPLETION.md`
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`
- `scripts/validate_phase_a_control_protocol.py`
- `pyproject.toml`

## Frozen Inputs and Execution Baseline

- Control Protocol path：`docs/tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json`；schema/protocol version均为`0.4`；exact SHA-256必须为`7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`。
- Requirement catalog path：`docs/tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json`；catalog version为`0.4.0`；exact SHA-256必须为`ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726`。
- Catalog required owner集合固定为`A01 | A02 | A02C01 | A03 | A03C01 | A04 | A05 | A06 | A07`，总数固定为131；B00 owned slice固定为全部15项`A07-META-001`至`A07-META-015`，其他116项必须保持显式remaining。
- JSON中的`status: review`是A07同一批准快照的冻结bytes，不得由B00改写，也不得被validator误判为未批准合同；执行资格来自B00自身YAML lifecycle。
- `scripts/validate_phase_a_control_protocol.py`是Phase A design-time lint。B00可以从collectable tests调用其独立语义检查，但不得修改该脚本、只包装其最终exit code或把它冒充Phase B matrix evidence。
- 执行前必须记录full `pytest -q`基线；任何基线失败都先分类为本ticket回归、已知外部数据问题或环境问题，不得直接降低B00 verification。

## Scope

- 用Python标准库实现strict duplicate-key JSON loader、closed-object schema validation和deterministic error/report ordering；
- 从冻结Control Protocol exact bytes确定性生成tracked runtime-facing enum/mapping projection，并提供无I/O、无副作用的只读lookup接口；
- 建立matrix schema、implementation slice、validation stage、construction/final mode、catalog/protocol digest binding和required coverage验证器；
- 冻结独立于matrix scenarios的final obligations、closed report/evidence schemas及final统一执行器；B05接入具体退出检查适配器；
- 建立pytest collection/result evidence插件，独立证明matrix nodeid真实collect、执行并pass，且没有skip、xfail、deselect或live-only依赖；
- 建立allowlist-based normalized trace codec及strict expected-trace fixture读取/比较；
- 建立A07全部声明边界的typed failpoint registry skeleton，冻结stable ID、source locator、future implementation owner和允许outcome class，但不在B00接入runtime hooks；
- 为15项B00-owned `A07-META-*` requirements建立required matrix scenarios和collectable meta tests；
- 建立稳定CLI验证入口，并把exact construction/final命令写入Verification Guide；
- 运行完整deterministic regression，更新Phase B状态、验收文档、Current State、Decision Log和独立completion record。

## Non-goals

- 不实现`ControlOperation` persistence、SQLite coordinator、Run bootstrap、lease takeover或operation replay；
- 不实现schema `0.4` budget/run ledger、bounded state projection、trusted clock或cross-head runtime validation；
- 不实现Pause/Resume/Replay/Fork/Cancel、ExternalOperation、watchdog、containment或terminal closure；
- 不实现`CodeAgentSubgraph`、`CodingBackend`、`FakeCodingBackend`、workspace、Code Bundle或fresh Analysis；
- 不改变A01 product routes、graph topology、Agent行为、Human Gate、artifact registry或现有checkpoint行为；
- 不为其他116项requirements创建placeholder scenario、虚假nodeid、skip、xfail或预先通过记录；
- 不使真实project matrix通过final mode，不声称zero-gap；
- 不运行live provider、真实Codex SDK、完整Agents SDK SandboxAgent、raw numeric data或历史`outputs/`；
- 不修改或执行已起草的B01–B05 ticket，不选择production checkpoint、distributed lock、认证系统或新dependency。

## Migration Boundary

- B00不改变任何Run、state、ledger、artifact、checkpoint或database schema，不提供`0.2/0.3 -> 0.4` migration。
- Generated protocol module只是frozen machine contract的deterministic Python projection，不是runtime state、config、migration input或旧Run解释器。
- Existing Run bytes、repository `outputs/`、legacy handoff artifacts、Human decisions和accepted results不读取、不转换、不改写。
- Matrix、trace、failpoint和pytest evidence只存在于test-owned namespace；不得被runtime、Agent或provider作为route/config authority读取。

## Proposed File Layout

执行完成后最小新增结构为：

```text
src/lqcd_agent/control/
  __init__.py
  protocol.py
  _generated_protocol.py
scripts/
  generate_phase_b_protocol.py
  validate_phase_b_acceptance.py
tests/phase_b/
  acceptance_matrix.json
  failpoint_registry.json
  final_obligations.json
  conftest.py
  harness/
    __init__.py
    strict_json.py
    matrix.py
    pytest_evidence.py
    trace.py
    failpoints.py
  expected_traces/
  test_acceptance_foundation.py
```

实现可以在`tests/phase_b/`内进一步拆分meta test文件，但不得把单用途代码扩展为另一套通用framework。`_generated_protocol.py`只能由tracked generator生成；人工维护接口和生成内容必须分离。

## Allowed Files

- `docs/tickets/corrections/B00_MAINTENANCE.md`：仅在发生本票范围内的contract-preserving局部修复时新增；同票后续条目只追加，不改写已记录事实；
- `docs/tickets/corrections/README.md`：仅追加本票maintenance链接，不改写已有索引项；
- `docs/tickets/phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md`：进入`ready`后只允许更新YAML lifecycle metadata；
- `src/lqcd_agent/control/__init__.py`；
- `src/lqcd_agent/control/protocol.py`；
- `src/lqcd_agent/control/_generated_protocol.py`；
- `scripts/generate_phase_b_protocol.py`；
- `scripts/validate_phase_b_acceptance.py`；
- `tests/phase_b/`：仅限B00 acceptance infrastructure、matrix、registry、final obligations、closed report/exit evidence、final driver、expected fixtures和meta tests；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`；
- `docs/tickets/completions/B00_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/ARCHITECTURE.md`；
- `docs/EVALS_AND_OBSERVABILITY.md`；
- `docs/VERIFICATION_GUIDE.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

已有completion/correction记录及其历史内容保持不变；Allowed Files仅为本票maintenance新记录/追加条目与corrections index追加链接保留例外，不授权修改前置票据的记录。

- `docs/tickets/phase-a-control-contracts/`全部文件及其exact bytes；
- `scripts/validate_phase_a_control_protocol.py`；
- 已完成ticket、completion/correction history、milestone和tag；
- `src/lqcd_agent/graph/`、`src/lqcd_agent/artifacts/`、`src/lqcd_agent/agents/`、`src/lqcd_agent/coder/`、`src/lqcd_agent/llm/`、`src/lqcd_agent/memory/`、`src/lqcd_agent/analysis/`、`src/lqcd_agent/analysis_programs/`、`src/lqcd_agent/demo/`、`src/lqcd_agent/report/`和`src/lqcd_agent/tools/`；
- B00执行前已经存在的`tests/test_*.py`；
- `pyproject.toml`、dependency versions、configs、evaluation、raw data、outputs和accepted artifacts；
- graph topology、current execution schema `0.2`、checkpoint backend、provider、认证、secrets和外部系统；
- B01–B05 ticket正文及其预期runtime实现。

## Requirements

### 1. Authority and Non-circularity

- Frozen protocol/catalog exact bytes是唯一contract input；matrix、generated module、tests或实现代码都不能反向定义expected protocol、catalog owner set或required requirement set。
- Generator和validator必须在解析前检查exact SHA-256，再进行strict schema/semantic验证；digest错误时不得继续生成或输出pass。
- Runtime-facing module不得在import或lookup时读取`docs/`、test fixture、环境变量、network、clock、filesystem state或provider。它只包含deterministically generated immutable declarations和纯lookup。
- Generated projection只包含B01/B02后续需要的closed enum/mapping数据：operation type/variant、phase/status、allowed edges、branch references、terminal outcomes、authority/effect/continuation、transaction domain、CAS guard、evidence union、reservation overlay、dependency、stop route、field binding和compatibility identity；不得复制自由文本设计说明。
- `generate_phase_b_protocol.py --check`必须重新生成到内存并与tracked `_generated_protocol.py` byte-equal；manual edit、stale hash、不同key/list order或generator版本漂移必须非零退出。
- Python源文件中的所有comment和docstring使用English。

### 2. Strict JSON and Closed Schemas

- Protocol、catalog、matrix、final obligations、failpoint registry、expected traces、report和pytest/exit evidence统一使用拒绝duplicate key、NaN、Infinity、`-Infinity`和overflow-to-nonfinite的strict JSON reader。
- 每层object必须拒绝unknown/missing field、错误scalar/container type、空stable ID、重复ID和未声明enum；JSON number不能隐式替代boolean/string/integer。
- Repo-relative path只允许POSIX相对路径，解析后必须位于声明root内；拒绝absolute path、`..`逃逸、symlink escape和不存在的required fixture。
- 所有诊断按稳定的category、object ID、field path排序；不得把Python set/dict偶然顺序、临时路径、timestamp或process ID写入canonical report。

### 3. `PhaseBAcceptanceMatrix 0.1`

Tracked matrix固定为`tests/phase_b/acceptance_matrix.json`。Top-level closed schema至少包含A07冻结字段，并增加机器可验证的implementation ownership：

```text
schema_version
phase
requirement_catalog_version
requirement_catalog_sha256
control_protocol_version
control_protocol_sha256
implementation_slices
scenarios
```

每个`implementation_slices` entry固定包含`ticket_id`和ordered unique `owned_requirement_ids`。每个scenario除A07字段外必须包含`implementation_ticket_id`与`validation_stage = construction | final`，并与恰好一个slice对应。B00 slice exact包含：

```text
A07-META-001
A07-META-002
A07-META-003
A07-META-004
A07-META-005
A07-META-006
A07-META-007
A07-META-008
A07-META-009
A07-META-010
A07-META-011
A07-META-012
A07-META-013
A07-META-014
A07-META-015
```

- Implementation slice只允许`B00 | B01 | B02 | B03 | B04`；A07已冻结B05只生成final zero-gap与exit evidence，因此B05不得拥有catalog ID或创建空/重复slice。
- 每个scenario的`contract_refs`必须是其`implementation_ticket_id`对应slice之`owned_requirement_ids`的非空子集；跨slice integration test必须拆成按owner归属的多个scenario，可以复用同一个pytest nodeid和expected trace，但不能由单个scenario跨owner取得ownership。
- B00创建的required scenarios均为`validation_stage=construction`，其`contract_refs` union必须与上述15项set-equal；每项至少被一个可执行scenario覆盖。后续可按原owner追加final scenarios；不得预填未来scenario、nodeid或passing证据。
- `scenario_id`、slice ticket ID和每个list内部ID必须唯一且canonical ordered；scenario可支持多个contract refs，test nodeid可跨scenario复用，但validator必须按scenario逐项报告。
- `layer`固定为`schema | node | route | trajectory | recovery | interface`；`evidence_class`固定为`required_control_acceptance | compatibility_regression | capability_evaluation`。
- Required scenario必须使用`required_control_acceptance`且至少有一个pytest nodeid。Compatibility/capability scenario即使pass也不得进入required covered/passed totals。
- `route | trajectory | recovery | interface` scenario必须引用非空expected trace fixture；`schema | node`可以为null，但仍必须有typed expected result和ordered nonempty invariants。
- Construction mode接收exact `ticket_id`，验证全部已存在acceptance文件的结构与绑定，但只执行该slice的construction scenarios；报告`construction.required=15`、`construction.covered=15`、`construction.passed=15`、`requirements.required=131`、`requirements.covered=15`、`requirements.remaining=116`。全局`requirements.passed/passed_ids`为null，`requirements_zero_gap=false`、`phase_b_complete=false`，不得把累计映射数量称为累计通过数量。
- Final mode不接收局部owner或stage豁免，执行所有required construction和final scenarios，并核验独立final obligations及全部退出检查。B00真实matrix必须报告exact 116项映射remaining，并分别报告runtime/exit gaps；synthetic完整fixture只能证明验证器算法，不得进入project totals。

### 4. Pytest Collection and Result Evidence

- `tests/phase_b/conftest.py`注册project-owned pytest evidence writer；不得增加第三方pytest plugin或修改`pyproject.toml`。
- Evidence必须分别记录collected、deselected、setup/call/teardown outcome、skip和xfail/XPASS，并以完整pytest nodeid为key。Duration、timestamp、worker/process ID和临时root不进入canonical evidence。
- Stable validator CLI必须自己创建one-time invocation token、启动fresh pytest subprocess并立即消费对应evidence；matrix自报`passing`、仅`--collect-only`、调用者提供的旧evidence路径或repository-tracked result JSON都不能满足passed状态。
- Required nodeid必须被精确collect且call phase pass；setup/teardown failure、skip、xfail、strict/non-strict XPASS、deselect、duplicate result、unknown nodeid、未执行nodeid或只在live opt-in下存在均非零退出。
- Evidence文件必须包含schema/version、ephemeral invocation token、selected test root和ordered node results，并由validator核对本次token、实际工作树输入摘要及matrix/registry/protocol/catalog/final-obligations digests。Token、临时路径和原始运行时元数据不进入canonical report；不同session、worktree inputs或contract bytes的evidence不可复用。
- B00 tests必须包含真实pytest subprocess self-test，证明正常证据通过以及skip、xfail、deselect、unknown和stale evidence各自被拒绝；不能只单元测试内部dict。

### 5. Normalized Trace Codec

- Codec接收typed event objects并输出UTF-8 canonical JSON bytes；object key顺序、event order、list order和nullable field presence必须确定，禁止通过字符串化任意Python object掩盖类型错误。
- Normalization只能删除A07明确排除的timestamp/duration、临时physical root/path、process ID和opaque provider/checkpoint literal；必须保留顺序、identity、digest/correlation、authority、status/phase、route/guard、ownership、budget、artifact/current/protection和bounded-head语义。
- 不允许通用“删除所有不稳定字段”、正则模糊匹配、unordered subset或只比较最终state。Unknown field默认拒绝，新增排除规则必须通过后续corrective ticket。
- Expected trace fixture使用strict closed JSON和exact byte/semantic comparison；不同event顺序、缺失typed null、duplicate event、错误identity、额外route、stale head或不一致digest必须失败。
- B00只用meta fixtures证明codec与comparator；真实subsystem trajectory由B01–B04各自owned scenarios提供，B05只增加保持原ownership的跨子系统组合证据并运行final gate。

### 6. Failpoint Registry Skeleton

- `tests/phase_b/failpoint_registry.json`逐项记录stable `failpoint_id`、A07 source locator、boundary owner、future implementation ticket、effect class、precondition、allowed exact outcomes和required contract refs。
- Registry必须覆盖A07 `Fault Injection and Crash Outcomes`列出的每个publication boundary group以及bootstrap、Pause、ExternalOperation、lease/fencing、budget/grant、child Run、terminal close、artifact和fresh Analysis边界；一项可拆成多个stable failpoint，但不得用`misc`、`other`、`TBD`或自由文本catch-all代替。
- Future implementation owner只允许`B01 | B02 | B03 | B04 | B05`，并必须符合A07拆票职责；B00只注册，不把`hook exists`或fault scenario pass写成当前事实。
- Outcome只允许A07冻结的same-operation continuation或typed fail-closed classes；registry不得授权自动退款、redispatch、重复target Attempt、partial repair、恢复旧current artifact或伪造terminal lifecycle。
- Validator必须拒绝duplicate/unknown boundary、无source locator、空outcome、跨ticket owner、未引用required contract和registry/matrix的合同摘要或cross-reference漂移。后续B01–B05只能追加hook binding和scenario evidence，不能重命名或删除B00冻结的stable failpoint。

### 7. A07 Meta-validation Ownership

B00必须以collectable nodeids分别证明：

- `A07-META-001`：所有acceptance JSON使用strict closed parsing；
- `A07-META-002`：catalog version/digest、九owner、131项和ordering冻结；
- `A07-META-003`：required set equality及unknown/stale/uncovered deterministic report；
- `A07-META-004`：pytest collect/pass与skip/xfail/deselect/live拒绝；
- `A07-META-005`：normalized exact trace和typed invariants；
- `A07-META-006`：construction验证完整typed failpoint inventory、outcome分类及验证器拒绝缺口的能力；final还须证明每个production hook实际触发并覆盖所有适用case；
- `A07-META-007`：compatibility/capability/happy-path evidence不能计入required totals；
- `A07-META-008`：construction slice与final zero-gap严格分离；
- `A07-META-009`：operation router/edge/terminal/reachability/termination、combined ownership和single final evidence静态闭包；
- `A07-META-010`：exact protocol authority、stale projection和unknown/cyclic graph拒绝；
- `A07-META-011`：single transaction domain、CAS guard和winner ordering静态关系；
- `A07-META-012`：十二variant exact reservation overlays及cross-binding；
- `A07-META-013`：branch exhaustiveness/disjointness、tagged union和unavailable closure integrity；
- `A07-META-014`：composite owner/resolution/stop-route totality和no duplicate terminal operation；
- `A07-META-015`：construction验证producer dominance、full noninitial phase coverage、independent seal及语义probe算法；final还须提供A07追加的全部production publication、handoff和post-claim probes。

Construction pass只对当前阶段的证据有效。特别是`A07-META-006/015`完整requirement在runtime义务满足前保持未获final验收；`A07-META-009`至`015`的静态检查也不得被描述为SQLite、并发或crash recovery已实现。B01–B05追加实际证据时保持原requirement owner；B05跨owner测试按owner拆成scenario，可复用同一nodeid/trace。

### 8. Final Obligations and Runtime Evidence

B00建立tracked `tests/phase_b/final_obligations.json`，使用closed `PhaseBFinalObligations 0.1`：top-level字段固定为`schema_version`、`control_protocol_sha256`、`requirement_catalog_sha256`、`runtime_obligations`、`exit_check_ids`。每个runtime obligation包含`obligation_id`、`contract_refs`、`source_locator`、ordered unique `case_ids`和`failpoint_ids`；case必须逐项展开，不用自由文本范围代替机器集合。

- Obligations从冻结A07及protocol建立，不从已有matrix scenarios反推；B00独立冻结其内容摘要和registry inventory摘要，后续只在registry增加binding/evidence，删除义务、缩减case或联动修改matrix/registry不能消除required gap。
- 至少包含所有registry boundary的适用outcome cases，以及META-015的ordinary/initial capability、recoverable timeout source Attempt completion、fresh Analysis preparation、consumption release、recovery reason/target authorization、严格JSON和post-claim failure义务。Post-claim按协议中7个entry phase × 4个stop/authority组合展开28条case，再关联每条路径必需的publication boundaries。
- Registry的runtime binding固定为`hook_ref`、`case_bindings`；未实现时`hook_ref=null`、`case_bindings=[]`只表示inventory。每个case binding包含`case_id`、`scenario_ids`，关联required scenario的nodeids/trace。一个hook/scenario的存在不证明其他case通过。
- Final逐项核验obligation/case集合、实际production hook、fresh invocation内的hook触发记录、nodeid result、expected outcome、exact trace及typed invariants；源码包含hook名称、inventory齐全或static test pass均不能替代触发证据。
- Final必须重新运行两个stage的全部required scenarios。每项requirement只有在其所有required scenarios及关联runtime obligations全部通过后才进入`requirements.passed_ids`；META-006/015不得仅由B00 static tests转绿。
- 缺失scenario/case/hook触发、stale绑定或不匹配trace都形成`runtime_evidence_gap`或`invalid_evidence`，不改变catalog IDs或ownership。

### 9. Unified Final Driver and Exit Evidence

公开CLI保持`--mode construction --ticket B00`及`--mode final`，使用fresh `--evidence-dir`和`--report`。Final不接受调用方提供的旧结果或任意shell命令，而由项目维护的typed adapters执行固定检查。

`exit_check_ids`固定为：`layer_0`至`layer_5`、`cross_system_fault_concurrency`、`phase_b_suite`、`full_pytest`、`compileall`、`synthetic_tests`、`full_mock_benchmark`、`legacy_regression`、`cli_smoke`和`documentation_scope`。每项均为必需项；Layer nodeids按matrix layer选择，cross-system检查按独立runtime obligations选择。文档/scope适配器覆盖Phase A validator、generated protocol check、links、metadata、Allowed Files/Do Not Touch、stale-doc证据及diff检查；其语义审核仍须记录依据，不声称关键词扫描等于人工合同审核。

- B00实现固定check分派、证据解析/校验和报告机制，并用隔离fixture验收；B05实现实际cross-system/CLI/documentation adapters和nodeid绑定。B05可补齐已冻结接口的适配器，不能缩减必需check集合或另造完成判定。
- Final先校验输入与独立清单，检查所需scenario/case/adapter是否具备；固定check与adapter的可信映射属于B00机制，B05只能在声明位置接入，公开CLI不能提供替代adapter或测试替身。缺失项逐项报告，已有检查错误另行报告；preflight不满足时不执行完整B05流程。具备后统一执行fresh required tests、各exit检查，最后才生成最终判定。不得以B05 YAML已completed为前提，否则会与completion record形成循环。
- Invocation生成one-time token并冻结`worktree_inputs`摘要：按POSIX path排序记录实际被检查的source、tests、scripts、configs、synthetic inputs/expected、文档及manifest bytes/type/mode，包含相关untracked实现和dirty changes，不用HEAD代替；不读取secrets/raw numeric/历史outputs/cache。检查前后输入摘要必须相同，发生变化则本次证据失效。
- Pytest与exit evidence共享同一session token和输入/contract摘要。每个必需check在session中只有一份权威结果；相同node结果只可在同session且selection/stage一致时复用，不允许跨会话拼接。适配器返回原始证据引用，最终passing由validator复核。
- Closed `PhaseBExitEvidence 0.1`字段为`schema_version`、`invocation_token`、`check_id`、`digests`、`exit_code`、`evidence_refs`；每个reference含`relative_path`和`sha256`，只能位于本次fresh evidence root内。Validator按check ID验证对应artifact schema、required case/node集合、semantic result和实际退出码，拒绝missing/unknown/duplicate/stale evidence。
- Full mock benchmark必须验证`full.json`指定的全部case唯一出现、每份structured checklist及其必需items通过；现有runner退出码0但`passed=False`时仍失败。CLI smoke必须验证ledger/state/checkpoint/artifact/budget/Pause/child/accepted invariants，退出码或成功字符串不足以通过。
- Legacy、synthetic和benchmark证据作为独立必需exit checks，不增加131项required control totals。测试命令中显式禁用live opt-in，子流程不能运行network/real Backend/raw data路径。
- 防止验收递归：meta tests只使用隔离runner/临时fixture测试final机制，不在full pytest内部再次启动真实project final流程；fixture成功永远不能生成project completion。

### 10. Closed `PhaseBAcceptanceReport 0.1`

成功和失败输出同一closed report。全部字段显式存在，各层拒绝unknown/missing字段；数量为非负整数，IDs按冻结catalog/obligation/check顺序排列且unique。

| Field | Exact shape and meaning |
| --- | --- |
| `schema_version` | `"0.1"` |
| `mode` | `construction \| final` |
| `ticket_id` | construction为B00–B04之一；final为null |
| `digests` | `protocol`、`catalog`、`generated_protocol`、`matrix`、`registry`、`final_obligations`、`worktree_inputs`，均为SHA-256；读取/验证失败的项显式null并附error |
| `construction` | final为null；construction包含`required`、`covered`、`passed`及对应`required_ids`、`covered_ids`、`passed_ids`，仅对应当前slice/stage |
| `requirements` | `required`、`covered`、`passed`、`remaining`及对应四个`*_ids`；covered为required scenarios的refs并集，remaining为required减covered，二者仅表示映射 |
| `runtime_evidence` | `status`、`required_case_ids`、`passed_case_ids`、`missing_case_ids`、`failed_case_ids` |
| `exit_checks` | ordered entries，每项只有`check_id`、`status`和`evidence_digests` |
| `requirements_zero_gap` | boolean；只在final中131项映射齐全、全部required scenarios/obligations实际通过且其证据有效时为true |
| `phase_b_complete` | boolean；仅final中`requirements_zero_gap=true`、全部exit checks passed且`errors=[]`时为true |
| `errors` | ordered entries，每项只有`category`、`object_id`和`field_path` |

- `status`固定为`not_run | passed | failed | missing`；`errors.category`固定为`coverage_gap | runtime_evidence_gap | exit_evidence_gap | invalid_input | invalid_evidence | check_failed | internal_error`，按category/object_id/field_path排序。
- Construction只确认当前slice的construction passed；`requirements.passed/passed_ids=null`，`runtime_evidence.status=not_run`且`passed_case_ids=null`，missing cases显式列出尚缺final证据的义务、failed cases为空；exit checks均not_run、evidence digests为空，两个全局完成标志为false。全局remaining不包含“已映射但未满足final义务”的数量，后者必须在runtime evidence中显式显示。
- Final preflight未通过而未运行时，全局passed也为null；运行后passed按本次证据计算，不从各ticket历史pass数相加。合法输入下count必须等于对应IDs长度；非法输入无法计算的值为null并记录error，不猜测为0。
- `exit_checks.evidence_digests`固定为ordered unique SHA-256字符串数组；这里使用规范化证据摘要，`PhaseBExitEvidence.evidence_refs.sha256`则核验原始文件bytes。未运行/缺失检查的数组为空；无本次有效证据不得标passed。
- Final的`requirements_zero_gap`与exit结果独立：全部control义务通过但benchmark/CLI/legacy失败时，可为true，而`phase_b_complete=false`且exit code非零；仅131 refs齐全时不能置true。
- Canonical report不包含session token、timestamp、duration、temporary physical path或process ID；normalized evidence digests排除这些ephemeral envelope字段，raw evidence仍保存token/path binding供本次校验。排除不允许删除identity/head/digest/authority等语义。
- Construction当前slice成功退出0不表示阶段完成；final只有`phase_b_complete=true`才退出0。缺adapter、错误token、不同工作树/contract摘要、内部异常均不能通过。
- B00–B05的Goal、Acceptance、Verification和completion evidence引用本节唯一字段；不维护其他顶层计数字段或同义完成标志。

## Deliverables

- deterministic generated Control Protocol runtime-facing declarations及`--check` generator；
- strict matrix/failpoint/trace/pytest-evidence validation modules，以及closed report/exit evidence与统一final driver；
- `tests/phase_b/acceptance_matrix.json`，只包含B00的15项A07 meta coverage；
- `tests/phase_b/failpoint_registry.json`、独立冻结的`final_obligations.json`和normalized expected meta traces；
- collectable B00 meta test suite与pytest evidence writer；
- stable construction/final validation CLI、固定exit check清单和待B05接入的typed adapter接口；
- B00 completion record以及同步后的Phase B Overview、Architecture、Evals/Observability、Verification Guide、Current State和Decision Log。

## Acceptance Criteria

- B00所有新增代码仅使用Python标准库和现有pytest环境；没有dependency、provider、config或runtime graph变更；
- protocol/catalog exact hashes与A07 completion一致，Phase A frozen files byte-equal；
- generator的fresh output与tracked generated module byte-equal，generated declarations与protocol所有相关closed tables exact一致；
- matrix和registry通过strict schema、digest、owner、path、ID、ordering、fixture和cross-reference检查；
- B00 owned requirements exact为15项A07 meta IDs，其construction covered/passed set exact相等；完整requirement是否通过只由final义务核验决定；
- 所有required B00 nodeids在fresh run中collect并pass，无skip、xfail、deselect、live-only或unknown；
- construction report exact显示`construction.required/covered/passed=15`、`requirements.remaining=116`、`requirements.passed=null`，两个全局完成标志均为false；
- 对真实B00 matrix运行final mode确定性失败，exact报告116项映射remaining及各runtime/exit gap；synthetic complete fixture不能污染project totals；
- 全部131项已映射但缺runtime/CLI/benchmark/legacy证据，inventory齐全但hook未触发或28条post-claim case缺一，旧token/不同工作树/不同合同摘要，以及benchmark退出0但case/checklist失败均有永久负向测试；这些只用隔离fixtures，不伪造project pass；
- strict JSON、wrong digest/version、unknown/non-required/duplicate/missing IDs、stale projection、invalid path、trace drift、bad failpoint、compatibility-as-required和pytest negative evidence均有永久回归；
- `pytest -q tests/phase_b`与完整`pytest -q`通过，compileall、relative links、ticket metadata、Allowed Files/Do Not Touch、stale docs和`git diff --check`通过；
- Current State明确B00只是acceptance foundation，current schema仍为`0.2`，B01–B05虽已起草为`draft`但均未执行。

## Verification

执行时先创建fresh evidence目录，再运行：

```bash
B00_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b00-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest --collect-only -q tests/phase_b
pytest -q tests/phase_b
python scripts/validate_phase_b_acceptance.py \
  --mode construction \
  --ticket B00 \
  --evidence-dir "$B00_EVIDENCE_DIR/construction" \
  --report "$B00_EVIDENCE_DIR/construction-report.json"
! python scripts/validate_phase_b_acceptance.py \
  --mode final \
  --evidence-dir "$B00_EVIDENCE_DIR/final" \
  --report "$B00_EVIDENCE_DIR/final-negative-report.json"
pytest -q
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

真实matrix的final命令预期非零，执行验收必须分别核对exact 116项映射remaining、缺失runtime obligations与未具备的exit adapters/evidence。缺口使用稳定分类；已有scenario的parser、collection、evidence或内部错误仍是独立失败，不能冒充预期缺口。Completion record必须分别记录construction成功与final expected-failure，不得把预期非零省略或写成Phase B pass。

还必须执行：

- protocol/catalog/generated/matrix/registry/final obligations exact digest审计与实际工作树输入绑定；
- B00 15项owned refs、construction covered refs和本次construction passed refs三集合set-equal，不称为全局requirement已通过；
- 131 catalog IDs减去B00 refs exact等于116项ordered remaining；
- 所有tracked及新增Markdown relative links检查；
- 相对执行前commit的Allowed Files/Do Not Touch、删除/重命名、dependency和stale-documentation审计；
- 确认B01–B05 draft正文未被B00执行修改，且没有B01–B05 runtime database、Run、accepted artifact或repository-local test output产生。

B00 standalone construction不运行benchmark。真实final negative probe先完成独立清单/适配器preflight；当前runtime或退出适配器缺失时报告缺口并停止后续执行，不提前运行完整B05验收。B00 final执行器的完整成功、失败与会话绑定以隔离synthetic适配器验证；测试替身只能由test入口注入，公开CLI不能用synthetic evidence宣告完成。任何模式均不运行live-provider、Codex SDK或raw-data evaluation。

## Stop Conditions

既有合同及Allowed Files内的局部bug允许修复，但必须使用本票maintenance路径留痕；缺失前置功能、需要扩大范围或改变架构/schema/public contract/验收边界时停止，先创建并批准corrective ticket，不用maintenance授权新功能。

- Frozen protocol/catalog digest、version、owner set、131项required set或A07 15项meta set与本ticket基线不一致；
- 需要修改Phase A ticket、Control Protocol、requirement catalog或Phase A design validator才能让B00通过；
- 需要从A07 prose重新发明operation phase/edge/authority/outcome，而不是消费frozen machine contract；
- 15项A07 meta requirements无法形成诚实的construction证据，或无法为META-006/015保留强制final runtime义务；
- 需要把其他116项写成placeholder、skip、xfail或虚假covered才能让construction mode成功；
- 需要让真实B00 matrix在116项remaining时通过final mode；
- 需要修改current graph/state/artifact/coder runtime、existing tests、pyproject、dependency、provider、config、checkpoint或外部系统；
- 需要扩大Allowed Files、触碰Do Not Touch或修改/执行B01–B05 ticket；
- pytest evidence无法独立证明collection/result，或必须依赖第三方plugin、network、真实sleep、概率race、历史outputs或raw data；
- baseline/full deterministic suite出现无法在Allowed Files内解释和修复的回归；
- 任何实现选择会改变A07 matrix schema、evidence class、zero-gap、fault outcome或Phase B拆票边界。

触发任一条件时保持B00未完成，记录证据并请求用户确认；需要改变已冻结Phase A合同时必须另开corrective ticket。

## Required Documentation Updates

- 若执行中发生既有边界内的局部修复，新增本票`docs/tickets/corrections/B00_MAINTENANCE.md`并向corrections index追加链接，记录问题、根因、改动、验证及关联ticket；
- `docs/ARCHITECTURE.md`：记录generated protocol declarations和acceptance harness是非runtime-authority foundation，当前graph未接入；
- `docs/EVALS_AND_OBSERVABILITY.md`：记录matrix slice、pytest evidence、trace/failpoint schema和construction totals；
- `docs/VERIFICATION_GUIDE.md`：写入实际可运行的generator、pytest evidence、construction/final命令和expected-failure语义；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`：记录B00 lifecycle、B01进入条件及后续draft仍不可执行；
- `docs/README.md`与`docs/REPO_CURRENT_STATE.md`：区分B00 foundation与未实现runtime；
- `docs/DECISION_LOG.md`：记录generated projection、matrix ownership和evidence protocol的实现选择；
- `docs/tickets/completions/B00_COMPLETION.md`及completion index；
- 完成stale-documentation scan并检查所有“没有B00/matrix/Phase B tests”的当前状态描述。

## Review Gate Before `ready`

- 确认本票maintenance路径和corrections index追加在Allowed Files内，已有历史不可改写；缺失前置功能或任何架构/schema/public contract/Allowed Files/验收边界变化必须停止并经corrective ticket批准；
- 确认B00 owned slice是15项`A07-META-*`，其他116项全部remaining；
- 确认generated Python projection而非runtime读取`docs/`是消费Control Protocol的方式；
- 确认matrix的`implementation_slices`、scenario `implementation_ticket_id/validation_stage`及construction/final证据边界；
- 确认B00–B04 slices互斥分配全部131项required IDs，B05无owned slice且只负责final integration/exit evidence；
- 确认pytest evidence由本地plugin生成，不引入第三方dependency；
- 确认failpoint registry在B00只冻结inventory，不声称runtime hook或fault scenario已经通过；
- 确认final统一驱动退出检查；`requirements_zero_gap`与`phase_b_complete`分开，不能仅由131项映射齐全提前宣告完成；
- 确认META-006/015 final obligations独立于matrix存在，缺hook触发或任一post-claim case均失败；
- 确认Allowed Files、Do Not Touch、verification commands及Stop Conditions足够执行且没有未决placeholder。

只有用户完成上述review并明确批准后，才能把B00 YAML提升为`ready`；起草或修订本文件本身不授权实现。
