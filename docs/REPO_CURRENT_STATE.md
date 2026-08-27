# Repository Current State

## 状态摘要

- **更新时间**：2026-08-26
- **当前分支**：`codex/phase-11-agent-harness-upgrade`
- **当前阶段**：Phase A控制合同澄清；A01–A03及A03C01已完成，A02C01与A04–A07交叉审查修订稿处于`review`
- **活动 ticket**：A02C01、A04–A07 `review`；G01、A01–A03及A03C01 `completed`
- **稳定基线**：[`v0.2-demo`](milestones/V0_2_DEMO_BASELINE.md)
- **本轮范围**：按2026-08-26批准的交叉审查建议修订控制合同、correction records和requirement catalog；不执行设计ticket或runtime，修订稿已通过静态/回归核验并等待最终冻结确认

## 当前稳定实现

`v0.2-demo` 已经提供一个可独立演示的科研多 Agent MVP：

- real LangGraph `StateGraph` 与 deterministic default path；
- Method Planner、file-based Codex Handoff、Analysis Engineer、Scientific Reviewer、Decision Coordinator、Human Approval Gate、Memory and Report；
- SQLite/Memory checkpoint、structured routing、manifest 与 final report；
- allowlisted synthetic analysis、Golden Demo 与 synthetic benchmark；
- optional OpenAI/DeepSeek provider path、strict structured output、local evidence safety floor 与 run-local `llm_calls/` audit；
- high/critical 风险的 Human Gate 与 accepted-memory protection；
- local web console 与 CLI entry points。

第一阶段的 Phase 0–10D 分组成果、复现方式和已知限制不再在本文件累积，统一固定在 [V0_2_DEMO_BASELINE.md](milestones/V0_2_DEMO_BASELINE.md)。

## 第二阶段控制合同状态

已经建立：

- [Docs Index](README.md) 与文档权威顺序；
- [Ticket Workflow](tickets/README.md) 和 [Ticket Template](tickets/TEMPLATE.md)；
- Phase A–E 目录与 Overview；
- Phase A A01–A07 的 control-contract tickets；
- 独立的 `v0.2-demo` milestone 文档；
- 第一阶段 Legacy 规则迁移与删除记录；
- 核心规则文档的第二阶段定位。

A01 已确认：

- graph-level re-review、rerun、code fix 和 replan 由 Decision Coordinator 统一派发；
- low/medium、诊断唯一且预算可用时允许自动回退；high/critical、诊断歧义、重复失败或预算耗尽进入 Human Gate；
- Coordinator 的四层回退目标是 Reviewer、Analysis、Code 和 Planner；
- Human Gate 统一处理 clarification、approval 和 external action，进出只连接 Coordinator；
- 完整 event log 不直接进入 Agent prompt；Agent 使用 scoped context 和相关 attempt history；
- target route contract 尚未接入 runtime；identity 已由 A02 确认，invalidation 已由 A03 实现，resume、Code Agent 和 budget 由 A04–A06 继续定义。

A02 corrective implementation 已完成实现与整体验收：

- 采用 Run / Cycle / Attempt 三层模型；Run 是完整科研任务，Cycle 是方法合同 epoch，Attempt 是一次持久化 node execution；
- identity contract 规定 initial/replan 创建 Cycle，re-review、analysis rerun 和 code fix 保持 Run/Cycle 并创建新 Attempt；`parent_run_id` 可表达派生 Run，但公开 replay/fork API 仍由 A04 实现；
- 每个新 Run 先写唯一 formal Run record，再创建 initial Cycle、预分配 Planner Attempt 并 commit START Transition；
- 当前 product routes 统一采用 source-wrapper selection/Transition commit：target Attempt 在目标副作用前分配，conditional edge 只读 committed route；
- 工作 Agent、Coordinator、Human Gate 和 Memory Report 共享统一 Attempt envelope；Human Request/Response 使用独立 deterministic identity、validator/consumer/target lineage 和 single-use consumption；
- `attempt_kind` 与 physical node 分离；当前 `codex_handoff` 只能记录为 `legacy_codex_handoff`，不是未来 `code_agent`；
- Run 继续拥有 canonical output root 和稳定 checkpoint thread；Cycle/Attempt 不创建新 thread；
- state 只保留 bounded current pointers/counters；`execution_history.jsonl` append-only 保存 Run/Cycle/Attempt/Transition/Human lifecycle，完整 history 不直接进入 Agent prompt；
- re-review、analysis rerun、code fix 和 replan 已经过最小 deterministic StateGraph identity harness，但仍是 harness-only protocol evidence，不是当前 product routes；其中 `code_agent` 只是 protocol sink；
- legacy incomplete-Run re-entry 只提供 immutable identity validation 和 counter/audit continuity，不是 durable resume。

