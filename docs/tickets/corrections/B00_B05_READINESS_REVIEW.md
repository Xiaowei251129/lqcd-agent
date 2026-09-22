# B00–B02 completion verification and B03–B05 draft readiness review

## 2026-09-22 — Review scope and conclusion

用户要求核验B00–B02达到既定要求后commit/push当前进度，并审查B03–B05有无矛盾及B03能否继续执行。本次不执行B03–B05，不改已冻结ticket正文、runtime、测试、matrix、case规则或trace合同；只修订三张仍为`draft`的后续票据及当前状态文档。既有未提交交付完整保留。

B00–B02各自范围已完成。B03 canonical Backend/Code Bundle/fresh Analysis、B04产品图与统一产品预算、B05全阶段exit不属于B02已交付功能，不能以B02完成宣告Phase B整体完成。

## Completion evidence checked

审查入口工作树摘要为`4d88c732386d8d37d2d6e2eda371bff0a57a276d14b3b2405ec2fb001a60c0d6`，与[B02完成记录](../completions/B02_COMPLETION.md#2026-09-21--b02-completed-after-integrated-acceptance)最终状态一致。核对全量验收3218项输入清单后，源代码、测试、fixtures、matrix/registry与该全量运行一致；全量运行后的15项差异全部是既有文档/生命周期收尾。此次后续草案修改也不改变运行实现。

| 验证范围 | 已复核结果 |
| --- | --- |
| B00/B01/B02 construction | 15/15、11/11、30/30；累计56、剩余75 |
| 全量冻结输入运行 | 2599 passed；Phase B 2274、其他回归325；104个同session批次 |
| B02故障验收 | 205 boundaries、1410/1410独立case；保留实际生产hook与进程证据 |
| 全局final | 仅75 coverage、798 runtime binding、15 exit adapter缺口；passed=null、phase_b_complete=false |
| 本次定向复验 | 114 passed；失败收尾、Resume准入、进程回执、预留case语义、external source trace及legacy source兼容 |

独立清单共324 boundaries/2208 cases，owner分别为B02 205/1410、B03 101/654、B04 18/144；后续798项未完成不归类为B02缺陷。B02 control half中的合成领域adapter不声称已经实现A05完整Backend。

历史全量原始证据仍在`/private/tmp/lqcd-agent-b02-integrated-4un4q9qb/`。本次审查证据在`/private/tmp/lqcd-agent-b00-b05-review-2b485tra/`，`baseline-proof.json`绑定审查入口与历史全量输入；历史session复核不冒充本次fresh全量运行。

重新调用既有验证器已确认历史2599项结果、1481项scenario observations和1410项runtime case有效；104份原始batch的token/摘要相同，完整selection无重复或遗漏。首次fresh construction仍15/11/30通过，final只报告预期75/798/15缺口。独立Phase A检查另发现上次文档收尾漏掉`docs/README.md`中的protocol引用；本轮恢复合同/需求目录链接并记录于[B02 maintenance](B02_MAINTENANCE.md#2026-09-22--documentation-reference-closure)。因此不沿用旧记录中“最终文档检查通过”的声明，提交须以本轮修复后的检查为准。

## Draft issues and corrections

| 草案 | 问题及影响 | 已写入草案的修正 |
| --- | --- | --- |
| B04 | 把所有edge写为advance/close会让START重复推进，与B02 bootstrap ownership冲突 | START归start/replay/fork；ordinary与END Transition归advance；END后close；Human外部validator入口归resume且不计17条产品rows |
| B04 | “post-claim failed/result-invalid closure后再route”混淆领域失败与消费完整性失败 | 合法canonical非成功bundle完成consume后才route；完整性失败由原resume失败tail收尾，不伪造bundle、Transition或第二terminal owner |
| B03 | 不实现B04 resource admission的宽泛表述可让本票aggregate/verification预留等待B04，形成依赖倒置 | 明确B03负责A05 producer/pre-start aggregate/verification accounting和typed adapters；B04负责产品选择与全局接线；不新增预算权威 |
| B03–B05 | 缺少已批准corrective基线；可能误用原1488个B02 case或旧trace语义 | 显式继承case0.2/trace0.4及旧版本各自规则，并要求独立inventory与真实source proof |
| B03/B04 | construction与负向final不足以证明本票全部故障case已运行 | 明确owned runtime在同session、冻结输入下有界分批并逐case核验，不能将缺口留到B05 |
| B03–B05 | production fingerprint覆盖全部包源码；新实现会改变已有source-bound golden中的真实build及派生head，原Allowed Files不明确 | 只允许来源可证明的fingerprint/head/reference同步；双fresh根复核、离线审定后固定；不得宽松比较或运行时重写expected |
| B05 | 当前final默认`run_pytest`单次300秒，无法容纳现有全量规模；Scope未明确允许改dispatcher接线 | 明确在driver/exit adapters复用C04 `run_pytest_batches`；同session、完整选择、输入不变、逐批校验，完成判定不变 |
| B05 | 未接本票exit adapter也可能被“final无法通过则停止”误当成入口阻塞 | 本票内接线可以继续；前置功能缺失或超出允许范围仍停止；验收完成前绝不能标记completed |

依据为冻结[A01](../phase-a-control-contracts/A01_TRANSITION_MATRIX.md)、[A04](../phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)、[A05](../phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)、[A06](../phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)、[C04](../phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)，以及当前B02 control ports、runtime fingerprint和final driver实现。本次仅澄清后续未冻结的执行范围，不修改这些合同。

## Commit gate and next ticket

提交前在修订后的固定文档状态重新运行B00/B01/B02 construction与global final负向检查，分别保存`B00-report.json`、`B01-report.json`、`B02-report.json`和`final-report.json`；断言15/11/30全部passed、56/75及仅75/798/15预期缺口。还须复核Phase A摘要、生成文件、既有冻结正文、scope、链接及diff；任何非预期错误阻止commit/push。此次没有重跑2599项全量，而是依据完整输入对照复核既有全量/逐case证据，并新增114项定向回归及fresh construction/final检查。

上述已知草案矛盾修正后，未发现要求先重做B02的阻塞。B03实施仍须覆盖654个独立case、28项construction及真实producer/backend/verification/handoff；本次静态审查不能保证未来实现无缺陷。B03–B05保持`draft`，按照[`AGENTS.md`](../../../AGENTS.md)及各票Review Gate，后续经用户审定为`ready`后再执行。本次commit/push授权不等于执行B03的批准。
