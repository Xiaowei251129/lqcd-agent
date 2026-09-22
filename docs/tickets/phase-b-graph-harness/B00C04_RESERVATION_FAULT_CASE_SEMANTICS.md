---
ticket_id: B00C04
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B01, B00C01, B00C02, B00C03]
---

# 修正 B02 验收的 Reservation 分类、来源证明与进程证据

## Goal

让B00独立fault-case集合准确表达“首次reservation事务未提交、完整回滚、无持久化operation”的结果，同时补齐external Pause资源预留摘要的来源证明和真实进程故障证据接线，解除B02已确认的验收前置冲突。保留Run前置authority、same-operation continuation、terminal tombstone和committed result不可变规则。完成后继续原冻结B02；本票不交付B02的30项功能验收。

用户已明确批准并要求实施《B02 状态核查与一并修复计划》，选择扩充本票统一处理验收前置问题。按照该批准冻结本版本；用户要求不commit/push，ready正文只在当前worktree冻结，独立completion记录其SHA-256与执行前副本，不声称存在Git冻结commit。

## Why

`tests/phase_b/harness/inventory.py`目前把每个ControlOperation phase统一展开为before/after × 四类结果。十二种variant的`operation_reserved`共96个case，其中每个before侧都要求`materializable_publication_prefix`与`non_materializable_domain_gap`。

真实新进程在首次reservation SQL写入前或写入后但COMMIT前退出，SQLite完整回滚：operation、phase、snapshot、publication、Run/Pause/terminal owner和capability都不存在，Run目录未创建。新进程使用原request重试，合法创建一个新operation，从epoch 1开始。不存在可继续或置为terminal recovery-required的原operation；补造该状态会违反B02的reservation authority合同。

复现：`tests/phase_b/test_b02_reservation_boundaries.py`。独立进程退出码84；before/after各一项。另四项确认start与Pause的已提交结果在materialization snapshot缺失或损坏后仍exact replay、owner和Run bytes不变。这四项是安全对照，不表示same-key replay的所有其他上下文不可达：已是recovery-required的tombstone同样可以原样重放。

B02的新reservation观察点目前位于同一个writer transaction的SQL写入前后，不能把“SQL已写入”当成“transaction已durable”。本票要求明确这种区别，不能移动fault到另一位置却沿用原case名称。B02 Allowed Files禁止改变B00冻结obligations、独立case集合和seals，故不能作为普通maintenance直接改数或删case。