A03 implementation 已完成：

- graph-managed plan、legacy code handoff、analysis、review、decision、approval和terminal bundles写入`attempts/<attempt_id>/`；
- `artifact_history.jsonl` append-only保存注册、current set/clear和protected events，`artifact_index.json`原子发布七个typed current slots；
- registered history event冻结完整typed pointer并交叉校验producing Attempt ledger identity，registry重放set/clear事件并要求结果与index current exact-equal；pointer identity、status、member、dependency、state path、跨slot或事件顺序篡改均fail closed；
- 普通registration必须紧邻且只允许一次current-set，clear后的artifact不能恢复；dependency按注册时replayed current chain验证，普通canonical member严格绑定producing Attempt及其logical/projection相对路径；
- producing Attempt的Run/Case/Cycle/Attempt/Kind/Node identity必须完整且与execution ledger exact-equal；`managed_projections`必须与replayed current members唯一派生的owner map exact-equal，路径逃逸、protected/control target、重复/额外/缺失entry和未知/错误owner均fail closed；
- Transition commit在target side effect前按target layer清除current，canonical bytes和history保持不变；
- 每个current-clear都与当时current artifact、目标Attempt完整identity、其唯一committed inbound Transition及固定slot policy exact-equal；target/triggering Attempt、Cycle、Transition、Kind、Node或reason篡改均fail closed；
- scheduled Attempt input current IDs与target policy反向派生完整required-clear map，finished Attempt output references反向派生required registration；删除单个clear、整个registration/current-set或producing Attempt started lifecycle均fail closed；initial和legacy incomplete-Run re-entry Planner也经过相同invalidation入口；
- 每个带target Attempt的committed Transition反向要求exact target lifecycle，bounded state中的current Attempt必须与ledger latest status/provenance一致；协调删除target lifecycle、artifact和current pointer不能形成可恢复head；
- state convenience paths指向canonical members并与index同步，run-root fixed paths是registry-owned copy projections；跨slot projection owner collision在复制前失败并保持registry/projection bytes不变，external code/Human ingress只豁免内容digest比较，仍强制验证路径、存在性和ownership；
- Human Response payload保存为immutable versioned snapshot，protected event与唯一submitted ledger的Request/Response identity、canonical path和digest exact-equal；accepted-result protection只接受当时current且status为accepted的terminal，未知kind和非terminal/non-accepted请求在history写入前拒绝；
- 每个submitted Human Response和registered accepted terminal都必须反向对应exactly one protection event；协调删除protection/history head后恢复仍fail closed；
- Human Response ledger sequence与跨事件identity必须稳定，state active response必须与latest lifecycle和snapshot protection exact-equal；snapshot publication只对当前新response保留一次受限preflight例外；
- A03C01进一步要求Cycle、Attempt、Transition、Human Request和Human Response的Run-local deterministic ID/index唯一且从1连续到max；bounded state必须等于各类global latest head，旧Attempt或同一request内旧Response即使自身lifecycle合法也不能成为current；
- committed Transition只有terminal `end`/`__end__` route允许全部target fields显式为null，字段缺失不等同于null；非terminal route必须保留完整target tuple并exact匹配目标Attempt；删除target Attempt/artifact、回滚state并协调清空target仍fail closed；bounded state与Cycle/Attempt ledger中的nullable identity fields也必须显式存在；
- Human Request lifecycle保留既有`created → packet_written? → satisfied?`顺序；Human Response snapshot只允许deterministic next global identity和空outcome fields的一次性write preflight，恢复与读取不接受该例外；
- 已populated artifact state在initialize时先exact validation且不静默修复，只有显式空重建state可以从validated registry同步；artifact history、index和execution ledger中的duplicate JSON key均fail closed；
- current runtime、legacy handoff continuation、Demo Human decision与synthetic benchmark兼容；benchmark历史分析证据只从validated artifact history读取；
- 四层fallback经过真实StateGraph commit/target-consumption invalidation harness，但仍不是A01产品路线。

