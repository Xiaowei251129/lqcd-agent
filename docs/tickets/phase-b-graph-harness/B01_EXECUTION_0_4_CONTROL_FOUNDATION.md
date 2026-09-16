---
ticket_id: B01
phase: phase-b-graph-harness
status: completed
type: implementation
depends_on: [B00]
---

# 建立 Execution 0.4 Control Foundation

## Goal

在不开放新产品路线、不实现durable public mutation的前提下，建立Phase B schema `0.4`的纯控制基础：canonical execution/budget records、append-only lifecycle replay、trusted clock、bounded projection、strict validators以及execution/artifact/checkpoint cross-head integrity，并让B01拥有的11项requirements通过construction-mode验收。

B01完成后，tracked matrix累计覆盖B00的15项meta requirements和B01的11项foundation requirements；必须明确报告`requirements.required=131`、`requirements.remaining=105`和`phase_b_complete=false`。这不表示`start_run`、Pause/Resume、Code Agent、A01产品拓扑或Phase B final gate已经完成。

所有construction数量仅对应本票`validation_stage=construction`证据。全局`requirements.passed/passed_ids=null`，`requirements_zero_gap=false`；原owner下新增的final scenarios和B00独立runtime obligations必须在final重新验证。

## Why

B02–B04需要共享同一组schema、record builder、replay validator、clock和bounded projection。如果这些基础分别在coordinator、Code Agent和graph wiring中临时实现，会产生第二套identity/head/budget authority，也无法可靠区分domain status、Run lifecycle与durable operation状态。

B01先把无外部副作用、可确定性验证的foundation接到A02/A03现有identity与artifact control plane上；所有durable mutation仍由后续B02通过冻结的Control Protocol执行。

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
- `docs/tickets/phase-a-control-contracts/A03C01_EXECUTION_HEAD_INTEGRITY.md`
- `docs/tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md`
- `docs/tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md`
- `docs/tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md`
- `docs/tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json`
- `docs/tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json`
- `docs/tickets/phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md`
- `docs/tickets/completions/B00_COMPLETION.md`
- `src/lqcd_agent/graph/state.py`
- `src/lqcd_agent/artifacts/registry.py`
- `tests/test_execution_identity.py`
- `tests/test_artifact_registry.py`
- `tests/test_state_schema.py`

## Frozen Inputs and Entry Conditions

- B00必须为`completed`，其generated protocol、matrix validator、trace codec、pytest evidence和failpoint registry均通过fresh verification；不得只依据ticket状态跳过B00 completion evidence审计。
- 批准本票为`ready`前，B00 ownership排序maintenance必须完成并有fresh回归：合法canonical slice前缀全部通过，非canonical/重复/遗漏/unknown/错误owner/重叠/非法slice顺序仍拒绝，单独增加slice不增加scenario coverage。B00 construction及真实final expected-failure必须重新验证，不能把该前置修复留到B01执行中。
- Control Protocol version/schema固定为`0.4`，exact SHA-256为`7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`。
- Requirement catalog version固定为`0.4.0`，exact SHA-256为`ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726`，required总数固定为131。
- A02/A03/A03C01当前实现是必须复用的identity、artifact current-selection与cross-head基础；B01不得另建平行ledger、artifact index或current projection authority。
- 执行前必须记录fresh full-suite基线、B00 construction report和真实matrix final expected-failure的exact 116项remaining结果。

## Scope

- 建立Execution schema `0.4`的closed Python types、canonical serializers、record builders与strict validators；
- 在现有`execution_history.jsonl`权威上增加versioned Run lifecycle与budget record的append/replay语义，不增加第二个budget ledger；
- 实现`BudgetPolicy 0.1`、`FailureFingerprint 0.1`、resource usage的typed unknown表达，以及后续B02–B04可消费的immutable validation结果；
- 实现trusted wall/monotonic clock port与deterministic fake clock，拒绝回退、overflow和non-finite值；
- 实现schema `0.4` bounded control projection的纯派生、重放和strict equality validation；
- 复用A03 registry，实现execution/artifact/checkpoint head与bounded projection的双向完整性校验；
- 为B01-owned requirements增加matrix slice、production serializer/replay/validator的required construction probes、expected fixtures和collectable pytest evidence；不交付durable failpoint bindings；
- 保持schema `0.2` legacy graph及已有tests兼容，不把compatibility pass计入B01 required totals。

