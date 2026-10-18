---
ticket_id: B00C27
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C25, B00C26, B04]
---

# B04 原恢复记账与 Host 身份 fixture 接续

## Goal

补齐C26执行中实测的两项合同缺口，并承接C26全部剩余来源实现与验收：显式区分原重复调用的无业务效果CAS记账；只在C26原生来源探针中使用有界、确定性的原Host UUID fixture，使父进程恢复创建的真实后续operation可双fresh exact。保留真实ID、原恢复行为和旧来源解释，不增加新的trace/proof版本。

C26/B04是纠偏目标，不要求先completed。本票为review，创建不代表批准、实施或C26/B04恢复。C26正文保持冻结；本票若获批准，仅以本票明确的补充条款衔接其矛盾部分，其余原要求全部继承。

## Why

2026-10-14 C26执行根 `/private/tmp/lqcd-agent-b00c26-execution-20261014-pvm54zpa` 保存同一输入 `b2eb9b024a87aad9ed5c5400faecf66c5fef7d3fc3e8725a0f50f07d861df35d` 的原生反例与真实request/receipt/S0–S3/SQLite：

- `budget.resource_settled.after.committed_result_replay` 两fresh中，原重复`publish_budget`均使同一capability的revision从11变为12；`artifact.transition_before_target_started.after.materializable_publication_prefix`两fresh的原重复`publish_started`使revision从4变为5。行payload和Run文件保持，未复现重复Agent effect。原`InvocationLeases._save`对每次合法调用执行CAS revision+1。这不是SQLite物理布局变化，C26“无新增业务写入”不能被静默改写成忽略该字段。旧C25预算诊断在同输入另两fresh仍通过。
- `budget.invalid_response_allow.after.committed_result_replay`两fresh实际完成、S0规范化exact；父进程恢复通过原`PauseOperations._invalid_human_followup`创建新的真实publish_pause owner。原Host UUID fixture只覆盖child，不覆盖parent。S2/S3的旧0.11均合法，但operation_id及派生execution/checkpoint摘要不同。不能把Host身份冒充provider opaque字段，不能删掉后态或放宽旧normalizer取得exact。
- C26已完成的局部预检证明S0可由原0.11验证，六类路径的四阶段来源可以保留、S0私有视图重验exact。另已识别并在新被动collector候选中隔离S0前回滚的child callback，避免在新epoch重复revision时将旧回调当作新owner观察；原process source完整保留。该项仍须最终meta验收。

