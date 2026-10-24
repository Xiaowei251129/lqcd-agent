---
ticket_id: B00C30
phase: phase-b-graph-harness
status: blocked
type: corrective-implementation
depends_on: [B00, B01, B02, B03, B04, B00C29]
---

# 复核并恢复 B04 golden 的当前运行基线

## Goal

为已冻结开发基线 `79c1eb1` 中仍然失败的 B04 exact golden 比较查明来源，恢复可审计的 before/after 来源和正确 expected，并在原断言及验收边界下通过受影响回归；完成后独立复核 B05 的恢复条件。

## Why

B05 执行中发现 P1 验收阻断：从 Git 独立导出 `79c1eb1`，使用原始源码、原始测试及 expected、Python 3.12.7、LangGraph 1.2.10、checkpointer 3.1.1，运行：

```text
tests/phase_b/test_b04_current_source_handoff.py::test_current_code_parent_source_is_exact_across_fresh_roots[success]
```

两份 fresh 生产来源的 normalized trace 相等，但原 `compare` 在 `invalid_evidence:trace:exact` 失败，93.75 秒结束；有 89 处 semantic SHA 差异，没有直接可见的 outcome/event/owner 等非摘要字段变化。实际加载路径和 `application_build=dbe26a2f18dfcecf5e11c6410adfae26234eff5f5e8ac7436eb109e701503d4f` 已核实。这证明失败先于 B05；尚不能据此认定 89 处差异均为无害摘要漂移，也不能把 fresh 两份一致当成旧 expected 正确。

证据：`/private/tmp/lqcd-agent-b05-execution-20261019-hvo2m1_7/confirmed-baseline-blocker.json`、`isolated-baseline-fingerprint.json`、`b04-code-baseline-79c1eb1.log`、`baseline-79c1eb1.tar`。原始双根为 `/private/tmp/lqcd-agent-b04-code-product-s36h2mx7` 和 `/private/tmp/lqcd-agent-b04-code-product-yunl8py0`。

