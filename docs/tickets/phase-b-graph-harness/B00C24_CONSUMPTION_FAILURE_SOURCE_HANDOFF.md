---
ticket_id: B00C24
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C16, B00C21, B00C22, B00C23, B04]
---

# Resume ConsumptionFailure 的原始失败来源交接

## Goal

补齐 C23 必验的 Resume-first ConsumptionFailure 来源，使真实 normal final、原 Resume owner 的 failed/unavailable 收尾、resource/active-time settlement 可以被显式 trace 0.11 / proof 0.8 严格验证。仅扩展尚未完成的 C23 新版本；0.1–0.10/default 原解释和拒绝不变。

C23、B04 是纠偏目标，不要求先 completed。只有用户批准并登记 ready 后才能执行；执行期间 C23、B04 保持 blocked。本票完成后独立复核 C23 入口，再按原授权继续 C23；B04 仍须等待 C23 整票验收和独立入口复核。

## Why

C23 已局部实现未消费 Code 来源，并通过 B04 七类停止路由的双 fresh 正向检查（7 passed）。在冻结 Requirements 4 的 Resume-first 分支，原产品 Host 生成 normal safe-stop final，原 Resume claim 后真实 consumer 拒绝或 verification 返回超时，原 ConsumptionFailure 完成 failed closure。final 未改写，唯一 Resume owner 结算并释放原 binding，无 Code/Analysis registration，无第二次 Backend dispatch。

两个模式各两个 fresh 根均在旧 collector 的 active_interval_settled 分支失败：它只尝试普通 status/artifact 或 Code delivery 摘要，而实际 evidence_digest 是原 failure_id_digest。旧 a05_trace.references 同样在通用 refs_at 扩展点之前要求普通 completion/delivery 来源；只增加 C23 声明不能到达该扩展点。

另一项同时发现的缺口是 failure identity 来源：生产 ConsumptionFailure.reserve 以 owner/source_phase/source_revision/epoch/cause_type/cause 计算摘要，但持久存储保留 failure_id_digest、原阶段/epoch、失败快照和停止/closure journal，未保存 cause_type/cause 的完整摘要原文。旧 failure_identity profile 要求完整原文。不能从测试标签、错误常量或后续 Attempt.error.message 反推原文，也不能假造 receipt。

反例及独立只读存储审计：`/private/tmp/lqcd-agent-b00c23-execution-20261013-e7t1vzzy/consumption-failure-source-blocker.json`；实际命令日志 `probe_modes.log`、`probe_failure.log`。该材料是当前工作树的 unit-only 反例，不是最终 native Session 验收。

