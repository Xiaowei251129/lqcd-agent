---
ticket_id: B00C28
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C26, B00C27, B04]
---

# B04 正式绑定的 meta 生命周期交接

## Goal

消除 C26 meta 把“canonical registry 尚未绑定 B04”当作永久条件的断言，使正式 B04 接线前后都能使用原 validators 验证真实来源、diagnostic 与完整 case result 的区别。只修正测试的临时生命周期假设，不引入新 trace/proof、生产行为或 validator 接受规则。

B04 是纠偏目标，不要求先 completed。本票初始为 review，创建不代表批准或实施；B04 保持 blocked。完成后独立复核 B04 正式接线入口，不代替其原 47 construction／144 owned 及剩余产品验收。

## Why

2026-10-16 B04 接续探针在两个 fresh native Session 复现：原 `budget.resource_settled.after.non_materializable_domain_gap` 的生产进程、hook、receipt、0.12 来源及实际 case result 均有效；追加合法的内存候选 binding 后，原 `validate_runtime` 返回该 case，而 `test_only_local_bindings_accept_complete_actual_result` 仍无条件要求对当前 canonical registry 抛出 `Invalid`，因此报 `DID NOT RAISE`。

无 case result 的诊断在合法绑定候选中仍返回空 owned；原 outcome/invariants/passing_node/source/hook/duplicate 六类拒绝在两个 fresh 根全部通过。问题是测试把暂时未绑定状态写成永久拒绝要求；不是新的生产故障，也没有证据表明来源或运行时 validator 应放宽。

- 本轮入口、原始脚本、候选 matrix/registry、双 fresh 反例：`/private/tmp/lqcd-agent-b04-execution-20261016-u47ty4p1/owned-lifecycle-counterexample.json`。
- 原 native 根：`/private/tmp/lqcd-agent-b00c26-native-owsndyed`；原 request/envelope/receipt/anchor 和两份 normalized 均保留。
- 实际仓库 matrix/registry 未改变；C26/C27 completed 保持。C26 已修订 C25 同类假设，但遗漏 C26 自己的后续激活断言。

## Read First