## Non-goals

- 不创建Run root、`control_operations.sqlite`或任何public/internal ControlOperation；
- 不实现A02C01 bootstrap、start/resume/replay/fork/cancel、Pause claim/publication、operation lease、child saga或terminal owner；bootstrap admission由B02复用本票policy/record/validator基础实现，不等待B04；
- 不实现ExternalOperation、Backend、workspace、watchdog、trusted code verification或fresh Analysis；
- 不接入A01 target graph，不开放四层fallback、Human Gate return或budgeted loop；
- 不执行artifact invalidation、Transition publication或target capability activation；
- 不修改B00 registry、final obligations或其seals；durable publication/crash hooks由冻结registry中的B02–B04 owner实现，纯校验probe不能替代这些final runtime证据；
- 不自动迁移schema `0.2`/`0.3` Run，也不把existing legacy state解释成schema `0.4`；
- 不改变provider、raw-data、accepted-result、approval、network或dependency policy；
- 不让真实matrix通过final mode。

## Migration Boundary

- Schema `0.4`使用显式version dispatch；schema `0.2`继续由现有runtime validator处理。Phase B不原地resume/migrate `0.2/0.3`；source验证后`0.2`仅可replay；`0.3`通过来源验证及相应replay/fork资格时可创建`0.4` child，B02实现这些入口。
- B01可以增加从canonical `0.4` records重建bounded projection的纯函数；不得从旧`graph_state.json`、目录扫描、mtime或compatibility projection推断权威history。
- Existing Run bytes、A02/A03 ledger、artifact history/index、human snapshots和accepted artifacts不得改写、补写或转换。
- 新validator可以读取由调用方显式提供的Run root进行校验，但B01测试只能使用fresh `/private/tmp/lqcd-agent-b01-*` fixtures；不得扫描repository `outputs/`。

## Owned Requirement IDs

B01 slice固定为以下11项；下列展示顺序只表达owned集合，写入matrix的`owned_requirement_ids`及`contract_refs`必须使用字典序且唯一。Global report仍按catalog顺序列出requirements，不因slice排序改变。Catalog中的summary与source locator都是验收语义的一部分：

```text
A02-IDENTITY-001
A02-LIFECYCLE-001
A02-AUTHORITY-001
A03C01-HEAD-001
A03C01-HEAD-002
A03C01-PUBLISH-001
A03C01-TAMPER-001
A06-BUDGET-006
A06-BUDGET-009
A06-BUDGET-013
A06-BUDGET-015
```

- B01 required scenario的`contract_refs` union必须与上述集合set-equal，不能引用B02–B04 owned IDs填充coverage。
- B01执行后，B00+B01 required映射集合应为26项，ordered global remaining必须exact为105项。
- B01不得重分配、重命名或删除B00 slice；ownership变化必须先通过新的acceptance corrective ticket。

## Proposed File Layout

最小目标结构为：

```text
src/lqcd_agent/control/
  __init__.py
  protocol.py
  _generated_protocol.py
  strict_json.py
  records.py
  clock.py
  execution.py
  budget.py
  projections.py
  integrity.py
tests/phase_b/
  test_execution_0_4_foundation.py
  expected_traces/
```

可以按现有代码风格合并单用途模块，但不得在`graph/state.py`、A03 registry与`control/`之间复制同一validator或identity allocator。

## Allowed Files

