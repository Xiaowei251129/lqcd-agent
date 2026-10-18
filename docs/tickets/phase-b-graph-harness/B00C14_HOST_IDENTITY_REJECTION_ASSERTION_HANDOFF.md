---
ticket_id: B00C14
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C10, B00C13, B04]
---

# B00C14：Host 保留身份提前拒绝的来源断言交接

## Goal

解除 C13 当前 full suite 的单项范围阻塞：把 C10 的 Host identity spoof 原端口负向测试交接到 B04 已实现的 production-before-publication 拒绝，保留来源 validator 对 foreign identity 的严格拒绝。C13、B04 是纠偏目标，不要求先 completed；创建 review 票不代表批准或执行。

## Why

2026-10-05，C13 固定输入 full Session 在 `test_b00c10_ordinary_trace.py::test_actual_agent_host_identity_override_is_rejected` 失败。该测试把 Agent content.run_id 改为 foreign-run，预期原图 completed 后 normalizer 拒绝 host_identity。B04 已保留的 `ProductNode` 会在写 domain member 前抛 `ControlIntegrityError: Agent content includes reserved Host fields`。当前资源实际调用一次并 settle；继续要求 completed 已不符合生产边界。

失败证据为 `/private/tmp/lqcd-agent-b00c13-execution-9305i1oz/full-current/session/full-0009-output.txt` 与同名 pytest/request JSON，同一固定输入完整选择 3792 项，3791 passed/1 failed；C13专项29项、B02 1410/1410、B03 645/645、legacy325项及fresh construction15/11/30/28均通过。C13 冻结 Allowed Files 未授权修改 C10 测试正文，故没有改断言、撤掉 Host guard 或排除该测试。C13 保持 blocked，B04 blocked。

2026-10-05 独立审查又确认两项收尾缺口：现有 `member_identity` 反例先因 `member_bytes` 拒绝，不能替代原明确的 `host_identity` 分支证明；根 README 和核心入口的当前摘要仍把已执行 C13 写为 review。用户本轮授权按建议修订并执行 C14；修订只补清这两项验收与文档范围，随后 ready 冻结，不改 production 或扩大产品目标。

## Read First