- `AGENTS.md`、`docs/README.md`、[ticket 工作流](../README.md)、[模板](../TEMPLATE.md)。
- `docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`、`docs/REPO_CURRENT_STATE.md`。
- [冻结 B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[B04 实际记录](../completions/B04_COMPLETION.md)。
- [C26](B00C26_B04_FAULT_SOURCE_AND_OWNED_ACTIVATION_HANDOFF.md) Requirements 6–10、[来源合同](../corrections/B00C26_B04_FAULT_SOURCE_CONTRACT.md)、[C26 完成记录](../completions/B00C26_COMPLETION.md)。
- [C27](B00C27_B04_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_FIXTURE_HANDOFF.md)、[来源补充合同](../corrections/B00C27_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_CONTRACT.md)、[C27 完成记录](../completions/B00C27_COMPLETION.md)。
- `tests/phase_b/test_b00c26_owned_activation.py`、`test_b00c26_trace_consumers.py`、`test_b00c25_process_session_binding.py`、`test_b00c27_recovery_fixture_contract.py`。
- `tests/phase_b/helpers/{b04_process_binding,b04_fault_sources}.py`、`tests/phase_b/test_b04_runtime_cases.py`。
- `tests/phase_b/harness/{failpoints,pytest_evidence,matrix,inventory,session,trace,fault_source_trace}.py`、实际 matrix/registry 与上列反例。

## Scope

- 只修订 C26 的一项临时未绑定假设，显式验证未绑定与合法绑定两种候选状态；其他原拒绝断言保持。
- 增加正式绑定候选与诊断隔离的 meta 检查，并扫描 C25–C27 现有 meta 是否还有同类永久未绑定假设。
- 使用原 validators 对完整 B04 候选接线做只读兼容性审计；候选仅在测试内存或 fresh 临时证据中，实际 B04 slice/bindings 仍由 B04 实施。
- 运行当前输入回归、独立前置验收与 B04 入口交接。

## Non-goals

- 不修改 production、预算、authority、Case 分类、owner、Session 或 process receipt 协议。
- 不新增 trace 0.13/proof 1.0，不修改任何 trace projector/resolver 或现有 validator。
- 不代为登记 B04 正式 owned，不实现 B04 剩余产品覆盖或 B05 adapters，不 commit/push。

## Allowed Files

- `tests/phase_b/test_b00c26_owned_activation.py`：仅 `test_only_local_bindings_accept_complete_actual_result` 的生命周期断言和必需 imports/fixture 引用；原其余六类负向测试正文保持。
- 新 `tests/phase_b/test_b00c28_owned_binding_lifecycle.py`：候选未绑定/合法绑定、诊断隔离、原拒绝与真实接线兼容检查；复用现有 native fixture，不复制来源生成器。
- 新 `tests/phase_b/fixtures/b00c28/`；如新增 scenario 确有 exact trace 需求，可新建 `tests/phase_b/expected_traces/b00c28/`，只保存实际双 fresh 审定结果，不修改旧 expected。
- `tests/phase_b/acceptance_matrix.json`：仅追加原 B00 owner、final、A07-META-006/A07-META-015 的本票 meta scenarios；已有 slices/scenarios 保持。
- 本票进入 ready 后仅 YAML lifecycle；新 `docs/tickets/completions/B00C28_COMPLETION.md` 与 `docs/tickets/corrections/B00C28_OWNED_BINDING_LIFECYCLE_ACCEPTANCE.md`。
- `docs/{README,REPO_CURRENT_STATE,VERIFICATION_GUIDE}.md`、Phase B Overview、completion/corrections 索引；`docs/DECISION_LOG.md` 仅在实际验收政策说明改变时追加事实。
- B04 completion/maintenance 仅追加实际关联；B04 YAML 仅本票完成且独立入口通过后的 lifecycle。

## Do Not Touch

- 全部 `src/`、Phase A、generated protocol/catalog、dependencies/configs、legacy tests、raw/outputs/accepted/Human/secrets。
- `tests/phase_b/harness/` 全部 validators、schemas、Session、launcher、trace/resolver、process-hook 协议及所有 helper/source producer。
- 实际 `failpoint_registry.json`、case obligations/seals、case IDs/分类/owners、B04 implementation slice 或正式绑定。
- 原 C25/C27 tests、C26 其余 tests、旧 fixtures/expected/sealed evidence、冻结票正文和旧 completion/correction 历史。

## Requirements

1. **明确临时状态。** 原 lifecycle 测试不再把当前实际 registry 的未绑定状态作为永久期望。始终构造两个独立候选：从副本移除该 case binding 后，真实 hook 必须由原 validator 拒绝；追加合法 hook/binding 后，没有 case result 的原诊断必须返回空 owned。不能用“若已绑定则跳过检查”替代这两项必测状态。
2. **完整结果与 observation 边界。** 代表 case 使用当前输入实际 native fixture 的两份 fresh 结果，先执行原 `validate_pytest`，再验证合法绑定下完整 passing node、case/outcome/invariants、唯一生产 hook 和 source-bound trace。探针 observation 保持真实 `B00C26-PROBE` ID及实际 invariants，以匹配的局部 scenario 通过原 `validate_observations`；正式 binding 形状另做候选 schema/inventory/runtime 逻辑检查，不得宣称探针已经通过正式 B04 scenario observation。必须验证探针直接匹配正式 scenario ID时仍拒绝 `observation:identity`，不得改写实际 observation、伪造正式 ID或修改 producer来获得通过。outer meta 的另一 Session 不能取得该 case，不得把内层结果重标为 B04 主 Session owned。
3. **真实身份与原拒绝。** 保留原六类负向测试及全部 C25 29 项、C26/C27 来源/拒绝检查。候选绑定前后额外覆盖缺失 case result、missing/foreign passing node、错误/重复 hook、outcome/invariants/source 篡改、stale/foreign Session；正例不可依赖伪造 event/result、expected-mode raw、历史来源冒充当前或新 validator 接受规则。
4. **144候选形状与诊断兼容。** 在隔离候选中按原 18 boundaries/144 case IDs 与 owners 构造正式 binding 形状，使用原 matrix/inventory 规则逐项验证，并检查原 runtime 对诊断空 result 返回空集合。原 C27 的288份封存 native envelopes均无 `case_results`，只证明来源、双fresh exact和诊断隔离；不据此声称144个完整结果已接受，不补造case_result。完整真实结果正例由Requirements 2的代表 case承担；正式144结果、正式observation及同一主Session owned验收仍由B04完成。每case候选fixture/expected须来自该case原始实际来源，不能用恒真布尔或一份成功trace覆盖144类。复核旧来源须保留原 Session/digests，明确只读未重执行、不计当前B04 owned；本票新测试在当前输入实际验证。
5. **生命周期扫描。** 审计所有 C25–C27 meta 中对 canonical registry、未绑定、owned 和 case binding 的假设。证明本票修订在未绑定/合法绑定候选两态均通过；若发现需要修改其他旧 test，不得静默扩范围，先在 review 阶段修订本票。不得为避免原断言，改变生产输入、另造 node identity、制造不同 expected 或重分类 case。
6. **实际仓库保持。** 所有 candidate 只在内存或新的 `/private/tmp/lqcd-agent-b00c28-*`。实际 registry bytes、原 84 mapped/47 remaining、2199 cases、324 boundaries、28 post-claim、144 B04 cases 和原 owner 集合保持；不增加 B04 slice、hook/binding 或正式 case result。meta 仍属 B00。
7. **当前输入验收。** 固定输入后 exact collection 包含原全部4674及本票新增，完整 suite 实跑并保留 legacy325；同一最终 Session 独立 B02 1410/B03 645，通过 fresh 原 CLI construction15/11/30/28，final 具体缺口仍 exact47 coverage/144 binding/15 exit adapter。不能以旧 C27 full 结果代替本票修改后的 full；原 source 没有变化时，完整144双fresh只读审计可以复用已封存原绑定，不能假称新跑或 retag。full 已新生成的来源不得遗漏其审计；原144来源复核限于Requirements 4的来源/诊断结论，不作为当前正式144通过证据。
8. **容量与批次。** 启动前保存文件快照、冻结正文、manifest、case/owner 集合和容量估算；沿用已测完整需求并计入本票增量，不降低余量。原300秒 outer/60秒 child和原集合保持；重来源用单项有界批次，Grant 串行，所有失败/容量停止与重新启动证据保留。空间不足不删除 native/sealed/反例、不过滤失败。
9. **独立交接。** 完成上述检查后才将本票 completed。再独立审查 B04 正式接线候选与前置 meta 的兼容性、冻结输入和原入口；只有已知 Stop 消除才按既有用户授权恢复 B04 ready。C26/C27 不重开、不重跑票据生命周期，也不因本票 completion 直接完成 B04。

## Deliverables

- 有界修订的 C26 lifecycle meta 与 C28 专用正负检查、原六类负向测试不变证明。
- 两种 candidate 状态、144候选形状/诊断逐项审计、代表case完整结果与真实probe observation、原反例及只读来源复核证据。
- 当前输入完整 suite、同 Session B02/B03 owned、fresh construction及具体 final 缺口报告。
- 独立 C28 completion/验收说明、scope/diff/冻结/链接审计和 B04 入口报告。

## Acceptance Criteria

- 原双 fresh 反例所示“合法完整结果仍必须抛 Invalid”的错误假设已消除；未绑定拒绝、合法绑定下诊断空 owned、合法实际结果接受三项始终独立通过。
- 原 C25 29、C26 七项及来源/消费者、C27 检查通过；未放宽原 validator、旧拒绝、source authority 或 Session fencing。
- C25–C27 生命周期兼容性、144候选形状/来源/诊断隔离与代表case完整结果分别有证据；probe ID直接用于正式observation仍拒绝。不把288份无case_result诊断说成正式144通过，不代计B04 owned。
- 当前 exact full、独立1410/645、15/11/30/28、final原47/144/15、131/84/47与原 owners 均核验。
- 生产、harness、helpers、旧 expected、实际 registry、case seals 和冻结正文 bytes 保持；scope/links/diff通过。

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests/phase_b pytest -q \
  tests/phase_b/test_b00c25_process_session_binding.py \
  tests/phase_b/test_b00c26_owned_activation.py \
  tests/phase_b/test_b00c28_owned_binding_lifecycle.py
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
git diff --check
```

上述专项不替代 Requirements 4–8 的当前输入 exact collection/full、原有界 Session/envelope、144候选审计、独立owned和CLI报告。所有新 evidence 在 fresh `/private/tmp/lqcd-agent-b00c28-*`，失败反例保持。

## Stop Conditions

- 需要修改生产、validator/Session/source/helper、trace版本、case/owner/registry 或旧 expected。
- 需要改变原六类拒绝测试、扩大其他旧 meta 文件权限，或用 skip/xfail/候选伪造/过滤失败通过。
- 完整144候选出现未获批准的来源、identity、scope 或判定语义缺口。
- 必要验收无法在原集合/超时/容量约束内执行，或 B04 入口有其他真实 Stop。

## Required Documentation Updates

- 独立 C28 completion、验收说明和 B04 入口；B04 completion/maintenance 仅追加实际事实。
- Docs Index、Current State、Verification Guide、Phase B Overview 与 completion/corrections 索引。
- 创建阶段仅保存 review 票据和关联入口、真实停止事实；不实施测试修订、不创建完成声明、不 commit/push。
