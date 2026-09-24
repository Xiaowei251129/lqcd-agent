---
ticket_id: B03
phase: phase-b-graph-harness
status: blocked
type: implementation
depends_on: [B00, B01, B02]
---

# 实现 Graph-managed Fake Code Agent

## Goal

在B02 durable control authority之上，实现A05冻结的`CodeAgentSubgraph`、`CodingBackend` port、coordinator-owned `ExternalOperation 0.1`、deterministic `FakeCodingBackend`、workspace/containment、图外ingress、trusted verification、canonical Code Bundle和fresh Analysis handoff，并让B03拥有的28项requirements通过construction-mode验收。

B03完成后，B00–B03累计required映射覆盖必须为84项，`requirements.remaining=47`且`phase_b_complete=false`。B03证明canonical Fake Code Agent control path可用，但不把它接成A01完整产品拓扑；Planner/Coordinator发起code、success/non-success产品route和统一budget stop由B04完成。

所有construction数量仅对应本票`validation_stage=construction`证据。全局`requirements.passed/passed_ids=null`，`requirements_zero_gap=false`；原owner下新增的final scenarios和B00独立runtime obligations必须在final重新验证。

## Why

当前`legacy_codex_handoff`只消费外部文件，不能证明Backend operation幂等、workspace隔离、external-result Pause、trusted verification、content-addressed bundle或fresh Analysis。直接让B04沿用legacy node会违反A05/A07 canonical coverage边界。

B03先在真实B02 operation/Pause/lease入口上建立可替换Backend边界，并用完全network-free的Fake证明所有外部副作用和结果消费受Host控制。Phase C只允许替换backend，不得绕过B03固定的schema、validator、verification、registry和Analysis入口。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/tickets/README.md`
- `docs/tickets/corrections/README.md`
- `docs/ARCHITECTURE.md`
- `docs/AGENT_ROLES_AND_BOUNDARIES.md`
- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/EVALS_AND_OBSERVABILITY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md`
- `docs/tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md`
- `docs/tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md`
- `docs/tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md`
- `docs/tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md`
- `docs/tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json`
- `docs/tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json`
- `docs/tickets/phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md`
- `docs/tickets/phase-b-graph-harness/B01_EXECUTION_0_4_CONTROL_FOUNDATION.md`
- `docs/tickets/phase-b-graph-harness/B02_DURABLE_CONTROL_OPERATIONS.md`
- `docs/tickets/completions/B00_COMPLETION.md`
- `docs/tickets/completions/B01_COMPLETION.md`
- `docs/tickets/completions/B02_COMPLETION.md`
- B00C01–B00C04、B02C01 corrective tickets及其completion records；现行依据见[B00–B05审查记录](../corrections/B00_B05_READINESS_REVIEW.md)
- `src/lqcd_agent/coder/task_packet.py`
- `src/lqcd_agent/coder/test_runner.py`
- `src/lqcd_agent/tools/command_runner.py`
- `src/lqcd_agent/artifacts/registry.py`
- B00–B02实际新增的control和Phase B harness文件

## Frozen Inputs and Entry Conditions

- B00–B02必须为`completed`；B02 construction report必须exact显示30 owned passed、累计56 covered和75 remaining。
- Protocol/catalog exact versions/digests不变；B03必须复用B02 coordinator、Pause、lease/capability与terminal ownership，不得建立Backend-local transaction authority。
- A05 `0.1` schemas、status taxonomy、workspace lifecycle、containment proof、bundle members和Analysis handoff是冻结合同，不允许根据Fake实现能力缩减。
- 执行前记录B00–B02 focused、full pytest与B02 final expected-failure基线。
- 验收继承已完成corrective的case语义`0.2`和source-bound trace `0.4`；旧trace版本语义不变，不能回退到B00原始case计数或放宽digest检查。B02的205 boundaries/1410 cases与当前全局独立集合必须由冻结规则重算并核对。

## Scope

