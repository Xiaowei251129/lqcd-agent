---
ticket_id: B00C03
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B01, B00C01, B00C02, B02C01]
---

# 验证 Historical 0.3 Fork 的来源绑定轨迹

## Goal

补齐B02已复现的验收前置缺口：合法0.3 historical source经trusted reader验证、Fork为0.4 child后，其真实lineage/source head必须能进入fresh-root exact trace。新增显式test-owned trace版本`0.3`，保留旧trace `0.1/0.2`语义，不改变runtime或Phase A合同。完成后恢复原冻结B02，继续其30项construction和production hook接线；本票本身不声明B02完成。

用户于2026-09-21明确批准本票实施。先单独冻结本票ready快照，保留现有未提交工作；不把其他实现混入ticket-only commit，不push。

## Why

B02允许0.3合格来源Fork为0.4，并要求source bytes不变及exact normalized lineage/head evidence。Runtime正向测试已经成功；当前B00 trace `0.2`只接受`execution_0_4`、`canonical_json`和`checkpoint_manifest` source kinds，所有`execution_head`引用必须指向`execution_0_4`，随后调用0.4 replay。

0.4 child的lineage record包含`SourceSnapshotProof/fork_head.source_latest_heads.execution_head`，它真实引用0.3历史record。三种尝试均失败：把历史record标为0.4触发`source_validation`；按generic JSON提供触发`reference_kind`；省略来源触发`missing_reference`。这些拒绝在现有trace版本中应当保留，不能通过删除head、关闭reference检查、伪造0.4 source或复用固定物理root绕过。

复现入口为`tests/phase_b/test_historical_source_control.py::test_historical_fork_exposes_missing_trace_source_kind`。完整记录见[B02 maintenance](../corrections/B02_MAINTENANCE.md)。B02 Allowed Files禁止修改B00冻结schemas/obligations，B02C01也明确禁止B00 trace schema变化；需要本独立批准。

## Read First

- `AGENTS.md`、`docs/README.md`、`docs/tickets/README.md`；
- `docs/SECURITY_AND_DATA_POLICY.md`、`docs/VERIFICATION_GUIDE.md`；
- A04的Replay/Fork source proof及0.3兼容边界；A07 Normalized Exact Trajectory Contract；
- `B00_ACCEPTANCE_FOUNDATION.md`、`B00C01_SOURCE_BOUND_SEMANTIC_TRACES.md`、`B00C02_SEMANTIC_TRACE_EXIT_BINDING.md`；
- `B02_DURABLE_CONTROL_OPERATIONS.md`、`B02C01_LEGACY_SOURCE_FINGERPRINT.md`及各自completion；
- `tests/phase_b/harness/trace.py`、`trace_proof.py`、`pytest_evidence.py`、`failpoints.py`、`exit_checks.py`、`session.py`；
- `src/lqcd_agent/control/children.py`的只读historical source port，以及`test_historical_source_control.py`的原格式synthetic fixture。

## Scope

- 新增closed trace `0.3`，仍区分`raw_with_proof`与`semantic_expected`，显式分派验证与projection。
- 在该版本中支持有完整来源证明的historical 0.3 execution/checkpoint事实及其到0.4 child lineage的引用；按原schema校验，不调用0.4 replay解释历史record。
- 将新版本接入matrix expected fixture、fresh pytest observation、runtime case及exact-trace exit evidence。
- 使用原B00 meta owner补充construction场景，验证跨schema head、fresh-root projection、负向篡改和session绑定。
- 完成后解除这一验收前置阻塞；B02其余工作按原冻结票继续。

## Non-goals

- 不新增0.3 runtime、creator、migration或原地resume；不实现B03/B04。
- 不改变production source reader、fingerprint、record、artifact、checkpoint或coordinator schema。
- 不放宽0.4 mutation authority，不把历史证据当作当前capability。
- 不修改Phase A protocol/catalog、required IDs、ownership、registry inventory/case集合或exit门槛。
- 不把诊断测试、单次成功Fork或本票完成计为B02 construction 30/30。

## Allowed Files

- 本票：ready后只改YAML lifecycle metadata。
- `tests/phase_b/harness/trace.py`、`trace_proof.py`：仅显式新版本和historical source验证/projection。
- `tests/phase_b/harness/matrix.py`、`pytest_evidence.py`、`failpoints.py`、`exit_checks.py`：仅新trace版本的同等严格接线，不能更改检查清单、outcome或report schema。
- `tests/phase_b/test_source_bound_traces.py`、新增`tests/phase_b/test_historical_source_traces.py`；`tests/phase_b/test_historical_source_control.py`仅复用只读fixture、将已解决的诊断变为明确正负回归。
- `tests/phase_b/helpers/trace_sources.py`、`control_traces.py`及新增`historical_trace_sources.py`：仅test-owned evidence捕获，不授予authority。
- `tests/phase_b/fixtures/historical_trace_*.json`、`expected_traces/historical_trace_*.json`。
- `tests/phase_b/acceptance_matrix.json`：仅原B00 meta owner追加construction scenarios，不新增slice或改变已有scenario语义。
- `docs/VERIFICATION_GUIDE.md`、`EVALS_AND_OBSERVABILITY.md`、`REPO_CURRENT_STATE.md`、`DECISION_LOG.md`、`README.md`、Phase B `OVERVIEW.md`。
- `docs/tickets/completions/B00C03_COMPLETION.md`及completion/correction indexes；B02 completion/maintenance只追加阻塞解除事实；B02原票只更新YAML生命周期。

