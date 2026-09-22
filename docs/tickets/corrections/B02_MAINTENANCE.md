# B02 Maintenance Record

## 2026-09-16 — Frozen bootstrap action validation

- Related ticket: [B02 Durable Control Operations](../phase-b-graph-harness/B02_DURABLE_CONTROL_OPERATIONS.md).
- Finding: B01's `validate_budget_payload` accepted only `route`, `resource`, and `repause`; it rejected A02C01's frozen `decision_recorded(allow, action=bootstrap_initial_route)` before the B02 trusted bootstrap could publish it.
- Root cause: the static proposal-kind allowlist omitted the already-approved bootstrap action. This is not a new decision enum, schema version, or admission authority.
- Fix: admit the existing `bootstrap_initial_route` action in the record validator. B02's trusted bootstrap admission computes capacity from the exact allowlisted policy, includes one Cycle, one Planner Work Attempt, one START Transition and the full terminal reserve, and binds its proposal to the operation, root input digest and policy digest. Public requests cannot supply an `allow` decision or counters.
- Verification: pending the resumed B02 verification run; results will be appended without replacing this entry.

### Verification result

- The trusted-bootstrap and storage tests pass **52/52**, including policy/digest replacement and injected-allow rejection; the emitted decision precedes the initial Cycle and Attempt records and includes the complete terminal reserve.
- Phase B tests: **220 passed**; full suite with live providers disabled: **545 passed**; A02/A03/state regressions: **139 passed**.
- Frozen Phase A validator and generated protocol byte check pass. The protocol/catalog bytes, ownership and completed ticket bodies are unchanged.
- This closes only the omitted bootstrap-action validation defect. B02 remains in progress and has no owned-slice acceptance pass.

## 2026-09-17 — Invocation expiry across validation and encoding

- Finding: a lease valid at entry could expire while checkpoint/Run validation or started-record encoding was running, yet the original code could still save started intent. Renewal and read-only effect authorization had corresponding elapsed-validation gaps.
- Reproduction: the regressions advance the trusted FakeClock inside validation and encoding, not by sleeping. The original start/renew/effect cases failed before the fix.
- Fix: reacquire fresh trusted time and recheck worker, invocation epoch, lease expiry, original budget deadline, activation, terminal ownership and invocation state at the final started-intent CAS. Acquire, renew and immediate effect boundaries also recheck after expensive validation. A rejected pre-start invocation writes no intent or Attempt started and remains eligible for legal pre-start takeover; an existing started intent is never reclaimable for execution.
- Verification: the focused invocation/bootstrap regression group passed after the repair, including expiry during encoding, elapsed acquisition, stale epoch and terminal-owner fencing. The complete B02 verification and fresh machine acceptance results will be appended after the remaining implementation, not inferred from these local tests.

## 2026-09-17 — Deterministic bootstrap integrity closure

- Finding: confirmed bootstrap prefix corruption could remain an in-progress operation and be reported as ordinary materialization-pending. The original corrupt-prefix regressions reproduced this behavior.
- Fix: explicit bootstrap source-integrity failures freeze canonical evidence and last trusted heads, reserve a deterministic dependent `close_run` in the same coordinator, and fail the bootstrap operation. An exact appendable prefix receives its unique failed lifecycle/checkpoint; unverifiable authority retains the unique terminal owner with `terminal_closure=unavailable` and no fabricated Run status. Stale writers are fenced, not converted into authoritative Run failures. Interrupting an owner atomically makes its pending closure unavailable.
- Verification: exact early prefixes, unknown extra files with appendable authority, damaged/missing ledgers, policy/index corruption and idempotent failure replay are covered. Fourteen before/after close-phase cases use real spawned processes and fresh-process restart; no history is truncated and no Run identity is replaced. The focused bootstrap/storage group passed. This fixes the local defect; it does not declare all B02 terminal variants or 30 owned requirements complete.

### Continuation verification checkpoint