- `docs/tickets/corrections/B01_MAINTENANCE.md`：仅在发生本票范围内的contract-preserving局部修复时新增；同票后续条目只追加，不改写已记录事实；
- `docs/tickets/corrections/README.md`：仅追加本票maintenance链接，不改写已有索引项；
- `docs/tickets/phase-b-graph-harness/B01_EXECUTION_0_4_CONTROL_FOUNDATION.md`：进入`ready`后只允许更新YAML lifecycle metadata；
- `src/lqcd_agent/control/__init__.py`；
- `src/lqcd_agent/control/protocol.py`；
- `src/lqcd_agent/control/_generated_protocol.py`：只能由B00 generator保持byte-equal，不得人工编辑；
- `src/lqcd_agent/control/strict_json.py`；
- `src/lqcd_agent/control/records.py`；
- `src/lqcd_agent/control/clock.py`；
- `src/lqcd_agent/control/execution.py`；
- `src/lqcd_agent/control/budget.py`；
- `src/lqcd_agent/control/projections.py`；
- `src/lqcd_agent/control/integrity.py`；
- `src/lqcd_agent/graph/state.py`：仅限复用A02 identity并增加versioned `0.4` adapter；
- `src/lqcd_agent/artifacts/registry.py`：仅限cross-head adapter与strict validation，不改变A03 slot/invalidation policy；
- `tests/phase_b/`：仅限B01 slice、foundation construction fixtures/tests和expected traces；B00 meta infrastructure不得降级，registry、final obligations及其seals排除在修改范围外；
- `tests/phase_b/acceptance_matrix.json`：仅追加本票`validation_stage=construction` scenarios及canonical ordered owned slice；不改ownership、不预填后续slice、不修改B00冻结schemas或必需check清单，不把纯基础层probe计为final durable evidence。后续B02–B05按各自批准范围追加integration/final scenarios时保留原requirement owner；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`；
- `docs/tickets/completions/B01_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/ARCHITECTURE.md`；
- `docs/STATE_SCHEMA.md`；
- `docs/ARTIFACT_CONTRACTS.md`；
- `docs/EVALS_AND_OBSERVABILITY.md`；
- `docs/VERIFICATION_GUIDE.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

已有completion/correction记录及其历史内容保持不变；Allowed Files仅为本票maintenance新记录/追加条目与corrections index追加链接保留例外，不授权修改前置票据的记录。

- `docs/tickets/phase-a-control-contracts/`及其exact bytes；
- B00 frozen ticket body、B00 completion/correction history和B02–B05 ticket正文；
- `scripts/validate_phase_a_control_protocol.py`、B00 generator和acceptance CLI的contract semantics；
- `tests/phase_b/failpoint_registry.json`、`tests/phase_b/final_obligations.json`及其独立seals；
- `src/lqcd_agent/graph/analysis_graph.py`、`routing.py`、`nodes.py`、runner与demo入口；
- `src/lqcd_agent/agents/`、`src/lqcd_agent/coder/`、`src/lqcd_agent/llm/`、`src/lqcd_agent/memory/`、`src/lqcd_agent/report/`、`src/lqcd_agent/tools/`、`src/lqcd_agent/analysis/`和`src/lqcd_agent/analysis_programs/`；
- B00执行前已有的`tests/test_*.py`；
- `pyproject.toml`、dependency versions、configs、evaluation cases/expected outputs、raw data、repository `outputs/`、human decisions和accepted artifacts；
- existing schema `0.2` public behavior、graph topology、checkpoint backend、provider或外部系统。

## Requirements

本票继承B00的validation stages、final obligations和closed report；本票只增加construction probes。后续integration/final runtime证据必须保留原requirement owner及独立case集合；对应production hook须有本次实际触发记录、passing nodeid和exact trace，不能以inventory、静态检查或B01纯校验probe替代。

### 1. Single Authority and Canonical Encoding

- Control Protocol已机读定义的closed enums、field bindings和compatibility identities必须唯一消费B00 generated projection，不得在B01重复定义、覆盖或从prose重建。
- 未进入机读协议、但已由冻结A02/A04/A06明确定义的record、budget event、identity和fingerprint内容，允许在本票现有Allowed Files内实现静态types/constants；必须逐项保留source locator并由测试核对合同来源和exact语义。已有A02/A03实现继续复用，不另建authority；未获冻结合同批准的语义不得自行补充，合同冲突时停止。
- Protocol import/lookup保持无I/O，不读取docs、matrix、test fixture、environment、network或clock；实际计时只通过trusted clock port，validator保留对显式提供的Run root的只读校验权限。所有runtime路径均不得读取设计文档或测试文件作为authority。
- 所有schema `0.4` records使用strict closed objects与canonical UTF-8 JSON bytes；拒绝duplicate key、unknown/missing field、NaN/Infinity、overflow-to-nonfinite、错误scalar type、空identity和non-canonical ordering。
- A02 canonical Run/Cycle/Attempt/Transition/Human identity格式、nesting、continuous index和agent authority边界保持不变；Agent/model output不能构造或提交authoritative record。
- 同一事实只允许一个authoritative representation。Bounded state、checkpoint manifest与artifact index均为可验证projection，不得成为ledger的竞争source of truth。

