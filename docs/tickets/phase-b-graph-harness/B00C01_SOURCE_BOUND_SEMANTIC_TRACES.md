---
ticket_id: B00C01
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B01]
---

# 为 Fresh Run 增加来源绑定的 Semantic Trace

## Goal

修正B02执行中发现的验收前置缺口：保留真实canonical digest及head引用校验，同时允许不同fresh physical root的等价执行匹配同一固定semantic expected trace。新增显式版本化、test-owned的trace projection，不改变runtime hash、Phase A合同、requirement ownership或完成门槛。修正验收通过后解除B02阻塞，恢复原冻结B02的剩余实现。

用户已在讨论上述两层验证、负向回归及恢复B02顺序后明确“批准修改”；本票把该批准范围具体化。执行前仅提交本票ready快照，不纳入此前B02未提交改动；不push。Ready正文随后冻结，结果写独立记录。

## Why

Execution 0.4 Run-created的canonical bytes包含实际output root与timestamp；它们影响execution chain、bounded state和checkpoint摘要。B00 trace 0.1只删除独立ephemeral envelope，无法处理摘要内部的临时输入。B01固定路径的纯trajectory没有覆盖这个fresh-root集成问题。

B00禁止自行新增排除规则，B02把缺少前置验收能力列为Stop Conditions。本corrective只扩展test evidence的语义投影，不修改真实记录、伪造路径、抹掉head或改变Phase A required语义。

## Read First

- `AGENTS.md`
- `docs/README.md`
- `docs/tickets/README.md`
- `docs/SECURITY_AND_DATA_POLICY.md`
- `docs/VERIFICATION_GUIDE.md`
- `docs/tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md`的Normalized Exact Trajectory Contract
- `docs/tickets/phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md`
- `docs/tickets/phase-b-graph-harness/B02_DURABLE_CONTROL_OPERATIONS.md`
- `docs/tickets/completions/B02_COMPLETION.md`
- `tests/phase_b/harness/{trace,pytest_evidence,failpoints,matrix,driver,session}.py`
- B01 production `records.py`、`execution.py`、`projections.py`、`integrity.py`及对应tests

## Scope

- 新增closed trace `0.2`，区分`raw_with_proof`与`semantic_expected`；旧版`0.1`比较语义完全不变，禁止隐式升级。
- 新增来源感知的canonical JSON digest DAG验证与semantic projection；原始证据和canonical report的ephemeral边界保持明确。
- 将新trace验证接入matrix fixture读取、pytest observation、runtime case和final driver；不能只在单个测试里自报pass。
- 增加fresh-root、time、content/head tamper、stale binding、schema和版本隔离回归，以及真实pytest subprocess evidence测试。
- 以原B00 owner追加construction meta scenarios，不新增slice、catalog ID或B02 passing coverage。

## Non-goals

- 不实现B02 durable control功能，不把本票完成当作B02完成。
- 不修改runtime schema/serializer/hash、control graph、lease、权限或兼容政策。
- 不归一化Run/Attempt/operation身份、policy/material content digest、owner、phase、route、budget或失败类别。
- 不做通用“删除不稳定字段”、正则匹配、first-seen hash alias、模糊fixture或实际输出反写expected。
- 不引入依赖、live provider、network或真实Backend；不访问raw numeric data及历史outputs。

## Allowed Files

- 本票：ready后只改YAML lifecycle。
- `tests/phase_b/harness/trace.py`、新增`tests/phase_b/harness/trace_proof.py`。
- `tests/phase_b/harness/pytest_evidence.py`、`failpoints.py`、`matrix.py`、`driver.py`：仅新trace版本、proof/session绑定及验证接线。
- `tests/phase_b/test_source_bound_traces.py`、`tests/phase_b/helpers/trace_sources.py`及必要`helpers/__init__.py`。
- `tests/phase_b/fixtures/trace_*.json`、`tests/phase_b/expected_traces/trace_*.json`。
- `tests/phase_b/acceptance_matrix.json`：仅原B00 owner新增construction scenarios；原slice、scenario及owned IDs保留。
- `tests/phase_b/test_control_operation_recovery.py`：把旧缺口诊断补充为实际修正回归，不声称durable checkpoint或多进程恢复已实现。
- `docs/tickets/completions/B00C01_COMPLETION.md`及completion index。
- `docs/tickets/corrections/README.md`：追加本corrective链接，不改历史条目。
- `docs/tickets/completions/B02_COMPLETION.md`：只追加解除阻塞事实，不回写历史。
- `docs/tickets/phase-b-graph-harness/B02_DURABLE_CONTROL_OPERATIONS.md`：仅恢复执行所需YAML lifecycle。
- `docs/README.md`、`docs/REPO_CURRENT_STATE.md`、`docs/VERIFICATION_GUIDE.md`、`docs/EVALS_AND_OBSERVABILITY.md`、`docs/DECISION_LOG.md`、Phase B `OVERVIEW.md`。

## Do Not Touch

- Phase A、Control Protocol/catalog及其exact bytes；generated projection；B00/B01及B03–B05冻结正文。
- `src/`及当前B02未提交runtime代码；legacy tests、dependencies、configs、raw data、outputs、accepted artifacts。
- Registry inventory、runtime bindings、final obligations、独立seals和15项exit清单。
- 旧completion/correction记录；B02记录仅保留上述append-only例外。

