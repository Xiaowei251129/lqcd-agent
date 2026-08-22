# 第二阶段 Ticket 工作流

## 目的

Ticket 是一次具体工作的执行合同，不是当前系统事实的长期来源。方向文档说明为什么改进，Phase Overview 说明阶段目标，ready ticket 说明本次具体做什么，核心 source-of-truth 文档说明执行后系统实际变成什么。

执行 ticket 前必须先阅读：

- [`../../AGENTS.md`](../../AGENTS.md)
- [`../README.md`](../README.md)
- ticket 的 `Read First`

## 生命周期与冻结点

```text
draft → review → ready → in_progress → completed
                     ↘ blocked
draft/review/ready → superseded
```

- `draft`：正在讨论，不能执行；
- `review`：内容基本形成，等待最终确认，不能执行；
- `ready`：用户已经确认，ticket正文从此冻结，可以执行；
- `in_progress`：正在执行；
- `completed`：目标和验证已完成；
- `blocked`：满足 Stop Conditions 或存在外部阻塞；
- `superseded`：已被新的设计或 ticket 替代。

只有用户确认后的 `status: ready` ticket 可以进入执行。Codex 不得自行把 ticket 从 `draft` 或 `review` 提升为 `ready`。进入`ready`后，Goal、Scope、Non-goals、Allowed Files、Do Not Touch、Requirements、Acceptance Criteria、Verification、Stop Conditions及其他正文均不可再改；后续只允许变更YAML中的lifecycle metadata。

冻结ticket应在执行前进入Git历史。若用户明确要求暂不commit，completion record必须如实记录ticket只冻结在当前worktree，不能声称存在可恢复的committed snapshot。

## 执行规则

- 一个 ticket 只解决一个可以验证的目标；
- Phase Overview 不是执行 prompt；
- 严格遵守 Allowed Files、Do Not Touch 和 Stop Conditions；
- deterministic/mock path 保持默认；只有 ticket 明确批准时才能改变 provider 或 data policy；
- ticket 不能静默放宽 `AGENTS.md`、raw-data、security、approval 或 public contract；
- 需要新 state field、artifact schema、graph edge、status value 或 dependency 时，如果 ticket 没有明确批准，必须停止；
- 实现 Agent/Node 的 ticket 必须把它接入 graph 与相应 harness；如果本轮明确只做 standalone module，必须写出原因和后续 integration ticket；
- 验证必须与风险相称，并记录实际结果；
- verification 默认使用 `/private/tmp/lqcd-agent-...` 或新的 run id，不能把历史 `outputs/` 当成验收证据；
- 完成后在[`completions/`](completions/README.md)建立独立completion record，并同步受到影响的核心文档和 `REPO_CURRENT_STATE.md`；
- 架构、政策、schema 或阶段顺序发生变化时，追加 `DECISION_LOG.md`；
- final response 前执行 stale-documentation scan：检查根 README、相关核心文档、Current State、Decision Log 和本次涉及的 TODO 是否仍与实现一致，只修改本 ticket 导致过时的内容；
- completed ticket不再内嵌或追加Completion Record；实际changed files、verification、commit和follow-ups写入独立completion record；
- completed ticket 是工作记录，不能替代当前核心文档。

## 执行中发现新问题

不改变schema、架构、public contract、Allowed Files、Do Not Touch或验收边界的局部bug，可以直接修复，但必须在[`corrections/`](corrections/README.md)留下简短maintenance record。

出现以下任一情况时，必须停止当前实现并创建新的corrective ticket，原ticket保持冻结：

- 改变schema、graph topology、状态机、authority或public contract；
- 扩大Allowed Files或触碰原Do Not Touch；
- 引入新的恢复、preflight、migration或compatibility policy；
- 原Acceptance Criteria无法覆盖新风险；
- 修复需要跨多个控制平面重新定义完整性关系。

corrective ticket使用普通ticket模板，`type`设为`corrective-implementation`并通过`depends_on`引用原ticket。它必须独立经过`draft → review → ready`确认，不能把新要求写回原ticket。

## 使用方式

用户可以指定一个 ready ticket，例如：

```text
Codex，请执行 docs/tickets/phase-a-control-contracts/A01_TRANSITION_MATRIX.md
```

Codex 应先验证其 `status`，再按 ticket 的完整合同执行。如果状态不是 `ready`，只能继续讨论或完善 ticket，不能实施其内容。

## 阶段目录

- [`phase-a-control-contracts/OVERVIEW.md`](phase-a-control-contracts/OVERVIEW.md)：控制合同澄清；
- [`phase-b-graph-harness/OVERVIEW.md`](phase-b-graph-harness/OVERVIEW.md)：图与 harness 可靠性；
- [`phase-c-code-agent/OVERVIEW.md`](phase-c-code-agent/OVERVIEW.md)：graph-managed Code Agent；
- [`phase-d-agent-capabilities/OVERVIEW.md`](phase-d-agent-capabilities/OVERVIEW.md)：Agent 能力与物理知识；
- [`phase-e-integrated-benchmark/OVERVIEW.md`](phase-e-integrated-benchmark/OVERVIEW.md)：综合 benchmark 与下一 milestone。

新ticket必须从[`TEMPLATE.md`](TEMPLATE.md)创建；完成记录从[`completions/TEMPLATE.md`](completions/TEMPLATE.md)创建。2026-08-22之前已经把Completion Record内嵌在ticket中的A01/A02作为历史格式保留，不追溯重写；A03因存在持续纠偏问题，已单独拆分。
