# B00C27 Completion Record

## 2026-10-14 执行入口

- Status：**in_progress，未completed**。用户“执行C27”授权后review → ready冻结 → in_progress；C26/B04仍blocked。
- Changed：当前完成入口快照与容量核验，实施和整票验收尚待完成。冻结仅在worktree，无commit/push。
- Verified：当前输入与C27只读审查一致；4926文件快照、manifest、既有diff和45份冻结正文摘要已保存。执行根：`/private/tmp/lqcd-agent-b00c27-execution-20261014-4tnw5c0n`。
- Capacity：280个已关闭、无引用旧生成目录经9批归档及成员字节/权限/链接验证后清理展开副本；26674个保留根完整。净归档节省约3.28GiB，可用约13.18GiB；完整当前输入计划约12.78GiB，含完整外部根、四阶段gzip、raw/调用/manifest、开发及meta、私有副本和2GiB余量。新raw无损压缩实测外推约0.105GiB、预留0.25GiB。每批重估，不能减少集合。归档：`/private/tmp/lqcd-agent-storage-c27-preflight-z7pwmvr5`。
- Follow-ups：先完成两个合同补充，再完成下列共同责任；本入口不代表专项或full已通过，不代计B04 owned。

### C26 原要求承接表

| C26 条款 | C27 必须完成的工作 | 入口状态 |
| --- | --- | --- |
| 1 原生捕获 | 原receipt/source/typed producer及实际PID、四阶段链 | partial候选，待完整验证 |
| 2 闭合声明 | proof0.9/fault_sources、独立anchor、明确null边界 | 待实现 |
| 3 快照/差异 | 完整SQLite与文件，精确fault/recovery/repeat及窄CAS | 快照partial，差异待实现 |
| 4 来源边界 | 外部binding定位anchor，S3/live，再私有解析，重算hash拒绝 | resolver候选，独立验证待实现 |
| 5 失败语义 | 旧拒绝保持，真实不可用后态及安全/authority边界 | 待专项验收 |
| 6 全144 | 18 boundaries，原工厂双fresh source-bound exact | 待全量验收 |
| 7 C25 lifecycle | 原29项、局部合法绑定、伪造正式结果拒绝 | 原局部修正待当前输入回归 |
| 8 拒绝/敏感性 | 四阶段/完整closure/来源/重绑/实际变化 | 待实现验收 |
| 9 四消费者/回归 | full原4578+新增、legacy325、同Session1410/645、15/11/30/28及具体47/144/15 | 待整票验收 |
| 10 独立交接 | C27整票完成后C26逐项复核，再B04入口 | 尚未具备条件 |

C27额外要求：父恢复HostIdentities完整case namespace/连续ordinal/真实分配证明、两类CAS增量及派生prefix完整验证、allow/halt/race等全入口审查。C26/B04冻结正文、旧解释、registry/owners、131/84/47、2199/324/28/144/15保持。

## 2026-10-14 实施与专项验证（整票验收前）

- Changed：完成显式0.12/proof0.9独立anchor/闭合proof、完整SQLite与文件快照、实际call/contender/分配来源、精确fault/recovery/repeat验证；原两类CAS、Human allow/halt、terminal index/checkpoint、A03投影删除和fresh Analysis tree均按原合同验证。
- Verified：`source-native-v3-results.json`的9组18份fresh source-bound主trace exact；`specialized-v2.log`119 passed。初轮117 passed/1 failed为新matrix排序遗漏，已修正且原失败保留。`source-controls-v5/v6`保留ledger parser与物理hash投影两个开发失败，按已批准C26原规则补齐；`source-controls-v7-results.json`5个control分支全部通过，首项两fresh exact。最后两项针对parser/回滚callback的专项另存日志。
- Scope：生产、Phase A、registry/owners及45份冻结正文未改；36条原factory assert全部保留；8个resolver文件逆变换AST与C26执行前相同。新expected来自两份实际fresh normalized相等的原生证据，原expected未修改。
- Follow-ups：固定最后代码/文档输入后执行原4578加全部新增测试、同Session独立B02/B03、144双fresh、construction及具体final缺口；当前不是completed。所有路径在本记录执行根，后续交付文档另存manifest，不retag Session。

### 完整验收前容量复核

