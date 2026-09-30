# B03 Maintenance Record

## 2026-09-24 — Verification resources in the original resume transaction domain

- Ticket：[B03](../phase-b-graph-harness/B03_GRAPH_MANAGED_FAKE_CODE_AGENT.md)，既有 Allowed Files 内的 resource binding、invocation fencing 与 consumption failure 接线；不更改 A04/A05/A06 合同。
- 原因：B02 consumer 在单个 SQLite writer transaction 内执行，且 effect/completion 只接受 Attempt started 时的 ledger head，无法容纳独立持久化的 verification reservation/settlement。
- 改动：normal external consumer 在 writer 外运行；member publication 使用短事务及原 resume owner/invocation 双重 fence。独立命令预留与结算保存在已有 capability row 的精确 publication journal，复用原 budget record/replay 与原 resume 失败收尾。未新增预算 authority、数据库或可重跑许可。
- 恢复：进程中断只补齐已经提交的精确 ledger/index suffix，随后由原 resume 关闭失败；已有 completion intent 才能恢复完成。过期 worker 不能继续结算，pending reservation 由原 owner 保守计费；其他 attempt 的资源不改变当前 completion 条件。
- 不可追加分支：Run index 被篡改时，failure snapshot 从已验证的 durable journal 保留全部 pending verification IDs；这些历史记录不构成当前可追加 authority，不允许据此伪造 failed lifecycle。
- 验证：11 项资源测试覆盖预算耗尽、重复命令、consumer error、authority tamper、过期 lease 以及五个真实新进程 crash/recovery 边界。相关 B02 回归初次 163 passed；增加历史 journal 保留后继续定向复验。日志位于 `/private/tmp/lqcd-agent-b00c08-review/`。
- 限制：这些测试不计 canonical Backend/Bundle/Analysis 或 B03 的 28/645 验收；最终 full suite、同 Session runtime 和来源 golden 仍须整体验证。

### Resume takeover follow-up

授权尚未消费时，合法接管后的首次 invocation 必须绑定 acquire 时的 resume epoch，而非旧 authorization 的 producing epoch。已将该绑定保存在 invocation lease 私有元数据，并在 started publication、资源和 member/completion 的共同 fence 中验证；这同时阻止仍持有 invocation lease 的旧 resume worker 继续写入。单个 verification timeout 也必须完整落在当前 resume lease 窗口内。

基础回归 **294 passed**；上述 epoch 修复后，12 项资源/恢复与 external consumption、failure closure 定向复验合计 **108 passed**（`continued-focused.log`、`epoch-regression.log`）。其中新增真正的授权提交后、首次 Attempt started 前的进程退出与 epoch 2 恢复。未重跑完整 suite，未计 B03-owned acceptance。

### Workspace recovery follow-up

新增独立 immutable Git base 的只读 materialization、全树 path/type/scope 检查及 managed workspace identity 校验。Private device/inode ownership 不进入 public content digest。Physical workspace 在 core 后 create-new；中断恢复只补同 owner、同 bytes 的预计算文件，未知或替换 root 拒绝。

新进程在 `external.workspace_materialized/after` 退出时，恢复流程会重读此前 core；原 phase gate 错误拒绝这个无副作用读取。已允许该 phase 下复核并返回 exact core，不重新推进 phase 或覆盖内容。Prestart **23 passed**（10 个进程故障边界），workspace **14 passed**；Unix socket 负例只在 `/private/tmp` 创建本地文件，没有网络连接。

活动时间账本表达缺口属于另一个合同问题，未借本 maintenance 实施；见待审 B00C09 与 B03 completion 最后条目。

## 2026-09-25 — Completed Code Attempt before binding release

在 canonical `needs_input` 消费中，Attempt 与其 `attempt_active` 区间可先完成，而原 resume 随后尚未提交 `external_consumption_released`。该边界发生故障时，原 B02 failure closure 错把已结算区间视为未结算，拒绝同一 owner 的安全失败收尾。局部修复只在区间已有唯一 settlement 且 Attempt 已结束时复用该既有记录；仍仅对 running、未结算的 Attempt 追加结算，拒绝 closed interval 与 open Attempt 的矛盾。未改变事件 schema、计费数值、CAS、route 或故障归类。原 required nodeid `test_failure_cas_at_each_claimed_phase_closes_same_operation[invocation_authorized-external_consumption_released]` 重新通过；完整回归仍待 B03 收尾复验。

