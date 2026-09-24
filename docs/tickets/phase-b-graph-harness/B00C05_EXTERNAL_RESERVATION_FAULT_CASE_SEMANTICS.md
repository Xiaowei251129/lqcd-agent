---
ticket_id: B00C05
phase: phase-b-graph-harness
status: ready
type: corrective-implementation
depends_on: [B00, B01, B02, B00C04]
---

# 明确首次 ExternalOperation Reservation 的故障验收语义

## Goal

让独立fault inventory明确区分首次ExternalOperation authority事务的未提交回滚与已有durable producer的恢复，补齐B03开始实施时发现的验收分类缺口。保留A05 producer先于task/workspace/aggregate/Pause的顺序、同coordinator authority和所有已有安全约束；完成后继续冻结于`b78c15a`的B03。

用户于2026-09-24批准按审阅建议继续：补齐本票、冻结并实施修正，验证后接续B03。本票仅授权以下修正，不授权改写B03正文。

## Why

当前case语义`0.2`把`external.stub`和`external.external_operation_reserved`分别展开为before/after × `committed_result_replay | materializable_publication_prefix | non_materializable_domain_gap | integrity_conflict`，共16项；它没有声明各side相对首次COMMIT的位置，也没有为首次producer完整回滚提供对应case。

使用当前production `Coordinator.transaction()`、真实B02创建的Run/plan/scheduled Code target及contract-shaped external stub，四个独立子进程切点已证明：INSERT前、INSERT后但COMMIT前、production COMMIT-before退出均无durable external row；COMMIT-after退出保留exact stub。Run文件、parent advance、target capability及其他authority tables全部不变。见`tests/phase_b/test_b03_reservation_boundaries.py`及[B03执行记录](../completions/B03_COMPLETION.md)。

这是现有coordinator事务原语的反例，不是完整B03 producer实现或654项runtime acceptance。它证明首次提交前结果缺少明确验收表达；不证明16项既有case在所有durable上下文都不可达。不能把新request重新准入称为原producer的恢复，也不能把hook移到已提交stub之后来掩盖首次事务窗口。

B00C04明确保持B03/B04 case集合不变，B03又禁止修改冻结inventory/obligations。因此必须独立审批本修正，不能在B03 maintenance中自行变更验收范围。

## Audited Case Contexts and Disposition Rule

以下是本票明确批准的验收上下文划分，不是从SQLite原子性推导出所有旧恢复场景不可达。表中每行的四个旧case分别对应四列；逐项机读disposition必须展开完整16项，保存旧case ID、new case ID、authority context、实际cut、合同定位与反例nodeid。

| 初始事务切点 | committed_result_replay | materializable_publication_prefix | non_materializable_domain_gap | integrity_conflict |
| --- | --- | --- | --- | --- |
| external.stub.before：首次INSERT前，无旧producer | replaced → 同side rollback | replaced → 同side rollback | replaced → 同side rollback | replaced → 同side rollback |
| external.stub.after：首次INSERT后、COMMIT前，无旧producer | replaced → 同side rollback | replaced → 同side rollback | replaced → 同side rollback | replaced → 同side rollback |
| external.external_operation_reserved.before：首次COMMIT前，无旧producer | replaced → 同side rollback | replaced → 同side rollback | replaced → 同side rollback | replaced → 同side rollback |
| external.external_operation_reserved.after：首次COMMIT后，exact durable stub | retained | retained | retained | retained |

前三行只分类“合法新producer首次事务因进程退出而中断”的结果；request冲突、已有producer和被篡改authority不能混入该上下文。没有durable producer时没有可重放的原terminal结果、可续写的原operation或可归属的domain gap；必须保持parent Run/target并重新准入。原有的replay、continuation、gap与tamper保护由最后一行的四个独立durable上下文及未改动的后继boundary义务承接，不因删除重复的初始窗口分类而取消。

最后一行四类均先通过真实初始COMMIT-after切点退出并由新进程读取exact stub，再分别构造下列合同上下文；不是要求刚提交的空stub直接成为terminal result：

- `committed_result_replay`：B03完成原producer的合法后继路径并持久化terminal证据，再删除可丢弃的delivery snapshot并重放；原terminal bytes/owner保持，不重新dispatch或验证执行。
- `materializable_publication_prefix`：同producer的缺失publication suffix已有durable预授权及exact identities/digests，current epoch仅materialize合同允许的确定性前缀；不能用新的request临时内容补造授权。
- `non_materializable_domain_gap`：原producer存在，但缺失后继所需的durable预授权，或其domain effect结果不确定；按原A05/A07合同进入相应fail-closed处理，不能重新执行副作用或把新producer冒充恢复。
- `integrity_conflict`：在durable producer或其绑定evidence中形成可检测的identity/head/digest冲突；旧epoch或冲突调用必须失败且不能替换原producer/terminal owner。

