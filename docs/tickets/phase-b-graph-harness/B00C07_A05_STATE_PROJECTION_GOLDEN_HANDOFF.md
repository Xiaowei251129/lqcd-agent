---
ticket_id: B00C07
phase: phase-b-graph-harness
status: review
type: corrective-contract
depends_on: [B00, B01, B02, B00C05, B00C06]
---

# 明确 A05 状态投影的兼容边界与 B03 Golden 同步授权

## Goal

在不修改 A05 合同、旧格式或 trace normalization 语义的前提下，明确 B03 实现既定 canonical state projection 时允许同步的前置语义轨迹范围。原 B03 正文保持 `b78c15a` 冻结；本票只形成显式补充授权，实际 production 实现与完整验收仍由原 B03 完成。

本票当前为 review，未批准、未执行。它不把 B03 预算事务、Backend 或状态 adapter 计为已实现。

## Why and Reproduced Boundary

A05 要求 schema 0.4 bounded state 始终显式包含四个 canonical Code paths 及两个独立 scalar；无 current code 时均为 null。Code pointer 对 canonical/legacy producer 使用完整 nullable path-key 集合，另一组 paths 显式为 null。当前 shared `STATE_FIELDS_BY_SLOT["code"]` 只有两个 legacy paths，projection 和多个 registry validator 都消费该常量。

两个只读生产路径探针已经确认：

1. 不改源码和 runtime fingerprint，仅在独立进程临时注入六个 null projection fields，真实 B02 recovery 场景仍可完成，但 7 个 state preimage 和 9 个 event 的派生摘要改变。故此差异不是 fingerprint-only。
2. 直接扩展全局 code path 集合后，既有 legacy fixture 的实际注册 pointer 被拒绝为 `Registered artifact pointer state paths do not match its slot.`；恢复常量后同一对象重新通过。不能全局替换旧格式。

探针位于 `/private/tmp/lqcd-agent-b00c06-3f4x2xhh/` 的 `probe-state-projection.py`、`B03-state-projection-probe.json`、`B03-state-projection-raw.json`、`probe-registry-compat.py` 与 `B03-registry-compat-probe.json`。探针不是新 production 实现。B03 completion 记录长期保留结论与代码位置，临时目录不是新的合同 authority。

B03 Allowed Files 目前只允许 runtime fingerprint 及其派生 head/reference 的前置 golden 同步；新增 nullable 结构不在该范围。B03 Stop Conditions 要求先批准 corrective ticket，不能用 maintenance 或移除 null 字段规避。

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
6. 每条受影响轨迹在两个独立 fresh 根重跑并 exact 相等后离线审定固定 expected。旧版本 normalizer、事件顺序、route/outcome/status/owner/invariant 与 requirement/case 集合保持；禁止在线 actual 回写 expected、忽略新增字段或新增 wildcard。若发现超出上述来源的材料差异，停止审查。

### B02 control-half compatibility boundary

`tests/phase_b/test_external_consumption_control.py::ExternalDomainConsumer` 明确使用普通 A03 synthetic members 与 legacy-shaped state_paths 证明消费顺序；它不是 A05 Backend/Bundle。B03 必须检查这类已有 fixture 与新 projection/registry adapter 的交界，保留其全部原 required nodeids、真实 hooks、outcome、invariants 和控制保护。不得为使旧 fixture 通过而给 canonical B03 validator 添加 bypass，也不得把旧 fixture 的通过计入 B03 canonical coverage。若必要的兼容修复超出本票明确的 nullable projection / field mapping 和原 B03允许范围，须先提供具体差异，不作静默 golden 更新。

## Non-goals

- 本票不编写 src，不提前实现或计数 B03 canonical Backend、预算事务、verification、bundle/Analysis；
- 不改 Phase A、schema 0.4 public contract、旧格式、trace0.1–0.5、case0.3、2199 cases、324 boundaries、28 post-claim 或 131 requirements/owners；
- 不扩大 B03 对 legacy graph、coder、root tests、dependencies、network/provider 的权限；
- 不把 source fingerprint mismatch 转为兼容通过。

## Allowed Files

- 本票：ready 后仅 YAML lifecycle；
- `docs/tickets/completions/B00C07_COMPLETION.md` 及 completion index；
- `B03_COMPLETION.md` 仅追加交接事实，原 B03 ticket 仅 YAML；
- `docs/README.md`、`REPO_CURRENT_STATE.md`、`VERIFICATION_GUIDE.md`、`STATE_SCHEMA.md`、`ARTIFACT_CONTRACTS.md`、`DECISION_LOG.md`、Phase B Overview：仅本次补充授权、未来实现边界和状态。

这里不授权本票修改 runtime/tests/goldens。上述 B03 handoff 是待用户明确批准的原票执行范围补充；实际改动另在 B03 maintenance/completion 留痕。

## Deliverables and Acceptance

- 经审阅的窄范围补充授权与独立完成记录，B03 frozen body hash 保持；
- 两个探针可复现，明确区分空值结构引起的语义变化与 fingerprint 引起的派生变化；
- 明确旧格式 byte preservation、版本分派和 pointer/result/scalar 交叉验证边界，无 nullable shape 自动猜测；
- 文档 links、scope、ticket lifecycle 与 protocol/catalog frozen checks 通过；
- 只在本票完成后恢复原 B03 执行；B03 完成仍需 28 项 construction、645 runtime、全部前置与完整 suite，不因本票交接豁免。

## Required B03 Verification After Handoff

- Canonical/legacy schema 0.4 pointer path set、空 current、注册、失效、结果 scalar 与错误交叉填充的正负检查；
- schema 0.2/0.3 与历史 reader 的原字节对照；旧 0.4 fingerprint mismatch 仍拒绝原地 resume；
- 在同一真实预算/owned prefix 路径验证 reservation → verifier 执行 → settlement → invocation completion/failure，禁止放宽 head fence；
- 完整 old/new golden derivation 审计和双 fresh 根 exact 对照；
- B00/B01/B02 construction 15/11/30 与同 Session B02-owned 1410 保持，之后完成 B03 28/645；完成 B03 后 mapped84/remaining47，Phase B仍未完成。

## Stop Conditions

需要修改 A05 字段/status/member 合同、旧格式、authority/invalidation policy、trace exclusion、owners/cases/exit 门槛或增加其他 golden 差异时停止，不将本票用作通用验收放宽。
