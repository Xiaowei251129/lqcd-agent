# Repository Current State

## 状态摘要

- **更新时间**：2026-09-14
- **当前分支**：`codex/phase-11-agent-harness-upgrade`（已快进包含`xgao`的Phase A设计冻结提交`d0f108a`）
- **当前阶段**：Phase A控制合同澄清；A01–A03及A03C01已完成，A02C01与A04–A07已获用户最终确认并冻结为`ready`
- **活动 ticket**：A02C01、A04–A07 `ready`；G01、A01–A03及A03C01 `completed`
- **稳定基线**：[`v0.2-demo`](milestones/V0_2_DEMO_BASELINE.md)
- **本轮范围**：已将`xgao`分支的`f4f0eaa`设计与`d0f108a`冻结提交快进合入当前开发分支；A02C01与A04–A07为`ready`，票据正文、protocol与catalog exact bytes不变，尚未执行这些票据或Phase B runtime。

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

当前已冻结target-contract状态：

- A02C01以仓库支持的`corrective-implementation`类型新增`ControlOperation 0.1`和schema `0.4+` bootstrap纠正合同：`<output_root>/.lqcd/control_operations.sqlite`在任何Run-root bytes前事务性占用幂等key、operation和target Run locator；policy和bootstrap admission先于initial Cycle/Planner Attempt/START Transition，完整heads/checkpoint验证先于Planner副作用；schema `0.2`历史正文和runtime不变；
- A02/A03独立clarification统一复合Transition publication为Human Request（如有）→scheduled target allocation→A03 invalidation→committed Transition append→target start，已完成ticket正文不回写；
- A04新增权威`run_status = initializing | running | paused | completed | failed | halted`；十二种ControlOperation组合包含统一`advance_run`，使START与Human Response resume之外的每个普通Transition在预算、target allocation、A03 invalidation、Transition、head verification和commit-gated capability之间具有durable owner；START/Replay/Fork child bootstrap也在checkpoint后prepare capability并只由same-operation result激活；显式Pause cancel按trigger优先，对ExternalOperation absent/present/resolved均可达，branch与terminal resolution共享同一tuple domain和可达phase；interrupt winner在同一operation内解析recoverable/halted/failed/unavailable并闭合Pause/Run；
- A05把Python Codex SDK保留为C00 capability gate后的条件性候选，Phase B仍只使用Fake；ExternalOperation以单一`coordinator_sqlite`中的normal/cancel/interrupt CAS仲裁，normal safe-stop candidate只存在于contender request，unavailable candidate不写公共状态而转入integrity interrupt；dispatch前interrupt使用与present字段互斥的typed reservation absence，resource snapshot绑定exact ExternalOperation identity/phase/revision/epoch与reservation，合法resolution统一收敛到唯一final evidence；
- A06直接依赖A02C01，并统一bootstrap、admission、grant与invalid-response reserve顺序；预计算exact且无副作用的publication prefix保持`in_progress/materialization_pending`，缺少预授权或副作用结果不确定才终止为`recovery_required`；完整ExternalOperation `safe_stop` proof才允许halted/failed closure，任一停止证明维度缺失时必须Pause quarantine和`terminal_closure: unavailable`；stop route先冻结trigger class，每个class声明完整required External context并恰好选择一个operation，只有显式Pause取消使用cancel intent；
- A07维护catalog version `0.4.0`的tracked `PHASE_B_REQUIREMENT_CATALOG.json`，为九个owner的131项required合同分配stable IDs；A04为21、A07为15。未来matrix必须与catalog required ID集合set-equal并绑定exact catalog SHA-256；failpoints覆盖advance、child capability、terminal total function、source Run/lineage与Replay policy分类、resource-to-ExternalOperation binding、stable fork、phase dominance、resolution interleaving、late integrity、trigger-class route totality与single-owner closure；
- Phase A已冻结的tracked [`CONTROL_PROTOCOL_0_4.json`](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json) machine schema `0.4`冻结九类、十二种ControlOperation组合、ExternalOperation、Pause/Run lifecycle、branch guards、tagged evidence unions、transaction domain/CAS、trigger-class stop route、variant phase dependencies、pre-start DAG和field binding；[`scripts/validate_phase_a_control_protocol.py`](../scripts/validate_phase_a_control_protocol.py)执行strict independent graph seal、dominance、guard/terminal tuple join、union cross-binding、capability producer closure、overlay、owner、interleaving、route totality、catalog与prose闭包检查，不属于runtime或Phase B实现；
- 上述内容是已批准并冻结的target contract，A02C01与A04–A07 ticket状态为`ready`；`CONTROL_PROTOCOL_0_4.json`中的`status: review`作为批准快照内容保持不变。这不表示当前runtime已具有schema `0.4`、durable resume、Code Agent、budget manager或Phase B product graph。

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

