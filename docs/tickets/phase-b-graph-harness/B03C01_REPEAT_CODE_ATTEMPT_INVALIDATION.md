---
ticket_id: B03C01
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B01, B02, B03, B00C07, B00C08, B00C09]
---

# 修正同一 Run 内重复 Code Attempt 的失效来源

## Goal

使 schema 0.4 Run 中已有 canonical Code Bundle 时，B02 `advance_run` 安排下一次 `code_agent` Attempt 能按既有 A03 target-layer 规则清除旧 Code/downstream current，并在 scheduled Attempt 中冻结与该清除集合一致的 prior artifact IDs。修复后由 B03 继续证明独立 workspace、不可变旧成员和新 Attempt/producer；本票不代替 B03 的 28/645 验收。

`depends_on: B03` 指向被纠偏的原票，不要求当前 blocked 的 B03 先完成。沿用用户对 B03 工作的“不提交、不推送”边界；若获批准，本票和 B03 的执行结果先保留在工作树，并在 completion 中如实记录未形成 committed snapshot。

## Why

真实 Fake Backend、normal-final、trusted Code consumer 和 A03 registry 已产生 status `needs_input` 的 canonical current Code Bundle。在同一 Run 中使用 B02 public `advance_run` 与 `code_agent` target adapter 安排第二个 Code Attempt，`AdvanceOperations._snapshot` 生成的 `Attempt.scheduled.input_references.current_artifact_ids` 固定为空，同时写入清除旧 Code pointer 的 `current_cleared` event。A03 registry 从 scheduled input refs 反向验证 required-clear map，因此在 `transition_committed` 后拒绝这个合法 A05 多 Attempt 前缀，原 advance 最终为 `failed / terminal_closure=unavailable`。

复现的原始 ledger、artifact history/index 和摘要在 `/private/tmp/lqcd-agent-b03-repeat-code-review-an23397g/`。其中第二个 Attempt 是 `attempt_000003`，其 scheduled input refs 为 `{}`；同一目标的 `current_cleared` 精确记录旧 `code` artifact。该反例不经过 B04 产品图、真实 Backend、provider 或网络。冻结 [A03失效合同](../phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md)要求 code target 清除旧 code/downstream current 并保留历史；[A05-CODE-019](../phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)要求多次 Code Attempt 独立且旧 artifact 不再 current。

B03 Allowed Files 对 `control/` 仅授权 ExternalOperation、资源、watchdog/settlement 和 typed target preparation integration，对 `artifacts/registry.py` 仅授权 A05 Code 注册 adapter；修正通用 `AdvanceOperations.advance/_snapshot` 的来源绑定与 scheduled provenance 超出该范围，不能记作 B03 maintenance 或删除 A03 反向验证。

`runtime_fingerprint()` 对整个 `src/lqcd_agent/**/*.py` 计算 application build 摘要，因此本票即使只改 `operations.py` 中的重复 Code 分支，也会改变其他 schema 0.4 Run 的源码指纹及派生 head。此前跨越源码修改的 B03 探索性运行出现 15 项待审 exact trace 失败；这些旧路径的最终 expected 必须按 B03 原授权在完整 production 稳定后审定，本票不能要求先更新它们才能解除重复 Code 阻塞。

