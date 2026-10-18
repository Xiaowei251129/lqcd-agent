# B00C13 Human 接续与失败前缀来源补充合同

2026-10-05。由[冻结 C13](../phase-b-graph-harness/B00C13_HUMAN_CONTINUATION_SOURCE_AND_PREFIX_HANDOFF.md)批准，补充 [C11](B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_CONTRACT.md) 与 [C12](B00C12_HUMAN_REQUEST_PACKET_TRACE_CONTRACT.md)。执行结果与当前输入验收见 [C13 completion](../completions/B00C13_COMPLETION.md)。本合同修正旧 Human fixture 的分类并扩展实际接续来源；旧记录保留为其输入下的历史事实。

## 成员身份与版本

只在 trace 0.7/proof 0.4 中，以原注册 `(case, run, artifact_id)`、registration head、Attempt 与 logical member 解析 Coordinator diagnostic。相同 SHA 可以共享已核验 bytes，不能共享 owner。Human created 必须绑定 requesting Attempt 唯一的真实 diagnostic；后继 consumer/remediation 使用各自注册。缺失、重复、foreign 或篡改来源仍拒绝。没有新增 wire/schema/profile/version、exclusion 或 digest alias；0.1–0.6 原解释和拒绝行为不变。

## 原 packet 的真实生命周期位置

C12 已核验的 typed `execution_0_4` 顶层 `human_request:packet_written.packet_reference` 继续使用原 packet locator。C13 新核验的唯一后继位置是实际 ledger 顶层 `human_request:satisfied.packet_reference`：必须是同 request 的真实记录，其 Human request 字段除 status 外逐项等于原 packet_written，status 为 satisfied；previous_execution_head 必须 exact 指向同 request 的唯一 consumed response。两者绑定同一个原 publisher、registration、canonical member 和 created bytes。

仅完成上述 bytes/heads/owner 校验后，沿原 DAG 编码已核验 locator。未知 canonical JSON 容器即使嵌入完全相同的记录也保持 material。外来 request、consumer、packet path、成员及新位置不能凭字段名获得归一资格。

## 故障分类和单次执行

原 scoped observer 在 Human validator 的真实 `invocation.attempt_finished:after` 故障：submitted/validated 已真实写入，没有 consumed；原 capability 持久化了 exact completion_intent。只读核验原 resume producer/worker/epoch/phase、activation authority、started/resource prefix、execution/index/artifact history、冻结 projection/checkpoint/manifest 全部一致后，保持 in_progress/materialization_pending。原 operation 可补齐该冻结后缀；不重执行 validator/Agent/effect，不重新计算 route。

独立 `invocation.attempt_started:after` 故障没有 completion_intent，保持 recovery_required/no-consumed，不再派发。测试者知道故障位置不构成执行许可。integrity conflict 不获得 pending 资格。真实 invalid response 保留 decision=null 和非空 error，并绑定实际 Human validator finished；它不获得 validated/consumed 或 Work authority。非法动作可按原流程重提，停止链仍沿原 request 延续。两类来源都保存原 Run/request/validator/resume producer、触发边界、completion 存在性及实际 effect 计数。

committed 同 key 请求保持只读，即使 graph 尚未 advance、Run 仍 running；原 public port 继续核对 actor 与 idempotency 冲突。in_progress 的 exact materialization 与只读 replay 分开；completed graph reentry 不新增事件、artifact 或 effect。

## Human 与 terminal tail

validator 只检验当前 active request 的最新 submitted response；finished output_refs 不声称旧 publisher 的 approval。原 packet/protected response 保留，不重新注册。physical node 与 canonical attempt kind 严格匹配；外部 validator 的 HUMAN_RESPONSE Transition 不冒充产品 edge。

普通审批不创建 stop_sequence。只有原 budget_stop 的 requester/source/hash 与 Gate inbound 证明的停止链，才能穿过原 validator Transition、后继 advance、Coordinator、Memory。trace 同时核对单一 origin、连续 source/target 与 Human request；停止链只能到 Control/END，不能返回 Work。

普通 Human validation 仍要求一次 validation 加原完整 5 Control/6 Transition reserve。已合法进入停止链的 validation 核验剩余实际 tail 的 3 Control/4 Transition absolute capacity，不重复索取完整 reserve。phase_b_test 的真实 re-review 额度耗尽后，Gate 剩余 5 Control 可以完成原 terminal closure；任何批准也不派发 Work、不形成 accepted result。容量不足以接续的普通 validation/route 使用既有 typed halt 和原 close_run。Memory 使用 deterministic budget stop evidence，terminal 为 halted；最大记账、响应提交或 operation committed 本身都不是安全停止证明。

## 消费与 B04 交接

原 B00C11-HUMAN observe ID 保留，交接到独立 C13 human_prefix expected。新增批准/拒绝两类 B00 meta 只接原 A07-META-006/015，B04_owned=false。collector、正式 matrix、runtime validator 与 exit semantic digest 共用严格 0.7 来源及当前 Session；stale token/每项 digest、缺失/篡改/foreign 来源均拒绝。

旧 C11/C12 Human expected、合同/completion/raw 保留。其他旧 expected 的同步必须有原 raw 重构、双 fresh 和完整语义 preimage 审计，只允许真实 runtime fingerprint 与其派生 head/reference 变化。不能借此改变 outcome/owner/invariant。

C13 不计 B04 owned runtime。Planner dependency、ordinary 收尾、Code parent、四层 fallback、fresh Analysis、fingerprint/grant 与原 47/144 仍由 B04 实施。C13 完成且独立入口复核通过后才恢复 B04 ready；库存、owners、15 exit 与 Phase B 未完成状态保持。
