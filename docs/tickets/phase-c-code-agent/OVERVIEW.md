# Phase C：Graph-managed Code Agent

## Status

`planned`

## 目标

在不改变主图已验证合同的前提下，先通过独立C00 capability gate选择满足A05完整port、隔离、停止、审计和重启恢复合同的真实backend，再实现隔离、可预算、可审计的Code Agent，并打通代码修改、验证和新Analysis Attempt的完整闭环。

## 进入条件

- Phase B 控制层和 Fake Code Agent 路线通过；
- Code Agent contract、workspace isolation 和 approval policy 已冻结；
- 成功与失败的集成验收已定义。

## 首个 Gate

Phase C第一份ticket必须是`C00_CODEX_SDK_BACKEND_FEASIBILITY`。它使用pinned候选SDK/runtime验证Host-owned operation identity、restart lookup、tool audit、exact cancel与停止后无activity、workspace-write边界、immutable result/seal和fail-closed recovery。Python Codex SDK是条件性首选候选，不因文档提供thread或sandbox能力就跳过C00；C00失败时必须另建design ticket选择替代backend，不能降低A05合同。

## 退出方向

完成后进入 Phase D 的 Agent 能力与物理知识增强。具体 implementation tickets 将在前置阶段完成后创建，本阶段当前没有可执行 ticket。