- 实现`CodeAgentTask 0.1`、`WorkspaceManifest 0.1`、`WorkspaceSeal 0.1`、dispatch receipt、external/canonical result、change manifest、verification results、tool audit和`AnalysisExecutionSpec 0.1` closed schemas；
- 实现Host-owned `ExternalOperation 0.1` identity/core/final-evidence lifecycle及与B02同一coordinator的normal/cancel/interrupt resolution CAS；
- 实现`CodingBackend`的`dispatch | lookup | fetch_result | cancel` port和由stable scenario ID选择结果的`FakeCodingBackend`；
- 实现deterministic workspace provider、write lease、seal、release和test-only strict containment provider，不操作current control repository；
- 实现durable watchdog、request-owned normal safe-stop candidate、normal-unavailable到integrity interrupt的handoff，以及cancel/interrupt safe/unavailable proof；
- 实现图外ingress validator、trusted verification、canonical Code Bundle registration与fresh Analysis preparation/execution handoff；
- 建立可被B04嵌入parent graph的`CodeAgentSubgraph`，pre-start stage不产生额外work/control Attempt；
- 用B02 generic `advance_run` adapter证明success handoff、valid non-success outcome与post-claim failure closure，但不计A01 product edge；
- 增加B03 owned matrix scenarios、normalized traces、failpoint bindings、restart/concurrency tests和fresh pytest evidence。

## Non-goals

- 不接入Planner/Coordinator product edge，不实现A01 route rows或四层fallback；
- 不把B03 generic parent adapter计作`method_planner -> code_agent`、`decision_coordinator -> code_agent`、`code_agent -> analysis_engineer|decision_coordinator`的A01 coverage；
- 不实现B04产品route选择、通用resource admission、Human grant、global loop stop或accepted memory/report终态；本票Code backend aggregate及trusted verification所需的A06 reservation/admission/settlement属于B03，不等待B04；
- 不安装或调用Python Codex SDK、Codex CLI、Agents SDK SandboxAgent或其他真实backend；
- 不使用network、真实provider、raw numeric data、accepted payload或current repository作为coding/analysis workspace；
- 不commit/merge/push/PR/deploy或把verified patch promotion到control repository；
- 不删除、改名或转换legacy handoff；
- 不让真实matrix通过final mode。

## Migration Boundary

- Canonical `code_agent`与`legacy_codex_handoff`使用不同Attempt kind、task/result validator、artifact identity和route guard；不转换legacy packet/result为A05 bundle。
- Phase B只注册`FakeCodingBackend`。Future real backend必须通过Phase C C00门禁并复用完全相同port/schema/Host control，不在B03预留绕过分支。
- 每个Code Attempt使用fresh Host-owned workspace，以immutable full Git commit/tree为base；dirty control worktree、source Run workspace、旧Attempt或provider session不可复用。
- Fake结果只能由trusted harness stable fixture ID选择；task自由文本、Agent payload或Backend自报不能选择成功、预算或route outcome。
- Existing schema `0.2`/legacy graph保持不变；canonical B03 subgraph只从B02 schema `0.4` interface进入。

## Owned Requirement IDs

B03 slice固定为以下28项：

```text
A05-CODE-002
A05-CODE-003
A05-CODE-004
A05-CODE-005
A05-CODE-006
A05-CODE-007
A05-CODE-008
A05-CODE-011
A05-CODE-012
A05-CODE-013
A05-CODE-014
A05-CODE-015
A05-CODE-016
A05-CODE-017
A05-CODE-018
A05-CODE-019
A05-CODE-020
A05-CODE-021
A05-CODE-022
A05-CODE-024
A05-CODE-025
A05-CODE-026
A05-CODE-027
A05-CODE-028
A05-CODE-029
A06-BUDGET-004
A06-BUDGET-007
A06-BUDGET-008
```

以下A05 cross-product IDs明确由B04拥有，不属于B03 slice：`A05-CODE-001`、`A05-CODE-009`、`A05-CODE-010`、`A05-CODE-023`。`A06-BUDGET-019`及其他统一stop/settlement route IDs也由B04闭合。

- B03 owned refs union必须set-equal为28项；B00–B03累计映射covered exact为84项，remaining exact为47项。
- B03可以为后续cross-product IDs提供非required support tests，但不得把它们计入B03 required totals或提前声明产品route pass。

## Proposed File Layout

```text
src/lqcd_agent/code_agent/
  __init__.py
  schemas.py
  backend.py
  fake_backend.py
  external_operation.py
  workspace.py
  containment.py
  ingress.py
  verification.py
  artifacts.py
  analysis_handoff.py
  subgraph.py
tests/phase_b/
  test_fake_code_agent.py
  test_external_operation_recovery.py
  test_code_agent_trust_boundary.py
  expected_traces/
```

Runtime schemas和validators位于`src/`；scenario selection、fault injection配置与Fake outcomes位于`tests/phase_b/`，不能成为production task输入。

## Allowed Files

