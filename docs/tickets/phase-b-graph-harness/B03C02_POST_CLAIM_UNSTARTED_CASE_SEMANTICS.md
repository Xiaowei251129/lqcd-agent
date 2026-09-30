---
ticket_id: B03C02
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B02, B03, B00C05, B00C08, B03C01]
---

# 修正未启动消费者的 post-claim runtime case 语义

## Goal

使 B03 的 post-claim 独立故障集合只要求真实可达的 consumer stop 分类，同时保留七个入口阶段、四格设计时分类、28 个 post-claim runtime case、B03 的 645 个 case、全局 2199 个 case、101/324 boundary、owner、construction 和 exit 门槛。`depends_on: B03` 指被纠偏的原票，不要求其先完成。沿用 B03 不提交、不推送边界。

## Why

现行 case0.3 对七个 `post_claim` entry phase 各自展开 `safe_stop/unavailable × appendable/unavailable` 四格。真实 canonical normal-result Resume 在 `invocation_authorized` 前六个阶段尚未启动 consumer；`ConsumptionFailure.start` 冻结的 capability `started_intent` 为 null。`continue_failure` 在此情形直接形成可信 `not_dispatched` stop proof，不调用 `stop_consumption`。因此前六阶段的 `consumer_stop=unavailable` 共 12 个独立 case 无法在不伪造 started intent、改变安全停止语义或篡改结果的条件下触发。

现行工作树真实 canonical fixture 的七阶段探针 `/private/tmp/b03-post-claim-probe.log`：前六阶段均为 `started=False, stop_calls=0, safe_stop/appendable → failed`；`invocation_authorized` 为 `started=True, stop_calls=1, unavailable/appendable → unavailable`。另以真实 unavailable Run authority 复核前六阶段，仍为 `started=False, stop_calls=0, safe_stop/unavailable → unavailable`，原始结果在 `/private/tmp/b03-post-claim-authority-probe.log`。探针源码分别为 `/private/tmp/b03_post_claim_probe.py`、`/private/tmp/b03_post_claim_authority_probe.py`。进一步的12项跨进程可达性探针在 `/private/tmp/b03c02_cross_process_probe.py` 与 `/private/tmp/b03c02-cross-process-probe-asserted.log`：每项在原 owner 提交后退出并由新进程恢复，appendable六项为`failed_closure`，unavailable六项为`unavailable_closure`，consumer调用均为零。这些探针是审查证据，不是带production hook回执、passing nodeid与固定exact trace的独立runtime acceptance。生产顺序由 `pause.py` 的 `ResumeRun._continue_recovery` 在 `invocation_authorized` 后才调用 `InvocationLeases.invoke`、`ConsumptionFailure.start` 冻结 `started_intent`、`continue_failure` 的 `started is None` 分支共同保证。A07 的 7×4 设计时总函数仍有意义；问题是 B00 case0.3 将抽象四格无条件施加到每个 runtime entry phase。

`Coordinator.step` 的phase `after` observer仍在SQLite事务内，直接在那里退出会回滚`consumption_failure_ownership_reserved`；`Coordinator.transaction` 的`coordinator.database_commit.after`才位于提交之后。故障测试必须先由该failure phase的`after`标记本次目标，再只在紧随其后的`coordinator.database_commit.after`退出，并由独立进程重读已持久化的owner/failure intent；不能把phase `after`回执冒充durable COMMIT后的崩溃证明。