### 2. Execution and Run Lifecycle Replay

- `execution_history.jsonl`继续append-only，并对schema `0.4`定义closed record union、continuous event identity、pre/resulting execution head和exact canonical digest。
- Run lifecycle replay支持`initializing | running | paused | completed | failed | halted`，但B01只实现schema、builder与validator；B02才有权通过ControlOperation持久化这些records。
- Attempt lifecycle仍只允许一次`scheduled -> started -> terminal`历史；duplicate/gap、cross-Run identity、terminal rewrite、nonterminal target-null、Transition/Attempt mismatch和bounded counter rollback必须fail closed。
- Lifecycle replay必须同时验证Control/domain status正交；domain `pending`不能自行证明Run paused，domain `accepted/rejected/held`也不能自行发布terminal Run lifecycle。

### 3. Budget Foundation

- `BudgetPolicy 0.1`是immutable project-owned control artifact schema，profile来自fixed allowlist；canonical digest、Run/runtime binding与version全部strict验证。
- 所有budget events仍进入execution ledger；禁止创建`budget_history.jsonl`、Backend-owned counter或provider-owned retry/stop authority。
- Trusted fake clock精确覆盖host setup、backend active、paused waiting、verification、Run和Attempt计时边界所需的typed timestamps；clock回退、overflow、non-finite或未声明source拒绝。
- `FailureFingerprint 0.1`只由stable typed cause与material semantic context构成；execution identity、timestamp、summary、physical path和opaque job/thread/session literal不得改变fingerprint，backend/runtime/base/policy/verified patch/effective tree或material evidence变化必须改变。
- Missing token/cost usage保持typed unknown，不得隐式转为0、maximum、pass或hard gate authority。
- Policy/record/counter/reservation/fingerprint/grant/projection任何tamper必须分类为control integrity failure；B01只产生typed validation result，不越权追加Run terminal lifecycle。

### 4. Bounded Projection and Cross-head Integrity

- Schema `0.4` bounded projection只能从validated execution ledger、A03 artifact history/index和explicit checkpoint manifest派生，并保留global latest execution/artifact/checkpoint heads、current identities、counters及nullable fields。
- Execution global head必须由每条authoritative execution record推进；artifact history/index和bounded state必须绑定exact execution/artifact cross-head，checkpoint manifest必须绑定写入时的exact pair。
- Validator从history正向派生expected projection并exact比较；禁止信任state自报head、只检查latest record、目录扫描或partial repair。
- Partial/conflicting head advancement、协调篡改history/index/state/checkpoint、合法旧head回滚、错误nullable omission和跨Run proof全部fail closed，不得静默修复。
- A03 slot、dependency、current-selection、projection owner、protected snapshot与invalidation matrix保持原语义；B01 adapter不得扩大preflight exception。

### 5. Acceptance and Failure Evidence

