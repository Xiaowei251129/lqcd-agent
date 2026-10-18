# B00C14 Host 身份拒绝断言交接

2026-10-05。由[冻结C14](../phase-b-graph-harness/B00C14_HOST_IDENTITY_REJECTION_ASSERTION_HANDOFF.md)授权；执行状态和实际验证见[C14记录](../completions/B00C14_COMPLETION.md)。只交接测试断言，不改变production、trace/proof、旧来源合同、normalizer或owners。

原Agent在原compiled graph返回foreign run_id，生产端口在domain member写入前抛reserved Host fields。原测试应核验一次实际effect、同资源真实reservation/actual settlement、typed unknown tokens/cost、没有domain注册/后继Work/accepted memory。异常返回不构成Run completed/halted或安全停止证明。

独立member反例从真实正向0.6 trace的已验证来源取内存副本，重算恶意成员的SHA/size和registration声明后进入原member projector，明确要求host_identity拒绝。它只测试该校验层，不能伪装生产证据或完整trace；原full normalize、bytes/registration/owner反例保持，真实Run与源trace不修改。

原nodeid、observe IDs、matrix和expected保持，B04_owned=false。正式验收需新固定输入Session完整suite、B02/B03 owned、fresh15/11/30/28和exact原47/144/15负向缺口。C14完成只交接C13原验收；C13完成及B04独立入口复核前B04仍blocked。文档交付输入与固定验证输入分别审计，旧完成历史不重写。

2026-10-05完成：正式固定Session3792/3792、同Session owned B02 1410/B03 645、专项78/29、fresh15/11/30/28及final具体47/144/15集合均通过；原端口事实保存在C14执行根。C14completed后C13仅恢复in_progress，B04保持blocked/0-of-144。验证后的文档/lifecycle输入单独审计，实际证据以独立completion为准。