## Do Not Touch

- Production `src/`、默认graph/CLI、dependencies、raw data、repository outputs、existing Run/source目录、accepted artifacts或外部服务。
- Phase A文件、generated protocol、B00 report/schema/obligation seals、`final_obligations.json`、`failpoint_registry.json`的inventory和case定义、requirement ownership。
- 已冻结ticket正文、已有completion/maintenance历史、B03–B05正文；旧tests不能削弱或删除。
- 旧trace `0.1/0.2`不能隐式升级、接受新historical kinds或改变projection排除范围。

## Requirements

1. 新版本source kind必须closed且schema显式：在既有三种kind之外，只增加`historical_execution_0_3`和`historical_checkpoint_manifest_0_3`。Historical execution、manifest及其引用的原payload/state必须按原0.3语义验证，绑定真实Run/Case、record sequence、raw digest、root inputs、latest heads、checkpoint、source-control-revision proof及所选artifact snapshot。`canonical_json`的历史state/payload只有经上述manifest及同Run证明才能参与历史引用解析，不能成为任意0.3 head入口；不得仅信任传入的`validated=true`或测试自报pass。
2. Historical证据是test-owned只读来源，按固定、可审查的历史格式validator校验。不能由trace携带任意callable、改变serializer或选择新schema；source格式不支持、事实不完整或有冲突时拒绝。Fixture必须保持原0.3格式，不调用0.4 builder后改schema tag。
3. Historical引用只在已证明的同一source Run、0.3 history/checkpoint和0.4 lineage `fork_head`上下文中允许。Child的自身execution chain、checkpoint和capability仍必须0.4。外来Run、错误schema、循环、缺失/重复/orphan source、错误reference kind和跨schema head互换必须拒绝。
4. 原始canonical digest、文件bytes及references先验证，再计算semantic digest DAG。仅投影A07允许的时间与已证明fresh Run root路径；material content、policy/fingerprint、identity、owner、phase、route、budget、failure class和source revision不可删除或alias。两个只差fresh root/允许时间的等价source→child轨迹须匹配同一固定expected trace。
5. Expected trace必须固定并经独立语义审查；不得在test运行中由actual重写expected。负向测试必须证明改变历史root input、record、fingerprint、head、checkpoint、artifact或source identity/revision会失败或产生不同semantic trace。
6. Fresh pytest/session binding、report摘要与final exact-trace exit必须支持新版本；stale token/digest、错误representation、版本混用仍拒绝。旧0.1/0.2正负回归保持原结果。
7. B00/B01 construction分别保持15/15、11/11；累计mapped仍26/131、remaining105，global passed为null，Phase B completion为false。本票不创建B02 passing evidence；解除后才由原B02完成其余验收。

## Deliverables

- Closed trace 0.3实现、固定historical-source validator、原始和semantic证据接线。
- 真实0.3 Fork→0.4 child的两fresh-root正向及篡改/跨schema/错误session负向测试。
- 原B00 owner新增meta scenarios、固定expected traces、fresh construction/negative-final报告。
- 独立completion及核心验证文档更新。

## Acceptance Criteria

- B02复现的三种旧版本拒绝保持可解释；新版本可以完整验证原始0.3 head及0.4 child lineage，不隐藏任何required head。
- 同一场景两fresh roots通过同一expected trace；source目录逐文件bytes不变，包括有未checkpoint WAL的情况。
- 所有Required负向、新旧trace测试和fresh evidence/exit regression通过，无skip/xfail或自报结果。
- 完整pytest、Phase A摘要、generated bytes、links、scope、metadata和diff检查通过；B00/B01实际报告仍15/15与11/11。
- 原B02正文、runtime、protocol/catalog/ownership/independent cases均未改变，B02剩余工作恢复到原票执行。

## Verification

```bash
C03_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b00c03-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
pytest -q tests/phase_b/test_source_bound_traces.py tests/phase_b/test_historical_source_traces.py tests/phase_b/test_historical_source_control.py
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B00 --evidence-dir "$C03_EVIDENCE_DIR/b00" --report "$C03_EVIDENCE_DIR/b00.json"
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B01 --evidence-dir "$C03_EVIDENCE_DIR/b01" --report "$C03_EVIDENCE_DIR/b01.json"
! python scripts/validate_phase_b_acceptance.py --mode final --evidence-dir "$C03_EVIDENCE_DIR/final" --report "$C03_EVIDENCE_DIR/final-negative.json"
pytest -q
python -m compileall -q tests/phase_b
git diff --check
```

Final缺失后续runtime/adapters是预期；collection、解析、source-validation、session或已有exit错误不能被当作预期缺口。使用新的`/private/tmp/lqcd-agent-*`证据，不提前执行未具备的B05全套。

## Stop Conditions

- Historical trace需要改变production runtime、0.3 source eligibility、Phase A合同或原文件bytes；
- 必须删除head、放宽source/digest/session验证或回写expected才可通过；
- 需要修改requirement/case/exit集合、扩大Allowed Files或接触Do Not Touch；
- 原格式历史证据不足以独立验证，且无法在只读test-owned validator范围闭合。

## Required Documentation Updates

记录trace版本、支持范围、来源不变与negative regression；completion说明fresh结果和未交付的B02/B03/B04能力。B02仅在此前置缺口验证闭合后恢复，不因本票完成而改为completed。