新进程在已物化 failure disposition 后恢复时，原 `_plan` 用接管进程的时钟重新计算已结算的活动区间，使同一 frozen suffix 的 actual/conservative 形状冲突。现从原 ledger 读取已物化的同一 owner settlement，并用其可信时间和实际秒数重建原计划；`retain_materialized_record` 仍逐字段验证已有记录，只为未发布后缀创建新记录。跨 epoch 的未结算区间继续按 C09 保守结算，可信同 epoch 超限继续作为完整性失败。相关新进程故障节点已恢复通过，完整矩阵仍待复验。

## 2026-09-25 — Verifier 后失败收尾的可信时间

canonical Code 消费在同一 Attempt 内完成多个 verifier settlement 后发生失败时，原 failure plan 仍沿用 resume 创建时的时间，可能早于已发布的 verifier 记录，触发账本时钟回退。现于原 `consumption_failure_stop_verified` 阶段的既有 stop proof 中冻结可信停止时间，后续同 owner 的确定性失败后缀复用该时间；已物化的 active settlement 继续优先复用其原记录时间。未改变协议 phase、required evidence 顶层字段、资源收费公式或 terminal 分类。C09 原计费用例的 synthetic Code 输出不再能通过 A05 canonical registry，故该用例保留 3+6+5（含 2 秒 verifier）计费断言，改以安全可证明的同 owner 失败收尾作为观测点；真实 canonical bundle 正向消费另由 B03 source-complete 用例验证。未结算且越过 parent interval 的 verifier 继续进入 unavailable，不伪造 failed lifecycle 或资源 settlement。定向复验：活动时间四个原失败用例通过、资源 12 passed；全量结果仍待审定。

## 2026-09-25 — schema 0.4 Code pointer guard placement

一次 Phase B 探索性回归发现 B02 human response 构造路径在 `ArtifactEffectPort._human_response_lifecycle_records` 触发 `NameError: state`。原因是 B03 的 canonical Code pointer 完整性检查误置于该函数；此处没有 `state`，且 human response 与 Code pointer 无关。现将同一检查移至 `_has_populated_artifact_state` 的 schema 0.4 分支，只在 state 中存在 canonical Code pointer 时检查六个 state 字段已填充。未改变 A03 slot/invalidation policy、legacy 路径或 B03 接受条件。原失败覆盖的 human/B02 construction 定向回归 **34 passed**；全量与 B03 28/645 尚待最终验证。

## 2026-09-25 — Absent patch symlink must fail closed

正常 Code delivery 不带 patch 时，悬空的 `changes.patch` symlink 会被 `Path.exists()` 当作文件缺席，绕过 preflight 与 normal-final replay 的路径检查。现显式拒绝该 symlink；真实文件仍须经过原 `read_regular` 与 digest 校验，不改变 A05 member/status 合同。原 normal-final 正反路径加入同一悬空链接反例，**2 passed**；完整回归仍待最终验证。

后续同边界审计：`read_regular` 的 `O_NOFOLLOW` 只作用于最终文件，不能替代父目录检查。Backend dispatch 的 `_source` 与 Code delivery preflight 现要求 Attempt control directory 的物理路径保持在原 Run 内；测试将已有目录移走并以 symlink 替换，preflight 在消费前拒绝，恢复原目录后正常重放仍成功。对应 normal-final 选择 **2 passed**，完整回归待验收。

Fresh Analysis 的 member 读取也须验证父目录的物理路径，不能仅依赖最终文件的 `O_NOFOLLOW`。`AnalysisHandoff._source` 现在对每个 Code member 检查该路径仍位于原 Run；同一 symlink 反例直接调用 adapter 会被该检查拒绝，经 public advance 入口则由更早的 A03 registry 路径检查拒绝，均不产生新 Transition。`_run_root` 同时保持 coordinator 根内的物理路径约束；新增负例 **1 passed**。

