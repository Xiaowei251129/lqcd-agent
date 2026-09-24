---
ticket_id: B00C08
phase: phase-b-graph-harness
status: ready
type: corrective-contract
depends_on: [B00, B01, B02, B00C05, B00C06, B00C07]
---

# 为 B02 canonical fixture 补齐显式 trace 0.5 交接

## Goal

补齐B00C07 fixture适配的完整交接范围：normal与safe-timeout的上游来源链、canonical成员及状态投影、显式trace0.5/proof0.2、受影响验收引用，以及Analysis preparation fixture边界。旧normalizer不改变，B02控制义务与B03独立canonical验收不合并。用户于2026-09-24同意按审阅结论补强、冻结并执行交接，随后继续原B03。

## Why

B00C07批准将B02 synthetic Code材料替换为真实validators可接受的needs_input bundle，同时禁止这些B02证据切换至0.5。真实A03注册反例证实二者不能同时满足：任务成员引用真实prestart execution head，其原始bytes SHA随fresh Run根变化；trace0.4将members[].sha256保持为literal，结果两次真实control run均committed且事件/结果一致，normalized attempt:finished及resume result摘要仍不同。固定golden不能匹配两次运行。

反例只增加具有必要source依赖的contract-shaped任务成员，不冒充完整A05 bundle。复现为`tests/phase_b/test_b03_control_member_trace_boundary.py`；raw/report在`/private/tmp/lqcd-agent-b00c07-a6jronvr/member-trace-*`。这是此前C06已解决的摘要投影问题在既有B02证据中的适用范围遗漏，不是要求再新增trace版本。