- 首次最终容量复核失败：可用11.85GiB，保守需求12.17GiB。保留失败报告，没有启动full或删除旧证据。
- 按本票允许的新快照无损压缩范围，使用标准库XZ保存新content-addressed blob，原gzip捕获保持。15组完整样本逐blob解压/重压/解压字节校验，完整轮估算降至10.75GiB，含原full/external根、raw/anchor/meta、私有峰值及2GiB余量；逐批仍须保留2.5GiB。报告：`final-capacity-xz-preflight.json`。
- `source-xz-regression.json`：原grant owner race缺失snapshot及started CAS各两fresh完整主trace exact，新增XZ来源通过；旧gzip预算CAS来源只读复验通过。原过程及反例完整保留，不减少原验收集合。

### 首轮完整验收发现的原 index 临时文件消费

- 首轮固定输入`19125aeaa1ab680a4acea0f441c5442b4b60e7d73d23019b062ae235266dbddf`收集4670项，30项原B04 source case启动，29通过、1失败后自动停止；`final-session/full-0717-output.txt`及`full-inventory.json`完整保留。
- 失败为`artifact.index_publication.before.committed_result_replay`的`recovery_removed_file`。真实捕获`/private/tmp/lqcd-agent-b00c26-native-hdmtowfh`证明原`replace_projection`消费`.artifact_index_<原冻结内容SHA>.tmp`，正式index等于同一冻结intent bytes，没有新生产缺陷。
- 在新verifier内补齐精确临时前像/文件名摘要/目标bytes/mode与原owner恢复的关系；normalized显式记载atomic index consumption，实际文件名与bytes留在四阶段证据。没有按扩展名放行删除。专项双fresh及篡改前像拒绝测试1项通过（`atomic-index-regression.log`）。本地实现遗漏属于C26/C27已批准的原publication恢复来源范围。
- 代码及专项增加后必须重新固定输入和完整运行；首轮结果不拼接为新输入通过。新一轮证据写`acceptance-v2/`，原失败及所有native根保留。C27仍in_progress，C26/B04仍blocked。

### 2026-10-15 第二轮来源失败与局部修复

- 第二轮固定输入`05e96253974e67f147ad9c3cd743e54b735cd7b3c0ed2fad45ae5fb03431d302`、Session `4110e26483ed8aa9d4986a23f6f1bbf8394f8258fe90a4af26bdd426d96481cf`保留90个source case通过和1个失败；未形成完整通过声明。driver在IPC环境交接时只接收中断并等待已排队批组，所有原子进程报告保留于`acceptance-v2/`。
- 失败`budget.resource_settled.after.integrity_conflict`来自被动collector在损坏index后、报错前写出无效prefix，违反精确S0→S1差异。新collector先使用原严格JSON parser读取index；新verifier在无completion intent的原invocation integrity fault中独立验证捕获字节的原parser拒绝，后态raw保持null。旧S0历史prefix可合法重读，不强迫旧normalizer拒绝，也不以S0替代后态。原损坏bytes及失败原生来源完整保留。
- `corrupt-index-regression-v2.log`两项通过：新增损坏index无派生写入/原parser拒绝双fresh；既有atomic index精确消费/篡改拒绝。修复仅涉及新collector/verifier及专用meta，原production/旧规则/工厂断言未改。
- 第二轮construction B00/B01/B02为15/11/30；B03首次本地Unix socket受sandbox限制，允许本地IPC后原CLI完整重跑28/28通过，见`acceptance-v2/final-construction/B03-ipc-report.json`。该输入结果不拼接为第三轮通过。
- 第三轮在重新实测容量、冻结新输入后执行原4578加94新测试及144双fresh；原300秒outer/60秒child timeout和集合保持。C27仍in_progress，C26/B04仍blocked。日期按客户端2026-10-15，原主执行目录名称保持。

### 2026-10-15 第三轮 Grant failure 来源补全