- B01每项owned requirement至少由一个required construction scenario覆盖；schema/trajectory probes使用production serializers/replay/validators，不能只测试手写dict。
- 冻结registry没有B01-owned durable boundary，本票不新增、重分配或绑定failpoint，不修改final obligations或seals。Durable publication/crash hooks由B02–B04对应owner实现；纯serializer/replay/validation probe只证明construction行为，不得将未实现的durable case标为passing或减少final runtime缺口。
- Expected trace必须保留identity、record order、heads、policy/fingerprint、clock classification和typed failure；不能只比较最终projection。
- Required tests必须由fresh pytest subprocess collect并pass，无skip、xfail、deselect、live-only或旧evidence复用。
- Construction report使用B00的`PhaseBAcceptanceReport 0.1`：`construction.required/covered/passed=11`，`requirements.required=131`、`requirements.covered=26`、`requirements.remaining=105`、`requirements.passed/passed_ids=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。累计covered只表示映射，不能从前置ticket历史结果推断本次全局passed。

## Deliverables

- Execution schema `0.4` canonical record/serializer/validator foundation；
- append-only execution/Run lifecycle replay与bounded projection；
- BudgetPolicy、trusted/fake clock、FailureFingerprint和typed unknown usage基础；
- execution/artifact/checkpoint cross-head integrity adapter；
- B01 11项owned matrix slice、foundation construction probes、expected traces和collectable tests，不含durable failpoint bindings；
- B01 construction与final expected-failure reports；
- 独立B01 completion record和必要的source-of-truth同步。

## Acceptance Criteria

- B01仅使用Python标准库和已有依赖；没有新增dependency、provider/config或network路径；
- Phase A protocol/catalog exact bytes、B00 generated projection与B00 validator semantics不变；
- B00 canonical ownership排序回归与fresh construction/final expected-failure验收已通过；本票未修改registry、final obligations或seals，没有用pure probe替代durable hook evidence；
- 已机读合同只消费generated projection；其余静态定义有冻结A02/A04/A06来源与exact校验，protocol import/lookup无I/O，实际clock和显式Run root读取遵守各自port/validator边界；
- Schema `0.4` round-trip、closed union、lifecycle replay、budget/fingerprint/clock和cross-head negative cases均fail closed；
- A02/A03现有identity、registry、projection和protected evidence行为保持兼容，legacy schema `0.2` full regression通过；
- B01 construction owned/covered/passed三集合exact为11项，B00+B01累计映射covered exact为26项，remaining exact为105项；
- Required tests全部可collect且passing，无skip/xfail/deselect/live-only；
- 真实matrix construction通过但`phase_b_complete=false`，final mode分别报告105项映射remaining、runtime与exit缺口并非零退出；
- `pytest -q tests/phase_b`、A02/A03 focused suites、完整`pytest -q`、compileall、links、ticket metadata、scope、stale docs和`git diff --check`通过；
- Current State明确B01只完成control foundation，B02–B05未执行，current default product graph仍是legacy/schema `0.2`兼容路径。

## Verification

```bash
B01_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b01-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest --collect-only -q tests/phase_b
pytest -q tests/phase_b/test_closed_schemas.py
pytest -q tests/phase_b/test_execution_0_4_foundation.py
python scripts/validate_phase_b_acceptance.py \
  --mode construction \
  --ticket B01 \
  --evidence-dir "$B01_EVIDENCE_DIR/construction" \
  --report "$B01_EVIDENCE_DIR/construction-report.json"
! python scripts/validate_phase_b_acceptance.py \
  --mode final \
  --evidence-dir "$B01_EVIDENCE_DIR/final" \
  --report "$B01_EVIDENCE_DIR/final-negative-report.json"
pytest -q tests/test_execution_identity.py tests/test_artifact_registry.py tests/test_state_schema.py
pytest -q
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

还必须审计：

- B01 construction owned/covered/passed exact set、累计26项coverage及105项ordered remaining；
- B00排序maintenance的fresh正/负向回归和本票批准前的15/15 construction、116/2286/15 final预期缺口；slice IDs使用字典序，global report保留catalog顺序；
- generated定义与prose-only静态定义的source mapping、protocol import/lookup无I/O，以及clock/显式Run root只读校验边界；
- registry、final obligations和seals与执行前byte-equal；B01新增scenarios均为construction，纯probe不生成durable hook/case passing证据；
- construction/final report digests与fresh evidence token；
- schema `0.2 | 0.3 | 0.4` compatibility matrix和zero-migration断言；
- execution/artifact/checkpoint cross-head mutation suite不是仅由snapshot digest失败代替；
- 相对执行前frozen commit的Allowed Files、Do Not Touch、dependency、删除/重命名和stale-documentation scan；
- fresh evidence/output全部位于`/private/tmp/lqcd-agent-b01-*`，repository内没有runtime output。

不运行live provider、benchmark、Codex SDK、raw numeric data或历史`outputs/`。

Final negative report必须分别列出exact 105项`requirements.remaining`、`runtime_evidence`缺口和`exit_checks`缺口；缺失后续scenario/adapter是预期缺口，已有检查的解析、collection或证据错误不能被忽略。Final preflight未具备时不提前运行B05全套检查。

