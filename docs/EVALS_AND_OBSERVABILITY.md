# Evals and Observability

## 当前定位

评估体系必须分别回答“控制流程是否正确”和“Agent 是否足够聪明”。deterministic harness 负责验证 graph contract；provider/RAG benchmark 负责比较能力、成本与稳定性。两类证据不能互相替代。

当前所有自动评估仍是 synthetic-only，不读取 real raw numeric data。实际运行 artifacts 属于 `<output_root>/<case_id>/<run_id>/`，不是 curated baseline。

## `v0.2-demo` 验证基线

第一阶段封版时已经验证：

- full deterministic suite：`162 passed`；
- Phase 8 good/ambiguous/bad synthetic evaluation；
- Phase 9 `l64c64a076_m140` Golden Demo；
- Phase 10C 9-case full mock-provider benchmark；
- 5-case live-provider advisor demo；
- provider safety floor、Human Gate 与 accepted-memory protection。

完整封版证据与复现命令见 [V0_2_DEMO_BASELINE.md](milestones/V0_2_DEMO_BASELINE.md)。

## 当前评估集合

### Phase 8 synthetic cases

`evaluation/run_evaluation.py` 验证三类基础行为：

- good：low risk，直接进入 Memory and Report，memory accepted；
- ambiguous：medium risk，生成 report，memory pending；
- bad：high risk，进入 Human Approval Gate，未批准时 memory pending。

### Phase 10C advisor-demo benchmark

`evaluation/synthetic_benchmarks/` 将 agent-visible input 与 instructor-only expected sidecar 分离。

- demo set：clean fit、noisy valid fit、fit-window contamination、normalization violation、targeted rerun；
- full set 额外包含 plateau instability、invalid uncertainty、missing input 与 controlled code-fix branch；
- mock-provider mode 是普通开发和 CI-style regression；
- live-provider mode 只用于显式 opt-in rehearsal。

mock full benchmark：

```bash
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py \
  --provider mock \
  --case-set full \
  --output-dir /private/tmp/lqcd-agent-phase10c-mock
```

live demo 不是普通验收要求：

```bash
RUN_LIVE_LLM_TESTS=1 python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py \
  --provider-config configs/runtime/openai.yaml \
  --case-set demo \
  --output-dir /private/tmp/lqcd-agent-phase10c-live
```

hidden expected behavior 不得进入 Agent input、provider prompt 或 final-report evidence。

## 当前 Observability Contract

每次 run 应能定位：

- `graph_state.json` 与 checkpoint metadata；
- node/event log 和 `route_decisions`；
- command provenance、manifest、warnings 与 errors；
- method、analysis、review、decision、approval、memory 和 final-report paths；
- provider-backed run 的 `llm_calls/<agent>.json`。

`llm_calls/` 记录 agent、timestamp、status、non-secret provider metadata、structured request、response/parse status、artifact path 与 errors。它可能包含 bounded prompt/response content，因此只能保存在 ignored run output 中，不能进入 tracked baseline。

## 当前指标

现有可观测指标包括：

- case status、risk level、recommended action 与 approval required；
- retry count、command success 与 artifact validation；
- warnings by severity；
- context-window status；
- actual-vs-expected route、memory 与 warning checks。

这些指标描述 `v0.2-demo` 当前能力，不等于第二阶段最终 trajectory metric。

## A06 已确认的 Budget/Stop Observability 目标（尚未实现）

A06要求Phase B normalized trace与acceptance matrix能够从权威policy和ledger重建，而不是相信Agent summary或mutable state。每个Run至少可观察：

- policy version/profile/reference/digest，以及每个hard dimension和automatic route的used、remaining与projected-after；
- `BudgetDecision allow | human_gate | halt`、reason、exact proposed action、validated heads、failure fingerprint occurrence和nullable grant；
- resource reservation/settlement identity、maximum/actual vector、timeout、Attempt/Run active-time归属，以及unsettled crash的conservative charge；
- Code Agent唯一aggregate envelope与ExternalOperation/task/workspace/Pause binding，确保dispatch/lookup/fetch期间budget和execution heads零漂移；
- grant issued/consumed、exact Human Response snapshot/actor/scope/target及duplicate或mismatch拒绝；
- Pause opened/deadline/claim边界、terminal reserve余额、typed stop trigger、safe-stop proof、settlement disposition、Pause quarantine与terminal closure outcome。

