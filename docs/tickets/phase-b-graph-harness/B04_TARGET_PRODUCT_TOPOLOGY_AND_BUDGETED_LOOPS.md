---
ticket_id: B04
phase: phase-b-graph-harness
status: completed
type: implementation
depends_on: [B00, B01, B02, B03]
---

# 接入 Target Product Topology and Budgeted Loops

## Goal

把B03 canonical Fake Code Agent接入A01批准的顺序产品图，完成Coordinator四层fallback、Human Gate return、A03 transition-time invalidation、A06 admission/reservation/grant/stop、recoverable interrupt后的独立`advance_run`以及所有target capability activation，并让B04拥有的47项requirements通过construction-mode验收。

B04完成后，B00–B04的required refs映射与catalog 131项set-equal，`requirements.covered=131`、`requirements.remaining=0`；这不证明全部final证据通过。Construction保持`requirements.passed=null`、`requirements_zero_gap=false`、`phase_b_complete=false`；最终判定还须通过B00定义的runtime obligations和B05退出检查。

所有construction数量仅对应本票`validation_stage=construction`证据。全局`requirements.passed/passed_ids=null`，`requirements_zero_gap=false`；原owner下新增的final scenarios和B00独立runtime obligations必须在final重新验证。

## Why

B01–B03分别建立了control、durability与Fake Code Agent能力，但没有证明A01每条真实产品edge、四层loop和forbidden route在同一个compiled target graph中工作。A03 invalidation、A06 budget和Human Gate授权必须在Transition commit与target capability之间统一执行，不能由每个Agent或router自行决定。

