# A03 Transition Publication-order Clarification

## Issue

A03 §6 的成功路径使用了以下缩写：

```text
Transition commit
-> pre-target invalidation/current clearing
-> target Attempt starts
```

如果把第一行理解为“committed Transition record已经append”，它会与A02 target preallocation、A03当前实现、A03C01 cross-head验证和A02 Human Gate commit-order clarification冲突。

## Clarification

该行表示进入复合`commit_transition`控制操作，不表示Transition record先落盘。权威durable publication顺序保持为：

```text
enter commit_transition
-> create Human Request when applicable
-> allocate the target Attempt as scheduled
-> apply A03 target-layer invalidation/current clearing
-> append the committed Transition record
-> validate resulting execution/artifact heads
-> let the target wrapper consume/start that exact scheduled Attempt
```

`current_cleared` events仍绑定预先确定的Transition identity和scheduled target identity；Transition ID可以在复合操作开始时确定，不要求其committed record已经append。Human Response lifecycle继续由A02/A04自己的顺序约束，不由本clarification重定义。目标Attempt在完整Transition及heads验证前不得`started`。

## Scope

- 本记录只消除A03已完成正文中的术语歧义，不修改A03正文；
- 不改变execution/artifact schema、identity、invalidation matrix、graph topology、public interface或恢复策略；
- 不批准跨文件自动repair；任一partial publication仍由A04返回`recovery_required`；
- A06及后续ticket必须引用本顺序，不得重新声明为Transition append后再invalidation。

## Verification

- `src/lqcd_agent/graph/state.py::commit_transition`在`_record_committed_transition`前执行`allocate_attempt`和`invalidate_for_target`；
- `src/lqcd_agent/graph/state.py::commit_external_transition`使用相同顺序；
- A02 Human Gate clarification同样记录request → allocation → invalidation → Transition append；
- A01–A03及A03C01 completed ticket正文保持未修改。
