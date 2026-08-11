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

## 第二阶段 Harness 方向

第二阶段按以下层次扩展，但本轮不提前批准具体 metric 或实现：

1. Phase A 明确 transition、attempt、invalidation、resume、Code Agent 和 budget contracts；
2. Phase B 用 deterministic fake nodes 做 transition/trajectory、cycle、checkpoint 与 termination tests；
3. Phase C 验证真实 Code Agent 的 scope、tests、budget 和回环；
4. Phase D 对 physics/RAG 能力做有来源、可比较、支持 abstention 的评估；
5. Phase E 形成 integrated benchmark 与下一 milestone。

具体 Phase B acceptance 先由 draft [A07](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md) 讨论。现在不能把尚未确认的 transition coverage、trajectory score 或 cost threshold 写成正式要求。

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