B04是最后一张拥有catalog IDs的subsystem ticket。它必须用production selectors、B02 operations、B03 subgraph和现有A03 registry闭合全部remaining requirements，而不是用test-only graph或一个happy path代替产品route矩阵。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/tickets/README.md`
- `docs/tickets/corrections/README.md`
- `docs/PROJECT_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/AGENT_ROLES_AND_BOUNDARIES.md`
- `docs/STATE_SCHEMA.md`
- `docs/ARTIFACT_CONTRACTS.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/EVALS_AND_OBSERVABILITY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md`
- `docs/tickets/phase-a-control-contracts/A02_RUN_CYCLE_ATTEMPT_MODEL.md`
- `docs/tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md`
- `docs/tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md`
- `docs/tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md`
- `docs/tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md`
- `docs/tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md`
- `docs/tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json`
- `docs/tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json`
- B00–B03 ticket与completion records
- B00C01–B00C09、B02C01、B03C01/B03C02 corrective tickets及其独立completion records；[B00–B05审查记录](../corrections/B00_B05_READINESS_REVIEW.md)仅保留2026-09-22的审查事实，现行输入以[B03完成记录](../completions/B03_COMPLETION.md)和后续已批准纠偏为准
- [B00C05 case0.3](B00C05_EXTERNAL_RESERVATION_FAULT_CASE_SEMANTICS.md)、[B00C06 trace0.5/proof0.2](B00C06_A05_SOURCE_BOUND_DIGEST_TRACES.md)、[B00C07状态投影](B00C07_A05_STATE_PROJECTION_GOLDEN_HANDOFF.md)、[B00C08 canonical来源交接](B00C08_B02_CANONICAL_EVIDENCE_TRACE_HANDOFF.md)
- [B00C09活动时间交接](B00C09_ACTIVE_TIME_LEDGER_HANDOFF.md)及其[独立账本合同](../corrections/B00C09_ACTIVE_TIME_LEDGER_CONTRACT.md)、[B03C01重复Code失效来源](B03C01_REPEAT_CODE_ATTEMPT_INVALIDATION.md)、[B03C02 case0.4](B03C02_POST_CLAIM_UNSTARTED_CASE_SEMANTICS.md)
- `src/lqcd_agent/graph/state.py`
- `src/lqcd_agent/graph/routing.py`
- `src/lqcd_agent/graph/analysis_graph.py`
- `src/lqcd_agent/graph/nodes.py`
- `src/lqcd_agent/graph/approval_packet.py`
- `src/lqcd_agent/graph/run_graph.py`
- `src/lqcd_agent/agents/decision_coordinator.py`
- `src/lqcd_agent/artifacts/registry.py`
- B00–B03实际新增的runtime/harness files

## Frozen Inputs and Entry Conditions

- B00–B03、B00C01–B00C09、B02C01及B03C01/B03C02必须为`completed`；B03 report必须exact显示28 owned passed、累计84 covered和47 remaining，独立runtime证据必须可复核B03 645/645及B02 1410/1410。
- Protocol/catalog exact versions/digests不变；remaining ordered set必须exact等于本ticket 47项owned set。
- B02 public/internal interfaces与B03 subgraph必须已经通过restart/fault/concurrency evidence；B04不得在graph layer复制其operation/ExternalOperation authority。
- Existing A02/A03 implementation是identity/invalidation唯一primitive；target graph必须复用而非fork。
- 执行前记录full legacy suite及fresh B00–B03 construction reports，分别为15/15、11/11、30/30、28/28；global final入口负向基线的错误集合必须exact为本票47项`coverage_gap`、本票144项`runtime_evidence_gap`（`binding`）和15项`exit_evidence_gap`（`adapter`），没有额外错误。按独立catalog/case/exit规则核对具体IDs，不能只比较数量。
- 现行独立case语义为B03C02冻结的`0.4`：共2199项，B02/B03/B04分别为1410/645/144，324 boundaries和28个post-claim路径保持。依赖canonical A05成员的source-bound证据沿用B00C06/C07/C08批准的trace `0.5` / proof `0.2`；既有trace `0.1`–`0.4`、旧case版本及sealed历史输入保留各自语义，不隐式升级phase-only证据。从独立规则核对case集合、dispositions和seals，不能沿用修正前计数或忽略材料摘要。
- 复用B00C07/C08已实现的producer/version状态投影、完整canonical来源与独立success/usable Analysis前置，B00C09活动时间账本，以及B03C01失效前来源绑定。上述交接是已完成前置，不授权本票再次改变旧格式、normalizer、账本合同或case分类。

## Scope

- 建立并编译A01 canonical target graph，使用canonical Attempt kinds与B02 project-owned operation入口；
- 实现A01全部17条positive route、9类forbidden behavior及guard negative/escalation路径；
- 把B03 `CodeAgentSubgraph + FakeCodingBackend`接入Planner gap与Coordinator code-fix入口；
- 实现Coordinator re-review、analysis rerun、code fix、replan四层fallback与Cycle/Attempt semantics，以及A01 typed remediation packet和scoped context边界；
- 实现Human Gate null-target Pause、valid response回Coordinator、single-use authorization/grant与invalid-response repause/halt；
- 在每个ordinary Transition内复用A03 target-layer invalidation、artifact dependency/protection与cross-head checks；
- 复用B01基础和B02已实现的start/replay/fork bootstrap admission，实现后续产品route/resource/grant/stop admission、policy replay、resource reservation/settlement、fingerprint repetition、route ceilings、terminal reserve、BudgetGrant和统一stop/outcome matrix；
- 实现recoverable interrupt result提交后由新的`advance_run`进入Coordinator，以及terminal close/interrupt/cancel/END的唯一operation derivation；
- 增加B04 47项matrix scenarios、exact product trajectories、forbidden negatives、fault bindings和fresh evidence。

## Non-goals

- 不修改Phase A contracts、B00 validator或B01–B03 frozen ticket bodies；
- 不实现parallel graph、fan-out/fan-in、reducers或parallel budget semantics；
- 不接入真实Code backend、Codex SDK、live provider、RAG或raw data；
- 不删除legacy graph/CLI/handoff，不自动迁移existing Run或转换legacy artifacts；
- 不改变Agent科学权限、risk floor、accepted-result或Human approval policy；
- 不实现B05的退出检查适配器或full exit smoke，不把B04 construction称为Phase B completed；允许调用B00 final诊断当前证据缺口；
- 不commit/merge/push/PR/deploy或promotion verified code。

## Migration Boundary

- Canonical Phase B graph只接受schema `0.4` project-owned interfaces和new Run；legacy schema `0.2` graph保留为显式compatibility entrypoint。
- 不把physical `codex_handoff`重命名为`code_agent`；canonical graph只调用B03 subgraph，legacy result不能进入canonical validator/route/current artifact。
- Existing CLI默认行为是否切换不在B04隐式决定：B04提供stable canonical Python entrypoint；B05在exit smoke中验证明确的versioned CLI入口，同时保留legacy compatibility命令。
- Existing `outputs/`、old checkpoint、Human decision和accepted result不迁移、不覆盖；所有B04 runtime tests使用fresh `/private/tmp/lqcd-agent-b04-*`。
- A03 seven-slot model保持；budget/control/external/workspace evidence不注册成新的domain slot。

## Owned Requirement IDs

B04 slice固定为catalog中最后47项未分配requirements：

```text
A01-ROUTE-001
A01-ROUTE-002
A01-ROUTE-003
A01-ROUTE-004
A01-ROUTE-005
A01-ROUTE-006
A01-ROUTE-007
A01-ROUTE-008
A01-ROUTE-009
A01-ROUTE-010
A01-ROUTE-011
A01-ROUTE-012
A01-ROUTE-013
A01-ROUTE-014
A01-ROUTE-015
A01-ROUTE-016
A01-ROUTE-017
A01-FORBID-001
A01-FORBID-002
A01-FORBID-003
A01-FORBID-004
A01-FORBID-005
A01-FORBID-006
A01-FORBID-007
A01-FORBID-008
A01-FORBID-009
A03-NAMESPACE-001
A03-REGISTRY-001
A03-INVALIDATE-001
A03-PUBLISH-001
A03-PROTECT-001
A05-CODE-001
A05-CODE-009
A05-CODE-010
A05-CODE-023
A06-BUDGET-001
A06-BUDGET-002
A06-BUDGET-003
A06-BUDGET-005
A06-BUDGET-010
A06-BUDGET-011
A06-BUDGET-016
A06-BUDGET-017
A06-BUDGET-018
A06-BUDGET-019
A06-BUDGET-020
A06-BUDGET-021
```

- B04 owned refs、B04 covered refs和fresh passed refs必须set-equal为47项。
- B00–B04 slice union必须与catalog 131项required IDs set-equal、互斥且无duplicate；B05不拥有或重分配requirement ID。
- B04可以增加cross-contract scenarios引用多个B04 IDs；强化B01–B03 IDs时必须按owner拆分matrix scenarios并保留原`implementation_ticket_id`，不同owner scenarios可以复用同一pytest nodeid/trace且必须在B05 final前可collect/pass。

## Allowed Files

- `docs/tickets/corrections/B04_MAINTENANCE.md`：仅在发生本票范围内的contract-preserving局部修复时新增；同票后续条目只追加，不改写已记录事实；
- `docs/tickets/corrections/README.md`：仅追加本票maintenance链接，不改写已有索引项；
- `docs/tickets/phase-b-graph-harness/B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md`：进入`ready`后只允许更新YAML lifecycle metadata；
- `src/lqcd_agent/graph/state.py`；
- `src/lqcd_agent/graph/routing.py`；
- `src/lqcd_agent/graph/analysis_graph.py`；
- `src/lqcd_agent/graph/nodes.py`；
- `src/lqcd_agent/graph/approval_packet.py`；
- `src/lqcd_agent/graph/run_graph.py`：仅限提供显式canonical Phase B Python entrypoint，不切换或删除legacy CLI；
- `src/lqcd_agent/agents/decision_coordinator.py`：仅限A01 structured diagnosis/remediation output，不扩大Agent route authority；
- `src/lqcd_agent/artifacts/registry.py`：仅限B02 operation integration、A03 frozen invalidation/protection与B03 bundle handoff；
- B01/B02已有的`src/lqcd_agent/control/`文件：仅限admission/grant/settlement/stop与graph integration；
- B03已有的`src/lqcd_agent/code_agent/`文件：仅限parent-graph integration，不改变Backend/schema/trust contract；
- `src/lqcd_agent/memory/store.py`和`src/lqcd_agent/report/generate_report.py`：仅限typed terminal disposition与accepted protection integration；
- `tests/phase_b/`：仅限B04 slice、target graph/trajectory/budget/invalidation fixtures和failpoint bindings；
- `tests/phase_b/expected_traces/`及其关联fixture：允许为本票源码/topology变动同步真实runtime fingerprint及可证明的派生head/reference；须保存真实来源与逐项差异，在两个fresh根复核后审定固定。不得改前置outcome/owner/invariant，不得运行时按actual重写expected或放宽trace exclusion；其他行为变化按Stop Conditions处理；
- `tests/phase_b/acceptance_matrix.json`及registry bindings：允许为本票实现对应的runtime义务追加`validation_stage=final`场景，引用本票或已存在前置slice的原owner（包括B00 meta IDs）；不改ownership、不预填后续slice、不修改B00冻结schemas/obligations/必需check清单；
- `docs/tickets/phase-b-graph-harness/OVERVIEW.md`；
- `docs/tickets/completions/B04_COMPLETION.md`；
- `docs/tickets/completions/README.md`；
- `docs/README.md`；
- `README.md`：仅当canonical Python entrypoint的用户说明实际改变；
- `docs/PROJECT_SPEC.md`、`docs/ARCHITECTURE.md`、`docs/AGENT_ROLES_AND_BOUNDARIES.md`、`docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`、`docs/SECURITY_AND_DATA_POLICY.md`、`docs/EVALS_AND_OBSERVABILITY.md`、`docs/VERIFICATION_GUIDE.md`、`docs/REPO_CURRENT_STATE.md`和`docs/DECISION_LOG.md`。

## Do Not Touch

已有completion/correction记录及其历史内容保持不变；Allowed Files仅为本票maintenance新记录/追加条目与corrections index追加链接保留例外，不授权修改前置票据的记录。

- Phase A frozen files、completed/correction history、milestone和tag；
- B00–B03 frozen ticket bodies及B05 ticket正文；
- `src/lqcd_agent/coder/` legacy files、legacy result schema和compatibility tests；
- `src/lqcd_agent/llm/`、`src/lqcd_agent/demo/`、`src/lqcd_agent/tools/`、`src/lqcd_agent/analysis/`和`src/lqcd_agent/analysis_programs/`；
- B04执行前已有的`tests/test_*.py`；
- `pyproject.toml`、dependency versions、configs、evaluation inputs/expected outputs、raw data、repository outputs、accepted artifacts、human decision files和secrets；
- provider/network/external systems、real Backend和parallel topology。

## Requirements

本票继承B00的validation stages、final obligations和closed report。追加final runtime证据必须保留原requirement owner及独立case集合；对应production hook须有本次实际触发记录、passing nodeid和exact trace，不能以inventory或静态检查替代。

### 1. Compiled Target Graph and Route Authority

- Compiled graph topology exact为A01 17条target rows，只有顺序single-target Transition；任何未声明edge、multi-target branch、parallel reducer或source bypass拒绝。
- Work Agent只输出structured outcome/diagnosis/remediation candidate；pure route selector结合validated heads、risk、budget和policy生成selection，conditional reader只读committed route。
- A01的`START -> method_planner`由B02 `start_run|replay_run|fork_run`的trusted bootstrap拥有；其余ordinary fixed/conditional Transition及typed-null END Transition由`advance_run`拥有，END之后由`close_run`完成Run closure。Target scheduled allocation、A03 invalidation和Transition commit在任何target side effect/capability activation前完成，不把START重复提交为advance。
- Human external control进入validator由原`resume_run`拥有，不计入A01 17条产品rows；validator完成后的`human_gate -> decision_coordinator`才由新的`advance_run`拥有。
- 每条guard failure必须证明错误target未scheduled、artifact未clear、side effect未发生、accepted state未变化；只测router return value不够。
- Physical node/canonical Attempt kind严格区分，canonical route不调用legacy handoff。

### 2. Product Trajectories and Four-level Fallback

- Exact trajectories至少覆盖no-code forward、planned code+Fake+fresh Analysis、planner failure/needs-input、re-review、analysis rerun、code fix、replan、Human Gate、accept/reject/hold/pending和control failed/halted。
- Initial/replan创建new Cycle；re-review/rerun/code-fix保持Cycle并创建fresh Attempt。所有Transition/Attempt identities与A02/A03 heads exact。
- Reviewer/Analysis/Planner/Code合法non-success都先进入Coordinator；只有唯一low/medium diagnosis且budget可用才automatic fallback。
- High/critical、ambiguous、second exact fingerprint、route/resource exhaustion、clarification/approval/external action必须Human Gate或typed terminal stop，不能继续automatic loop。
- Work Agent diagnostic必须结构化表达status/问题类别、受影响层级、证据引用、retryability、candidate remediation、diagnosis confidence、failure fingerprint和是否需要补充输入/批准/外部动作；自由文本不能代替这些guard输入。
- Coordinator每次派发四层fallback都形成typed remediation packet，至少绑定目标、问题、证据、约束、成功条件、相关父Attempt、预算状态与nullable Human authorization reference。Packet复用现有identity、per-Attempt artifact namespace和输入证据引用，不新增domain slot或control authority；target只执行packet授权的工作，不能自行扩大scope或选择其他Transition。
- Coordinator只读取bounded global execution summary；Work Agent只读取scoped current context、typed packet、直接父Attempt和与当前fingerprint/目标相关的bounded history。完整event log、route trace和checkpoint state不能直接注入Agent prompt；跨Agent历史只有经Coordinator选为证据引用后才能进入target context。
- Memory/report是terminal sink，不能发起loop；normal domain pending/held/rejected仍可`run_status=completed`，control failure/halt保持`failed|halted`。

### 3. Human Gate, Authorization and Grant

- Human Gate只与Coordinator建立产品edge；external control Transition进入validator不能计作`human_gate -> human_gate`。
- Response必须identity/digest/actor/scope/Run/Pause exact、single-use，validation后只授权exact target/action；invalid response终结validator并根据machine budget decision repause或close。
- `BudgetGrant 0.1`只由validated `approve_budget_window` snapshot派生，绑定route/fingerprint occurrence/target/actor scope并在exact Transition一次消费。
- Grant不能突破absolute ceilings、恢复terminal reserve、授权unrelated target或在duplicate response中重复消费。
- Human decision不能改写route policy、无限budget、response bytes、accepted result或长期rules/skills。

### 4. Invalidation, Artifact and Fresh Analysis Integration

- 每个target使用A03 frozen invalidation matrix；clear exact downstream current pointers/projections但保留canonical history、Human snapshots和accepted protection。
- Finished Attempt registration、dependency、current pointer、projection owner、state convenience path与execution/artifact/checkpoint heads双向exact。
- Code success只有在B03 usable bundle current后，才能由new `advance_run`分配Analysis target、commit Transition、完成Analysis preparation并激活capability。
- Schema-valid、Attempt-attributable且经B03 Host验证的canonical code non-success（包括合法`failed`/`result_invalid` bundle）完成原consume、release和checkpoint后，由new `advance_run`进入Coordinator；claim前invalid ingress不产生产品Transition。
- Claim后snapshot/identity/path/digest/policy完整性失败进入原resume的ConsumptionFailure tail；只有consumer safe-stop且Run authority可信才发布failed，否则same-owner unavailable/recovery_required。此路径保留原external final，不伪造Code failed bundle、不给Coordinator发Transition、不创建第二close/interrupt；仅有预授权且可证明的无副作用publication suffix可由原operation继续。
- 选中current canonical `success + usable` Code Bundle的Analysis（包括后续rerun）必须使用B03 `AnalysisExecutionSpec`、fresh workspace和subprocess；不能复用coding workspace或current control repo。
- 无current Code Bundle的no-code forward或rerun沿用B02 `TargetPreparationSnapshot.preparation_kind=not_applicable`及明确reason，并在same `advance_run` committed result后激活Analysis capability；不伪造Code Bundle或空Code spec来满足fresh preparation。存在Code Bundle却非success/usable时不能退回no-code分支，必须按A01 guards拒绝该Analysis target。

### 5. Budget Admission, Reservation and Stop

- Admission顺序固定为integrity → risk/security/data/accepted protection → policy/counters/reservations/grants → exact action；budget充足不能降低安全或科学risk gate。
- Initial forward execution不计automatic route；automatic route在limit以下allow，在limit处Human Gate/stop；Work/Control/Transition absolute ceilings与5 Control/6 Transition terminal reserve保持。
- LLM/tool/verification/resource operation在side effect前reservation，exactly once settlement；unsettled crash按maximum charge且不退款、不redispatch。
- Backend aggregate、Pause binding、post-claim settlement和observed overage复用B03/B02 identities；duplicate operation/settlement/refund或Backend-owned counter拒绝。
- First retryable fingerprint可继续，second exact升级；policy/security/data/non-retryable scientific issue立即gate。
- Budget stop不能绕过risk、Human Gate、A03 invalidation或accepted protection；terminal exhaustion不得产生new provider/tool/accepted-memory side effect。
- Interrupt winner的recoverable/halted/failed/unavailable total function、External safe/unavailable proof、Pause N/A/aborted/interrupted/quarantined、settlement/release和Run closure必须exact；recoverable result后只由新`advance_run`进入Coordinator。
- Trigger-first stop routing覆盖所有required external contexts，每个class/context pair派生唯一cancel/interrupt/close，interrupt winner后不得创建第二terminal operation。

### 6. Capability and Ownership Fencing

- Initial/Replay/Fork target只消费same producer committed result激活的capability；ordinary target只消费same `advance_run` result capability；resume target只消费same-operation running authorization。
- Capability在preparation/checkpoint/result前不可兑换；lease expiry后未started capability可由new epoch唯一接管，started或uncertain side effect不得自动重跑。
- Run terminal owner revision增长后，所有old/nonowner invocation capability即使lease未过期也不能写Run bytes。
- Recoverable interrupt在原winner内完成Code Attempt/artifact/checkpoint/release；product Transition只能由后续`advance_run`拥有。

### 7. Acceptance Evidence

- 47项owned requirements全部使用production target graph/selector/control/subgraph/registry/budget入口；test fixture只注入structured outcomes、clock、failpoint和Fake external result。
- Route/trajectory/recovery/interface scenario全部有exact normalized trace；forbidden scenarios保留no-side-effect invariants。
- 四层fallback分别验证typed packet与target context的来源/授权；错误target或父Attempt、篡改证据、越scope、无效Human authorization和完整audit内容直接进入prompt的负例必须在target副作用前拒绝。No-code `not_applicable`与verified-Code `analysis_fresh`各有production正向及错误分支反例。
- B00 registry中归属B04的budget/grant/transition/invalidation/bundle-to-route/Analysis/terminal boundaries全部绑定真实hook。
- 全部B04 owned独立case必须在冻结输入、同一fresh Session内使用C04有界分批机制实际通过，独立核验18个B04 boundaries对应的144/144 case；复用既有observation/runtime验证器校验完整无重复/遗漏集合及同session/case/nodeid的生产进程回执。Construction或expected-fail final均不能替代owned runtime evidence。
- Construction report使用B00的`PhaseBAcceptanceReport 0.1`：`construction.required/covered/passed=47`，`requirements.required=131`、`requirements.covered=131`、`requirements.remaining=0`、`requirements.passed/passed_ids=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。累计covered只表示映射，不能从前置ticket历史结果推断本次全局passed。

