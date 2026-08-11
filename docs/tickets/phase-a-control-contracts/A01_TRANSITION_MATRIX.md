---
ticket_id: A01
phase: phase-a-control-contracts
status: completed
type: design
depends_on: []
---

# 定义允许路线矩阵

## Goal

确认当前节点之间哪些路线是允许、禁止、已实现、仅记录 intent 或计划新增的，并为每条允许路线定义触发证据和安全边界。

## Why

当前图的声明边、routing 实际返回值和文档中的回退意图没有完全统一。后续 attempt、resume 和 harness 都依赖这份合同。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/ARCHITECTURE.md`
- `docs/STATE_SCHEMA.md`
- `docs/NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md`
- `src/lqcd_agent/graph/analysis_graph.py`
- `src/lqcd_agent/graph/routing.py`

## Scope

- 盘点当前声明和实际可达边；
- 区分 current、intent-only、proposed 和 forbidden；
- 为允许路线定义触发者、结构化条件、前置 artifacts 和停止条件；
- 确认由 Decision Coordinator 统一拥有 graph-level 回退决策；
- 为后续 identity、artifact、resume、Code Agent、budget 和 harness tickets 提供输入。

## Non-goals

- 不修改 routing 或 graph code；
- 不决定 Run/Cycle/Attempt schema；
- 不实现 rerun 或 resume。

## Allowed Files

- 本 ticket 文件；
- 经讨论明确批准的核心文档。
- 用户为 stale-documentation consistency 明确批准的 `phase-a-control-contracts/OVERVIEW.md` 和 `docs/VERIFICATION_GUIDE.md`。

## Do Not Touch

- `src/`
- `tests/`
- `configs/`
- `raw_data/`
- `outputs/`

## Requirements

- 不把图上技术可连的边自动视为产品允许路线；
- 路由条件必须来自结构化状态或 artifacts；
- 普通 Agent 只报告结构化结果、诊断证据和候选修复，不直接控制 graph-level 回退；
- Decision Coordinator 根据受影响层级统一选择 re-review、rerun、code fix 或 replan；
- low/medium risk 只有在诊断唯一且预算可用时才允许自动回退；
- high/critical risk、诊断歧义、重复相同失败或预算耗尽必须进入 Human Gate；
- Human Gate 和 deterministic risk floor 不能被绕过；
- 所有允许循环必须有有限停止条件，但具体预算值由 A06 定义；
- 完整 `event_log` 只用于审计、UI 和 runtime，不直接作为 Agent prompt context。

## 术语与分类

- `current`：当前 graph 中已声明、router 可选择，并可由正常节点输出状态实际到达；
- `declared-only`：graph 声明了目标，但 router 不会选择；
- `intent-only`：state、artifact 或文档记录了后续方向，但当前 runtime 不执行；
- `proposed`：本 ticket 确认为目标合同，但需要后续 ticket 才能实现；
- `forbidden`：即使技术上可连接，也不属于产品允许路线；
- `PAUSE`：逻辑执行状态，不预先规定它最终实现为 LangGraph interrupt、显式 runner resume 或其他机制。

本 ticket 中的 `code_agent` 指未来 graph-managed Code Agent 接口。当前实现中的 `codex_handoff` 只用于盘点现状；A01 不把现有 file-based handoff 行为误写成最终 Code Agent 合同。

## 当前实现盘点

当前 `analysis_graph.py` 共声明 19 条包含 `START` / `END` 的边。其中 17 条可由固定边或 router 源码返回；结合各节点实际生成的状态，正常完整 trajectory 中约 16 条可达。

| 来源 | 当前 declared targets | router 可能返回 | 正常状态下实际可达 | 差异 |
| --- | --- | --- | --- | --- |
| `START` | `method_planner` | 固定边 | `method_planner` | 无 |
| `method_planner` | `analysis_engineer`, `codex_handoff`, `decision_coordinator`, `END` | `analysis_engineer`, `codex_handoff`, `END` | 同 router | `decision_coordinator` 是 declared-only |
| `codex_handoff` | `analysis_engineer`, `END` | 两者 | 两者 | 当前只表达 file-based handoff success 或 safe stop |
| `analysis_engineer` | `scientific_reviewer`, `codex_handoff`, `method_planner`, `decision_coordinator` | 除 `method_planner` 外 | 同 router | `method_planner` 是 declared-only；code failure 当前可直接回 `codex_handoff` |
| `scientific_reviewer` | `decision_coordinator` | 固定边 | `decision_coordinator` | reviewer failure 也进入 Coordinator |
| `decision_coordinator` | `human_approval_gate`, `memory_report` | 两者 | 两者 | rerun/code-fix 只写 `proposed_follow_up_route` |
| `human_approval_gate` | `analysis_engineer`, `codex_handoff`, `memory_report`, `END` | 四者 | `codex_handoff`, `memory_report`, `END` | `approve_rerun` 当前实际 `END`；`analysis_engineer` 只是正常流程不可达的 router 分支 |
| `memory_report` | `END` | 固定边 | `END` | 无 |

当前 intent-only 路线包括：

- Decision Coordinator 通过 `rerun_requested` / `rerun_target` 提议 `analysis_engineer`；
- Decision Coordinator 通过 `code_fix_requested` 提议 `codex_handoff`；
- Human Gate 的 `approve_rerun` 记录 `analysis_engineer`，但以 `pending` 停止；
- Human Gate 等待或收到 invalid decision 时记录返回 gate 的意图，但尚无正式 resume protocol；
- 文档描述非 code failure 可能 replan，但当前 Analysis Engineer 实际进入 Decision Coordinator。

## 已确认的控制原则

### 1. 集中回退决策，分布式结构化诊断

所有 graph-level re-review、rerun、code fix 和 replan 都由 Decision Coordinator 派发。普通 Agent 对本领域的现象、证据和候选修复负责，但不能直接选择语义回退目标。

Coordinator 不根据“哪个 Agent 报错”机械路由，而根据“必须改变哪一层”选择目标：

- analysis 不变，只需重新审查：`scientific_reviewer`；
- plan 和 code 仍有效，需要调整参数或重新执行：`analysis_engineer`；
- 实现、测试或 executable behavior 需要修复：`code_agent`；
- 方法假设、输入合同或分析步骤需要改变：`method_planner`。

候选目标冲突、证据不足或无法唯一归因时，Coordinator 不得默认选择最深回退，必须进入 Human Gate。

### 2. 正常前进与 graph-level 回退分离

以下属于正常前进，不需要经过 Coordinator：

- Method Planner 成功后进入 Analysis Engineer；
- Method Planner 明确发现实现缺口后进入 Code Agent；
- Code Agent 完成且验证通过后进入 Analysis Engineer；
- Analysis Engineer 成功后进入 Scientific Reviewer。

节点内部可以进行后续合同明确允许的、幂等且有限的工具级重试，但任何创建新 attempt、改变 artifact validity 或跳回其他工作 Agent 的行为都属于 graph-level 回退，必须经过 Coordinator。

### 3. Human Gate 只与 Coordinator 交互

Human Gate 统一处理三类请求：

- `clarification`：补充 Planner、Code Agent 或其他节点所需输入；
- `approval`：批准、附条件批准、拒绝或 hold 高影响动作；
- `external_action`：请求人类完成 graph 无权自动完成的外部动作。

工作 Agent 不直接进入或离开 Human Gate。Agent 先把 structured `needs_input` 或 `needs_human` outcome 交给 Coordinator；Coordinator 创建 human request。Human Gate 收到有效响应后只返回 Coordinator，再由 Coordinator 验证响应并派发目标。

没有有效输入时逻辑状态为 `PAUSE`。暂停期间必须继续保留 pending audit/report 能力，且不得写 accepted memory；具体 interrupt、resume 和 pending-report 实现由 A04 定义。

人类批准继续循环时，每次只增加一个新的有限 execution window。Human decision 必须 single-use；再次耗尽预算时重新进入 Human Gate，不能把一次批准解释为无限循环授权。

## 目标 Transition Matrix

| 来源 | 目标 | 类型 | 最低触发证据 | Guard / 停止条件 |
| --- | --- | --- | --- | --- |
| `START` | `method_planner` | current forward | 已验证的 run input identity | 无 |
| `method_planner` | `analysis_engineer` | current forward | usable method plan，且不需要新增实现 | plan validation 必须通过 |
| `method_planner` | `code_agent` | target forward | usable method plan、明确 implementation gap 和 scoped code task | Code Agent security policy 必须允许 |
| `method_planner` | `decision_coordinator` | proposed control | structured `needs_input`、planning failure 或 `needs_human` outcome | Coordinator 只能请求澄清、报告或升级，不得伪造缺失 plan |
| `code_agent` | `analysis_engineer` | target forward | attempt-matched code result、required verification passed、可用 revision/patch evidence | tests passed 不等于 scientific acceptance |
| `code_agent` | `decision_coordinator` | proposed control | failed、no-change、needs-input、needs-human、budget-exhausted 或 invalid outcome | 不允许 Code Agent 自行选择 replan/rerun |
| `analysis_engineer` | `scientific_reviewer` | current forward | `run_success=true` 和可审查 analysis artifacts | 无成功 artifact 时禁止继续 |
| `analysis_engineer` | `decision_coordinator` | current/target control | 任意非成功 structured outcome | 删除直接 code-fix/replan authority |
| `scientific_reviewer` | `decision_coordinator` | current control | review outcome，包括 warnings、failure 或 unusable evidence | Reviewer 不直接控制回退 |
| `decision_coordinator` | `scientific_reviewer` | proposed re-review | analysis 保持有效，review 需要重做，诊断唯一 | low/medium、review budget 可用，否则 Gate |
| `decision_coordinator` | `analysis_engineer` | proposed rerun | plan/code 有效，存在 targeted rerun spec 和证据 | low/medium、analysis budget 可用，否则 Gate |
| `decision_coordinator` | `code_agent` | proposed code fix | implementation/test failure evidence 和 scoped remediation | low/medium、code budget 与 security policy 允许，否则 Gate |
| `decision_coordinator` | `method_planner` | proposed replan | plan/method/input contract 需要改变的结构化证据 | low/medium、replan budget 可用；扩大科学或安全范围时 Gate |
| `decision_coordinator` | `human_gate` | target escalation | high/critical、诊断歧义、重复 fingerprint、预算耗尽、需要澄清/批准/外部动作 | Human Gate 不得被 risk floor 绕过 |
| `human_gate` | `decision_coordinator` | target response | identity-matched、valid、single-use human response | pending/invalid response 保持 PAUSE |
| `decision_coordinator` | `memory_report` | current/target terminal | accept、reject、hold、pending report 或不可继续的已分类结果 | accepted-memory policy 继续生效 |
| `memory_report` | `END` | current terminal | report/memory artifacts 已按 policy 写入 | 禁止重新发起循环 |

## 四层回退语义

| 回退目标 | 保持有效 | 新执行身份 | 原则上的下游影响 |
| --- | --- | --- | --- |
| `scientific_reviewer` | 当前 plan、code 和 analysis | 新 review attempt | 旧 review 与 decision 不再是 current |
| `analysis_engineer` | 当前 plan 和 code | 新 analysis attempt | 旧 analysis、review 与 decision 不再是 current |
| `code_agent` | 当前批准的目标和允许 scope | 新 code attempt | 旧 code result 及下游 analysis、review、decision 不再是 current |
| `method_planner` | Run-level user goal 和不可变政策 | 新 cycle / plan attempt | 旧 plan 及全部下游结果不再是 current |

这里的“新执行身份”和“失效”只是 A01 对后续合同的约束，不批准具体 state fields、目录或覆盖行为。A02 定义 identity，A03 定义 versioning、current pointer 和 invalidation。

## Diagnostic 与 Remediation Contract

每个 Agent outcome 必须能够结构化表达：

- outcome status 和问题类别；
- 受影响层级；
- evidence/artifact references；
- retryability；
- 一个或多个 candidate remediation；
- diagnosis confidence；
- failure fingerprint；
- 是否需要补充输入、人类批准或外部动作。

A01 只确认这些语义要求，不冻结字段名称或 artifact schema。A02、A05 和 A06 必须把它们转成可验证合同。

Coordinator 派发回退时必须形成 typed remediation packet，至少说明目标、问题、证据、约束、成功条件、相关父 attempt、预算状态和 human authorization reference。目标 Agent 只能执行 packet 授权的工作，不能把 candidate remediation 自行扩大为其他 graph transition。

## Context 与 Memory Boundary

- 完整 `event_log`、route trace 和 checkpoint state 供 runtime、审计和 UI 使用，不直接注入 Agent prompt；
- Coordinator 读取 bounded global execution summary，包括 current artifact pointers、route history、budget、failure fingerprints 和 human decisions；
- 工作 Agent 只读取 scoped current context、typed remediation packet、直接父 attempt，以及与当前 fingerprint 或目标相关的 bounded attempt history；
- 每个 Agent 的 attempt history append-only 保存，但不是 Agent 可自主改写的长期 memory；
- 跨 Agent 历史只有在 Coordinator 选为 evidence reference 后才进入目标 Agent context；
- 跨 Run 经验只有经过测试或人类确认后才能进入 curated knowledge/few-shot；Agent 可以提出候选更新，但不能直接改写永久规则或 routing policy。

## Current-to-Target 差异

| 当前行为 | 目标合同 | 后续 owner |
| --- | --- | --- |
| `method_planner -> decision_coordinator` 已声明但 router 不返回 | 用于 structured needs-input/planning-failure control path | Phase B routing implementation |
| `analysis_engineer -> codex_handoff` 可直接发生 | 所有 graph-level code fix 先进入 Coordinator，再派发 Code Agent | Phase B + A05 |
| `analysis_engineer -> method_planner` declared-only | 删除直接回退；replan 必须由 Coordinator 派发 | Phase B |
| Codex Handoff 失败主要 `END` | 最终 Code Agent 把所有非成功 outcome 交给 Coordinator | A05 + Phase B |
| Coordinator 只能实际进入 Gate 或 Report | 增加四层受控回退目标 | A02–A06 + Phase B |
| Human Gate 可直接进入 Analysis、Handoff、Report 或 END | Human Gate 只向 Coordinator 返回 valid response；pending 时 PAUSE | A04 + Phase B |
| `approve_rerun` 仅记录 intent 后停止 | human response 回 Coordinator，创建一个新的有限 attempt window 后派发 | A02 + A04 + A06 |
| 完整 `event_log` 保存在 graph state，当前主要供 checkpoint、审计和 UI 使用 | 保持完整 audit state，但 Agent 只使用 scoped context 和相关 attempt history | A02 + Phase B context tests |

## Forbidden Routes and Behaviors

- Analysis Engineer 直接进入 Code Agent 或 Method Planner；
- Scientific Reviewer 直接进入 Analysis Engineer、Code Agent 或 Method Planner；
- Human Gate 直接进入工作 Agent、Memory Report 或自行修改 human response；
- Memory and Report Node 发起 re-review、rerun、code fix 或 replan；
- 仅凭自由文本、来源节点、未经验证的 provider 建议或完整 event log 内容决定路线；
- 在没有新 attempt/cycle identity 和 invalidation contract 时覆盖旧结果；
- high/critical、诊断歧义、预算耗尽或重复失败时继续自动循环；
- 重复消费同一 human decision，或把一次批准解释为无限预算；
- 让 Agent 从未审核的单次经历直接改写长期规则、skills 或 routing policy。

## Downstream Ticket Inputs

- A02：Run/Cycle/Attempt identity、父子关系、Agent-scoped attempt history 和 remediation parent references；
- A03：四层回退的 artifact namespace、current pointers、versioning 和 invalidation；
- A04：typed Human Gate request、PAUSE/resume、single-use response 和 pending audit/report compatibility；
- A05：Fake/real Code Agent 共同接口、diagnostic outcome、sandbox 和 verification evidence；
- A06：route/run budgets、failure fingerprint、重复失败判定和 human-granted finite window；
- A07：所有允许/禁止路线、context boundary、cycle、budget 和 resume 的 harness acceptance。

## 已确认决策

- graph-level 回退全部由 Decision Coordinator 统一拥有；
- low/medium、诊断唯一且预算可用时允许自动回退；
- Coordinator 正式允许回退到 Reviewer、Analysis、Code 和 Planner 四层；
- Agent 使用分布式结构化诊断，Coordinator 不从自由文本猜测根因；
- 诊断歧义直接进入 Human Gate；
- Human Gate 统一处理 clarification、approval 和 external action，进出只连接 Coordinator；
- 人类批准只提供一个新的有限 execution window，且 response single-use；
- Agent 默认没有可自主写入的长期 memory，只使用 scoped context 和相关 attempt history；
- 跨 Run 经验必须经测试或人类确认后才能进入 curated knowledge。

## Deliverables

- 经确认的 transition matrix；
- 当前实现与目标合同之间的差异清单；
- 后续 schema、routing 和 test tickets 的输入。

## Acceptance Criteria

- 每个当前和目标节点都有明确的允许出口；
- 每条允许路线都有 authority、结构化触发证据和停止/升级条件；
- Coordinator 可以区分并选择 re-review、rerun、code fix 和 replan；
- low/medium 唯一诊断可以自动执行，high/critical、歧义、重复 fingerprint 和预算耗尽进入 Human Gate；
- `needs_input` 按 `Agent -> Coordinator -> Human Gate -> Coordinator -> Agent` 流动；
- Human decision 不直接控制工作节点，且不能重复消费；
- 完整 `event_log` 不进入 Agent context，多 attempt 只加载相关 scoped history；
- intent-only 和 proposed 路线不会被误写成 current；
- graph 中不存在未分类的 declared-only edge；
- 所有禁止路线都进入 A07 harness 输入。

## Verification

```bash
git diff --check
```

还必须检查：

- ticket front matter 在验收完成后为 `status: completed`；
- 本轮只修改 Allowed Files 中的 A01 ticket 和 Required Documentation Updates；
- Markdown 相对链接有效；
- 当前实现事实、目标合同和下游依赖没有互相混写。

## Stop Conditions

- 需要在 A01 中提前冻结 Run/Cycle/Attempt 字段、artifact namespace、resume mechanism、Code Agent wire schema 或具体预算数值时停止；
- 需要扩大 Human Gate 以外的科学裁决权或放宽 risk floor 时停止；
- 同一路线仍存在多个影响不同且无法通过结构化诊断消除的合理解释时停止；
- 代码实际行为无法从仓库确认时停止。

## Required Documentation Updates

本次 A01 执行同步：

- `docs/ARCHITECTURE.md`
- `docs/AGENT_ROLES_AND_BOUNDARIES.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`

Stale-documentation scan 经用户确认后还同步：

- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`
- `docs/VERIFICATION_GUIDE.md`

## Completion Record

- Status：`completed`（2026-08-11）
- Changed：确认 current / declared-only / intent-only / proposed / forbidden 路线分类；确认由 Decision Coordinator 集中拥有四层 graph-level 回退；确认 Human Gate、structured diagnostic、scoped context 和 curated cross-run memory 边界；同步核心 source-of-truth 与经用户批准的 stale documentation。
- Verified：A01 metadata、A02–A07 draft metadata、28 个现行 Markdown 文件的相对链接、stale-documentation scan、Allowed Files / Do Not Touch 范围和 whitespace checks 均通过；本 ticket 为纯设计变更，因此未运行 runtime 或 live-provider tests。
- Commit：未提交。
- Follow-ups：A02–A07 分别落实 execution identity、artifact invalidation、pause/resume、Code Agent、budget/fingerprint 和 Phase B harness；在这些合同完成并形成实现 ticket 前不修改 runtime graph。
