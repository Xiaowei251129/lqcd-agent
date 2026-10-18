---
ticket_id: B00C22
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C10, B00C11, B00C12, B00C21, B04]
---

# 普通资源已结算、domain publication 未完成的来源交接

## Goal

以显式 `trace 0.10 / proof 0.7` 表达普通资源真实返回、真实结算之后，原 Invocation 的 domain registration/finished/index/checkpoint 尚未完成的合法前缀。保留原返回值、原 producer/capability/settlement authority、冻结 publication source 和实际发布阶段；不把已结算解释为 domain publication、停止成功或 Run closure。

B04 是纠偏目标，不要求先 completed。本票仅交接证据表达与被动采集；完成后须独立复核 B04 入口，再按原授权恢复 ready。创建 review 票不代表批准或实施；B04 保持 blocked，原 47 construction/144 owned 不由本票代填。

## Why

2026-10-12 B04 使用原 compiled graph、原普通资源端口和独立进程，复现 `budget.resource_settled.before` 后进程退出。原 Invocation 已冻结真实 settlement，effect 一次且真实 Agent return 已采集；原 `ArtifactEffectPort.publish_budget` 能单次补完 settlement，重复调用不写新字节、不执行 effect。此时尚无 completion_intent、domain member 或 registration，原 graph 保留 started/uncertain，不能重新 invoke，也不能伪造终态。

显式 0.9 仍经旧 ordinary rule 调用 `agent_result`，无条件要求唯一已注册 diagnostic，拒绝 `invalid_evidence:ordinary_trace:agent_registered_diagnostic`。这不能用最大结算 receipt 修复：Agent 已实际返回且结算为 actual。另一个原 `invocation.artifact_registration.after` 前缀有冻结 completion 及真实 artifact-history suffix，但 finished/index/checkpoint 尚未绑定 registration，旧采集闭包仍无已注册 diagnostic；原 completion publication 可继续，证明并非无效返回。