B05 的 Frozen Inputs 禁止把前置 golden 问题归入新增 CLI 的同步；Requirements 7 只授权其批准修改引起的来源审定。该基线问题需要单独审定，不能通过 B05 按 actual 覆盖旧 expected。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`。
- [B05 冻结票据](B05_ACCEPTANCE_INTEGRATION_AND_END_TO_END_HARNESS.md)、[B05 执行记录](../completions/B05_COMPLETION.md)、[B05 维护记录](../corrections/B05_MAINTENANCE.md)。
- B04 ticket/completion、C25–C29 合同和完成记录、原测试维护记录；均保持历史内容不变。
- 原 trace/proof validators、B04 source factories、对应 expected、上述实际反例及旧来源审定材料。

## Scope

- 逐项区分源码 build、Python/Host executable、LangGraph/checkpointer、fixture 输入和真实协议行为造成的差异，先明确影响范围，再决定是否同步 expected。
- 对受影响的既有 B04 expected 建立来源/preimage/DAG 审计，保留原断言、原格式和原 case/scenario/owner 集合。
- 取得当前固定输入的实际回归；本票不直接交付 B05 CLI 或 final adapters。

## Non-goals

- 不以来源一致替代合同正确，不用同步 expected 掩盖运行时缺陷。
- 不实现或扩大 runtime、authority、operation/schema、provider 或依赖。
- 不实施已保存的 B05 候选；其三个跨 Run 隔离修复继续由 B05 在恢复后验证和交付。

## Allowed Files

- `tests/phase_b/expected_traces/`：仅审计明确涉及本基线问题的既有 B04 expected，且必须满足下述来源与语义审定；不按目录整体覆盖。
- `tests/phase_b/test_b00c30_golden_baseline.py`：必要的来源/环境错误拒绝检查，调用原验证器，不另建通过判定。
- 本票 YAML lifecycle metadata；ready 后正文冻结。
- `docs/tickets/completions/B00C30_COMPLETION.md`，以及 completion index 的追加条目。
- `docs/tickets/corrections/B00C30_MAINTENANCE.md`，以及 corrections index 的追加链接。
- 实际状态受影响的核心 docs、Phase B Overview、ticket index、B05 执行记录；B05 仅 YAML lifecycle 可变。

## Do Not Touch

- Production source、原 tests 的断言、Phase A/protocol/catalog、validator/normalizer/selection/authority/schema、owners、2199 cases/324 boundaries/28 post-claim/B04 144、15 exits。
- 前置 frozen ticket bodies、原 completion/correction 历史、legacy tests/format、evaluation/config/dependencies、raw data、outputs、accepted artifacts、secrets。
- 不删除旧 native/sealed/反例，不 patch runtime fingerprint 或伪造环境/生产返回，不在旧 Run 重执行 effect 来修补来源。

## Requirements

1. 保存执行前全部输入和 expected 的摘要；重验上述独立 Git 基线反例。B05 候选包必须继续隔离，不能作为本票的通过输入。
2. 找到与原 expected 对应的可信原始来源和实际版本；允许从明确、可核验的原源码/输入快照在全新临时根建立对照来源，并明确其诊断身份；不得把重建材料重标为原 native/旧 Session，或用反事实改写原 sealed evidence。
3. 对全部受影响 expected 逐字段核对完整 before/after 与摘要依赖。除已证明的真实环境/build 及其派生 head/reference 外，outcome、事件顺序、typed null、identity/revision/epoch、owner、预算、source eligibility、invariant 必须保持。任一其他差异停止，不自行扩大授权。
4. 候选必须分别经两份 fresh 生产来源、原严格 normalizer 和原断言核验；固定 expected 后再开始正式回归。不能以 actual 自动重写、跳过断言、伪造版本或扩大 exclusion 获得通过。
5. 固定输入完整 fresh collection 回归，包含原 4785 项及本票实际新增项；受影响 B04 required/owned 证据用原规则独立核验。保留 450 秒 runner、全部完整 selection、Session 绑定、容量/分批/失败记录；不复用旧 token 作为当前通过。
6. 单独记录完整 legacy 325 与任何受影响的 golden/reference；不能以部分结果声明整票完成。完成本票仍不等于 Phase B completed；B05 恢复后须执行原完整 final。

## Deliverables

- 影响范围、原环境/来源、before/after preimage、逐字段差异和双 fresh 审定报告。
- 经审定且仅包含必要摘要变化的 expected，以及实际完整回归与独立 B04 证据。
- 独立 completion、当前状态与 B05 恢复入口复核记录。

## Acceptance Criteria

- 所有同步均有来源和逐字段理由；没有把基线问题重标为 B05 的 CLI 改动。
- 原 exact 反例及全部受影响场景通过，完整当前 selection 通过；没有放宽合同、断言、时限或证据规则。
- 原目录/协议/case/owner/exit 集合保持，所有受保护历史及源材料可恢复。
- B05 仅在本票完成且独立入口核验后恢复；原 B05 冻结正文保持，Phase B 不提前转绿。

## Verification

先用隔离基线及原始用例复现，再按审定范围运行原 B04 tests、原 acceptance validators、完整 collection/pytest、compileall、JSON/链接/metadata/scope/diff 检查。全部命令与原始输出保存于新的受控临时根；不得从测试递归启动真实全仓 final。

## Stop Conditions

- 无法恢复可信原来源/输入/版本，或候选差异不能限定到 Requirements 3。
- 实际发现 runtime/contract/schema/validator 缺陷，或需要改既有断言、ownership、Allowed Files、依赖或其他 Do Not Touch。
- 无法完成当前固定输入的完整回归、独立证据或容量要求；不删除受保护来源换取通过。

## Required Documentation Updates

更新本票 completion、`docs/REPO_CURRENT_STATE.md`、README/docs index、Verification/Evals、Phase B Overview，按实际政策变动追加 Decision Log。完成 stale-documentation scan。旧结果保留各自输入，不宣称 B05/Phase B 已完成。

用户已明确授权审定并执行本票；ready 后正文冻结，执行结果单独记录。
