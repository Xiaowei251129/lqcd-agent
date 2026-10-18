---
ticket_id: B00C20
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C10, B00C15, B00C18, B00C19, B04]
---

# B00C20：C10 当前普通失败入口的显式来源版本交接

## Goal

把 C10 仍实时执行当前产品 structured failure 的测试入口显式接到已批准的 trace 0.8 / proof 0.5，保留原端口、科学输入、nodeid、业务结果、结算和 effect 不变量，并以原 0.6/proof0.3 字段集合证明旧版本继续拒绝新增因果来源。只补遗漏的当前测试入口范围，不引入新版本、profile、生产合同或预算行为。

B00/C10/C19 须 completed；C15/C18/B04 是纠偏目标，不要求先 completed。创建仍为 review，不代表批准或实施；C18/C17/C16/C15/B04 保持 blocked。

## Why

C19 已完成不可达 transition 阈值的验收方法交接；C18 依原授权恢复并补齐 Human/FP/Grant/真实 publication 故障矩阵。最终原 native Session 发现 C10 `test_structured_domain_failure_is_settled_and_source_bound` 仍调用 `helpers/ordinary_mixed.py::no_code_trace` 的显式 0.6 collector。产品合法 failure 已按 C15 发布真实因果 fingerprint，原 0.6 `failure_member_source` 按冻结规则拒绝。这不是应放宽旧 normalizer 的理由。

C15/C16/C18 的允许接线清单列出了 C11–C13 Human 测试，却未包括上述 C10 测试与 ordinary_mixed helper。单纯给共享 collector 自动升级版本会破坏显式版本合同；修改旧规则或删除 failure 也不允许。因此需要本票批准这一窄入口交接。C18 Stop 的“需要未列 production/profile/文件范围”是停止依据。

原失败和完整扫描保存在 `/private/tmp/lqcd-agent-b00c18-after-c19-20261007-rkvqcvbq/full-session/`。同一 Session 全部 4122 项实际执行，4120 passed、上述 C10 两项 failed；其余纠偏专项和 legacy 均通过。同批 C10 mixed exact 差异已保存两份 before/两份 after raw 的完整 preimage 审计，只涉及 runtime fingerprint 与派生摘要；已按 C18 原范围同步，并在新的 native Session 通过原双 fresh nodeid。这一项已修复，不需要本票新增来源合同。local UNIX socket 的沙箱拒绝单独按原测试权限处理，不改变测试或当作产品缺陷。

## Read First

- [AGENTS](../../../AGENTS.md)、[文档入口](../../README.md)、[工作流](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)、[验证指南](../../VERIFICATION_GUIDE.md)；
- [C10](B00C10_ORDINARY_RESOURCE_TRACE_HANDOFF.md)、[C15](B00C15_PRODUCT_FAILURE_FINGERPRINT_AND_GRANT_SOURCE_HANDOFF.md)、[C18](B00C18_ORDINARY_REPAUSE_CAPACITY_SOURCE_HANDOFF.md)、[C19](B00C19_HUMAN_CAPACITY_REACHABILITY_ACCEPTANCE.md)及其独立合同/completion；
- `test_b00c10_ordinary_trace.py`、`test_b00c10_trace_consumers.py`、`helpers/ordinary_mixed.py`、`helpers/product_failure_sources.py` 与原显式 dispatch；
- 执行根的完整失败清单、legacy-current-call-sites、coverage 和输入 manifest，不把专项累计 passed 当成完整 Session 通过。

## Scope

- C10 当前 structured failure 的显式 0.8 被动来源交接；
- 当前正向与同一实际材料的旧 0.6 拒绝，原 nonfailure/mixed/primitive 兼容；
- 所有当前 0.6/0.7 调用点的只读核对、当前四消费者和最终 C18 接续交接。

## Non-goals

- 不新增 trace/proof/profile，不修改生产、预算、科学 fingerprint recipe、authority 或效果；
- 不重写旧 sealed evidence、冻结正文、原 cases/owners，不完成 B04 Code parent、泛化 graph recovery 或 47/144；不 commit/push。

## Allowed Files

- `tests/phase_b/test_b00c10_ordinary_trace.py`：仅原 structured failure nodeid 的显式新来源接线与保留其原实质断言；其余原 nodeids、outcome 和 observe IDs 保持。新增专用兼容/双 fresh 拒绝测试可以独立命名，不能删除、skip 或改写失败业务期望；
- `tests/phase_b/helpers/ordinary_mixed.py::no_code_trace`：仅明确选择 0.8 与对应已有被动 collector/observer 的参数接线。参数仅允许原 0.6 与显式 0.8，未知值拒绝。默认仍为 0.6，no-failure、primitive、mixed 原默认不改；不按运行结果自动升版、不改原 Agent/输入/调用/时钟/selector/ledger；
- `helpers/{product_failure_sources,ordinary_sources,control_traces}.py` 仅上述显式接线确需的被动捕获，已有来源和旧分支规则不变；优先直接复用；
- 新 `test_b00c20_current_failure_handoff.py`、`fixtures/b00c20/`、`expected_traces/b00c20/` 及对应四消费者；可复用既有 C15 消费工具，不扩大其校验语义；
- `acceptance_matrix.json` 仅 B00 A07-META-006/015 的新来源 meta，按原排序接线，不改已有 scenario owner、cases 或 required；
- 前置 expected 仅按 C18 原 runtime fingerprint/完整派生 preimage 审计规则同步；原 0.7 expected/旧 sealed evidence 不改，合法新轨迹使用新路径；
- 本票 YAML、新独立 contract/completion；C18/C15/C16/C17/B04 completion 与 maintenance 追加；当前状态、Overview、索引及必要 Verification Guide/Decision Log。

