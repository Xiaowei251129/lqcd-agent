---
ticket_id: B00C23
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C16, B00C21, B00C22, B04]
---

# 未消费 Code normal final 的停止来源交接

## Goal

新增显式 `trace 0.11 / proof 0.8`，在尚无 domain Code registration 的合法停止路径中，验证真实 Code task、manifest、dispatch receipt、external result/final 及相关材料的原 producer/Run/Attempt/workspace 来源。新版本复用全部既有来源校验，不改变 wire bytes、生产运行结果、旧 0.1–0.10 的解释或拒绝行为。

B04 是纠偏目标，不要求先 completed。本票完成及独立入口复核后才按原授权恢复 B04 ready；创建 review 不代表批准或实施。B04 保持 blocked，47 construction/144 owned 不由本票代填。

## Why

2026-10-13 B04 接续在原 compiled product graph、ProductCodeHost、Fake Backend、ExternalNormalFinal 和原 `close_run` 复现 A06 必须覆盖的 `terminal_system_stop / normal_terminal_attached_opened_pause`：Code 已有真实 normal safe-stop final，尚未通过原 Resume 消费；trusted `terminal_operator_stop` 由唯一 close owner 结算、终结 Pause、abandon scheduled Code Attempt 并使 Run halted。重复调用返回原结果、Run bytes 不变，没有 Code/Analysis domain registration，也没有第二次 effect。

原显式 0.10 collector/projector 拒绝 `invalid_evidence:a05_reference:missing_source`，缺失实际 final 的 `dispatch_receipt_digest` 来源。仅被动加入真实原 receipt 并声明旧 `receipt` profile 后，仍拒绝 `invalid_input:a05_source:identity`。Receipt wire 只有 producer/workspace 等字段，没有 case_id/run_id/attempt_id；旧 owner derivation 借已注册 Code bundle 绑定这些字段，该合法停止路径没有此 bundle。补写 receipt identity、伪造 Code registration、删去 final reference、改旧 projector 或使用无 source proof 的 phase-only trace 都不能解决此缺口。

执行根 `/private/tmp/lqcd-agent-b04-continuation-20261013-uyn8zmgm` 的 `normal-final-attached-stop-blocker.json`、`attached-final-dual-fresh-final.log` 保存两次真实 fresh 生产结果、两类严格拒绝、完整 raw/原 receipt 与已有 profile 探针。原根分别为 `/private/tmp/lqcd-agent-b04-code-product-6tl_mbtd`、`/private/tmp/lqcd-agent-b04-code-product-2bfnnkwh`；原始 digest 分别保存，不声称 opaque provider 字节或 raw digest 跨根相同。前面私有审查脚本的 record-type/字段及 raw-digest-equality 断言错误另保留，不作为生产阻塞。

