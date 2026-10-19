---
ticket_id: B05
phase: phase-b-graph-harness
status: ready
type: implementation
depends_on: [B00, B01, B02, B03, B04]
---

# 完成 Acceptance Integration and End-to-End Harness

## Goal

在不重新分配B00–B04 requirement ownership、不补做遗留subsystem实现的前提下，完成Layer 0–5跨子系统normalized traces、fault/concurrency组合验证、legacy compatibility独立报告、project-owned CLI smoke、full deterministic regression、full mock benchmark和由B00统一final驱动生成的完整需求与退出证据，形成Phase B唯一completion gate。

B05成功时，必须输出B00冻结的`PhaseBAcceptanceReport 0.1`：`requirements.required/covered/passed=131`、`requirements.remaining=0`、`requirements_zero_gap=true`和`phase_b_complete=true`。报告绑定本次工作树与合同摘要；各层scenario totals、legacy结果、smoke root及deferred capabilities保存在可核验证据和completion record中，不扩展closed report字段。

## Why

B04 construction达到`requirements.covered=131`、`requirements.remaining=0`只说明每个stable requirement都有owner下的场景映射；它不能自动证明跨operation/graph/backend/artifact/budget边界组合后仍满足exact ordering，也不能替代fresh CLI、full suite、mock benchmark和compatibility审计。

B05只负责把已经完成的实现作为一个系统验收。既有验收边界内、Allowed Files内的局部integration bug可以修复并记录maintenance；缺失前置功能，或需要改变架构、schema、public contract、Allowed Files或验收边界时，必须停止并走经批准的corrective ticket。不能用happy path、宽松trace或重新标注ownership掩盖缺口。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/tickets/README.md`
- `docs/tickets/corrections/README.md`
- 全部核心source-of-truth文档
- `docs/tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md`
- `docs/tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json`
- `docs/tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json`
- B00–B04 tickets及其completion records
- [B00C29 pytest runner 450秒政策](B00C29_PYTEST_RUNNER_TIMEOUT_450.md)：用户明确批准的唯一outer runner时限修订；不改变其他child deadline或业务预算。
- B00C01–B00C28、B02C01及B03C01/B03C02 corrective tickets、独立合同及completion records；[B00–B05审查记录](../corrections/B00_B05_READINESS_REVIEW.md)保留2026-09-22历史，当前入口以[B04完成记录](../completions/B04_COMPLETION.md)及各纠偏实际交接为准
- [B03C02 case0.4](B03C02_POST_CLAIM_UNSTARTED_CASE_SEMANTICS.md)、[C25进程Session绑定](B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md)、[C26故障来源](B00C26_B04_FAULT_SOURCE_AND_OWNED_ACTIVATION_HANDOFF.md)、[C27来源与fixture补充](B00C27_B04_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_FIXTURE_HANDOFF.md)和[C28绑定生命周期](B00C28_B04_OWNED_BINDING_LIFECYCLE_META_HANDOFF.md)
- `tests/phase_b/harness/driver.py`、`exit_checks.py`、`pytest_evidence.py`及当前显式版本的trace/proof validators
- `tests/phase_b/test_historical_source_control.py`中的`Archived03Reader`与`src/lqcd_agent/control/children.py`的`HistoricalSourceRead/_historical_source`；[测试维护基线](../corrections/TEST_INFRASTRUCTURE_MAINTENANCE.md)
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`
- B00–B04实际新增/修改的runtime、scripts和`tests/phase_b/`文件
- `evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py`
- `evaluation/synthetic_benchmarks/case_sets/full.json`
- `README.md`
- `pyproject.toml`

## Frozen Inputs and Entry Conditions

2026-10-19 用户审定：用户明确将“当前完整回归及维护后前置证据复核”和“长时验收分批安排”两项进入条件视为已满足，并授权审定本票、commit/push当前开发基线后执行。该确认允许进入B05，不构成新实跑的4785项通过证据，也不重标旧Session；本票实施后的完整fresh final、全部必需selection、450秒runner及Requirements 6的实际容量/批前检查仍必须执行。

