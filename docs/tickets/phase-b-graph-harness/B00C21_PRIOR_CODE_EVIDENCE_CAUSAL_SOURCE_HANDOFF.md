---
ticket_id: B00C21
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B03, B00C15, B00C16, B00C20, B04]
---

# B00C21：产品 Code 重试的历史 evidence 与因果来源交接

## Goal

闭合真实产品 `Code 非成功 -> Coordinator -> Human -> Coordinator -> 新 Code -> Coordinator` 路径中的历史 Code evidence 科学来源，使原 Host fingerprint 与严格 trace 对同一材料独立计算一致，并完整验证 Task 的 Human authorization 来源。引入显式 trace **0.9 / proof 0.6**；保留 0.1–0.8 原解释、原字段集合及拒绝行为。

B00/B03/C15/C16/C20 须 completed；B04 是纠偏目标，不要求先 completed。本票创建只代表 review，未批准或实施，B04 保持 blocked。C15–C20 各自已完成的原验收与冻结正文不回写；本票完成也不自动完成 B04 的 47/144。

## Why

2026-10-08 B04 接续已实现产品 Code parent，组合原 B03 reservation、prestart、Pause、dispatch、normal final、Resume consumption 和新 advance；Code success/needs_input/failed 三项产品测试通过，成功分支实际执行独立 fresh Analysis。三条路径的 0.8 来源另各在两个 fresh 根通过并 normalized 相等。

真正的 Code 失败重试必须在 Task 中携带 Coordinator typed packet 所引用的前次 `code_agent_result.json`，不能删除该 evidence 或只留下 Plan。首次反例被原 prestart 的 historical evidence slot 集合拒绝 `Task evidence changed`；B04 parent integration 候选已仅补充原 advance snapshot 的失效前 Code slot，保留原 SHA、Run、Transition、registry 与 authority 检查。候选与验证记录见 [B04 maintenance](../corrections/B04_MAINTENANCE.md)。

补齐后，两 fresh 根各真实完成两次独立 Code dispatch、final 和消费，随后第二个 Coordinator 在 `product_failure_material` 拒绝 **`Code evidence lacks a scientific profile`**，Run 保持 running，没有发布第二次 failure/Grant 或制造终态。当前生产 recipe 仅接受 Task evidence 的 Plan/Analysis/Review 主成员；0.8 projector 的 `product_code_evidence` 同样排除 Code slot。C15 定义的科学 Code preimage 已存在，但没有交接它作为另一个 Task 的 historical evidence leaf 的完整 owner/时间/消费关系。

执行根：`/private/tmp/lqcd-agent-b04-continuation-20261008-89ygr3t6/`。`repeat-code-fourth/` 保存原 prestart 拒绝；`repeat-code-fifth/` 保存两次真实科学来源拒绝；`repeat-code-source/` 保存被动捕获的完整 raw proof。早期 helper/candidate 的 capability、Human payload 字段和路径错误已分别修复，不能把那些开发失败当作本票来源阻塞。

停止后只读来源审计另确认投影接缝：两份真实 stopped prefix 可以被 0.8 接受，但 normalized 有 28 个派生 head/reference 差异。完整投影 preimage 证明第二次 Task 的历史 Code `evidence[].sha256` 和 `human_authorization_ref.scope_digest` 两项仍为 **literal raw SHA**，没有绑定实际 Code member / Request scope；它们随已验证物理来源变化后传递到整条 Task/Code 后缀。第一次 Task 投影相同；只读审计仅将上述两项标记为比较占位值后，第二次 Task 的完整投影 preimage exact 相等，不修改原 hash 返回值、生产或 expected。材料在 `repeat-code-source/*-preimages.json`、`normalized-prefix-diff.json`、`task-preimage-diff.json`、`scope-binding-audit.json` 和 `repeat-preimage-audit.log`。不能删除 evidence/scope 字段或扩大全局 hash 排除；R1–R3 必须一起闭合。

