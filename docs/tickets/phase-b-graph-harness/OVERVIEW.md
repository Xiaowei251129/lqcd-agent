# Phase B：图与 Harness 可靠性

## Status

`planned`

## 目标

根据 Phase A 已冻结的控制合同，复用 A02 已验收的 Run/Cycle/Attempt/Transition/Human identity protocol，实现 artifact invalidation、durable resume、有限循环和 A01 产品路线改造，并使用 Fake Agents 建立分层 graph harness 证明控制系统正确。

A02 的 re-review、analysis rerun、code fix 和 replan tests 只证明 transition-time identity protocol；它们不是 Phase B 的完整 product-route、forbidden-route、budget 或 recovery coverage。Phase B 必须在不重新定义 identity 的前提下补齐这些控制行为。

## 进入条件

- Phase A A01–A07 全部 completed；
- transition、identity、invalidation、resume、budget 和 harness acceptance 已进入核心文档；
- 实现者不需要自行补充控制层设计决定。

当前 physical `codex_handoff` / canonical `legacy_codex_handoff` 是兼容路径，不是 Phase B 的 Fake `code_agent`。只有 A05 合同完成后，Phase B 才能接入 deterministic Fake Code Agent；真实隔离 Code Agent 仍属于 Phase C。

## 退出方向

完成后进入 Phase C，把 Fake Code Agent 替换为隔离的真实实现。具体 implementation tickets 将在 Phase A 完成后创建，本阶段当前没有可执行 ticket。