- B00–B04及上述已交付纠偏必须全部为`completed`，各completion record和独立交接必须可复核；只看YAML状态不足。
- B04 construction report必须显示`construction.required/covered/passed=47`、B00–B04 slice union exact 131、`requirements.covered=131`、`requirements.remaining=0`、`requirements.passed/passed_ids=null`、`requirements_zero_gap=false`及`phase_b_complete=false`。
- Protocol/catalog exact versions/digests与前置票一致；matrix/registry/final obligations/generated projection的tracked digest必须记录为B05 baseline。
- 所有B00–B04 required nodeids在fresh collect中存在；任何missing/skip/xfail/deselect/live-only先视为entry failure，不由B05改写scenario为non-required。
- 当前入口基线为提交`057a8364a603a14e3de33eb8bbc870db15b32629`的B04交付：full **4749/4749**（Phase B4424、legacy325）、同Session独立owned **B02 1410/B03 645/B04 144**、fresh construction **15/11/30/28/47**。执行前逐文件比较验证/交付manifest；本次票据和索引的文档差异单列，不能把旧Session重标为B05。非文档输入变化时重新取得受影响的前置证据；本票最终full以当前fresh collect的完整集合为准，不能锁死4749而漏掉新增测试。
- 用户已授权的测试分层、单次验证AST复用、普通测试目录生命周期及ledger管线去重维护纳入本地待冻结基线，详见上述独立维护记录；原4749项、新增12项基础设施回归及24项ledger回归均须包含在完整selection中，当前fresh collect为4785项。ledger维护保留原fencing、严格解析、篡改检测、独立副本；后续统一pytest时限按C29改为450秒；27份expected仅按真实application_build变化审定重算摘要。B05批准前核验维护交付manifest、实际验收环境和完整回归；该维护不是B05实施，既有B04/纠偏Session不重标为新输入通过。
- 12项已复现的基线golden失败必须先定位并验证解决，不能归入本票新增CLI的摘要同步。记录实际Python、LangGraph和checkpointer版本；冻结expected绑定的真实runtime fingerprint，不能通过伪造版本、patch fingerprint、放宽normalizer、跳过断言或未经来源审定按actual覆盖expected取得通过。验收环境变化时重新验证来源和完整selection，不能将不同环境的结果拼接。
- 完整legacy回归需要原`lat-hadron-analysis/examples/l64c64a076_m140`的全部七份参考资料；本轮已用用户提供的原fit summary及`analysis-DA@f7277044bc49cf24d4bfabbf9f7e4e0004ff9b2b`的其余六份原资料恢复，独立legacy回归325/325通过。执行前仍须核验全部七份资料及来源摘要；资料缺失或当前完整selection未通过时，入口条件仍未满足。不能以部分资料、替代数据或8项legacy adapter通过替代325项完整验收。具体来源核验见测试维护记录。
- 前一ledger维护固定输入的C16/C21完整模块31/31、43/43及legacy325/325通过；原300秒正式C16子进程242.95秒通过，C21 triple_success直接运行422.545秒。用户随后通过已完成C29将统一pytest runner上限批准为450秒；C21在新的固定输入中经真实450秒runner通过，子进程395.88秒，原envelope/observation与Session验证均通过。前一422.545秒直接运行保留原输入，不重标为新证据。当前完整4785项仍待回归，不能由final adapter吞掉失败。
- 在adapter接入前，用原final命令核验入口负向：错误集合exact为原15项`exit_evidence_gap`（`adapter`），无coverage/binding缺口，退出码1。此入口不执行全局runtime，故其missing仍为2199、passed仍null，不能代替或否定独立owned证据。
- Full mock benchmark须在fresh根实跑并按原validator核验9个case及117项checklist；2026-10-17只读核验已通过，但不是B05 final evidence。环境失败、历史full证据及本次新运行结果分别记录。
- 继承B03C02冻结的case `0.4`：**2199 cases、324 boundaries、28条post-claim paths、B04 18 boundaries/144 cases**及原IDs/分类/owners不变；runtime obligations从独立规则生成。按实际来源选择已批准的显式trace/proof版本，现行最高为C26/C27的**trace `0.12` / proof `0.9`**；trace `0.1`–`0.11`及对应proof、旧case/sealed evidence保留原解释和拒绝行为，不统一升级或降级。B00–B04已有owned通过仅作入口证据，B05仍须在本次final Session验证全部2199项。
- 实施前保存文件快照、输入manifest、冻结票正文摘要和容量估算；按Requirements 6测量实际可用空间后才能启动长时验收。2026-10-17约15GiB的观测不是容量充分的证明。

## Scope

- 审计B00–B04 matrix slices互斥、union set-equal、scenario ownership、trace/invariant和fresh pytest result；
- 补充`validation_stage=final`的跨子系统required tests与exact normalized traces，对照B00独立final obligations补齐实际hook/case证据；matrix按B00–B04 owner拆成多个scenario并复用test nodeid/trace，每个scenario只引用其slice拥有的contract refs；
- 完成A07指定publication boundary的组合fault injection，覆盖bootstrap、Pause、ExternalOperation、budget/grant、terminal close、artifact和fresh Analysis；
- 完成two-client/two-process跨域winner、stale lease、same-key replay、post-claim failure和consumption-release组合测试；
- 在`src/lqcd_agent/graph/canonical_cli.py`建立显式schema `0.4` CLI和最小Host组装，由`scripts/run_phase_b_smoke.sh`调用真实CLI子进程；保留现有`run_graph.py`的legacy CLI；
- 为B00已冻结的全部exit check接入检查适配器，由统一final session运行Layer 0–5、cross-system fault/concurrency、Phase B suite、full pytest、compileall、synthetic tests、full mock benchmark、legacy regression、CLI smoke和documentation/scope检查；
- 将C04已验证的`run_pytest_batches`接入final dispatcher及需要分批的pytest exit adapters，避免完整runtime/full suite受单次450秒调用上限截断；保留同一session、冻结输入、完整selection及现有完成判定；
- 分别交付冻结`legacy_regression` adapter的8项检查和full-suite中全部325项legacy的独立统计，确认canonical coverage未调用legacy；
- 由final创建session、执行检查、验证本次证据后生成canonical report；任一必需检查缺失、失败或证据无效均非零退出；
- 完成scope、link、metadata、stale docs、diff和deferred capability审计，建立Phase B completion record。

