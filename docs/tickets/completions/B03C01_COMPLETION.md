# B03C01 Execution Record

## 2026-09-25 — Scheduled prior-ID correction, in progress

- 用户批准[修订后的 B03C01](../phase-b-graph-harness/B03C01_REPEAT_CODE_ATTEMPT_INVALIDATION.md)进入 `ready`；冻结正文 SHA-256 为 `c588611e9abb23379217f7990e7078d5c0558128f3e6c52d2ab6540047ae5cb4`。票据现为 `in_progress`，未提交或推送。
- `AdvanceOperations.advance` 在原 reservation 事务中绑定 `artifact_index.json` 原始 bytes、`validate_run_root` 的 current/revision/heads、route view 与计划创建；校验后至 snapshot 创建期间不同 bytes 被拒绝。`_snapshot` 仅对已验证 canonical Code current 的下一次 `code_agent` target，把 A03 将清除的每个 populated slot 的 prior ID 写入 scheduled input refs；A03 policy/validator、协议及旧 target 规则未改。
- 真实 Fake/Host `needs_input` 后的第二次 Code target 已提交，旧 Code member 原字节保留，旧 current 清除，新 producer/workspace/Attempt 独立。Code→Analysis→Code 的 A03 downstream 反例证明 `code` 与 `analysis` 两个 populated slot 同时进入 scheduled prior IDs 并清除。三个独立进程故障切点及双进程同 key 竞争均只产生一个第二次 scheduled Attempt；验证与 reservation 之间的同语义不同 index bytes 被拒绝。新增 trace0.5 的两个 fresh 根标准化 exact 相等，原始 trace、摘要和候选 expected 保存在 `/private/tmp/lqcd-agent-b03c01-trace-v8t7pbfj/`。
- 新增 C01 定向测试首次为 **9 passed**；首次 Code 无 current 的独立节点另为 **1 passed**。A03 registry、B02 advance/preparation 与 C01 的定向组合 **138 passed**。Phase A protocol 验证及 Phase B 生成字节检查通过。
- 前置 construction 目前 **B01 11/11**；B00 required pytest 为 **19 passed、10 failed**，B02 为 **30 passed、5 failed**，故 B00/B02 construction 均未通过，不能记作 15/15、30/30。B00 失败包括 5 条 A05 source/evidence 与 5 条旧 source-bound expected；B02 失败是 5 条旧 source trajectory expected。已核对 B02 `fork/human/replay/terminal` 事件顺序不变，`timeout` 多出 4 条 B00C09 授权的活动时间账本事件；剩余差异为派生 head/index/result 摘要。旧 expected 按 B03/B00C07/C08 规则留到完整 production 稳定后审定，不能由本票覆盖或把失败标为通过。
- 独立的 B02 consumption failure integrity-conflict 尾部回归仍在现有 B03 工作树，归 B03 maintenance；本票不触碰 `pause.py`。C01 的完整 construction、Phase B/全仓诊断和最终 completion 状态仍待 B03 源码稳定及旧 golden 审定后复验。

### B03 maintenance 后的新路径 trace 重审

B03 随后修复 `pause.py` 的独立失败尾部，导致 C01 新 trace 的 application build 及派生摘要变化。保留旧 expected/raw 与新两份 fresh 根原始 trace 于 `/private/tmp/lqcd-agent-b03c01-trace-after-b03-maintenance-i9ydnnqt/`；两根标准化结果 exact 相等，事件数与事件名顺序不变，差异字段仅 `artifact_head`、`execution_head`、`result_digest`。新路径 expected 已按该证据重审，旧 B00/B02/A05 expected 仍未改写；如后续 production 再变动，须重新执行双根审定。

### B03原范围内的前置来源审定后

B03 production稳定后，旧B00/B02/A05十份来源expected已在原B03/B00C07/C08授权下单独完成双fresh根raw preimage与逐字段审定；A05/B02/external source定向 **79 passed**，审计见[B03执行记录](B03_COMPLETION.md)与`/private/tmp/b03-golden-audit-current/`。C01自身未修改这些旧expected。重复Code新trace在B03 maintenance后的两个fresh根仍exact且已通过独立golden节点。C01仍为`in_progress`，待本轮B00/B01/B02 construction、Phase B及全仓诊断在固定输入上收尾；B03的645项runtime不作为C01完成数量。

本轮 C01 指定的重复 Code、external consumption、Analysis handoff 与 reservation 定向组合 **104 passed**。B03 原范围另审定两份 B00 source expected，并修正 B02 construction 间接调用造成的 B03 observation 归属污染；现时独立 fresh construction 为 **15/11/30/28**，其中前三项满足 C01 的前置门槛。两项修复的 raw 与根因详见[B03执行记录](B03_COMPLETION.md)及[maintenance](../corrections/B03_MAINTENANCE.md)。Phase B、全仓与同 Session B02 runtime 仍待本轮固定输入复验，C01 不提前标 completed。

### 2026-09-28 — C01 completed on the current worktree

当前固定源码下，C01 定向组合 **104 passed**；Phase A protocol semantic/freeze、生成字节 exact、compileall 与 `git diff --check` 通过。fresh construction 的 B00/B01/B02 为 **15/11/30**，并与 B03 **28/28** 一起在同一 fresh Session 复验；该 Session 的 B02 独立 runtime **1410/1410** 与已绑定的 B03 **7/7** 真实 hook、passing nodeid、exact trace 均通过，报告为 `/private/tmp/lqcd-agent-b03-partial-session-xxm_nv_w/session/report.json`。Phase B 全套 **2531 passed**（`/private/tmp/b03-phase-b-full-escalated-sep28.log`），全仓 **2856 passed**（`/private/tmp/b03-full-repo-escalated-sep28.log`）。旧来源 expected 的最终审定由 B03 独立记录承载；C01 未修改旧 expected 或 A03 validator/policy。未见 C01 导致的未解释 route、outcome、owner 或事件顺序退化。

C01 的重复 Code provenance 阻塞已解除，YAML 仅将 lifecycle 改为 `completed`。它不代表 B03 完成：当前 B03 仍只有 **7/645** 个独立 runtime case 绑定，另发现冻结 case0.3 的 12 个 post-claim 组合不可达，须由待审 [B03C02](../phase-b-graph-harness/B03C02_POST_CLAIM_UNSTARTED_CASE_SEMANTICS.md) 独立纠偏。工作树未提交、未推送，尚无 C01 committed snapshot。
