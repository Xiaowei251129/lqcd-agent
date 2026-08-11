# Architecture

## 文档用途

本文只描述当前代码已经实现的架构，并把尚未执行的 `route intent` 和第二阶段缺口单独标明。未来方向不能被理解为已经存在的 graph edge。

当前 runtime 是一个 LangGraph `StateGraph`，包含五个核心 Agent/节点和两个支持节点。它负责组织可审计工作，不是 notebook wrapper，也不是自主科学决策者。

## 当前节点

核心 Agent/节点：

- Method Planner Agent
- Codex Handoff Node
- Analysis Engineer Agent
- Scientific Reviewer Agent
- Decision Coordinator Agent

支持节点：

- Human Approval Gate
- Memory and Report Node

## 当前真实运行路径

当前实现已经把以下模块接入真实 `StateGraph`：

- Method Planner Agent
- Codex Handoff Node
- Analysis Engineer Agent
- Scientific Reviewer Agent
- Decision Coordinator Agent
- Human Approval Gate
- Memory and Report Node

Codex Handoff Node 默认是 file-based handoff：写入或读取 `coder_task_packet.yaml`、`tests_status.json` 和 `code_change_summary.md`。只有显式启用 automatic handoff 时，运行时才可以调用本地 Codex CLI worker。它目前还不是完整的图内 Code Agent。

Human Approval Gate 同样是 file-based：它写 approval packet、读取 `approval_packet/07_human_decision.yaml`，但绝不改写人类决定。默认 Agent 路径是 deterministic；只有传入显式 provider config 时，Method Planner、Scientific Reviewer 和 Decision Coordinator 才调用 provider。

当前入口与主要路线是：

```text
START
  -> Method Planner Agent
  -> if code_needed == true:
       Codex Handoff Node
       -> tests pass: Analysis Engineer Agent
       -> missing/failed handoff result: END with pending or halted status
     else if plan is complete:
       Analysis Engineer Agent
     else if needs_more_info:
       END with pending status
  -> if run_success:
       Scientific Reviewer Agent
       -> Decision Coordinator Agent
     else if failure_type == code:
       -> if retry_count < max_retry: Codex Handoff Node
       -> else: Decision Coordinator Agent
     else:
       Decision Coordinator Agent
  -> if risk_level in high, critical:
       Human Approval Gate
     else:
       Memory and Report Node
  -> END
```

Human Approval Gate 当前路线：

- `approve_with_conditions` -> Memory and Report Node
- `approve_rerun` -> 记录 Analysis Engineer rerun intent，并以 `pending` 停止；当前不会真正恢复执行
- `request_code_change` -> Codex Handoff Node
- `reject_or_hold` -> Memory and Report Node
- no decision -> Memory and Report Node 写 pending memory/report artifacts；accepted memory 继续被阻止

## 已记录但尚未执行的路线意图

以下内容可能出现在 `decision_log.json`、`rerun_target`、`code_fix_requested` 或文档描述中，但不等于完整 runtime transition 已存在：

- 从非 code analysis failure 返回 Method Planner；当前实际保守路线进入 Decision Coordinator。
- `approve_rerun` 后自动返回 Analysis Engineer；当前仅记录意图并停止为 `pending`。
- 通过同一个 checkpoint 自动恢复旧运行；普通 CLI 入口仍初始化新 state，未实现正式 resume protocol。
- reviewer/coordinator 触发任意多轮闭环；当前只存在有限的 code retry 与 human decision 路线。
- 多 Agent fan-out、并行 reducer 或 attempt namespace；当前没有正式实现。

这些差距必须由 [Phase A](tickets/phase-a-control-contracts/OVERVIEW.md) 逐项明确合同，再由 Phase B harness 验证。A01 已确认逻辑路线合同，但不得仅修改本文或流程图就把目标边视为现有 runtime 能力。

## A01 已确认的目标控制合同（尚未实现）

[A01 Transition Matrix](tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md) 已确认第二阶段的逻辑路线白名单。它是 A02–A07 和 Phase B 的实现约束，不改变上一节所述当前真实运行路径。

目标控制原则是“分布式结构化诊断、Decision Coordinator 集中回退决策”：

- 正常成功路径仍可按 Planner -> Code/Analysis -> Reviewer -> Coordinator 前进；
- 普通 Agent 只报告结构化 outcome、诊断证据和候选修复，不直接控制 graph-level 回退；
- 所有 re-review、rerun、code fix 和 replan 由 Decision Coordinator 根据受影响层级派发；
- low/medium risk 只有在诊断唯一且预算可用时才能自动循环；
- high/critical、诊断歧义、重复相同 failure fingerprint 或预算耗尽必须进入 Human Gate；
- Human Gate 统一处理 clarification、approval 和 external action，进出只连接 Decision Coordinator；
- Memory and Report 保持 terminal sink，不能重新发起循环。