原 C16 same-Run retry fixture 的后续 Task 仍只引用 Plan，证明了独立 producer/workspace/audit owner，不等于本次完整产品 packet/历史 Code evidence 路径。这是前置验收没有覆盖的产品接缝，不能靠重跑原 fixture、改旧 expected、把 raw result SHA 当科学 digest 或扩大 B04 的 B00 validator 权限解决。

## Read First

- [AGENTS](../../../AGENTS.md)、[文档入口](../../README.md)、[票据规则](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)、[验证指南](../../VERIFICATION_GUIDE.md)；
- [冻结 B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[B04 completion](../completions/B04_COMPLETION.md)、[B04 maintenance](../corrections/B04_MAINTENANCE.md)；
- A01/A03/A05/A06/A07、Control Protocol 0.4、requirement catalog；B03/B03C01 原票及完成记录；
- C12/C13/C15/C16/C18/C20 冻结来源合同与独立完成记录，特别是 C15 的 profile/field pairing、C16 的完整 owner 绑定和 C20 的显式调用入口规则；
- `graph/nodes.py::product_failure_material`、`code_agent/subgraph.py::ProductCodeHost`、`code_agent/prestart.py::commit_task`、原 schemas/artifacts/ingress/verification；
- `harness/{trace,product_failure_trace,ordinary_trace,a05_trace}.py`、`helpers/{control_traces,product_failure_sources,b04_code_product}.py`；上述执行根的 raw、真实 Task/packet、ledger、artifact history、producer 和差异。

## Scope

- 在原 Host recipe 中接受一个经过原 A05 全链验证的历史 Code 主结果作为 Task 的科学 evidence leaf；不改变原 A06 primitive 或原 A05 wire context。
- 显式 0.9/0.6 来源声明、独立 projector、被动 collector 与四消费者；原 0.8 对新 leaf 仍拒绝。
- 验证产品 Code retry Task 的 protected Human snapshot、原 validated/consumed response、父 Coordinator 和 inbound Transition 关联，优先复用既有来源；只补确有反例的专用 Task reference 绑定。
- 完成下列完整接缝验收、前置回归和 full Session，避免只修首次拒绝后立即交回 B04。

## Non-goals

不改变 topology、case IDs/分类/owners、预算算法、absolute ceilings、terminal reserve、权限、公开 schema/状态或 Backend 信任规则；不授权新的 Human 行为，不再消费 Human response，不把批准或最大费用记账解释为科学接受或停止证明。不执行 B04 剩余 47/144，不完成 B05，不 commit/push。

## Allowed Files

- `src/lqcd_agent/graph/nodes.py`：仅 `product_failure_material` 的历史 Code evidence 科学 leaf 派生与必要的局部共用读取；其余 failure/Grant/risk/stop 行为保持。
- `src/lqcd_agent/code_agent/subgraph.py::ProductCodeHost._task`、`prestart.py::CodePrestart.commit_task`：仅审定/补齐上述历史 evidence 与实际 Human reference 的 parent provenance；原 reservation/dispatch/final/消费所有者、schema、Backend、sandbox、verification、settlement 不改。
- `tests/phase_b/harness/trace.py`、`product_failure_trace.py` 及新增 `prior_code_evidence_trace.py`：仅显式新版本 dispatch 与专用来源验证；旧分支冻结。`ordinary_trace.py`、`a05_trace.py` 若确需接线，只可增加由显式新版本开启的专用 Task evidence/Human reference origin resolver，不改变旧默认、科学 hash 或既有 validator。
- `tests/phase_b/helpers/control_traces.py`、`product_failure_sources.py`、`b04_code_product.py`：仅显式 0.9/0.6 被动来源与原端口 fixture 接线。默认 0.8 及旧调用点保持；新路径不得按失败结果自动升版。
- 新 `test_b00c21_prior_code_evidence.py`、`test_b00c21_trace_consumers.py`、`helpers/prior_code_evidence_sources.py`、`fixtures/b00c21/`、`expected_traces/b00c21/`；原 `test_b04_code_parent.py` 只允许追加真实接续与拒绝测试，保留原三项。
- `acceptance_matrix.json`：仅 B00 原 A07-META-006/015 owner 下追加新版本专用 meta 接线，不计 B04 owned runtime。
- 既有 fixed expected：只允许实际 runtime fingerprint 与可证明的派生 head/reference 同步；保存 before/after raw、完整 preimage 差异和双 fresh 审计，不改原 outcome/material/owner/invariant。没有必要的新入口不批量升版。
- 本票 YAML lifecycle；执行后新增独立 `completions/B00C21_COMPLETION.md`、`corrections/B00C21_PRIOR_CODE_EVIDENCE_SOURCE_CONTRACT.md`；追加 B04 maintenance/completion 与索引，更新 Phase Overview、docs/README、REPO_CURRENT_STATE、VERIFICATION_GUIDE、ARTIFACT_CONTRACTS、STATE_SCHEMA、ARCHITECTURE、DECISION_LOG 中实际受影响说明。

## Do Not Touch

Phase A、protocol/catalog、冻结票正文、旧 sealed evidence、既有 completion/correction 历史、legacy runtime/tests/CLI、依赖、config、case/required/exit/owner/exclusion 集合、真实 provider/network/raw/accepted/secrets、control repository promotion。B04 18 boundaries/144 cases 保持未绑定事实，不能以本票 meta 代填。

## Requirements

### R1：闭合的历史 Code leaf

只接受 `Task.evidence` 中原 registry 验证的 Code bundle 主成员 `code_agent_result.json`。同 Run、完整 source owner、原 Task/Manifest/Result/Change/Verification、producer/final、seal 或原 typed absence、safe-stop 与原消费 registration 全链必须一致。该 registration 必须先于 consumer Task 的 inbound Transition，且被原 advance 的失效前 snapshot 和实际 Coordinator packet 共同选中；旧 pointer 不恢复 current。

科学 leaf 使用 C15 已批准的 Code 科学 preimage **`base_revision,base_tree_digest,final_tree_digest,changes,patch_digest`** 的 canonical digest，changes 保留原完整 ENTRY_FIELDS。它只加入新 Task 的 `input_evidence_digests`；原 `task_context` wire SHA、reservation、receipt 和 bundle bytes 不改。新 Task 的 requirements/acceptance/base/backend/runtime/path/tool/network/policy 仍依 C15 规则完整绑定；前次 Task、verification 与所有 raw 来源也必须保留完整 provenance 和 normalized material，不能借 leaf 投影删除。

原合法 host-timeout/interrupt Code bundle 必须按原 typed absence 和 Host change/verification evidence 校验；不借缺失 seal/result 伪造正常 final 或 empty/zero 内容。无法通过原 A05 安全消费的材料不是合法 leaf。普通 domain、diagnostic、Task、audit、report、authorization、未知成员不能冒充 Code leaf。不可从最新 Code pointer、裸 SHA 或 free text 猜 owner。拒绝自引用、向未来引用、环、缺失/重复/外来 declaration。

### R2：显式版本与独立来源

0.9/proof0.6 复用原 0.8/proof0.5 全部来源，新增闭合 `code_evidence_sources` 与 `code_task_authorizations` lists。前者每项 exact fields 为 `schema_version,consumer_task_head,evidence_index,consumer_transition_head,source_registration_head,source_task_head,source_result_head,source_manifest_head,source_change_head,source_verification_head,source_final_evidence_head,source_producer_operation_id`，schema_version 为 0.1；head 均引用实际已验证 raw source，index 为 consumer Task evidence 的原位置。producer/final source 沿原 C16 完整 owner 关系验证，不能把 declaration 当 authority。

`code_task_authorizations` 每项 exact fields 为 `schema_version,consumer_task_head,human_request_head,response_submitted_head,response_validated_head,response_consumed_head,snapshot_registration_head,resume_operation_id,parent_transition_head,consumer_transition_head`，schema_version 为 0.1。parent Transition 是原 Human validator -> 父 Coordinator，consumer Transition 是该 Coordinator -> 本次 Code。声明与实际 non-null Task Human refs set-equal，无授权的 Task 不得有声明；原 response/snapshot/Resume/Transition/capability 验证优先复用 C12/C13/C15，不从裸 ID 或最新 Request 猜来源。

声明集合须与所有 consumer Task 中实际读取的历史 Code leaves set-equal；不同 owner 即使 SHA 相同也独立绑定。Host 与 projector 各自从原 bytes 重算 R1，不能复用 self-reported 科学 SHA。普通 Plan/Analysis/Review leaf、其 metadata 剥离、nullable 和十二因果字段 pairing 保持 C15 原规则；没有 Code leaf 时声明为空，新旧共同合法材料计算一致。0.1–0.8 不增加字段或新 leaf 解释；同一新来源转回旧版本必须拒绝。

新版本中 Task 的历史 Code evidence `artifact_id,path,sha256` 先与声明所绑定的原 registration/member exact 校验，再把 sha256 投影为该实际 Code member 的专用来源引用，不能留作未解释 literal，也不能以科学 leaf digest 改写原 Task wire 字节。只修闭合 Task evidence 路径，不扩大 COMMON/全局 SHA alias、按名字猜 digest 或改旧版本。

### R3：Task Human reference 与单次授权

真实产品 retry Task 的 `human_authorization_ref` 必须对应 packet 的原 protected response：artifact_id/single_use_id 为实际 Human response ID，path 为该 Run 下原 payload 的 canonical relative path，sha256 为原 payload_sha256，action 为实际 validated/consumed decision，scope_digest 为原 Request scope digest。original Resume actor、decided_by、Request action/work target、Pause scope、validated/consumed response、父 Coordinator 和新 Code inbound Transition 必须一致。

用既有 C12/C13/C15 snapshot/authorization 验证表达这些关系；新版本可补上述专用 Task 引用解析，不能制造新授权。重复读 Task/trace 不再次消费 response、Grant、resource 或 effect；伪造、foreign response、同 SHA 错 owner、过期/stale authority 必须拒绝。

`scope_digest` 必须独立验证为原 Request `authorization_scope` 的 canonical digest，再沿该已验证 scope 的完整字段和原 diagnostic source 投影引用；payload sha256 必须绑定原 protected snapshot。不得把 scope/payload digest 作为未解释 literal，不按字段名剥离科学值、不删除 action/scope/path，也不增加全局 SHA alias。raw scope/Human narration 与 original owner 保留完整 provenance；新 projection 只修复经验证来源关系。

### R4：完整产品接缝交接

必须实跑 compiled product graph 和原生产端口；不能用手工 Plan-only Task 代替 Coordinator packet。覆盖 Code 非成功 -> Human 批准 Code 修复 -> 第二次 Code：第二次成功真实 fresh Analysis 和后续 close；第二次非成功真实 failure/升级或原 typed budget stop；验证 no_change、needs_input、needs_human、failed、budget_exhausted、policy_blocked 及原安全 host-timeout/interrupt 结果的合法来源与实际既有路由，不降低 risk floor 或捏造审批。不可安全消费的分支保持 recovery_required，不进入 Work。

覆盖三次同 Run Code attempt 的独立 producer/workspace/owner、旧历史保留与实际可达预算/Grant；必要审批/Grant由原 Request/Resume/Coordinator/advance 完成。不可达的绝对阈值用原 policy 可达性证明与合同单元测试区分，不能强行 patch runtime counters。Code failure/source publication 的 before/after 故障和 graph 重入保留原分类；有完整冻结 suffix 只由原 owner 物化，无 effect 重跑、退款、伪造终态。

## Deliverables

- 专用来源版本、Host recipe 最小修复和被动采集；完整 raw/preimage/owner/source 声明审计与新固定 expected。
- 逐条 R1–R4 验收对照、四消费者证据、完整当前 Session/前置报告和独立 completion/contract。
- B04 阻塞复核，区分本票已解除的来源缺口与 B04 原集成/47/144 尚未验收的责任。

## Acceptance Criteria

- A1：当前两 fresh 反例通过新版本；旧 0.8 仍按原规则拒绝新 leaf。两个 Code effects 各一次，无伪造返回、科学结果或停止事实；normalized 双 fresh 相等。
- A2：R4 全部适用原结果与成功/再次失败/安全 timeout/recovery 分支完成；Human reference、单次消费、原 invalidation 和父 owner 全链核验。
- A3：同科学内容不同 execution identity 得相同科学 fingerprint；base/tree/change/repo-relative path、selected evidence 内容、当前 Task requirement/acceptance、runtime/environment/command/policy 等合法材料变化必须改变相应科学值和 normalized material。source owner/registration变化保持不同来源，不能 alias 合并。
- A4：缺失/篡改/重复/外来/未来/环来源、错误 protected snapshot、伪造 Human、stale Invocation/Session 和 unsafe final 拒绝；旧 ordinary、Code 与 Human 规则回归。
- A5：collector、matrix、runtime validator、exit digest 四路径均验证 0.9/0.6；旧 C10/C11/C12/C13/C15/C16/C18/C20 当前入口逐项审计，默认/显式版本不自动更换。meta 不计 B04 runtime。
- A6：所有必要 fixed expected 更新只经完整 before/after preimage 与两 fresh 原来源审定；最终稳定当前输入同一 Session 全仓 exact suite、legacy325、独立 B02 **1410** / B03 **645**、fresh construction **15/11/30/28** 通过。final 具体 ID 仍仅 B04 **47 coverage/144 binding** 与 B05 **15 exit adapter**；无其他错误，不把 prior Session retag 为当前通过。
- A7：保持 **131 required、84 mapped、47 remaining、2199 cases、324 boundaries、28 post-claim、B04 144、15 exits** 和原 owner 集合；B05 draft、Phase B false。各已 completed 纠偏票原事实保持；新版本整票通过后才独立复核并依原授权恢复 B04 ready。

## Verification

```bash
/opt/anaconda3/bin/python -m pytest -q tests/phase_b/test_b00c21_prior_code_evidence.py tests/phase_b/test_b00c21_trace_consumers.py tests/phase_b/test_b04_code_parent.py tests/phase_b/test_code_prestart.py
/opt/anaconda3/bin/python -m pytest --collect-only -q
```

执行时用仓库原 native Session/CLI 完成 A6，逐项保存测试 nodeids、raw、input manifest、four-consumer reports、owner reports 与 final exact ID 审计；collect-only 或专项累计不等于完整 suite。

创建阶段只检查模板、依赖、links、scope、冻结正文摘要和 diff；不执行新版本、不改旧 expected、不写完成记录、不 commit/push。

## Stop Conditions

- 需要改变 Phase A/A05 wire/A06 primitive、预算/authority/trust、旧 profile 意义、case/owner/exclusion 或未列范围；
- 必须删除 packet evidence、伪造科学 leaf/返回/settlement/stop、猜 owner、自动升版，或放宽旧拒绝才能通过；
- 无法完成 R4 接缝的真实来源/fault/四消费者，或只能过滤失败、用历史 Session 代替当前验收；
- 出现未批准的科学 recipe 或 public contract 变化。触发时保存反例并停止，不以“来源修复完成”提前把剩余已知接缝交回 B04。

## Required Documentation Updates

执行后按真实新来源更新独立 contract/completion 和受影响 source of truth；追加 B04 maintenance/completion、当前状态、Phase Overview、文档与纠偏索引。创建阶段只追加本票 review/B04 blocked 入口，保留既有历史；不批准、不实施新规则，也不撤销 C15–C20 的历史 completed。