- With source edits stopped, Phase B tests passed **453/453**, the full suite with live providers disabled passed **778/778**, and A02/A03/state regressions passed **139/139**. The invocation expiry and bootstrap closure regressions are included in these runs.
- Phase A validation, the generated protocol byte check and compileall passed. Fresh B00/B01 construction remains **15/15** and **11/11**; final has only **105 coverage**, **2286 runtime evidence** and **15 exit evidence** gaps, with global passed null and both completion flags false.
- These results verify the two local repairs alongside the partial B02 implementation. They do not close B02's 30 owned requirements. Remaining implementation and the legacy source-fingerprint clarification are tracked separately in the [B02 execution record](../completions/B02_COMPLETION.md).

## 2026-09-18 — Prepared external interrupt continuation

原interrupt入口仅接受absent/opened，prepared发布前缀被stable-checkpoint校验拒绝。现从唯一coordinator的冻结publication验证完整prepared前缀、原checkpoint和不变artifact/policy；支持Run仍running及已paused但尚未opened两种阶段。遇到文件已发布而SQLite事务因进程退出回滚的窗口，Pause ownership只能从已验证的原publication reservation恢复，并在同一interrupt CAS中取得，不能仅凭ledger分配authority。

安全停止提交prepared→aborted；停止不可证明提交prepared→quarantined和unavailable closure。原publisher被Pause/Run ownership阻止继续打开Pause，不接管其worker lease。未修改generated graph、Pause allowed edges或B03 backend职责。外部/Pause定向160 passed（148.85s），包含四个prepared publication边界的独立进程退出和过期publisher恢复拒绝。B02其余control分支与完整matrix尚未完成。

## 2026-09-18 — Normal consumption and same-owner failure continuation

修复external_result resume的一律拒绝、已释放external row仍阻塞advance、原resume遇consumer不确定性时仅置operation recovery_required而遗留Run无闭合owner，以及已有cancel/interrupt winner无法经public cancel观察的问题。使用原冻结phase/branch/snapshot合同和同一coordinator；新typed Code verification与consumer containment ports只分隔B03领域职责，未改A05 schema或default CLI。Invocation completion把external消费的最终checkpoint推迟到绑定释放后；fail-safe tail由原resume owner撤销execution epoch并唯一结算、处置Attempt/Pause，normal backend final始终只读。

分组验证和仍未完成事项见B02 completion的2026-09-18续执行条目；本轮未增加B02验收slice或改写frozen protocol/catalog。

## 2026-09-18 — Normal final system stop control

发现`close_run`只接受无Pause且external absent的running source，遗漏冻结`close_source_contract`的normal-safe-stop attached opened Pause路径。现增加trusted internal `terminal_operator_stop`输入，原子CAS Run/Pause owner，按resource settlement→Pause interrupted/target abandoned/external released→terminal eligibility→lifecycle/checkpoint收尾。原external resolution/revision/epoch/final bytes保持不变；每个suffix重新验证其不可变事实。其他未结算resource、非normal final、已claimed Pause、已启动target及竞争owner拒绝。历史detachment验证新增same-close-owner证据。

正向及14个fresh-process phase before/after边界共15 passed；原terminal/bootstrap/child回归90 passed。计数分组不相加为full-suite。当前只扩展B02 control half，没有实现B04自动policy/hard-limit决策，也没有Backend终止行为。

## 2026-09-18 — Analysis preparation control port

发现advance只接受TargetPreparationSnapshot/not_applicable，Recovery continue也整体拒绝已有Code的Analysis。现按冻结analysis_fresh union核验target/Transition、canonical spec/manifest bytes与digest、selected Code binding；Host domain port负责source与effective-tree验证，控制层在Transition闭合后、capability准备前create-new物化audit文件，并冻结typed verification receipt。Invocation acquire/start/effect/checkpoint重新验证准备文件与Host receipt；Recovery复用原advance的同一准备证明。B02不实现worktree、patch application或Analysis subprocess；测试明确为external/domain adapter。

定向准备/普通advance15 passed；后续准备完整分组20 passed且1项Recovery测试发现fixture错误（请求source不是failed Attempt），改为真实失败的Decision Attempt后，该Recovery单项1 passed。后续合并回归负责消除分组时间差。10个fresh-process准备边界均包含在20项通过记录中，重启不重新选择route。

## 2026-09-18 — Recoverable timeout deterministic consumption

