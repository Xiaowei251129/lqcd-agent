# 第二阶段文档索引

## 目的

本目录是 `v0.2-demo` 之后第二阶段开发的文档入口。它区分当前系统合同、未来方向、具体执行 ticket 和历史记录，避免旧计划、当前事实和未来设想互相混淆。

第二阶段文档以中文解释为主；代码标识、类型名、schema 字段、命令和代码块保持英文。代码注释继续遵守根目录 `AGENTS.md` 的全英文规则。

## 权威顺序

发生冲突时按以下顺序处理：

1. [`AGENTS.md`](../AGENTS.md)：仓库级行为与编码规则；
2. `status: ready` 的 ticket：本次任务的目标和允许范围；
3. 核心 source-of-truth 文档：当前系统合同；
4. [`DECISION_LOG.md`](DECISION_LOG.md)：架构和政策选择的理由；
5. [`REPO_CURRENT_STATE.md`](REPO_CURRENT_STATE.md)：代码实际实现状态；
6. Phase Overview 与方向文档：尚未全部落实的阶段目标；
7. milestone：冻结版本的历史事实。

Ready ticket 不能静默覆盖 `AGENTS.md`、安全策略或当前 public contract。出现冲突时必须停止并先形成明确的设计决定和合同更新。

## 核心 Source of Truth

- [`PROJECT_SPEC.md`](PROJECT_SPEC.md)：项目目标、当前基线、第二阶段目标和持续非目标；
- [`ARCHITECTURE.md`](ARCHITECTURE.md)：当前实际图结构、运行边界和已知缺口；
- [`AGENT_ROLES_AND_BOUNDARIES.md`](AGENT_ROLES_AND_BOUNDARIES.md)：Agent 当前职责和不可突破的边界；
- [`STATE_SCHEMA.md`](STATE_SCHEMA.md)：当前真实 `AnalysisState` 合同；
- [`ARTIFACT_CONTRACTS.md`](ARTIFACT_CONTRACTS.md)：当前运行 artifacts 的结构合同；
- [`SECURITY_AND_DATA_POLICY.md`](SECURITY_AND_DATA_POLICY.md)：数据、命令、secrets、provider 和审批策略；
- [`EVALS_AND_OBSERVABILITY.md`](EVALS_AND_OBSERVABILITY.md)：当前 benchmark、可观测性和下一阶段 eval 方向；
- [`VERIFICATION_GUIDE.md`](VERIFICATION_GUIDE.md)：当前验证入口和 ticket 完成检查；
- [`REPO_CURRENT_STATE.md`](REPO_CURRENT_STATE.md)：第二阶段实时状态；
- [`DECISION_LOG.md`](DECISION_LOG.md)：已确认设计决定。

核心文档同时区分当前runtime与已确认的目标合同。A02已完成Run/Cycle/Attempt/Transition/Human identity，A03已完成per-attempt artifact namespace、typed current index、compatibility projection和transition-time invalidation；四层fallback仍只是control harness evidence。A02C01已完成schema `0.4` bootstrap后继合同的治理同步，A04已完成Pause/Resume/Replay/Fork目标合同同步，A05已完成graph-managed Code Agent、replaceable backend、isolated workspace、trusted verification与fresh Analysis handoff目标合同同步，A06已完成immutable budget policy、admission/reservation、failure fingerprint、single-use grant、Pause deadline与fail-closed stop目标合同同步，A07已完成六层deterministic acceptance、exact trajectory、fault/concurrency、machine matrix与zero-gap exit目标合同同步；这些完成项都没有把相应目标能力接入当前schema `0.2` runtime。未来RAG设计也不能提前写成当前runtime能力。A02/A03冻结正文中的commit-order歧义使用独立correction records澄清，不回写历史ticket。

## 第二阶段方向与 Tickets

- [`NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md`](NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md)：第二阶段三个改进方向和 A–E 阶段关系；
- [`tickets/README.md`](tickets/README.md)：ticket 生命周期、执行规则和目录说明；
- [`tickets/TEMPLATE.md`](tickets/TEMPLATE.md)：统一 ticket 合同。
- [`tickets/completions/README.md`](tickets/completions/README.md)：独立执行结果记录；
- [`tickets/corrections/README.md`](tickets/corrections/README.md)：maintenance与corrective历史记录。

Phase Overview 不是执行 prompt。只有经过用户确认并标记为 `status: ready` 的具体 ticket 才能执行；`ready`后ticket正文冻结，执行结果和后续纠偏不得回写原计划。

Phase A的A01–A07、A02C01及A03C01现均为`completed`；设计合同完成不代表Phase B runtime已实现。阶段闭合状态见[Phase A Overview](tickets/phase-a-control-contracts/OVERVIEW.md)，B00–B05状态与进入条件见[Phase B Overview](tickets/phase-b-graph-harness/OVERVIEW.md)。[Control Protocol 0.4](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json)与[需求目录](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json)提供机读合同及stable IDs；验证入口见[Verification Guide](VERIFICATION_GUIDE.md)，结果见[Repo Current State](REPO_CURRENT_STATE.md)，理由与历史见[Decision Log](DECISION_LOG.md)。B00验收基础和B01纯Execution 0.4 foundation已完成，construction分别为15/15及11/11；累计映射26/131、剩余105，global passed为null，`requirements_zero_gap`与`phase_b_complete`均为false。执行事实见[B00 completion](tickets/completions/B00_COMPLETION.md)与[B01 completion](tickets/completions/B01_COMPLETION.md)。B02已获用户批准为`ready`，待冻结快照后执行；B03–B05仍为`draft`。当前默认product runtime仍为schema `0.2`；durable control、Code Agent与产品budget enforcement均未实现。

## Milestones

- [`milestones/V0_2_DEMO_BASELINE.md`](milestones/V0_2_DEMO_BASELINE.md)：第一阶段 `v0.2-demo` 冻结基线。

Milestone 文档只允许事实纠正，不随当前开发持续改写。可变状态只写入 `REPO_CURRENT_STATE.md`。

## 第一阶段历史资料

第一阶段的累计成果、验证基线、持续边界和已知限制已归档到 [`milestones/V0_2_DEMO_BASELINE.md`](milestones/V0_2_DEMO_BASELINE.md)。旧的单体 build plan、ticket ledger 和 prompt playbook 已在规则迁移及依赖审计通过后从当前工作树删除，不再参与第二阶段文档解析。

如需核对原始历史内容，可从 Git tag `v0.2-demo` 查看：

```bash
git show v0.2-demo:docs/CODEX_BUILD_PLAN.md
git show v0.2-demo:docs/TICKETS.md
git show v0.2-demo:docs/PROMPT_PLAYBOOK.md
```