## Stop Conditions

既有合同及Allowed Files内的局部bug允许修复，但必须使用本票maintenance路径留痕；缺失前置功能、需要扩大范围或改变架构/schema/public contract/验收边界时停止，先创建并批准corrective ticket，不用maintenance授权新功能。

- B00未完成、B00 matrix/validator/failpoint contract不满足本ticket，或protocol/catalog exact digest不匹配；
- B00 ownership排序maintenance或fresh验收未通过，或B01需要修改registry/final obligations/seals、以纯probe替代durable runtime evidence才能验收；
- 需要改变A02 identity、A03 artifact/invalidation、A04 lifecycle、A06 budget或Control Protocol semantics；
- 所需静态定义无法追溯到冻结A02/A04/A06、与机读合同冲突，或需要重复定义/覆盖generated authority；
- 需要由B01创建coordinator/public operation、写Run root、开放graph edge或执行side effect才能证明owned requirement；
- 需要自动迁移或改写existing schema `0.2`/`0.3` Run；
- 需要新增state field、record variant、status、artifact slot、checkpoint authority或dependency而未由冻结合同批准；
- 需要修改B02–B05 ticket正文、B00 frozen files、existing tests、graph topology、provider/config/evaluation/raw data；
- 任何required B01 evidence必须依赖sleep timing、network、live provider、历史outputs、skip/xfail或test-only authority；
- baseline/full suite回归无法在Allowed Files内以contract-preserving local fix解决。

触发任一条件时保持B01未完成，记录证据并请求用户确认；改变冻结合同必须另开corrective ticket。

## Required Documentation Updates

- 若执行中发生既有边界内的局部修复，新增本票`docs/tickets/corrections/B01_MAINTENANCE.md`并向corrections index追加链接，记录问题、根因、改动、验证及关联ticket；
- `docs/ARCHITECTURE.md`：区分B01 pure control foundation与尚未实现的durable operations/product graph；
- `docs/STATE_SCHEMA.md`：记录versioned schema `0.4` records、bounded projection和`0.2/0.3/0.4` compatibility边界；
- `docs/ARTIFACT_CONTRACTS.md`：记录cross-head adapter与budget control artifact，不改变A03 slots；
- `docs/EVALS_AND_OBSERVABILITY.md`：记录B01 slice、construction totals和focused evidence；
- `docs/VERIFICATION_GUIDE.md`：加入B01 focused/construction/final expected-failure命令；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`、`docs/README.md`和`docs/REPO_CURRENT_STATE.md`：同步B01 lifecycle与remaining状态；
- `docs/DECISION_LOG.md`：记录实际module boundary、canonical replay和compatibility选择；
- `docs/tickets/completions/B01_COMPLETION.md`及completion index；
- 完成stale-documentation scan。

## Review Gate Before `ready`

- 确认本票maintenance路径和corrections index追加在Allowed Files内，已有历史不可改写；缺失前置功能或任何架构/schema/public contract/Allowed Files/验收边界变化必须停止并经corrective ticket批准；
- 确认B00 ownership排序maintenance及fresh验收已通过，合法slice前缀可接入且所有排序/ownership负向约束仍成立；
- 确认B01 exact owned set为11项、累计covered为26项、remaining为105项；
- 确认机读内容唯一消费generated projection，prose-only静态定义有冻结来源；protocol import/lookup无I/O不误伤trusted clock或显式Run root只读校验；
- 确认B01仅交付construction probes，registry/final obligations/seals不可修改，durable hook证据由后续owner实现且保留原requirement ownership；
- 确认A02C01 bootstrap和所有durable mutation留给B02，B01不以standalone writer冒充operation authority；
- 确认A03C01由adapter复用现有registry，不建立第二套artifact/current authority；
- 确认B01提供BudgetPolicy/record/fingerprint/clock及校验基础；B02负责start/replay/fork bootstrap admission，B04负责后续产品route/resource/grant/stop admission；
- 确认migration、Allowed Files、Do Not Touch和verification没有未决placeholder。

只有用户完成review并明确批准后，才能把B01 YAML提升为`ready`；起草本文件不授权执行。