本票只交付真实初始入口、rollback/exact-stub/重复与冲突的证据以及上述分类的meta约束；四类完整canonical continuation的runtime证据属于B03，不能由synthetic terminal row冒充。本票内若真实入口不支持已审定切点，保持blocked并报告；不得为了计数移动hook、删case或扩展恢复政策。

## B03 Version Handoff and Unblocking

本票完成后，显式以case `0.3`取代B03 `Frozen Inputs and Entry Conditions`中case `0.2`的版本条件及这两个boundary的旧展开规则；这是独立批准的窄修正，B03正文仍保持`b78c15a`冻结摘要。Trace `0.4`、protocol/catalog、B03的28项owned requirements及其他条件不变。

只有本票全部Acceptance Criteria通过、fresh证据与逐项disposition已记录，才把B03从blocked恢复ready并接续原授权执行。不能仅凭新probe或计数符合就解除阻塞。恢复后先验证B03 allowed resource-binding范围内的trusted verification reservation → side effect → settlement与invocation事务/head校验接线，再推进完整canonical路径；本票不修改这些实现或预先声明B03完成。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`；
- `docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`；
- A05 ExternalOperation初始stub、A06 reservation顺序、A07 fault-injection合同；
- `CONTROL_PROTOCOL_0_4.json`、`PHASE_B_REQUIREMENT_CATALOG.json`；
- B00、B00C04、B03冻结ticket及各自completion records；
- `tests/phase_b/harness/inventory.py`、`final_obligations.json`、`failpoint_registry.json`；
- `src/lqcd_agent/control/coordinator.py`及`operations.py:ExternalControl`；
- `tests/phase_b/test_b03_reservation_boundaries.py`。

## Scope

- 增加显式case语义版本`0.3`，保留`0.1/0.2`历史语义与封存摘要，不改变trace `0.1–0.4`。
- 明确首次事务hook位置：`external.stub`的before/after位于INSERT前后、都在同一个未提交事务中；`external.external_operation_reserved`的before/after位于该事务COMMIT前后。
- 为三个COMMIT前side使用已有`reservation_rolled_back`类别，新增external-specific invariants：原Run/parent/target authorization保持、无durable producer/initial external owner、无task/workspace/aggregate/Pause/dispatch副作用，重试必须重新验证准入。
- COMMIT后的durable-stub side保留原有四类义务及各自明确的frozen authority/evidence上下文；不能用初始回滚删除durable recovery、tamper或replay保护。
- 实现仅限初始producer reserve/lookup的Host内部入口与实际hook，使反例最终经production入口复现；复用既有`external_operations`表及committed Code target授权，不引入第二套authority或新的public control API。
- 对16个旧case逐项记录`retained | replaced`、实际事务位置、合同依据和反例；其他case及全部boundary IDs保持不变。
- 为新case语义增加meta正负验证；B03 runtime bindings继续由B03交付，不把本票的事务probe算作canonical Backend完成。

## Non-goals

- 不修改A04/A05/A06 runtime状态、phase graph、budget/lease/claim/dispatch或recovery政策。
- 不实现task/core/workspace/backend/verification/bundle/Analysis余下B03功能；不提前添加B03 construction slice。
- 不修改B02/B04 case集合、28个post-claim组合、131项requirements、ownership或15项exit gates。
- 不重写B03或其他已冻结ticket正文；不使用real backend/provider/network/raw/accepted数据。

## Allowed Files

- 本ticket：ready后仅YAML lifecycle metadata；
- `src/lqcd_agent/code_agent/__init__.py`、`external_operation.py`：仅Host初始producer reserve/lookup、committed Code target校验及真实事务hooks；
- `src/lqcd_agent/control/coordinator.py`：仅必要的已存在COMMIT观察点接线，不改变表/schema或事务语义；
- `tests/phase_b/test_b03_reservation_boundaries.py`及必要的同目录process helpers；
- `tests/phase_b/harness/inventory.py`、`seals.py`：仅版本化case分类与seal；B00C04的`expected_dispositions`保持显式0.2语义及原字节，不放宽trace/report/evidence验证；
- `tests/phase_b/final_obligations.json`、`failpoint_registry.json`：按审定规则重建独立集合，保留全部boundary IDs/owners及前置bindings；
- 新增`tests/phase_b/external_reservation_case_dispositions.json`及对应meta测试；
- `tests/phase_b/fixtures/`：仅新case版本的meta正负fixture，不改既有B02领域fixture或历史source；
- `tests/phase_b/test_acceptance_foundation.py`、`test_evidence_and_final.py`、`test_reservation_case_semantics.py`：仅case版本/数量与新负向检查，保留已有保护；
- `tests/phase_b/acceptance_matrix.json`：只在原B00 owner追加本修正meta证据；
- `tests/phase_b/expected_traces/`及关联fixture：只同步production fingerprint导致的可证明派生head/reference，两个fresh根审查固定，不改owner/route/outcome/invariant；
- `docs/tickets/completions/B00C05_COMPLETION.md`、completion index；
- `docs/tickets/completions/B03_COMPLETION.md`：仅追加解除阻塞证据；B03原票仅YAML生命周期；
- `docs/README.md`、`docs/REPO_CURRENT_STATE.md`、`docs/VERIFICATION_GUIDE.md`、`docs/EVALS_AND_OBSERVABILITY.md`、`docs/DECISION_LOG.md`及Phase B Overview。

## Do Not Touch

- Phase A frozen tickets、protocol/catalog/generated bytes、requirement ownership、schema与product graph；
- B00–B03及B04/B05冻结正文、旧completion/correction历史、milestones；
- B02/B04独立case集合、post-claim组合、旧trace语义、必需exit IDs和最终完成判定；
- legacy实现/tests、dependencies/configs/provider/data/repository outputs/accepted artifacts及secrets。

## Requirements

1. 在绑定runtime证据前从独立规则生成并封存case集合，拒绝混版/stale seal；不能按实现通过数量决定required集合。
2. 对`external.stub.before`、`external.stub.after`、`external.external_operation_reserved.before`，故障发生于首次authority COMMIT前，必须证明完整回滚；保留前置Run/plan/target及authorization，不要求删除它们。
3. 对`external.external_operation_reserved.after`，必须证明durable stub存在；后续同producer continuation仍受exact bytes、current epoch和terminal ownership约束。已有terminal结果不可因snapshot丢失被重新分类。
4. 按Audited Case Contexts中的独立规则生成逐项disposition：三个初始pre-COMMIT side各有一项rollback，durable side保留四类。由该规则推导两个boundary共7项，预计总数2199、B03为645；这些是校验结果，不是反向裁剪集合的目标。B02仍1410、B04仍144；324 boundaries与28个post-claim case不变。任何规则、disposition或真实入口反例不一致均停止，不允许调整义务来凑数。
5. 新生产入口必须验证已提交parent、exact scheduled canonical Code target、external-prestart-only scope、Run heads/closure及现有producer；Agent或caller不得自签producer身份。首个事务只提交A05 stub；task/manifest/reservation/core/Pause字段仍为null。
6. 使用确定性真实进程退出与新进程重开，分别证明pre-commit rollback、post-commit exact bytes、同target双client至多一个durable producer及冲突请求零mutation；禁止sleep竞态、skip/xfail或test-only success分支。
7. 无durable producer时的重试是新的准入，不是恢复已存在operation，不得伪造terminal ExternalOperation、workspace、Backend work或Run failure来满足旧case。
8. 故障probe与case0.3 meta验证不计B03 construction/runtime已完成；B03恢复后必须通过自己的全部审定owned cases。

## Deliverables

- case0.3独立inventory/obligations/seals和完整16项disposition；
- 初始producer真实事务入口与进程反例/对照；
- 保留旧版与前置runtime义务的正负meta验证；
- 本票completion record及B03解除阻塞记录。

## Acceptance Criteria

- 三个pre-COMMIT side返回可验证的无durable producer事实；post-COMMIT side保留exact producer与授权链。
- case计数/集合/disposition符合Requirements，所有原boundary及B02/B04/post-claim集合不变。
- B00/B01/B02 fresh construction保持15/11/30，mapped56/remaining75，global passed为null，Phase B未完成。
- 前置B02 runtime1410项及完整回归通过；final仍按当前未交付binding/exit报告预期缺口，无解析、collection或证据错误。
- B03正文hash等于`b78c15a`冻结正文，无canonical Backend完成声明。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b03_reservation_boundaries.py tests/phase_b/test_reservation_case_semantics.py
pytest -q tests/phase_b/test_acceptance_foundation.py tests/phase_b/test_evidence_and_final.py
python -m compileall -q src tests
git diff --check
```

另用独立fresh根运行B00/B01/B02 construction与exact final-negative检查；按现有同Session分批入口重跑B02-owned runtime及完整suite。保存所有原始evidence、frozen input digests、case集合和双fresh-root golden审定差异。

## Stop Conditions

- 实际production入口反例不支持上述三个pre-COMMIT side或durable side分类；不得在执行中自行扩大替换范围。
- 需要改变runtime schema/authority、A05 pre-start顺序、current public contract或新增producer意图authority。
- 需要修改其他boundary、B02/B04/post-claim case、requirement ownership或exit门槛。
- 需要绕过同Session、真实进程、strict trace或旧版本验证。

## Required Documentation Updates

- 本票completion及索引、B03执行记录、Current State、Docs Index、Phase B Overview；
- Verification/Evals文档记录新旧case版本和审定集合；Decision Log只在批准并实际实施后记录验收语义变化。