A03没有实现PAUSE/resume、partial-commit recovery、Fake/real Code Agent、budgets、failure fingerprint或A01新产品edges；这些工作仍分别由A04、A05、A06与A07/Phase B承接。

当前target-contract review状态：

- A02C01新增`ControlOperation 0.1`和schema `0.4+` bootstrap corrective contract：`<output_root>/.lqcd/control_operations.sqlite`在任何Run-root bytes前事务性占用幂等key、operation和target Run locator；policy和bootstrap admission先于initial Cycle/Planner Attempt/START Transition，完整heads/checkpoint验证先于Planner副作用；schema `0.2`历史正文和runtime不变；
- A02/A03独立clarification统一复合Transition publication为Human Request（如有）→scheduled target allocation→A03 invalidation→committed Transition append→target start，已完成ticket正文不回写；
- A04新增权威`run_status = running | paused | completed | failed | halted`，现有领域`status`不再决定resume；所有public mutation复用独立ControlOperation coordinator，operation status/phase、Run status、Pause lifecycle和领域status保持正交；invalid Human Response固定使用decision→old Pause consumed→checkpoint→new Pause opened或halt顺序；
- A05把Python Codex SDK从固定真实backend改为C00 capability gate后的条件性首选，Host-owned producer operation保持产品权威identity；真实backend必须证明完整process-tree取消、bounded grace/force kill、output-reader终止、lease撤销和post-stop无activity，Phase B仍只使用Fake；
- A06直接依赖A02C01，并统一bootstrap、admission、grant与invalid-response reserve顺序；完整policy/operator停止映射`halted`，heads/counters或termination完整性无法证明映射`failed`；
- A07新增tracked `PHASE_B_REQUIREMENT_CATALOG.json`，为A01 routes/forbidden behaviors、A02C01及A04–A06 required bullets分配stable IDs，未来matrix必须与catalog required ID集合set-equal并绑定exact catalog SHA-256；B02明确实现与LangGraph checkpoint分离的SQLite coordinator及双进程/failpoint验收；
- 上述内容仍是`review` target contract，不表示当前runtime已具有schema `0.4`、durable resume、Code Agent、budget manager或Phase B product graph。

第二阶段文档迁移此前已通过 scope check、Markdown link check、ticket metadata、tag、`git diff --check` 与完整 `pytest -q` 验收。

## 当前验证状态

稳定 milestone 的冻结验证结果为：

- milestone 封版：`162 passed`；
- Legacy 清理与第二阶段文档迁移后：`162 passed in 4.30s`；
- 9-case full mock synthetic benchmark passed
- 5-case live-provider demo passed
- Golden Demo smoke passed

本轮按计划没有运行 live-provider 测试；上面的 suite、live-provider 与 benchmark 结果都是 milestone/文档迁移的历史事实，不是 A02 当前 worktree 的完成证据。第二阶段文档迁移当时还额外验证了 29 个现行 Markdown 文件的相对 links、Legacy 删除前的规则/依赖审计、当时的 A01–A07 draft 状态、Phase B–E overview-only 结构，以及 `v0.2-demo` 仍 peel 到 `e73e4d3b967008f290259851caf05f28e087cd5b`。第一阶段原始文档仍可从该 tag 恢复。

A01 是纯设计 ticket。A02 corrective implementation的历史证据为 targeted suite `125 passed`、full suite `218 passed`。A03初次完成证据为focused registry/identity/state suite `44 passed`、full deterministic suite `229 passed`；前五轮corrective证据依次为focused/full `58/243 passed`、`85/270 passed`、`91/277 passed`、`111/297 passed`和`117/303 passed`。第六轮Transition/active-response reverse-anchor corrective pass证据为focused registry/identity/state suite `119 passed`、其余三组focused suites `22/43/61 passed`、full deterministic suite `305 passed`、synthetic benchmark tests `6 passed`和registry suite `86 passed`。