## 2026-09-25 — Consumption failure unavailable tail after corrupted ledger

B03 的活动时间结算接线在 `ConsumptionFailure.continue_failure` 的每个分支无条件解析 live execution ledger。B02 integrity-conflict 故障注入会使该文件留下残缺行；原 `consumption_failure_stop_verified` 已把 Run authority 判为 unavailable，但额外解析再次抛错，使同一 failure owner 在 `stop_verified` 或 `classified` 提前停下，遗漏冻结的 `consumption_failure_unavailable_recorded` 尾部。此回归独立于 B03C01 的 scheduled prior IDs。

局部修复只在 authority `appendable` 且 stop proof `safe_stop` 时读取 live ledger 以复用同 owner 已物化的 `attempt_active` settlement；其他情况由已冻结的原 source 构造 unavailable 分类及尾部，不读取不可信 ledger。未改变协议 phase、owner、CAS、费用公式、Run lifecycle 或 expected。B02 `continue_execution` integrity-conflict 选择含受影响的 10 项及相邻路径，重验为 **38 passed**；B03 external consumption/Analysis/reservation 与 B02 construction 定向组合 **124 passed**。旧 golden 和全量回归仍由 B03 最终验收。

## 2026-09-25 — B03 construction observations inside B02 calls

B02 construction 的 `construction_trace` 会直接调用既有 external consumption 和 timeout 测试函数。B03 新增的三个 `observe` 随之以 B02 construction nodeid 写出 B03 scenario；timeout 函数被调用两次，还产生重复 observation。B02 的 35 个 pytest 节点本身通过，但 acceptance validator 正确拒绝了这些不属于 matrix 的 scenario/nodeid 组合（`invalid_evidence:observation:identity`）。

局部修复仅在这些 B03 测试函数作为 matrix 中列明的直接 pytest nodeid 运行时写出 B03 construction observation；B02 construction 的既有调用、断言、trace 和 required nodeid 未改。修复后 fresh construction 报告为 B00 **15/15**、B01 **11/11**、B02 **30/30**、B03 **28/28**；B02 单独 pytest 为 **30 passed**。报告位于 `/private/tmp/lqcd-agent-b00-construction-after-2R4uhb/`、`/private/tmp/lqcd-agent-b02-construction-after-sisbgA/`、`/private/tmp/lqcd-agent-b03-construction-after-JLC7ZO/`。B02 1410 与 B03 645 的同 Session runtime 验收仍独立进行。

## 2026-09-28 — Canonical fixture recovery actor and trace 0.5 assertion

B02 原 `external_resume_client` 在新进程中固定使用四项 actor scope；B00C08 适配的 canonical `needs_input` fixture 创建同一 idempotency key 时只使用 `control.internal`、`resume` 两项。重启本应进入原 failure owner，却在 `Same-key request conflict` 被拒，测试父进程只见 EOF。仅在该 helper 已识别的 canonical fixture 分支，恢复进程使用创建请求时相同的两项 scope；旧 synthetic fixture 仍用原四项，生产 same-key digest 校验不变。两个损坏/缺失 snapshot 负例恢复为原 expected unavailable 尾部，定向 **2 passed**。

旧 member-digest 反例曾断言两根 trace 0.5 标准化后仍不同；B00C07/C08 已批准并实施 canonical member 的来源绑定，此断言与现行合同相反。原测试现要求 raw events 与真实 member SHA 在两根不同、完整 trace 0.5 标准化 exact 相同；独立 raw member SHA 篡改仍被拒。未修改 trace 0.1–0.4 投影或其既有 expected。与上项及 recovery golden 定向合计 **22 passed**；Phase B 完整复验另记。

## 2026-09-29 — Expired pre-start aggregate publication suffix