上述新前缀需要来源合同交接，超出 B04 的旧规则/派生摘要同步权限。执行根 `/private/tmp/lqcd-agent-b04-continuation-20261012-g565kgdc` 保存原进程回执、双 fresh 反例、实际 journals/Run、before/after raw 和审查事实。B04 两项已完成局部修复（null active_pause、finished ledger 后补完原 completion）另记 maintenance，不授权本票扩大生产恢复策略。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/tickets/corrections/README.md`、`docs/tickets/TEMPLATE.md`。
- `docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`、`docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`、`docs/REPO_CURRENT_STATE.md`。
- A03/A04/A06/A07 冻结合同、`CONTROL_PROTOCOL_0_4.json`、`PHASE_B_REQUIREMENT_CATALOG.json`。
- [冻结 B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[B04 maintenance](../corrections/B04_MAINTENANCE.md)、[B04 completion](../completions/B04_COMPLETION.md)。
- C10/C11/C12/C21 冻结票、独立来源合同和 completion；C13/C15/C16/C18/C20 已完成来源及完整前置验收。
- `tests/phase_b/harness/{trace,trace_proof,a05_trace,ordinary_trace,ordinary_maximum_trace,product_failure_trace,prior_code_evidence_trace}.py`。
- `tests/phase_b/helpers/{control_traces,ordinary_sources,ordinary_maximum,b04_product_sources,product_failure_sources,prior_code_evidence_sources}.py`。
- 只读 `src/lqcd_agent/control/{capabilities,budget,coordinator,integrity,operations}.py`、`src/lqcd_agent/graph/{nodes,analysis_graph}.py`。

## Scope

- 为新版本新增闭合的普通 publication-prefix 声明及 projector；复用既有 producer、capability、reservation、真实 return/exception、clock/usage、settlement、Human、Code 与 failure/grant 校验。
- 被动 collector 从实际原端口、原 capability journal、publication plan 和实际文件采集证据；不从 expected、fixture pass flag 或测试分类合成生产事实。
- 覆盖 settled return 后无 completion/no domain、frozen completion 未发布、部分 artifact-history/projection、finished 已发布而 index/checkpoint 未完成等阶段；区分真实已发布材料与尚在原 journal 中的冻结材料。
- 覆盖原 Host 拒绝/失败 completion 的实际 error，保留真实 Agent return；无 Agent return 时仍为 null，异常/maximum 仍走 C12 原 receipt，不挪用为成功返回。
- 新版本四条消费路径及专用 meta；仅必要的 B00 meta 接线和文档。

## Non-goals

- 不修改 production runtime、恢复策略、资源预算算法、A03 domain registration 或 authority。
- 不自动恢复 effect、从 collector 数据生成 runtime completion、创建 synthetic Plan/Analysis/diagnostic、退款或把 actual 改为 maximum。
- 不完成 B04 的剩余产品集成、17 routes/9 forbidden、18 boundaries/144 owned、47 construction 或 B05 exit adapters。
- 不重写旧版本解释、旧 sealed evidence、case 分类、IDs、owners、Phase A、冻结票正文或已完成记录。
- 不 commit/push/PR、引入依赖、使用网络/真实 Backend/raw data。

## Allowed Files

- `tests/phase_b/harness/trace.py`：仅显式新增 0.10 dispatch；0.1–0.9 分支/default 保持。
- 新 `tests/phase_b/harness/ordinary_publication_prefix_trace.py`：新版本专用闭合声明校验与投影；复用旧校验而非放宽旧函数。
- `tests/phase_b/helpers/control_traces.py`：仅新显式版本被动采集/接线；旧入口与输出保持。
- 新 `tests/phase_b/helpers/ordinary_publication_prefix_sources.py`、新 `tests/phase_b/test_b00c22_ordinary_publication_prefix.py`、新 `tests/phase_b/test_b00c22_trace_consumers.py`。
- `tests/phase_b/fixtures/b00c22/`、`tests/phase_b/expected_traces/b00c22/`。
- `tests/phase_b/acceptance_matrix.json`：仅追加 B00 owner、`validation_stage=final`、原 `A07-META-006/A07-META-015` 专用 meta；不增加 B04 owned bindings。
- `tests/phase_b/expected_traces/`：仅为当前已有源码 runtime fingerprint 及可证明的派生 head/reference 做批准的离线摘要同步；逐项 before/after raw、完整 preimage、双 fresh 审计。不得改变 outcome、owner、invariant、材料语义或任何 exclusion，不能运行时写 expected。
- 本票 YAML lifecycle、独立 `docs/tickets/completions/B00C22_COMPLETION.md`、`docs/tickets/corrections/B00C22_ORDINARY_PUBLICATION_PREFIX_SOURCE_CONTRACT.md`。
- 文档入口 `docs/{README,REPO_CURRENT_STATE,STATE_SCHEMA,ARTIFACT_CONTRACTS,VERIFICATION_GUIDE,DECISION_LOG}.md`、Phase B Overview、completion/corrections 索引；B04 YAML 仅在独立入口复核后 lifecycle，B04 completion/maintenance 仅追加本票关联事实。

## Do Not Touch

- 全部 `src/`、Phase A、generated protocol/catalog、budget policy、control/Code wire 与 hash contract。
- 旧 harness validator/projector/registry/classification/ownership/seal/check 清单；旧 trace 0.1–0.9 的解释、接受/拒绝/default。
- 既有 tests/test_*.py、legacy、configs、evaluation、依赖、输出、accepted artifacts、Human 原始记录、secret 或旧 sealed evidence。
- 既有纠偏/完成历史、所有 ready/completed/blocked ticket 正文；不得让 C22 自动完成 B04。

## Requirements

1. **来源闭合与原 authority。** 声明 exact 绑定真实 reservation、唯一 settlement、capability 与 invocation epoch、原 producer operation/epoch/revision、原 authorization/启动源及同 Session 输入。实际 settlement journal、public prefix 和相关 producer 阶段须一致；不允许 foreign/stale/重复/orphan/future owner。来源只作证据，不授予写入权。
2. **实际返回和阶段。** settlement.actual 非 null 的真实 returned outcome 必须保留 canonical 原 bytes、evidence digest 和原 Host clock/usage。合法无 domain 前缀不能要求虚构注册 diagnostic；结构化返回仍按原类型和 Host 保留字段规则校验。已实际 Host 拒绝的返回必须绑定原 frozen failure/error，不把拒绝解释为 domain 成功。没有返回保持 outcome=null，actual exception/maximum、unsettled return 与实际结算不可混淆。
3. **发布与冻结材料严格分开。** 若有原 completion_intent，验证其整个 canonical journal、原 effect/lease/producer fence、artifact-publication plan、member bytes/hash、原 namespace、history previous/content、finished/index/checkpoint preimages、实际所在 prefix。冻结 registration 只标为 frozen source，不能冒充公开 registered/current；实际 suffix 必须是该原计划的合法前缀，无 foreign bytes。没有 completion_intent 的真实 settled prefix只能证明结算，不得从 passive return 创建 completion、科学接受或 closure。
4. **完成后的旧约束保持。** 实际 domain registration/finished 后，继续要求唯一原 diagnostic 与主成员、Agent→Host 派生、evidence、current dependency 和 scope exact；不能把 prefix 分支用于绕过 finished domain 校验。正常已有 0.9 材料的新投影保持既有语义，pending/frozen/registered 状态差异及合法材料变更必须改变 normalized 结果。
5. **不改变运行结果。** 原 completion 存在且原 authority 有效时，仅用原 publish_completion/publish_budget补 exact suffix；重读不得再 effect。无 completion、原 stop/authority 不可证明或材料缺失/冲突时保留真实 started/uncertain/unsettled/recovery 状态，不制造 failed/halted/completed/Pause/Transition。maximum 记账不证明停止，typed unknown 不触发 maximum、不能变零。
6. **版本与消费。** 仅显式 0.10/0.7 可表达新前缀；原 0.9 对同样反例继续按原错误拒绝。collector、matrix、runtime validator、exit digest 四消费者校验同 Session 新来源；测试专用 synthetic consumer 不计 B04 owned。
7. **固定验收集合。** 131 required/84 mapped/47 remaining、2199 cases（B02 1410/B03 645/B04 144）、324 boundaries、28 post-claim、18 B04 boundaries、15 exit checks 和原 owner 集合保持。整票执行最终固定输入 full exact、legacy325、同 Session独立 B02/B03 owned，fresh construction15/11/30/28，final具体47/144/15；仅审定派生摘要，不过滤失败。

## Deliverables

- 新显式 projector、被动 collector、独立来源合同及四消费者专用 fixtures/expected/meta。
- 每个合法 prefix、原 suffix 恢复、拒绝分支的双 fresh actual raw/journal/生产进程回执、差异审计和逐项验收索引。
- 独立 completion、固定输入 manifest、frozen-body/scope/owner 集合核对及 B04 入口复核。

## Acceptance Criteria

- A1：两个 fresh 根通过原生产端口复现“实际 return → actual settlement → 无 completion/domain 的 running prefix”；0.10 接受，0.9 仍 `agent_registered_diagnostic` 拒绝。原 effect=1；原 publish_budget重复 readonly；generic reentry 不重跑、不制造 closure。
- A2：resource_settled before/after、冻结 completion、artifact-history/projection before/after、finished/index/checkpoint 分别有原进程故障证据；原合法 suffix 可只读重放/完成。无 completion/失效 authority/材料缺失或冲突保留原 fail-closed 分类。覆盖原 Agent non-success、实际 Host rejection、exception/maximum、unsettled 与 typed unknown，返回来源不能相互替换。
- A3：missing/duplicate/foreign producer、错误 capability/epoch/revision、future/orphan registration、篡改原 return/settlement/member/plan、伪造已发布阶段、stale Session、不同 Run 必须拒绝；相同实际科学材料的不同 fresh identity 投影一致，实际内容/错误/发布阶段变化改变 normalized。
- A4：四条消费者均以 actual original evidence 验证正向及缺失/篡改/stale 负向；meta不计 B04 runtime。
- A5：稳定候选的 exact full collection 全部实跑通过；同一当前 native Session 独立 B02 1410/B03 645 回归，fresh 原 CLI 15/11/30/28及具体final47/144/15通过。不得延长原 timeout、扩大 exclusion、改旧 outcome 或用历史 Session retag。
- A6：原 wire/hash/public runtime、全部旧版本/default、冻结 bodies、原 counts/case IDs/owners保持；源码禁止修改，无 commit/push。
- A7：本票完成后独立检查 B04入口；仅通过才按原用户授权恢复 B04 ready。随后由 B04 完成剩余普通/Code/Grant/terminal/recovery集成、所有 route/forbidden/context guards、18 boundaries/144 native cases、47 construction和完整验收；局部运行缺陷仍记 B04 maintenance，不能宣称本票保证未来零阻塞。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest --collect-only -q tests
pytest -q tests/phase_b/test_b00c22_ordinary_publication_prefix.py tests/phase_b/test_b00c22_trace_consumers.py
python -m compileall -q src tests scripts
```