原始证据入口：`repeat-contract-probe-results.json`、`repeat-and-identity-contract-audit.json`、`repeat-contract-probes/`、`post-source-preflight-v2/`、`private-s0-projection-audit-v2.json`和`stop-input-manifest.json`。未完成的独立verifier草稿另行归档，未启用0.12 dispatch。上述事实不证明production故障，也不证明C26整票已完成。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/tickets/TEMPLATE.md`、`docs/SECURITY_AND_DATA_POLICY.md`。
- [冻结C26](B00C26_B04_FAULT_SOURCE_AND_OWNED_ACTIVATION_HANDOFF.md)、[C26实际记录](../completions/B00C26_COMPLETION.md)、[候选来源状态](../corrections/B00C26_B04_FAULT_SOURCE_CONTRACT.md)。
- [冻结B04](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[B04记录](../completions/B04_COMPLETION.md)、[C25](B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md)及其独立合同/完成记录。
- C26原Read First全部来源合同、原始反例和本票Why列出的新反例。
- `src/lqcd_agent/control/{capabilities,coordinator,pause,interfaces}.py`只读；`tests/phase_b/helpers/{host_identity_fixture,b04_fault_sources,b04_process_binding,b04_publication_cases,b04_control_cases,control_traces}.py`。

## Scope

- 对C26 S2→S3约束作窄补充：不新增业务效果、settlement或owner变化；允许下述原重复publication调用中精确可证明的同payload CAS记账，并保留其实际revision变化。
- 显式C26 native模式的父恢复Host identity fixture接续，记录真实分配来源；不修改production UUID实现，不将该fixture安装到默认C25/legacy路径。
- 完成C26尚未交付的0.12/proof0.9 projector、四阶段独立anchor验证、精确差异/调用来源、四消费者、144双fresh、全部拒绝/敏感性与最终验收。两项窄修复通过不等于本票完成。

## Non-goals

- 不修改production primitive以取消CAS、不改变原恢复顺序/请求/outcome/断言，不增加budget或stop authority。
- 不定义全局identity别名、不删除Host UUID字段、不规范化任意hex、worker、revision或材料，不改0.1–0.11/default。
- 不登记B04正式owned，不代替47construction/144owned或B05，不commit/push，不新增依赖。

## Allowed Files

- C26原允许的`tests/phase_b/harness/fault_source_trace.py`及`trace.py`新dispatch；`{trace_proof,a05_trace,ordinary_trace,ordinary_maximum_trace,product_failure_trace,prior_code_evidence_trace,ordinary_publication_prefix_trace,unconsumed_code_final_trace}.py`仅原有界只读source resolver接缝，原验证条件保持。
- `tests/phase_b/helpers/{b04_fault_sources,b04_process_binding,b04_publication_cases,b04_control_cases,control_traces}.py`、`test_b04_runtime_cases.py`：C26原被动接线，加本票明确批准的测试Host identity fixture作用域。可调用既有`HostIdentities`，不得修改其实现或安装到production默认路径。原process-hook/Session协议保持。
- C26三个专用meta文件、`fixtures/b00c26/`、`expected_traces/b00c26/`；新增`tests/phase_b/test_b00c27_recovery_fixture_contract.py`及`fixtures/b00c27/`、`expected_traces/b00c27/`。
- C25仅原已获准的一项lifecycle测试；其余29项覆盖及拒绝语义保持。
- `tests/phase_b/acceptance_matrix.json`仅B00/final/A07-META-006或015新增场景，不改B04 slice/bindings。
- 本票及C26 YAML；独立C27 completion/来源补充合同、C26 completion/候选合同、B04 completion/maintenance追加事实。
- `docs/{README,REPO_CURRENT_STATE,STATE_SCHEMA,ARTIFACT_CONTRACTS,VERIFICATION_GUIDE,DECISION_LOG}.md`、Phase B Overview、completion/corrections索引；B04 YAML仅最终独立入口通过后lifecycle。

## Do Not Touch

全部`src/`、Phase A、protocol/catalog/registry/obligations/seals、case IDs/分类/owners、冻结票正文、旧expected/fixtures/sealed/native证据、旧Session/hook/validator规则、legacy、依赖、实际数据及accepted/Human记录。不得调用新effect修补证据、复原故障文件或过滤失败。

## Requirements

1. **入口与全量责任。** 保存执行前快照、C26/C27冻结正文、当前输入及容量preflight；仅ready票可启动。逐条建立C26 Requirements 1–10/验收映射，明确当前候选哪些尚未实现。补充获批准后才实施；不把本轮partial当已通过。
2. **精确CAS分类。** 原capability必须同ID、同authorization、worker、invocation epoch、state和完整payload。只允许原工厂实际重复`ArtifactEffectPort.publish_budget`或`InvocationLeases.publish_started`通过原`_save`造成的revision变化；增量必须等于有原始调用前后来源证明的成功保存次数。保留完整S2/S3行及物理bytes，在normalized明确记载类型和delta。任何额外row、payload、owner/epoch、operation phase/revision、settlement或domain变化仍拒绝；不得全局忽略revision、时钟或整个table。
3. **派生collector文件。** 若同payload新revision生成新的原C22 prefix evidence文件，完整保留并逐字段核验其真实journal revision、绑定、publication及文件名摘要；只能允许由该实际捕获生成的精确派生文件，不能按目录名放行任意新文件。原Run byte-equal断言保持。
4. **原Host fixture接续。** 仅显式C26 native来源模式，在原父恢复操作之前进入既有HostIdentities作用域；seed使用固定完整case ID与独立的父恢复namespace，避免与child分配冲突，同一个first/repeat/reentry序列保持同一provider和连续ordinal。Session token、process nonce、真实PID、时间与故障内容不固定、不改写。退出/异常必须恢复原provider；unit-only、其他node或不匹配binding不得进入此模式。原child request/receipt及其既有fixture保持。
5. **真实分配证明。** 原始捕获保留实际allocation site、ordinal、UUID、namespace及S0–S3分配前后状态，并绑定同一native anchor。候选不能自行声称已使用fixture。校验生成出的真实后续operation与原parent/decision/Run请求关系；UUID仍出现在真实journal和旧0.11规范化结果中，禁止通过替换raw/semantic ID或临时monkeypatch normalizer获得exact。仅本条批准既有测试Host UUID provider的有限作用域，不批准其他production/文件API monkeypatch。
6. **全恢复入口审查。** 覆盖invalid-response allow后续publish_pause、halt后续close_run、ordinary started/budget/completion、transition/grant、Code→Analysis及owner race；先核对所有原18 boundaries的父/contender分配与重复保存入口，再运行144双fresh。若contender会分配新identity，须在同一case/原恢复角色下明确作用域和单owner约束，不能以worker胜者变化或省略观察取得exact。
7. **S0与后态。** 保留真实child退出和receipt消费后S0边界；只从已证明durable的S0事件接续新被动collector。原回滚callback仍留在原source中，不能在新epoch相同revision上冒充新观察；新增负向覆盖错误提升该callback、漏记真实恢复phase。S1/S2/S3 raw可用时由原来源规则独立验证；不可构成合法raw时保留实际错误和原validator拒绝，不以S0替代后态。
8. **完成C26全部未交付部分。** 实施闭合proof/anchor、完整文件/SQLite/aux/workspace来源、真实call参数/owner/return或exception、contenders/reentry、fault及合法recovery精确差异、S3/live对照、四消费者和candidate全量重算hash仍拒绝；补齐C25合法绑定/未绑定/正式结果伪造拒绝；全部meta只属B00。
9. **回归、敏感性与容量。** 两项本票反例至少各两fresh，旧规则/默认行为保留；合法材料、真实故障/恢复/CAS差异影响normalized，非法revision或fixture rebinding被四消费者分别拒绝。最终固定当前输入完整原4578加C26/C27新增、legacy325、同Session独立B02 1410/B03 645、fresh construction15/11/30/28、final具体47/144/15，原144 source-bound主trace双fresh exact。容量须重新实测完整外部根、全部raw/anchor/压缩快照、开发证据和私有峰值；可以无损压缩/按内容去重保存新快照，但完整清单、原bytes摘要、独立重读和保留要求不减。不得删除native/sealed/当前反例，不放宽timeout/exclusion。
10. **独立交接。** 本票必须完成上述共同实现和验收才completed。随后按批准补充对C26原条款逐项独立审计；同一固定代码/验收输入可复用原报告，仅文档/lifecycle交付另存manifest，不retag Session、不假称重跑。C26整票完成后再独立B04入口，已知Stop消除且输入满足时才恢复ready。保留131required/84mapped/47remaining、2199cases/324boundaries/28post-claim、B04 18/144且owned0、15exit、原owners及PhaseBfalse，不保证B04剩余产品工作自动完成。

## Deliverables

- 本票两项窄补充及C26完整来源实现、逐字段独立合同、专项tests/fixtures/expected。
- 原反例对照、144双fresh及四消费者全部正负、完整当前输入回归报告和容量/范围/冻结审计。
- 独立C27 completion、C26逐项验收和B04入口报告；历史与失败完整保留。

## Acceptance Criteria

- 原预算11→12、started4→5均保留真实CAS行，证明无新effect而严格拒绝任何越范围变更；默认C25仍通过。
- Human allow/halt的后续owner来自原生产调用和被绑定的Host fixture，两个fresh完整后态旧0.11仍通过且exact；没有删除UUID或扩大normalizer exclusion。
- 候选伪造fixture分配、错parent/decision/Run、跳ordinal/重复UUID、foreign worker/epoch、额外CAS或丢失真实call均拒绝；异常退出恢复fixture。
- C26全部Requirements及原18/144、四消费者、full/legacy/owned/construction/final通过；仅修两个反例不能completed。
- 原src/legacy/旧解释/冻结正文/IDs/owners/历史证据保持，独立交接不代计B04 owned。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b00c27_recovery_fixture_contract.py tests/phase_b/test_b00c26_fault_sources.py tests/phase_b/test_b00c26_trace_consumers.py tests/phase_b/test_b00c26_owned_activation.py tests/phase_b/test_b00c25_process_session_binding.py
pytest --collect-only -q
pytest -q
python -m compileall -q src tests/phase_b
git diff --check
```

正式验收沿用原C04有界机制，保留每批request/envelope/output并逐批监测磁盘；全量与独立owned必须同最终输入Session。无资源时停止，不缩减集合。创建阶段只做模板、依赖、链接、scope、冻结摘要及diff检查。

## Stop Conditions

- 需要修改production、case/owner、旧normalizer或原Session/hook协议，或需要超出本票的fixture/API替换。
- CAS变化超出已绑定原调用的精确同payload记账，出现新的业务effect/settlement/owner或不明恢复写入。
- 不能以原native证据证明Host分配、父子operation关系、四阶段/调用完整性，或只有删除identity/回调/失败才能exact。
- 全144或完整当前输入验收出现本票未覆盖的新来源/生产缺陷；资源不足且无已授权安全替代。

## Required Documentation Updates

C27独立completion/合同、C26独立逐项复核、B04 completion/maintenance追加事实；Docs/Overview/completion/corrections Index、Current State、State Schema、Artifact Contracts、Verification Guide及批准实施后的Decision Log。C26/B04恢复只按独立门禁；旧历史和冻结正文不改。
