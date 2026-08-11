# Agent Roles and Boundaries

## 全局硬边界

Agent 可以支持规划、执行受限分析、检查、报告与风险分类，但不得：

- 作出最终科学决策；
- 在缺少必要批准时 promote accepted results；
- 修改 `raw_data/` 或伪造证据；
- 用自由文本替代结构化字段进行 routing；
- 把 provider 输出当作可绕过本地安全规则的 authority。

## Method Planner Agent

允许：

- 把用户目标转成 structured physics goal；
- 识别 target observables、required inputs、expected outputs 和 method steps；
- 通过 `code_needed` 表达是否需要 code handoff；
- 生成 `method_plan.json`。

禁止：

- 编写 implementation code；
- 决定 central fit 或最终 systematic uncertainty；
- 虚构 literature 或 data evidence。

## Codex Handoff Node（当前合同）

允许：

- 生成 structured `coder_task_packet.yaml`；
- 读取外部 coding step 生成的 `code_change_summary.md` 和 `tests_status.json`；
- 仅在显式 automatic handoff opt-in 时调用本地 Codex CLI worker；
- 根据 structured test status 和 retry count 路由。

禁止：

- 默认或未经显式 opt-in 调用 Codex；
- 修改 raw data、accepted results、secrets 或 task packet scope 外文件；
- 决定 physics acceptance。

第二阶段计划把该角色演进为图内 Code Agent。A01 已确认它在目标逻辑图中的前进和回退位置，但不批准新权限、输入输出、tool allowlist、budget、retry 或 stop semantics。正式接口与安全边界由 [A05](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md) 定义；在该 ticket 完成前，本节当前合同继续有效。

## Analysis Engineer Agent

允许：

- 运行 allowlisted mock/test/smoke/benchmark commands；
- 验证预期 synthetic artifacts；
- 生成 run results、manifest records 和 failure classifications。

禁止：

- 运行 arbitrary shell command；
- 在政策批准前读取 real raw numeric data；
- 覆盖 previous runs 或 accepted results；
- 接受或拒绝 physics result。

## Scientific Reviewer Agent

允许：

- 检查 structured outputs 中 matrix element 随 `z` 和 `Pz` 的一致性；
- 生成 evidence-based warnings、diagnostics 和 recommended checks；
- 覆盖 correlator、fit 与 matrix-element sections，即使当前 case 只提供部分证据。

禁止：

- 选择最终 central fit；
- 删除或修改 data；
- promote high-risk result；
- 作出 paper-level claim。

## Decision Coordinator Agent

允许：

- 汇总 method、run 与 review artifacts；
- 设置 `risk_level`、`recommended_action` 和 `human_approval_required`；
- 生成带 structured reasons、evidence、next actions 和 route intent 的 `decision_log.json`；
- 把 low/medium risk 送往 reporting，把 high/critical 标记为必须审批；
- 用现有 structured state fields 表达 targeted rerun 和 code-fix recommendation。

禁止：

- 忽略 severe warning；
- 未经人类批准 promote high/critical result；
- 把 medium risk 写成 accepted memory；
- 改写 human decision。

## Human Approval Gate

允许：

- 在 `human_approval_required` 为 true 时生成 approval packet；
- 等待 human decision；
- 按 structured human decision file 路由。

禁止：

- 成为所有常规步骤的 always-on gate；
- 修改 human decision 内容。

当前 `approve_rerun` 只记录 rerun intent 并停止为 `pending`，不代表已经实现自动恢复。

## Memory and Report Node

允许：

- 按 risk 与 approval state 写 accepted、pending 或 rejected memory update；
- 生成 final report 与 evaluation summary。

禁止：

- 删除 historical case；
- 覆盖 human approval record；
- 把 medium/high/critical outcome 静默存为 accepted；
- 在没有有效批准时把 high/critical outcome 存为 accepted。

## A01 已确认的目标控制边界（尚未实现）

A01 确认目标系统采用集中控制、专业诊断的职责划分。以下边界是后续 tickets 和 Phase B 的实现约束，不表示当前 runtime 已经具备这些路线或字段。

所有工作 Agent 允许：

- 对本领域 outcome 产生结构化问题类别、受影响层级、证据引用、retryability、候选 remediation、诊断置信度和 failure fingerprint；
- 在 scoped context 内使用 Coordinator 提供的 remediation packet 和相关 attempt history；
- 提出 `needs_input`、`needs_human` 或候选修复。

所有工作 Agent 禁止：

- 直接选择 graph-level re-review、rerun、code fix 或 replan；
- 根据完整 `event_log`、自由文本或未验证 provider 建议自行改变路线；
- 从一次未审核经历直接改写长期 memory、skills 或 routing policy。

Decision Coordinator 在目标合同中拥有唯一 graph-level 回退 authority：

- 根据受影响层级选择 Scientific Reviewer、Analysis Engineer、Code Agent 或 Method Planner；
- 只有 low/medium、诊断唯一且预算可用时才能自动派发回退；
- high/critical、诊断歧义、重复 failure fingerprint 或预算耗尽时必须进入 Human Gate；
- 为目标 Agent 形成 typed remediation packet，并保留 evidence、parent attempt、budget 和 authorization references；
- 不得把“来源 Agent”直接等同于“回退目标”，也不得默认采用失效范围最大的 replan。

Human Gate 在目标合同中是统一的人类交互边界：

- 处理 clarification、approval 和 external action；
- 只接收 Decision Coordinator 的请求，只把 valid response 返回 Decision Coordinator；
- 无有效输入时保持逻辑 `PAUSE`，不得直接进入工作 Agent 或 Memory and Report；
- human response 必须 single-use；继续循环时每次只授权一个新的有限 execution window。

工作 Agent 的多次 attempt 记录属于 append-only execution history，不是 Agent 可自主写入的长期记忆。Coordinator 可以使用 bounded global execution summary；其他 Agent 只能读取与当前目标相关的 scoped history。跨 Run 经验只有经过测试或人类确认后才能进入 curated knowledge/few-shot。

## 能力增强原则

未来 RAG、physics corpus、tool use 或更强 provider 可以增强判断，但不能改变上述 ownership boundary。知识增强必须记录来源、版本与引用，并通过 capability evaluation 证明收益；它不能直接扩大 Agent 的写权限或科学裁决权。

## Related Documents

- [Architecture](ARCHITECTURE.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Phase A: Control Contracts](tickets/phase-a-control-contracts/OVERVIEW.md)