2026-09-10顺序覆盖修复：补齐六条线性publication路径的独立安全阶段顺序、可达性与端点约束，关闭此前16种同步graph/dependency逆序仅被freeze拦截的缺口。新增178项直接顺序变异，原101项语义、3项结构及6项JSON/catalog检查保留；协议/catalog字节、版本、摘要及review状态不变。本轮验证全部通过；完整pytest为324 passed、1项既有golden文件缺失失败，排除该环境依赖后324 passed、1 deselected。

2026-09-10验证器精简：结构、语义和freeze分离，104项变异明确为101项语义及3项结构；删除完整线性图副本和自然语言逐字/关键词门禁，保留独立安全规则、图冻结摘要、机读ID与枚举检查，并将28条消费失败路径纳入tracked验证器。协议/catalog字节与digest不变；仅Phase A review验证与文档调整。本轮协议/结构/语义检查及28条失败路径通过，完整pytest为324 passed、1项既有golden文件缺失失败，排除后324 passed、1 deselected。

2026-09-10新增P2修复：无效Human Response重新暂停统一使用`BudgetDecision allow | halt`，具体动作由机器`budget_decision_contract`绑定为`publish_pause | close_run`；删除未声明的独立decision值，补齐跨文档枚举检查与4项负向变异。A02C01与A04–A07仍为`review`，未实现Phase B runtime。本次验证：104项协议负向变异与6项JSON/catalog检查通过；完整pytest为324 passed、1项sibling golden文件缺失失败，排除该环境依赖用例后324 passed、1 deselected。

2026-09-10最终冻结核验结果：P1“normal结果领取后无法注册Code artifact而无合法收尾”已在Phase A修复。原resume operation从7个post-claim/pre-release边界通过guarded failure branch原子取得Run terminal owner、撤销invocation并冻结消费者stop intent；原External normal final不变。消费者/verifier safe-stop且Run authority可append时复用terminal eligibility/lifecycle/checkpoint关闭为failed，否则同owner unavailable tombstone隔离，不伪造Run lifecycle或Code artifact。失败处置保留consumed Pause与已terminal Attempt，claimed Pause只在同claim/Run owner下interrupted，原aggregate settlement不重复计费。Continue verdict与successor phase revision原子提交，failure intent不能改写已提交边。后续P2修复又将无效Human Response重新暂停统一到`BudgetDecision allow | halt`及`publish_pause | close_run`动作绑定。最终Design validator通过9类/12变体、131项requirements、101项语义变异、3项结构变异、178项publication-order变异和6项JSON/catalog负向检查；独立语义probe通过28条failure-entry/stop/authority模型路径。Strict JSON/duplicate keys、41个Markdown文件的391个relative links、临时目录bytecode编译及git diff --check通过。冻结时完整pytest为324 passed、1 failed，唯一失败为缺少sibling golden reference files；排除该用例后324 passed、1 deselected，未增加fallback。A02C01与A04–A07已冻结为`ready`，已完成票据、历史完成记录、runtime和测试均未修改。Protocol SHA-256：`7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`；Catalog SHA-256：`ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726`。

2026-08-22起，`ready` ticket正文冻结；completion和maintenance/corrective历史分别进入`docs/tickets/completions/`与`docs/tickets/corrections/`。A01/A02不追溯改写；A03已把初次completion和六轮pre-governance corrective history从原ticket拆出。A03详细implementation ticket执行前没有独立commit，仓库明确保留这一provenance限制，不声称可以恢复不存在的committed中间版本。

## 下一项工作

用户已最终确认`f4f0eaa`设计，A02C01、A04–A07全部为`ready`。本次冻结提交同时保存五张票据、Control Protocol与requirement catalog；仅票据YAML状态变更，正文和两份JSON保持批准版本的exact bytes。JSON内原有`status: review`作为批准快照的一部分保留，票据执行资格由YAML与本次用户冻结决定确定。

下一步按A02C01 → A04 → A05 → A06 → A07依赖顺序分别执行，建立独立completion records并同步源事实文档，完成后才标记`completed`。Phase A完成后起草B00 Acceptance Foundation，再按依赖起草B01–B05；本次未执行这些工作。

## Blockers

本次设计冻结无已确认阻断项。此前完整pytest的唯一外部检查仍为缺少sibling golden reference files，数据可用后须复跑对应测试；不将其记录为通过。

A02/A03当前只实现identity与artifact control plane；五张ready设计票据不代表schema `0.4` bootstrap、resume、Code Agent、budgets或新的product runtime edges已经实现。

## 入口

- [Docs Index](README.md)
- [下一阶段改进方向](NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md)
- [Phase A Overview](tickets/phase-a-control-contracts/OVERVIEW.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
