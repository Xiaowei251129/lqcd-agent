---
ticket_id: B00C07
phase: phase-b-graph-harness
status: completed
type: corrective-contract
depends_on: [B00, B01, B02, B00C05, B00C06]
---

# 明确 A05 状态投影的兼容边界与 B03 Golden 同步授权

## Goal

在不修改 A05 合同、旧格式或 trace normalization 语义的前提下，明确 B03 实现既定 canonical state projection 时允许同步的前置语义轨迹范围。原 B03 正文保持 `b78c15a` 冻结；本票只形成显式补充授权，实际 production 实现与完整验收仍由原 B03 完成。

用户于2026-09-24同意按审阅结论补强并执行交接，随后继续原 B03。补充授权包含下述四个 canonical path 的来源投影修复与 B02 control-half fixture 的具体适配；不把 B03 预算事务、Backend 或状态 adapter 计为已实现。

## Why and Reproduced Boundary

A05 要求 schema 0.4 bounded state 始终显式包含四个 canonical Code paths 及两个独立 scalar；无 current code 时均为 null。Code pointer 对 canonical/legacy producer 使用完整 nullable path-key 集合，另一组 paths 显式为 null。当前 shared `STATE_FIELDS_BY_SLOT["code"]` 只有两个 legacy paths，projection 和多个 registry validator 都消费该常量。

两个只读生产路径探针已经确认：

1. 不改源码和 runtime fingerprint，仅在独立进程临时注入六个 null projection fields，真实 B02 recovery 场景仍可完成，但 7 个 state preimage 和 9 个 event 的派生摘要改变。故此差异不是 fingerprint-only。
2. 直接扩展全局 code path 集合后，既有 legacy fixture 的实际注册 pointer 被拒绝为 `Registered artifact pointer state paths do not match its slot.`；恢复常量后同一对象重新通过。不能全局替换旧格式。

探针位于 `/private/tmp/lqcd-agent-b00c06-3f4x2xhh/` 的 `probe-state-projection.py`、`B03-state-projection-probe.json`、`B03-state-projection-raw.json`、`probe-registry-compat.py` 与 `B03-registry-compat-probe.json`。探针不是新 production 实现。B03 completion 记录长期保留结论与代码位置，临时目录不是新的合同 authority。

B03 Allowed Files 目前只允许 runtime fingerprint 及其派生 head/reference 的前置 golden 同步；新增 nullable 结构不在该范围。B03 Stop Conditions 要求先批准 corrective ticket，不能用 maintenance 或移除 null 字段规避。

