# B02 可执行性审查（2026-09-18）

## 结论与审查边界

B02可以继续完成，但“修正legacy fingerprint后即可完成”不成立。已确认一个需要批准的兼容合同补充，以及多组原票内尚未实现、尚未接入验收的工作。当前没有证据说明必须推翻单一coordinator架构；同样，没有依据预先保证剩余功能与全部故障分支一定通过。

本次审查检查B02冻结正文、A04/A02C01机器与文字合同、现有WIP、B00验收入口，并复跑验证；没有执行新的runtime修正。B02维持`in_progress`，未commit/push，进入审查前的未提交修改全部保留。

B02正文与`83681a7`冻结快照byte-equal，正文SHA-256为`d6308a1be68d7c56795ffa0e7ccab3852f8ce271a231df66a8e8df202112eb86`。先前的两项maintenance并未被本次审查否定；它们解决的是局部缺陷，不代表整票完成。

## 具体发现

### R1 — P1：legacy fingerprint缺失的表示没有合同定义

- 证据：[旧创建器](../../../src/lqcd_agent/graph/state.py)的`initialize_state`写schema `0.2` Run-created，保存goal/config引用，但不保存runtime fingerprint；[A04](../phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)的Compatibility与Child-run Bootstrap Saga要求source fingerprint；机读`SourceSnapshotProof/replay_root`把`runtime_fingerprint`列为required field，却未定义历史缺失值。
- 本次使用未修改的production创建器生成4条bootstrap records，goal/config SHA逐一匹配，所有records均无fingerprint。不是损坏source，也不能用当前build补造历史值。
- 影响：忠实读取真实0.2与必须提交source fingerprint之间缺少明确表示；单纯拒绝所有0.2又违反B02的合法root replay目标。
- 修正：独立[B02C01草案](../phase-b-graph-harness/B02C01_LEGACY_SOURCE_FINGERPRINT.md)，只为经验证的0.2 replay定义closed“历史未记录”值；保留真实0.3/0.4 fingerprint和Pause/resume的严格校验。草案未经批准，不是当前生效合同。

### R2 — P1：兼容reader未完成，不能只改fingerprint validator

- 证据：[children.py](../../../src/lqcd_agent/control/children.py)的`_source`先用canonical-only JSON解析首条记录，再硬性要求`schema_version == "0.4"`；随后假定root引用有`reference`字段、source有本coordinator bootstrap snapshot及`budget_policy.json`。Replay policy proof也写死`source_schema: 0.4`和`supported`。
- 实测：合法0.2调用公共`replay_run`首先失败于`Non-canonical JSON encoding`，尚未走到fingerprint分支；没有创建operation，也没有改写source bytes。这是安全拒绝，但缺少要求的正向功能。
- 旧格式实际为`root_goal_reference(kind=state_field, field=user_goal, sha256)`和`input_snapshot_reference(kind=file, path, exists, sha256)`，不能冒充0.4 Run-local JSON引用。[lineage validator](../../../src/lqcd_agent/control/records.py)也直接复用Pause fingerprint validator，单改children仍会失败。
- 修正：按schema分派只读reader，分别验证旧bytes摘要、JSON结构、Run身份和输入引用，再构造child输入；无效/缺失输入继续拒绝。0.2/0.3的`pre_a06`必须由可信source证据证明policy absence，不能把0.4丢失policy文件降级为legacy。公共request继续只接收locator和digest。
- 0.3需要独立正向fixture和source adapter，证明真实source revision、stable paused/terminal head及单coordinator CAS；目前代码与child tests没有该路径。这里是尚未交付的验证任务，不能把缺少历史production 0.3 creator自动当成无法实现，也不能伪造revision来通过测试。

### R3 — P1：正常external结果消费主路径尚不存在

- 证据：[pause.py](../../../src/lqcd_agent/control/pause.py)的`resume`在claim前只接受`recovery_decision | human_response`；`external_result`直接被拒绝。已有external tests主要覆盖Pause binding和cancel/terminal interrupt。
- 影响：无法满足三种Pause reason均能恢复一次；Code Agent的`external_prestart_only`也缺少通向合法`attempt_execution`的完整消费路径。
- 修正：用Host-owned typed domain adapter提供外部事实，由production control实现exact normal resolution、claim、唯一settlement、consumed、running checkpoint、授权、结果消费、binding release及final checkpoint。B03负责真实backend/Code schemas，B02必须完成自己的控制顺序和所有权，不能等待B03替它实现。

### R4 — P1：interrupt和post-claim故障闭环尚未交付

- 证据：`ExternalInterruptOperations.interrupt`只构造absent/opened Pause snapshot，拒绝prepared Pause；`_plan`明确拒绝`recoverable_delivery`。除generated protocol外，production control尚无`consumption_failure_*`实现。
- 影响：safe recoverable timeout不能完成原scheduled Attempt的确定性失败消费；prepared阶段发生terminal interrupt和claim后7个边界的失败不能视为已完成验收。
- 修正：按generated graph实现prepared的aborted/quarantined处置、recoverable timeout消费，以及原resume owner的7×4消费者stop/Run-authority分类。不得新建第二terminal owner，不得把backend safe-stop当作consumer safe-stop，不得伪造Code artifact补尾部。
- Ownership说明：冻结inventory中`post_claim.*`的28条完整跨domain cases归B03；B02需证明其原票控制半边和相应control phases，不得把28条改归B02，也不能以B03归属为由跳过B02控制实现。