## Non-goals

- 不拥有新的catalog requirement ID，不创建B05 implementation slice或重分配B00–B04 ownership；
- 不实现B01–B04遗漏的schema、coordinator、route、Code Agent、budget或artifact功能；
- 不改变Phase A contract、Control Protocol、catalog、matrix/report/exit evidence/final obligations schema、trace exclusion、evidence class或完成判定算法；
- 不新增product edge、state/artifact schema、operation variant、budget policy或migration policy；
- 不删除legacy entrypoint，不自动迁移old Run或转换legacy artifacts；
- 不安装/调用Codex SDK、真实Backend、live provider、RAG、raw numeric data或parallel graph；
- 不把mock benchmark/capability结果计入required control totals；
- 不发布deployment、PR、accepted scientific result或control-repo patch promotion。

## Migration Boundary

- Schema `0.2`来源验证通过后仅可replay，不可resume/fork；`0.3`禁止原地resume/migration，但来源验证通过且满足冻结资格时可replay/fork为新的`0.4` child；`0.4`按冻结fingerprint、source proof和资格规则处理。所有source Run保持不变，canonical CLI/API只创建或操作符合上述合同的`0.4`目标。
- Legacy CLI/graph/handoff只作为compatibility regression并单独报告；canonical smoke必须使用B03 Fake Code Agent和B04 target graph。
- CLI不能暴露raw checkpoint/thread ID、arbitrary state/route patch、force overwrite、caller-selected unrestricted output root或policy override。
- 所有smoke/benchmark/evidence使用fresh `/private/tmp/lqcd-agent-phase-b-*` root；repository `outputs/`与历史artifacts只做不变性审计，不作为evidence。

## Owned Requirement IDs

B05没有owned catalog IDs。A07已冻结“B01–B04拥有并转绿subsystem requirements，B05生成final zero-gap与exit evidence”。因此：

```text
owned_requirement_ids = []
```

- Matrix只包含B00–B04 implementation slices；B05不得增加空或重复slice。
- B05新增runtime scenario固定为`validation_stage=final`，保留原construction证据；新增或强化的scenario必须使用被验证合同的原owner `implementation_ticket_id`，每个scenario的refs仅来自该owner slice；跨owner integration test通过多个scenario复用同一pytest nodeid/trace，且不得改变原owned set。
- Final的`requirements.covered`来自131项catalog映射；`requirements.passed`必须同时满足construction/final适用场景和独立runtime obligations，不能仅凭set equality或B05自定义“integration complete”ID。

## Allowed Files