此前recoverable_delivery解析后直接拒绝，导致safe timeout进入unavailable。现按冻结phase graph补齐同一interrupt操作的canonical failed delivery→Pause claim/consume→running checkpoint→受限invocation authorization→started intent/A02 started→Code注册/Attempt failed→binding release→final checkpoint/result。Domain bytes通过typed Host port提供；B02只验证冻结失败语义、身份、exact bytes与A03注册闭合，不实现B03 canonical bundle格式、Backend或verifier。

Started intent只允许当前interrupt worker及独立invocation lease创建；该scope不能进入普通consumer/effect接口。Restart只物化原frozen intent/result，不能重新求值delivery或启动目标。35项定向检查通过，包含32个phase before/after及started-intent/member-file两个额外fresh-process故障边界。Full-suite重新运行中，B02未完成。

## 2026-09-18 — Historical source read-only checkpoint and terminal competition

- 0.3 historical source now uses a trusted original-format reader port, with independent control checks for raw bytes, root inputs, historical fingerprint, source head/revision, Pause/Run ownership and selected evidence. The synthetic archived fixture is not a new historical creator or a relabelled 0.4 Run. A caller must configure the original-format reader; unsupported historical formats still reject.
- SQLite `mode=ro` can create WAL/SHM files. Source Fork verification now copies the complete checkpoint durability unit into a private temporary directory while holding the same coordinator writer transaction, verifies that snapshot, and rechecks source bytes. It does not use `immutable=1`, which can ignore uncheckpointed WAL content. Fourteen historical positive/negative/CAS/read-only checks passed, including live WAL and two-process source claim ordering.
- Close and normal resume racing after close reservation now leave one winner. A losing close terminalizes as failed without acquiring or changing the winner's Pause/Run/resource ownership. A failure after terminal ownership makes that original closure unavailable; stale workers still cannot terminalize a successor. Close/terminal focused checks: 26 passed.
- An owned advance whose preparation conflicts now derives a dependent close under the existing non-Pause runtime-failure contract. A verified, appendable control prefix closes failed; unavailable authority closes unavailable. The scheduled target is preserved: no started/abandoned/retargeted Attempt or second outbound Transition. Two new classification checks passed; earlier focused run had 29 passing checks and one local missing-tag error, then the missing tag was fixed and both classification checks rerun successfully.
- Review of the fixed recovery golden trace found exactly eight digest updates downstream of the real runtime fingerprint change; event order, phase, owner, epoch, status and all other fields were unchanged. Candidate/diff evidence was saved before accepting that intentional fixture update. No trace schema or normalization rule changed.

## 2026-09-18 — New B00 prerequisite: historical Fork trace sources

Runtime historical Fork succeeds, but its exact source-bound trajectory cannot be represented by B00 trace 0.2. `trace_proof.REFERENCE_KINDS` assigns every nested `execution_head` to `execution_0_4`; `_sources` then uses production 0.4 replay. Child lineage necessarily references the original 0.3 source head and checkpoint. The three deterministic diagnostic encodings produce:

| Attempted historical representation | Actual rejection |
| --- | --- |
| `execution_0_4` | `invalid_evidence:trace_proof:source_validation` |
| `canonical_json` | `invalid_evidence:source:reference_kind` |
| omitted source objects | `invalid_evidence:source:missing_reference` |

Reproduction: `pytest -q tests/phase_b/test_historical_source_control.py -k missing_trace`. These three tests assert the known rejection; they are diagnostics, have no acceptance observation and add no passing coverage. Combined with the two preparation classification checks: **5 passed**. Raw proof/error captures are under `/private/tmp/lqcd-agent-b02-final-review-qxn1sask/historical-trace-gap-*.json`.

Deleting heads, interpreting 0.3 bytes as 0.4, or allowing arbitrary JSON would weaken the frozen acceptance contract. B02 and B02C01 do not authorize that change. [B00C03](../phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md) is a concrete `review` corrective ticket proposing an explicit new test-owned trace version; it is not approved or implemented. B02 is `blocked` with its frozen body unchanged. This discovery does not negate completed B02C01 or claim the remaining B02 matrix/runtime obligations are implemented.

### 2026-09-21 — Historical trace prerequisite resolved

