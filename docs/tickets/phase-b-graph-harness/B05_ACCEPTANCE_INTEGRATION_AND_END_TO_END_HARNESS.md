---
ticket_id: B05
phase: phase-b-graph-harness
status: draft
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
- B00C01–B00C04、B02C01 corrective tickets及其completion records；现行依据见[B00–B05审查记录](../corrections/B00_B05_READINESS_REVIEW.md)
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`
- B00–B04实际新增/修改的runtime、scripts和`tests/phase_b/`文件
- `evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py`
- `evaluation/synthetic_benchmarks/case_sets/full.json`
- `README.md`
- `pyproject.toml`

## Frozen Inputs and Entry Conditions

- B00–B04必须全部为`completed`，各completion record必须存在并包含fresh evidence；只看YAML状态不足。
- B04 construction report必须显示`construction.required/covered/passed=47`、B00–B04 slice union exact 131、`requirements.covered=131`、`requirements.remaining=0`、`requirements.passed/passed_ids=null`、`requirements_zero_gap=false`及`phase_b_complete=false`。
- Protocol/catalog exact versions/digests与前置票一致；matrix/registry/final obligations/generated projection的tracked digest必须记录为B05 baseline。
- 所有B00–B04 required nodeids在fresh collect中存在；任何missing/skip/xfail/deselect/live-only先视为entry failure，不由B05改写scenario为non-required。
- 执行前记录cleanly attributable full-suite和full mock benchmark baseline；环境失败必须与implementation回归分开。
- Baseline继承case语义`0.2`、trace `0.4`及旧版本各自冻结语义；全部runtime case从独立规则生成，不从matrix当前绑定倒推。B00–B04已有owned runtime通过是入口证据，B05仍须在本次final session重新验证。

## Scope

- 审计B00–B04 matrix slices互斥、union set-equal、scenario ownership、trace/invariant和fresh pytest result；
- 补充`validation_stage=final`的跨子系统required tests与exact normalized traces，对照B00独立final obligations补齐实际hook/case证据；matrix按B00–B04 owner拆成多个scenario并复用test nodeid/trace，每个scenario只引用其slice拥有的contract refs；
- 完成A07指定publication boundary的组合fault injection，覆盖bootstrap、Pause、ExternalOperation、budget/grant、terminal close、artifact和fresh Analysis；
- 完成two-client/two-process跨域winner、stale lease、same-key replay、post-claim failure和consumption-release组合测试；
- 建立stable explicit schema `0.4` CLI入口与新的`/private/tmp/lqcd-agent-phase-b-*` smoke；保留legacy compatibility入口；
- 为B00已冻结的全部exit check接入检查适配器，由统一final session运行Layer 0–5、cross-system fault/concurrency、Phase B suite、full pytest、compileall、synthetic tests、full mock benchmark、legacy regression、CLI smoke和documentation/scope检查；
- 将C04已验证的`run_pytest_batches`接入final dispatcher及需要分批的pytest exit adapters，避免完整runtime/full suite受单次300秒调用上限截断；保留同一session、冻结输入、完整selection及现有完成判定；
- 独立统计legacy compatibility regression，确认canonical coverage未调用legacy；
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
- `scripts/run_phase_b_smoke.sh`；
- `tests/phase_b/`：仅限cross-subsystem scenarios/traces/fault/concurrency/CLI tests、已定义exit checks的适配器、matrix/registry实际hook和case绑定及report fixtures；不得重分配ownership或削弱前置tests；
- `tests/phase_b/harness/driver.py`及`exit_checks.py`：仅限将现有C04分批runner接入命令调度与exit adapter，保留preflight、原始selection、schema、session/摘要校验、observation/runtime验证和final完成规则；不得引入跨session拼接或历史证据替代；
- `tests/phase_b/expected_traces/`及关联fixture：仅允许对本票production integration fix造成的真实runtime fingerprint与派生head/reference做审定同步，保存原始来源和逐项差异，两个fresh根复核后固定；不改前置outcome/owner/invariant，不按运行actual重写expected或放宽trace exclusion；
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
- B00 matrix/report/exit evidence schema、final obligations及exit check清单、trace normalization exclusion、failpoint stable IDs和pytest evidence authority；
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
- Post-claim integrity failure覆盖frozen 7个entry phase与consumer-stop safe/unavailable × Run-authority appendable/unavailable四格，共28条publication paths；只有safe+appendable可failed lifecycle。
- Consumption release覆盖normal delivery/recoverable timeout后的settlement → Pause consumed → Attempt/artifact terminal → release → checkpoint → Transition/END/new operation，并拒绝duplicate/stale/foreign/N/A伪造。
- Two independent processes验证Pause/Run/External/grant/source/capability winners、normal/cancel/interrupt all orderings和late writer rejection；不用真实sleep或概率kill。

### 4. CLI Smoke and Compatibility

- Explicit canonical CLI只通过project-owned `start_run|resume_run|replay_run|fork_run|cancel_pause`接口，不直接resume LangGraph checkpoint或patch state。
- Fresh smoke至少核对control `run_status`与domain `status`、execution/artifact/checkpoint heads、canonical/projection bytes、budget counters、Pause lifecycle、child lineage、accepted protection和terminal owner。
- Smoke分别包含normal no-code、planned Fake code、Human Pause/resume、Replay/Fork和terminal stop；每个root唯一且不可overwrite。兼容fixtures必须证明合格`0.3` source可fork为`0.4` child，`0.2` fork和`0.3`原地resume被拒绝，原source bytes保持不变。
- Legacy graph/CLI/handoff regression完整通过并单独计数；canonical matrix/nodeids不得导入或调用legacy result validator。

### 5. Full Exit Verification

- Layer 0–5 focused tests、`pytest -q tests/phase_b`、完整`pytest -q`和compileall全部通过。
- Synthetic tests及full mock-provider benchmark通过，结果标为compatibility/capability，不计required totals但属于强制exit checks。Benchmark适配器必须核验full case-set完整性、每个case的structured passing/checklist与输出摘要；进程退出码为0而任一case/checklist失败仍判失败。
- No Codex SDK/live provider/network/raw data/history outputs/parallel graph/dependency change审计通过。
- Markdown links、ticket metadata、Allowed Files/Do Not Touch、deletion/rename、stale docs和`git diff --check`通过。
- Completion record不得只写pytest总数，必须保存final totals、layer commands、legacy count、mock benchmark、smoke root和deferred list。Final在本次全部检查执行和证据核验完成前不得生成成功报告；不能先成功final再另行运行smoke/benchmark补证。

## Deliverables

- 完整Layer 0–5 cross-system tests、exact traces与fault/concurrency evidence；
- stable explicit Phase B CLI smoke入口；
- B00闭合schema的final canonical JSON report与human summary；
- legacy compatibility和full mock benchmark独立报告；
- Phase B completion record、Overview/status/core docs同步；
- 明确defer到Phase C/D/E的real backend、capability/RAG和integrated benchmark事项。

## Acceptance Criteria

- B00–B04 completion evidence全部可复核，matrix slices互斥union exact 131；B05没有owned slice；
- 所有required scenarios fresh collect/pass，无skip/xfail/deselect/live-only/unknown/stale；
- Layer 0–5及A07全部cross-contract handoff/fault/concurrency断言通过；
- Final report为`requirements.required/covered/passed=131`、`requirements.remaining=0`、`requirements_zero_gap=true`及`phase_b_complete=true`，全部runtime obligations和exit checks均为本次有效passing evidence；
- Canonical CLI smoke从fresh root验证ledger/state/checkpoint/artifact/budget/Pause/child/accepted invariants；
- Legacy compatibility独立通过，canonical coverage不调用legacy；
- Full pytest、compileall、synthetic tests、full mock benchmark、links、metadata、scope、stale docs和diff checks全部通过；
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
- synthetic tests及full mock benchmark的完整case-set、逐case passing/checklists；
- no-live/no-raw/no-history-output/no-dependency/no-parallel/no-promotion、scope、links、metadata和stale-doc结果。

还必须以B00隔离fixture/session机制验证以下反例，不递归启动真实full final：

- 131项已映射，甚至所有requirement已通过，但缺CLI smoke、benchmark或legacy有效证据时，`phase_b_complete=false`且final非零；
- Inventory齐全但hook未触发、outcome缺失或28条post-claim path缺一时，`requirements_zero_gap=false`且final非零；
- 旧token、不同工作树输入或不同合同摘要的证据被拒绝；
- 分批遗漏/重复nodeid、错session/case/nodeid进程回执、批间输入变化、失败/超时及full-suite selection不完整均被拒绝；正常分批与同一完整selection的验证语义一致；
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
- 本票范围内的adapter/调度/跨域场景接线及允许的integration fix完成后，final仍无法用本次有效证据证明全部131项适用requirement、独立runtime obligations及所有exit checks通过；不得因覆盖数已满而忽略缺口。B05开始时尚未接入本票负责的exit adapter不是前置功能缺失，可在本票范围继续实施；
- baseline/full/benchmark回归无法在Allowed Files内以contract-preserving maintenance fix解决。

触发任一条件时不得标记Phase B completed。局部contract-preserving integration bug按仓库规则建立maintenance record；改变架构/schema/public contract/acceptance boundary则建立corrective ticket并重新review。

## Required Documentation Updates

- 若执行中发生既有边界内的局部修复，新增本票`docs/tickets/corrections/B05_MAINTENANCE.md`并向corrections index追加链接，记录问题、根因、改动、验证及关联ticket；
- 所有核心source-of-truth文档：只把实际通过final evidence的能力从“目标/未实现”更新为“当前实现”，保留deferred边界；
- `docs/EVALS_AND_OBSERVABILITY.md`和`docs/VERIFICATION_GUIDE.md`：记录final命令、Layer totals、legacy/mock/smoke结果；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`：标记Phase B exit与Phase C entry；
- `docs/README.md`、`README.md`和`docs/REPO_CURRENT_STATE.md`：同步canonical/legacy入口和当前状态；
- `docs/DECISION_LOG.md`：记录final integration和实际CLI/module选择；
- `docs/tickets/completions/B05_COMPLETION.md`及completion index；
- 完成全仓stale-documentation scan并检查所有“Phase B未实现/没有matrix/tests/runtime”的陈述。