## Do Not Touch

- 所有 production、Phase A、预算 limits/reserve/算法、authority/Grant、科学 recipe、旧 0.1–0.7 dispatch/接受拒绝规则；
- B00 schemas/catalog/cases/Session/failpoints/exclusions、B02/B03 owned 语义和原 owner、旧 sealed evidence、冻结正文、Phase A/legacy runtime 及 `tests/phase_b/` 之外的 legacy tests、dependencies/configs、raw/outputs/accepted/secrets、外部系统和 B05。

## Requirements

1. 保留原 C10 structured failure 端口/输入/业务预期：真实 Analysis structured failure 有真实 Agent 返回和原 settlement，进入 Coordinator/Human paused，不是 Host exception，不生成 maximum receipt。所有普通 effect 和 failure occurrence 单次；重读不执行 effect。
2. 新正向明确使用已有 0.8/proof0.5 与 ProductFailureSources。原 failure/member/call/issuer/producer 交叉校验完整通过；不得使用后处理伪造来源或额外预算事实。
3. 从同一实际材料构造原 0.6/proof0.3 的合法字段集合，去掉仅新版本声明（0.6 也不携带 0.7 才新增的 `ordinary_maximum_settlements`；本路径须先证明没有 maximum 结算）；原公开 records、原返回和 fingerprint bytes 保持。必须复现 `failure_member_source`，不能以 schema mismatch 冒充来源拒绝。0.7 如覆盖也使用原 proof0.4 字段集合。
4. 0.6 nonfailure、mixed Code/fresh Analysis、primitive actual/unknown/unsettled 均保持原 nodeids 和行为；C10 structured failure 的原 paused/returned/settled 断言不能删除或降格成“拒绝就是成功”。新版本正向与旧版拒绝分别验证。
5. 对所有直接/间接调用 `no_code_trace`、当前产品 `ControlTrace` 0.6/0.7 的入口建立明确表：实际 domain failure/新增 FP、Host failure、无失败、原 primitive 分别绑定版本与测试。当前完整失败扫描中出现的其他必要源交接必须在实施前核对确属本票明确文件/语义范围；不借 helper 全局切换隐式处理。
6. 两个 fresh 根原端口输出完整 normalized 一致；固定新 expected 保存 before/after raw 并审核，科学/返回/来源材料变化应改变 normalized 或拒绝。missing/duplicate/foreign/stale 声明、旧版本兼容与 collector/matrix/runtime validator/exit digest 四条消费路径全部核验。meta 不计 B04 owned。
7. 修复后由原授权恢复 C18 剩余验收，重建稳定当前输入 Session，实跑全部 exact collection；同 Session 独立验证 B02 1410/B03 645、construction15/11/30/28、final 具体47/144/15。真实 socket 测试使用能执行本机 socket 的环境，禁止 skip、替换 fixture 或修改 expected 掩盖权限错误。
8. C15/C16/C17/C18 必须分别按原覆盖表和最终证据复核后才 completed；B04 仍独立入口复核，不自动 ready/completed。保持131/84/47、2199、324 boundaries、28 post-claim、B04 144、15 exits/原 owners。

## Deliverables

- 最小显式入口接线、新旧版本同材料验证与双 fresh 原端口证据；
- 当前旧版本调用点完整清单、四消费者和固定输入验收；
- 独立 contract/completion、C18 覆盖项与 B04 接续边界交接。

## Acceptance Criteria

- 原 C10 structured failure nodeid 在当前 0.8 下通过原 paused/settled/真实返回断言，双 fresh 单次 effect；同材料 0.6 按原来源规则拒绝；
- C10 其他所有原测试、C15–C19 新来源/预算/Human/Code 和旧版本规则无回退；
- 不依赖隐式升版、state/selector/ledger patch、假 failure/return、过滤、扩大 exclusion、历史 retag 或修改科学 fixture；
- 当前完整 exact suite、同 Session owned、construction 与准确 final 集合按原规则验证，并保留所有真实失败/重跑记录；
- C18 各票独立复核与 source-of-truth 同步完成，B04 owned 仍0/144、Phase B false；未 commit/push。

## Verification

```bash
/opt/anaconda3/bin/python -m pytest tests/phase_b/test_b00c10_ordinary_trace.py tests/phase_b/test_b00c10_trace_consumers.py tests/phase_b/test_b00c20_current_failure_handoff.py -q
/opt/anaconda3/bin/python -m pytest --collect-only -q
```

批准 ready 后先保存完整输入/冻结摘要和当前失败 raw，再完成原 nodeid 的显式交接与对应双 fresh/消费者。最后冻结输入，按原 Session/native 有界分批检查全部 exact nodeids，独立 owned/construction/final。Review 阶段仅检查模板、链接、范围、依赖及已有证据，不执行本票代码或创建完成记录。

## Stop Conditions

- 需要修改未列文件、production、科学 recipe、预算/authority、旧来源解释、版本/schema/profile；
- 只能通过隐式切换旧测试版本、删原实质断言、改 fixture 科学内容/原结果、假 effect/return、skip/过滤/排除来通过；
- 需要改变 case/owner/required、旧 sealed evidence、冻结正文或用历史 Session 声称当前通过。

## Required Documentation Updates

执行后新增独立 contract/completion，追加 C18 完整覆盖及 C15/C16/C17 各自结论、B04 独立入口结论；同步 Current State、Overview、文档/纠偏/完成索引与必要验证说明。创建阶段只登记 review 及真实阻塞，不把候选或原专项结果写成完成。
