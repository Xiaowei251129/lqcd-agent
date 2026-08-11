# `v0.2-demo` 第一阶段封版基线

## 文档状态

- Milestone tag：`v0.2-demo`
- Tag object：`61824d363bc7a1e84b7da33ed436e86a6f0cdd25`
- Peeled commit：`e73e4d3b967008f290259851caf05f28e087cd5b`
- Commit message：`Complete Phase 10D demo milestone`
- 性质：可复现的 demo-ready research MVP，不代表 production readiness

本文冻结第一阶段完成时的项目事实。以后只允许修正事实错误，不随第二阶段持续更新。

## 第一阶段成果

### 基础合同与 LangGraph 骨架

- 建立 source-of-truth 文档、repository skeleton 和真实 LangGraph `StateGraph`；
- 建立 `AnalysisState`、artifact contracts、SQLite checkpoint 和 `MemorySaver` 测试后端；
- 建立五个核心 Agent 与两个支撑节点的基础拓扑；
- routing 使用结构化字段，不依赖自由文本。

### Agent 与运行能力

- Method Planner 可以生成结构化 method plan 和 coder task packet；
- Codex Handoff 可以读取结构化 handoff 结果，并支持显式 opt-in 的本地 Codex CLI worker；
- Analysis Engineer 可以运行 allowlisted mock、local 和 synthetic statistical programs；
- Scientific Reviewer 可以生成 correlator、fit 和 matrix-element diagnostics；
- Decision Coordinator 可以执行 deterministic risk rubric 和 provider safety floor；
- Human Approval Gate 可以生成 approval packet 并读取结构化人工决定；
- Memory and Report 可以生成 accepted、pending、rejected memory 与 final report。

### Provider、审计与 Demo

- deterministic provider 路径保持默认且无网络依赖；
- Method Planner、Scientific Reviewer 和 Decision Coordinator 支持显式 provider-backed structured output；
- OpenAI-compatible 和 DeepSeek 配置使用本地环境变量，不提交 secrets；
- provider request/response 审计记录写入每个 run 的 `llm_calls/`；
- Phase 10D console 支持 YAML/JSON case discovery、provider 选择、live guard、命令预览、run polling、approval actions 和 artifact 查看；
- Golden Demo `l64c64a076_m140` 展示 severe evidence 如何进入 Human Approval Gate 并保持 pending memory。

### Evaluation Harness

- Phase 8 覆盖 good、ambiguous 和 bad synthetic cases；
- Phase 10C advisor-demo benchmark 使用 agent-visible input、instructor-only expected behavior 和真实 synthetic statistical fit；
- full case set 包含 9 个 synthetic scenarios；
- milestone 验证时全量测试为 `162 passed`；
- full 9-case mock benchmark 和 demo smoke 均通过；
- live OpenAI-compatible demo case set 通过预期 risk、route、memory、warning 和 Human Gate 检查。

## 第一阶段持续边界

- `raw_data/` 保持只读，第一阶段不读取真实 raw numeric data；
- actual-run artifacts 写入 `<output_root>/<case_id>/<run_id>/`；
- `outputs/` 是 ignored actual-run root，不是 reference-output 目录；
- secrets 不得提交、打印或写入 artifacts；
- arbitrary shell command 被禁止，analysis command 必须 exact-allowlisted；
- high/critical 结果没有有效人工批准时不能写入 accepted memory；
- provider 不能降低 deterministic severe/high evidence；
- final physics claims、central fit 和 systematic uncertainty 仍由人类决定。

## 已知限制

- 当前图主要证明单轮受控路径，没有正式的 Run/Cycle/Attempt 多轮模型；
- rerun、replan 和部分 code-fix 行为仍可能只记录 route intent，没有形成完整恢复循环；
- ordinary runner 还没有统一的 start/resume/replay/fork 协议；
- Codex 编码智能仍主要由图外 worker 提供，尚不是完整 graph-managed Code Agent；
- code attempts 没有独立 worktree/sandbox identity 和 patch contract；
- state 仍以单套 artifact paths 为主，没有 attempt namespace 和正式 invalidation 规则；
- 当前没有真实 fan-out，因此没有建立完整 parallel reducer、join 和 merge harness；
- 物理知识增强和 RAG 尚未进入正式实现或评估。

## 复现入口

查看冻结源码：

```bash
git checkout v0.2-demo
```

查看 tag 指向：

```bash
git show --stat v0.2-demo
```

运行 Golden Demo：

```bash
bash scripts/run_langgraph_demo.sh
```

运行完整 deterministic tests：

```bash
pytest -q
```

运行 full mock benchmark：

```bash
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py \
  --provider mock \
  --case-set full \
  --output-dir /private/tmp/lqcd-agent-v0.2-full
```

第二阶段当前状态见 [`../REPO_CURRENT_STATE.md`](../REPO_CURRENT_STATE.md)。