- `docs/tickets/corrections/B05_MAINTENANCE.md`：仅在发生本票范围内的contract-preserving局部修复时新增；同票后续条目只追加，不改写已记录事实；
- `docs/tickets/corrections/README.md`：仅追加本票maintenance链接，不改写已有索引项；
- `docs/tickets/phase-b-graph-harness/B05_ACCEPTANCE_INTEGRATION_AND_END_TO_END_HARNESS.md`：进入`ready`后只允许更新YAML lifecycle metadata；
- `scripts/validate_phase_b_acceptance.py`：允许接入B00已定义的检查适配器、命令调度及证据收集，并修复contract-preserving defects；不得改变已冻结schema、必需检查清单、证据规则或完成判定语义；
- `scripts/run_phase_b_smoke.sh`：仅启动本票canonical CLI smoke并传递受控输入，不实现另一套control/graph；
- `src/lqcd_agent/graph/canonical_cli.py`：仅新增Requirements 4的CLI解析、现有端口组装和有界deterministic/Fake Host适配，不增加公共控制请求schema、authority、状态机或provider能力；
- `tests/phase_b/test_historical_source_control.py`、`tests/phase_b/helpers/historical_trace_sources.py`、`tests/phase_b/helpers/process_client.py`：仅将原`Archived03Reader`最小只读实现移用到上述Host适配位置并改为从该唯一位置导入；历史fixture构造留在tests，原断言、格式资格和拒绝行为不变，不保留第二份reader；
- `tests/phase_b/`：仅限cross-subsystem scenarios/traces/fault/concurrency/CLI tests、已定义exit checks的适配器、matrix/registry实际hook和case绑定及report fixtures；不得重分配ownership或削弱前置tests；
- `tests/phase_b/harness/driver.py`及`exit_checks.py`：仅限将现有C04分批runner接入命令调度与exit adapter，保留preflight、原始selection、schema、session/摘要校验、observation/runtime验证和final完成规则；不得引入跨session拼接或历史证据替代；
- `tests/phase_b/harness/pytest_evidence.py`：仅允许在原`run_pytest_batches`循环增加由可信dispatcher提供的批前容量检查点及其定向回归；第一批前与后续批次间均检查，检查点只可中止，不得改写selection、批次、Session或证据。现行450秒runner、验证算法、逐批与合并集合检查、writer/schema和证据权威保持；
- `tests/phase_b/expected_traces/`及关联fixture：允许新增本票cross-system/CLI场景的固定expected；已有expected仅按Requirements 7审定同步本票批准的**CLI新增/Host组装或contract-preserving integration fix**引起的真实runtime fingerprint及派生head/reference。不改前置outcome/owner/invariant、旧sealed evidence或trace exclusion，不按运行actual批量重写expected；
- B01–B04实际引入的`src/lqcd_agent/control/`与`src/lqcd_agent/code_agent/`文件：仅限B05发现的contract-preserving integration fix；
- `src/lqcd_agent/graph/state.py`、`routing.py`、`analysis_graph.py`、`nodes.py`、`approval_packet.py`和`run_graph.py`：仅限canonical CLI/integration fix，不改变A01 topology；
- `src/lqcd_agent/artifacts/registry.py`、`src/lqcd_agent/memory/store.py`和`src/lqcd_agent/report/generate_report.py`：仅限cross-boundary integration fix；
- `README.md`及全部受实际完成状态影响的核心docs；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`；
- `docs/tickets/completions/B05_COMPLETION.md`；
- `docs/tickets/completions/README.md`。

## Do Not Touch

已有completion/correction记录及其历史内容保持不变；Allowed Files仅为本票maintenance新记录/追加条目与corrections index追加链接保留例外，不授权修改前置票据的记录。

- Phase A frozen files/protocol/catalog/completions/corrections、milestone和tag；
- B00–B04 frozen ticket bodies及其completion records；
- B00 matrix/report/exit evidence schema、final obligations及15项exit check清单、`SUITE_ROOTS`/完整selection校验、trace normalization exclusion、failpoint stable IDs和pytest evidence authority；
- `src/lqcd_agent/coder/` legacy implementation、legacy artifact formats和existing compatibility tests；
- `src/lqcd_agent/llm/`、`src/lqcd_agent/demo/`、`src/lqcd_agent/tools/`、`src/lqcd_agent/analysis/`和`src/lqcd_agent/analysis_programs/`；
- B05执行前已有的`tests/test_*.py`；
- `evaluation/` inputs/expected outputs/runner、`configs/`、`pyproject.toml`、dependencies、raw data、repository outputs、human decisions、accepted artifacts和secrets；
- provider/network/real Backend/external service、parallel topology和deployment systems。

## Requirements

### 1. Matrix and Evidence Closure

- 继承B00闭合协议：final validator从frozen catalog构造required set，核验owner slices互斥且union exact 131；执行construction与final两个阶段的全部适用required scenarios，并独立核对冻结runtime obligations。只有所有适用证据通过才计入`requirements.passed`，不得仅从matrix现有条目推断必需runtime清单。
- Unknown/non-required/duplicate/stale/uncovered/uncollectable/skipped/xfail/deselected/live-only/missing trace或invariant任一使final非零。
- Final创建one-time invocation token并启动必需检查；所有scenario、runtime与exit evidence绑定本次token、实际工作树输入摘要及protocol/catalog/generated protocol/matrix/registry/final obligations摘要。旧token、不同输入或合同版本、自报passing、仅collect成功均不能复用为验收证据。
- 全部required selection及各pytest exit check可在同一Session有界分批；逐批验证setup/call/teardown、无skip/xfail/deselect和输入未变，合并后核对集合exact、无重复/遗漏，再调用既有observation/runtime/exit验证器。保留原始batch receipts；不同exit check有各自完整selection，不能拿部分required测试冒充full-suite exit。任一批失败、超时、输入漂移、回执错session/case/nodeid或缺失，final均失败。
- Required runner和每个pytest adapter均复用原`run_pytest_batches`，使用互不冲突的check/name与batch编号；Layer、cross-system、Phase B suite和full-suite即使nodeid重叠，也各自执行并提交完整证据，不能复用另一个check的回执冒充运行。仍由原`validate_adapter_targets`校验各selection；共享node的observation按原owner/scenario规则验证，不过滤已知或未知的失败证据。
- 新CLI/跨进程测试沿用C25的真实父子request/Session绑定；不得以unit-only token、重写来源token或当前诊断补造正式hook/case result。测试内的final正反例继续使用隔离fixture和注入runner，禁止从required/full suite递归调用真实全仓final。
- Compatibility/capability/benchmark/happy-path evidence单独报告，不能增加required totals。
- Final report严格使用B00的`PhaseBAcceptanceReport 0.1`字段与完成语义，拒绝unknown字段/别名。规范化报告排除token、临时路径等不稳定值；原始证据保留session绑定，Layer 0–5 totals等明细通过证据与completion record复核。

### 2. Exact End-to-End Trajectories

- 对A07 required trajectory classes执行完整canonical schema `0.4` graph，比较exact normalized event sequence、identity、head、route/guard、ownership、budget、artifact/current/protection和capability。
- Planner gap → Fake Code Agent → external-result Pause → trusted verification → Code Bundle → fresh Analysis → Reviewer → Coordinator → report/END必须完整且不调用legacy。
- 四层fallback、Human validation/grant、budget exhaustion、recoverable timeout、terminal cancel/interrupt/close和child Replay/Fork分别具有完整exact trace。
- Trace只能删除A07允许的不稳定字段；event order、typed null、digest correlation或intermediate head drift均失败。

### 3. Cross-subsystem Fault and Concurrency

- B00 failpoint registry每个entry必须关联实际production hook、实际触发证据、全部适用outcome case、passing nodeid及exact trace；单有inventory/hook名称不足。META-006/015的construction pass不能替代这些final证明；漏列matrix scenario也必须被独立obligations检出。
- Bootstrap、publish_pause、dispatch/final evidence、resume claim、settlement、grant、Transition/invalidation、bundle/current、Analysis preparation/artifact、terminal checkpoint/result的每个组合prefix只允许same-operation continuation或typed fail-closed outcome。
- Post-claim按B03C02 current case0.4覆盖原7个entry phase的28项：前六阶段保留原safe-stop两格，并以12项真实跨进程`unstarted_recovery`替代不可达的consumer-unavailable项，证明`started_intent=null`、`not_dispatched`且stop adapter调用0次；`invocation_authorized`保留真实started consumer的四格。A07设计时7×4分类保持，runtime不能重新要求旧12项不可达组合；只有完整safe-stop（含可信not_dispatched）且authority appendable可failed lifecycle。
- Consumption release覆盖normal delivery/recoverable timeout后的settlement → Pause consumed → Attempt/artifact terminal → release → checkpoint → Transition/END/new operation，并拒绝duplicate/stale/foreign/N/A伪造。
- Two independent processes验证Pause/Run/External/grant/source/capability winners、normal/cancel/interrupt all orderings和late writer rejection；不用真实sleep或概率kill。

### 4. CLI Smoke and Compatibility

- 固定入口为`python -m lqcd_agent.graph.canonical_cli`，公开`start`、`resume`、`replay`、`fork`、`cancel`子命令，分别构造原typed request并调用project-owned `start_run|resume_run|replay_run|fork_run|cancel_pause`。`start`及合法child创建后用B04 compiled graph接续；`resume`复用`CanonicalProductRuntime.resume`的原target/后续graph接续。内部advance/close/interrupt仍由原Host owner选择，不新增CLI强制控制端口。
- Host组装复用现有Coordinator、ControlPlane、B04 runtime、B03 `ProductCodeHost`/`FakeCodingBackend`、workspace/containment与fresh Analysis端口；有限deterministic Agent返回只作为原Agent port输入，全部照常经过现有validator。CLI不得导入`tests/`实现，不能用直接调用场景工厂或修改ledger/数据库来模拟命令成功；smoke fixture只提供合成输入和Fake效果。
- `0.3`来源使用原`Archived03Reader`的最小可信只读Host适配：将现有实现移用至`canonical_cli.py`，原测试改为复用同一实现，保留原fixture格式的适用范围及拒绝语义。端口仍返回原typed `HistoricalSourceRead`，并由`ChildOperations._historical_source`独立验证原始bytes、identity、fingerprint、checkpoint、revision/CAS与资格；reader不能自选信任根、创建来源authority或将不支持格式降级为通过。历史fixture及其原控制状态只在测试准备阶段构造，不放入生产CLI；本票不新增通用历史reader、导入/迁移或新的来源资格。
- Actor、scope、预算profile和端口由可信Host固定选择，CLI不接受调用者自报的allow、权限、grant、settlement、stop proof、raw checkpoint/thread ID或arbitrary state/route patch；Human业务输入仍经原validator，不能直接变为科学接受或控制授权。Host分配fresh受控临时根，后续命令仅定位该受控根内的Run并经过原来源/权限校验，不开放任意output root、overwrite、policy override或provider配置。
- Fresh smoke至少核对control `run_status`与domain `status`、execution/artifact/checkpoint heads、canonical/projection bytes、budget counters、Pause lifecycle、child lineage、accepted protection和terminal owner。
- Smoke分别包含normal no-code、planned Fake code、Human Pause/resume、Replay/Fork和terminal stop；每个root唯一且不可overwrite。兼容fixtures必须证明合格`0.3` source可fork为`0.4` child，`0.2` fork和`0.3`原地resume被拒绝，原source bytes保持不变。
- Smoke由真实独立CLI进程运行，覆盖重复请求、跨进程接续、无效输入、越权/路径逃逸拒绝及无重复effect；校验实际持久材料，不能只断言输出文本或pytest子进程退出0。历史0.2/0.3来源适配只在原Replay/Fork端口中进行，不用legacy graph/result validator替代canonical coverage。
- 冻结`legacy_regression` adapter继续按`SUITE_ROOTS`运行`tests/test_codex_handoff_worker.py`与`tests/test_run_graph_with_codex_handoff.py`，当前共**8项**，不能扩大或缩小该selection。完整legacy集合由当前fresh collect的`tests/test_*.py`确定，入口共**325项**；从本次`full_pytest`的原始完整回执核对exact node集合、setup/call/teardown及无skip/xfail/deselect，另存legacy统计，不裁剪或改写full-suite回执。两份统计分别报告，8项通过不代表325项通过；不新增exit check或closed report字段。

### 5. Full Exit Verification

- Layer 0–5 focused tests、`pytest -q tests/phase_b`、完整`pytest -q`和compileall全部通过。
- Synthetic tests及full mock-provider benchmark通过，结果标为compatibility/capability，不计required totals但属于强制exit checks。Benchmark适配器必须核验full case-set完整性、每个case的structured passing/checklist与输出摘要；进程退出码为0而任一case/checklist失败仍判失败。
- No Codex SDK/live provider/network/raw data/history outputs/parallel graph/dependency change审计通过。
- Markdown links、ticket metadata、Allowed Files/Do Not Touch、deletion/rename、stale docs和`git diff --check`通过。
- Completion record不得只写pytest总数，必须保存final totals、layer commands、legacy count、mock benchmark、smoke root和deferred list。Final在本次全部检查执行和证据核验完成前不得生成成功报告；不能先成功final再另行运行smoke/benchmark补证。

### 6. Bounded Execution and Capacity

- 启动final前保存每个check的完整selection、预计批次数、代表节点耗时/临时数据实测、可用空间与预计峰值。容量估算包含required、各layer/cross-system、Phase B suite、full-suite重复执行产生的来源材料、smoke/benchmark和最终只读重验所需保留材料，并列出安全余量及停止阈值；不得只按单轮full规模或用户口述空闲容量判断。
- 以固定完整selection安排有界批次；已知耗时的C15/C16来源等节点应使用单节点或经实测可容纳的批次，保留现行450秒runner及各子进程既有上限。允许dispatcher选择较小batch_size和独立name，并仅在原`run_pytest_batches`循环加入上述批前容量检查点；不另写批处理/证据合并路径，不修改原validator或完成判定、不延长上限、不过滤慢节点、不增加exclusion，也不以多进程并行运行产品图规避限制。
- 若单个节点仍超过现行450秒上限，`batch_size=1`也不构成解决；先定位无用setup等contract-preserving维护原因并验证，不能仅缩小批次就宣称入口通过。无法在原合同内解决时按Stop Conditions停止。
- 长时验收前和批间检查剩余容量；容量不足则保存当前request、日志、失败/未执行清单并失败退出，不生成成功final。任何批次失败/超时的当次final不能转绿；调整调度或修复输入后启动新的fresh final Session，重新执行本次所需全部检查，旧失败/成功材料保留原token与摘要供审计，不拼接为新Session证据。
- 本票不授权自动删除旧证据或当前Session来源。清理仅在另有授权且确认关闭、无引用、不属于native/sealed/反例或重验依赖时进行；必要归档须验证可恢复性。无足够空间且不能安全清理时停止验收，不能缩减selection或删材料换取通过。

### 7. Expected Trace Review

- `runtime_fingerprint.application_build`来自整个生产包源码；新增canonical CLI即使不改控制语义也可能改变它。实施前保存原源码manifest、所有受影响expected/fixture与其原raw来源；CLI新增与本票允许的integration fix均是本节窄范围同步的合法原因。
- 旧expected逐项核对完整before/after来源和摘要依赖，只允许真实runtime fingerprint及由该变化推导的head/reference/digest差异；outcome、event order、typed null、operation/epoch/revision关系、owner、预算、invariant与各版本来源验证保持原语义。用两个独立fresh根经原normalizer验证后固定，并保存逐字段差异及原始材料；不能修改旧sealed evidence、伪造返回或重新执行旧effect来修补来源。
- 新cross-system/CLI expected从批准的原合同确定语义，经实际生产端口两份fresh来源审定后固定；新增场景继续归原B00–B04 owner，不修改旧case集合或旧expected的业务结论。正式final必须使用已固定expected和当前Session真实证据，不在验收中按actual重写expected。
- 若变化无法归因于上述摘要传播，或原严格trace/proof不能表达合法新组合，保存最小反例并按Stop Conditions停止；不得扩大normalizer/exclusion、放宽来源校验或以本节授权新schema。

## Deliverables

- 完整Layer 0–5 cross-system tests、exact traces与fault/concurrency evidence；
- stable explicit Phase B CLI smoke入口；
- B00闭合schema的final canonical JSON report与human summary；
- 冻结legacy adapter 8项、full-suite legacy 325项及full mock benchmark 9 case/117 checklist的独立证据与统计；
- 容量/分批计划、原始失败和batch receipts，以及新旧expected的来源审定记录；
- Phase B completion record、Overview/status/core docs同步；
- 明确defer到Phase C/D/E的real backend、capability/RAG和integrated benchmark事项。

## Acceptance Criteria

- B00–B04 completion evidence全部可复核，matrix slices互斥union exact 131；B05没有owned slice；
- 所有required scenarios fresh collect/pass，无skip/xfail/deselect/live-only/unknown/stale；
- Layer 0–5及A07全部cross-contract handoff/fault/concurrency断言通过；
- Final report为`requirements.required/covered/passed=131`、`requirements.remaining=0`、`requirements_zero_gap=true`及`phase_b_complete=true`，全部runtime obligations和exit checks均为本次有效passing evidence；
- Canonical CLI smoke从fresh root验证ledger/state/checkpoint/artifact/budget/Pause/child/accepted invariants；
- 冻结legacy adapter与全量legacy分别通过并报告8/325 exact node集合，canonical coverage不调用legacy graph/result validator；
- Full pytest、compileall、synthetic tests、full mock benchmark、links、metadata、scope、stale docs和diff checks全部通过；
- 同一final Session原2199 cases（1410/645/144）、131 requirements、15 exit checks全部通过；新增tests进入fresh完整collection，原324 boundaries/28 post-claim/18 B04 boundaries及owners不变；
- 容量/分批及expected审定记录完整，无跨check/Session替代、递归full final或输入漂移；
- 无live provider/real Backend/Codex SDK/raw data/history outputs/parallel/dependency/promotion变化。

## Verification

```bash
B05_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-phase-b-evidence-XXXXXX)"
python scripts/validate_phase_b_acceptance.py \
  --mode final \
  --evidence-dir "$B05_EVIDENCE_DIR/final" \
  --report "$B05_EVIDENCE_DIR/final-report.json"