- 第三轮固定输入`d7ec85095da9c0b24db744be2fc938e58bdf0c168a4cc41494e77b42a4f5ab01`、Session `1c547ec3971c994cb35ff6d1793b190ef60c58c93f2c971c5076e9fb67562ec0`收集4672项；`acceptance-v3/partial-run-inventory.json`保留72个通过、1个失败的实际原报告，另759/760两个在调度停止时活动的批次未形成完整outer报告。全部内层来源与失败保留，不宣称full完成。
- fresh construction15/11/30/28通过；final逐ID对比原C25只有47requirements/144binding/15adapter。额外四消费者审计替换独立候选材料、重算全部manifest引用及S0–S3链后仍拒绝，原anchor不变，见`rehashed-candidate-audit.json`。这些属于第三轮输入，不能拼接为后续输入整票通过。
- 为缩短耗时，同Session提前运行后段8个互不重叠Grant批次，总并发最多4批；其中1通过、1失败后停止其余调度。主调度随后停止，原300秒timeout未改，没有删除失败。`early-grant-plan.json/results.json`和`source-failure-stop.json`保留调度事实。
- 失败为`budget.grant_transition.after.integrity_conflict`，原生根`/private/tmp/lqcd-agent-b00c26-native-ph39qpu2`，新verifier报`foreign_control_owner`。原`TerminalOperations.fail_advance`按真实parent failure创建关联close_run；损坏ledger使原close停于terminal_ownership_reserved/failed，closure unavailable、run_status null，无新domain文件写入。不是新生产失败，而是新verifier未覆盖已批准原Control recovery关联owner。
- 局部修复仅在新0.12 verifier中，逐字段绑定原advance owner/phase/error、旧control heads、frozen policy、close request/reservation/trigger/precondition/Host allocation和原unavailable closure；不允许任意foreign owner，不制造terminal publication。原失败来源只读重验通过；`grant-close-regression.log`实际原工厂双fresh专项1项通过，两个fresh均保留failed/unavailable/null及重复无effect。C27仍in_progress，C26/B04仍blocked，完整新输入验收待完成。


### 第四轮入口与容量

双fresh Grant close专项1项通过后停止全部测试，重新扫描3191个临时目录和完整引用闭包（读取约66.79GiB）；28658个来源根保留，仅2个关闭且无引用目录可清理。先无损归档、逐成员bytes/mode/link校验，再移除展开副本，净节省约90.6MiB；保护根无缺失。审计`/private/tmp/lqcd-agent-storage-c27-resume-yeusay3y`。系统同期可用空间变化不计作本次清理收益。旧native/sealed/反例保持。

第四轮容量复核沿用原10.75GiB保守需求（含完整外部根、快照、meta、私有峰值和2GiB余量），没有降低预留强行启动。证据`acceptance-v4/capacity-preflight.json`。固定新输入后先跑Grant完整性故障及其他Grant分支，再覆盖原全部144和完整4673（原4578+95新测试）；同Session独立owned、fresh construction/final及来源审计仍必须完成。原失败不拼接、不重标，不改原超时。

## 2026-10-15 第四轮停止、必要父目录修复与容量阻塞

- Status：**blocked（资源门禁）**；C26/B04仍blocked，没有completed或B04 ready声明。
- 第四轮固定输入`5e24d94e7a8c05ed450fbb40c9d0fe48edd7c16dd1b67ec5b58411bfa03da004`、Session `f1d845be7a934a55e0a46d5f9f09a332f35f2f743202a30dfe85bbac589b651d`选中4673项，在原source144组保留**133通过、1失败**后原调度自动停止；完整suite与owned尚未完成。Grant40/40和Human allow/halt16/16在该输入通过。独立来源审计保留133份通过记录，没有伪造全部144完成。
- 同第四轮输入fresh construction **15/11/30/28**及final原具体ID **47/144/15**通过，四消费者完整重算候选链仍拒绝。修复后必须重跑，不能拼接为新输入验收。原始报告位于`/private/tmp/lqcd-agent-b00c27-execution-20261014-4tnw5c0n/acceptance-v4`。
- 失败`budget.resource_settled.before.committed_result_replay`为新verifier的`call_snapshot_continuity`遗漏：原collector在first recovery后首次写入合法C22 prefix时，同步创建`trace_prefix_evidence`父目录；完整差异仅该目录及一个逐字段验证的prefix文件，没有新增业务effect。反例`/private/tmp/lqcd-agent-b00c26-native-l_jn1l5x`完整保留。
- Changed：仅新`fault_source_trace.validate_calls`允许已验证prefix所需的精确root级父目录；原目录变更、空的无来源目录、额外目录/文件和错误类型仍拒绝。新专用meta通过原工厂两fresh验证合法路径并拒绝错误目录类型/额外目录。没有改原工厂动作/断言、production、旧normalizer、case/owner或冻结正文。
- Verified：`prefix-directory-regression.log` **12/12**（失败项及此前未运行的10个source case各两fresh，另1项专用父目录测试）；`prefix-final-specialized.log` **125/125**（C26/C27新增96、原C25 29）。`prefix-directory-counterexample-audit.json`证明原失败捕获经新校验器只读通过、没有重执行effect；原失败envelope仍保留failed。当前输入`39777bae121645be15e90a670395f3691e710cdc373f6cd26d62facc7a105faf`全仓exact collection **4674**，不是全量运行通过。Phase A validator、generated byte-equal、compileall、diff及scope检查通过。
- Capacity：再次扫描3285候选目录及约73.56GiB引用，29727保护根保留，**0可安全清理**，未执行删除；报告`/private/tmp/lqcd-agent-storage-c27-prefix-resume-d1vxny1h/review.json`。交付时可用5.75GiB，完整重跑仍按原保守10.75GiB需求，差约5.00GiB；没有降低2GiB安全余量或2.5GiB批次门禁。见`prefix-capacity-final.json`。
- Follow-ups：容量恢复后重新核对输入/冻结摘要，按原执行授权恢复ready再启动；运行完整4674、全部144双fresh、同Session独立B02 1410/B03 645、fresh15/11/30/28与final具体47/144/15，再做C26原条款独立审计及B04入口。`acceptance-v5-pending-capacity/`仅准备脚本，无Session/运行/完成报告；旧轮次不retag。本次局部修复不需要新增纠偏票，但资源问题未消除前不能宣布整票通过。
- Scope：45份冻结正文、原36条工厂assert、163个原反例文件及src/legacy/registry/owners保持；131required/84mapped/47remaining、2199cases/324boundaries/28post-claim、B04 18/144且owned0、15exit及PhaseBfalse保持。文档/lifecycle交付与专项输入分别manifest，无commit/push。