在原producer已冻结aggregate record、ledger/index物理发布进行中、SQLite的`reservation_committed`尚未提交时，进程退出后若setup期限到期，Watchdog直接调用B02 interrupt。`validate_control_root`看到ledger的resource reservation，但ExternalOperation仍无`reservation_digest`，抛出`External reservation source mismatch`，因此无法发布同owner的unavailable尾部。三个可复现窗口为`external.aggregate_reservation.before/after`及`external.reservation_committed.before`；诊断记录位于`/private/tmp/b03_prestart_gap_probe_all.log`。

局部修复限于B03的Code pre-start与Watchdog：Watchdog取得原producer epoch后，若确有已冻结而未提交的aggregate，只物化该原record的精确ledger/index后缀并以原CAS推进`reservation_committed`，然后继续原B02 interrupt。该恢复在过期effect窗口内不接受新aggregate request、Backend调用或新producer；`_materialize_aggregate`在文件写入前复核冻结record、append bytes、index、identity、source control及投影。原期限仍由Watchdog按setup超限处理为`recovery_required`/unavailable，不扩大可执行effect窗口，也不改变schema、资源数值或公开route。

三窗口的期限故障已恢复为真实新进程Watchdog收尾；20项pre-start期限case的两个fresh根trace0.1集合原字节一致，定向 **20 passed**。另以篡改冻结aggregate content的反例确认在ledger/index发布前拒绝，**1 passed**。此前未增补source校验时的pre-start/Fake与活动时间选择分别为 **23/62 passed**；最终同Session及全量仍待B03整票复验。

## 2026-09-29 — Backend stop source integrity and proof classification

Backend dispatch前/后真实进程切点退出后，若原`code_agent_task.json`被篡改，独立恢复会拒绝继续；但Watchdog的stop观察只在Backend status非`unknown`时验证Task/manifest。`before`切点因此可把损坏来源当作safe stop，后续timeout delivery才因无效Task失败；`after`切点会标记`backend_lookup`缺失，却保留全部为safe的stop dimensions，同时把`proof_kind`写成`unavailable`，与既有final classifier矛盾，ExternalOperation停在`termination_evidence_committed`。两种路径都不能形成一致的unavailable final。

局部修复只在已记录`dispatch_started_at`的原操作上，无论Backend lookup是否为unknown都验证冻结Task、manifest及其原producer/digest绑定。Backend lookup、cancel或来源验证缺失时，若物理stop dimensions全为safe，也把原操作的`termination_or_not_dispatched`判为`unknown`并记录该缺失；不把无法绑定到可信Backend来源的containment观察伪装为完整safe stop。既有公开proof字段、CAS、资源计费、route和pre-start未dispatch规则未改。两个真实before/after切点的完整性反例现在先由两个新进程拒绝篡改来源，再由两个新进程取得并重放同一个`external_final_evidence_committed / recovery_required / unavailable`尾部；Backend分别保持unknown/completed且未二次dispatch。相关5项定向 **5 passed**，三项新case的双fresh根trace0.1集合原字节一致，摘要`66fd94e86a32e541782fe2abd9ee6531915e00109cb661488c9b9b9fbdf45861`，原始集合在`/private/tmp/b03-dispatch-remaining-final-one.json`与`/private/tmp/b03-dispatch-remaining-final-two.json`。相邻回归及整票验收仍待后续固定输入结果。

相邻回归发现pre-start stop intent尚未拥有`dispatch_started_at`键，新校验初稿若以必填键读取会使原deadline恢复抛`KeyError`。已改为读取可选值，仅真正发生dispatch后验证Task/manifest；初始stub、20项pre-start期限故障及两项损坏Task尾部定向 **23 passed**。探索性Phase B排除尚待最终来源审定的5项A05 golden后执行到 **109 passed、5 deselected**，主动中断以优先完成B03定向固定输入；这不是全量通过证据。上述双根集合在最终来源校验代码下仍需复核，整票验收仍未完成。

后续复核中，Backend dispatch三项来源冲突/不可用case的两根raw trace集合再次exact相同，摘要仍为`66fd94e86a32e541782fe2abd9ee6531915e00109cb661488c9b9b9fbdf45861`，保存在`/private/tmp/b03-dispatch-remaining-stable-one.json`与`/private/tmp/b03-dispatch-remaining-stable-two.json`。包含该局部修复的B03绑定集合先后在同一fresh Session通过153/153、161/161、175/175及181/181，最近报告见[执行记录](../completions/B03_COMPLETION.md)；整票645项及前置全量仍未完成。