## Deliverables

- compiled canonical Phase B target graph与stable Python entrypoint；
- A01 routes、four-level fallback及其typed remediation/scoped context、Human Gate return和terminal topology；
- A03 invalidation/protection与B03 Code/fresh Analysis integration；
- A06 admission/reservation/settlement/fingerprint/grant/stop implementation；
- B04 47项matrix slice、exact trajectories、forbidden/fault evidence；
- construction report显示131 covered/0 remaining但Phase B未完成；
- B04 completion record和必要文档同步。

## Acceptance Criteria

- A01 17条positive rows、guard negatives、9类forbidden和required trajectory classes全部在同一compiled canonical graph通过；
- Four-level fallback的Cycle/Attempt、invalidation、budget和Human escalation exact；
- A01 structured diagnosis、typed remediation packet、scoped context及bounded history边界通过四层fallback正向和来源/授权/越scope负向验收；
- Fake Code Agent success/non-success/invalid ingress分别遵守B03 trust、A03 artifact和B02 operation边界；
- 无Code Bundle的Analysis走`not_applicable` preparation；verified-Code Analysis走B03 fresh spec/workspace/subprocess，错误或不可用Code不能绕过success/usable guard；
- Budget ceilings/reserve/resource accounting/fingerprint/grant/stop/terminal total function及all trigger routes通过；
- Target capability activation和Run terminal owner fencing无early start、duplicate start或post-terminal write；
- B04 construction owned/covered/passed exact为47项，B00–B04 slice union exact等于131项且remaining 0；construction仍`phase_b_complete=false`，没有B05 completion claim；
- 独立规则生成的全部B04 owned runtime case本次实际通过；B00–B03前置construction/runtime回归仍通过，不能把本票未执行case留给B05；
- Global final负向探针的错误集合exact为15项B05未交付的exit adapter缺口，coverage与runtime binding缺口均为0且没有额外错误；该探针未执行全局runtime，不能代替上述独立owned runtime证据；
- Legacy compatibility、full pytest、compileall、links、metadata、scope、stale docs和diff checks通过；
- 无parallel/live provider/real Backend/raw data/repository outputs/dependency/promotion变化。