## 2026-10-15 用户授权清理临时文件后的容量复核

- 本轮仅按用户要求清理临时文件，未恢复票据lifecycle、未执行C27全量或B04产品工作。C27/C26/B04保持blocked；当前容量门槛已满足，后续按原执行授权重新入口核验后接续完整验收。
- 已关闭的7个compileall字节码缓存删除，减少42.49MiB；旧清理过程中保存的99个gzip fixture备份由5.70GiB无损重压缩为0.58GiB XZ，逐份验证原压缩SHA、完整解压tar SHA/bytes一致，保存映射后删除冗余gzip副本，净减少5.13GiB。
- 原1184377个tar成员的内容/mode/link和原manifest/verification报告保持；各备份目录新增`ARCHIVE_FORMAT_HANDOFF_20261015.json`和`RESTORE_CURRENT_20261015.md`。旧gzip路径为历史格式，恢复时使用映射中的tar.xz；三个代表成员按原manifest SHA/size/mode抽查通过。旧native/sealed及当前反例未删除，不把损坏或引用中的运行根当垃圾清理。
- 清理删除合计约5.17GiB（未扣新审计记录少量占用），容量复核可用15.14GiB ≥ 原10.75GiB需求。系统同期可用空间波动不计入清理收益。当前源码/原冻结正文未变，清理前后4944个仓库输入exact一致；29856个临时来源根仍存在，163个原反例文件SHA保持。随后仅追加本记录及Docs/Current State说明，单独保存交付manifest。
- 审计入口：`/private/tmp/lqcd-agent-storage-c27-user-cleanup-pcampdmz`，包括`cleanup-result.json`、`recompression-verified.jsonl`、`archive-removal-journal.jsonl`、`bytecode-removal-manifest.json`、恢复抽查及仓库before/after manifest。全量4674、同Session owned1410/645、全部144双fresh、fresh construction与C26/B04独立交接仍待执行；没有拼接旧结果或retag，无commit/push。

## 2026-10-15 第五轮恢复执行入口

- 用户再次授权继续C27；清理交付输入1007a4c3c4edccf821f6d6f050df1f635e951db559a7da96070f83153558958c exact核对，4944文件执行前快照、manifest、diff及45份冻结正文保持。C27 blocked→ready冻结→in_progress；C26/B04仍blocked。
- 当前可用15.05GiB，沿用原10.75GiB完整需求及2.5GiB批次门槛，不降低集合、timeout或余量。第五轮根`/private/tmp/lqcd-agent-b00c27-execution-20261014-4tnw5c0n/acceptance-v5`，全部失败轮次和来源保留。
- 本轮先运行96个新增meta，再原144来源各两fresh及全部原测试，完整4674；同Session独立B02 1410/B03 645、fresh15/11/30/28与原具体final47/144/15、C26逐项独立审计及B04入口尚待实际通过。先前125/12仅保留历史专项，不拼接新输入full。没有完成声明、commit/push或B04产品实施。

