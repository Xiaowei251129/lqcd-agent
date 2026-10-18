# B00C24 ConsumptionFailure and Unaccepted Backend Source Contract

2026-10-13：C24 来源候选已实施，90项原生专项和16类双fresh验证通过；完整验收因既存B04 child Session接线缺口停止，C24/C23/B04均blocked，C25 review。以下描述当前候选，不代表整票交付。

- 仅显式 trace 0.11 / proof 0.8 启用；proof 顶层和 unconsumed_code_sources 闭合字段不变，旧 0.1–0.10/default 保持。A05 只增加可选 active_interval_settled 来源回调，由已验证的新 projector 提供；缺少回调或来源不符继续走原校验/拒绝。
- ConsumptionFailure 来源读取原 SQLite 的 Resume owner、原 claim、capability/撤销 epoch、原 prestart/normal final、failure ownership/stop journal、唯一 terminal closure 和实际 Run records。原 source revision/epoch、failure_id、完整 disposition contract、reservation/唯一 settlement、实际/保守 active time 与后续 Attempt 必须闭合。不恢复缺失 cause_type/cause，不添加旧 failure_identity 声明，不赋予新 effect authority。
- failure_id 保留为绑定原 owner 的不透明材料值；其原始 preimage 不存在时不做派生摘要替换。完整持久 failure snapshot 作为原 canonical source；started-intent ledger/index 原文先逐字核验，再引用完整原 prefix、实际 registration 和对应 head。没有删除材料字段来稳定 expected。
- 原 external normal/safe_stop 与 Resume consumer 停止及 Run append authority 分别验证。安全分支验证原 failed closure/release/publication；不安全分支保持 normal final、原 recovery_required/quarantined，不生成 finished/settlement/checkpoint 后缀。既有 aggregate settlement 与 failure tail 新结算分别核对。
- 显式 0.11 Fake dispatch 仅被动保存当时已生成的完整 Backend task/manifest/receipt/result/change/seal/audit/patch 原文；原 Backend immutable SQLite 返回与实际 producer/prestart、Session 绑定。未接纳 claim 使用独立来源标签，不伪装为已发布 Host seal/注册 Code。所有 byte SHA/logical checksum/引用先验证；只有具备真实 preimage 的结构引用及既有时钟语义才能规范化。旧/default 不采集，不改变原 effect/返回。
- 四消费者使用同一 fresh native Session 的真实 src/lqcd_agent/control/coordinator.py:boundary；专用 test-local runtime binding 仅在其独立验证子调用中发出，不写原 registry、不占 B04 owned。正式 matrix 仅追加 B00 final、A07-META-006/015 来源 meta。

票据：[冻结 C24](../phase-b-graph-harness/B00C24_CONSUMPTION_FAILURE_SOURCE_HANDOFF.md)。实际验收和限制见 [completion](../completions/B00C24_COMPLETION.md)。旧 C23 来源记录保留历史。

## 2026-10-13 C24 来源实施与原生验收停止

C24 专用90项、16类双fresh来源、8个fresh native四消费者及188组拒绝、construction15/11/30/28与final原47/144/15已验证。完整4549集合仅4261节点取得合格批次证据（含legacy325）；同Session独立owned未完成。两个B04 publication/control工厂的spawn child来源binding为unit-only而父进程为真实Session，独立原生反例均失败；文件与C24执行前一致，超出其Allowed Files。C24/C23/B04保持blocked，C25仅review，原始失败与未完成清单保留。B04仍owned0/144，不把局部测试当作整票完成。见[C24实际记录](../completions/B00C24_COMPLETION.md)及[C25待审](../phase-b-graph-harness/B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md)。无commit/push。

## 2026-10-14 C25 原生验收接线完成

[C25](../completions/B00C25_COMPLETION.md)完成child Session来源交接与独立诊断hook隔离；本合同候选源码保持原字节。共同固定输入90来源、16双fresh、8四消费者188拒绝、七类停止及full4578通过。C24仅经独立入口恢复ready，C23/B04保持blocked；本段不声明本合同所属票自动completed，不扩大来源语义或B04ownership。

## 2026-10-14 独立验收完成

**C24 completed**。上述显式0.11/proof0.8来源合同的R1–R10及C23 A1–A5/A4b独立核验通过：原failure_id继续作为绑定原owner/journal的不透明身份，缺失cause原文不补造；唯一settlement、actual/conservative active-time、safe closure和真实unavailable prefix按原存储验证。未接纳Backend claim保持原bytes/preimage与Session绑定，不获得Host seal/注册/停止authority。

共同冻结输入full4578/legacy325、owned1410/645、16双fresh、8个四消费者188组拒绝及七停止route均独立复核通过；旧/default与正式owners保持，本轮无代码变更。C23仅ready，B04仍blocked/owned0-of-144。证据及验收输入/文档交付边界见[C24完成记录](../completions/B00C24_COMPLETION.md)。