## Verification

```bash
B04_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b04-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest --collect-only -q tests/phase_b
pytest -q tests/phase_b
python scripts/validate_phase_b_acceptance.py \
  --mode construction \
  --ticket B04 \
  --evidence-dir "$B04_EVIDENCE_DIR/construction" \
  --report "$B04_EVIDENCE_DIR/construction-report.json"
python - "$B04_EVIDENCE_DIR" <<'PY'
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path("tests/phase_b").resolve()))
from harness.contracts import EXIT_CHECKS
from harness.inputs import load_inputs
from harness.report import validate_report
from harness.session import worktree_digest
from harness.strict_json import read

evidence_root = Path(sys.argv[1])
report_path = evidence_root / "final-negative-report.json"
result = subprocess.run([
    sys.executable, "scripts/validate_phase_b_acceptance.py", "--mode", "final",
    "--evidence-dir", str(evidence_root / "final"), "--report", str(report_path),
], check=False)
assert result.returncode == 1, "Expected the final exit gate to reject incomplete B05 evidence"
report = read(report_path)
validate_report(report)
inputs = load_inputs()
assert report["digests"] == dict(inputs["digests"], worktree_inputs=worktree_digest(inputs["root"]))
requirements = report["requirements"]
assert (requirements["required"], requirements["covered"], requirements["remaining"]) == (131, 131, 0)
assert requirements["required_ids"] == requirements["covered_ids"] == inputs["required"]
assert requirements["remaining_ids"] == []
assert requirements["passed"] is None and requirements["passed_ids"] is None
actual_errors = {(row["category"], row["object_id"], row["field_path"]) for row in report["errors"]}
assert actual_errors == {("exit_evidence_gap", check_id, "adapter") for check_id in EXIT_CHECKS}
assert len(report["exit_checks"]) == 15 and all(row["status"] == "missing" for row in report["exit_checks"])
runtime = report["runtime_evidence"]
assert runtime["required_case_ids"] == list(inputs["specs"])
assert runtime["status"] == "missing" and runtime["passed_case_ids"] is None
assert runtime["missing_case_ids"] == runtime["required_case_ids"]
assert report["requirements_zero_gap"] is False and report["phase_b_complete"] is False
print("B04 final negative probe: exactly 15 exit adapter gaps; global runtime not executed")
PY
pytest -q tests/test_execution_identity.py tests/test_artifact_registry.py tests/test_state_schema.py tests/test_routing.py tests/test_graph_smoke.py tests/test_approval_packet.py tests/test_memory.py tests/test_report.py tests/test_run_graph_with_codex_handoff.py
pytest -q
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

B04完成时必须调用B00 final作负向探针并验证完整report及当前输入摘要：错误集合exact为15项`exit_evidence_gap`（`adapter`），`coverage_gap`和`runtime_evidence_gap`（`binding`）均不存在；任何额外错误或非预期退出码均使本票验收失败，不能仅用shell `!`接受任意非零退出。B05 exit adapters尚未接入时，B00 driver不会执行全局runtime，故report的`runtime_evidence.status=missing`、`passed_case_ids=null`且`missing_case_ids`仍为全部2199项；这表示本次全局final未执行，不撤销独立owned Session通过证据，也不能据此宣称全局passed。Construction和此负向探针均保持`requirements.passed/passed_ids=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。不得用禁止提前运行final来代替机器门槛。还必须审计：

