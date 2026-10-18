---
ticket_id: B00C26
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B00C22, B00C23, B00C25, B04]
---

# B04 故障来源与正式 owned 接线交接

## Goal

使B04原18 boundaries／144 cases在故障注入后仍能提交可独立重验的真实Run来源证据，并解除C25诊断meta对“B04永远未绑定”的临时假设。交付显式trace0.12/proof0.9及有界来源读接口，保留0.1–0.11和默认行为；原生产故障、恢复、case分类及owners不变。

B04是纠偏目标，不要求先completed。本票review只供审查，不代表批准或实施；B04保持blocked。完成本票全部验收及独立B04入口后才按原授权恢复ready，不代填B04的47construction/144owned或完成B05。

## Why

2026-10-14 B04接续入口保存于 `/private/tmp/lqcd-agent-b04-resume-20261014-vhavwlql`。三个原case分别运行两份fresh native Session，原生产spawn、hook receipt、工厂断言和双fresh诊断全部通过；其正式来源重验暴露：

- `budget.resource_settled.after.non_materializable_domain_gap`：按原fixture删除invocation capability后，故障前0.10证明重验被`ordinary_trace:publication_prefix_journal_revision`拒绝。
- `artifact.projection_publication.before.integrity_conflict`：按原fixture损坏canonical member后，故障前0.10证明重验被`ordinary_trace:publication_prefix_frozen_member`拒绝。
- 正向对照`artifact.bounded_state_sync.after.committed_result_replay`两fresh仍接受。确认无ExternalOperation后，仅显式选择0.11及其闭合空unconsumed声明的兼容探针保留相同正/负结果，不能靠版本选择消除缺口。
- `test_b00c25_process_session_binding.py::test_native_diagnostics_keep_canonical_registry_and_outer_hooks`固定要求canonical registry以`hook:case_id`拒绝原诊断hook。在内存中加入本来就由B04拥有的hook/binding后，原validator正确返回空owned集合，原测试却`DID NOT RAISE`；两fresh原envelope均复现。全程未修改实际registry或validator。