## Requirements

### 1. Two-layer Proof and Version Boundary

Trace `0.2/raw_with_proof`保存raw events及closed proof，后者绑定当前invocation token与完整worktree/protocol/catalog/matrix/registry/final-obligations/generated digests。父validator必须独立核对绑定，不能接受proof自报的passing或沿用旧token。

Proof的source objects保存typed kind、canonical JSON value、raw SHA-256及显式digest-reference edges。每个raw SHA均由production-compatible canonical bytes重新计算；checkpoint manifest使用其既有body digest规则并验证self-head。Execution records必须通过production replay验证完整前缀、身份、顺序和clock；不能因归一化跳过raw校验。

允许的基础kind为`execution_0_4`、`canonical_json`、`checkpoint_manifest`；后两者不替代各子系统production validator。Canonical JSON节点只提供内容与明确引用的证明，不得宣称它已满足Code/Pause/terminal等domain合同。新domain shape继续由其owner的production tests验证。

Sources构成有向无环图；拒绝duplicate、missing、unknown、orphan、cycle、wrong-kind或字段值不相等的reference。只允许明确的head/state/checkpoint摘要字段作为引用，不将任意material SHA按首次出现顺序替换。

`semantic_expected`是tracked、固定、strict JSON fixture，不包含运行时proof。Actual不得提交此representation冒充已验证结果；旧`0.1`与新`0.2`不能跨版本比较。Semantic digest使用明确的version/domain标记，不冒充真实SHA。

### 2. Narrow Projection

Output roots必须与对应Run-created的case/run/实际canonical root绑定，并验证absolute canonical、fresh temporary-root containment及不含symlink escape。只投影这些root之下的完整物理路径，保留Run identity、root角色和相对路径；不做自由文本替换。根路径关系必须唯一，禁止重叠root造成歧义。

仅对production已校验的Execution `created_at`及Transition `committed_at`去除绝对时间字面值；clock source、顺序/回退拒绝仍保留，budget/expiry/guard的语义结果不得排除。其它JSON字段默认全部保留。测试优先使用trusted FakeClock；随机operation identity在测试Host侧使用确定性分配，不通过trace alias抹掉。

Semantic digest必须从完整source content及已校验的reference DAG计算。使用类型区分的投影编码，避免被排除路径的替代值与真实业务内容发生表示碰撞；同一raw digest不得被多个不一致proof解释。Event的非空heads必须有exact source link，错误关联到另一合法对象仍须被拒绝或与固定fixture不匹配。

### 3. Acceptance Integration and Limits

Writer与父validator两端均校验proof，普通observations和runtime case_results使用同一规则。无ACTIVE writer的unit检查不构成acceptance evidence；真实验收必须通过fresh pytest subprocess和现有session验证。

报告继续使用`PhaseBAcceptanceReport 0.1`。不向canonical report添加raw proof、token或临时路径。真实matrix仍仅B00/B01；B00 construction仍15/15，B01仍11/11，累计26、remaining105、global passed=null；final仍为105 coverage、2286 runtime、15 exit缺口及false完成标志。

## Deliverables

- Versioned source-bound semantic trace实现、固定fixture及正/负向tests。
- 原B00 owner的fresh pytest/meta evidence与不变的全局coverage。
- 独立completion和状态/验证/决策文档；满足恢复门槛后解除B02阻塞。

## Acceptance Criteria

- 两个fresh roots、相同semantic inputs的轨迹exact相等；受允许的绝对时间平移不改变semantic轨迹。
- 原始hash错误、物质内容变化（包括重算合法raw chain后的变化）、错误head引用、跨Run绑定、路径逃逸、clock回退、缺失/重复/循环/未引用source、旧token及错误worktree/contract digests均拒绝。
- Head、owner、phase、identity、route、budget等semantic变化不会被路径/时间归一化隐藏。
- Trace 0.1现有tests和fixtures不改义；0.2不能无proof或跨版本冒充通过。
- 新证据实际经过matrix、writer、parent validator及runtime-case比较路径；construction及final expected-failure数量保持上述不变。
- 完整deterministic suite、Phase A validator、generator check、compileall、scope、links和diff检查通过。

## Verification

```bash
RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b/test_source_bound_traces.py
RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b
RUN_LIVE_LLM_TESTS=0 pytest -q
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
python -m compileall -q src tests scripts
git diff --check
```

另用新的`/private/tmp/lqcd-agent-b00c01-*`目录分别运行B00/B01 construction与final expected-failure，核对所有errors恰好为预期缺口；所有临时fixture、SQLite与证据都在新temporary root，不复用历史outputs。

## Stop Conditions

- 需要改变Phase A required语义、真实hash/identity、public runtime/API、graph或ownership；
- 无法同时证明raw完整性与semantic exactness，或必须删除material事实才能通过；
- 需要扩大Allowed Files、修改seals或重写历史；
- 必要回归无法在本范围内保持合同地解决。

## Required Documentation Updates

记录0.1/0.2区分、proof绑定、排除边界、验证命令及最新实测结果。B02历史停止事实保留，追加解除阻塞说明；只在本票全部验收通过后恢复B02，不把7项既有基础/诊断测试算作30项完成。