The user approved B00C03, frozen at `3c53a41`. Its explicit trace0.3 validates original historical0.3 sources and real Fork reservations before projecting references into the 0.4 child. Full regression: 1063 passed; fresh B00/B01: 15/15 and 11/11, mapped26/remaining105. Old trace rejection diagnostics remain valid. [B00C03 completion](../completions/B00C03_COMPLETION.md) closes this prerequisite. Restore original B02 to ready and continue its approved execution; no B02 slice or runtime completion is claimed, and the frozen B02 body remains unchanged.

## 2026-09-21 — Lost materialization plans and granted replan validation

- A bootstrap interrupted after root/checkpoint publication could remain indefinitely `in_progress/materialization_pending` after its frozen coordinator snapshot disappeared or failed integrity checks. The diagnostic is saved at `/private/tmp/lqcd-agent-b00c03-oyghj99y/b02-recovery-audit.json`. Snapshot reads now distinguish missing/corrupt plans without writing. The rightful, fenced mutating retry records the existing protocol's terminal outcome; missing authority requires recovery, confirmed corruption fails, and any already-owned closure becomes unavailable atomically. Bootstrap corruption uses its unique dependent close; no replacement Run, fabricated lifecycle, or regenerated domain plan is introduced. External uncertainty retains recovery-required classification. Query and committed-result replay remain read-only.
- Fresh-process regressions cover missing/checksum-invalid/malformed bootstrap plans and missing/corrupt publish/cancel/abandon plans, including unchanged Run bytes, preserved owners, immutable retries and stale-worker rejection. Snapshot/bootstrap/child regression group: **101 passed** in 41.95s (`/private/tmp/lqcd-agent-b02-plan-loss-regression.log`). This does not claim every external failure-tail branch has been audited.
- A valid single-use grant for replan was rejected because the execution validator required its Planner target to remain in the source Cycle. A06 already requires replan to create a new Cycle. The repair preserves the grant's source Cycle binding and additionally verifies the new Cycle's parent, replan trigger, creating Coordinator, allocation order, target node and exact inbound Transition. The trusted B04 grant issuance port remains outside B02. Positive and coherently rehashed negative regressions plus foundation/advance checks: **45 passed** in 2.22s (`/private/tmp/lqcd-agent-b02-grant-replan-regression.log`).
- These are contract-preserving B02 repairs. Frozen protocol/catalog bytes and ownership are unchanged; B02 remains in progress pending complete construction and runtime evidence.

## 2026-09-21 — Reservation fault-case executability audit

B00C03 is completed and its historical-source trace blocker is resolved. Resumed B02 fixed lost/corrupt materialization-plan terminalization and the granted replan new-Cycle validation defect; focused groups passed 101 and 45 checks respectively. These groups overlap and are not a full-suite total.

A separate B00 prerequisite defect is now reproduced at the initial reservation transaction. New before/after-SQL observation points expose actual boundaries in the same writer transaction. A fresh Python process exits at either point before COMMIT: SQLite rolls back all operation/phase/snapshot/owner/capability rows, and no Run directory exists. A new process retries the request successfully with one newly reserved operation at epoch 1. B00 nevertheless enumerates materializable-prefix and terminal domain-gap cases for these no-durable-authority contexts. Runtime cannot invent an original operation to satisfy them. The distinction between SQL publication and durable transaction commit must be represented explicitly.

Six production regressions passed in 2.84s: two hard-exit/restart cases and four immutable committed-replay controls for start and Pause. The replay controls do not prove every same-key outcome context is impossible; previously failed/recovery-required tombstones can themselves be replayed. No case waiver, binding or passing B02 observation was added. The 12 reservation boundaries currently expand to 96 independent cases; the new proof identifies a classification/context defect, not permission to delete all 96.

[Proposed B00C04](../phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md) is review-only. It proposes explicit rollback classification, commit-position semantics, a complete audited B02 case disposition table, fresh evidence and unchanged runtime authority/requirements/exit gates. It is not approved or implemented. B02 is **blocked**, with its frozen body unchanged. B02C01 and B00C03 remain completed.

Trace capture now includes actual reservation observations. The reviewed fixed traces add three reservation events to the B02 Recovery flow (40→43) and one to the historical Fork flow (29→30); other event identities/order/status/owners/epochs remain unchanged. Eight and ten head/digest fields respectively propagate the genuine changed runtime build fingerprint. Candidate, previous, raw and review artifacts are retained at `/private/tmp/lqcd-agent-b02-boundary-review-e9vgtj2h/`; expected traces are not generated during tests.

