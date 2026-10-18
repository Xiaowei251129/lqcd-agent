---
ticket_id: B00C25
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C22, B00C23, B00C24, B04]
---

# B04 实际 publication 子进程的原生 Session 来源交接

## Goal

让 B04 两类实际 publication 工厂的 spawned child 使用父进程原始 process-hook request 的同一 native Session，消除 C24 完整验收中已复现的 unit-only 来源错配。保持真实进程、原 hook/nonce/退出状态/owner/trace 校验和原 18 boundaries／144 cases。

C24、C23、B04 是纠偏目标，不要求先 completed。用户批准修订并登记 ready 后方可执行；执行前冻结本正文。C24/C23/B04 保持 blocked；本票不能直接恢复 B04，也不能代替 C24/C23 原整票验收。

## Why

C24 已补齐 ConsumptionFailure 来源，最终固定输入的 90 项专用测试通过，16 类来源双 fresh exact 通过；8 个 fresh native Session 的四消费者拒绝 188 组来源篡改。完整 exact collection 为 4549，已验证通过的批次覆盖 4261 个节点（含 legacy 325）；完整验收尚未通过。

原生批次 484 在 `artifact.bounded_state_sync.after.committed_result_replay` 失败。`multiprocessing.get_context("spawn")` 的 child 重新 import，未启动 pytest writer，`pytest_evidence.ACTIVE` 为 None；`current_binding()` 因而返回 `unit-only-not-acceptance`。父进程携带真实 native Session，严格相等断言正确拒绝。原 process-hook request 已有真实 binding，但 source receipt 和后续被动来源没有消费它。

同一当前 Session 下，将该 case 单独运行，仍在原断言失败；独立 control case `budget.decision_before_transition.after.committed_result_replay` 同样失败。两类 helper、trace_sources 与 pytest_evidence 均与 C24 执行前字节一致。旧局部 unit-only 检查中父子双方都是 unit-only，不能证明原生 Session 接线正确。

原始证据：`/private/tmp/lqcd-agent-b00c24-execution-20261013-t2dy06c8/native-child-binding-blocker.json`、`partial-full-stop-audit.json`、`final-session/binding-stop-{0,1}-pytest.json` 和实际 child `process-source.json`。固定输入摘要 `c118a9c21145568409e84b494dabe08ab3746e99aeb91a3d4d609088852fab48`，Session `e8a54dddc50542973ab4432b3218062a1d0e8cb7e52c5fe7122b1aaa21716e5d`。

另有批次 475 十项组合触及原 300 秒进程上限，原日志保留。它不等同于上述确定性断言错误；后续必须完整拆分其十项重跑，不能过滤、扩容 timeout 或用它解释 binding 失败。