追加审查证明：即使补齐artifact历史原文并固定测试领域proposal，external Pause的`proof.dependency.reservation_digest`仍把物理Run路径经真实resource-reserved record的摘要带入语义trace。现行trace没有声明此结构性引用。仅在内存中验证该引用后，两次独立临时目录的34条external consumption轨迹exact相等。另有production hook只能由src直接调用，而standalone故障子进程没有pytest ACTIVE writer，必须建立同session的真实触发回执。以上均属于本票统一的“B02验收可执行性”目标。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/SECURITY_AND_DATA_POLICY.md`；
- A02C01 coordinator reservation/FULL durability、A04 idempotency/outcome partition、A07 fault injection与crash outcomes；
- B00、B02冻结ticket及B02 completion/maintenance末尾；
- `tests/phase_b/harness/inventory.py`、`seals.py`、`failpoints.py`、`pytest_evidence.py`、`session.py`；
- `tests/phase_b/failpoint_registry.json`、`final_obligations.json`；
- `src/lqcd_agent/control/coordinator.py`及新增reservation进程回归。

## Scope

- 独立case语义新增显式版本`0.2`，不改变runtime protocol或trace版本。
- 根据实际transaction commit位置，为initial reservation的before/after故障定义closed authority context及可达结果；新增`reservation_rolled_back`，明确无旧operation、无domain mutation以及原request重新准入的行为。
- 核对B02的205个boundary与1488个旧case：保留每个boundary、side、owner和所有可达的安全/故障要求；只修正有合同及真实反例证明不可能的组合。其余B03/B04 cases保持不变，包括28个post-claim组合。
- 保留完整旧→新case disposition表及逐项依据；旧case不能静默消失。Committed replay和已持久化operation的materialization/gap/integrity分区仍须有独立实际证据。
- 原B00 meta owner下追加版本、可达性、缺失组合拒绝及fresh hook/evidence验证。
- 新增显式trace `0.4`，继承0.3来源证明，且仅在Execution external Pause的`proof.dependency.reservation_digest`位置增加typed `resource_reserved`引用，校验Run、Attempt、producer与实际原文。旧0.1/0.2/0.3语义保持，不忽略任意材料摘要。
- 完善artifact原文采集与稳定测试proposal；领域adapter仍明确是external/domain输入，不宣称B03/B04实现。
- 同session的独立子进程hook回执、实际src调用位置、case/nodeid绑定、退出前durable记录及父进程校验；保留passing nodeid、exact trace、完整集合和输入摘要检查。有界分批只能精确合并同session、不重叠的完整selection。

## Non-goals

- 不减少131个requirements，不改变owner、30项B02 construction目标、15项exit gates或Phase B zero-gap条件。
- 不改变任何runtime operation/Run/Pause状态、phase graph、lease/ownership、原子提交或failure处置政策。
- 不为凑齐旧case而补造operation、提前创建Run、把committed操作改成recovery-required，或在不同fault位置自报原case通过。
- 不实施B03/B04，也不把本票的meta检查算作B02 runtime通过。

## Allowed Files

- 本票：ready后仅YAML lifecycle metadata；
- `tests/phase_b/harness/inventory.py`、`seals.py`、`failpoints.py`：仅版本、closed context、独立case语义及验证；
- `tests/phase_b/harness/session.py`、`pytest_evidence.py`、`exit_checks.py`、`matrix.py`：仅新obligation版本的同等严格接线，不削弱report/session/trace/nodeid检查；
- `tests/phase_b/harness/trace.py`、`trace_proof.py`：仅显式trace0.4及typed资源预留引用，不改变旧版语义；
- `tests/phase_b/failpoint_registry.json`、`final_obligations.json`：按审查后的独立语义重建，保留全部324 boundary IDs、owner与source locator；
- 新增`tests/phase_b/reservation_case_dispositions.json`、`test_reservation_case_semantics.py`及必要fixture/expected trace；
- 新增`tests/phase_b/test_external_source_traces.py`、`test_process_hook_evidence.py`及对应fixture/expected trace；
- `tests/phase_b/test_b02_reservation_boundaries.py`、`helpers/process_client.py`：仅真实进程、事务边界及证据捕获；
- `tests/phase_b/helpers/control_traces.py`、`helpers/trace_sources.py`、`helpers/domain_adapters.py`、`test_advance_control.py`：仅完整来源采集、稳定的测试领域proposal与代表性trace，不修改领域runtime；
- `tests/phase_b/test_acceptance_foundation.py`、`test_evidence_and_final.py`、`test_source_bound_traces.py`、`test_historical_source_traces.py`：更新独立case版本/数量期望，原负向保护不删除；
- `tests/phase_b/acceptance_matrix.json`：只在B00原owner增加construction/final meta证据，不新增slice；
- `src/lqcd_agent/control/coordinator.py`：仅澄清或补齐实际reservation/commit观察点和直接production观察回调，不改变SQL authority、durability或状态转换；
- 核心`README.md`、`VERIFICATION_GUIDE.md`、`EVALS_AND_OBSERVABILITY.md`、`REPO_CURRENT_STATE.md`、`DECISION_LOG.md`及Phase B Overview；
- 新增`docs/tickets/completions/B00C04_COMPLETION.md`及索引；B02 completion/maintenance仅追加，B02原票仅YAML生命周期。

## Do Not Touch

- Phase A所有冻结文件、protocol/catalog bytes、generated protocol、requirement ownership和product graph；
- Production除coordinator观察点以外的实现；runtime schema/状态/authority、默认CLI、dependency、provider、raw data、仓库outputs及外部服务；
- 已完成记录与冻结ticket正文、B03–B05正文；旧trace0.1/0.2/0.3语义和来源绑定规则；
- B03/B04独立case集合与exit gate清单。

## Requirements

1. Case集合在运行测试前独立生成并封存；不能根据本次实际结果、registry binding数量、skip/xfail或手工waiver决定是否required。旧版封存摘要作为历史保留，新版本必须显式验证，混版/stale seals拒绝。
2. 首次reservation的每个side必须明确fault是在COMMIT前还是后。COMMIT前进程退出的`reservation_rolled_back`必须证明无持久化operation/owner/capability/Run写入，重启重新验证request，且不复用未提交identity。COMMIT后的同operation continuation必须绑定实际保留下来的operation ID、phase revision及新的worker epoch。
3. Durable reservation仍存在且冻结计划完整时证明exact materialization；缺失预授权且无法重建时证明terminal recovery-required；真实完整性冲突按现有合同证明failed/unavailable或无mutation拒绝。Committed operation必须exact replay原结果，不能为了满足case分类而改变已提交结果。
4. 为B02全部旧case逐项产生`retained | replaced` disposition。替换必须包含原ID、新ID、authority context、合同定位及实际反例test；不得使用自由文本豁免或删除整个boundary/side。可达的原case必须保留。审查表和新case集合set-equal，差额和新总数由机器计算，不把减少数量当作成功指标。
5. 对新分类使用真实production入口、确定fault、独立Python进程、fresh SQLite和固定expected trace。回滚前未发布的head不伪造为Run evidence；真实已有Run/source heads仍需完整source-bound证明。Expected不能在测试时由actual重写。
6. Validator持续要求每个已提交验收的required case具有实际production hook、passing nodeid、exact trace与正确session；漏一项、错误side/commit位置、替代operation、伪造epoch、给无operation情况补ID或把committed结果重分类均拒绝。本票以代表性production回滚/重启与正负meta证据证明validator可执行；B02全部runtime case的binding与通过证据由后续B02完成，不构成本票与B02互相等待的完成门槛。
7. 本票完成时B00/B01 construction仍15/15、11/11，mapped26、remaining105、global passed null、phase_b_complete false；final仍须因后续runtime/exit缺口失败。新case总数以及B02义务数量必须明确记录，不能继续引用旧2286/1488作为当前数量。
8. Trace0.4必须验证资源预留原文的摘要、record type/event、同Run/target Attempt/producer绑定，以及complete execution ancestry；不存在、错类型、foreign identity、重算摘要后的伪造来源和错误引用位置均拒绝。旧版本不得悄悄获得新引用规则，材料内容变化仍须导致trace mismatch。
9. 子进程回执必须由实际生产调用栈产生，绑定fresh invocation token、全部输入digests、父pytest nodeid、指定case及预期生产hook。接收旧session、错case、错node、重复回执、测试侧伪造hook、未触发故障或子进程异常结局均拒绝。回执不能自行宣告case通过；结果与trace由父测试验证并交回原validator。
10. Bounded batches不得删减selection或降级任何检查；逐批validate原始evidence后验证合并selection、setup/call/teardown、observations、hook和case集合完整唯一，最终再次验证同一worktree未改变。

## Deliverables

- 版本化、独立封存的case语义与完整disposition表；
- 原子reservation rollback、durable resume及immutable replay的实际进程/负向meta证据；
- 完整artifact来源、显式trace0.4、跨fresh roots exact external trace及负向来源证明；
- 同session独立进程hook回执及有界完整证据执行；
- Fresh B00/B01报告与仅含真实剩余缺口的negative final报告；
- 独立completion与B02阻塞解除记录。

## Acceptance Criteria

- 本票复现的COMMIT前回滚进入明确的新case，不要求不存在的旧operation产生terminal状态。
- 324个boundary、所有side、owner、131 requirements和15 exit gates保留；B03/B04及post-claim cases字节/集合检查不变。
- B02每个case的保留/替换可审查、无未解释遗漏；不通过伪造production状态或弱化证据获得通过。
- 旧正负测试、fresh session/hook/trace验证、全量pytest、Phase A摘要、generated byte check、links/scope/diff全部通过。
- 两次独立Run根的external consumption实际trace0.4 exact一致；旧trace版本全部原有负向保护继续有效；新资源预留引用不能把content tamper、foreign producer或未触发的hook变成通过。
- 完成后只恢复原B02，不宣称B02或Phase B完成。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b02_reservation_boundaries.py tests/phase_b/test_reservation_case_semantics.py
pytest -q tests/phase_b/test_acceptance_foundation.py tests/phase_b/test_evidence_and_final.py tests/phase_b/test_source_bound_traces.py tests/phase_b/test_historical_source_traces.py
pytest -q
python -m compileall -q src tests/phase_b
git diff --check
```

另在新的`/private/tmp/lqcd-agent-*`目录运行B00/B01 construction和negative final；冻结worktree输入后运行，不以旧report替代本次结果。

## Stop Conditions

- 需要改变Phase A runtime合同、状态、ownership或原子事务行为；
- 需要改B03/B04 case集合、requirement owner或exit门槛；
- 无法给case替换提供精确authority context、合同依据和实际反例；
- 必须修改其他production代码、删除head、关闭session/digest验证或扩大Allowed Files。

## Required Documentation Updates

记录旧→新case差额、实际事务边界、新语义版本/seals、trace0.4来源引用、进程证据及已验证数量。保留历史2286/1488结果的时间背景，更新所有当前数量；B02恢复原票后仍需完成全部30项construction和新版独立runtime义务。B02运行代码的失败收尾与lease修复在原B02范围执行并追加maintenance，不在本票提前实施。
