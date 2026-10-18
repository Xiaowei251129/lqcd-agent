# B00C19 — Human 容量不可达阈值验收补充

本补充由[冻结 C19](../phase-b-graph-harness/B00C19_HUMAN_CAPACITY_REACHABILITY_ACCEPTANCE.md)授权，实施状态与实际日志以[独立 completion](../completions/B00C19_COMPLETION.md)为准。仅补充 C17/C18 的不可达 transition 阈值验收方法，不修改冻结正文或生产合同。

## 证明前提与推导

原 `control/execution.py::_checked_replay` 要求每个非 END Transition 引用一个已唯一分配的 scheduled Attempt，并逐字段核对 `transition_id == inbound_transition_id`。不同 Transition 不能共用同一个 inbound identity，因此存在非 END Transition 到已分配 Attempt 的单射。`records.py` 只允许 END 使用 null target；原 `AdvanceControl._snapshot` 仅允许 Memory Report 提交 END，原产品图随 END 结束、原 terminal Run 禁止后续记录。故产品合法前缀满足 `T <= W + C + 1`。包含一个 END 已比 Human 前缀需要的上界更宽松；尚未提交 inbound 的 allocation 只会放宽此上界。

`execution.py::_budget_projection` 直接从唯一 Attempt/Transition 计数，Work/Control kinds 不交叠。原 policy 的全局限额不受 Grant 扩展；`AdvanceControl._snapshot` 对原 replayed used/remaining 和实际增量校验硬上限。`balanced_v1` 的 `(Wmax,Cmax,Tmax)=(16,16,40)`，`phase_b_test` 为 `(8,8,20)`。当剩余 control 至少为 `k`：

`remaining T >= Tmax - Wmax - (Cmax-k) - 1`。

| 路径 | 所需 control/transition | balanced 的 transition 下界 | phase_b_test 的下界 |
| --- | --- | --- | --- |
| ordinary publisher | 7/8 | 14 | 10 |
| terminal publisher | 4/5 | 11 | 7 |
| ordinary repause | 6/7 | 13 | 9 |
| terminal repause | 3/4 | 10 | 6 |

各下界均严格大于对应 transition 阈值。因此，在 control 充足条件下，原 policy 不允许独立 transition 临界或不足的实际 Run。对于 invalid validator，原 Resume 在进入前还检查 ordinary 6/7 或 terminal 3/4；执行 validator 后 control 至少 5/2，即使本次 repause 因 control 不足失败，transition 保守下界仍分别为 balanced 12/9、phase_b_test 8/5，严格高于 7/4。

专用测试对所有 `0<=W<=Wmax, 0<=C<=Cmax, 0<=T<=Tmax, T<=W+C+1` 的宽松计数集合枚举。这是合法计数的超集，包含未声称实际可达的组合；在超集中不存在反例，不能由少量实跑路径代替证明。每份证明报告保存当时原计数/端口源码与 protocol 的 SHA256。测试校验完整 allowlisted profile 集合、原限额/reserve/Grant 属性；实际 ledger 逐前缀核验单射、END 数、计数上界，并与原 replay 最终计数对照。限额变化或实际合法端口产生反例时须失败并重新审查，不能扩大此不可达清单。

## 三类证据及使用边界

1. `test_capacity_reachability_proof`：两 profiles × 四路径，共 8 项数学/有限集合检查；报告分类 `reachability_proof_not_runtime`，包含四项 post-validator 下界。
2. `test_contract_only_capacity_predicates`：两 profiles × 四路径 × control/transition 的 `required-1/required/required+1` 笛卡尔积，共 72 项。仅向原纯 selector/repause adapter 传入内存 view；不创建 Run、不落盘人工预算、不调用 Agent/Backend、不生成 trace/observe_case/owned。ordinary publisher 不足时仍可允许原 terminal 分支，测试分别断言其 sequence/trigger、禁止 Work/Grant 的 scope 和 tail 允许/拒绝结果，不能把允许 terminal 当普通 admission 成功。
3. `test_original_repause_dual_fresh`：保留 C18 三条原端口业务路径与原科学输入，每条双 fresh。新增 `capacity-witness.json` 被动记录原 ledger 的逐前缀计数与 Human decisions；原 raw/normalized/facts/views 均保留。ordinary insufficient 保持 halted，无新 Pause；ordinary corrected 保持 completed；terminal corrected 保持 halted、五条同 sequence、无新增 Work/Grant。来源重读/同 key 重入保持无 effect。

前两类只联合替代 C17/C18 中不可达的独立 transition 阈值实跑方法，不证明 authority、来源真实性、Human 全链或任何可达的 control 边界已验收。所有可达边界仍由 C18 H1/H2 的原端口双 fresh 验证；C18 原其余 H1–V2、C15–C17 全部逐项验收及最终固定输入 Session 不减项。

## 接续与不变量

C19 完成只解除已记录的验收方法阻塞。核对当前输入和冻结摘要后，依既有授权恢复 C18；C15/C16/C17/B04 不自动完成。C18 完成其全部覆盖和独立逐票复核后，才能重新审查 B04 入口；B04 原 Code parent、fallback、fresh Analysis、publication 接续和 47/144 仍待执行。

保持 131 required、84 mapped、47 remaining、2199 cases、324 boundaries、28 post-claim、B02 1410/B03 645/B04 144、15 exits 与原 owners；本票不修改 production、Phase A、旧 expected、sealed evidence、Session/registry/case/exclusion 或依赖，不 commit/push。