- [AGENTS.md](../../../AGENTS.md)、[docs 入口](../../README.md)、[工作流](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)、[验证指南](../../VERIFICATION_GUIDE.md)；
- [C10 冻结票](B00C10_ORDINARY_RESOURCE_TRACE_HANDOFF.md)和[来源合同](../corrections/B00C10_ORDINARY_RESOURCE_TRACE_CONTRACT.md)；
- [C13 冻结票](B00C13_HUMAN_CONTINUATION_SOURCE_AND_PREFIX_HANDOFF.md)、[执行记录](../completions/B00C13_COMPLETION.md)及[补充合同](../corrections/B00C13_HUMAN_CONTINUATION_SOURCE_CONTRACT.md)；
- [B04 冻结票](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[maintenance](../corrections/B04_MAINTENANCE.md)；
- `src/lqcd_agent/graph/nodes.py`、`tests/phase_b/test_b00c10_ordinary_trace.py`、`test_b04_host_boundary.py`、`helpers/ordinary_mixed.py`、`harness/ordinary_trace.py`。

## Scope

- 仅修正 C10 该负向测试的原端口触发/断言，明确提前拒绝仍满足 Host identity integrity；
- 核对同一失败中 effect、reservation/settlement 和 domain publication 的真实事实；
- 保留原测试 nodeid 和所有来源反例，不把新拒绝误当 completed、maximum、停止成功或 B04 owned 覆盖；
- 在稳定当前输入中完成专项和正式回归，再交接 C13 原全部验收。

## Non-goals

- 不修改 production、harness、helpers、trace/proof schema/version、预算、authority、风险或架构；
- 不改变 owner/case/observe IDs、原 matrix 选择、required refs 或 frozen expected；
- 不实施 B04 Planner dependency、ordinary 收尾、Code/fallback/Analysis/fingerprint/grant 或 47/144；
- 不 commit/push/PR/deploy，不访问 provider/Backend/network/raw/secrets。

## Allowed Files

- 本票 ready 后仅 YAML lifecycle；
- `tests/phase_b/test_b00c10_ordinary_trace.py`：仅 `test_actual_agent_host_identity_override_is_rejected` 及确需 imports/fixture 参数，保留函数名/nodeid；使用 fresh 原 Coordinator/compiled graph/Agent port 核验提前拒绝，并在该函数内独立核验原 0.6 member projector 的 host_identity 拒绝；
- 新 `docs/tickets/completions/B00C14_COMPLETION.md`、`docs/tickets/corrections/B00C14_HOST_IDENTITY_REJECTION_HANDOFF.md`，记录实际修正和验证；
- C13 仅 YAML lifecycle，待 C14 completed 后恢复 in_progress 以完成其原验收；C13 completion 只追加交接事实；
- `README.md`、`docs/README.md`、`docs/REPO_CURRENT_STATE.md`、`docs/tickets/phase-b-graph-harness/OVERVIEW.md`：仅局部更新受本次交接影响的当前摘要/活动 ticket，消除 C13 尚未执行的过时表述，区分正式验证输入与收尾文档输入；历史日期条目保留并只追加本次事实；
- `docs/tickets/completions/B04_COMPLETION.md`、`docs/tickets/completions/README.md`、`docs/tickets/corrections/README.md` 仅追加真实索引与状态，已有活动索引项可同步实际状态，不改 completion 历史。

## Do Not Touch

- production、harness、helpers、Phase A、frozen ticket bodies、旧合同/completion 历史、expected/raw/sealed evidence、依赖；
- B00 required schemas/catalog/cases/obligations、matrix/registry/owner/exit 清单；
- 其他测试行为、B04 lifecycle 与未完成产品工作、B05 正文、repository outputs/accepted/raw/secrets。

## Requirements

1. 原 Agent 真实返回包含 foreign run_id 的 content；production 原端口实际抛 reserved Host fields，不能合成异常或 patch runtime/selector/ledger/effect。
2. 实际 effect 恰好一次，真实 reservation/settlement 各一次且 actual 保持原 typed 值；没有 domain member/artifact 注册、accepted memory 或下一个 Work Attempt/Transition。没有返回完整 Run 结果，不宣称 completed/halted。
3. 原 ordinary source validator 的 host_identity/foreign owner/bytes/registration 严格拒绝保持。先以原端口真实正向 trace 完整 normalize 通过，再从其已验证成员/registration/Attempt 材料的内存副本构造 foreign identity 反例；在原 0.6 member projector 的独立校验入口中重算 member SHA/size 和 registration 声明，使 bytes/registration 校验通过后明确拒绝 `invalid_evidence:ordinary_trace:host_identity`。这份恶意内存材料仅证明校验器拒绝，不能写回真实 Run、伪装原生产证据或替代完整 trace/Session 验收。原成员字节、registration 和运行证据不变；不修改或 patch normalizer，不用 skip/xfail/过滤或降低断言通过。
4. 原 nodeid、C10 observe IDs 和 meta 接线保持。本票不建立 B04 owned/runtime 或 B05 exit adapter。
5. 在同一稳定当前输入 fresh Session 记录完整 suite 与 B02 1410/B03 645 独立 owned 回归；fresh construction 15/11/30/28、final 原 47/144/15 缺口和 inventories/owners exact 保持。C13 完成仍须逐项复核其原冻结验收，不由本票预填。

## Deliverables

- 最小测试断言交接、原端口证据、独立 completion/合同；
- 当前输入验证与 C13 继续验收的明确交接；B04 保持 blocked。

## Acceptance Criteria

- 原失败 nodeid 通过，原调用/结算/未发布事实全部验证；独立 foreign identity 反例在重算 SHA/size/registration 后明确命中原 `host_identity` 拒绝，不能以 `member_bytes` 拒绝代替；相邻 C10 source negatives、C13/C11/C12 四消费者与 B04 Host 边界通过；
- 正式固定 Session 的完整 suite 和 B02/B03 owned 回归通过，无 skip/xfail/新遗漏；
- fresh 15/11/30/28、131/84/47、2199 cases（1410/645/144）、324 boundaries、28 post-claim、15 exit 与原 owners 保持；final exact 缺口为原 B04 IDs 的 47/144/15；
- production/harness/helper/expected/frozen body 未变，文档/链接/scope 审核通过；C14 完成后仅恢复 C13 in_progress，B04 待 C13 completed 和独立入口复核。

## Verification

```bash
pytest -q tests/phase_b/test_b00c10_ordinary_trace.py tests/phase_b/test_b04_host_boundary.py
pytest -q tests/phase_b/test_b00c13_human_continuation.py tests/phase_b/test_b00c13_trace_consumers.py
```

另使用既有 B00C04 bounded runner 记录完整当前输入 fresh Session、独立 owned reports 和四个 construction/final 报告；列出 exact selections/IDs，不凭库存或旧 Session 推定通过。

## Stop Conditions

- 需要改 production/validator/helper/expected、扩大范围或弱化 Host integrity；
- 不能在原端口证明一次 effect、真实 settle 和 publication 前拒绝；
- 新失败需要改其他测试/合同、owner、预算、schema 或 frozen 验收；
- 无法以本票范围闭合必要完整验证。

## Required Documentation Updates

创建 review 时追加索引、C13/B04 blocked 关联和当前状态，保留历史。批准执行后独立记录实际测试交接，不改 C10 历史或 C13 冻结正文。C14 completed 后恢复 C13 原验收；只有 C13 completed 且 B04 独立复核通过，才按原授权恢复 B04 ready。

执行前将授权范围内的当前摘要同步为 C14 in_progress/C13 blocked；执行后按真实结果同步并检查根 README、核心文档和相关 TODO。新 completion/合同记录实际证据，不预填完成；正式固定输入之后的文档/lifecycle交付另存 manifest/diff/link/scope 审计，不能冒称原 Session 覆盖后续输入。