本轮 B04 144 个独立工厂的双 fresh 局部复核通过，但未绑定 registry/matrix/native owned；它们不能替代上述必需产品停止路径。当前仍 131 required/84 mapped/47 remaining、B04 owned 0/144，C16/C21/C22 原 completed 保持，不重跑或重写它们的历史来掩盖新缺口。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/tickets/TEMPLATE.md`、`docs/tickets/corrections/README.md`。
- `docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`、`docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`、`docs/REPO_CURRENT_STATE.md`。
- A03/A04/A05/A06/A07 冻结合同及 `CONTROL_PROTOCOL_0_4.json`、`PHASE_B_REQUIREMENT_CATALOG.json`，尤其 stop_route_contract 的全部七组 class/context 和 interrupt outcome total function。
- [B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[维护](../corrections/B04_MAINTENANCE.md)、[实际结果](../completions/B04_COMPLETION.md)；C16/C21/C22 冻结票、来源合同与 completion。
- `tests/phase_b/harness/{trace,a05_trace,ordinary_trace,product_failure_trace,prior_code_evidence_trace,ordinary_publication_prefix_trace}.py`。
- `tests/phase_b/helpers/{control_traces,b04_code_product,b04_stop_routes,ordinary_publication_prefix_sources}.py`。
- 只读 `src/lqcd_agent/code_agent/{schemas,external_operation,subgraph}.py` 与 `src/lqcd_agent/control/{operations,pause,capabilities}.py`，上述 counterexample 原 SQLite、journals、Run 和材料。

## Scope

- 新版本的闭合未消费 Code 来源声明及专用 projector，借真实生产存储验证 owner，复用原 typed/material/wire validators。
- 新显式版本的被动 collector；完整采集实际 receipt/result/seal/change manifest/tool audit/patch/final，按原真实引用闭包决定必需材料和合法 nullable absence。
- 覆盖 normal final 消费前、attached close 后未注册 Code、safe/non-success/late-integrity 与缺少停止维度导致 unavailable 的合法材料状态；不能把 prepared、published、registered、consumed、released 或 terminal closure 混为一类。
- 专用双 fresh fixtures/expected、四消费者 meta、必要 B00 final 接线和文档。
- 将既有 B04 七类停止路由正向测试显式接入新来源版本，保留 helper 的旧默认和 C23 的旧版本严格拒绝反例；仅版本选择与被动来源接线，不扩大 B04 产品实现或 owned 范围。

## Non-goals

- 不修改 production、stop selector、恢复策略、预算/authority、原 Code/receipt/schema/hash contract；不新增领域 artifact slot。
- 不生成 Code registration、Resume consumption、usable bundle、Analysis/Coordinator Transition 或科学接受；不重执行、退款、重复 settlement 或第二次 terminal operation。
- 不完成 B04 剩余产品集成、47/144、B05 exit adapter；不把 meta 算成 B04 owned。
- 不改变旧版本解释、旧 sealed evidence、case IDs/分类、owners、Phase A、冻结票正文或已完成历史；不 commit/push/PR、引入依赖或真实 Backend/provider/network/raw data。

## Allowed Files

- `tests/phase_b/harness/trace.py`：仅显式 0.11 dispatch；旧 0.1–0.10/default 保持。
- 新 `tests/phase_b/harness/unconsumed_code_final_trace.py`：新版本闭合声明、原存储 provenance 校验及投影，继承/组合旧实现，不改旧函数语义。
- `tests/phase_b/helpers/control_traces.py`：仅新增显式 0.11 被动接线，保留旧输出。
- 新 `tests/phase_b/helpers/unconsumed_code_final_sources.py`、新 `tests/phase_b/test_b00c23_unconsumed_code_final.py`、新 `tests/phase_b/test_b00c23_trace_consumers.py`。
- `tests/phase_b/helpers/b04_code_product.py`：仅新增显式 0.11 的被动来源/collector 分支，保留旧版本分支、默认 0.8、原 Fake/产品行为。
- `tests/phase_b/helpers/b04_stop_routes.py`：仅增加显式 trace_version 参数并转交原 collector/Code helper，默认保持 0.10；不改变停止动作、断言、fixture 或运行结果。
- `tests/phase_b/test_b04_stop_routes.py`：仅将七类正向来源验证显式选择 0.11，保留全部七类、双 fresh、原断言和规范化比较；旧 0.10 拒绝由本票专用负向测试保留。不得删除、过滤或改成 expected-failure。
- `tests/phase_b/fixtures/b00c23/`、`tests/phase_b/expected_traces/b00c23/`。
- `tests/phase_b/acceptance_matrix.json`：仅追加 B00 owner、validation_stage=final、原 A07-META-006/A07-META-015 场景；不增加 B04 owned bindings。
- `tests/phase_b/expected_traces/`：仅当前既有 runtime fingerprint 和可证明派生 head/reference 的离线同步，保存 before/after raw、完整 preimages、双 fresh 审计；不得改变 outcome/owner/invariant/材料语义/exclusion，不运行时写 expected。
- 本票 YAML lifecycle；独立 `docs/tickets/completions/B00C23_COMPLETION.md`、`docs/tickets/corrections/B00C23_UNCONSUMED_CODE_FINAL_SOURCE_CONTRACT.md`。
- `docs/{README,REPO_CURRENT_STATE,STATE_SCHEMA,ARTIFACT_CONTRACTS,VERIFICATION_GUIDE,DECISION_LOG}.md`、Phase B Overview、completion/corrections 索引；B04 completion/maintenance 仅追加关联事实，B04 YAML 仅独立入口复核后的 lifecycle。

## Do Not Touch

- 全部 src/、Phase A、generated protocol/catalog、control/Code wire/hash、budget policy、owners、case 分类、registry bindings、旧 validator/projector/obligations/required checks/seals。
- 旧 trace 0.1–0.10/default 的接受/拒绝和旧 sealed evidence；已有 tests/test_*.py、legacy、configs、evaluation、依赖、repository outputs、accepted artifacts、Human 原始记录、secrets。
- 既有 completion/correction 历史、所有冻结票正文；不能把 C23 completed 解释成 B04 completed。

## Requirements

1. **闭合声明及真实 owner。** 新 proof 在原 0.7 必需字段外仅新增闭合 `unconsumed_code_sources`。每份声明固定包含 schema_version、producer_operation_id、producer_snapshot、task_head、manifest_head、core_head、receipt_head、external_result_head、seal_head、change_manifest_head、tool_audit_head、patch_head、final_head、reservation_head、resolution_owner、resolution_operation_id、terminal_operation_id、pause_snapshot、publication_stage；各 head 只引用完整真实源或经合同证明的 null。Snapshot 必须是原 ExternalOperation 及其实际 revision/epoch，不接受 caller 自填 owner 或选择任意历史 producer。Stage 仅 `normal_final_unconsumed`、`closed_without_consumption`、`unavailable_without_consumption`；其差异须改变 normalized 结果。
2. **绑定与引用闭包。** 从原当前 Session 数据库、原 parent control/capability/prestart、immutable task/manifest、producer 对应 Run/Attempt/workspace 及原 final/publication journal 验证 full owner。Receipt producer、task_id/task digest、manifest digest、workspace、原 dispatch phase/receipt bytes exact；原 logical checksum 与完整 wire byte SHA 分开校验。Seal/change/audit/patch/result/final 沿原 wire 引用逐项验证，不将无 owner receipt 补写为新 wire，也不把 owner 暂缺转成忽略字段。引用闭包缺一项拒绝；不得只靠同一字符串或测试 fixture 标签给材料分配 owner。
3. **注册与停止分开。** 未注册 Code 的声明不能冒充 artifact-history registration/current/usable/consumed。验证 normal safe-stop final 与原 single close/cancel/interrupt winner、Pause 原 snapshot/状态、原 reservation、唯一 settlement、actual overage 和 release/closure；external final 的原 normal owner 与后续 terminal close owner 必须各自保留。无安全停止或原 Run authority 不可证明时保留真实 recovery_required/unavailable，不制造 halted/failed/completed。最大费用不是停止证明；typed token/cost unknown 不变零、不触发 maximum。
4. **优先级和幂等。** recoverable/halted/failed/unavailable total function 和 late integrity/overage precedence 仍按原合同；停止后重读 evidence 不执行 effect。Interrupt winner 不能拥有第二 close，原 Resume 已先 claim 的分支必须保留原 normal final 并进入原 ConsumptionFailure tail，不能借本来源声明强行改成新 interrupt/Code failed bundle。
5. **旧规则复用和拒绝。** 真正注册/完成/消费后的 Code、普通 source、failure/Grant、Human、prior Code 与 ordinary prefix 继续走既有全部校验。缺失/篡改/foreign owner/跨 Run/Attempt/workspace/重复声明/孤儿或 future phase/伪造 registration/receipt/closure/settlement/stale Session 拒绝。合法材料变化必须改变 normalized；旧 0.10 对本反例保留原严格拒绝，新规则不回流旧版本。
6. **消费者和身份。** collector、matrix、runtime validator、exit digest 四条路径在同一 current native Session 验证新来源及负向篡改；meta 保持 B00 owner，不计 B04 runtime。所有 raw/journal/root/生产调用资料 fresh 生成；旧 unit-only、旧 Session 和伪造生产 hook 不能提交为本次验收。
7. **集合和前置。** 131/84/47、2199 cases、324 boundaries、28 post-claim、18 B04 boundaries/144、15 exit checks、原 owner 集合保持。最终稳定输入完整 exact suite、legacy325、同 Session 独立 B02 1410/B03 645、fresh 原 CLI construction15/11/30/28 和 final具体47/144/15 通过；不过滤失败、不扩 timeout/exclusion、不 retag 旧 Session。

## Deliverables

- 新显式 projector、被动 collector、独立来源合同、四消费者 meta 和审定 fixtures/expected。
- 双 fresh 反例的实际生产结果、原 wire/owner/prefix、每个来源的审查差异、完整负向及所有专用分支逐项验收索引。
- 独立 completion、最终输入 manifest、冻结正文/scope/owners 核对和独立 B04 接续入口报告。

## Acceptance Criteria

- A1：两个 fresh 根用原产品端口真实复现 normal safe-stop final 未消费后原 close；新 0.11 通过，旧 0.10 继续按原错误拒绝；只读重放、一次 dispatch/settlement、没有 Code/Analysis registration、没有第二 terminal owner。
- A2：至少覆盖未消费前 normal final、attached close、合法 Code non-success、实际完整性/usage overage 优先 failed、每个停止维度缺失时原 unavailable 分支，材料是否存在按实际阶段证明，不合成不存在的 Code/member/返回。
- A3：缺失/篡改/foreign owner/重复/跨 Run-Task-workspace/future phase/伪造 receipt 或 domain registration/重复 settlement/stale Session 全部严格拒绝；合法材料变化产生 exact mismatch。
- A4：四消费者同 Session 逐项通过；在同一个被绑定 trace 上删除/篡改声明均被四消费者拒绝，原 0.1–0.10 正负回归保持。
- A4b：原 B04 七类停止路由正向测试仅显式选择 0.11 后全部双 fresh 通过；三个接线文件的 old/default 输出、生产路径及全部原断言保持。0.10 对未消费 normal final 的原严格拒绝另以本票负向测试证明；不借接线完成 B04 owned 或其他未完成工作。
- A5：完成 Requirements 7 的完整当前输入验证；未执行项不能从 C16/C21/C22 历史或 construction 推断通过。只允许批准的派生摘要同步，语义变化按 Stop。
- A6：独立 B04 入口确认本次已复现 source Stop 消除后恢复 ready。B04 后续必须补齐全部七 stop class/context、post-claim failure/unsafe/fencing、packet/context 四层负例、原 47construction/144owned/full；主 runtime evidence 保留真实 Run source proof，不能仅用 phase-only 摘要代替。其他未来阻塞需实际复核，不能预先保证整票零阻塞。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b00c23_unconsumed_code_final.py tests/phase_b/test_b00c23_trace_consumers.py
pytest --collect-only -q
pytest -q
python -m compileall -q src tests/phase_b
git diff --check
```