## 2026-09-29 — Uncommitted normal-final candidate and interrupt publication

真实 `external.final_evidence.after` 或 `external.resolution_cas.before/after` 进程切点可留下已落盘的 normal final 候选，但原 SQLite CAS 因进程退出未提交。独立恢复若原 Backend lookup 不可用，Watchdog 取得 interrupt owner 并冻结 unavailable termination evidence；原代码随后把 interrupt final 写入同一个 `external_final_evidence.json`，因 normal 候选的不同字节抛出 `Conflicting publication bytes`。Run 被标为 unavailable，但 ExternalOperation 停在 `termination_evidence_committed`，不能判为完整的 unavailable final。该问题由 `/private/tmp/b03_normal_final_probe.py` 的 `external.final_evidence.after.non_materializable_domain_gap` 真实恢复探针复现，与 golden 无关。

局部修复仅限既有 final publication：若原文件是同一 producer/Run/Attempt/Cycle、同一 receipt/result digest 的未提交 normal 候选，interrupt/cancel final 使用同一 owner 决定的独立不可变文件名，并保留候选原字节。非 normal、无法绑定原来源或同 owner 冲突仍拒绝，不以新文件掩盖损坏证据。没有改变 resolution CAS、proof classifier、schema、收费、Backend dispatch 或 consumer authority。新 case 检查原 Backend terminal receipt/result不变，正常恢复只查询原操作、完成 normal CAS；完整性反例由两次新进程拒绝；domain-gap由同一 Watchdog owner完成并重放 `external_final_evidence_committed / recovery_required / unavailable`。Run前缀和normal候选字节均保留。

24项 normal seal/final publication/CAS case 在两个独立fresh根的trace0.1集合exact相同：`/private/tmp/b03-normal-final-audit-one.json`与`/private/tmp/b03-normal-final-audit-two.json`，摘要 `a10660782711ebfb0220e4a3eb13f38c03948928b9d5ee2fea2153b2eb504763`。相邻Backend/恢复回归 **38 passed**；无法绑定的冲突文件反例 **1 passed**。这24项的同Session验收、construction和全量回归仍待固定输入验证，不表示B03完成。

## 2026-09-29 — Completion recovery fence and termination candidate

真实 `invocation.artifact_projection` 的进程退出后，在新进程损坏 ledger 的恢复反例中，`recover_completion` 的失败未携带本次接管的 Resume fence；外层错误收尾使用旧 epoch/revision，先抛出 `Stale or terminal operation fence`，无法完成原 owner 的 unavailable 尾部。仅在 `pause.py` 原 completion 恢复调用周围使用既有 `failure_context(operation)`，保留正确 fence；不修改 coordinator、lease policy 或 failure contract。两项 before/after 反例 `/private/tmp/b03-bundle-integrity-fence-probe.json` 已通过。Bundle/current/Attempt/release 64项随后完成两fresh根审计；`external.bundle_current` 首轮切到了同名较早 projection hook，独立expected检查发现 epoch 差异，因此先限定在真实 artifact registration 后才 arm，再将该八项在两个新fresh根重跑。旧审计保存在 `/private/tmp/b03-bundle-release-extra-before-current-arm-{one,two}.json`，正确切点审计为 `/private/tmp/b03-bundle-current-exact-audit-{one,two}.json`；未修改B02 expected、事件顺序或任何验收门槛。