另按 `docs/VERIFICATION_GUIDE.md` 原 C04 bounded batch/native Session 流程运行完整当前集合和同 Session owned；用原 `scripts/validate_phase_b_acceptance.py` 运行 construction B00/B01/B02/B03及final负向，核对具体 IDs、完整 report/digests。保存执行前快照和稳定输入 manifest；执行/交付输入分开，不 retag。核对模板、依赖、链接、frozen-body、Allowed Files、deletion/rename、before/after raw、preimages及diff。

## Stop Conditions

- 原输入/依赖/冻结正文或完整前置证据不满足入口；
- 需要改变 production runtime/恢复策略、旧版本、预算、wire、authority、case 分类/owners/验收集合；
- 需要 synthetic diagnostic/registration/final、collector充当runtime journal、重新 effect、宽松 digest/例外/过滤才能通过；
- 需要超出本票 Allowed Files，或旧 expected 改动超出批准的离线派生摘要同步；
- 出现其他无法由闭合来源表达的合法路径，或无法完成原固定输入完整验收。

发生上述条件必须停止并保存真实反例，先创建/批准新纠偏；不能用 maintenance 扩权或将新阻塞留给 B04/B05 不记录。

## Required Documentation Updates

- 独立 C22 来源合同与 completion；Phase B Overview、docs/README、current state、corrections/completions 索引。
- State/Artifact/Verification 文档写明 settled≠registered≠finished≠closure、explicit version 与 suffix authority；架构/政策不变，来源版本决策追加 Decision Log。
- B04 completion/maintenance仅追加交接与独立入口复核，保留所有历史；B05 draft、Phase B false、B04 owned0/144保持至原整票验收。
