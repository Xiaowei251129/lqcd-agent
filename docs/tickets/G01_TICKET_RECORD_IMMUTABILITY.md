---
ticket_id: G01
phase: repository-governance
status: completed
type: governance
depends_on: []
---

# 冻结执行 Ticket 并分离完成与纠偏记录

## Goal

将 repository ticket 明确定义为执行前冻结的合同，并把执行结果、后续小修记录和大型 corrective work 从原 ticket 中分离，确保任何时候都能独立回答“最初批准了什么”和“后来实际做了什么”。

## Why

A03 在完成后持续追加多轮 corrective pass，导致原始执行计划、实现结果与后续修复要求混在同一文件中。该结构削弱了 scope audit、历史恢复和后续执行的可解释性。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/tickets/README.md`
- `docs/tickets/TEMPLATE.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/DECISION_LOG.md`
- `docs/tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md`

## Scope

- 冻结 `status: ready` ticket 的 Goal、Scope、Non-goals、Allowed Files、Requirements、Acceptance Criteria、Verification 和其他正文；
- 只允许 ready 后更新 YAML lifecycle metadata，不再向 ticket 正文追加 Completion Record；
- 建立独立 completion records 和 historical correction records；
- 要求大型偏差或合同变化使用新的 corrective ticket；
- 允许不改变合同的局部 bug fix 使用简短 maintenance record；
- 从 A03 原 ticket 拆出累积 Completion Record，并保留可追溯历史；
- 更新 ticket template、索引、verification 和 repository governance 文档。

## Non-goals

- 不修改 A01 或 A02 的历史 ticket；
- 不修改 A03 runtime code或测试；
- 不恢复无法由现有 Git/工作区证据证明的 A03 中间版本；
- 不创建 commit；
- 不改变 A04–A07 的产品合同或状态。

## Allowed Files

- `AGENTS.md`
- `docs/README.md`
- `docs/DECISION_LOG.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/tickets/README.md`
- `docs/tickets/TEMPLATE.md`
- `docs/tickets/G01_TICKET_RECORD_IMMUTABILITY.md`
- `docs/tickets/completions/`
- `docs/tickets/corrections/`
- `docs/tickets/phase-a-control-contracts/A03_ARTIFACT_INVALIDATION.md`
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`

## Do Not Touch

- `src/`
- `tests/`
- `configs/`
- `raw_data/`
- `outputs/`
- `evaluation/`
- A01、A02、A04–A07 ticket正文；
- dependency、provider、checkpoint和external system。

## Requirements

- `ready` 表示正文已经冻结；执行中发现新设计不得回写原正文；
- ticket状态转换只允许修改YAML lifecycle metadata；
- completion record必须独立保存实际changed files、verification、commit和follow-ups；
- maintenance record只适用于不改变schema、架构、public contract、Allowed Files或验收边界的局部修复；
- 改变上述任一边界时必须创建并单独批准corrective ticket；
- A03拆分必须保留全部现有执行与corrective evidence，不得丢弃历史；
- 无法证明是原始执行前内容的A03版本必须明确说明provenance限制，不能伪称精确原版。

## Deliverables

- 更新后的repository ticket governance；
- 无内嵌Completion Record的新ticket template；
- completion/correction record目录及模板；
- 独立A03 completion与legacy corrective history；
- 只保留执行合同正文的A03 ticket。

## Acceptance Criteria

- 原ticket、completion evidence和corrective history可以分别读取；
- 新规则明确区分小修和需要新ticket的大修；
- A03全部既有记录均可从独立文件访问；
- A01、A02正文不变；
- Markdown links、metadata和`git diff --check`通过。

## Verification

```bash
git diff --check
```

- 检查所有tracked Markdown relative links；
- 检查A01/A02相对本轮开始没有变化；
- 检查A03 ticket不再包含`## Completion Record`；
- 检查completion/correction索引能定位A03历史。

## Stop Conditions

- 需要删除任何A03历史记录时停止；
- 无法区分A03执行合同正文与Completion Record边界时停止；
- 需要修改runtime、tests或A01/A02时停止；
- 需要创建commit时停止并请求用户决定。

## Required Documentation Updates

- `AGENTS.md`
- `docs/README.md`
- `docs/DECISION_LOG.md`
- `docs/REPO_CURRENT_STATE.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/tickets/README.md`
- `docs/tickets/phase-a-control-contracts/OVERVIEW.md`