```

这一个final命令必须按B00协议创建session、执行检查并核验本次证据，最后生成报告。它负责调用Phase A validator、generated protocol check、fresh collect与Layer 0–5 focused nodeids、cross-system fault/concurrency、Phase B suite、完整pytest、compileall、synthetic tests、full mock benchmark、legacy regression、CLI smoke及文档/scope/diff检查；不能通过事后手动运行检查使先前报告转绿。

Final dispatcher须为smoke/benchmark建立本次唯一的fresh子目录，并保存：

- 本次工作树输入及matrix/registry/protocol/catalog/generated protocol/final obligations digests与闭合报告；
- two-process winner/fencing、全部cross-system failpoints和逐hook/case触发证据；
- 28条post-claim failure paths、publication、fresh Analysis和consumption-release closure；
- canonical CLI smoke roots及逐项bytes/invariant审计；
- legacy compatibility nodeids/pass count；
- 冻结legacy adapter的8项与full-suite的325项分别列明selection和原始回执引用，不将8项声称为全量legacy；
- synthetic tests及full mock benchmark的完整case-set、逐case passing/checklists；
- 容量估算/余量/停止阈值、每check完整分批计划和request/receipt命名、CLI/Host组装来源及expected before/after双fresh审定材料；
- no-live/no-raw/no-history-output/no-dependency/no-parallel/no-promotion、scope、links、metadata和stale-doc结果。

还必须以B00隔离fixture/session机制验证以下反例，不递归启动真实full final：

- 131项已映射，甚至所有requirement已通过，但缺CLI smoke、benchmark或legacy有效证据时，`phase_b_complete=false`且final非零；
- Inventory齐全但hook未触发、outcome缺失或28条post-claim path缺一时，`requirements_zero_gap=false`且final非零；
- 旧token、不同工作树输入或不同合同摘要的证据被拒绝；
- 分批遗漏/重复nodeid、错session/case/nodeid进程回执、批间输入变化、失败/超时及full-suite selection不完整均被拒绝；正常分批与同一完整selection的验证语义一致；
- 不同check复用回执、旧final恢复拼接、legacy仅8项却声称325项、CLI绕过真实命令或注入Host权限，以及容量不足仍声称完成均须拒绝；容量/调度反例使用隔离fixture，不耗尽真实磁盘或递归启动全仓final；
- 批前容量检查点在首批及批间拒绝时，不启动该批或后续批次；保留已执行批次的原始request/receipt，最终失败且不跨Session续拼。检查点启用/未启用时，容量充足的同一完整selection仍经原逐批、合并及来源验证；历史reader移用前后原正负测试与拒绝行为一致；
- Benchmark退出码为0但case/checklist失败，或full case-set不完整时，exit check失败；
- 合法0.3 fork创建0.4 child；0.2 fork与0.3原地resume拒绝，source不改写；
- Bootstrap绕过可信admission或注入allow拒绝；
- 每票局部修复所需maintenance路径及index追加都在Allowed Files内，历史记录不可改写。

不得运行`RUN_LIVE_LLM_TESTS=1`或任何real backend。

## Stop Conditions

既有合同及Allowed Files内的局部bug允许修复，但必须使用本票maintenance路径留痕；缺失前置功能、需要扩大范围或改变架构/schema/public contract/验收边界时停止，先创建并批准corrective ticket，不用maintenance授权新功能。

- 任一B00–B04 ticket未完成、completion record缺失或construction evidence不可复核；
- matrix在B05开始时不是131 covered/0 remaining，或存在owner overlap/gap；
- 任一required scenario/nodeid失败、缺失、skip/xfail/deselect/live-only，且原因是前置subsystem实现缺口；
- 需要改变Phase A contract、protocol/catalog、matrix/trace/evidence schema、B00–B04 ownership或public runtime contract；
- 需要新增product edge/state/artifact/operation/budget/migration/dependency才能通过；
- 需要真实Backend/provider/network/raw data/history outputs/parallel graph或宽松trace；
- 需要修改B00–B04 frozen ticket/completion、legacy formats/tests或evaluation expected outputs；
- 需要改变旧trace/proof来源语义、case集合/分类、`SUITE_ROOTS`/selection规则，或expected差异超出Requirements 7的授权摘要传播；
- CLI需要在已列路径之外新增生产模块，或需要新公共控制合同、authority、provider/dependency才能组装现有端口；
- 无法满足容量估算与安全余量，或需要删除受保护来源/跨Session复用/放宽timeout与selection才能完成；容量恢复后先重新核验入口，不把容量停止记作subsystem已通过；
- 本票范围内的adapter/调度/跨域场景接线及允许的integration fix完成后，final仍无法用本次有效证据证明全部131项适用requirement、独立runtime obligations及所有exit checks通过；不得因覆盖数已满而忽略缺口。B05开始时尚未接入本票负责的exit adapter不是前置功能缺失，可在本票范围继续实施；
- baseline/full/benchmark回归无法在Allowed Files内以contract-preserving maintenance fix解决。

触发任一条件时不得标记Phase B completed。局部contract-preserving integration bug按仓库规则建立maintenance record；改变架构/schema/public contract/acceptance boundary则建立corrective ticket并重新review。

## Required Documentation Updates

- 若执行中发生既有边界内的局部修复，新增本票`docs/tickets/corrections/B05_MAINTENANCE.md`并向corrections index追加链接，记录问题、根因、改动、验证及关联ticket；
- 所有核心source-of-truth文档：只把实际通过final evidence的能力从“目标/未实现”更新为“当前实现”，保留deferred边界；
- `docs/EVALS_AND_OBSERVABILITY.md`和`docs/VERIFICATION_GUIDE.md`：记录final命令、Layer totals、legacy 8/325两种统计、mock/smoke结果、容量/分批和来源审定规则；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`：标记Phase B exit与Phase C entry；
- `docs/README.md`、`README.md`和`docs/REPO_CURRENT_STATE.md`：同步canonical/legacy入口和当前状态；
- `docs/DECISION_LOG.md`：记录final integration与本票canonical CLI/Host组装的实际交付；
- `docs/tickets/completions/B05_COMPLETION.md`及completion index；
- 完成全仓stale-documentation scan并检查所有“Phase B未实现/没有matrix/tests/runtime”的陈述。

