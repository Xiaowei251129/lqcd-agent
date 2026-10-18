# 项目规范

2026-10-17 B04完成：显式schema0.4 canonical Python产品入口已完成17条产品edge、四层fallback、Human return、Fake Code/fresh Analysis及预算/停止集成。仅接受new Run；默认legacy0.2 CLI及旧outputs保留。131项映射齐全和B04独立47/144通过不代表B05退出门槛已完成。 见[完成记录](tickets/completions/B04_COMPLETION.md)。以下日期条目为历史记录。

## 项目目标

本项目构建一个面向 lattice QCD pion quasi-DA 分析支持的、可审计的 LangGraph 多 Agent 工作流。系统负责把用户目标转成结构化方法计划，执行允许的分析流程，检查结构化证据，评估风险，并产出可复现的 artifacts、报告和审计记录。

系统是科学分析辅助工具，不是自主科学裁决者。central fit、最终 systematic uncertainty、accepted-result promotion 和 paper-level physics claim 始终属于人类责任；高风险或关键风险结果必须经过 Human Approval Gate。

## `v0.2-demo` 稳定基线

第一阶段已经形成可演示基线：

- deterministic mock 路径可在无网络条件下运行完整图；
- OpenAI/DeepSeek provider abstraction、strict structured output 和本地 evidence safety floor 已接入；
- Golden Demo、9-case synthetic benchmark、checkpoint、manifest、approval packet、memory 和 final report 已形成可复现链路；
- 当前基线的完整事实、验证结果和已知限制固定记录在 [V0_2_DEMO_BASELINE.md](milestones/V0_2_DEMO_BASELINE.md)。

## 第二阶段目标

第二阶段不是推翻 `v0.2-demo`，而是在稳定基线上解决三个能力缺口：

1. 明确 graph control contracts，证明所有批准路线、循环、停止条件和恢复语义可以被验证；
2. 把当前以外部 worker 为主的 Codex Handoff 演进为图内具有明确合同的 Code Agent；
3. 在 harness 可靠之后，分别提升各 Agent 的物理判断、证据使用和工具能力，并用 integrated benchmark 验证整体效果。

阶段顺序、讨论范围和 ticket 入口见 [第二阶段方向](NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md) 与 [Tickets](tickets/README.md)。任何新 graph edge、state field、artifact schema、RAG 模块或 Code Agent runtime 都必须经过独立 ticket 讨论，不能由本文件提前批准。

## 持续有效的硬边界

- 不得写入或修改 `raw_data/`；在正式 raw-data policy 获批前，运行时不得读取真实 raw numeric data。
- synthetic evaluation cases 必须位于 `raw_data/` 之外。
- routing 必须依赖结构化字段，不能依赖自由文本或被截断的摘要。
- provider 不能降低本地证据计算出的安全风险下限。
- secrets 不得进入 artifacts、日志、prompt 记录或版本控制。
- high/critical 结果没有有效人类批准时不得进入 accepted memory。
- 已有历史结果、human decisions 和已完成运行目录不得被静默覆盖。

这些边界不能由普通 ticket 静默放宽；如需改变，必须停止执行并进行明确的政策决策。

## 当前持续非目标

- 不自动决定 central fit、最终 systematic uncertainty 或论文级物理结论。
- 不把 LLM 输出当作未经本地证据验证的事实。
- 不允许任意 shell command、任意文件写入或无限循环。
- 不在控制合同和 harness 尚未验证前大规模加入 RAG、并行 fan-out 或复杂自治行为。
- 不用自定义图运行时替代 LangGraph。

## 第二阶段成功标准

第二阶段完成时，应能用测试和 benchmark 证明：

- 批准的 transition、retry、rerun、pause/resume 和 termination 行为都有确定合同；
- state 与 artifact 在 attempt/cycle 之间不会被错误复用；
- Code Agent 在受限权限、预算和验证门槛内工作；
- Agent 能力提升有证据来源、可观测记录和回归评估；
- 任何失败都能安全停止，并保留足够信息供人类诊断和恢复。

## 相关文档

- [Architecture](ARCHITECTURE.md)
- [Agent Roles and Boundaries](AGENT_ROLES_AND_BOUNDARIES.md)
- [State Schema](STATE_SCHEMA.md)
- [Artifact Contracts](ARTIFACT_CONTRACTS.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