目标逻辑拓扑是：

```text
START -> Method Planner
Method Planner -> Analysis Engineer | Code Agent | Decision Coordinator
Code Agent -> Analysis Engineer | Decision Coordinator
Analysis Engineer -> Scientific Reviewer | Decision Coordinator
Scientific Reviewer -> Decision Coordinator
Decision Coordinator -> Scientific Reviewer | Analysis Engineer | Code Agent
                      | Method Planner | Human Gate | Memory and Report
Human Gate -> Decision Coordinator
Memory and Report -> END
```

四个回退目标分别表示：重新审查相同 analysis、在相同 plan/code 下重新分析、修复实现、重新规划方法。候选目标冲突或无法唯一归因时不得默认选择最深回退，必须进入 Human Gate。

这里的 `Code Agent` 是 A05 将定义的 graph-managed 接口，不是把当前 Codex Handoff 直接改名。Run/Cycle/Attempt identity、artifact invalidation、PAUSE/resume、Code Agent wire contract 和具体预算仍分别由 A02–A06 定义；在这些合同和 Phase B harness 完成前，目标闭环不得接入 runtime。

## Checkpoint 与上下文边界

Checkpointing 与 LLM context 是两个不同问题：

- local CLI 使用 SQLite checkpoint，unit/smoke tests 使用 `MemorySaver`；
- checkpoint database 位于 `<output_root>/<case_id>/<run_id>/checkpoints/`；
- 同一 `case_id` 和 `run_id` 的 `checkpoint_thread_id` 必须稳定；
- `graph_state.json` 在重要节点完成和 route decision 后写出；
- LLM 只能收到挑选后的 state fields 与 bounded artifact summaries；
- routing 不能依赖被截断或概括后的自由文本。

A01 进一步确认：完整 `event_log`、route trace 和 checkpoint state 只用于 runtime、审计和 UI，不直接注入 Agent prompt。目标工作 Agent 只读取 scoped current context、typed remediation packet、直接父 attempt 和与当前问题相关的 bounded attempt history；Decision Coordinator 读取 bounded global execution summary。跨 Run 经验必须经过测试或人类确认后才能进入 curated knowledge，Agent 不能从单次经历直接改写长期规则或 routing policy。

当前 checkpoint persistence 不应被误称为完整 pause/resume。正式恢复语义由 [A04](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md) 讨论。

## Command 边界

运行时只允许 allowlisted mock、test、smoke 和 internal statistical benchmark commands。Golden Demo 使用 `mock:write_golden_example_matrix_elements`；Phase 10C generated cases 使用 exact-allowlisted `analysis:run_synthetic_benchmark:<scenario_path>`。每次执行必须在 manifest 中记录 command、working directory、return code、timeout、stdout/stderr summary 和 output paths。

## Output 边界

实际运行 artifacts 写入 `<output_root>/<case_id>/<run_id>/`。仓库内 `outputs/` 是被忽略的实际运行目录，不是 reference-output 目录。curated evaluation baseline 位于 `evaluation/reference_outputs/`，expected behavior 位于 `evaluation/expected_behavior/`。

没有 `--run-id` 时 CLI 生成 timestamp run id；显式 run id 指向已有完成/决策 artifacts 时，CLI 拒绝复用目录。resume 和 force overwrite 仍未获批准。

## Provider 边界

默认 provider 行为 deterministic 且不联网。显式 `llm_provider_config_path` 或 CLI `--llm-provider-config` 才启用 provider-backed structured output。输出必须通过 strict JSON schema validation 后才能写 artifact 或影响 routing；失败时只允许通过保守结构化字段路由。Phase 10D 会把非 secret request/response audit records 写到 run-local `llm_calls/`，并登记在 manifest 和 final report。

Scientific Reviewer 和 Decision Coordinator 只向 provider 发送 bounded artifact summaries，不发送 raw numeric data。Decision Coordinator 先计算 local deterministic risk；provider 可以增加 structured reasoning，但不能把 high/critical local evidence、severe warning、failed run 或 unusable artifact 降为 low-risk accepted memory。若 provider 低于 local floor，`decision_log.json` 记录 `provider_safety_floor`，并走保守路线。

Local console 可发现 YAML/JSON cases、预览分析路线、选择已配置 provider，并在没有显式 opt-in 环境变量时阻止 live provider。默认 output root 是仓库内被忽略的 `outputs/`。

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [State Schema](STATE_SCHEMA.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
