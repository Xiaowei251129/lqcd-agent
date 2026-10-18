# B00C25 Process Session Binding Contract

2026-10-14：**C25 completed**，下述候选合同已按冻结要求验收：4578全量、144双fresh原生诊断及原反向校验通过。C24独立入口通过后仅ready；C23/B04保持blocked。原正式B04 owned0/144保持。见[完成记录](../completions/B00C25_COMPLETION.md)。下方为实施时记录，合同内容保持。

2026-10-14：C25 **in_progress**；以下为候选实现，整票验收尚未完成。C24/C23/B04保持blocked。

- 四类原spawn入口通过显式原process-hook request交接binding。子进程上下文检查字段、真实spawn身份、项目、case、nonce、receipt路径和digest；current_binding仍优先使用原父pytest Writer，无明确上下文时保持unit-only。上下文复制来源，正常退出/异常恢复；foreign嵌套拒绝。
- 原父进程继续通过consume_process_hook验证原pending request、Session/node、nonce、PID、真实production hook和退出97。新上下文不替代原验证，不产生生产authority。
- 原144外层case各启动两份fresh native诊断Session；原case与故障/恢复断言在内层执行，实际hook、request、envelope、source/raw/normalized/result路径及字节摘要保留。局部registry仅证明诊断hook的case/边界，不产生owned case_results；原工厂phase摘要不代表B04正式Run source acceptance。
- 外层完整Session从生成时就没有这些诊断hook；内层完整保留，调用原validate_pytest和validate_runtime，再检查实际factory结果及双fresh exact。任何内层失败传递到原外层node。没有取消ACTIVE、伪造Writer、事后删hook、缓存旧结果或过滤失败。
- 正式registry/matrix/validator保持。原未绑定B04 hook在canonical validator继续拒绝；B04仍0/144和47construction，原owners与PhaseBfalse保持。

见[冻结C25](../phase-b-graph-harness/B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md)和[实际记录](../completions/B00C25_COMPLETION.md)。