### R5 — P1：typed preparation接口只完成N/A，grant控制顺序仍有缺口

- 证据：[operations.py](../../../src/lqcd_agent/control/operations.py)的`AdvanceOperations._snapshot`拒绝非空`budget_grant_id`，并把`target_preparation`限制为`not_applicable`；Analysis存在Code Bundle时拒绝。Recovery continue同样拒绝需要原Analysis preparation proof的情况。
- 修正：先对照generated contract落实适用preparation的typed proof校验/提交和能力授权顺序；不适用分支继续提交明确N/A。B02只接收、校验并发布可信adapter结果；真实fresh Analysis workspace/subprocess属于B03，产品grant决策与容量策略属于B04。B02不得自造grant，也不能把现有“全部拒绝”当成通用接口已完备。

### R6 — P1：功能测试与机器验收尚未连接

- `acceptance_matrix.json`只有B00/B01；本次真正运行`--mode construction --ticket B02`返回`invalid_input / construction / ticket_id`，不是B02已有30项测试未全绿，而是尚无可验收slice。
- Frozen registry共有324个boundary，其中B02拥有205个，对应1,488个before/after/outcome runtime cases；当前所有B02 `hook_ref`均为空。全局2,286个runtime gaps还包含B03的654个、B04的144个，不能全部归为B02。
- 需要把production入口、实际hook触发、fresh passing nodeid、exact expected trace和requirement映射一起接入；只添加30条矩阵标签、继续累积pytest数量或运行成功返回值检查，都不能完成本票。
- B00C01已经要求测试Host确定性分配随机identity、使用可信FakeClock，且禁止trace抹掉identity。先验证一条真实start→Pause→resume→close的fresh exact trace，再铺开其余路径；不能等全部代码完成才第一次检查验收接线。

## 执行顺序与每步出口

以下是原B02的续执行检查表，不是第二套状态机，也不改写原票要求。

| 步骤 | 工作 | 必须拿到的证据 |
| --- | --- | --- |
| 1 | 独立批准并完成B02C01 | 真实0.2 source replay成功、缺失表示绑定、0.3/0.4不被降级、source不变、旧格式负向回归 |
| 2 | 先打通验收纵向路径和兼容fixture | 一个真实control流程的production hook、fresh evidence和固定exact trace；0.3 reader/CAS正向与竞争用例 |
| 3 | 完成normal external与typed preparation控制半边 | prestart不得启动Attempt；claim/settlement/checkpoint后只授权一次；适用proof与N/A均验证 |
| 4 | 完成interrupt、post-claim与所有仲裁分支 | prepared/opened/absent、三interrupt variants、7×4控制分类、唯一owner及不可重跑副作用 |
| 5 | 逐组完成restart/concurrency和registry接线 | 两个真实独立进程；B02的205个boundary/1,488个cases逐项有有效绑定和相应结果，未实现后续domain保留原owner |
| 6 | 最后一次源码固定后执行整票验收 | B02 construction 30/30；累计56 covered、75 remaining；B02所属runtime缺口为0；final只剩后续owner/exit的明确缺口 |

`105 remaining`是全局映射缺口，其中30项属于B02、75项属于B03/B04；不是B02还欠105项功能。B02完成也不等于Phase B或默认产品图完成：global passed仍null，两全局完成标志仍false，默认0.2 CLI不切换。

最终还须完整pytest、Phase B focused、A02/A03 regression、compileall、冻结摘要、links、scope和stale-documentation通过。Final非零本身不算成功；必须核对剩余ID/owner，不能含解析错误、collection错误或无效证据。

## 本次验证与交付状态

- Fresh evidence目录：`/private/tmp/lqcd-agent-b02-audit-yztzribs/`。
- B00 construction 15/15；B01 construction 11/11；B02 construction按缺失slice失败。
- Final负向报告只有105 coverage、2,286 runtime、15 exit gaps；global passed=null、`requirements_zero_gap=false`、`phase_b_complete=false`。
- 真实legacy诊断见该目录`legacy-reproduction.json`：4条records，输入digest正确，无fingerprint，公共reader拒绝，0个新operation，source bytes不变。
- Phase A validator和generated protocol byte check通过；protocol/catalog exact SHA未变。
- 本次重新运行`RUN_LIVE_LLM_TESTS=0 pytest -q`：**778 passed in 288.39s**。这是当前完整suite的绿色基线，不能替代缺失的B02 acceptance。

本次交付为审查报告及`status: review`的B02C01草案；未把草案升级ready，未修改B02冻结正文，未声称兼容问题或B02已修复完成。按仓库治理，新增兼容表示需用户明确批准后实施；其余R2–R6主要是原B02范围内的未完成工作，无需为每条重新批准原范围。