- `docs/tickets/corrections/B03_MAINTENANCE.md`：仅在发生本票范围内的contract-preserving局部修复时新增；同票后续条目只追加，不改写已记录事实；
- `docs/tickets/corrections/README.md`：仅追加本票maintenance链接，不改写已有索引项；
- `docs/tickets/phase-b-graph-harness/B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md`：进入`ready`后只允许更新YAML lifecycle metadata；
- `src/lqcd_agent/code_agent/`：仅限上述canonical A05/Fake实现；
- B01/B02已有的`src/lqcd_agent/control/`文件：仅限ExternalOperation coordinator integration、resource binding、watchdog/settlement和typed target preparation adapter；
- `src/lqcd_agent/artifacts/registry.py`：仅限A05 code bundle/member/dependency registration adapter，不改变A03 slot/invalidation policy；
- `tests/phase_b/`：仅限B03 slice、Fake/backend/workspace/recovery fixtures、expected traces和failpoint bindings；不得削弱前置tests；
- `tests/phase_b/expected_traces/`及其关联fixture：允许对本票production源码变动引起的真实runtime fingerprint及其派生head/reference做前置golden同步；须保存新旧差异及真实来源、在两个fresh根复核后审定固定。不得改route/outcome/owner/invariant，不得测试时按actual重写expected、固定伪造production fingerprint或扩大trace exclusion；超出这类派生变化按Stop Conditions处理；
- `tests/phase_b/acceptance_matrix.json`及registry bindings：允许为本票实现对应的runtime义务追加`validation_stage=final`场景，引用本票或已存在前置slice的原owner（包括B00 meta IDs）；不改ownership、不预填后续slice、不修改B00冻结schemas/obligations/必需check清单；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`；
- `docs/tickets/completions/B03_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `docs/ARCHITECTURE.md`；
- `docs/AGENT_ROLES_AND_BOUNDARIES.md`；
- `docs/STATE_SCHEMA.md`；
- `docs/ARTIFACT_CONTRACTS.md`；
- `docs/SECURITY_AND_DATA_POLICY.md`；
- `docs/EVALS_AND_OBSERVABILITY.md`；
- `docs/VERIFICATION_GUIDE.md`；
- `docs/REPO_CURRENT_STATE.md`；
- `docs/DECISION_LOG.md`。

## Do Not Touch

已有completion/correction记录及其历史内容保持不变；Allowed Files仅为本票maintenance新记录/追加条目与corrections index追加链接保留例外，不授权修改前置票据的记录。

- Phase A frozen tickets/protocol/catalog、completed/correction records、milestone和tag；
- B00–B02 frozen ticket bodies及B04/B05 ticket正文；
- `src/lqcd_agent/coder/` legacy implementation及其tests/artifact formats；
- `src/lqcd_agent/graph/analysis_graph.py`、`routing.py`、`nodes.py`、legacy runner和demo；
- `src/lqcd_agent/agents/`、`src/lqcd_agent/llm/`、`src/lqcd_agent/memory/`、`src/lqcd_agent/report/`、`src/lqcd_agent/analysis/`、`src/lqcd_agent/analysis_programs/`和existing command runner behavior；
- B03执行前已有的`tests/test_*.py`；
- `pyproject.toml`、dependencies、configs、evaluation inputs/expected outputs、raw data、repository outputs、human decisions、accepted artifacts和secrets；
- control repository Git state、external network/provider/service和真实process containment claim。

## Requirements

本票继承B00的validation stages、final obligations和closed report。追加final runtime证据必须保留原requirement owner及独立case集合；对应production hook须有本次实际触发记录、passing nodeid和exact trace，不能以inventory或静态检查替代。

### 1. Canonical Subgraph and Backend Authority

- Parent只看见一个scheduled canonical `code_agent` Attempt和structured outcome；subgraph control stages不创建额外Work/Control Attempt或automatic route count。
- Inbound target capability不能启动Attempt。只有B02 external-result claim、aggregate settlement、Pause consumed、paused-to-running lifecycle与running checkpoint完成后的same-operation authorization可启动consume stage一次。
- Backend只实现port并返回untrusted immutable reference；不能写graph/state/ledger/registry/budget/Pause/route、分配identity或选择retry/stop。
- Fake与future real backend必须共享exact schema、port、ingress、trusted verification、registration和fresh Analysis entry；不允许`is_fake`绕过验证。

### 2. ExternalOperation and Pre-start Ordering