- B04 construction exact 47 owned/covered/passed set、全部slice互斥union 131和0 remaining；
- 17 positive edge traces、每个guard negative、9 forbidden no-side-effect traces及完整trajectory classes；
- route/budget/fingerprint/grant/stop/terminal trigger matrix；
- A01 structured diagnosis、每层fallback的typed remediation packet与scoped/bounded context正负证据，以及no-code/verified-Code两类Analysis preparation分支；
- all B04 failpoint registry hook bindings；
- 按`docs/VERIFICATION_GUIDE.md`同session分批机制保存本票全部owned case的独立选择、production hook回执、batch/merged envelopes、fixed traces及逐case验证报告；原始来源与前置golden派生变化须离线审定；
- canonical/legacy入口隔离、no-migration/no-parallel/no-network/no-raw/no-promotion；
- Allowed Files/Do Not Touch、deletion/rename、dependency和stale-documentation scan。

所有runtime/evidence写入新的`/private/tmp/lqcd-agent-b04-*`。

## Stop Conditions

既有合同及Allowed Files内的局部bug允许修复，但必须使用本票maintenance路径留痕；缺失前置功能、需要扩大范围或改变架构/schema/public contract/验收边界时停止，先创建并批准corrective ticket，不用maintenance授权新功能。

- B00–B03未完成或其contract/evidence/digest不满足入口；
- remaining catalog set不与本ticket 47项exact相等；
- 需要改变A01 topology、A02 identity、A03 invalidation、A04 operations、A05 Code contract、A06 budget/stop或A07 acceptance；
- 需要test-only graph/selector/state patch、legacy handoff或Fake shortcut才能覆盖canonical route；
- 需要parallel graph、真实Backend/provider/network/raw data、dependency或control-repo code promotion；
- 需要自动迁移existing Run、删除legacy或静默切换未审查CLI public contract；
- 需要扩大Allowed Files、触碰Do Not Touch或修改B05 ticket正文；
- 任一required scenario只能通过skip/xfail/live-only/历史evidence或宽松trace；
- baseline/full regression无法在Allowed Files内以contract-preserving local fix解决。

