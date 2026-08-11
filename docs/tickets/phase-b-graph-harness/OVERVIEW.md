# Phase B：图与 Harness 可靠性

## Status

`planned`

## 目标

根据 Phase A 已冻结的控制合同，实现 Run/Cycle/Attempt、artifact invalidation、durable resume、有限循环和分层 graph harness，并使用 Fake Agents 证明控制系统正确。

## 进入条件

- Phase A A01–A07 全部 completed；
- transition、identity、invalidation、resume、budget 和 harness acceptance 已进入核心文档；
- 实现者不需要自行补充控制层设计决定。

## 退出方向

完成后进入 Phase C，把 Fake Code Agent 替换为隔离的真实实现。具体 implementation tickets 将在 Phase A 完成后创建，本阶段当前没有可执行 ticket。