复审在`/private/tmp/lqcd-agent-b00c08-review/`进一步确认：normal source的task/input/context/manifest摘要仍是synthetic字符串摘要，仅切换版本会被0.5拒绝为missing_source；timeout production adapter写死两个legacy state keys，完整path-key集合探针在Attempt started前被拒绝。B02另有`b02-source-timeout`轨迹；1410个runtime与30个construction expected全为不携带成员摘要的trace0.1。`prepared_source`又复用normal fixture进入Analysis preparation，不能将needs_input作为canonical Analysis输入。以下范围统一处理这些已确认交界。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`；
- B03、B00C06、B00C07冻结票及completion；A05/A07及protocol/catalog；
- `helpers/control_traces.py`、`test_external_source_traces.py`、`harness/trace_proof.py`、`harness/a05_trace.py`；
- 上述实际注册反例、B02 construction/runtime evidence的生产入口。

## Scope

本票只做文档交接。完成后B03继续原实现，补充B00C07的范围如下：

1. 对实际依赖canonical成员的B02 raw proof及对应固定expected，显式标记trace0.5/proof0.2并提供真实typed sources/material sources；不得只改版本号、制造source、删除引用或保持constant摘要。
2. 必需迁移的source轨迹为`B00-EXTERNAL-TRACE-001`和`b02-source-timeout`，分别保留原`test_external_reservation_source_trace`及`test_source_bound_trajectory[timeout]` nodeid。1410个B02 runtime和30个construction phase-only轨迹保持0.1及原IDs/expected；复用fixture需要重跑并不意味着升级trace。其他source轨迹仅在来源闭包实际包含已替换canonical对象时允许同样显式迁移，实施前保存exact影响清单、来源原因和旧新引用映射。
3. Collector、scenario、runtime case、exit四条路径共用已存在的0.5验证规则。缺少来源、换Run/Attempt/producer、错误checksum/member bytes、stale Session必须拒绝；Task/Manifest/Code result/member/state/checkpoint全链闭合。
4. 保留原required nodeids、owner、cases、events/control outcomes/invariants及真实hooks。B02成功仍只计B02控制义务；不能因此增加B03 passed。旧0.1–0.4正常/负向回归和版本规则继续存在；原expected文件保留为旧版本历史基线，新canonical expected另存并显式更新相关引用，不自动升级旧source。
5. Golden差异只接受C07既定材料替换、本票明确的normal/timeout上游来源与Analysis fixture分离、独立path修复、runtime fingerprint及上述显式投影版本带来的派生差异。保存raw旧新对象、identity/reference映射、投影版本、每项变化原因；两个fresh根exact一致后离线审定。保持被测控制操作的事件顺序、结果、winner/owner、故障组合和不重复执行/结算断言；拒绝弱化比较或在线actual回写。

### Complete source fixtures and timeout handoff

- Normal fixture从task/context、unmaterialized manifest、aggregate reservation、immutable core、Pause binding到receipt、external result、normal final、canonical needs_input bundle提供真实bytes和摘要闭包。由同一B03 production builder/validator验证；不保留`digest("task")`等无对应typed对象的占位，也不以collector伪造对象去迎合已有摘要。共享synthetic source helper可保留原控制用途，并新增显式canonical初始化入口供normal/timeout fixture选择，防止无关cancel/interrupt测试被静默改义。
- Safe-timeout fixture使用canonical host_timeout failed bundle：完整四个canonical paths及两项legacy null paths，status=failed、usable=false，逐spec not_run/operation_timeout、真实interrupt evidence及按dispatch phase确定的receipt引用/typed absence；不生成虚假Backend result、seal、audit或patch，不执行verifier，不重复aggregate settlement。原recoverable timeout、integrity failure及unavailable三种控制结果和same-winner收尾保持。
- B03可在原control integration范围修改`InterruptedDelivery`的legacy-only key检查、成员解析和registry接线以接受A05既定完整nullable集合；null不是文件名，不转成字符串路径、不参与member引用集合。新增canonical closed validator核对result status、成员集合、identity与typed absence，不能仅扩大key allowlist。原timeout negative cases改为对对应canonical字段施加相同故障，保留required nodeid和拒绝位置。
- 上游材料替换所需的source/head/identity重新绑定须保存逐项原因；它不是修改A04/A05状态机或放宽budget/authority的许可。旧fixture的synthetic控制证据不因此自动变成B03 canonical证据。

### Analysis preparation fixture boundary

Normal消费顺序fixture保持needs_input；不得将其直接交给canonical Analysis入口。`prepared_source`及相应进程fixture独立使用B03生产验证通过的success/usable=true bundle作为前置，真实完成必要verification与资源结算，然后执行原被测preparation操作。允许这套独立前置新增合同要求的verification resource事件，保存原因与断言；不改变原preparation控制事件、required nodeids、拒绝条件或consumer不重派发的验证。普通needs_input与host_timeout fixture仍保持原一次aggregate settlement，不能因Analysis前置需要而放宽这些计数。

纯B02 control-half synthetic preparation adapter仅用于既有control ordering测试，不计canonical Analysis成功；B03还必须另行验证真实fresh Analysis来源、success/usable guard、effective tree及父图入口。禁止通过移除guard让needs_input进入canonical Analysis。

## Non-goals

不新增trace0.6、不改旧normalizer，不修改runtime/public contract、case0.3、2199 cases、324 boundaries、131 owners/requirements、28 post-claim或15 exit gates；不实现本票以外的Backend或产品路由。

## Allowed Files

本票执行仅允许自身YAML、独立`docs/tickets/completions/B00C08_COMPLETION.md`与index、B03 completion追加与生命周期、docs README/Current State/Verification Guide/State Schema/Artifact Contracts/Decision Log/Phase B Overview。

交接后B03新增窄授权：

- `tests/phase_b/test_external_control.py`、`test_external_consumption_control.py`、`test_timeout_consumption_control.py`、`test_target_preparation_control.py`及相关新增canonical helper：仅上述来源fixture、timeout与Analysis前置适配，保留原控制保护；
- `helpers/control_traces.py`、`helpers/b02_source_traces.py`、`helpers/process_client.py`、`helpers/runtime_cases.py`、`helpers/construction_cases.py`及必要的已有A05 helper：仅fixture选择、真实source捕获、同一版本证据接线；
- `test_external_source_traces.py`、`test_b02_source_trajectories.py`及本次反例测试：原nodeids/正负义务保持，更新显式expected定位并增加来源闭包回归；
- `fixtures/`、`expected_traces/`新增显式0.5文件；`acceptance_matrix.json`与确实受影响的证据bindings只更新fixture/expected来源引用，原IDs、owner、checks和计数不变；
- `src/lqcd_agent/control/pause.py`及原B03已允许的control/registry/code_agent文件：仅A05既定timeout完整nullable映射、validators、source与verification integration，不改变A04 phase/authority/public contract；
- C07已授权的trace0.5四路径来源修复保持；不得修改0.1–0.4投影或增加调用方exclusion。

## Do Not Touch

冻结票正文、旧trace实现、Phase A/protocol/catalog/inventory/case seals、legacy/root tests、dependencies/configs/data/provider/network；本票不修改src或tests实现。迁移到0.5的source轨迹保留原expected字节作为历史基线，新expected另存；其他未迁移轨迹仍适用原B03/C07明确批准的fingerprint/nullable projection派生同步规则，本条不撤销该授权。

## Deliverables and Acceptance Criteria

- 独立治理完成记录和B03窄交接，明确替代C07受影响B02证据版本限制，并补充完整来源、timeout及独立Analysis fixture；C07其他保护保持。
- 真实A03 member反例与raw tamper负向检查通过；protocol/catalog/generated/frozen body/links/scope checks通过。
- 只有B03后续完成上述fixture适配、双fresh根和四条验证路径后才能宣称技术阻塞已修复；仅本票文档完成不计runtime通过。
- B03接续验收必须覆盖normal needs_input、host_timeout、post-claim failed/unavailable及独立Analysis前置；实际注册member/pointer/state/checkpoint全链的正向双根证据通过，并拒绝foreign/missing/rehashed错误来源。不能仅重复“旧版本不支持”的负向probe后宣称修复完成。
- B03最终仍须full suite、B00/B01/B02 construction15/11/30、同Session B02 runtime1410及B03 construction28/runtime645；累计mapped84/remaining47，Phase B仍未完成。

## Verification

执行本票仅重跑member反例、raw tamper、protocol/catalog/generated及文档冻结检查。B03实施时先完成exact影响清单，再做正负证据、双根golden审查与完整原验收。

## Stop Conditions

需要改变runtime合同、旧版本语义、case/owner/check门槛或授权范围外材料时停止；仅更新expected无法使双fresh根一致时不得宣称完成。B03预算事务与失败恢复仍按原票实现，不由本交接豁免。

## Required Documentation Updates

Current State、Verification Guide、Decision Log、索引和B03记录需区分文档授权、已实现修复及仍待完成的B03工作；完成stale-documentation检查。