触发任一条件时停止B04；不能把缺失项留给B05用happy path补齐。

## Required Documentation Updates

- 若执行中发生既有边界内的局部修复，新增本票`docs/tickets/corrections/B04_MAINTENANCE.md`并向corrections index追加链接，记录问题、根因、改动、验证及关联ticket；
- `docs/PROJECT_SPEC.md`、`docs/ARCHITECTURE.md`和`docs/AGENT_ROLES_AND_BOUNDARIES.md`：记录canonical target graph与仍保留的legacy boundary；
- `docs/STATE_SCHEMA.md`和`docs/ARTIFACT_CONTRACTS.md`：记录实际route/budget/invalidation/terminal projection；
- `docs/SECURITY_AND_DATA_POLICY.md`：把已实现Fake product path与deferred real backend/provider分开；
- `docs/EVALS_AND_OBSERVABILITY.md`和`docs/VERIFICATION_GUIDE.md`：记录131 covered/0 remaining construction结果与B05未完成；
- Phase B Overview、Docs Index、Current State和Decision Log；
- `README.md`仅同步实际新增的canonical Python入口，不提前声称Phase B exit；
- `docs/tickets/completions/B04_COMPLETION.md`及completion index；
- 完成stale-documentation scan。

## Review Gate Before `ready`

