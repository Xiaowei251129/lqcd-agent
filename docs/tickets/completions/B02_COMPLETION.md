# B02 Execution Record — Blocked, Not Completed

- Ticket：[B02 Durable Control Operations](../phase-b-graph-harness/B02_DURABLE_CONTROL_OPERATIONS.md)。
- Status：2026-09-16，用户批准`ready`后已冻结并开始执行；现为`blocked`，没有完成B02验收。
- Commit：执行前唯一commit为`83681a7d5b4ed8e0d9a7de8b633d2ab5cb5f1d52`，message为`feat: complete B01 foundation and freeze B02 ready`。包含此前未提交的B01交付、B02 ready快照及对应状态文档，共39个文件；commit后工作树曾为空。没有push，也没有第二次commit。
- Changed：执行后保留未提交的`control/coordinator.py`、`control/operations.py`基础实现，两个B02测试文件，以及本记录、索引和当前状态文档。B02仅改YAML lifecycle；正文保持冻结。没有更改Phase A、generated protocol、B00/B01正文、B03–B05、matrix、registry或final obligations。
- Delivered boundary：仅验证了部分SQLite初始化/预留、same-key冲突、operation epoch fencing、精确文件追加、同步后异常的重新打开、SQLite backup及generated phase/branch结构检查。尚无完整durability preflight、12-variant实现、public control接口、bootstrap/Pause/child/capability实现、fresh-process并发验收或30项requirement交付。这些未接入模块不是可用的durable control runtime。

## Stop Condition and Reproduction

接入真实fresh-root轨迹时发现B00 exact-trace前置能力缺口。最小复现仅使用已完成的B01 production record/replay/cross-head代码；没有把本次WIP coordinator当作完整Run实现。

```bash
RUN_LIVE_LLM_TESTS=0 pytest -q \
  tests/phase_b/test_control_operation_recovery.py::test_fresh_root_changes_digest_after_current_trace_normalization
```

测试建立两份新的`/private/tmp/lqcd-agent-b02-trace-*` foundation snapshots。两份root的输入、Run/Attempt身份及固定clock相同，均通过production `validate_run_root`；checkpoint manifest沿用B01 construction fixture，不宣称已经实现durable LangGraph checkpoint。

唯一变化是物理root。`canonical_output_root`进入Run-created canonical bytes，进而改变整个execution hash chain和checkpoint head。当前`harness.trace.normalize`只删除event的显式`ephemeral` envelope，保留已经包含root影响的raw head，因此同一semantic fixture的exact comparison报`invalid_evidence:trace:exact`。

一次实测的execution heads为：

- `/private/tmp/lqcd-agent-b02-trace-xlaz_jmx`：`6fb1e38054de262e41aaac933d230e43d0db2d3f93a3291470035013bc2a20c4`；
- `/private/tmp/lqcd-agent-b02-trace-a5z6csf1`：`7d9b3f204ab98c139cf96e4f97882a1125f46b6a69ec7cf163ad891df924771e`。

这个诊断测试通过表示“当前缺口可复现”，不是问题已修复，也不是新增acceptance evidence；它未加入matrix。