探索性运行另有 10 项 B02 `continue_execution.*.integrity_conflict` exact 失败；现已逐项复现并确认全组存在非摘要差异：B03 工作树的 `ConsumptionFailure.continue_failure` 在已判定 Run authority unavailable 后仍无条件解析被故障注入破坏的 execution ledger，使恢复停在 `consumption_failure_stop_verified` 或 `consumption_failure_classified`，缺少冻结的后续分类/unavailable阶段。该回归与本票的 scheduled prior IDs 无关；须在 B03 原 control failure/settlement 范围内按 maintenance 路径恢复，不能纳入本票 `operations.py` 修复或以 expected 更新掩盖。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/tickets/corrections/README.md`；
- A03、A04、A05、A07 冻结合同，B02 与 B03 票及 B03 maintenance/completion；
- `src/lqcd_agent/control/operations.py` 的 `AdvanceOperations.advance/_snapshot`、`src/lqcd_agent/control/integrity.py` 的 `validate_run_root`、`src/lqcd_agent/artifacts/registry.py` 的 `_validate_history` 与 `_slots_for_target`；
- `/private/tmp/lqcd-agent-b03-repeat-code-review-an23397g/report.json` 及并列原始文件。

## Scope

- 仅在 schema 0.4 的下一目标为 `code_agent`、且源 index 的 current `code` 为已验证 canonical Code pointer 时，冻结计划创建时、失效前的 A03 required-clear 集合，并将对应 slot→prior artifact ID 写入新 `Attempt.scheduled.input_references.current_artifact_ids`。canonical Code pointer 以现有 validator 接受、`attempt_kind=code_agent` 的 current `code` 为准；集合覆盖 A03 对该 target 要求清除的每个 populated Code/downstream slot，不包含空 slot。该集合必须与同一计划的 `current_cleared` event、目标 Attempt 和 inbound Transition exact 一致；不从清除后的 index 重建。
- 在同一 advance reservation 事务中先读取原始 `artifact_index.json` bytes，再调用 `validate_run_root`；校验后将原始 bytes 与当前文件重读结果比较，并将其解析值的 `current`、`revision`、`execution_head`、`artifact_head` 分别与验证所得 state 的 `current_artifacts`、`artifact_event_index`、`execution_head`、`artifact_head` 比较。route view 的 `selected_code`、target preparation 与 `_snapshot` 的失效集合均使用这个已绑定的解析值；route admission 后在 reservation callback 生成冻结计划前后再次核对原始 bytes。任一次不一致都在计划提交前拒绝，不回退到未验证的新 index，也不调用 Backend。
- 保留原 B02 操作身份、阶段、fence、故障收尾和 A03 registry 反向验证。Restart 只 materialize 已冻结字节，不重算输入集合或重新执行失效。
- 增加同一 Run 两次 canonical Code Attempt 的真实 Fake/Host 正负回归，包含 Code 及 downstream slot 同时 populated 的失效集合；证明第一次成员历史保持原字节、第二次 producer/workspace/Attempt 不复用、旧 Code/downstream 不再 current、第二次合法 target 可继续 pre-start；在 scheduled、clear、Transition 与后续验证切点覆盖崩溃恢复、双进程竞争和篡改拒绝。另覆盖首次 Code、无 current Code、非 canonical/旧格式 Code pointer、验证与 reservation 间的 index bytes 更换，以及缺失、额外、错 slot/ID 的 scheduled prior IDs。
- 本票固定新增重复 Code 路径的 source-bound exact trace；对其他路径由源码指纹产生的 raw 差异保存前后来源和候选原因，不更新旧 expected。B03 最终 golden 仍须按原票及 B00C07/C08 在 production 稳定后逐项、双 fresh 根审定。

## Non-goals

- 不改变 A03 slot/invalidation policy、registry 的 required-clear 判定、A05 public schema/status/member、B02 protocol phase、B00 catalog/case/owner/exit 集合。
- 不把 B04 产品 route 接入默认图，不修改 legacy coder/format，也不使 legacy Code pointer 自动成为 canonical Code Bundle。
- 不修改 `ConsumptionFailure` 的 B02 integrity-conflict 收尾；已确认的 B03 局部回归由原 B03 maintenance 处理。本票的宽回归诊断须将它与来源摘要差异分开报告。
- 不借本票宣称 B03 28 construction、645 runtime 或 Phase B 完成。

## Allowed Files

- 本票在 `ready` 后只改 YAML lifecycle metadata；新增独立 completion record `docs/tickets/completions/B03C01_COMPLETION.md`，仅向 completions/corrections index 追加本票链接；
- `src/lqcd_agent/control/operations.py`：仅限 `AdvanceOperations.advance` 的原始 index bytes 读取、验证、route view 与 reservation 绑定，以及 `_snapshot` 对重复 canonical Code target 的 scheduled input provenance；不改变其他 operation、既有计划/恢复阶段或 A03 规则；
- `tests/phase_b/test_b03_repeat_code_attempts.py` 及既有 `test_b03_analysis_handoff.py`、`test_external_consumption_control.py`、`test_b03_reservation_boundaries.py`：限复用现行 Fake/Code fixtures、正负/故障/进程证据；
- `tests/phase_b/expected_traces/` 与关联 fixture：仅限新增重复 Code 路径，按 B03/B00C07/C08 的 raw preimage、来源和双根规则处理；既有 B02/A05 expected 留待 B03 production 稳定后的最终审定；
- `docs/tickets/phase-b-graph-harness/B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md`：仅在纠偏完成后更新 YAML lifecycle metadata；
- `docs/README.md`、`docs/REPO_CURRENT_STATE.md`、`docs/tickets/phase-b-graph-harness/OVERVIEW.md`、`docs/ARCHITECTURE.md`、`docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`、`docs/EVALS_AND_OBSERVABILITY.md`、`docs/VERIFICATION_GUIDE.md`、`docs/DECISION_LOG.md`：仅同步已证实的当前状态或本票引入的 provenance 语义。

## Do Not Touch

Phase A 冻结正文、Control Protocol、requirement catalog、B00–B03 冻结正文、B04/B05 正文、A03 registry policy/validator、legacy graph/coder/default CLI、已完成记录历史、依赖、配置、真实 Backend/provider/network、raw/accepted/secrets 和 control repository Git state。

## Requirements

- `scheduled.input_references.current_artifact_ids` 只能引用本次验证后冻结的原 index 中的 prior IDs，且仅含 A03 对此 target 实际要求清除的 populated slots；与同一 Transition/target 的 `current_cleared` 集合精确一致，不接受 caller/Backend 输入或验证后的不同 index bytes。source bytes、验证 state、route view、target preparation 和 reservation snapshot 必须按上述同一次绑定规则对应；不同 bytes 即使解析出相同 current/head 也拒绝。
- 首次 Code target、无现行 canonical Code pointer 的路径和现有 B00–B02/legacy 输入保持原 scheduled 字段规则与控制结果；不扩大现有 target kind 或接受非法 route。源码指纹及其派生摘要的变化仍按 B03/B00C07/C08 的 golden 审定规则单独核验，不能声称这些 raw bytes 不变。
- A03 完整反向验证继续拒绝缺失、额外、错 slot、错 prior ID、错 Transition/Attempt 和改写后的 scheduled/clear 证据；验证前后、route admission 中或 reservation callback 期间更换 source index bytes 必须拒绝，不以跳过检查让反例通过。
- 同一 Run 的第二次 canonical Code target 不复用第一次 producer/workspace/成员，旧成员 canonical bytes 保留，旧 Code/downstream current 按 A03 清除；后续 B03 pre-start/Backend 仍由原 authority、预算和 Pause 约束。

## Deliverables

- 最小 scheduled provenance 修复与重复 Code Attempt 回归；
- 独立 completion、原始故障/双进程证据、确有影响的文档同步。

## Acceptance Criteria

- 现有复现从 `failed / unavailable` 转为同一 Run 合法第二个 scheduled Code target；A03 required-clear 反向验证、Code member 历史和新 workspace 隔离同时通过。
- 首次 Code、无 current Code、非 canonical/旧格式 Code、普通 forward、Analysis、Human、legacy 路径保持原字段生成规则、route、outcome 与事件顺序；篡改 scheduled prior IDs 或 clear event 仍 fail closed，崩溃重启不重新推导计划。验证与 reservation 间发生 index bytes 变化时不产生有效计划或 Backend dispatch。任何由源码指纹引出的旧路径 raw 差异必须经原 B03/B00C07/C08 来源与双 fresh 根审定。
- B00/B01/B02 construction 15/11/30 和本票针对的重复 Code 正负/故障/双进程节点通过；B03 原 28/645 目标和全局 `phase_b_complete=false` 保持。新增重复 Code trace 在两个 fresh 根标准化 exact 相等。对既有 B02/A05 exact 失败保存本票前后 raw、字段差异与来源候选；不得借本票覆盖 expected 或把未审定失败声称为通过。Phase B 与全仓探索性回归不得出现未解释的新增 route、outcome、owner、事件顺序或非派生失败；最终旧 golden 和完整 1410/645 回归由 B03 收尾。
- 若实现需要修改 `artifacts/registry.py` 的 A03 validator/policy、改变控制协议/目录、扩大 Allowed Files 或改变旧路径语义，按 Stop Conditions 再审，不以本票放宽。

## Verification

```bash
C01_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b03c01-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b03_repeat_code_attempts.py
pytest -q tests/phase_b/test_external_consumption_control.py tests/phase_b/test_b03_analysis_handoff.py tests/phase_b/test_b03_reservation_boundaries.py
pytest -q tests/phase_b/test_b02_construction.py
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B00 --evidence-dir "$C01_EVIDENCE_DIR/b00-construction" --report "$C01_EVIDENCE_DIR/b00-construction.json"
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B01 --evidence-dir "$C01_EVIDENCE_DIR/b01-construction" --report "$C01_EVIDENCE_DIR/b01-construction.json"
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B02 --evidence-dir "$C01_EVIDENCE_DIR/b02-construction" --report "$C01_EVIDENCE_DIR/b02-construction.json"
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