- Pre-start严格形成producer operation/ExternalOperation stub → task → unmaterialized manifest → aggregate reservation → immutable core → physical workspace → B02 Pause publication；每步create-new、idempotent、head/digest exact。
- B02提供同一coordinator中的resolution CAS、Pause publication/claim、consumer failure closure、lease/capability和typed preparation ports；B03负责真实producer分配、完整ExternalOperation row/schema、pre-start phase推进、Backend/stop evidence、Code consumption与Analysis preparation adapter。B02测试中手工构造的producer/reservation/domain proof仅证明control half，不能作为B03 canonical运行实现或验收证据。
- Pre-start aggregate及consume后的verification调用使用B01冻结policy/replay与B02 ownership primitives，按A05/A06验证可信BudgetDecision、hard dimensions和actual usage。B03 generic parent adapter提供可信admission输入以验证这些primitive；不得接受caller自报allow或绕过限额。B04再把这些能力接入完整产品route与统一stop，不重复建立账本或producer authority。
- Public paused checkpoint之前不得dispatch。Crash/receipt缺失/Backend unknown只lookup/fetch原operation，绝不redispatch。
- Duplicate dispatch同payload返回同receipt，conflicting payload拒绝；lookup/fetch/query不创建工作、刷新预算、续租或改execution head。
- Normal/cancel/interrupt共享exact External revision/epoch/empty-resolution CAS和唯一`external_final_evidence_committed`；normal只接受request-owned safe-stop candidate，unavailable先重分类为integrity interrupt。
- Winner后的late result/cancel/interrupt/old epoch写入失败；所有legal orderings恰有一个winner。

### 3. Workspace, Scope and Containment

- Task冻结exact identity/base/read-write-forbidden paths/tool/network/filesystem policy/verification specs/budget reference/authorization和producer operation。
- Paths只允许normalized repo-relative POSIX；absolute、empty、`..`、normalization collision、symlink/hardlink/submodule/mount escape、Git metadata、device/socket、secret/raw/accepted/control/output路径全部拒绝。
- Workspace lifecycle exact为`prepared -> leased -> running -> sealed -> verified -> released`；manifest先于bytes，seal在Backend停止且write lease撤销后冻结。
- Deterministic containment fixture必须实现kill-all、bounded drain、lease revocation、verify-empty和post-stop stability的typed proof；任何false/unknown都映射unavailable，不伪造safe stop。
- B03不声称真实OS descendant containment capability；该能力留给Phase C C00。

### 4. Ingress and Trusted Verification

- Delivery在图外strict验证Run/Case/Cycle/Attempt/Transition/task/operation/base/workspace/Pause/receipt/seal/member digests、scope、policy和authorization；malformed/duplicate-key/foreign/tampered content无产品Transition。
- Backend-reported pass不能替代trusted verifier。每个required spec恰有一个`passed | failed | blocked | timeout | not_run`结果；只有全部required passed可产生usable success。
- Non-empty unverified change不能成为success/partial success；status只允许A05七个canonical值，不定义`partial_success`。
- Claim后precomputed exact side-effect-free suffix可materialize；uncertain side effect为`recovery_required`；trusted tamper进入same-owner integrity closure，不重复claim/settlement/verifier或Attempt。
- Safe stop+appendable authority才可形成failed Run lifecycle；consumer stop或authority不完整只写同owner unavailable tombstone，不伪造artifact/lifecycle。

### 5. Bundle and Fresh Analysis Handoff

- 每个validated terminal Code Attempt至多注册一个content-addressed `code` bundle；member set、result origin、status/usable、dependencies、pointer status和provenance与A05 exact一致。
- Regular delivery bundle必须包含dispatch receipt、workspace manifest/seal、change/verification/tool audit和条件patch；host-timeout bundle只允许frozen recoverable safe timeout shape。
- Missing/tampered/reused/drifted/swapped/foreign/post-seal workspace或legacy evidence不能被canonical validator消费。
- Success bundle current后，B03使用B02 target-preparation adapter冻结`AnalysisExecutionSpec`、base/patch/effective tree/runtime/target identity；fresh Analysis使用new workspace/new subprocess，不读取control repo或复用coding workspace。
- Bundle-to-Transition与Transition-to-Analysis preparation的exact side-effect-free publication可same-operation恢复；execution uncertainty不得自动重跑、abandon、retarget或提交第二Transition。
- B03的generic parent adapter只证明A05 handoff primitive，不计B04产品route coverage。

### 6. Budget and Recovery Evidence

