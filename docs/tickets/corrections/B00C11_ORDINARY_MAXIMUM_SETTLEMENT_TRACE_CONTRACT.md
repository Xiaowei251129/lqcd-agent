# B00C11 ordinary maximum 与 Human snapshot 来源合同

2026-10-02。由[冻结C11](../phase-b-graph-harness/B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_HANDOFF.md)及[批准C12](../phase-b-graph-harness/B00C12_HUMAN_REQUEST_PACKET_TRACE_HANDOFF.md)实施验收。Request packet和closed Host receipt见[C12补充合同](B00C12_HUMAN_REQUEST_PACKET_TRACE_CONTRACT.md)，实际逐项结果见[C12完成记录](../completions/B00C12_COMPLETION.md)及[C11独立记录](../completions/B00C11_COMPLETION.md)。本合同是test-owned来源证明，不授予运行、恢复或停止authority；[C10基础合同](B00C10_ORDINARY_RESOURCE_TRACE_CONTRACT.md)继续有效。

## 版本、声明和原关系

仅trace0.7/proof0.4选择MaximumProjection。Proof保留原0.3字段，并新增ordinary_maximum_settlements。每项闭合为schema_version,reservation_head,settlement_head,capability_id,reason_code,evidence,observation，version0.1；与实际ordinary actual=null settlement逐项set-equal，missing/orphan/duplicate严格拒绝。非maximum与unsettled前缀不声明此项。

Evidence/observation沿用closed {schema_version,profile,sha256,content}，version0.1，profile分别maximum_evidence/maximum_observation。先raw SHA、strict parse与canonical reserialization，再核对实际ledger reservation/settlement、resource、capability、Run/Attempt、唯一settlement及原committed producer operation/epoch/revision。Evidence SHA必须等于真实settlement evidence_digest；原actual分支继续C10校验。Direct异常或实际Host receipt不伪装成ordinary outcome。

## 实际观测与分类

Observation闭合为schema_version,resource_operation_id,call_disposition,clock_read_state,clock_epoch_before,clock_epoch_after,start_at,end_at,hard_usage,host_error，version0.1。Timestamp闭合为source,wall_seconds,monotonic_seconds，数值finite/nonnegative；epoch为原string或实际缺失null，error仅type/message。

| read state | 必须具备的实际事实 |
| --- | --- |
| complete | returned，原start/end均成功，有真实outcome，callee exception=null |
| callee_raised_before_end | raised、真实exception、outcome=null，原start成功、未执行end读取、end=null、Host read error=null |
| read_failed | 原callee返回后Host确实尝试end读取并失败，保留真实Host error；不能用漏采或callee展开冒充 |

分类优先级clock_untrusted→duration_overrun→callee_exception。Clock违规须有实际epoch/source变化、回退或真实read failure；异常未执行end或hard usage unknown本身不触发clock不可信。可信原间隔超过reservation timeout才是overrun，保留原实际返回，即使未发布domain artifact。三个原因均无证明时maximum拒绝。

Hard usage闭合{state,value}；unknown/null保留原因与已证明调用次数，不能改零，也不新增独立usage-unknown原因。Known四维vector按实际resource kind、调用一次及可信间隔核对。正常可信返回token/cost unknown仍走actual。原actual=null记满reservation maximum，不退款；typed token/cost unknown不等同hard usage或零。

被动Clock wrapper每次原now只委托一次，返回同一Timestamp或抛同一原错误；记录原边界与callee入/出epoch，无补读异常end、跨阶段借时间、effect重派发、patch生产Clock。实际读失败若作为正向，必须真实采得；当前正向覆盖真实epoch变化，回退的fencing分支保持unsettled。

## Authority与真实前缀

Maximum只证明费用来源。同步effect真实退出、原owner/lease有效且原合同允许时，原Host meta经原port结算，原Invocation completion及close_run实际形成failed closure。不能据此声称远程provider停止。原unsettled、expired/nonowner和clock回退导致无法安全收尾的分支保持running/unsettled或原recovery_required，不补造终态、不切新resource ID重试。

LLM/tool及scoped LLM异常/overrun均保存实际return或null；没有domain artifact时遵守原no-output合同。Code aggregate/verification仍原A05 profile，无新resource kind或slot。

## Protected Human snapshot与授权来源

复用原ordinary_members/protected_snapshot_registered；同case/run、protected_kind=human_response、唯一payload.json、artifact/response identity和canonical human_responses/<response_id>/payload.json逐项核对。Root来自可信Session/Run owner；仅该canonical相对引用或exact绝对引用可接受，拒绝别名、traversal、symlink、foreign root/Run/member及同内容其他文件。

实际原文件bytes/SHA/size和strict JSON必须与registration、declaration、submitted payload_snapshot相等。原resume input/operation、prestart_records_committed publication bytes、producer epoch/revision、observer phase/owner和原history原记录相等；不要求整个resume completed。Submitted/validated/consumed原request/response/locator/action一致，未发生事件不能补造。

经过校验的human_response.payload_reference、实际grant_issued.payload.response_reference及原grant source只作同源snapshot binding：case/run、response ID、canonical member、真实snapshot source。未知字符串保持material；raw/source heads先校验，原DAG完整。Grant关联还核对validated approve_budget_window、request scope、fingerprint/occurrence与single-use；human_scope核对consumed、authorized target Attempt/action/scope和同一snapshot。

实际双fresh Human trace保持recovery_required及真实validated，没有消费、grant或Work。Grant/remediation链只在真实locator入口后以closed contract-only材料验证，contract_only=true、work_dispatched=false、B04_owned=false；不注入实际trace，不计144 runtime。

## 验收与接续

双fresh实际来源fixed exact、material sensitivity、全部strict负例及四消费者通过；旧0.1–0.6原接受/拒绝和golden/fixtures/seals保持。C12补充正式B00 final meta，不改required/case/owner，131 required、84 mapped、47 remaining、2199 cases、324 boundaries、28 post-claim、15 exits保持，global passed=null、phase_b_complete=false。

完成须有当前固定fresh Session的来源meta、B02 1410/B03 645独立owned与完整repository suite、fresh construction15/11/30/28及final exact47/144/15负向入口。所有逐项依据在C12记录，验收manifest与后续文档/lifecycle事实追加明确区分。C12 completed后C11仅独立证据复核与生命周期交接；C11 completed后才复核B04入口。B04 Human validator/physical-node、审批/terminal区分、Host字段、高风险/歧义guard、ordinary实际收尾和Code/fallback/fresh Analysis/fingerprint/grant及47/144仍未完成。
