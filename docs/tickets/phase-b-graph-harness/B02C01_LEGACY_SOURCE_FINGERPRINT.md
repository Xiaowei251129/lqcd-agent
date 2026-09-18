---
ticket_id: B02C01
phase: phase-b-graph-harness
status: ready
type: corrective-implementation
depends_on: [B02]
---

# 定义 Legacy Replay 的历史 Fingerprint 缺失证明

## Goal

允许root inputs可完整验证、历史创建格式未记录runtime fingerprint的真实schema `0.2` source，通过B02公共replay入口创建全新schema `0.4` child；lineage如实表达“未记录”，不伪造历史runtime。关闭这一兼容合同缺口后继续原B02，不能把本票完成等同B02完成。

本票仍待用户批准；`depends_on: [B02]`指向被纠偏的冻结合同，不要求B02先完成，也不形成新的B02 YAML循环依赖。批准后方可进入ready，执行前冻结本票快照；不纳入其他WIP、不push。

## Why

旧`initialize_state`生成的schema `0.2` Run-created没有fingerprint。A04与`SourceSnapshotProof/replay_root`要求source fingerprint，但没有定义历史缺失表示。当前B02还使用0.4-only reader和Pause fingerprint validator处理source/lineage，不能直接消费真实旧格式。具体复现与其他剩余任务见[B02审查](../corrections/B02_EXECUTABILITY_REVIEW.md)。