真实 termination 发布后、其CAS尚未提交时退出，再损坏原task，观察所得 unavailable proof 与未提交safe candidate冲突。原 `publish_exact` 保留候选但打断stop收尾，producer停在stop intent；反例日志 `/private/tmp/b03-stop-publication-conflict-probe.log`。仅在 `CodeExternalStop.stop` 中识别同一producer/Run/Attempt/Cycle/epoch/resolution及其原resource/disposition字段的canonical safe候选；新观察为 unavailable 时保留原bytes，独立发布 `termination_evidence_unavailable.json`，仍由同一coordinator的原termination/final CAS绑定reference和digest。未知、非canonical、身份不符或其他冲突继续拒绝。未新增schema字段、authority、producer、owner或正常safe通道。三个定向恢复反例 `/private/tmp/b03-stop-publication-conflict-probe-fixed.json` 已通过，分别覆盖termination物理发布、termination CAS和已冻结termination后的final发布；后者的safe stop proof保持原样，canonical消费因task损坏完成unavailable，不重新分类已提交proof。完整双根/节点验收仍在继续。

## 2026-09-29 — Durable normal-unavailable handoff recovery

真实 Fake Backend normal final 的首次 containment kill 失败，Host 已持久化 `normal_unavailable_trigger.json` 并保留原 interrupt operation，随后在 `interrupt_and_terminal_ownership_reserved` 的 before/after 进程退出，SQLite arbitration 回滚而 producer 仍无 resolution owner。后续实际 containment 可以安全停止；原恢复代码重新评估 normal proof 并走 normal CAS，遗留已保留的原 interrupt。复现见 `/private/tmp/b03-normal-unavailable-before-fix.log`。

在 `ExternalNormalFinal.commit` 的既有恢复入口，若 producer 尚无 resolution owner 且原 unavailable handoff 存在，继续同一原 interrupt；既有 `publish_exact` 校验触发材料原字节，不重建、覆盖或另立 owner。既有 arbitration、proof classification、收费和 schema 均保持。8 项真实重启、Task 损坏及 snapshot 丢失反例，两独立 fresh 根 exact 相同：`/private/tmp/b03-reclassification-audit-one.json`、`/private/tmp/b03-reclassification-audit-two.json`。未知 `{}` / `[]` trigger 仍拒绝且 producer、原字节及 operation 数保持，定向 **2 passed**，日志 `/private/tmp/b03-reclassification-negative-fixed.log`。全部同 Session 与全仓验证待最终冻结输入验收。

### Final authority-hook receipt wiring

新增 late consumer effect 反例的生产 gate 会在同一拒绝操作中读取 capability 两次。首轮带真实进程回执的定向检查发现测试 observer 重复发布同一不可变 receipt；无 hook 的第二次重放又因 observer 缺少 `production_hooks` 属性失败。仅修正该新增 observer：首次实际 gate 回调后解除本 case 的观察，未绑定 hook 的重放不访问属性。保持生产 gate、两次独立拒绝操作、原数据不变与 exact trace；首轮失败日志保留在 `/private/tmp/b03-authority-hook-failure.log`、`/private/tmp/b03-authority-hook-regression.log`。无修改 production 或 expected 来掩盖失败。

### B02 fixture import regression detected by full Session

最终同Session复验在Cancel/Interrupt原B02路径发现 `UnboundLocalError`；新增canonical Backend stop分支内的局部 `CancelPauseRequest/ResolveExternalInterruptRequest` import使整函数把这些已有全局类型视为局部变量，原B02路径无法构造request，尚未进入production。只移除冗余局部import并使用原全局类型，不修改B02结果、expected、fault、owner或生产实现。失败Session全部保留于 `/private/tmp/lqcd-agent-b03-b02-full-runtime-dqhyc5dt/session/`；停止时58批通过、30批失败，不计完整验收。修复后须在新的冻结输入Session重验整个645/1410集合，禁止拼接前一Session证据。

## 2026-09-29 — Final maintenance verification closed

上述contract-preserving生产恢复修复与测试接线修正已在最终冻结输入 `01aefd8d558a85eac651ebbaad204818d4d85f0c217d754157017b5be586a082` 验证：同一fresh Session B03 **645/645**、B02 **1410/1410**、全仓 **3514 passed**（Phase B **3189 passed**），construction **15/11/30/28**。原失败/错误切点/超时审计保留，未拼接不同输入或不同Session。最终结果与原始报告见[B03完成记录](../completions/B03_COMPLETION.md)；所有“待最终验证”条目至此闭合，历史内容保持。
