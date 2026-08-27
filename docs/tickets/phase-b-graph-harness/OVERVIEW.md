# Phase B：图与 Harness 可靠性

## Status

`planned`

## 目标

根据Phase A已冻结的控制合同，复用A02 identity protocol、A02C01 schema `0.4` bootstrap与`ControlOperation 0.1`、A03 artifact invalidation infrastructure，实现独立于LangGraph checkpoint的durable mutation/resume、有限循环和A01产品路线改造，并使用Fake Agents建立分层graph harness证明控制系统正确。

A02/A03 的 re-review、analysis rerun、code fix 和 replan tests只证明 transition-time identity与invalidation protocol；它们不是 Phase B 的完整 product-route、forbidden-route、budget 或 recovery coverage。Phase B必须复用这些 primitives，不得另建第二套 current-selection或失效规则。

## 进入条件

- Phase A A01–A07及A02C01全部completed；
- transition、identity、invalidation、resume、budget 和 harness acceptance 已进入核心文档；
- 实现者不需要自行补充控制层设计决定。

当前 physical `codex_handoff` / canonical `legacy_codex_handoff` 是兼容路径，不是 Phase B 的 Fake `code_agent`。只有 A05 合同完成后，Phase B 才能接入 deterministic Fake Code Agent；真实隔离 Code Agent 仍属于 Phase C。

## 退出方向

完成后进入Phase C，先执行C00 capability gate，再把Fake Code Agent替换为通过门禁的隔离真实实现。具体implementation tickets将在Phase A完成后创建，本阶段当前没有可执行ticket。
