# B00C20 — C10 当前普通失败的显式来源交接

2026-10-08 accepted status: C15–C18 and C20 have independently completed their original requirements against the same final native Session (4139 exact tests, B02/B03 owned1410/645, construction15/11/30/28). Earlier candidate/blocked status statements below are retained as dated implementation history. The independent completion records contain the current evidence and lifecycle. B04 has separately passed its entry review and is ready; its remaining47/144 work and Phase B completion are not claimed here.

[冻结 C20](../phase-b-graph-harness/B00C20_C10_CURRENT_FAILURE_SOURCE_VERSION_HANDOFF.md)只授权当前 C10 测试入口使用既有 trace0.8/proof0.5。实际验收与状态见[独立 completion](../completions/B00C20_COMPLETION.md)，当前候选不代表完整 suite 已通过。

`helpers/ordinary_mixed.py::no_code_trace` 新增显式 `trace_version`，仅接受0.6/0.8，默认0.6。0.8复用原 ProductFailureSources及其被动observer，收集原Host的failure来源；原Agent、输入、时钟、selector、reservation/settlement、Invocation/producer完全不改。未知值在创建Run及调用effect之前拒绝；不根据运行结果自动升版。

原 C10 structured failure nodeid只追加显式0.8参数，保留真实Analysis失败返回、Coordinator/Human paused和来源通过的原断言。新专用测试验证Planner/Analysis各调用一次、两个原reservation各有唯一actual settlement、failure occurrence=1、无maximum/Grant。重读前后Run文件字节、SQLite全部持久化逻辑内容及effect计数保持；SQLite的临时读锁文件不当作领域写入。

新旧版本检验使用同一实际材料。0.6/proof0.3移除两项0.8声明和0.7新增的ordinary_maximum_settlements（先证明该列表为空）；0.7/proof0.4仅移除两项0.8声明。原events、公开objects、Agent输入/返回和member bytes全部保持；两旧版本须准确按failure_member_source拒绝，不能用字段集合错误替代来源拒绝。原默认0.6在真实当前failure下也继续拒绝。

## 当前端口调用点清单

| 入口 | 实际材料 | 显式版本与处理 |
| --- | --- | --- |
| C10 structured failure原nodeid | Analysis领域失败、真实Host因果FP | 0.8；本票唯一原测试升版 |
| C10 no_code模块fixture/双fresh/四消费者 | 无失败、正常完成 | 默认0.6不改 |
| C10 changed reviewer risk/Changed科学成员 | 无领域failure或新增FP | 默认0.6不改；原material断言保留 |
| ordinary_mixed::primitive_trace | 原资源成功、unknown及exception/overrun unsettled前缀 | 固定0.6不改 |
| ordinary_mixed::mixed_trace | 原B03 Code/fresh Analysis组合，无新增产品FP | 固定0.6不改；原fixed expected按既有审计保持 |
| ordinary_maximum::maximum_trace | 原primitive maximum/exception/clock/usage与安全关闭来源 | 固定0.7不改 |
| b04_product_sources::product_trace | Host exception/overrun/clock失败，或Planner风险控制路径 | 固定0.7不改，未冒充domain failure |
| ordinary_human及C13/C15/C16/C18当前Human/Code调用 | 已批准的当前领域failure/Grant/repause来源 | 原显式0.8不改 |
| C20旧默认负例与同材料降版 | 当前真实failure | 明确证明0.6/0.7拒绝，不作为新正向入口 |

完整位置扫描保存在本轮执行根current-version-call-sites.txt；固定旧JSON/sealed evidence没有实时端口，不升级或retag。最终完整exact suite仍须检查这些调用点之外的兼容性。

## 消费与完成边界

新B00 meta只引用A07-META-006/015，双fresh原端口对比完整normalized固定expected。collector、matrix、runtime validator、exit digest分别验证实际材料及missing/duplicate/foreign/stale拒绝。科学返回值的合法变化必须改变完整normalized与FP；伪造返回/来源拒绝。不改production、旧projector、case/owner/required或B04 owned。

C20修复并核对输入后按原授权恢复C18最终验收。C15/C16/C17/C18逐票引用同一合格固定Session，独立复核原覆盖表后才completed；不靠历史累计passed、也不为每票重跑不同输入的完整suite。B04仍须独立入口复核，Code parent/四层fallback/fresh Analysis产品集成、ordinary通用publication接续与47/144归B04；本票不自动完成B04。