Token和normalized cost只作audit metric；provider未报告时必须显示`unknown`，不能计作0或影响hard-gate通过率。Stop telemetry必须区分`halted`、已证明且可发布的`failed`、`recovery_required`、`terminal_closure: unavailable`和非terminal`materialization_pending`，不得只报告“任务失败”。这些是A07/Phase B的目标证据字段；当前trace仍只有普通`llm_calls/`和schema `0.2` execution records。

## A07 已确认的 Phase B Acceptance 模型（尚未实现）

A07把评估证据分成required control acceptance、compatibility regression和capability evaluation。只有第一类决定Phase B是否完成：它必须network-free、deterministic、使用production selector/validator/ledger/registry/Pause/budget/CodeAgentSubgraph入口，并对exact normalized semantic trace和typed invariants断言。Legacy、live provider、benchmark score、人工演示或单一happy path必须单独报告，不能填补required coverage。

六层模型覆盖schema/replay/invariants，node/subgraph/backend/trusted boundary，route/guard/Transition，trajectory/Cycle/termination，durable recovery/concurrency/fault injection，以及project interface/CLI smoke。Normalized trace纳入control与domain identity/lifecycle、route/guard、artifact current/invalidation/protection、budget/grant、Pause/Run、ExternalOperation/workspace/backend、fresh Analysis和每步bounded heads；只排除timestamp duration、临时物理路径、process ID及opaque provider/checkpoint字面值，同时仍单独验证其顺序、containment、binding和唯一性。

Phase B matrix必须绑定tracked protocol/catalog exact digests，并以九个owner的131项required IDs为唯一required set。Construction模式只能报告当前implementation ticket已覆盖的owned subset与remaining IDs；B05 final模式必须set-equal并生成zero-gap report。Required nodeid不可skip、xfail、deselect、live-only或uncollectable，route/trajectory/recovery/interface场景必须具有exact expected trace。Process restart必须真正重启Python并重新打开durable store；Pause claim、terminal owner、grant和idempotency竞争必须使用两个独立client/process，fault outcome只能是exact same-operation continuation或冻结的typed fail-closed分类。

当前尚无matrix、Phase B tests或B00–B05 ticket。A07完成只冻结验收权威和拆票顺序，不把design validator的通过计作runtime acceptance。

## 第二阶段 Harness 方向

第二阶段按以下层次扩展，但本轮不提前批准具体 metric 或实现：

1. Phase A 已明确 transition、attempt、invalidation、resume、Code Agent、budget 和 harness acceptance contracts；
2. Phase B 用 deterministic fake nodes 做 transition/trajectory、cycle、checkpoint 与 termination tests；
3. Phase C 验证真实 Code Agent 的 scope、tests、budget 和回环；
4. Phase D 对 physics/RAG 能力做有来源、可比较、支持 abstention 的评估；
5. Phase E 形成 integrated benchmark 与下一 milestone。

具体 Phase B acceptance 已由`completed`的 [A07](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)、tracked [`Control Protocol 0.4`](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json) machine schema 0.4和catalog version 0.4.0共同冻结。B00必须消费其中的transaction domain、resolution CAS、guarded branches、tagged evidence unions、winner-observation组合状态、request-owned normal safe-stop candidate classification、完整trigger-class/context stop route、interrupt disposition、interrupt late-integrity outcome、Cancel branch-to-resolution tuple/phase闭包、START/Replay/Fork/ordinary Transition的commit-gated capability、exact terminal lifecycle、reservation到ExternalOperation tuple及source proof到request Run/lineage的绑定、Replay source-policy classifier、stable fork、variant overlay与phase dominance及其exact digests，而不是从自然语言或实现反向定义验收范围。A06已经冻结具体policy、accounting和stop metrics，但这些仍是目标合同，不能写成当前runtime要求。

## Raw-data-backed Evals 的前置条件

只有同时满足以下条件，才可增加 raw-data/reference-output-backed evaluation：

- raw-data manifest 与 checksum 已定义；
- raw numeric data access 有明确批准；
- reference outputs versioned 或 append-only；
- expected behavior 位于 `raw_data/` 之外；
- reference outputs 与 actual-run `outputs/` 严格分离。

## 相关文档

- [Project Specification](PROJECT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
- [Phase B Overview](tickets/phase-b-graph-harness/OVERVIEW.md)