- 确认本票maintenance路径和corrections index追加在Allowed Files内，已有历史不可改写；缺失前置功能或任何架构/schema/public contract/Allowed Files/验收边界变化必须停止并经corrective ticket批准；
- 确认B04 exact owned set为47项，B00–B04 union为131且无duplicate；
- 确认已完成纠偏输入为case0.4的2199项（1410/645/144）、324 boundaries和28 post-claim路径，canonical source trace0.5/proof0.2与旧版本各自隔离；
- 确认B04 construction的0 remaining仅为映射齐全；完成负向final只允许15项exit adapter缺口，未执行全局runtime与本票144/144独立owned通过证据分别记录；
- 确认B02 bootstrap admission先于本票存在，本票只接后续产品route/resource/grant/stop admission；
- 确认START/ordinary/END/Human external各自owner明确，canonical领域non-success与消费完整性失败不会进入同一路由；全部owned runtime case有真实执行门槛；
- 确认canonical/legacy入口、CLI切换、migration、A03 slots与code promotion边界清楚；
- 确认全部route/forbidden/budget/stop证据使用production入口；
- 确认typed remediation/scoped context验收及no-code `not_applicable`与verified-Code `analysis_fresh`边界明确，不新增public schema或借packet扩大route authority；
- 确认Allowed Files、Do Not Touch和verification没有未决placeholder。

只有用户完成review并明确批准后，才能把B04 YAML提升为`ready`；起草本文件不授权执行。