Coverage remains mapped26/remaining105, with B02's 30 construction requirements and 205 boundary/1488 runtime bindings unfinished. Full current-tree regression and fresh B00/B01/final-negative results are recorded below after verification. No implementation commit or push has been made.

Focused current-tree verification: **68 passed in 12.39s**, covering the reviewed trace fixtures, historical source evidence, reservation process boundaries, granted replan and lost Pause plans. Full current-tree verification follows; these are not construction/runtime acceptance passes.

### Current-tree final verification, 2026-09-21

- Full deterministic pytest: **1086 passed in 541.65s**; Phase B collection: **761 tests**, no collection errors. The six rollback/replay diagnostics have no acceptance observations and add no coverage.
- Fresh construction: B00 **15/15**, B01 **11/11**, no errors. Mapped **26**, remaining **105**, global passed null; both completion flags remain false.
- Fresh negative final: exactly **105 coverage + 2286 runtime evidence + 15 exit evidence** gaps. No additional parse, source-validation, collection or internal error. B02 construction and its **205 boundaries/1488 cases** remain unbound.
- Phase A validator and generated-byte check passed with the original protocol/catalog SHA. Compileall and diff checks passed. Scope audit checks all **310** Git-visible files and **24** resumed-B02 changes; all are in scope, including the review-only corrective proposal. **344** local Markdown links resolve. B02/B02C01/B00C03 bodies remain byte-equal to their frozen commits; independent inventory, obligation seals, matrix and completed prerequisite records are unchanged from B02 resumption.
- Evidence directory: `/private/tmp/lqcd-agent-b02-boundary-review-e9vgtj2h/`. `full-pytest.log`, `focused.log`, `inventory-counterexamples.json`, `reservation-regression.log`, reviewed trace deltas and `scope-freeze-links.json` record the findings. The `b00-final-report.json`, `b01-final-report.json` and `final-final-report.json` reports bind the finalized review documentation.

B02 remains **blocked** on the review-only B00C04 case-semantics correction, not completed. Existing implementation is uncommitted; no push occurred. Approval of B00C04 would authorize that defined correction and subsequent continuation of the already-approved original B02, not B03/B04 or a claim of finished B02 acceptance.

## 2026-09-21 — Integrated failure closure and lease audit

B00C04已completed，用户已批准统一修复并要求实现。原B02通过ready恢复后进入in_progress，正文仍与83681a7一致。此次contract-preserving修复范围：实际失败边界epoch/revision隔离；Pause日志完整性失败持久化及既有terminal owner unavailable；external claimed resume快照失败必须进入原failure尾部；Human后续终态向父操作传递；测试proposal/实际来源稳定化及完整B02验收接线。公共接口、状态及generated phase graph保持不变。

复现基线：publish/cancel/abandon破损JSONL反复异常、既有owner悬空；旧worker的epoch1错误可读新epoch2代为终结；claimed external损坏快照被直接quarantine绕过原failure owner；Human repause子操作failed而父resume停留external_consumption_released。修复及新回归进行中，不能以C04的1118绿测宣称上述缺陷已消失。

## 2026-09-21 Integrated verification follow-up

C04 source-CAS补验发现16项B02旧测试要求已撤销的Pause publisher重复抛错，与已批准的持久化failure收尾不一致。当前全量1117 passed/16 failed，未计为通过。按B02原Allowed Files恢复ready并冻结同一正文后继续in_progress，修复运行与更新旧断言；C04仍in_progress，仅负责case/source/process验收范围，集成回归通过前两票都不宣告完成。当前用户批准已包含全部运行缺陷和验收接线，不另行扩大范围。

独立进程接线另复现close在terminal ownership提交前重试损坏来源会遗漏已存在的reservation；将优先查找同Run/trigger的原close，再由原owner续执行或持久化失败，禁止第二reservation。