## Review Gate Before `ready`

- 确认本票maintenance路径和corrections index追加在Allowed Files内，已有历史不可改写；缺失前置功能或任何架构/schema/public contract/Allowed Files/验收边界变化必须停止并经corrective ticket批准；
- 确认B05 owned set为空且matrix不创建B05 slice；
- 确认B04映射覆盖齐全不表示完整需求已通过；`requirements_zero_gap`与`phase_b_complete`分别绑定runtime证据和完整exit evidence；
- 确认B05不能补做或重新标注B01–B04缺失功能；既有边界内的局部integration bug允许修复并记录maintenance，边界变化必须corrective；
- 确认统一final先执行所有检查再生成报告，token/工作树/合同摘要有效；final totals、Layer commands、CLI smoke、legacy/mock独立证据与deferred list完整；
- 确认C04分批机制的final/exit接线在Allowed Files内，所有批次同Session且集合完整；调度变化不改变B00/C04证据权威、trace规则、必需检查或完成语义；
- 确认当前case0.4、显式trace/proof至0.12/0.9和旧版本隔离，原2199/324/28/144/15及ownership保持，B04实际47/144与入口负向15 adapter可复核；
- 确认canonical_cli.py及最小Host组装范围明确，CLI新增引起的fingerprint同步可按Requirements 7执行，不能借此改变来源/业务语义；
- 确认历史reader只移用原最小只读实现且由生产与测试共享，fixture写入不进入CLI，原`ChildOperations`来源校验不变；容量检查点只接入原批处理循环、不复制runner或改变证据权威；
- 确认测试维护纳入待冻结输入、原4749加新增12项基础设施与24项ledger回归共4785项完整收集，12项golden基线失败已有可复核根因与解决证据；实际运行环境和输入manifest明确，用户进入条件确认不替代本票fresh final回归；
- 确认legacy adapter 8项与full-suite legacy 325项分别验收，容量/批次/失败保留与fresh Session规则明确，不把重复运行成本遗漏在容量估算之外；
- 确认0.2仅replay、合格0.3可replay/fork为0.4 child而不可原地resume，且不存在caller注入bootstrap allow的路径；
- 确认Allowed Files、Do Not Touch、maintenance/corrective边界和verification没有未决placeholder。

只有用户完成review并明确批准后，才能把B05 YAML提升为`ready`；起草本文件不授权执行。