另运行 `test_b02_runtime_cases.py`、Phase B 和全仓套件作为诊断，逐项比较本票前后的失败集合、raw 来源、route/outcome/owner/事件顺序；将上述已确认的 B03 消费失败尾部回归、未审定 golden 和任何新增失败分别列出。当前失败不是本票通过证据，也不能在本票范围内覆盖 expected。若出现本票造成的新非派生失败，依 Stop Conditions 停止。在新的 `/private/tmp/lqcd-agent-b03c01-*` 根保存原进程/恢复进程、source/index/history 和精确输入摘要。B03 全量同 Session 645 与最终 golden 审定仍归 B03；本票不得以旧通过记录充当本轮证据。

## Stop Conditions

- 必须改变 A03 invalidation policy/validator、A05 public schema、B02 protocol phase 或旧路径语义才能通过；
- 必须触碰未列文件、B04 产品图、legacy 实现或真实 Backend/provider/network；
- scheduled prior IDs 无法在原 advance reservation 中准确冻结，或崩溃恢复需要重算/覆盖已冻结字节；
- 出现不能解释为既有 B03 待审 golden 或本票源码指纹派生的新增 regression，或 golden 差异涉及 route、outcome、owner、事件顺序及其他未授权来源。

## Required Documentation Updates

完成时在独立 completion 记录问题、实际差异、验证及 B03 恢复条件；同步受影响的 current-state/source-of-truth、Overview 与 Docs Index。若政策或架构发生变化，追加 Decision Log；执行 stale-documentation 和链接检查。

## Review Gate Before `ready`

请确认仅授权上述 schema 0.4 重复 canonical Code target 的 scheduled prior-ID 来源修正及同文件 `advance` 的已验证 index bytes 绑定，保持 A03 clear policy/validator 与旧路径语义；确认独立的 B02 消费失败尾部回归归 B03 maintenance，本票完成后 B03 仍须继续原 28/645、旧 golden 和全仓验收。本票仍为 `review`，未获批准前不得修改 `AdvanceOperations.advance/_snapshot`。