本票只补充既有`runtime_fingerprint`字段内部的closed值合同，不修改`SourceSnapshotProof`外层tag/required fields、Control Protocol graph、catalog IDs或ownership。它是显式批准的source兼容补充，不能伪称普通maintenance。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`、`docs/tickets/corrections/README.md`。
- `docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`、`docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`。
- A04的Compatibility、Child-run Bootstrap Saga、Replay/Fork Contract；A02C01的migration boundary。
- `CONTROL_PROTOCOL_0_4.json`中的`SourceSnapshotProof`与`budget_policy_selection_contract`；冻结catalog。
- B02冻结正文、B02 completion/maintenance、本次审查报告。
- `src/lqcd_agent/graph/state.py`的旧root references、`initialize_state`、`save_graph_state`。
- `src/lqcd_agent/control/{children,records,execution,interfaces,pause,strict_json}.py`与child/source-bound trace tests。

## Scope

- 明确source fingerprint存在与未记录的closed校验规则，以及source proof/child lineage绑定。
- 完成真实0.2来源的只读验证，接入原child reservation/bootstrap saga与冻结policy classification。
- 增加实际公共入口的兼容、幂等、负向及fresh-process测试，更新当前合同文档。

## Non-goals

- 不支持0.2 fork或原地resume/migration，不放宽0.3/0.4的source资格或Pause fingerprint。
- 不实现0.3历史runtime，不修改旧创建器来回填历史fingerprint，不新增caller-supplied身份或输入补造接口。
- 不实现B02其余external、preparation、interrupt或完整验收工作；这些仍须原B02完成。
- 不修改Phase A冻结文件、generated protocol、B00验收schemas/obligations、B03–B05正文或默认CLI。

## Allowed Files

- 本票：ready后只允许YAML lifecycle metadata。
- `src/lqcd_agent/control/children.py`：source reader、source fingerprint校验、policy分类及child绑定。
- `src/lqcd_agent/control/records.py`：lineage source fingerprint分派与交叉绑定。
- `src/lqcd_agent/control/execution.py`：仅必要的lineage replay绑定校验。
- `src/lqcd_agent/control/interfaces.py`：仅child bootstrap携带已验证source fingerprint；不改变public request或start语义。
- `tests/phase_b/test_child_control.py`及新`tests/phase_b/test_legacy_source_compatibility.py`。
- `tests/phase_b/helpers/process_client.py`：仅legacy child的fresh-process测试入口。
- `tests/phase_b/fixtures/legacy_source_*`：仅synthetic、closed旧格式正负fixtures，不保存真实数据。
- `docs/STATE_SCHEMA.md`、`docs/ARTIFACT_CONTRACTS.md`、`docs/ARCHITECTURE.md`、`docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`：仅同步本票兼容合同与验证事实。
- `docs/README.md`、`docs/REPO_CURRENT_STATE.md`、`docs/DECISION_LOG.md`、Phase B `OVERVIEW.md`。
- `docs/tickets/completions/B02C01_COMPLETION.md`及completion index；corrections index仅追加链接；B02 completion仅追加解除本缺口的事实。

## Do Not Touch

- B02及其他ready/completed ticket正文、既有completion/correction历史、Phase A protocol/catalog、`_generated_protocol.py`。
- `pause.py`的真实fingerprint构造/校验与resume exact-match规则；其他control模块、coordinator/checkpoint schema与authority。
- B00 generator/validator/trace schema、matrix ownership、registry inventory、final obligations和seals。
- 旧`graph/state.py`、默认graph/runner、agents/coder/backend、dependencies/configs、`tests/test_*.py`。
- 任何existing source Run、source policy、checkpoint、accepted artifacts、raw data、repository outputs、远端服务。

## Requirements

### 1. Source fingerprint值合同

保留现有完整fingerprint对象。对于schema `0.3 | 0.4`，source fingerprint必须来自可验证历史记录，components与声明source schema一致；不要求source build等于当前target build，因为Replay创建新Run。Target fingerprint仍为真实当前0.4 fingerprint。

只为验证通过且未记录fingerprint的schema `0.2` **replay**，在既有`SourceSnapshotProof/replay_root.runtime_fingerprint`字段中允许如下唯一缺失值：

```json
{"availability":"not_recorded","reason":"legacy_schema_0_2"}
```

它是“该历史格式没有记录此事实”，不是可运行fingerprint，不含虚构build/schema component。它不得用于Pause、resume、target fingerprint、fork或0.3/0.4 source。不得接受null、空字符串、空对象、任意reason、unknown fields，或把验证失败自动转成这个值。

Source proof中的source schema、source Run identity、validated immutable inputs和缺失值一起进入既有lineage digest；child `source_runtime_fingerprint`必须与该Replay proof字段相等。缺失值必须由trusted reader派生，公共request不能指定缺失、历史fingerprint或source schema。校验source与target使用不同入口，不修改Pause validator来迁就legacy。

真实0.2创建格式若包含未知fingerprint扩展，不能默默忽略后标记not_recorded；按unsupported source拒绝。0.3/0.4中丢失或损坏已要求的历史证据同样拒绝，不得降级。

### 2. 真实旧格式读取与完整性

- 使用strict JSON检测duplicate keys、非有限数、错误类型等；旧JSON允许历史writer产生的空白/键顺序，但不要求源文件重写成0.4 canonical编码。摘要校验先针对真实原bytes，新的proof/child再使用现有canonical serializer。
- Source只能由project-owned locator解析。核验0.2 Run-created身份、canonical root、creation/reference结构；不接受任意checkpoint ID、state patch或caller-selected filesystem root。
- `graph_state.json.user_goal`仅作为被Run-created SHA约束的旧输入载体；核验case/run身份和UTF-8 goal摘要，绝不把整个graph state作为child state恢复。
- Config输入只从历史reference和现有可信Host读取边界取得，核验`exists`及原bytes SHA，使用已有受支持解析方式；若路径、格式、缺失文件或政策不允许读取则在reservation前拒绝。不得因此读取raw numeric data、secrets或任意调用方路径。
- 仅在输入完整验证后构造`root_goal={"goal": <verified user_goal>}`和`input_snapshot=<verified config object>`；冻结其canonical digest并匹配request的`source_root_input_digest`。配置不是有效非空对象、goal缺失或原reference无法验证时拒绝，不用当前配置或请求文本替换。
- 验证无历史fingerprint必须依赖实际受支持0.2 source格式，不以caller声明或缺少coordinator row作证。实际source records若出现versioned policy/lineage或其他冲突证据，不得伪装纯0.2输入。

### 3. Policy、identity与durable行为

- 按冻结classifier生成0.2的`pre_a06` authoritative policy absence proof并选当前`balanced_v1`；不能把“某个文件不见了”单独当absence proof。0.4原有supported/unsupported行为保持不变。
- 使用同一个coordinator reservation、可信bootstrap admission、child lineage和inactive→committed capability路径；仅source字段含缺失值，target仍记录真实fingerprint。
- 同key同request仍重放同一child，变更payload冲突；crash后继续同operation/current epoch；source bytes、source checkpoint、accepted状态与写权限不得复制或修改。
- Fork source proof仍禁止Replay-only fingerprint字段；0.2 fork/resume必须在任何领域mutation前拒绝。

## Deliverables

- source fingerprint缺失表示与绑定的明确合同、只读legacy source adapter及child lineage集成。
- 从未修改production `initialize_state`生成的真实0.2正向回归；不得只用手写0.4形状再改schema tag的fixture。
- 独立B02C01 completion，记录实测、source不变及原B02剩余缺口。

## Acceptance Criteria

1. 真实0.2 source经公共`replay_run`创建唯一0.4 child，8条child bootstrap records包含合法lineage，source fingerprint为上述closed缺失值，target为真实当前fingerprint；child从START开始且admission先于initial allocation。
2. 同key幂等、changed request冲突；至少在source snapshot、lineage、child checkpoint、capability publication边界使用真实fresh process重启，保持同child和同operation合法continuation。
3. 输入摘要错误、普通JSON空白、重复key、缺失goal/config、错误case/run、escaped或不允许的引用、伪造policy absence分别有正确accept/reject；拒绝无child bytes/operation reservation，source bytes均不变。
4. 缺失值的unknown/missing fields、错误reason、null、移植到0.3/0.4/fork/Pause/target、lineage与proof不相等均拒绝。原0.3/0.4完整fingerprint校验不放宽，0.4 child happy path和source build变化的Replay语义不回归。
5. Phase A/generated byte检查、child/legacy focused与完整deterministic suite通过，B00/B01 fresh construction仍15/15、11/11；不得用本票宣称B02的30/30。
6. 只更新既有字段内部source兼容规则；协议/catalog/ownership/final obligations字节保持不变，默认0.2运行行为不变。

## Verification

```bash
B02C01_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b02c01-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_child_control.py tests/phase_b/test_legacy_source_compatibility.py
RUN_LIVE_LLM_TESTS=0 pytest -q
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B00 --evidence-dir "$B02C01_EVIDENCE_DIR/b00" --report "$B02C01_EVIDENCE_DIR/b00-report.json"
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B01 --evidence-dir "$B02C01_EVIDENCE_DIR/b01" --report "$B02C01_EVIDENCE_DIR/b01-report.json"
python -m compileall -q src tests
git diff --check
```

另行核验本票负向矩阵、真实独立process、source前后bytes、冻结摘要、links、metadata、scope与stale docs。所有新Run/evidence放fresh临时目录，不复用历史outputs。整票B02恢复后仍必须完成其30项construction、205个boundary接线及其他原定验收。

## Stop Conditions

- 需要修改Phase A protocol/catalog、outer source union、phase/owner/CAS、Pause/resume规则或B00验收语义。
- 需要扩大Allowed Files、修改旧writer/source bytes、增加dependency或放宽数据/路径政策。
- 不能基于真实旧输入证明identity、root inputs或policy absence，却需要用当前值、test注入allow或伪造source authority才能通过。
- 发现0.3 source资格或authority需要新的设计决定：保留其原合同，另行明确，不把本票0.2缺失规则扩大成0.3兜底。
- 验证失败不能在批准边界内解决，或出现新的公共合同冲突。

## Required Documentation Updates

- State/Artifact合同写明source-only缺失值、lineage绑定和严格Pause/target边界；Architecture/Security记录只读legacy adapter的实际范围。
- Verification Guide记录实际新旧格式正负测试；Current State和B02 completion仅追加已解除的具体缺口及原B02仍未完成项。
- Decision Log记录批准后的设计决定；Docs/Phase B/corrections/completions索引同步。审批前不把草案写成生效政策。
- 完成stale-documentation scan，保留所有冻结正文及历史记录。
