# A02 Human Gate Commit-order Clarification

## Issue

A02 的通用 `Commit order` 已冻结：非终态目标必须先分配为 `scheduled` Attempt，再追加 committed Transition record。A02 `Human Response` 的 runtime-flow 简写却使用了以下顺序：

```text
Coordinator -> Human Gate transition commit
-> create Human Request
-> preallocate first Human Gate Attempt
```

如果把第一行理解为“committed Transition record 已经落盘”，它会与同一 ticket 的通用顺序、target-consumption规则和当前实现冲突。

## Clarification

该行只表示 Coordinator 开始执行进入 Human Gate 的复合 `commit_transition` 操作，不表示 Transition record 已先追加。权威 durable 顺序保持为：

```text
terminal Coordinator source Attempt
-> enter commit_transition
-> create the identity-bound Human Request
-> allocate the target Human Gate Attempt as scheduled
-> apply A03 target invalidation
-> append the committed Coordinator-to-Human-Gate Transition
-> let the target wrapper consume that exact scheduled Attempt
```

A04 `human_input` 恢复使用另一条已冻结路径：Pause 打开时 target 为 null；Human Response 成功 claim 后，控制层通过 A02 external control Transition先分配新的 Human Gate validation Attempt，再追加该 external Transition，最后才启动 validator。它不是 A01 product edge，也不是 `human_gate -> human_gate`。

## Scope

- 本记录只消除已完成 ticket 中的顺序歧义，不修改 A02 正文；
- 不改变 execution schema、graph topology、Human Request/Response lifecycle、public interface 或恢复策略；
- 不需要 runtime、test 或 source-of-truth 修改；
- 若未来实现无法保持 target Attempt preallocation-before-Transition-record，则必须新建 corrective ticket，不能引用这段历史简写放宽 A02。

## Verification

- `src/lqcd_agent/graph/state.py::commit_transition` 在 `_record_committed_transition` 前执行 `create_human_request`、`allocate_attempt` 与 `invalidate_for_target`；
- `src/lqcd_agent/graph/state.py::commit_external_transition` 在 `_record_committed_transition` 前执行 `allocate_attempt` 与 `invalidate_for_target`；
- A04 与 A07 一致把 Human Response validation external Transition 与 A01 product route 分离；
- A01、A02、A03 与 A03C01 completed ticket 正文保持未修改。