- 每个Code Attempt恰有一个aggregate backend reservation，绑定producer operation、task semantic context、backend/runtime、unmaterialized manifest和后续Pause；第二aggregate、Backend counter或refund拒绝。
- Lookup/fetch不改变budget；watchdog在maximum/timeout边界强制stop exact operation并产生complete/unavailable proof。
- B00归属B03的全部failpoint必须接真实hook，覆盖pre-start、dispatch、receipt、completion、seal/result、delivery、claim、settlement、verification、bundle和Analysis preparation边界。
- 全部owned独立case须在一个冻结输入、同一fresh Session中通过；使用C04 `run_pytest_batches`有界执行并复用现有observation/runtime验证器，核对完整selection、无重复/遗漏及同session/case/nodeid的production hook进程回执。Expected traces须预先审查固定；construction通过或global final的预期负结果均不能代替本票runtime验收。
- Restart必须用new Python process重开coordinator；normal/cancel/interrupt和stale worker至少用two-process确定性interleaving验证。
- Construction report使用B00的`PhaseBAcceptanceReport 0.1`：`construction.required/covered/passed=28`，`requirements.required=131`、`requirements.covered=84`、`requirements.remaining=47`、`requirements.passed/passed_ids=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。累计covered只表示映射，不能从前置ticket历史结果推断本次全局passed。

## Deliverables

- A05 closed schemas、canonical serializers和validators；
- `CodeAgentSubgraph`、Backend port和`FakeCodingBackend`；
- coordinator-owned ExternalOperation、watchdog和deterministic containment fixture；
- workspace/ingress/trusted verification/canonical bundle/fresh Analysis implementation；
- B03 28项matrix slice、restart/concurrency/fault/trace evidence；
- construction/final expected-failure reports；
- B03 completion record与必要文档同步。

## Acceptance Criteria

- Fake Code Agent完整经过B02 public Pause/Resume/operation authority，不存在test-only success shortcut；
- Pre-start、dispatch、lookup/fetch、normal/cancel/interrupt、settlement、consume、verify、bundle和fresh Analysis顺序及每个fault outcome与frozen contract一致；
- Scope/path/seal/identity/digest/authorization负向矩阵fail closed，current control repository、raw/accepted/secrets/network均不可达；
- Success/no-change/所有valid non-success及invalid ingress分类exact，Backend自报pass不能绕过trusted verifier；
- Multiple Code Attempts workspace/artifact隔离，legacy evidence不能被canonical path消费；
- B03 construction owned/covered/passed exact为28项，累计映射covered 84项，remaining exact 47项；construction通过、final expected-fail、`phase_b_complete=false`；
- 冻结规则生成的全部B03 owned runtime case具有本次passing evidence，B00–B02前置场景保持通过；所有case保留实际production hook、exact trace与outcome，不以静态绑定完整代替执行；
- B00–B02 focused、A03 registry regression、legacy coder regression、完整pytest、compileall、links、metadata、scope、stale docs和diff checks通过；
- 未修改product graph/default legacy CLI，未调用真实Backend/provider/network或修改control Git state。

## Verification

```bash
B03_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b03-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest --collect-only -q tests/phase_b
pytest -q tests/phase_b/test_fake_code_agent.py
pytest -q tests/phase_b/test_external_operation_recovery.py
pytest -q tests/phase_b/test_code_agent_trust_boundary.py
python scripts/validate_phase_b_acceptance.py \
  --mode construction \
  --ticket B03 \
  --evidence-dir "$B03_EVIDENCE_DIR/construction" \
  --report "$B03_EVIDENCE_DIR/construction-report.json"
! python scripts/validate_phase_b_acceptance.py \
  --mode final \
  --evidence-dir "$B03_EVIDENCE_DIR/final" \
  --report "$B03_EVIDENCE_DIR/final-negative-report.json"
pytest -q tests/test_artifact_registry.py tests/test_coder_task_packet.py tests/test_test_runner.py tests/test_codex_handoff_worker.py tests/test_run_graph_with_codex_handoff.py
pytest -q
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

还必须独立记录：