## Review Gate Before `ready`

- 确认本票maintenance路径和corrections index追加在Allowed Files内，已有历史不可改写；缺失前置功能或任何架构/schema/public contract/Allowed Files/验收边界变化必须停止并经corrective ticket批准；
- 确认B05 owned set为空且matrix不创建B05 slice；
- 确认B04映射覆盖齐全不表示完整需求已通过；`requirements_zero_gap`与`phase_b_complete`分别绑定runtime证据和完整exit evidence；
- 确认B05不能补做或重新标注B01–B04缺失功能；既有边界内的局部integration bug允许修复并记录maintenance，边界变化必须corrective；
- 确认统一final先执行所有检查再生成报告，token/工作树/合同摘要有效；final totals、Layer commands、CLI smoke、legacy/mock独立证据与deferred list完整；
- 确认C04分批机制的final/exit接线在Allowed Files内，所有批次同Session且集合完整；调度变化不改变B00/C04证据权威、trace规则、必需检查或完成语义；
- 确认0.2仅replay、合格0.3可replay/fork为0.4 child而不可原地resume，且不存在caller注入bootstrap allow的路径；
- 确认Allowed Files、Do Not Touch、maintenance/corrective边界和verification没有未决placeholder。

只有用户完成review并明确批准后，才能把B05 YAML提升为`ready`；起草本文件不授权执行。
