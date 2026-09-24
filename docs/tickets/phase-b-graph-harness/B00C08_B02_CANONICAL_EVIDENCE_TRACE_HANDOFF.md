---
ticket_id: B00C08
phase: phase-b-graph-harness
status: review
type: corrective-contract
depends_on: [B00, B01, B02, B00C05, B00C06, B00C07]
---

# 为 B02 canonical fixture 补齐显式 trace 0.5 交接

## Goal

仅修正B00C07 fixture适配与trace版本限制之间的冲突：当既有B02控制证据引用新增canonical A05成员时，允许该证据显式使用trace0.5/proof0.2。旧normalizer不改变，B02控制义务与B03独立canonical验收不合并。本票为review，未获批或执行。

## Why

B00C07批准将B02 synthetic Code材料替换为真实validators可接受的needs_input bundle，同时禁止这些B02证据切换至0.5。真实A03注册反例证实二者不能同时满足：任务成员引用真实prestart execution head，其原始bytes SHA随fresh Run根变化；trace0.4将members[].sha256保持为literal，结果两次真实control run均committed且事件/结果一致，normalized attempt:finished及resume result摘要仍不同。固定golden不能匹配两次运行。

反例只增加具有必要source依赖的contract-shaped任务成员，不冒充完整A05 bundle。复现为`tests/phase_b/test_b03_control_member_trace_boundary.py`；raw/report在`/private/tmp/lqcd-agent-b00c07-a6jronvr/member-trace-*`。这是此前C06已解决的摘要投影问题在既有B02证据中的适用范围遗漏，不是要求再新增trace版本。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`；
- B03、B00C06、B00C07冻结票及completion；A05/A07及protocol/catalog；
- `helpers/control_traces.py`、`test_external_source_traces.py`、`harness/trace_proof.py`、`harness/a05_trace.py`；
- 上述实际注册反例、B02 construction/runtime evidence的生产入口。

## Scope

本票只做文档交接。完成后B03继续原实现，在B00C07已批准的canonical fixture替换范围内：

1. 对实际依赖canonical成员的B02 raw proof及对应固定expected，显式标记trace0.5/proof0.2并提供真实typed sources/material sources；不得只改版本号、制造source、删除引用或保持constant摘要。
2. 受影响对象至少含`B00-EXTERNAL-TRACE-001`，以及执行同一canonical fixture且来源闭包实际包含Code bundle的B02 construction/runtime证据。实施前列出exact scenario/case/nodeid清单及引用原因；未受影响证据保持原版本。
3. Collector、scenario、runtime case、exit四条路径共用已存在的0.5验证规则。缺少来源、换Run/Attempt/producer、错误checksum/member bytes、stale Session必须拒绝；Task/Manifest/Code result/member/state/checkpoint全链闭合。
4. 保留原required nodeids、owner、cases、events/control outcomes/invariants及真实hooks。B02成功仍只计B02控制义务；不能因此增加B03 passed。旧0.1–0.4正常/负向回归和版本规则继续存在；原expected文件保留为旧版本历史基线，新canonical expected另存并显式更新相关引用，不自动升级旧source。
5. Golden差异只接受C07既定材料替换、独立path修复、runtime fingerprint及上述显式投影版本带来的派生差异。保存raw旧新成员、投影版本、每项变化原因；两个fresh根exact一致后离线审定。拒绝弱化比较或在线actual回写。

## Non-goals

不新增trace0.6、不改旧normalizer，不修改runtime/public contract、case0.3、2199 cases、324 boundaries、131 owners/requirements、28 post-claim或15 exit gates；不实现本票以外的Backend或产品路由。

## Allowed Files

本票执行仅允许自身YAML、独立`docs/tickets/completions/B00C08_COMPLETION.md`与index、B03 completion追加与生命周期、docs README/Current State/Verification Guide/Decision Log/Phase B Overview。

交接后B03新增窄授权：`tests/phase_b/helpers/control_traces.py`、相关canonical fixture helper、`test_external_source_traces.py`及本次反例测试；`fixtures/`、`expected_traces/`新增显式0.5文件；`acceptance_matrix.json`与确实受影响的runtime证据bindings只更新fixture/expected来源引用。原IDs、owner、checks和计数不变。必要的source捕获接线可进入已存在A05 helper；不得修改0.1–0.4投影或增加调用方exclusion。

## Do Not Touch

冻结票正文、旧trace实现和旧expected字节、Phase A/protocol/catalog/inventory/case seals、legacy/root tests、dependencies/configs/data/provider/network；本票不修改src或tests实现。

## Deliverables and Acceptance Criteria

- 独立治理完成记录和B03窄交接，明确替代C07“受影响B02证据不得升级0.5”这一条；C07其他范围保持。
- 真实A03 member反例与raw tamper负向检查通过；protocol/catalog/generated/frozen body/links/scope checks通过。
- 只有B03后续完成上述fixture适配、双fresh根和四条验证路径后才能宣称技术阻塞已修复；仅本票文档完成不计runtime通过。
- B03最终仍须full suite、B00/B01/B02 construction15/11/30、同Session B02 runtime1410及B03 construction28/runtime645；累计mapped84/remaining47，Phase B仍未完成。

## Verification

执行本票仅重跑member反例、raw tamper、protocol/catalog/generated及文档冻结检查。B03实施时先完成exact影响清单，再做正负证据、双根golden审查与完整原验收。

## Stop Conditions

需要改变runtime合同、旧版本语义、case/owner/check门槛或授权范围外材料时停止；仅更新expected无法使双fresh根一致时不得宣称完成。B03预算事务与失败恢复仍按原票实现，不由本交接豁免。

## Required Documentation Updates

Current State、Verification Guide、Decision Log、索引和B03记录需区分文档授权、已实现修复及仍待完成的B03工作；完成stale-documentation检查。