原 B03 的 Allowed Files 与 Stop Conditions 不允许更改冻结 case0.3 独立集合或其验收语义，不能将 12 个 case 静默 skip、用同一结果冒充 `unavailable`、或记作 maintenance。B03 的其他 runtime 义务继续执行，但完整 645/645 因该边界不能完成。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/tickets/TEMPLATE.md`；
- [A07](../phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md) 的 post-claim 消费失败和设计时 28 路径、[B03](B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md)、[B00C05](B00C05_EXTERNAL_RESERVATION_FAULT_CASE_SEMANTICS.md)；
- `tests/phase_b/harness/inventory.py`、`tests/phase_b/harness/seals.py`、`tests/phase_b/harness/failpoints.py`、`src/lqcd_agent/control/pause.py` 的 Resume 与 ConsumptionFailure、`src/lqcd_agent/control/coordinator.py` 的 `step/transaction`、上述原始探针及其输出。

## Scope

- 生成并冻结新的 case0.4 runtime 语义与相对于 case0.3 的逐项 disposition。只替换前六个 post-claim entry phase 各两项 `consumer_stop=unavailable` case，共 12 项；保留其它 2187 项 ID、outcome、owner、hook 与语义不变。
- 每个替换项仍绑定同一原 entry phase、同一 Run authority 类别，命名为 `post_claim.<phase>.unstarted_recovery.<authority>`。原进程在`consumption_failure_ownership_reserved`的phase `after`只武装目标，必须在本次事务紧随的`coordinator.database_commit.after`退出；新进程先重读已持久化的原failure owner/intent再恢复。须证明冻结 `started_intent=null`、不调用 stop adapter、`not_dispatched` proof、同一 owner 与唯一 terminal 收尾；phase `after`退出造成的回滚不能计入新case。`appendable` 的精确 outcome 为 `failed_closure`，`unavailable` 为 `unavailable_closure`。保留前六阶段原 `safe_stop` case 作为原失败入口的分类证据；保留 `invocation_authorized` 的真实四格。
- 六个替换阶段固定为 `pause_ownership_reserved`、`pause_claimed_recorded`、`prestart_records_committed`、`pause_consumed_recorded`、`running_lifecycle_recorded`、`resume_checkpoint_committed`。每个阶段恰好替换 `post_claim.<phase>.unavailable.appendable` 和 `post_claim.<phase>.unavailable.unavailable`，分别成为 `post_claim.<phase>.unstarted_recovery.appendable` 和 `post_claim.<phase>.unstarted_recovery.unavailable`；新 case 不得沿用旧 `consumer_stop:unavailable` invariant，应验证 `started_intent:null`、`stop_proof:not_dispatched`、`stop_adapter_calls:0` 和原 Run authority invariant。逐项机器可读候选映射在 `/private/tmp/b03c02-case-disposition-review.json`，实施时须把它纳入本票 Allowed Files 中的固定 disposition fixture。
- 12 项中六个原 `unavailable.appendable` 的 outcome 是 `unavailable_closure`，替换后须明确变为 `failed_closure`；另外六个原 `unavailable.unavailable` 与新项均为 `unavailable_closure`。这六个 outcome 变化只属于逐项列明的 replaced case，不能解释为保留 case 的结果漂移。
- 对 case0.4 的 inventory、obligations、registry、matrix、fixture、expected trace 与 seal 做最小一致更新；按旧→新 disposition 验证 12 replaced、2187 retained，case 总数仍 2199/B03 645。既有 initial ExternalOperation case0.2→0.3 反例测试须显式以旧 0.3 为比较终点，不能因 current 切换而误判 post-claim 纠偏。不得复用旧 ID 或以当前 raw 动态生成 expected。两个独立 client/process 必须分别触发冻结入口和恢复；真实 production hook、passing nodeid、固定 exact trace 与结果在同一 fresh Session 验证。
- `inventory.py` 的现行 case0.3 特判还决定初始 ExternalOperation reservation outcome；case0.4 必须显式继承该特判，不能因版本字面比较使其它 case 悄然恢复旧分类。旧 case0.3 的 inventory/obligations/seals/reader 按原字节与原语义可继续独立验证。
- B03 在新 case 版本确认后再继续原 645/645 同 Session 验收；本票不代替外部、release、Analysis、timeout 等其他 B03 case 的实施。

## Non-goals

- 不修改 Phase A protocol/catalog 及其 7×4 设计时验证，不修改生产 `ConsumptionFailure` 的可信停止分类；
- 不改变 B02 1410、B04 144、B03 28 construction、131 个 required ID、owners 或 Phase B 全局完成规则；
- 不新增 Backend/provider/network、B04 产品路由或 legacy 行为。

## Allowed Files

- `docs/tickets/phase-b-graph-harness/B03C02_POST_CLAIM_UNSTARTED_CASE_SEMANTICS.md`：进入 ready 后仅 YAML lifecycle；
- `tests/phase_b/harness/inventory.py`、`seals.py`、`tests/phase_b/final_obligations.json` 及本票新增的 case0.3→0.4 disposition fixture/validator；只限 12 项替换及版本封存；
- `tests/phase_b/acceptance_matrix.json`、`failpoint_registry.json`、`fixtures/b03_runtime/`、`expected_traces/b03_runtime/`、`tests/phase_b/test_b03_runtime_cases.py`；仅限新12项的真实进程绑定、对应提交前/后反例和旧12项移除，可复用现有只读测试helper，不借本票绑定其它B03 case；`tests/phase_b/test_external_reservation_case_semantics.py` 仅可将 case0.2→0.3 旧反例的比较终点固定为旧 0.3，不弱化原断言；
- 本票独立 completion record、`docs/tickets/completions/README.md`、`docs/tickets/corrections/README.md`、`docs/README.md`、`docs/REPO_CURRENT_STATE.md`、`docs/tickets/phase-b-graph-harness/OVERVIEW.md`、`docs/EVALS_AND_OBSERVABILITY.md`、`docs/VERIFICATION_GUIDE.md`；若验收合同解释发生变化，追加 `docs/DECISION_LOG.md`。

## Do Not Touch

Phase A 冻结票据、protocol、catalog 与生成源码；B00–B03 ready 票正文、已有 completion/correction 历史；`src/lqcd_agent/`、legacy 实现、B04/B05 票正文、依赖与配置、真实 Backend/provider/network、raw/accepted/secrets、control repository Git state。不得把本票作为其它 B03 case 缺口的通用豁免。

## Requirements

- 旧 case0.3 inventory、obligations、seals、reader 和旧证据原字节保留；新 case0.4 入口明确列出 12 个旧 ID→12 个新 ID，无隐式重解释。
- 新 12 项均需新进程取回原 owner 的 frozen failure intent，证明未启动的 consumer 无 stop callback，`not_dispatched` 是完整安全停止证明；Run authority 两格分别由真实 appendable/unavailable 来源产生，不靠篡改 expected 或跳过生产 validator。
- 真实production hook回执须绑定本次failure owner的提交后`coordinator.database_commit.after`，新进程确认该owner、frozen intent及唯一terminal收尾；不得以事务内phase `after`、同进程异常或审阅探针代替。相同phase其它事务的commit不能触发本case。
- `invocation_authorized` 的四个 stop/authority 组合仍由真实 started intent 和 stop proof做定向回归核对；该普通回归不计为四项B03独立runtime通过。原有其余16项post-claim case仍由B03后续逐项绑定真实hook、passing nodeid与exact trace；A07 设计时 28 路径、原 B03 其余 runtime case 和所有安全断言不弱化。
- 若任何旧 case0.3 中非上述 12 项也不可执行，或 12 项替换会改变 public schema、协议、catalog、B02/B04 case/owner 或 exit 门槛，停止并重新审阅，不扩大本票解释。

## Deliverables

- case0.4 与明确 disposition、12 项真实独立进程证据及固定 trace；
- 独立 completion record、验收报告及受影响的 source-of-truth 更新。

## Acceptance Criteria

- case0.3→0.4 差异恰为 12 replaced/12 new，其中六项 `unavailable_closure`→`failed_closure`、六项 outcome 保持 `unavailable_closure`；其余2187项ID与语义不变。current 总数 2199，B03 645、post-claim 28、B02 1410、B04 144、boundary 324、required IDs 131 不变；
- 六个未启动阶段×两种 authority 的12项均有本次提交后hook回执、原owner崩溃恢复、passing nodeid、固定exact trace；旧四格`invocation_authorized`与B02前置回归不退化，但旧四格的普通回归不计入本票12项或B03的独立runtime通过数；
- protocol/generated-byte、旧 case seal、construction、Phase B 与全仓回归通过，B03 后续仍按 645/645 独立验证。

## Verification

先保存旧/新 inventory 和 obligation SHA、12 项 disposition 与双 fresh 根 trace；逐项验证phase `after`退出会回滚，而武装目标后的`coordinator.database_commit.after`退出留下恰好一个持久化owner，新进程只恢复该frozen intent。再运行 `python scripts/validate_phase_a_control_protocol.py`、`python scripts/generate_phase_b_protocol.py --check`、case0.3/0.4 兼容检查、12 项子进程故障与反例、现有`tests/phase_b/test_external_consumption_control.py::test_post_claim_consumer_failure_preserves_normal_final_and_original_owner`四格定向回归、B00–B03 construction、Phase B、全仓、compileall、链接、范围、冻结正文及 `git diff --check`。以同一 fresh Session 验证本票12项的实际hook/nodeid/outcome/trace，不把审阅探针或旧四格普通回归当作B03 runtime acceptance。

## Stop Conditions

- 需要修改 Phase A 协议/catalog、生产停止语义、其它 case/owner/exit 门槛或 Allowed Files；
- 无法为每个替换项建立相互独立的真实进程故障与固定 trace，或只能通过 mock 结果/skip 使其通过；
- 回归出现未解释的 route、outcome、owner、事件顺序或安全证明差异。

## Required Documentation Updates

同步 `docs/README.md`、`docs/REPO_CURRENT_STATE.md`、Phase B Overview、eval/verification 指南及独立 completion；若修改验收语义的决定获批准，追加 `docs/DECISION_LOG.md` 并完成 stale-documentation scan。