Resume拒绝prepared-only来源的负向回归另发现SQLite mode=ro会创建source WAL/SHM。准入已改用现有完整main/WAL/SHM只读副本校验，持有同一coordinator writer lock，不引入新authority或忽略WAL；拒绝前后所有Run文件和coordinator rows均需不变。取消观察者及超时分支接线错误均已修正。对另一操作随后成功终结Run的竞争场景，单独验证原operation/result/error不可变，并精确核对query的Run closure投影等于实际唯一owner；不把全局Run投影误当原operation可写结果。

2026-09-21 B02验收接线：C04已completed后，新增B02完整30项slice、5条完整来源轨迹及1410个独立runtime case绑定。初始reservation的两项C04进程反例作为并列必需final证据保留，没有移除旧正负检查；历史trace回归只隔离其B00/B01前置slice，完整matrix另行验证。现行映射56/131、remaining75；B02仍in_progress，正执行fresh验收，不能将接线或离线通过当作完成。全局final规则未改变，其他票据798个runtime binding及15项exit仍未交付。

## 2026-09-21 — Integrated repairs verified

本条关闭上述本轮诊断。C04已完成独立case、来源和进程证据前置修正；以下运行修复全部保持B02 public schema、phase graph与原Allowed Files边界：

| 根因 | 修复与验证 |
| --- | --- |
| 错误handler重新读取租约/phase，使旧错误借新epoch取得权限 | 在实际失败边界捕获operation/worker/epoch/revision；same-worker epoch2、同epoch新revision及重启负向回归拒绝旧错误。 |
| Pause日志损坏反复抛错，cancel/abandon留下pending owner | 原操作持久化failed/recovery结果；已有closure owner同步unavailable，Run bytes不伪造terminal。 |
| Claimed external snapshot丢失绕过原resume failure tail | 进入原ConsumptionFailure仲裁，按可证明的intent续执行；不可证明时撤销invocation、隔离binding并由同owner收尾，normal final保持。 |
| Human repause失败不传递，或committed child的plan丢失触发重新验证 | 父resume读取真实child终态和已提交Run/checkpoint证明，持久化结果；不重复validator、创建Pause或结算。 |
| Close在owner提交前重试时遗漏已有reservation | 先按Run/trigger/stopkind找到原reservation，再由原操作验证事实并续执行/失败；无第二operation。 |
| 拒绝prepared-only Resume时只读SQLite仍创建sidecar | 在同coordinator锁下复制完整main/WAL/SHM后验证；8类拒绝前后全部Run文件和coordinator rows不变。 |
| External轨迹缺artifact历史，测试proposal依赖临时目录 | 捕获真实artifact preimage，固定测试领域输入；production身份/head/完整binding摘要检查保留，source轨迹跨两fresh roots精确相等。 |

16项旧Pause publisher回归改为断言持久化失败结果，同时保留已有winner、无新增publication和重复调用不变检查；没有通过跳过故障消除失败。所有normal/cancel/interrupt六种顺序使用三个独立进程，另有真实claim/owner竞争回归。Query的当前Run投影可以反映另一合法owner的终态，但原operation/result/error严格不可变。

同一冻结输入下完整2599 passed，包含1410个B02独立case；fresh construction为15/15、11/11、30/30。具体session、fixed fixture审查、各类case数量及最终文档闭合审计见[B02完成记录](../completions/B02_COMPLETION.md)。本轮原工作保留，无commit/push。

## 2026-09-22 — Documentation reference closure

提交前独立重跑Phase A validator发现`docs/README.md`缺少`CONTROL_PROTOCOL_0_4.json`引用。根因是2026-09-21最终状态段替换时遗漏原有protocol/catalog链接；全量测试后发生的文档变更未被该次全量验证覆盖。历史完成记录不回写，本条纠正最终文档已全部通过的过早结论。

本次仅恢复文档索引的冻结合同与需求目录链接；不改validator、Phase A合同、runtime、测试或验收规则。重新运行Phase A validator、generated check及最终文档下的B00/B01/B02 construction/global final负向检查作为提交门槛；结果与范围审计保存到`/private/tmp/lqcd-agent-b00-b05-review-2b485tra/`。已有2599项全量与1410项runtime证据另经原验证器复核，源代码/测试/fixtures输入未变；本次新增114项定向回归通过。详见[审查记录](B00_B05_READINESS_REVIEW.md)。