补充审查另在两个 fresh missing_drain 根复现：分别 normalize 成功但三个 normalized head 不相等，normal/attached 对照相等。未被 ingress 接纳的 Backend 返回含随原 task/manifest/receipt 派生的 seal claim；当前 Fake 在 dispatch 中真实生成其 preimage，却只留下返回摘要。新 projector 保留整份 raw SHA，不能证明其跨 fresh 的语义等价。另实测 external normal/safe_stop 与 Resume consumer unavailable 同时成立，生产正确 recovery_required，当前 projector 却以 external proof 推断 terminal owner committed 而拒绝。审查材料位于 `/private/tmp/lqcd-agent-c24-review-7cztmaaa`；本票同时闭合这两项，不将局部 normalize 成功当作 exact 验收。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/tickets/TEMPLATE.md`。
- `docs/SECURITY_AND_DATA_POLICY.md`、`docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`、`docs/VERIFICATION_GUIDE.md`。
- [C23](B00C23_UNCONSUMED_CODE_FINAL_STOP_SOURCE_HANDOFF.md)、[C23 completion](../completions/B00C23_COMPLETION.md)、[B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)。
- A03/A04/A05/A06/A07 冻结合同、CONTROL_PROTOCOL_0_4.json 的 consumption failure/active time/terminal 合同。
- `tests/phase_b/harness/{a05_trace,ordinary_trace,prior_code_evidence_trace,ordinary_publication_prefix_trace,unconsumed_code_final_trace}.py`。
- `tests/phase_b/helpers/{control_traces,unconsumed_code_final_sources,b04_code_product,b04_stop_routes}.py`。
- 只读 `src/lqcd_agent/control/{pause,operations,capabilities}.py`、`src/lqcd_agent/code_agent/{verification_resources,subgraph,external_operation}.py` 及上述 fresh 原 SQLite、journals、Run 文件。

## Scope

- 先端到端预演 C23 所有剩余必验分支，盘点 ConsumptionFailure 原存储中的失败身份、claimed/consumed Pause、started/uncertain capability、已结算/未结算 verification 和 safe/unavailable closure；一次覆盖已复现的完整来源链。
- 新版本从原持久失败快照及 owner journals 验证 failure identity，不需要也不声称恢复未保存的错误原文。
- 仅为新版本增加旧 A05 projector 的可选 active-time 来源扩展点；旧分支和默认执行路径保持字节、接受/拒绝不变。
- 完成 C23 的新 projector/collector、专用 fixtures/tests/expected 和真实四消费者接线，保留全部冻结验收项。
- 仅显式 0.11 被动保存 Fake Backend 原实际生成的未接纳 claim preimage；绑定原 immutable 返回、producer/task/manifest 和当前 Session，逐项验证后规范化有来源的引用。该审计材料不发布为 Run Host seal，不产生停止、注册或消费 authority。

## Non-goals

- 不修改 production、Phase A、wire/schema 0.4、失败/停止结果、预算算法、authority 或 effect。
- 不新增生产 receipt，不补造 cause，不改旧 failure_identity profile，不把停止证明、最大记账、domain registration/consumption 混同。
- 不完成 B04 47/144 或 B05 exit adapter；meta 不计 B04 owned。
- 不 commit/push/PR，不重标旧 Session 或重写历史结果。

## Allowed Files

- `tests/phase_b/harness/a05_trace.py`：仅添加 opt-in active_interval_settled 来源扩展点，由新 projector 显式启用；旧 projector 实例、旧 versions/default 原分支保持。不得改旧 typed/material/checksum/owner/registration 校验或降低其要求。
- `tests/phase_b/harness/unconsumed_code_final_trace.py`、`tests/phase_b/helpers/unconsumed_code_final_sources.py`：补齐 C23 新版本的持久 ConsumptionFailure 来源与原未消费材料闭包。
- `tests/phase_b/helpers/control_traces.py`：仅显式 0.11 的被动来源采集；不猜错误原文、不伪造 publication。
- `tests/phase_b/helpers/b04_code_product.py`：仅显式 0.11 保存原 Fake dispatch 已实际生成的 change/seal/audit/patch/receipt/result preimage 及来源绑定；old/default 不采集，原 effect、返回、停止与 dispatch 次数不变，不重新计算或补造历史缺失材料。
- `tests/phase_b/test_b00c23_unconsumed_code_final.py`、`tests/phase_b/test_b00c23_trace_consumers.py`、新增 `tests/phase_b/test_b00c24_consumption_failure_source.py`。
- `tests/phase_b/fixtures/{b00c23,b00c24}/`、`tests/phase_b/expected_traces/{b00c23,b00c24}/`。
- `tests/phase_b/acceptance_matrix.json`：仅 B00 owner/final、原 A07-META-006/A07-META-015 meta 入口；不得增加 registry bindings、sealed cases 或 B04 ownership。
- 既有 `tests/phase_b/expected_traces/`：仅完整 preimage 审计后的 runtime fingerprint/可证明派生 head 离线同步，保存 before/after raw 并双 fresh 验证；禁止材料语义或 exclusion 变化。
- 本票 YAML；新增 `docs/tickets/completions/B00C24_COMPLETION.md`、`docs/tickets/corrections/B00C24_CONSUMPTION_FAILURE_SOURCE_CONTRACT.md`；C23 completion/source contract、B04 completion/maintenance 仅追加。
- `docs/{README,REPO_CURRENT_STATE,STATE_SCHEMA,ARTIFACT_CONTRACTS,VERIFICATION_GUIDE,DECISION_LOG}.md`、Phase B Overview、completion/corrections 索引。
- C23 YAML 仅独立入口复核后的 lifecycle；本票不直接恢复 B04。

## Do Not Touch

- 全部 src/、Phase A/generated contract、旧 projectors/validators（上述唯一 opt-in 扩展点除外）、legacy tests、依赖。
- 旧 0.1–0.10/default 的规则、sealed evidence、case IDs/分类/owner 集合、registry bindings、冻结票正文、历史 completion/correction。
- 不通过过滤/skip/xfail、扩大 timeout/exclusion、删引用、忽略 raw field 或伪造生产 hook 取得通过。

## Requirements

1. 保持 trace 0.11/proof 0.8 的顶层和 C23 unconsumed_code_sources 闭合字段不变。借其原 producer_snapshot、final、Pause 和 release owner，读取真实当前 Session 的 control database/journals。失败来源只适用于实际同 Run/Attempt 的原 external-result Resume，不能成为任意摘要的通用旁路。
2. 必须核验原 claim owner、reservation、capability identity/epoch、原 normal final、failure ownership phase/revision、original_normal_final_digest、stop phase、authority classification、唯一 terminal owner 及 actual publication。失败身份由原 durable failure_id_digest 和这些完整持久关系证明；保留缺失 cause 为不可获得，不补成空字符串、零或可重算摘要。
3. 新来源与旧 failure_identity profile 分离。原失败摘要作为被绑定的原身份/材料值保留；只对经源验证的结构性引用生成语义引用。普通 completion、delivery、已注册 Code、prior Code、Human/Grant/ordinary prefix 继续走全部原校验。每条新增引用必须有实际 owner、阶段与原 bytes/preimage 的依据；不存在的 preimage 不参与派生摘要同步。
4. active-time 扩展点只能处理本版本已验证的 ConsumptionFailure settlement：原 interval/reservation、原 Attempt、Resume owner/epoch/revision、实际 end/duration 或 conservative maximum、后续 failed/abandoned disposition 均 exact；唯一 settlement、原 failure_id 必须匹配。未注册该扩展点或验证失败时保持原拒绝，不能以失败类型字符串单独启用。
5. 同时覆盖 resource settlement、active-time settlement、Pause failure reference、Attempt.error、release、closure/checkpoint 等已复现的整条尾部来源。先 claim 后失败保留原 normal final；不得创建新的 interrupt winner、Code failed bundle、Analysis 或科学接受。原 consumer 停止/Run authority 不可证明时保留 unavailable/recovery_required。
6. 正常未消费、attached close、合法 non-success、每个停止维度缺失、实际 late integrity/verification overrun 和重复只读进入都按原 C23 验收。未通过 ingress 的真实 Backend 返回与已验证 normal result 必须分开；保留实际 raw bytes/digest，不给缺失 seal/audit/patch 虚构来源，不把 unaccepted claim 当成功材料。
7. 四消费者必须使用同一 fresh 当前 native Session、真实生产 boundary 和同一 trace；缺失/篡改 source、foreign Run/Attempt/owner、旧 epoch/future revision、伪造错误 preimage/receipt、重复 settlement、伪造 release/registration、stale Session 均拒绝。专用 meta mapping 不能改原 registry 或算作 B04 owned。
8. 最终输入完整 exact suite、legacy325、同 Session 独立 B02 1410/B03 645、fresh 原 CLI construction 15/11/30/28；final 仅原 47/144/15 缺口。保持 131/84/47、2199 cases、324 boundaries、28 post-claim、18 B04 boundaries/144 和 15 exit checks、原 owners。不得用原 C22/C23 局部结果代替。
9. 未接纳 Backend claim 的被动快照在其实际生成时保存完整 canonical 原文/bytes，绑定原 producer/prestart/receipt/immutable Backend result 和当前 Session。只读验证原始 byte SHA、logical checksum、实际 owner、声明阶段及原引用，不能从结果摘要反推或补造缺失 preimage。保留原始返回的每个材料字段，只有通过原完整 preimage 校验的 task/manifest/receipt/seal/change/audit/patch 引用才能生成语义引用；沿用既有已验证物理根和 clock 字段的解释，不扩大 exclusion。原始 bytes/digest 保留在证据中；未知或不具备来源的材料值不得变成空值、常量或虚构语义引用。Backend claim 明确标记未接纳，与真正发布的 Host seal/停止证明及注册材料隔离；原 final/containment 仍是停止结果的唯一来源。
10. 分开验证 external producer final 与 Resume consumer 的停止和 authority。显式覆盖 external normal/safe_stop 不变、consumer stop unavailable、原 Resume owner recovery_required 的组合；另覆盖 Run authority unavailable。允许原 unavailable tail 没有 ledger settlement、finished Attempt、release 或 checkpoint publication，必须与其真实 journal/Run bytes exact，不能要求或制造安全收尾才会存在的后缀。

## Deliverables

- 最小 opt-in 扩展点、新版本原失败来源验证、独立 source contract、专用正负测试及审定 expected。
- C23 全部必验分支逐项端到端结果和未完成项，完整 fresh raw/native Session/四消费者证据及 scope/frozen-body 审计。
- 独立 completion、C23 入口报告；C23 只能在其整票 A1–A6 实际完成后另行 completed。

## Acceptance Criteria

- 两个 fresh 根分别复现原 consumer integrity rejection 和真实 verification 返回后 overrun；同一 Resume owner 完成原 failure tail，normal final 不变、无重复 dispatch/effect/settlement 或 domain registration；新版本严格通过。
- actual failed 与 unsafe/unavailable 两类结果均与原数据库、lease、journal 和 Run bytes 一致；只读重放不产生第二 owner 或 effect。
- 五个停止证明维度各自缺失的路径全部双 fresh exact 相等；normal/attached/non-success 对照同样双 fresh。每份 Backend claim 原文、owner、checksum、Session 及引用的删除/篡改/跨源替换均拒绝，合法实际材料变化引起 normalized mismatch。原未接纳返回不能借新快照成为已接纳 Host seal 或成功 domain 结果。
- external normal/safe_stop 加 consumer unavailable，以及原 Run authority unavailable，分别以原端口生成；原 final 不变、无重复 effect/owner，原 recovery_required/未发布后缀保持；四消费者验证同一来源事实。
- 新 active-time 扩展点仅对显式新 projector 的完整已验证来源生效；原版本在相同反例继续严格拒绝，旧正负回归全部保持。
- 前述所有来源篡改由 collector/matrix/runtime validator/exit digest 拒绝；合法原材料变化引起 normalized mismatch，不能通过删字段稳定 expected。
- C23 原 A1–A5（含 A4b）和本票全部验收实际运行并通过。独立确认本次 source 阻塞消除后恢复 C23 ready；B04 保持 blocked 等待 C23 原 A6。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b00c23_unconsumed_code_final.py tests/phase_b/test_b00c23_trace_consumers.py tests/phase_b/test_b00c24_consumption_failure_source.py tests/phase_b/test_b04_stop_routes.py
pytest --collect-only -q
pytest -q
python -m compileall -q src tests/phase_b
git diff --check
```

完整集合使用原 bounded batch envelopes 和 validators，保留同 Session 独立 owned 1410/645、fresh 四 construction、exact final 47/144/15 和未改写的原日志。所有新证据使用 fresh `/private/tmp/lqcd-agent-b00c24-*`；不得 retag 历史 evidence。

## Stop Conditions

- 需要生产持久字段/新 receipt、改变 source wire/hash/budget/authority/失败结果，或无法只读验证原 source；不猜测原错误原因。
- 需要更改 proof 顶层/声明闭合字段、旧 profile、更多旧 projector 函数语义或本票之外文件。
- 需要放宽拒绝、伪造原文/registration/owner/停止、过滤失败或重标 Session。
- 出现超出允许派生摘要同步的 baseline/full 语义变化；实际资源不足且没有已授权安全替代。

## Required Documentation Updates

- 新 source contract/completion，C23 completion 追加实际结果、独立入口和剩余验收；冻结 C23 正文不改。
- Docs/Phase B/correction/completion 索引、Current State、State Schema、Artifact Contracts、Verification Guide、Decision Log。
- stale links/scope/frozen-body/owner 集合核对；不创建虚假的 completed 记录。