- 按`docs/VERIFICATION_GUIDE.md`的同session分批方式，从独立inventory生成B03 owned case/nodeid选择，运行并验证全部case，保存原始batch envelopes、merged evidence、exact case集合和输入摘要；不能直接复用B02的owner过滤条件或历史证据；
- 原始source-bound轨迹及审定的fingerprint/head派生变更，确认不同fresh根标准化一致、其他材料摘要仍被校验；
- two-process ExternalOperation resolution、stale epoch、duplicate/conflicting dispatch与restart lookup/fetch；
- path/symlink/base/seal/scope/authorization/legacy-ingress negative matrix；
- trusted verification status matrix和fresh Analysis workspace/subprocess proof；
- 接入完整Code Agent后，`code_agent`和`legacy_codex_handoff`的`RecoveryDecision.continue_existing_target`仍在claim前拒绝，Pause/target保持不变，不产生capability、Backend调用或Attempt started；
- B03 construction owned/covered/passed set、累计84项和47项ordered remaining；
- failpoint registry hook completeness与normalized traces；
- control worktree Git status前后、no-network/no-raw/no-accepted/dependency/scope/stale-doc审计。

所有workspace、coordinator、Run、checkpoint和evidence位于新的`/private/tmp/lqcd-agent-b03-*`。

Final negative report必须分别列出exact 47项`requirements.remaining`、`runtime_evidence`缺口和`exit_checks`缺口；缺失后续scenario/adapter是预期缺口，已有检查的解析、collection或证据错误不能被忽略。Final preflight未具备时不提前运行B05全套检查。

## Stop Conditions

既有合同及Allowed Files内的局部bug允许修复，但必须使用本票maintenance路径留痕；缺失前置功能、需要扩大范围或改变架构/schema/public contract/验收边界时停止，先创建并批准corrective ticket，不用maintenance授权新功能。

- B00–B02未完成或其contract/evidence/digest不满足入口；
- 需要改变A05 schema/status/member/port/workspace/containment/Analysis contract、A04 operation或A06 reservation semantics；
- 必须调用真实Codex/SDK/provider/network、操作current control repo或读取raw/accepted payload才能证明B03；
- Backend无法提供restart-safe lookup/exact cancel semantics，或Fake需要绕过production validator/verifier；
- 需要接入B04 product route、修改legacy format或把B04 IDs计入B03 totals；
- 需要新增dependency、扩大Allowed Files、触碰Do Not Touch或修改B04/B05 ticket正文；
- recovery/concurrency只能依赖sleep、概率kill、same-process object或skip/xfail；
- baseline/full regression无法在Allowed Files内以contract-preserving local fix解决。

触发任一条件时停止B03；真实Backend能力不足属于Phase C gate，不得降低Phase B合同。

## Required Documentation Updates

- 若执行中发生既有边界内的局部修复，新增本票`docs/tickets/corrections/B03_MAINTENANCE.md`并向corrections index追加链接，记录问题、根因、改动、验证及关联ticket；
- `docs/ARCHITECTURE.md`和`docs/AGENT_ROLES_AND_BOUNDARIES.md`：记录canonical subgraph/Host/Backend authority及尚未接入的product route；
- `docs/STATE_SCHEMA.md`和`docs/ARTIFACT_CONTRACTS.md`：记录A05 schemas、ExternalOperation projection、bundle和Analysis handoff；
- `docs/SECURITY_AND_DATA_POLICY.md`：区分已实现Fake containment与deferred real containment；
- `docs/EVALS_AND_OBSERVABILITY.md`和`docs/VERIFICATION_GUIDE.md`：记录B03 matrix totals、trust/restart/fault命令；
- Phase B Overview、Docs Index、Current State和Decision Log；
- `docs/tickets/completions/B03_COMPLETION.md`及completion index；
- 完成stale-documentation scan。

## Review Gate Before `ready`

- 确认本票maintenance路径和corrections index追加在Allowed Files内，已有历史不可改写；缺失前置功能或任何架构/schema/public contract/Allowed Files/验收边界变化必须停止并经corrective ticket批准；
- 确认B03 exact owned set为28项、累计84项、remaining 47项；
- 确认四项A05 product-route IDs及A06统一stop IDs留给B04；
- 确认B03自己实现producer/pre-start aggregate/verification accounting及typed adapters，B02 control-half fixtures不冒充领域实现；owned runtime必须实际通过，前置golden同步严格限于可证明派生变化；
- 确认Fake与future real backend共享同一port/trust path，B03不声称真实containment能力；
- 确认canonical/legacy、workspace/control repo、bundle/promotion和migration边界清楚；
- 确认Allowed Files、Do Not Touch和verification没有未决placeholder。

只有用户完成review并明确批准后，才能把B03 YAML提升为`ready`；起草本文件不授权执行。