上述证明“工厂诊断通过”不等于“正式来源可以在故障后重验”。原strict拒绝是正确行为，不能删除故障、恢复被损坏文件、伪造capability或只用phase-only摘要绕过。C23/C24/C25的已完成交付保持，本票承接正式B04接线时新增的来源表达和meta生命周期缺口。原入口审查未覆盖这两项，不能继续沿用其ready结论。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/tickets/TEMPLATE.md`。
- `docs/SECURITY_AND_DATA_POLICY.md`、`docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`、`docs/VERIFICATION_GUIDE.md`、`docs/REPO_CURRENT_STATE.md`。
- [B04冻结票](B04_TARGET_PRODUCT_TOPOLOGY_AND_BUDGETED_LOOPS.md)、[完成记录](../completions/B04_COMPLETION.md)、[维护记录](../corrections/B04_MAINTENANCE.md)。
- [C22](B00C22_ORDINARY_SETTLED_PUBLICATION_PREFIX_SOURCE_HANDOFF.md)、[C23](B00C23_UNCONSUMED_CODE_FINAL_STOP_SOURCE_HANDOFF.md)、[C25](B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md)及其来源合同和独立completion。
- Phase A原A03/A04/A05/A06/A07、`CONTROL_PROTOCOL_0_4.json`、`PHASE_B_REQUIREMENT_CATALOG.json`。
- `tests/phase_b/helpers/{b04_publication_cases,b04_control_cases,b04_process_binding,control_traces}.py`、`test_b04_runtime_cases.py`、`test_b00c25_process_session_binding.py`。
- `tests/phase_b/harness/{trace,trace_proof,a05_trace,ordinary_trace,ordinary_maximum_trace,product_failure_trace,prior_code_evidence_trace,ordinary_publication_prefix_trace,unconsumed_code_final_trace,pytest_evidence,failpoints}.py`。
- 上述执行根的`confirmed-probes/formal-source-entry-probes.json`、`confirmed-probes/latest-source-and-binding-audit.json`、`confirmed-probes/C25-original-meta-reproduction.json`及其引用的原始request/envelope/receipt/raw/SQLite/material。

## Scope

- 仅harness新显式版本的故障来源声明、被动捕获及只读来源解析；分别证明故障前真实生产状态、真实注入动作、故障后真实存储与恢复结果。
- B04原144工厂的被动接线及同Session正式来源可消费性诊断，覆盖全部既有故障类别；不改变生产动作、原case断言或登记正式B04owned。
- C25一项meta接续修正：同时证明未绑定hook仍被拒绝、合法B04绑定后的诊断仍没有owned result、外层hook隔离及原tampering拒绝保持。
- 新版本专用fixtures/expected、四消费者meta、B00 final接线、独立验收及文档。

## Non-goals

- 不修production runtime、恢复策略、预算/Grant、authority、wire/hash、Run schema0.4或case分类。
- 不补造缺失journal/capability，不恢复被故障删除/损坏的文件，不向Run授予新写权限；不把取证快照用于生产恢复。
- 不删除故障、不更换原outcome、不降低断言、不改timeout、不扩exclusion、不skip/xfail、不把phase-only或旧Session当正式来源。
- 不完成B04的47construction、正式144owned、四层packet/context等剩余产品验收；不完成B05、不commit/push、无新依赖或真实Backend/provider/network/raw data。

## Allowed Files

- 新 `tests/phase_b/harness/fault_source_trace.py`：显式0.12/proof0.9闭合声明和只读取证来源解析；原validators仍独立验证来源和语义。
- `tests/phase_b/harness/trace.py`：仅新显式dispatch，旧版本/default保持。
- `tests/phase_b/harness/{trace_proof,a05_trace,ordinary_trace,ordinary_maximum_trace,product_failure_trace,prior_code_evidence_trace,ordinary_publication_prefix_trace,unconsumed_code_final_trace}.py`：仅增加有界、显式opt-in的只读source resolver接缝，供0.12访问经本票独立校验的原生取证快照；默认仍原物理来源，原分支判断/验证/拒绝不得改变。不得借resolver跳过owner、journal、material或Run验证。若需要其他语义变化，按Stop处理。
- 新 `tests/phase_b/helpers/b04_fault_sources.py`；`helpers/{control_traces,b04_publication_cases,b04_control_cases,b04_process_binding}.py`：仅显式0.12、四阶段被动取证、exclusive-create捕获记录/anchor、来源proof及原hook/Session转交；新捕获协议限于本票新增helper/harness，不给旧process receipt或pytest envelope增加字段。保留原故障动作/顺序/结果/生产入口/断言及旧默认诊断行为；不改process-hook协议。
- 新 `tests/phase_b/test_b00c26_fault_sources.py`、`test_b00c26_trace_consumers.py`、`test_b00c26_owned_activation.py`；`tests/phase_b/test_b04_runtime_cases.py`仅可增加显式来源探针选择，不替换C25原诊断路径，不登记正式owned。
- `tests/phase_b/test_b00c25_process_session_binding.py`：仅`test_native_diagnostics_keep_canonical_registry_and_outer_hooks`的临时未绑定假设及必要局部fixture引用；原测试其余断言、29项覆盖及tampering/失败传播必须保持，新增断言不能将预期拒绝改成无检查。
- `tests/phase_b/fixtures/b00c26/`、`tests/phase_b/expected_traces/b00c26/`。
- `tests/phase_b/acceptance_matrix.json`：仅追加B00 owner、final、原A07-META-006/A07-META-015场景；不得添加B04 implementation slice或正式case bindings。
- 本票YAML；独立 `docs/tickets/completions/B00C26_COMPLETION.md`、`docs/tickets/corrections/B00C26_B04_FAULT_SOURCE_CONTRACT.md`。
- `docs/{README,REPO_CURRENT_STATE,STATE_SCHEMA,ARTIFACT_CONTRACTS,VERIFICATION_GUIDE,DECISION_LOG}.md`、Phase B Overview、completion/corrections索引；B04 completion/maintenance仅追加、B04 YAML仅独立入口通过后的lifecycle。

## Do Not Touch

- 全部`src/`、Phase A、generated protocol/catalog、registry/obligations/seals、独立case IDs/分类、原owners、B04 frozen正文。
- 原pytest/matrix/runtime/exit validator、Session/binding规则和production hook协议；resolver仅限上述明确列出的新版本来源接缝。
- 旧0.1–0.11语义、旧expected/fixtures及sealed evidence，旧completion/correction历史、legacy tests、依赖、configs/evaluation、repository outputs、accepted artifacts、Human原始记录和secrets。

## Requirements

1. **原生捕获。** 原child在真实cut保留原process source；父进程按原协议消费receipt并确认child已退出后，在原fault action之前捕获S0完整durable来源。不得把进程退出时已回滚的未提交内存状态当作S0。声明绑定原Session/token/input digests、case/nodeid、原process request/nonce/receipt、child/collector PID、真实boundary/side及唯一producer/epoch/revision。按下方“原生捕获证明链”实施；receipt只证明hook触发，不单独证明快照内容或恢复结果。
2. **闭合声明。** proof0.9继承0.8，仅新增`fault_sources`。每项固定包含`schema_version`、`case_id`、`failpoint_id`、`side`、`outcome`、`process_request`、`process_receipt`、`original_source`、`before_snapshot`、`fault_observation`、`after_snapshot`、`recovery_observation`。其中before_snapshot固定为S0，after_snapshot固定为S1；S2/S3位于recovery_observation，不得复用after_snapshot混指。原生anchor、阶段、差异及必需/nullable规则以下方约定为准；独立来源合同逐字段闭合并由专用tests验证，不能在实施时改变这些信任或阶段边界。所有原schema/hash/identity不重写。
3. **快照与实际故障。** S0/S1/S2/S3各含完整manifest及SQLite完整main/WAL/SHM持久单元，详见下方阶段表。仅S0→S1按原case的精确fault target检查；S1→S2按原owner的恢复合同检查，S2→S3按原重复调用合同检查。缺失文件/行保留具名absent与前像；不能把合法恢复写入算成注入，也不能借恢复放行额外破坏。
4. **来源边界。** 新resolver只能读取当前原生Session的已验证快照，区分原逻辑Run路径和快照物理位置；不得重写`canonical_output_root`、原wire/path/owner，也不得临时复原live文件、monkeypatch生产/文件API、以expected-mode绕过raw验证、关闭旧验证或把任意历史根接入。读取顺序固定为：从外部expected binding确定原生anchor、验证阶段记录与完整引用闭包、核验S3及原live durable来源、最后解析指定阶段。不得从candidate proof自选anchor或使用其hash建立信任；S0仅证明历史前态，S1/S2/S3不能借S0取得当前authority。
5. **保留失败语义。** live缺失capability或损坏member在旧版本仍严格拒绝。新版本仅证明该原case发生的故障和原owner恢复/拒绝结果；不把故障前capability解释为故障后有效authority，不把failed/recovery_required变为committed，不新造settlement/terminal/Code registration/Agent返回。停止与最大记账、token/cost unknown保持原义。
6. **完整接线诊断。** 逐项检查原144case的before、fault、recovery、重复读取来源；包括invocation publication、grant/transition、invalid-response、Code bundle handoff、owner race。每case保留真实hook、原nodeid与source-bound主trace，在两个fresh根exact一致。使用仅测试局部的registry/scenario验证可消费性，正式registry/owners保持；不能用phase-only摘要或成功case代替失败case。
7. **C25 lifecycle。** 使用原validator，无修改地分别验证未绑定candidate拒绝、合法绑定candidate对诊断返回空owned集合；仍要求诊断无case_result、原outer hook隔离及29项原负向/失败传播通过。增加正式B04结果必须具有passing node、匹配case/outcome/invariants和真实source proof的拒绝测试。actual registry bytes前后相同；修复测试假设不能扩大validator接受规则。
8. **拒绝与敏感性。** 缺失/伪造任一阶段、source/SQLite/member篡改、foreign producer/Run/Attempt/workspace、stale epoch/revision/Session、错误case/node/process receipt、重复声明/settlement、重排故障顺序、越范围破坏、伪造成功恢复均拒绝。必须覆盖“替换快照并重算candidate全部hash/链”仍与原生anchor不符、“只持有合法hook receipt无捕获记录”、“把S0复制为S2”、“漏记恢复写入”和“重复调用新增业务写入”；不能仅测单字段hash不匹配。合法材料或实际故障/恢复差异必须改变normalized；重读不能执行effect。
9. **四消费者与回归。** 同一新trace经collector、matrix、runtime、exit digest逐项验证，正负材料均覆盖；meta为B00。旧0.1–0.11/default正负回归保持，尤其两类原反例继续严格拒绝。运行完整当前exact collection/full（包含原4578项及本票新增）、legacy325、同一最终输入Session独立B02 1410/B03 645、fresh CLI construction15/11/30/28、final具体47/144/15。保留失败，不retag旧Session。
10. **独立交接。** 保持131required/84mapped/47remaining、2199cases/324boundaries/28post-claim、18B04boundaries/144、15exit及原owners。本票通过后独立审查B04接线是否仍触发前置meta/来源边界；仅已知Stop消除且当前输入满足入口才恢复B04ready，未来整票完成不能预先保证。

### 原生捕获证明链

- 原`process_hook_request`、production hook receipt、`consume_process_hook`与pytest envelope保持原格式和校验。新helper仅在原native node的ACTIVE binding下工作，拒绝unit-only、其他node和未消费/不匹配的receipt；原child PID与parent实际Process对象、原process source必须一致。真实cut由原factory的生产hook映射和原source共同确认，不接受自由填写boundary/producer。
- trusted producer是当前固定输入中由原pytest launcher实际启动的项目捕获helper。它从实际文件和DB读取S0，并在故障注入前以旧0.11验证原raw、owner及引用闭包；原case中无unconsumed Code来源时，只允许其已证明为空的声明。capture记录使用exclusive-create、fsync及按阶段前序摘要串联；闭合字段为`schema_version`、`binding`、`case_id`、`nodeid`、`stage`、`previous_stage_sha256`、`collector_pid`、`child_pid`、`process_request_sha256`、`process_receipt_sha256`、`process_source_sha256`、`producer`、`snapshot`、`observation`。stage严格为S0/S1/S2/S3，S0前序为null，其余必须为实际前一阶段记录bytes摘要；snapshot/observation不能反向引用当前record或最终anchor摘要，以免形成循环hash；PID为正整数，identity为非空字符串，binding为原闭合对象；producer保存原typed owner/epoch/revision前像，snapshot绑定该阶段完整manifest，observation只接受该阶段的原实际操作/结果。
- anchor目录由外部expected `invocation_token`确定为fresh `/private/tmp/lqcd-agent-b00c26-capture-<token>/`，case目录由原完整case ID的SHA-256确定；记录固定为S0/S1/S2/S3及最终`anchor.json`。token必须为原native Session token，不得使用unit-only；路径必须canonical、无symlink，禁止proof指定替代目录或fallback到其他Session。缺失anchor只拒绝，不由resolver创建或补写。该目录属于本票证据，必须和原native request/output、receipt、Run roots共同保留。
- `original_source`必须绑定原逻辑Run roots、原before-raw及固定位置anchor；最终anchor由同一捕获helper在S3完成后exclusive-create，闭合字段为`schema_version`、`binding`、`case_id`、`nodeid`、`process_request_sha256`、`process_receipt_sha256`、`process_source_sha256`、`stage_heads`。`stage_heads`恰为四个顺序阶段摘要，不接受缺失、重复、额外或重排；binding复用原闭合集合。所有摘要为原bytes的SHA-256，不以重新序列化值替代原bytes。
- candidate仅携带引用与待验证声明；0.12从上述独立位置读取原生anchor及原捕获bytes作比较，随后复用原source validators。替换candidate中的快照、manifest、raw和自填hash不能改动原anchor。collector在原调用中完成验证，matrix/runtime/exit分别用同一native Session保留的原anchor重读；禁止靠projector进程内缓存、测试临时monkeypatch或expected数据授信。完整full验收保留原launcher返回的passing node、唯一hook及其原envelope，不能以捕获anchor代替pytest或owned验证。
- 信任边界沿用原project-owned Session/文件证据模型：不是抵抗能够同时改写全部可信launcher输出和保存证据的同进程攻击者的新认证沙箱。必须证明candidate不能自选、生成、覆写或重绑定trusted anchor；不能把exclusive-create或可自填hash单独宣传为真实性证明。若需要修改旧hook/Session协议才能完成此链，停止并保留反例。

### 四阶段来源与差异规则

| 阶段 | 捕获时点与字段归属 | 必须验证的关系 |
| --- | --- | --- |
| S0 `before_fault` | 原child退出、父进程按原工厂恢复读取且旧raw验证通过之后，原注入动作之前；`before_snapshot` | 原hook/source、原始owner和完整Run来源一致；不声称包含已回滚的未提交状态。 |
| S1 `after_fault` | 原删除事务提交或损坏写入完成后，首次recover/clock推进之前；`after_snapshot` | S0→S1仅允许该原case指定的文件bytes替换/追加或精确table+primary key删除；前像必须来自S0，禁止任意SQL或任意路径。 |
| S2 `after_recovery` | 原recover返回/抛错之后；owner race须等所有原contender结束；`recovery_observation.after_recovery` | 对照原Invocation/Control owner、真实返回或exception和durable journal，验证实际恢复写入及结果。允许的差异须来自原冻结intent/operation合同，不能只按文件名放行。 |
| S3 `after_repeat` | 原重复recover及工厂已有拒绝重入检查完成后；`recovery_observation.after_repeat` | 原返回/拒绝语义保持，domain bytes与持久业务行不新增effect/settlement/owner变化；检查完整来源，不能只比较Run子目录。 |

- `fault_observation`闭合记录`kind`、`targets`、`before_snapshot_sha256`、`after_snapshot_sha256`、`injector_pid`；kind为`none`、`file_corruption`或`row_delete`。`committed_result_replay`与`materializable_publication_prefix`保留原进程cut，额外注入kind为none、targets为空、S0/S1业务状态相等；其余kind和唯一目标从原factory及case规范派生，不能由outcome标签自行授权。targets绑定精确相对路径或table+primary key、完整before/after bytes/row前像；deleted值明确absent而非空对象/零。
- `recovery_observation`闭合记录`after_recovery`、`after_repeat`、`first_call`、`repeat_calls`、`contenders`。call记录真实入口、原request/owner、返回值或exception二选一、调用前后snapshot manifest摘要；没有返回值时return为null。无race时contenders为空；race保留每个原contender的真实结果/exception及原phase_revision/lease_epoch，不删掉in_progress观察来制造一致。正常返回、原拒绝、无法收尾均不互相替代。
- 每阶段manifest完整覆盖原Run文件、control/checkpoint数据库及旧validators实际读取的workspace/material/auxiliary来源；root集合由原typed owner及原来源校验推导，不能由candidate缩小。捕获输出置于这些来源根之外，避免自包含；原request/receipt/source/raw另存其原bytes并绑定摘要。manifest包含逻辑root ID、相对路径、文件类型/mode、byte SHA/size；SQLite按同一稳定时点的main/WAL/SHM整体捕获并保留有/无状态及业务行前像。捕获不得checkpoint/vacuum、提交或恢复原DB；无并发写入的稳定性必须验证，尤其S2 race结束之后。只读解析在私有副本进行，避免SQLite读取修改原snapshot的SHM；不得把该副本当新生产来源。
- 必须区分SQLite物理变化与业务差异：保留并校验全部物理bytes；跨阶段以完整逻辑行/表结构对照判定业务变化，WAL checkpoint/SHM读取元数据不能冒充fault或业务写入，也不能据此忽略任何业务行。S2→S3须无新增业务写入；若原测试本来要求文件byte-equal，继续保留更严格断言。
- Invocation冲突恢复可能按原frozen started/budget intent补写execution history；须逐bytes匹配原intent且验证无额外后缀。Control recovery可按原operation合同记录failed/recovery_required或完成原publication；必须核对原owner/epoch/revision及实际journal变化。成功重放与materializable prefix按原已提交结果/可物化前缀验证，不能统称“没有变化”。
- S0的有效raw必需；S1/S2/S3如因原故障而不能构成合法Run raw，保存实际不可解析bytes、明确的原validator拒绝及null raw，不能将损坏内容修好或用S0冒充后态。新主trace由已验证S0来源和真实阶段证据共同组成，后态失败/不确定必须显式保留。
- normalized必须保留实际故障目标、语义前后像、恢复结果、合法写入及重复调用结论。仅按旧规则消解已验证的运行identity/物理位置；Session token、PID、anchor物理摘要与SQLite布局作为证明材料保留，不直接作为双fresh语义摘要。不得为获得exact而新增宽泛exclusion；有界race观察的语义投影沿用原可允许的in_progress/terminal约束并保留全部原始证据。

## Deliverables

- 显式0.12/proof0.9来源实现、受限resolver、被动捕获及独立来源合同。
- 原144case双fresh source-bound诊断、四消费者正负、C25生命周期接续和完整回归报告。
- 执行前快照、冻结摘要、最终验证输入与随后文档交付manifest，原始反例及新旧版本对照。
- 独立completion和B04入口报告；没有正式B04owned或Phase B完成声明。

## Acceptance Criteria

- 两个已复现fault case各在两fresh原端口完成，故障前proof、真实故障后状态及原恢复拒绝可由0.12独立验证；旧0.10/0.11保持原拒绝，正向对照继续通过。
- 原生anchor由真实捕获产生，四消费者分别拒绝替换快照并重算candidate所有hash/链、合法receipt搭配伪造前态、缺失/跨Session anchor和阶段错配；无需修改原hook/Session协议。
- 分别覆盖none注入成功重放、合法恢复补写、failed/recovery_required、损坏raw、owner race和重复调用；阶段证据与SQLite完整持久单元可独立重读且无新增effect。
- 原18/144全部case的source-bound主trace双fresh通过；主trace含完整Run来源，原actions/assertions/outcomes和真实hook全部保留，meta不计正式owned。
- C25原测试在未绑定和合法绑定候选下均满足正确语义；无case_result不能冒充owned，原tampering与outer隔离继续拒绝。
- Requirements 8/9的四消费者拒绝、材料敏感性、完整same-input full/legacy/owned/construction/final全部通过。
- 无生产、case、owner、旧版本/expected/Session变化；独立B04入口明确remaining work，不自动completed。

## Verification

```bash
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_b00c26_fault_sources.py tests/phase_b/test_b00c26_trace_consumers.py tests/phase_b/test_b00c26_owned_activation.py tests/phase_b/test_b00c25_process_session_binding.py
pytest --collect-only -q
pytest -q
python -m compileall -q src tests/phase_b
git diff --check
```

正式验收按原C04有界机制保存同Session完整collection、batch/merged envelopes、独立owned1410/645、原CLI四张construction和final具体47/144/15报告。新证据写fresh `/private/tmp/lqcd-agent-b00c26-*`；实际使用原B04工厂时其fresh `/private/tmp/lqcd-agent-b04-*` 根一并保留并绑定。不扩大timeout/exclusion，空间不足时记录实际资源停止，不声称通过。

执行前保存容量preflight：列明当前free、原full及其外部来源根的实测占用、144case双fresh四阶段保留量、私有SQLite验证副本和峰值批次所需空间，并明确安全余量与测量方法。不能仅凭曾有40G或单个full报告目录的大小认定充足。估算不足时先清理已确认无引用且关闭的生成产物或使用已授权空间；不删除sealed/native证据、当前反例及其引用闭包。小批测量也须纳入证据保留预算；执行中逐批监测free，低于已记录的下一批峰值加余量时停止调度，不等写盘失败，不减少验收集合。

创建/修订阶段只核对模板、依赖、链接、scope、冻结正文及diff，不实施新版本或改C25测试；不创建虚假的完成记录，不commit/push。

## Stop Conditions

- 需要production、Phase A、case/owner、预算/authority/恢复策略或原hook/Session协议变化。
- 快照无法证明真实原生来源、只靠自填hash/fixture标签、必须恢复live bytes或伪造root/owner才能重验。
- resolver需要改变旧默认/验证语义、允许范围外的源码或前置测试变化、旧expected语义同步或扩大exclusion。
- 原144case中的实际新生产缺陷或来源类别不在本票闭合方案内，或无法保留原故障动作/断言。
- 无法完成完整当前输入验收，或实际资源不足且无已授权安全替代。

## Required Documentation Updates

- 独立source contract/completion、B04 completion/maintenance关联事实。
- Phase B Overview、Docs/completion/corrections Index、Current State、State Schema、Artifact Contracts、Verification Guide；新来源合同批准实施后追加Decision Log。
- scope/links/frozen-body/stale-documentation/diff审计；旧历史仅追加，B04恢复ready仅在独立入口通过后更新YAML。