实际执行还须保存同最终 Session 的完整 collection、bounded batch envelopes、原 validator 验证与合并结果，独立 owned1410/645、fresh 四张 construction report、15项 exact final 缺口及原命令日志。新证据只能写 fresh `/private/tmp/lqcd-agent-b00c23-*`。

创建阶段仅检查模板/依赖/链接/scope/冻结正文/diff；不实施新版本、不创建虚假 completion、不 commit/push。

## Stop Conditions

- 需要修改 production、Phase A、wire/hash/budget/authority/stop 结果、schema 0.4、case 集合/分类/owners 或扩大 Allowed Files。
- 需要虚构 Code registration/消费/停止/terminal，忽略材料字段、放宽旧 projector、修改 legacy 或旧 expected 的语义来通过。
- 来源无法用真实 production storage/immutable bytes 闭合，或 baseline/full 的语义变化超出批准派生摘要同步。
- 使用历史/重标 Session、phase-only 证据、过滤/skip/xfail、改变 timeout/exclusion 代替要求的验收。
- 发生实际资源不足且无已授权安全替代时保存原始失败，不宣称完整通过。

## Required Documentation Updates

- 独立来源合同与 completion、B04 completion 关联说明；已有记录仅追加。
- Phase B Overview、Docs/completion/corrections Index、Current State、State Schema、Artifact Contracts、Verification Guide；来源合同变动追加 Decision Log。
- stale-documentation/link/scope/frozen-body scan；恢复 B04 只在独立入口通过后更新 YAML lifecycle。