复审又确认两项：trace0.5 的 `RUN_PATH_FIELDS` 从 legacy 表取得字段，遗漏四个 canonical paths；原 C06 fixture 仅包含一个相对 result path。双 fresh 根补入完整绝对 paths 后轨迹不同，进程内显式补齐四字段投影后相同。另外真实 B02 fixture 的 execution schema 同为0.4、Attempt kind同为code_agent，却有两项synthetic members及`external/domain adapter` status；不能仅按格式/kind把该fixture当成canonical。复现脚本和报告在 `/private/tmp/lqcd-agent-b00c07-review/`，不算 production 实现或 B03 coverage。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`；
- A03、A04、A05 Bounded State Projection、frozen protocol/catalog；
- 原 B03、B00C06 及其 completion；
- `src/lqcd_agent/artifacts/registry.py`、`src/lqcd_agent/control/projections.py`、`integrity.py`、historical/source readers；
- `docs/STATE_SCHEMA.md`、`ARTIFACT_CONTRACTS.md`、`VERIFICATION_GUIDE.md`；
- 上述两个探针及所有受影响 expected 的真实来源。

## Approved Handoff After Review

本票获批并完成文档交接后，原 B03 在原有 production 范围内实现 A05 既定 projection 和 registry adapter；以下边界作为 B03 的窄补充：

1. 新 schema 0.4 Run 的 bounded state 显式增加 `code_agent_task_path`、`code_agent_result_path`、`code_change_manifest_path`、`code_verification_results_path`、`code_agent_status`、`code_agent_usable`。无 current code 或 invalidation 后均为 null；有 canonical code 时与已验证 result/pointer exact-match。
2. 四个 canonical paths 与两个 legacy paths 组成同一个完整 nullable path 集合；status/usable 是独立 scalar，不塞进只接受路径的表。两种 producer 通过已验证的 execution/runtime 格式和 Attempt kind 明确分派，不能从成员内容猜测或将 legacy 解释成 canonical。
3. 隔离既有 schema 0.2/0.3、历史 artifact/checkpoint/source reader；既有 files 保持原 bytes 与 old schema validation，不原地改写、不自动补字段、不将 old pointer 重解释成 new pointer。旧 0.4 in-place resume 仍要求 exact supported runtime fingerprint；缺失或不匹配 fail closed。历史 read-only replay/Fork 继续遵守 A04。
4. 允许 B03 修改 `control/projections.py` 及 registry 的必要版本分派来实现上述 A05 已冻结目标；不得改变 A03 slot、invalidation、current-selection 或 authority policy。真实 Code Bundle registration/result 交叉验证仍由 B03 交付。
5. 在 B03 原 fingerprint-derived 授权之外，允许同步由上述明确 null fields、schema 0.4 code pointer 完整 nullable path 集合和合法 scalar projection 引起的前置 expected head/reference 变化。每个变化必须提供 old/new raw preimage、字段差异及来源因果，不能只称“hash changed”。
6. 每条受影响轨迹在两个独立 fresh 根重跑并 exact 相等后离线审定固定 expected。旧版本 normalizer、事件顺序、control route/outcome/status/owner/invariant 与 requirement/case 集合保持；领域fixture的唯一材料替换限下节明确的canonical evidence适配，不把它解释为控制结果变化。禁止在线 actual 回写 expected、忽略新增字段或新增 wildcard。若发现超出上述来源的材料差异，停止审查。

### Canonical path provenance repair

- 在原 B03 接续中允许修改 `tests/phase_b/harness/a05_trace.py`：显式列出四个 canonical path fields，不依赖扩展 legacy `STATE_FIELDS_BY_SLOT`。只投影已有来源绑定的 canonical Code pointer、bounded state及其checkpoint副本中的对应路径；验证所属Run/Attempt、registered member映射、canonical绝对路径及当前pointer/result一致性，不能让任意嵌套同名材料字段获得路径排除。
- 允许新增 `tests/phase_b/test_a05_state_path_traces.py`、调整 `helpers/a05_traces.py` 与必要的既有A05 trace测试：完整六个nullable path keys、两个独立scalars、pointer/state/checkpoint一致性；双fresh根正常/timeout对照，foreign Run/Attempt、未注册成员、路径替换、symlink/escape和同名材料字段反例。保留材料差异和原始摘要验证。
- trace0.5/proof0.2 的来源合同保持，旧0.1–0.4实现与既有字节不动。本修复不新增任意exclusion；若修复需改变来源合同，停止。四个C06 A05 goldens仅在完整路径fixture发生上述已授权差异时可离线双根重审；保存旧值、候选与逐字段原因，不在线回写。

### B02 control-half compatibility boundary

`tests/phase_b/test_external_consumption_control.py::ExternalDomainConsumer` 的原synthetic Code payload替换为B03相同closed validators/registry能够验证的canonical `needs_input` evidence：空change manifest、无patch、usable=false、真实fixture base/workspace及seal/audit来源，每个required verification spec显式not_run并给出needs_input理由。它不需要实际verification command，不新增verification budget事件，不把先前的一次aggregate settlement改成宽松计数。合法领域non-success结果与原控制Attempt成功完成相容；不改变原control outcome、正常external final的winner或后续generic route。

适配复用B03 production schema/ingress/registration验证和测试helper，不设is_fake、旧member猜测、synthetic status特判或canonical validator bypass。Runtime schema0.4/Attempt kind相同不再被当作隔离手段。原`external/domain adapter`标签保留在测试说明中，不能继续充当pointer status；pointer status唯一映射为validated result的needs_input。需要补齐的task、manifest、receipt、seal、change、verification、audit、result及其摘要形成可审计材料差异，不能伪造成功verification或真实Backend能力。

具体允许修改 `tests/phase_b/test_external_consumption_control.py`、其 `helpers/process_client.py`、`helpers/control_traces.py`、相关B02 external trace helper及新增canonical fixture helper；仅替换上述材料与必要的初始化接线，保留所有原required nodeids、真实hooks、control outcomes、原控制断言和故障组合。关联B02 goldens允许上述明确的member/path/domain-status变化及其派生head，逐项保存旧新材料映射、双fresh根复核；不增加、删除或重排控制事件，不更改case/owner/coverage集合。Trace0.1–0.4继续验证原控制半边证据，不将其升级为trace0.5或冒充B03 canonical coverage；新增完整canonical证据由B03自己的trace0.5测试验证。

原B02失败adapter对registry损坏、safe/unavailable stop和重启不重派发的断言必须保持。上述fixture适配应在B03 validators具备后进行；若普通旧trace不能表示新canonical fixture所需证据，须先提供具体反例并按Stop Conditions处理，不以省略摘要规避。

## Non-goals

- 本票不编写 src，不提前实现或计数 B03 canonical Backend、预算事务、verification、bundle/Analysis；
- 不改 Phase A、schema 0.4 public contract、旧格式、trace0.1–0.4及trace0.5/proof0.2来源合同、case0.3、2199 cases、324 boundaries、28 post-claim 或 131 requirements/owners；
- 不扩大 B03 对 legacy graph、coder、root tests、dependencies、network/provider 的权限；
- 不把 source fingerprint mismatch 转为兼容通过。

## Allowed Files

- 本票：ready 后仅 YAML lifecycle；
- `docs/tickets/completions/B00C07_COMPLETION.md` 及 completion index；
- `B03_COMPLETION.md` 仅追加交接事实，原 B03 ticket 仅 YAML；
- `docs/README.md`、`REPO_CURRENT_STATE.md`、`VERIFICATION_GUIDE.md`、`STATE_SCHEMA.md`、`ARTIFACT_CONTRACTS.md`、`DECISION_LOG.md`、Phase B Overview：仅本次补充授权、未来实现边界和状态。

这里不授权本票修改 runtime/tests/goldens。本票执行限文档治理；上述获批的 B03 handoff（包括明确列出的harness/fixture/golden文件）作为原票执行范围补充，实际改动在 B03 maintenance/completion 留痕。B03原票的其他Allowed Files与Do Not Touch保持。

## Deliverables and Acceptance

- 经审阅的窄范围补充授权与独立完成记录，B03 frozen body hash 保持；
- 四项审查结论可复现：空值结构与fingerprint变化的区别、legacy全局表兼容反例、canonical绝对路径双根不稳定、同schema/kind的B02 synthetic pointer；临时反例不能替代后续仓库内回归测试；
- 明确旧格式 byte preservation、版本分派和 pointer/result/scalar 交叉验证边界，无 nullable shape 自动猜测；
- 文档 links、scope、ticket lifecycle 与 protocol/catalog frozen checks 通过；
- 只在本票完成后恢复原 B03 执行；B03 完成仍需 28 项 construction、645 runtime、全部前置与完整 suite，不因本票交接豁免。

## Required B03 Verification After Handoff

- Canonical/legacy schema 0.4 pointer path set、空 current、注册、失效、结果 scalar 与错误交叉填充的正负检查；
- trace0.5完整pointer/state/checkpoint双根来源路径正负检查；B02 needs_input fixture适配的旧新材料对照与所有原控制故障测试；
- schema 0.2/0.3 与历史 reader 的原字节对照；旧 0.4 fingerprint mismatch 仍拒绝原地 resume；
- 在同一真实预算/owned prefix 路径验证 reservation → verifier 执行 → settlement → invocation completion/failure，禁止放宽 head fence；
- 完整 old/new golden derivation 审计和双 fresh 根 exact 对照；
- B00/B01/B02 construction 15/11/30 与同 Session B02-owned 1410 保持，之后完成 B03 28/645；完成 B03 后 mapped84/remaining47，Phase B仍未完成。

## Stop Conditions

需要修改 A05 字段/status/member 合同、旧格式、authority/invalidation policy、扩大已明确的来源路径投影、owners/cases/exit 门槛或增加其他 golden 差异时停止，不将本票用作通用验收放宽。预算事务接线属于原B03工作，先验证reservation commit → verifier在writer transaction外执行 → settlement → 同owner completion/failure；不得通过嵌套事务、跳过结算或放宽head fence使探针通过。