[B00 Normalized Trace Codec](../phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md#5-normalized-trace-codec)要求保留identity/head/digest/correlation，新增排除规则必须通过corrective ticket。B02又要求所有验收位于fresh root、exact trace保留heads，且把缺失B00前置能力或改变验收边界列为Stop Conditions。因此暂停实现，没有擅自选择以下绕过：

- 清空head、通配符或unordered/subset比较；
- 每次运行用actual结果重写tracked expected fixture；
- 复用固定历史root、伪造canonical physical root或绕过production root validation；
- 未定义证明关系就把raw SHA替换为固定别名，或改写B00 codec/seal/contract。

## Verification

执行前fresh基线位于`/private/tmp/lqcd-agent-b02-execution-7iP2Rm/`：full suite **445 passed**；B00/B01 construction分别**15/15、11/11**；全局映射26、remaining105、passed=null。Final按预期只有105 coverage、2286 runtime、15 exit gaps，两完成标志均false。

暂停前实际检查：

- B02基础测试6 passed，缺口诊断1 passed；没有skip/xfail，没有B02 construction通过声明。
- Phase B suite：**127 passed**。
- 完整`RUN_LIVE_LLM_TESTS=0 pytest -q`：**452 passed**。
- A02/A03/state regression：**139 passed**。
- Phase A validator：131 required、101 semantic + 3 structural mutations、178 publication-order、6 JSON/catalog checks通过。
- Generated protocol `--check`：byte-equal。
- `compileall`通过，bytecode位于`/private/tmp/lqcd-agent-b02-blocked-PCHFti/pycache`。
- Markdown links、scope、ownership、依赖、冻结bytes和`git diff --check`检查通过。

最终fresh前置验收报告目录为`/private/tmp/lqcd-agent-b02-blocked-PCHFti/`，文件为`b00-report.json`、`b01-report.json`、`final-negative-report.json`。Matrix仍仅包含B00/B01：construction分别15/15和11/11，映射26/131、remaining105；final仍只列105/2286/15预期缺口，两个完成标志均false。B02没有添加slice、scenario、passing evidence或production-hook binding。

## Git Commands Actually Used

`git add`把明确列出的B01交付及B02批准状态放入暂存区；`--cached`查看即将提交的内容；`commit`创建本地快照；`show`核对已提交快照。

```bash
git add -- docs/ARCHITECTURE.md docs/ARTIFACT_CONTRACTS.md \
  docs/DECISION_LOG.md docs/EVALS_AND_OBSERVABILITY.md docs/README.md \
  docs/REPO_CURRENT_STATE.md docs/STATE_SCHEMA.md docs/VERIFICATION_GUIDE.md \
  docs/tickets/completions/README.md docs/tickets/completions/B01_COMPLETION.md \
  docs/tickets/phase-b-graph-harness/B01_EXECUTION_0_4_CONTROL_FOUNDATION.md \
  docs/tickets/phase-b-graph-harness/B02_DURABLE_CONTROL_OPERATIONS.md \
  docs/tickets/phase-b-graph-harness/OVERVIEW.md \
  src/lqcd_agent/control src/lqcd_agent/graph/state.py tests/phase_b
git diff --cached --check
git diff --cached --stat
git commit -m "feat: complete B01 foundation and freeze B02 ready"
git show --stat --oneline HEAD
```

## Deviations and Follow-ups

没有放宽冻结合同；按Stop Conditions停止。没有把B02提升为completed，也没有授权或执行B03–B05。

下一步需要用户批准独立corrective工作的范围：先定义fresh-root/time等允许的ephemeral输入如何形成可验证的semantic digest/head projection，始终验证raw canonical digest与完整head引用关系，并增加路径独立性、时间独立性、head错误关联及digest tamper的正/负向回归。方案不得使非法内容变化被归一化隐藏。这个方案目前只是建议，未创建或批准新ticket、未修改验收合同。

Corrective完成且fresh B00/B01前置验收通过后，再恢复B02冻结合同的剩余实现与30项验收。此前不得把本记录标题中的路径名称理解为完成声明。

## 2026-09-16 Addendum — Acceptance Prerequisite Unblocked

用户随后批准B00C01与B00C02；其ready快照分别冻结于`d9af4e8`和`10db77c`。来源绑定的trace0.2保留raw digest、引用及production replay校验，支持fresh root/time的固定semantic expected比较；writer、父validator、runtime case与exit摘要调用均完成接线，旧trace0.1不变。B00C01/B00C02已completed，详见[B00C02完成记录](B00C02_COMPLETION.md)。

新证据位于`/private/tmp/lqcd-agent-b00c02-LZvk0k/`：source-bound 46 passed、相关74 passed、Phase B 174 passed、full suite 499 passed；B00/B01 construction仍15/15和11/11，final exact缺口仍105 coverage、2286 runtime、15 exit，两完成标志false。旧停止记录和当时证据保留，不回写历史。

B02从blocked恢复ready，仅解除上述验收前置阻塞；冻结正文不变。当前仍只有此前未提交的coordinator基础，完整public control接口、可信bootstrap、Pause/Resume、child saga和实际多进程验收必须在原B02继续实现，不能推给B03，也不能把本次修正完成当作B02完成。本次corrective没有修改B02 runtime，没有新增B02 matrix slice、production bindings或30项passing证据。

## 2026-09-16 Addendum — Resumed Bootstrap Implementation

用户要求继续后，B02从ready进入`in_progress`。这是一轮局部实现进展，不是B02 completion，不是新的Stop Condition，也不改变既有批准范围。B02正文继续与`83681a7` byte-equal；没有commit/push，此前B00C01/B00C02及其他未提交修改均保留。

本轮实现：

- `coordinator.py`：macOS writable-local-mount检查、实际file/directory sync和atomic replacement预检、closed SQLite schema object检查、operation lease续期，以及先commit到coordinator的immutable materialization snapshot/publication bytes。Publication绑定producing epoch/revision；完整的同operation JSONL前缀可追加预计算后缀，partial或冲突bytes不截断、不覆盖。
- `operations.py`及既有`budget.py`：可信bootstrap admission使用exact allowlisted policy计算initial Cycle、Planner Work Attempt、START Transition和5 control/6 transition terminal reserve；proposal绑定operation/input/policy，不接受caller-supplied allow。B01遗漏bootstrap action的局部修复已记入[B02 maintenance](../corrections/B02_MAINTENANCE.md)。
- 新`interfaces.py`：typed Host `ActorContext`/`StartRunRequest`与`ControlPlane.start_run`正常路径；从generated graph选择phase，按reservation、root/policy、7条bootstrap records、running checkpoint、inactive capability、committed result推进。同key同request重放原result，不创建第二个Run。
- 新`checkpoints.py`：per-Run `SqliteSaver`与coordinator物理分离；仅使用closed JSON serializer，不反序列化pickle/用户类型；校验payload、producer metadata、manifest/state/head digest，existing checkpoint不能被替换。
- 新`capabilities.py`：committed producer激活条件、独立invocation epoch/expiry、原budget deadline、live-owner续期、started intent CAS和A02 started publication；started intent后不能通过lease takeover自动重跑。`require_effect_authority`只是即时owned-prefix检查，不是可复用的dispatch许可，尚无产品target执行接线。
- 新`helpers/process_client.py`及`test_bootstrap_control.py`，扩展原coordinator tests：spawn独立Python进程，pipe同步竞争，真实`os._exit` crash。覆盖8个bootstrap phase、7个ledger durable-prefix边界、同key/不同payload、唯一invocation winner、intent/started crash禁止接管、损坏prefix/input/checkpoint拒绝和无副作用查询。

当前实现限制与剩余工作：

1. `start_run`的normal/materializable路径已实现，但integrity冲突目前只拒绝后续写入；把该故障归入failed operation、deterministic `close_run`及appendable failed/unavailable closure的完整收尾仍未接入，不能因此宣称bootstrap requirement全部通过。
2. Pause/Resume/Cancel、advance/close/interrupt完整图、Replay/Fork child saga、generic target/resource/source handoff仍待完成。Normal external result、timeout/interrupt、Human Response和所有terminal arbitration仍属于B02的剩余control half，不得转嫁B03。
3. 还需完成live effect端口、owned head推进和独立recovery处置，不能把只读authority检查作为绕过coordinator的许可。
4. 本轮未增加B02 matrix slice、scenario、registry binding或expected runtime trace；未声称30/30或56项累计coverage。真实matrix仍仅B00/B01，global passed为null，两完成标志false。
5. 当前preflight只验证macOS reference mount ABI；未知平台fail closed，没有宣称Linux/remote filesystem支持或通用power-loss保证。Legacy schema `0.2` CLI、product graph、B03/B04语义未切换。

实测结果：

- 执行前：完整suite **499 passed**；B00/B01 focused **40 passed**；fresh construction **15/15、11/11**。
- 最终局部bootstrap/storage：**52 passed**。
- 最终Phase B suite：**220 passed**；完整`RUN_LIVE_LLM_TESTS=0 pytest -q`：**545 passed**。
- A02/A03/state regression：**139 passed**；Phase A validator、generated protocol `--check`与`compileall`通过。
- Fresh前置验收目录：`/private/tmp/lqcd-agent-b02-progress-RTv74Q/`。`b00-report.json`、`b01-report.json`及`final-negative-report.json`分别记录15/15、11/11和预期final失败；coverage仍26、remaining105，runtime缺口2286、exit缺口15，没有新增B02 acceptance声明。
- Ownership仍15/11/30/28/47且互斥并集131；依赖、Phase A bytes、generated projection、B00/B01正文、B03–B05、matrix及验收基础本轮未变。Markdown文件链接与`git diff --check`另行核验。

下一实现顺序：先接入同一coordinator的terminal owner与close/unavailable分类，完成bootstrap故障收尾；然后实现Pause/Resume/Cancel和advance/interrupt control half，最后完成child saga、全量race/fault/trace/registry接线与30项验收。B02保持in_progress；无须重新批准原票范围，也没有批准B03执行。

## 2026-09-17 Addendum — Full Continuation in Progress

本条记录替代上一条对“当前实现”的描述，不改写其历史测试事实。用户已批准原冻结B02的完整续执行；本轮没有commit/push，B02仍为`in_progress`，尚未达到30项机器验收。

已落实并逐步验证的新增控制路径：

- Invocation在耗时校验、编码与实际写入/副作用边界重新fence；bootstrap实际完整性失败形成唯一appendable failed或unavailable closure。两个已复现局部缺陷见[B02 maintenance](../corrections/B02_MAINTENANCE.md)。
- Recovery Pause非对称双checkpoint publication、null/ordinary target abandon、无ExternalOperation的cancel、普通target continue，以及Code Agent/legacy recovery continue永久拒绝。
- Replay/Fork schema `0.4` child使用同一coordinator、可信bootstrap admission、source proof/revision CAS和全新identity；不修改source。Schema `0.2/0.3`兼容reader仍待实现，不能把当前0.4测试解释为完整兼容矩阵。
- `advance_run`通过Host-owned deterministic domain adapter冻结route/admission，执行allocation、invalidation、Transition、heads verification、typed N/A preparation、inactive capability和committed activation；END分支不分配Attempt/capability。当前仍需补齐grant、适用fresh Analysis preparation及外部结果控制证明。
- 普通Attempt可通过fenced artifact port发布真实A03 bundles，沿用slot/dependency/namespace规则。新增registry入口仅做只读preflight；默认legacy注册路径未修改。实际Memory Report END之后由同一terminal coordinator发布completed lifecycle和checkpoint。
- Human Request由Coordinator route prerequisites建立；Human Response claim后才分配validator。已接通protected response payload、外部control Transition、consumed/running checkpoint、实际validator invocation、scope-bound validation以及精确Transition消费。Invalid response按实际容量记录allow/halt decision，创建新的Pause或唯一close tail，旧Pause不重开。
- 恢复时保留所有已物化record/Transition的原producer和时间；只有未发布后缀使用新epoch/可信时间。Coordinator内部尚在构建的SQLite schema使用version 2保留各epoch的publication plans；未实现或执行旧coordinator自动migration。

阶段性验证事实：先前完整运行达到**658 passed**。之后新增普通artifact/END/close定向测试通过；Human正常/invalid容量流程**4 passed**，Human before/after与intent/completion边界的真实fresh-process测试**24 passed**。一次开发中全量运行产生**665 passed、1 failed**：失败来自测试跨越源码编辑、正确触发runtime fingerprint不匹配；该运行不是最终绿色基线，最终验证必须在源码不再编辑时重新执行。新增加的竞争/故障测试仍持续执行，不能以这些局部数量宣告完成。

尚未完成：ExternalOperation normal result/interrupt/cancel仲裁、7×4 post-claim failure tails、schema compatibility、全部registry production bindings/exact traces与fresh30项construction。未新增B02 matrix slice，真实coverage仍26、remaining105，两全局完成标志false；本条不是新的阻塞或停止决定。

后续范围复核：invalid-response的容量分支选择移入测试专用`SyntheticRepauseAdapter`，B02只接收Host配置的typed domain decision、校验canonical digest/来源绑定/冻结分支并发布；不能把此测试adapter或前述控制顺序解释为B04产品capacity policy已经实现。后续完整验证使用该职责边界。

### External Control Continuation — In Progress

继续实现了ExternalOperation的B02控制侧读取、reservation/core绑定核验与`pause_prepared`之后的一次性Pause binding CAS。外部domain输入由测试专用source/stop adapter提供；没有实现Backend、workspace containment或A05 canonical Code schemas，也没有把这些测试输入作为B03完成证据。

`cancel_pause`已接入同一SQLite事务中的External/Pause/Run仲裁，核验实际不可变final evidence文件及generated stop-proof classifier，覆盖cancel winner、normal safe-final winner、safe halt/failed和unavailable quarantine尾部。安全cancel记录close-disposition释放active binding，但保留原ExternalOperation row、resolution与Pause身份。已有winner观察分支仍需补齐竞争实测。

新增trusted-only `resolve_external_interrupt`入口，当前已验证`controlled_halt`和`integrity_failure`在无Pause/已opened Pause上的terminal tails，分别按safe、proven violation、unavailable派生halted/failed/unavailable。Prepared-only interruption、recoverable timeout正常Code delivery及完整仲裁竞争尚未闭合；不能将接口存在解释为全部三variant验收完成。

阶段实测：external定向suite **83 passed**，含28个cancel及32个interrupt before/after publication边界的fresh-process restart；此后新增3个stop evidence异常收尾用例，定向非process部分 **26 passed**。缺失/被改写/伪报safe-stop的证据只形成同一owner的unavailable tombstone，不伪造terminal Run lifecycle。Phase A validator和generated protocol `--check`通过，protocol/catalog SHA保持冻结值；正在继续执行Phase B回归，尚无新的全量绿色基线或B02 construction声明。

本条仍是正常续执行记录，不是完成或暂停决定。Normal external-result消费、recoverable timeout、7×4 post-claim failure、兼容source reader、Analysis preparation/grant及完整matrix/registry/trace接线仍待完成。B02保持`in_progress`，真实matrix未添加B02 slice。

### Verification Checkpoint and Compatibility Clarification

源码停止编辑后的本轮实测：Phase B suite **453 passed**；禁用live provider的完整pytest **778 passed**；A02/A03/state regression **139 passed**。Phase A validator、generated protocol `--check`、compileall及`git diff --check`通过；ownership仍15/11/30/28/47且互斥并集131，B02冻结正文及Phase A全部12个文件byte-equal，482个本地Markdown链接无broken link。未修改B03–B05或默认legacy runtime；保留进入本轮前的所有未提交工作，无commit/push。

Fresh验收先在`/private/tmp/lqcd-agent-b02-verification-PmpjTU/`验证B00/B01 construction为15/15、11/11。Final非零退出，且错误集合只有**105 coverage_gap、2286 runtime_evidence_gap、15 exit_evidence_gap**，没有解析或无效证据错误；global passed=null，两完成标志false。文档同步后的fresh报告位置为`/private/tmp/lqcd-agent-b02-review-4mPC9t/`，仍只证明前置slice和当前缺口，不是B02 acceptance完成报告。

兼容性核对发现一个需要用户明确的边界：[现有schema 0.2创建器](../../../src/lqcd_agent/graph/state.py)持久化root input references，但没有历史runtime fingerprint；[冻结A04](../phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)的Replay/lineage要求source fingerprint，机读`SourceSnapshotProof/replay_root`也包含该required field。目前合同没有显式说明如何表示这个历史缺失。直接填当前runtime值会伪造历史事实；自行加入缺失型又可能改变source proof的验收边界。因此已请求确认是否起草独立corrective ticket，明确旧source缺失fingerprint的表示与验证，而没有修改冻结protocol/catalog或偷偷加入新variant。

该澄清未获批准前暂停新增实现；遵照用户要求，B02 lifecycle保留`in_progress`，不改为completed。上节列出的其他控制分支和30项验收仍是原票正常待实现工作，不应被误写为这个兼容问题造成的缺失。建议的corrective只处理legacy source fingerprint证明，不改变0.2仅replay、0.3合格fork及0.4 exact resume边界；起草和批准之后再实施。

最小兼容诊断保留于`/private/tmp/lqcd-agent-b02-review-4mPC9t/legacy-fingerprint-reproduction/`：调用未修改的production `initialize_state`创建4条0.2 bootstrap records，goal/config digest逐项匹配，重新加载同一identity通过，未执行target；所有records均没有fingerprint字段。A04的完整component列表针对Pause，而当前新写的B02 source validator复用了Pause校验器；后者不是冻结B01权威，也不能单独作为合同阻塞依据。待明确的是A04仍要求child/source proof记录source fingerprint，却没有说明0.2历史缺失的表示和验收方式；既不能由这个过严实现反推合同，也不能用当前build补造历史值。

## 2026-09-18 B02C01 compatibility correction completed

用户批准的B02C01已在独立票据内完成：真实0.2 source经只读验证可Replay到新0.4 child，lineage如实记录历史fingerprint未记录；78项定向与833项全量测试通过，B00/B01 fresh construction仍15/15、11/11。ready票据冻结commit为`5e753d6`，实现未commit/push。原B02保持in_progress，继续补齐external消费/失败收尾、其余preparation/兼容和验收；30项slice尚未交付。详细证据见[B02C01 completion](B02C01_COMPLETION.md)。

## 2026-09-18 continued control implementation — in progress

B02C01完成后继续原冻结B02。新增prepared external interrupt（prepared→aborted/quarantined）、normal external_result resume、resource settlement→claim/consume→Code消费授权→registered result→binding release→final checkpoint顺序；支持释放后的advance。Code验证通过Host-owned typed domain port接入；当前测试明确是external/domain adapter的控制证据，不代表B03 canonical Code Bundle、Backend或verifier已经交付。

补齐同一resume operation的consumption_failure intent/terminal owner、invocation fencing、consumer stop/classification、failed/unavailable tails；保留原normal final，禁止重复调用消费者、结算或重开Pause。Cancel新增对已有cancel/interrupt winner的只读观察，允许winner已终结同一public Pause；观察不依赖或消费external final、不取得领域owner。Advance可消费已由可信B04输入签发且精确绑定的single-use grant；本轮没有实现grant issuance。

已运行：prepared/external/Pause focused160 passed；granted advance16 passed；normal consumption25 passed（24个fresh-process边界）；post-claim failure及七个entry CAS11 passed；failure尾部fresh-process24 passed；cancel winner观察及既有仲裁9 passed。Phase A协议摘要与generated byte检查仍通过。合并回归正在进行；这些分组有重叠，不能相加当成全量结果。

B02仍in_progress。剩余至少包括recoverable timeout failed-delivery链、normal-final system close、fresh Analysis preparation port、0.3 source reader/CAS、完整two-client竞争与负向矩阵、B02 construction slice、205个boundary/1488个独立case验收接线。当前covered26/remaining105不变；没有实现commit/push，不宣称B02或Phase B完成。

后续检查：上述消费/Pause/Human/终止合并回归267 passed。Normal final system stop现已补齐，正向及14个fresh-process重启边界共15 passed；terminal/bootstrap/child回归90 passed。关闭只处置未消费的结果，原external final不变。Fresh Analysis preparation的generic typed control port正在验证；真实worktree与Analysis subprocess仍属于B03。

后续实现：recoverable_timeout的safe-stop/clear分支可在同一interrupt winner内冻结typed failed delivery，claim/consume原Pause，写running checkpoint，签发仅限确定性失败结果消费的capability，先持久化started intent再写A02 started，注册可信domain port提供的失败artifact、记录Attempt failed、释放binding、写最终checkpoint并结束。没有Backend retry、verification command、业务consumer重执行或outbound Transition。35项检查通过（34个fresh-process边界）；full-suite已开始重新运行。测试结果只证明B02 control half，不代表A05 canonical timeout bundle实现。

## 2026-09-18 continued implementation — blocked on historical trace evidence

B02C01 was approved and completed, then original B02 execution continued. Normal external consumption, same-resume failure closure, prepared Pause interruption, normal-final system close, fresh preparation control, recoverable timeout completion and historical source ports now have production control paths plus focused tests. These use explicit external/domain adapters; they do not deliver A05 backend/worktree/canonical Bundle or A01/B04 product behavior.

Additional verified fixes and limits:

- Close/resume competition and integrity exceptions: 26 passed. The loser is terminal and cannot modify the winner; an owned terminal operation cannot leave pending closure.
- Historical 0.3 Replay/Fork and unchanged-source checks: 14 passed, including two-process claim/CAS and a live checkpoint WAL. The source reader is a trusted Host port for the original format; the runtime does not invent a missing 0.3 creator or migrate source data.
- Preparation conflict: safe append closes failed; broken authority closes unavailable; the original target remains scheduled. The two new classification tests passed after fixing a missing precondition tag.
- Latest earlier expanded full run: 995 passed in 514.42s, before the historical-source and later competition changes. A new full regression is running for the final current tree; results are appended below when complete.

A new required-evidence defect is reproduced: 0.3 Fork succeeds, but B00 trace 0.2 cannot validate its real historical execution/checkpoint reference graph. Three diagnostic encodings are all rejected for the expected different reasons; diagnostics are not matrix evidence. See [maintenance](../corrections/B02_MAINTENANCE.md) and the pending [B00C03 corrective ticket](../phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md).

B02 is now **blocked**, not completed. B02C01 remains completed. No B02 slice or runtime binding has been falsely added: mapped coverage remains **26**, remaining **105**, and B02's 30 construction requirements plus its 205 boundary/1488 runtime-case bindings still require actual acceptance evidence. Remaining work also includes final control branch auditing, grant/replan boundary verification and fresh exact traces; approving B00C03 only addresses the newly reproduced evidence prerequisite.

Only B02C01's ready ticket was committed (`5e753d6`); no runtime implementation commit or push was made. B02 body, Phase A protocol/catalog and independent acceptance obligations remain frozen.

### Final verification of the current blocked implementation

- Full pytest: **1024 passed in 609.72s**. This includes the three expected-rejection diagnostics; they do not represent passing B02 acceptance scenarios.
- A02/A03 regression: **139 passed**. Phase B collection: **699 tests**, no collection error.
- Fresh B00/B01 construction: **15/15**, **11/11**; global mapped **26**, remaining **105**, passed null, both completion flags false.
- Fresh final negative: exact **105 coverage + 2286 runtime evidence + 15 exit evidence** gaps, with no additional parsing/collection/internal error. B02's own 205 boundaries/1488 cases remain unbound.
- Phase A validator passed with unchanged protocol/catalog SHA; generated protocol byte-equal; compileall, local Markdown links and diff checks passed. B02 and B02C01 bodies exactly match frozen commits `83681a7` and `5e753d6` respectively.
- Approval-entry scope audit: only approved control/tests/docs and the unimplemented B00C03 review draft changed; legacy default runtime, Phase A, B00 harness and independent obligations are unchanged from entry.
- Evidence: `/private/tmp/lqcd-agent-b02-final-review-qxn1sask/`, including full regression logs, exact diagnostic proofs, reviewed trace digest delta, freeze/link/scope audits and fresh reports. The later `*-final-report.json` files bind the finalized review documentation; no code changed after the full regression began.

Status stays **blocked**. Next approval is solely [B00C03](../phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md); its proposed trace 0.3 has not been implemented. Once approved and verified, continue original B02 rather than equating the corrective completion with B02 completion.

### 2026-09-21 — Historical trace prerequisite resolved

The user approved B00C03, frozen at `3c53a41`. Its explicit trace0.3 validates original historical0.3 sources and real Fork reservations before projecting references into the 0.4 child. Full regression: 1063 passed; fresh B00/B01: 15/15 and 11/11, mapped26/remaining105. Old trace rejection diagnostics remain valid. [B00C03 completion](../completions/B00C03_COMPLETION.md) closes this prerequisite. Restore original B02 to ready and continue its approved execution; no B02 slice or runtime completion is claimed, and the frozen B02 body remains unchanged.

## 2026-09-21 — Reservation fault-case executability audit

B00C03 is completed and its historical-source trace blocker is resolved. Resumed B02 fixed lost/corrupt materialization-plan terminalization and the granted replan new-Cycle validation defect; focused groups passed 101 and 45 checks respectively. These groups overlap and are not a full-suite total.

A separate B00 prerequisite defect is now reproduced at the initial reservation transaction. New before/after-SQL observation points expose actual boundaries in the same writer transaction. A fresh Python process exits at either point before COMMIT: SQLite rolls back all operation/phase/snapshot/owner/capability rows, and no Run directory exists. A new process retries the request successfully with one newly reserved operation at epoch 1. B00 nevertheless enumerates materializable-prefix and terminal domain-gap cases for these no-durable-authority contexts. Runtime cannot invent an original operation to satisfy them. The distinction between SQL publication and durable transaction commit must be represented explicitly.

Six production regressions passed in 2.84s: two hard-exit/restart cases and four immutable committed-replay controls for start and Pause. The replay controls do not prove every same-key outcome context is impossible; previously failed/recovery-required tombstones can themselves be replayed. No case waiver, binding or passing B02 observation was added. The 12 reservation boundaries currently expand to 96 independent cases; the new proof identifies a classification/context defect, not permission to delete all 96.

[Proposed B00C04](../phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md) is review-only. It proposes explicit rollback classification, commit-position semantics, a complete audited B02 case disposition table, fresh evidence and unchanged runtime authority/requirements/exit gates. It is not approved or implemented. B02 is **blocked**, with its frozen body unchanged. B02C01 and B00C03 remain completed.

Trace capture now includes actual reservation observations. The reviewed fixed traces add three reservation events to the B02 Recovery flow (40→43) and one to the historical Fork flow (29→30); other event identities/order/status/owners/epochs remain unchanged. Eight and ten head/digest fields respectively propagate the genuine changed runtime build fingerprint. Candidate, previous, raw and review artifacts are retained at `/private/tmp/lqcd-agent-b02-boundary-review-e9vgtj2h/`; expected traces are not generated during tests.

Coverage remains mapped26/remaining105, with B02's 30 construction requirements and 205 boundary/1488 runtime bindings unfinished. Full current-tree regression and fresh B00/B01/final-negative results are recorded below after verification. No implementation commit or push has been made.

Focused current-tree verification: **68 passed in 12.39s**, covering the reviewed trace fixtures, historical source evidence, reservation process boundaries, granted replan and lost Pause plans. Full current-tree verification follows; these are not construction/runtime acceptance passes.

### Current-tree final verification, 2026-09-21

- Full deterministic pytest: **1086 passed in 541.65s**; Phase B collection: **761 tests**, no collection errors. The six rollback/replay diagnostics have no acceptance observations and add no coverage.
- Fresh construction: B00 **15/15**, B01 **11/11**, no errors. Mapped **26**, remaining **105**, global passed null; both completion flags remain false.
- Fresh negative final: exactly **105 coverage + 2286 runtime evidence + 15 exit evidence** gaps. No additional parse, source-validation, collection or internal error. B02 construction and its **205 boundaries/1488 cases** remain unbound.
- Phase A validator and generated-byte check passed with the original protocol/catalog SHA. Compileall and diff checks passed. Scope audit checks all **310** Git-visible files and **24** resumed-B02 changes; all are in scope, including the review-only corrective proposal. **344** local Markdown links resolve. B02/B02C01/B00C03 bodies remain byte-equal to their frozen commits; independent inventory, obligation seals, matrix and completed prerequisite records are unchanged from B02 resumption.
- Evidence directory: `/private/tmp/lqcd-agent-b02-boundary-review-e9vgtj2h/`. `full-pytest.log`, `focused.log`, `inventory-counterexamples.json`, `reservation-regression.log`, reviewed trace deltas and `scope-freeze-links.json` record the findings. The `b00-final-report.json`, `b01-final-report.json` and `final-final-report.json` reports bind the finalized review documentation.

B02 remains **blocked** on the review-only B00C04 case-semantics correction, not completed. Existing implementation is uncommitted; no push occurred. Approval of B00C04 would authorize that defined correction and subsequent continuation of the already-approved original B02, not B03/B04 or a claim of finished B02 acceptance.

## 2026-09-21 — B00C04 prerequisite completed

用户已批准并要求实施统一修复计划。B00C04完成case0.2、source trace0.4及真实进程证据，完整1118 passed；B02原阻塞解除，现行独立case为1416（总数2214），coverage仍26/105。接续原冻结B02实施计划内运行缺陷修复和30项construction/runtime验收，不改冻结正文，不commit/push。

## 2026-09-21 — Integrated verification checkpoint

B02与C04现均in_progress：C04独立语义/来源/进程修正已通过定向验证，等待本轮集成全量复验；B02按既有批准修复实际运行缺陷。1112个control phase独立case离线探测及25项修正复验通过，其余298个supplemental case也已全部离线通过（组合原探测及48项复验），这些不替代fresh验收。三个独立进程的normal/cancel/interrupt全部六种顺序通过；Resume准入8项及committed Human后续计划丢失2项通过。新增完整source-bound轨迹terminal/Human/timeout/Fork/Replay分别83/100/81/48/35事件，每条两次fresh roots exact相等，实际来源和旧golden审查保存在本轮证据目录。covered仍26、remaining105，尚无B02 slice或runtime binding，未commit/push。

2026-09-21 B02验收接线：C04已completed后，新增B02完整30项slice、5条完整来源轨迹及1410个独立runtime case绑定。初始reservation的两项C04进程反例作为并列必需final证据保留，没有移除旧正负检查；历史trace回归只隔离其B00/B01前置slice，完整matrix另行验证。现行映射56/131、remaining75；B02仍in_progress，正执行fresh验收，不能将接线或离线通过当作完成。全局final规则未改变，其他票据798个runtime binding及15项exit仍未交付。

## 2026-09-21 — B02 completed after integrated acceptance

用户批准并要求实施的B00C04/B02统一计划现已完成。B00C04先完成验收前置；原B02在完整运行修复和以下实际验收全部通过后标记`completed`。原B02正文仍与`83681a7`一致，C04正文仍与本轮ready快照一致；不改Phase A协议、公共接口/状态枚举、B03–B05或默认0.2产品入口。所有进入本轮前的未提交工作保留，没有commit/push。

### Delivered control behavior

- 唯一project-owned coordinator管理十二种冻结operation变体、request/result幂等、guarded phase、mutation lease、invocation capability、Pause claim及唯一Run terminal owner；bootstrap、ordinary/END advance、Pause/Resume/Replay/Fork/Cancel/interrupt/close和process recovery完整接线。
- 失败上下文携带实际operation/worker/epoch/revision，旧epoch错误和旧phase错误不能借新租约执行收尾；重新取得租约后重新验证。Pause完整性失败形成持久化结果，既有terminal owner同步unavailable，不伪造Run终态。
- External claim后的丢失/损坏snapshot走原resume失败仲裁、能力撤销和可证明前缀收尾；缺乏停止/领域预授权证据时隔离binding并保持同owner unavailable，原normal final不可改写。
- Human后续操作失败、不可用或已提交后的计划丢失均向父resume持久化传递；重复调用不再次运行validator、创建Pause或重复结算。Close在owner提交前重试复用原reservation；Resume准入拒绝不产生SQLite sidecar或其他来源变更。
- 真实0.2来源仅Replay并如实保存fingerprint历史缺失；合格0.3/0.4来源创建新child且保持来源bytes不变。完整artifact历史原文进入来源证明；稳定测试proposal不削弱production身份/head/binding摘要检查。

B02的external/domain/preparation/source ports只证明原票拥有的control half。B03 Backend、canonical Code Bundle及fresh Analysis，B04产品图/后续预算admission，以及B05全阶段退出适配器继续由各自票据交付。

### Fixed expectations and independent cases

30项construction、5条完整source-bound轨迹以及1410项runtime独立绑定已加入真实matrix。Expected traces在fresh验收前离线执行、逐项审查并固定；测试运行只比较，不写回golden。完整来源轨迹覆盖terminal、Human、timeout、0.4 Fork/Replay，结合既有Recovery、normal external及historical Fork轨迹，每条均在两个独立临时根验证exact相等。Legacy Replay另验证原历史bytes、lineage缺失值与身份隔离。

C04现行case语义0.2保留全部205个B02 boundary；旧1488项为1362 retained/126 replaced，现行1410项。减少78项只来自首次COMMIT前无法存在原durable operation的上下文；22项仅能unavailable的后续phase改为terminal tombstone重放，未删除有效失败义务。完整disposition见[独立审查表](../../../tests/phase_b/reservation_case_dispositions.json)。B03/B04独立集合及全部28项post-claim组合不变，总数2208。

| B02 outcome | Case数 |
| --- | ---: |
| committed_result_replay | 330 |
| integrity_conflict | 384 |
| materializable_publication_prefix | 296 |
| non_materializable_domain_gap | 352 |
| reservation_rolled_back | 26 |
| terminal_tombstone_replay | 22 |
| 合计 | 1410 |

Logical publication边界映射到真实production publication：同一冻结JSONL append内的bootstrap records共用真实fsync，SQLite FULL提交对应真实database commit，不能伪造每条record的独立提交。进程退出前由production `coordinator.boundary`直接记录回执；父进程验证同session/case/nodeid/PID和原request后，才接受触发，再独立验证恢复结果、invariants和fixed trace。两项C04 reservation反例保留为同case的并列必需证据；新runtime绑定不能替代或绕过它们。

### Fresh results

- B00 construction **15/15**；B01 **11/11**；B02 **30/30**。三份报告无错误，累计covered **56**、remaining **75**。
- 完整测试 **2599 passed**，其中Phase B **2274**、其余已有回归 **325**；无skip、xfail或deselect。完整nodeid集合只收集一次，在同一Session按每批25项执行，104个批次全部setup/call/teardown通过；逐批核对输入不变，再检查集合唯一完整。
- B02独立runtime **1410/1410**，205个boundary全部覆盖；全部required scenario观察、production hook、case outcome、invariant和exact trace由既有validator验证。其他票据798项保持缺口。
- Global final按原preflight规则非零：仅 **75 coverage_gap、798 runtime_evidence_gap、15 exit_evidence_gap**，无其他错误。`requirements.passed=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。Global final因为前置缺口没有执行全阶段runtime，报告中2208项仍为该次final未运行；独立B02通过不伪装成global final通过。
- Phase A validator通过，protocol/catalog SHA分别为`7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`与`ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726`；generated bytes、compile、冻结正文、scope、链接及diff检查通过。

Evidence根目录：`/private/tmp/lqcd-agent-b02-integrated-4un4q9qb/`。

- `B02-fresh-integrated-validation/B02-owned-runtime-report.json`：同session的完整选择、摘要、通过case集合和场景集合；`merged-pytest.json`及104份原始batch request/output/envelope保留可核查证据。
- `B02-full-frozen-input-manifest.json`：全量运行冻结的3218个输入及摘要；worktree digest为`1dcfbced1535306078f70fbc6a8ed86fb06f628586e6e52708bd3d9120071371`。
- `B02-wired-B00-construction-report.json`、`B02-wired-B01-construction-report.json`、`B02-wired-B02-construction-report.json`及`B02-wired-final-report.json`：同冻结输入的fresh门槛报告。
- `B02-reviewed-runtime-fixture-freeze.json`、`B02-runtime-fixture-candidate-audit.json`、`C04-integrated-golden-review.json`：验收前fixed expectations的审查、完整集合/边界映射及原文来源；离线探测本身没有计为fresh通过。
- `B02-integrated-scope-link-audit.json`、`B02-metadata-closure-audit.json`及`B02-closed-*-report.json`：最终文档闭合的scope/冻结/链接审计与fresh construction/final报告。全量运行之后只改文档和ticket lifecycle，源代码、测试、fixtures和matrix/registry没有变化；不把旧session摘要冒充文档更新后的摘要。

B02范围内的已知阻塞全部关闭。此结论限于本票、已支持的macOS durability profile及上述真实进程/故障验收；后续B03–B05完成与全Phase B成功须由各票自己的证据决定。