## 2026-10-16 整票验收完成

- Status：**completed**。用户执行授权后ready冻结并完成实施；冻结正文只在worktree和执行前快照保存，无commit/push。
- Changed：显式trace0.12/proof0.9、新原生四阶段anchor、完整文件/SQLite来源、精确fault/recovery/repeat及原调用/Host分配证明；原CAS真实delta、Human父恢复identity、原index临时文件消费均受窄规则验证。C26全部剩余实现由本票承接。
- Verified：固定输入完整**4674/4674**（原4578、新增96、legacy325），原**18 boundaries／144 cases各两fresh**，288份native request/envelope/hook/receipt/anchor与主trace exact；collector/matrix/runtime/exit正负来源、新旧拒绝、材料敏感性及无effect重读通过。C25原29项保持；全部meta属B00，B04 owned仍0/144。
- Verified：同主Session独立**B02 1410/1410、B03 645/645**；fresh原CLI construction **15/11/30/28**；final原具体ID集合保持**47 coverage／144 binding／15 exit adapter**，没有其他错误。
- Scope：45份冻结正文、原36条工厂assert、production/legacy/registry/owners及163个原反例文件保持；8个旧来源模块仅原已批准resolver接缝，逆变换AST审计保持。协议validator、generator check、compileall及diff通过。131required/84mapped/47remaining、2199cases/324boundaries/28post-claim、15exit及PhaseBfalse保持。
- Execution note：第五轮同输入保留96项meta及10个source case通过、两个outer 300秒超时；四个内层原生结果均通过。两个case串行诊断分别211.40/209.03秒通过。第六轮恢复Grant串行、延后只读审计，完整4674重新执行；原失败不删除、不重标。construction与四消费者重算候选审计复用第五轮同输入实际报告，路径见`reused-current-input-evidence.json`，未声称重新执行这两部分。
- Capacity stop：第六轮在4198及4216项实际通过后，两次由原2.5GiB门槛阻止下一批启动。受阻批均没有pytest request/envelope，没有实际测试失败；原停止清单、日志及通过envelope摘要分别保留于`capacity-stop-001`和`capacity-stop-002`。补足容量后仅在同一输入/Session继续未启动项，最终仍由原validator完整复核全部4674项。
- Batching correction：原10-node重来源批次full-0535触发300秒outer超时，只有8个stdout进度点、无完整envelope，未把它计为通过。保留`batch-timeout-001`及原request/stdout/原生来源，将该批全部10项和其余未通过项共155项拆为单项，在同一输入/Session、原300秒、2 workers下fresh重跑。原4519项通过envelope逐份SHA保持，未删除失败或修改验收集合。
- Capacity cleanup：完整suite期间，以完整引用扫描及后续增量扫描确认643个已关闭、无证据引用的临时fixture；逐成员bytes/mode/link核验XZ归档后回收展开副本，净回收10.24GiB。每轮保护根均无缺失，全部native/sealed/当前反例及旧99份归档保留；完整清单与归档位置见`inflight-cleanup-summary.json`。系统同期释放的其他空间未计入本清理，不修改源文件、不过滤失败。
- Evidence：`/private/tmp/lqcd-agent-b00c27-execution-20261014-4tnw5c0n/acceptance-v6`。原主Session `d2d6bb33792d3bebbc2753543210efc7b5ff4fbe6869356b38949a103903d187`，固定输入 `ffb712c5f3acdeda20302de658ed18689a26bf8ab8f93678d844dbbfa146ec89`。`C27-final-acceptance-audit.json`、`native-144-source-audit.json`、`final-session/repository-verification-report.json`、`full-inventory-fine-batches.json`（原容量停止清单另存）、owned与construction/final原始报告完整保留。首轮失败、局部修复、容量未通过记录仍在上级执行根，没有拼接或重标旧Session。
- Handoff：C26原Requirements 1–10另行独立复核通过（`C26-independent-acceptance-audit.json`），C26 completed；B04还须独立入口，只恢复ready，不代计原47construction/144owned或保证剩余产品验收无新问题。随后仅文档/lifecycle交付另存manifest，不声称修改文档后重新运行全套。