2026-10-14 追加只读审查：原生 envelope 已实际写入 B04 hook，但 canonical registry 的18个B04条目 hook_ref=null、case_bindings=[]。用两份独立反例及原批次484的真实hook分别调用原validate_runtime，均拒绝 invalid_evidence:hook:case_id。仅修复child binding仍不能通过完整汇总。本修订同时批准诊断Session隔离与测试局部hook绑定，原正式registry保持；审查证据 `/private/tmp/lqcd-agent-c25-review-20261014-a4nnccdh/original-hook-registry-rejection.json`。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/tickets/TEMPLATE.md`。
- `docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`。
- [C24](B00C24_CONSUMPTION_FAILURE_SOURCE_HANDOFF.md)、[C24 实际记录](../completions/B00C24_COMPLETION.md)、[C23](B00C23_UNCONSUMED_CODE_FINAL_STOP_SOURCE_HANDOFF.md)、[B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)。
- `tests/phase_b/helpers/{trace_sources,b04_publication_cases,b04_control_cases,control_traces}.py`。
- 只读 `tests/phase_b/harness/{session,pytest_evidence,failpoints,trace}.py` 与原 case registry、matrix。
- 上述原生 request/envelope、原始 receipt 和执行前源文件快照。

## Scope

- 为原 B04 spawned child 显式交接真实 process-hook request 的 binding；整条被动来源采集使用同一 binding，作用域结束必须恢复，不能污染后续测试。
- 覆盖 invocation publication、advance、Code bundle、invalid Human response 四类 child 入口，以及两类工厂的全部原 144 cases。竞态子进程不因本票获得任何 authority。
- 原144个外层测试入口编排独立fresh native诊断Session，真实hook仅在该Session产生并完整保存，原validator以显式测试局部绑定验证。外层完整Session不生成尚未绑定的B04正式runtime hook；不得生成后删除/过滤hook，不得改canonical registry或把局部诊断计作B04 owned。
- 在修复后先预演全部 144 个 case 的 fresh native 来源链，保留实际 hook、两根 exact、恢复/拒绝及 effect 次数证据，再进行完整验收。
- 复核 C24 专项、C23 所需来源及七类停止路由，保存原完整集合的所有失败和未完成项。

## Non-goals

- 不增加 trace/proof/wire 版本，不改变生产 authority、schema、预算、拓扑、停止或恢复合同。
- 不接受 unit-only、stale/foreign Session；不把 child 伪装成 pytest writer，不制造 hooks、observations、case_results 或已完成证据。
- 不建立 B04 registry/matrix ownership，不完成其 47 construction／144 owned；不实现 B05 exit adapters。
- 不把本票完成当作 C24/C23/B04 自动完成，不 commit/push。

## Allowed Files

- `tests/phase_b/helpers/trace_sources.py`：仅显式、作用域受限的原 child binding 交接；原父进程 ACTIVE 优先、unit-only 非验收含义和旧调用行为保持。
- 可新增 `tests/phase_b/helpers/b04_process_binding.py`：上述交接上下文、原request检查及专用native Session编排、原始receipt/source结果保留和测试局部hook验证。递归入口标志只选择诊断模式，不能提供或替代binding，不建通用环境变量来源旁路。
- `tests/phase_b/helpers/{b04_publication_cases,b04_control_cases}.py`：仅原request进入child、被动source binding、诊断receipt/raw/result路径保留和退出/清理接线；不得更改原生产路径、故障位置、结果预期或outcome分类。
- `tests/phase_b/test_b04_runtime_cases.py`：原144个case参数的外层native诊断Session编排/内层实际工厂分支；保留原IDs、集合和全部原工厂断言。每case两次fresh原生执行，保存完整inner envelope并exact比较；内层实际来源不能重标成外层Session。
- 新增 `tests/phase_b/test_b00c25_process_session_binding.py`：原生正反验证、作用域隔离和真实 child/process-hook 来源测试。
- 本票 YAML；新增 `docs/tickets/completions/B00C25_COMPLETION.md`、`docs/tickets/corrections/B00C25_PROCESS_SESSION_BINDING_CONTRACT.md`。
- C24/C23 completion/source contract、B04 completion/maintenance 仅追加；C24 YAML 仅独立入口复核后的 lifecycle。
- `README.md`、`docs/{README,REPO_CURRENT_STATE,VERIFICATION_GUIDE,DECISION_LOG}.md`、Phase B Overview、completion/corrections 索引：仅当前事实及证据入口。

## Do Not Touch

- 全部 production、Phase A、依赖、旧 harness validators、pytest_evidence/session 的 native 规则、旧 trace/proof/projector/default。
- registry、acceptance matrix、case IDs/分类/owner、已有 fixtures/expected、sealed evidence、冻结票正文和历史记录。
- 不删除父子 binding 相等断言；不放宽 hook 的 nodeid/case/nonce/PID/exit 验证；不使用 fork 掩盖 spawn 交接，不扩大 timeout/exclusion，不 skip/xfail/过滤失败。

## Requirements

1. 交接值必须来自父进程原 `process_hook_request` 的明确参数，绑定原 Session token、完整 digests、project root、nodeid、case 和 process token。缺字段、foreign request、stale token、错 case/nonce 或 digest 不符必须被原 request/receipt 校验链拒绝；不能用固定测试值或读取任意环境文件补齐。
2. source receipt、被动 collector 和所有在该 child 实际生成的原始来源绑定必须一致。不能只改 receipt 表面值、在父进程事后重标来源，或更改 immutable Backend/Run bytes。
3. 父进程 ACTIVE 的 binding 不可被 child 上下文替换；无明确 child request 的普通 unit-only 行为不变。多个顺序/嵌套测试及异常退出不泄漏上下文，不影响其他 native Session。
4. 保留原 production hook 和子进程真实退出 97 的验证；匹配实际 PID 与一次性 process token，child request 不能代替真实 hook 到达或原始执行证据。
5. 两类工厂及全部 child 入口均测试；全部原 144 case 在当前 native Session 下执行，逐项覆盖原四种 outcome。两份 fresh 根的 exact 比较使用原来源规则，不修改 expected，不忽略 material/raw 字段，不把局部 factory pass 当作 B04 owned。
6. 修复 binding 后出现的原来源/owner/收尾问题必须如实保留。若仍需改旧 projector、production、既有 expected 语义或原 case 断言，停止；本票不预先授权未知的后续修复。
7. C24 原 90 项专用测试、16 模式双 fresh、四消费者及原 B04 七类停止路由在新当前输入实际通过。缺失/篡改/跨源/旧 Session 继续拒绝；不重复 effect，不以本票交接产生新 authority。
8. 最终完整 exact collection（4549 为修复前基数，新增本票测试逐项列入），legacy325、同 Session 独立 B02 1410／B03 645、fresh 原 CLI construction15/11/30/28和 final 精确47/144/15。原批次475的十项全部以原300秒限制分别实跑；其他失败不按超时处理。
9. 131 required／84 mapped／47 remaining、2199 cases、324 boundaries、28 post-claim、B04 18 boundaries／144 cases／owned0、15 exit及原owners保持，Phase B false。
10. 正式完整Session与诊断Session必须在生成时隔离；内层使用原Session/run_pytest/validate_pytest/consume_process_hook，按case建立仅测试局部的hook绑定并调用原validate_runtime，验证唯一实际hook和完整原factory结果。局部binding不是canonical ownership，不产生正式B04 case_results；原factory的phase摘要不能替代B04后续Run source proof。完整inner request/envelope/source/raw/receipt保留，外层用实际通过的全部内层结果断言通过，禁止缓存旧结果/取消ACTIVE/伪造Writer/事后删事件。正式registry和matrix字节不变，原validator对未绑定正式B04 hook继续拒绝。
11. 专项必须证明完整Session外层不含诊断hook，内层完整保留且错token/digest/case/nonce/PID/receipt拒绝；失败内层让对应原外层节点失败。144节点无遗漏，局部双fresh相等、正式owned仍0/144、原final缺口保持。
12. 本票完成后独立审计 C24 原验收；满足其全部要求才可依原授权恢复并完成 C24。允许以共同冻结的最终代码输入形成各票独立报告，明确测试输入与后续文档/lifecycle交付差异，不能重标旧 Session。C23随后仍须原 A1–A6独立验收；B04入口另审。

## Deliverables

- 最小显式 child binding 接线、专用正负测试和独立来源合同。
- 两个原反例修复前/后原生证据、全部144 case逐项结果及原 hook/源 binding 记录。
- 当前完整 exact suite、owned/construction/final报告及 scope/frozen-body/owners审计。
- 独立 completion、C24入口报告和 C23/B04剩余责任，保留所有历史失败。

## Acceptance Criteria

- 两个已复现 case 在两个 fresh 根的真实 native Session 下通过；child receipt、proof 和父 Session一致，实际 hook和退出97保持。
- invocation、advance、bundle、invalid-response四类入口及全部144 case通过原断言；未知后续失败不能被本票吞掉。
- 删 binding、改 token/digest/nodeid/case/nonce、跨 Session/跨 child、伪造 receipt、遗漏实际 hook等反例拒绝；退出后上下文恢复、普通单测行为保持。
- C24来源、七类停止、完整suite及同Sessionowned通过，construction与final精确缺口不变；不得仅证明单个 binding 相等就宣布完成。
- 原validators、production、expected、registry、owners、冻结正文保持；诊断hook产生于独立native Session并由测试局部绑定严格验证，完整外层Session不被未绑定B04 hook污染。原canonical validator在原反例继续拒绝，任何内层失败传递为外层失败。C24独立入口明确，C23/B04未被自动提升。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest --collect-only -q
pytest -q tests/phase_b/test_b00c25_process_session_binding.py
pytest -q tests/phase_b/test_b04_runtime_cases.py
pytest -q tests/phase_b/test_b00c23_unconsumed_code_final.py tests/phase_b/test_b00c23_trace_consumers.py tests/phase_b/test_b00c24_consumption_failure_source.py tests/phase_b/test_b04_stop_routes.py
pytest -q
python -m compileall -q src tests/phase_b
git diff --check
```

普通 pytest 仅作开发检查；正式执行使用原 Session/run_pytest/validators 的新原生 bounded envelopes，覆盖 exact collection，不能用 unit-only结果替代。先完成所有 child 入口预演再跑昂贵完整集，保存原始日志和每票独立报告。

## Stop Conditions

- 需要更改 production、原 hook/native validator、schema/trace解释、故障 outcome、已有 expected 或未批准文件。
- 原 request不足以证明来源，必须靠猜测/事后重标/伪造Writer或receipt才能通过。
- 原144的其他失败需要放宽断言或扩展语义；不将潜在失败默认为已解决。
- 需要过滤失败、扩大timeout/exclusion或更改owners；资源不足且无已授权安全替代。

## Required Documentation Updates

- 本票独立completion/source contract；C24/C23/B04追加实际结果和独立接续责任。
- 当前状态、文档/Phase B/纠偏/completion索引、Verification Guide；必要时Decision Log。
- 保存执行前快照、冻结正文摘要、验收输入和文档交付manifest；stale links、scope和diff检查。根README早期ready条目保留历史，新增准确当前入口。
