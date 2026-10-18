# B00C26 Fault Source Candidate Status

2026-10-16 状态：**C27/C26已completed，显式0.12/proof0.9来源合同已交付**。C26原Requirements 1–10经独立审计通过；B04经独立入口恢复ready，正式owned仍0/144。下方实施中/候选条目保留历史，当前字段规则以本合同及C27批准补充为准。见[C27完成记录](../completions/B00C27_COMPLETION.md)和[C26独立交接](../completions/B00C26_COMPLETION.md)。

2026-10-14后续：C27已获批准并实施显式0.12来源候选，以下C26停止条目是历史状态。完整独立交接仍待验收；当前合同与阶段/调用/CAS/fixture规则见[C27补充](B00C27_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_CONTRACT.md)。C26/B04保持blocked。

2026-10-14：**C26 blocked；以下仅记录局部候选，不是已生效的0.12/proof0.9来源合同。** 原0.1–0.11/default保持，`trace.py`尚未开放0.12；完整projector及四消费者未交付。

见[冻结C26](../phase-b-graph-harness/B00C26_B04_FAULT_SOURCE_AND_OWNED_ACTIVATION_HANDOFF.md)、[实际记录](../completions/B00C26_COMPLETION.md)和[合并补充待审C27](../phase-b-graph-harness/B00C27_B04_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_FIXTURE_HANDOFF.md)。

- 已有候选：仅显式`LQCD_C26_FAULT_SOURCE=0.12`下的native node/已消费真实receipt检查、原0.11 S0前态校验、固定Session/case目录的S0–S3记录链和exclusive-create anchor、完整来源manifest及gzip字节、SQLite私有副本逻辑行对照、有界来源读取接缝。原工厂全部动作与assert AST保持，默认C25路径不启用捕获。
- 新捕获保留原回滚callback；后态被动collector从已验证durable的S0观察接续，不能把原child回滚的phase在新epoch相同revision上解释成新owner观察。六类局部预检及六份S0私有视图exact通过；这不是全部144或新版本接受证明。
- 未完成：闭合proof0.9/0.12 dispatch、独立anchor/原始call/完整closure验证、严格故障/恢复差异projector、四消费者和全部负向/敏感性、144双fresh及完整当前输入验收。被删除capability的原collector错误尚须转为独立原validator拒绝证据；不可将TypeError本身当作完整来源证明。
- 暂存manifest为闭合`schema_version/roots/files`；root含`id/path`，文件含`root/path/type/mode/sha256/size`，SQLite附属文件缺失明确为absent。原root层collector诊断文件单独绑定、不作为Run业务文件；Run/control/workspace/aux完整保留。当前gzip按完整bytes SHA保存；最终合同及任何存储优化仍须符合冻结C26的独立重验与完整清单要求。
- 当前两个冻结约束缺口：原无重复effect的publication重放仍真实CAS revision+1；原Human后续Pause在父恢复中产生非确定UUID。不得把CAS当SQLite物理噪声，亦不得忽略Host身份取得exact。待C27明确窄补充后，完成本票所有剩余验收；现不授予任何生产authority、不恢复B04。

本轮未改变production、原hook/Session协议、case/owner、registry/matrix、旧expected和冻结正文。后续不能将本候选状态文档引用为已完成验收。