A03C01当前证据为registry suite `106 passed`、focused registry/identity/state suite `139 passed`、full deterministic suite `325 passed`和synthetic benchmark tests `6 passed`；compileall通过。新的`/private/tmp/lqcd-agent-a03c01-final-20260822-smoke` CLI Run验证了history/index/state heads、9个exact projection owners、canonical/projection bytes和accepted-result protection。stale Attempt、same-request stale Response及协调删除target Attempt/artifact并清空nonterminal target的三项独立实验均fail closed。Markdown links、Allowed Files/Do Not Touch、ticket metadata、原A03/legacy-history hash和`git diff --check`在completion record中记录最终结果。A03/A03C01均不要求且未运行live-provider测试。

2026-08-26本轮review文档核验结果：strict JSON和duplicate-ID检查通过；`PHASE_B_REQUIREMENT_CATALOG.json`包含80个required entries，owner计数为A01 26、A02C01 2、A04 14、A05 21、A06 17，正文54个非A01 required ID与catalog exact-equal；307个现行relative Markdown links全部有效；A01–A03及A03C01正文相对基线`bb51901` zero diff；`git diff --check`与compileall通过；现有full deterministic suite `325 passed in 26.49s`。Catalog当前SHA-256为`f66a96f9c488c3f9571e398b8381b2d037bd32f56dc7b3a951717e10fda2ceac`，最终冻结时必须对届时exact bytes重新计算并写入A07 completion record。

2026-08-22起，`ready` ticket正文冻结；completion和maintenance/corrective历史分别进入`docs/tickets/completions/`与`docs/tickets/corrections/`。A01/A02不追溯改写；A03已把初次completion和六轮pre-governance corrective history从原ticket拆出。A03详细implementation ticket执行前没有独立commit，仓库明确保留这一provenance限制，不声称可以恢复不存在的committed中间版本。

## 下一项工作

G01治理和A03C01 execution-head修复已经完成并形成独立本地基线提交，原A02/A03 ticket及pre-governance legacy corrective history保持冻结。[A02C01 Bootstrap](tickets/phase-a-control-contracts/A02C01_EXECUTION_0_4_BOOTSTRAP_ORDER.md)、[A04 Pause/Resume](tickets/phase-a-control-contracts/A04_PAUSE_RESUME_SEMANTICS.md)、[A05 Code Agent](tickets/phase-a-control-contracts/A05_CODE_AGENT_CONTRACT.md)、[A06 Budget/Stop](tickets/phase-a-control-contracts/A06_BUDGETS_AND_STOP_CONDITIONS.md)与[A07 Phase B Acceptance](tickets/phase-a-control-contracts/A07_PHASE_B_HARNESS_ACCEPTANCE.md)已吸收交叉审查和Codex源码对照决定，并通过本轮静态/回归核验，当前均保持`review`。下一步是用户确认最终正文/catalog；确认后按依赖顺序冻结为`ready`，执行前创建包含frozen tickets、corrections、catalog及状态元数据的Git commit。

建议顺序：

1. 用户确认A02C01、A04–A07最终正文和A07 requirement catalog；
2. 按A02C01 → A04 → A05 → A06 → A07依赖顺序提升为`ready`，并在每次执行前保存frozen Git snapshot；
3. 分别执行并建立独立completion record，不把结果回写冻结正文；
4. Phase A完成后再起草B01–B05 implementation tickets；Phase C从C00 backend capability gate开始。

## Blockers

当前无runtime blocker。文档治理上的阻塞是A02C01与A04–A07仍为`review`，在最终确认和frozen commit前不能执行。

治理上的主动限制是：A02/A03只实现identity与artifact control plane，不实现A02C01 schema `0.4` bootstrap、A04 resume API、A05 Code Agent、A06 budgets或A01的新product runtime edges。A02C01与A04–A07当前仅为`review`合同稿；它们在冻结为`ready`前均不可执行。

## 入口

- [Docs Index](README.md)
- [下一阶段改进方向](NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md)
- [Phase A Overview](tickets/phase-a-control-contracts/OVERVIEW.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
