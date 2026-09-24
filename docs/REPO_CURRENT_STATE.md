# Repository Current State

## 状态摘要

- **更新时间**：2026-09-24
- **当前分支**：`codex/phase-11-agent-harness-upgrade`（已快进包含`xgao`的Phase A设计冻结提交`d0f108a`）
- **当前阶段**：Phase A、B00/B01/B02、B00C01–B00C06及B02C01已completed；B03 blocked（B00C08 completed，B00C09 review），B04/B05仍draft。
- **活动 ticket**：B03 blocked；活动时间账本表达需要独立合同审定，见[B00C09](tickets/phase-b-graph-harness/B00C09_ACTIVE_TIME_LEDGER_HANDOFF.md)。已完成基础保留，完整 canonical 交付与验收未完成。
- **稳定基线**：[`v0.2-demo`](milestones/V0_2_DEMO_BASELINE.md)
- **本轮范围**：B00C08在13f3b74冻结，92603f6提交治理完成；B03 blocked。资源事务、Task/Manifest、aggregate/core、workspace 基础已定向验证；真实 Pause 的 Run-only setup 计费缺口已复现；normal/timeout canonical 来源、Bundle、fresh Analysis、golden 和整票验收尚未完成。mapped56/remaining75、Phase B未完成。

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
- target route contract 尚未接入 runtime；identity 已由 A02 确认，invalidation 已由 A03 实现，A04已确认resume目标合同，A05已确认Code Agent目标合同，A06已确认budget/fingerprint/stop目标合同。

A02 corrective implementation 已完成实现与整体验收：

- 采用 Run / Cycle / Attempt 三层模型；Run 是完整科研任务，Cycle 是方法合同 epoch，Attempt 是一次持久化 node execution；
- identity contract 规定 initial/replan 创建 Cycle，re-review、analysis rerun 和 code fix 保持 Run/Cycle 并创建新 Attempt；`parent_run_id` 可表达派生 Run，公开 replay/fork目标合同已由A04确认但runtime仍由Phase B实现；
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

A03没有实现PAUSE/resume、partial-commit recovery、Fake/real Code Agent、budgets、failure fingerprint或A01新产品edges。A04、A05与A06现已完成相应目标合同同步，但实际Pause/Resume、recovery、Code Agent、fresh Analysis、budget ledger/resource enforcement与完整harness仍由Phase B承担。

当前已冻结target-contract状态：

- A02C01以仓库支持的`corrective-implementation`类型新增`ControlOperation 0.1`和schema `0.4+` bootstrap纠正合同：`<output_root>/.lqcd/control_operations.sqlite`在任何Run-root bytes前事务性占用幂等key、operation和target Run locator；policy和bootstrap admission先于initial Cycle/Planner Attempt/START Transition，完整heads/checkpoint验证先于Planner副作用；schema `0.2`历史正文和runtime不变；
- A02/A03独立clarification统一复合Transition publication为Human Request（如有）→scheduled target allocation→A03 invalidation→committed Transition append→target start，已完成ticket正文不回写；
- A04已完成目标合同同步：新增权威`run_status = initializing | running | paused | completed | failed | halted`与append-only lifecycle；三类typed Pause使用prepared/opened两checkpoint publication和single-use claim；十二种ControlOperation组合包含统一`advance_run`，使START与Human Response resume之外的每个普通Transition在预算、target allocation、A03 invalidation、Transition、head verification和commit-gated capability之间具有durable owner；每Run只有一个terminal closure owner，显式cancel和external interrupt复用同一CAS域并在原operation闭合；Replay/Fork通过A02C01 child saga创建隔离identity且不继承Pause、Human authorization或accepted status；
- A05已完成目标合同同步：Parent graph只看见canonical `code_agent` Attempt与稳定`CodeAgentSubgraph`；subgraph通过replaceable `CodingBackend dispatch/lookup/fetch_result/cancel`端口协调图外执行，Phase B只使用同合同Fake，Python Codex SDK保留为C00 capability gate后的条件性候选。每Attempt使用immutable-base isolated workspace、manifest/seal、typed path/tool/network policy与Host-owned containment；external result经过A04 Pause、A06 settlement、ingress validation及fresh trusted verification后才注册schema `0.1` content-addressed code bundle。只有`success + usable`可通过`AnalysisExecutionSpec`进入新worktree/subprocess，其他合法status进入Coordinator，invalid ingress不产生产品Transition，patch promotion与control-repo/Git mutation均未批准。ExternalOperation以单一`coordinator_sqlite`中的normal/cancel/interrupt CAS仲裁，所有合法resolution统一收敛到唯一final evidence，stop proof不足时隔离并返回unavailable；
- A06已完成目标合同同步：Run在正式creation前冻结allowlisted immutable `BudgetPolicy 0.1`，admission在target allocation/invalidation/Transition/side effect之前持久化`BudgetDecision 0.1`；Cycle/Attempt/Transition从权威records计数，resource side effect先reservation且crash按maximum；`FailureFingerprint 0.1`排除execution identity，同一Run第二次exact occurrence禁止automatic fallback；Human `BudgetGrant 0.1`只为exact route/fingerprint/target增加一次机会且不突破global ceilings；每Run保留5 Control/6 Transition收尾额度，Pause deadline过期resume零mutation；完整ExternalOperation `safe_stop` proof才允许halted/failed closure，任一停止证明维度缺失时必须Pause quarantine和`terminal_closure: unavailable`；
- A07已完成目标合同同步：required control acceptance与compatibility/capability evidence分离；Layer 0–5覆盖schema、trusted node/backend、route/guard、exact trajectory、durable recovery/concurrency/fault injection和project interface；`PhaseBAcceptanceMatrix 0.1`已由B00建立，必须绑定protocol/catalog exact digest、把九个owner的131项required IDs与required scenarios set-equal，并拒绝unknown/stale/uncollectable/skip/xfail/deselect/live-only缺口。B00–B05职责与依赖、legacy/parallel边界和Phase B exit gate已冻结；
- Phase A已冻结的tracked [`CONTROL_PROTOCOL_0_4.json`](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json) machine schema `0.4`冻结九类、十二种ControlOperation组合、ExternalOperation、Pause/Run lifecycle、branch guards、tagged evidence unions、transaction domain/CAS、trigger-class stop route、variant phase dependencies、pre-start DAG和field binding；[`scripts/validate_phase_a_control_protocol.py`](../scripts/validate_phase_a_control_protocol.py)执行strict independent graph seal、dominance、guard/terminal tuple join、union cross-binding、capability producer closure、overlay、owner、interleaving、route totality、catalog与prose闭包检查，不属于runtime或Phase B实现；
- 上述内容是已批准并冻结的target contract；A01–A07及A02C01/A03C01均已完成，Phase A退出条件满足。`CONTROL_PROTOCOL_0_4.json`中的`status: review`作为批准快照内容保持不变。B01已实现独立0.4纯基础层，matrix含B00/B01 construction证据；这不表示默认runtime已具有0.4 durable bootstrap/resume、Code Agent、budget manager或Phase B product graph。

第二阶段文档迁移此前已通过 scope check、Markdown link check、ticket metadata、tag、`git diff --check` 与完整 `pytest -q` 验收。

## 当前验证状态

B00/B01/B02 construction分别为 **15/15、11/11、30/30**，累计映射 **56/131、remaining75**。B02的 **205个boundary、1410个独立case** 全部具有同一冻结输入、同一fresh session的通过证据；完整suite **2599 passed**。全局final仍仅报告 **75 coverage / 798 runtime / 15 exit** 缺口，`requirements.passed=null`、`requirements_zero_gap=false`、`phase_b_complete=false`。详见[B02完成记录](tickets/completions/B02_COMPLETION.md)。完整运行之后仅更新文档和lifecycle，代码、测试、fixtures及验收输入不变；最终文档差异审计和fresh construction/final报告单独留存。

### 历史验证记录

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

2026-09-10最终冻结核验结果：P1“normal结果领取后无法注册Code artifact而无合法收尾”已在Phase A修复。原resume operation从7个post-claim/pre-release边界通过guarded failure branch原子取得Run terminal owner、撤销invocation并冻结消费者stop intent；原External normal final不变。消费者/verifier safe-stop且Run authority可append时复用terminal eligibility/lifecycle/checkpoint关闭为failed，否则同owner unavailable tombstone隔离，不伪造Run lifecycle或Code artifact。失败处置保留consumed Pause与已terminal Attempt，claimed Pause只在同claim/Run owner下interrupted，原aggregate settlement不重复计费。Continue verdict与successor phase revision原子提交，failure intent不能改写已提交边。后续P2修复又将无效Human Response重新暂停统一到`BudgetDecision allow | halt`及`publish_pause | close_run`动作绑定。最终Design validator通过9类/12变体、131项requirements、101项语义变异、3项结构变异、178项publication-order变异和6项JSON/catalog负向检查；独立语义probe通过28条failure-entry/stop/authority模型路径。Strict JSON/duplicate keys、41个Markdown文件的391个relative links、临时目录bytecode编译及git diff --check通过。冻结时完整pytest为324 passed、1 failed，唯一失败为缺少sibling golden reference files；排除该用例后324 passed、1 deselected，未增加fallback。A02C01与A04–A07当时冻结为`ready`，已完成票据、历史完成记录、runtime和测试均未修改。Protocol SHA-256：`7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`；Catalog SHA-256：`ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726`。

2026-09-14 A02C01执行只同步冻结的schema `0.4+` bootstrap目标合同、Phase A lifecycle与completion evidence，不修改当前schema `0.2` runtime、graph或tests。Protocol validator通过131项requirements、101项语义变异、3项结构变异、178项publication-order变异与6项JSON/catalog检查；完整pytest为325 passed，41个Markdown文件的400个relative links为0 broken，scope、冻结哈希与`git diff --check`通过。A02C01完成后，A04成为下一张可执行ticket；实际schema `0.4` coordinator、bootstrap runtime与fault-injection fixtures仍由Phase B B00–B02实现。

2026-09-14 A04执行把已冻结的Pause/Resume/Replay/Fork、Run lifecycle、single-use claim、terminal closure ownership、runtime compatibility与child isolation目标合同同步到核心文档，没有修改schema `0.2` runtime、graph、checkpoint backend或tests。Protocol validator通过相同131项requirements、101项语义变异、3项结构变异、178项publication-order变异与6项JSON/catalog检查；43个现行Markdown文件的402个relative links为0 broken，scope、冻结哈希、ticket metadata与`git diff --check`通过。按A04合同不运行runtime、benchmark或live-provider测试；A05成为下一张可执行ticket。

2026-09-14 A05执行把已冻结的Code Agent subgraph/backend boundary、ExternalOperation、isolated workspace、task/result taxonomy、trusted verification、canonical bundle与fresh Analysis handoff目标合同同步到核心文档，没有修改schema `0.2` runtime、legacy handoff、graph、dependencies、provider配置或tests。Protocol、catalog、29项A05 required scenarios、Markdown links、scope、冻结哈希、ticket metadata与`git diff --check`均按A05静态验收；按合同不运行runtime、benchmark或live-provider测试。A06成为下一张可执行ticket。

2026-09-14 A06执行把已冻结的immutable budget policy、admission/reservation、semantic failure fingerprint、single-use Human grant、Pause deadline、terminal reserve与fail-closed stop目标合同同步到核心文档，没有修改schema `0.2` runtime、graph、checkpoint、dependencies、provider配置或tests。Protocol validator通过131项requirements、101项语义变异、3项结构变异、178项publication-order变异与6项JSON/catalog检查；21项A06 required IDs与catalog set-equal，45个现行Markdown文件的413个relative links为0 broken，scope、冻结哈希、ticket metadata与`git diff --check`通过。按合同不运行runtime、benchmark或live-provider测试；A07成为下一张可执行ticket。

2026-09-14 A07执行把已冻结的六层deterministic acceptance、machine-readable matrix/catalog、exact normalized trajectory、process-restart/concurrency/fault injection、B00–B05拆分与Phase B zero-gap exit gate同步到验收和阶段文档，没有创建B00–B05 ticket、matrix、test或runtime。Protocol validator继续确认九个owner的131项requirements、101项语义变异、3项结构变异、178项publication-order变异与6项JSON/catalog检查；15项A07 meta IDs与catalog set-equal，46个现行Markdown文件的418个relative links为0 broken，scope、冻结哈希、ticket metadata与`git diff --check`通过。按合同不运行pytest、benchmark或live-provider测试；Phase A完成，Phase B保持planned。

2026-08-22起，`ready` ticket正文冻结；completion和maintenance/corrective历史分别进入`docs/tickets/completions/`与`docs/tickets/corrections/`。A01/A02不追溯改写；A03已把初次completion和六轮pre-governance corrective history从原ticket拆出。A03详细implementation ticket执行前没有独立commit，仓库明确保留这一provenance限制，不声称可以恢复不存在的committed中间版本。

## 下一项工作

B02范围内没有未关闭的已知阻塞。B03负责Backend和canonical Code Bundle，B04负责产品图与后续预算控制，B05负责全阶段退出验收；各票独立审定后执行。以下记录保留此前的进入条件和交付历史。

用户已最终确认`f4f0eaa`设计。A01–A07及A02C01/A03C01已按各自文档范围执行并标记`completed`；Phase A执行没有改变冻结正文、Control Protocol、requirement catalog或当时的runtime/tests。JSON内原有`status: review`作为批准快照的一部分保留。

B00初次完成时建立closed report、独立final obligations、统一final driver与证据绑定：construction为15/15，全局覆盖15/131、remaining=116、passed=null。真实final按预期失败，runtime/exit gaps独立报告；`requirements_zero_gap=false`、`phase_b_complete=false`。当时验收为80项Phase B tests通过、full suite 405 passed（执行前325 passed），Phase A validator、generator、compileall、links、scope与diff检查通过。当时下一步为依据[Phase B Overview](tickets/phase-b-graph-harness/OVERVIEW.md)逐票审阅B01–B05；后续批准与执行结果见下方日期记录。

2026-09-15 [B00 ownership排序维护](tickets/corrections/B00_MAINTENANCE.md)修复合法B01 slice因两种排序要求冲突而被拒绝的问题；新增15项跨slice正/负向回归，只在隔离副本测试，真实matrix仍仅有B00。最新Phase B suite为95 passed、full suite为420 passed；fresh construction保持15/15，真实final仅报告116 coverage、2286 runtime与15 exit预期缺口。B01草稿同步明确机读与prose-only静态定义来源、trusted clock/只读校验边界及construction-only证明范围；不修改registry/final obligations/seals，不用纯probe替代durable runtime证据。B01仍为`draft`，未执行；本轮没有commit/push或runtime/API/schema变化。

2026-09-16 B01在`537d10c`冻结后执行：新增strict/canonical 0.4 records、纯append/replay、BudgetPolicy/fingerprint/unknown usage、Host/Fake clock、bounded projection和复用A03的只读cross-head adapter；默认0.2 runtime不变。执行前基线420 passed，B00 fresh construction为15/15、final仅116/2286/15缺口；执行后foundation为25 passed，Phase B suite为120 passed，full suite为445 passed，A02/A03 focused为139 passed。B01 construction为11/11，累计映射26、remaining=105、global passed=null；final仅105 coverage、2286 runtime、15 exit缺口，两完成标志均为false。Phase A/generator、compileall、links、scope、冻结bytes与diff检查通过；详情见[B01 Completion](tickets/completions/B01_COMPLETION.md)。上一段2026-09-15结果保留为历史事实。

## 历史阻塞与解除记录

本轮已验证关闭B00C04前置缺口和B02运行缺陷；下列blocked/in_progress状态及旧计数属于各次审查时点。

2026-09-16 B00C02完成：source-bound 46 passed、相关74 passed、Phase B 174 passed、完整suite 499 passed；fresh B00/B01仍15/15和11/11。两次fresh invocation的0.2 trace经真实exit验证生成相同semantic摘要；两类trace的stale token、错误摘要与source tamper均拒绝。B00C01/B00C02已completed，B02恢复ready。Final仍只含105 coverage、2286 runtime、15 exit缺口，两完成标志false；隔离exit回归不冒充项目B05 adapters或Phase B完成。

2026-09-16 B02暂停时，新增6项coordinator基础测试和1项trace缺口诊断；Phase B为127 passed、full suite为452 passed、A02/A03/state regression为139 passed。该7项测试没有增加required coverage；真实matrix仍仅B00/B01，前述B01完成时445 passed保留为历史事实。实施范围与停止证据见[B02执行记录](tickets/completions/B02_COMPLETION.md)。

2026-09-16 B02恢复执行后的本轮局部验证：bootstrap/storage **52 passed**，Phase B **220 passed**，完整suite **545 passed**，A02/A03/state **139 passed**。实际接通startup正常路径、独立checkpoint、invocation启动与独立进程恢复/竞争测试；Pause/child/terminal完整实现和30项验收仍未完成，B02为in_progress而非blocked/completed。Matrix未增加B02 slice，不能把这些unit/integration tests解释为新增required coverage。

B00的generator、strict matrix、fresh pytest evidence、trace codec、registry inventory与final driver已实现。META-006/015 construction只证明静态清单、语义与验证能力，2286条runtime cases仍缺production证据；15项exit adapters待B05接入。B01纯foundation已完成；B02在`83681a7`冻结后执行，此前验收阻塞已解除、现为`in_progress`，B03–B05仍为draft。

2026-09-17 B02继续执行：已修复invocation校验期间过期及bootstrap integrity closure两个缺陷，新增Recovery/Human Pause、普通resume、schema `0.4` child、generic advance/END/close、fenced ordinary artifacts和部分external cancel/interrupt控制分支。当前Phase B回归**453 passed**、禁用live provider的完整pytest **778 passed**、A02/A03/state回归**139 passed**；fresh B00/B01仍为15/15和11/11，final仅有105 coverage、2286 runtime和15 exit缺口，没有解析/证据错误。B02尚无30项construction或56 covered声明。

旧schema兼容的待明确项：现有`0.2` Run创建记录没有历史runtime fingerprint，而A04 replay source proof要求source fingerprint；尚未批准其显式缺失表示，不能用当前build冒充source。已请求确认是否通过corrective ticket明确该表示；暂不实施新变体。其余normal external consumption、recoverable timeout、prepared interrupt、post-claim failure、Analysis preparation/grant和matrix/registry/traces仍属原票未完成工作，不归因于这一单独问题。详见[B02执行记录](tickets/completions/B02_COMPLETION.md)。默认legacy runtime及Phase A bytes未改，B02保持in_progress、未commit/push。

2026-09-18完成[B02可执行性审查](tickets/corrections/B02_EXECUTABILITY_REVIEW.md)，形成待批准的[B02C01草案](tickets/phase-b-graph-harness/B02C01_LEGACY_SOURCE_FINGERPRINT.md)（`review`，未实施）。真实0.2创建器诊断确认输入摘要有效且历史fingerprint缺失，当前公共replay更早因旧JSON编码被0.4 reader拒绝；需同时落实reader与lineage校验。重新运行完整suite为778 passed；fresh B00/B01 construction仍15/15、11/11，B02因无slice返回invalid_input；final仍仅105 coverage、2286 runtime、15 exit缺口。B02归属的205个registry boundaries/1488个runtime cases尚无绑定。本次仅新增审查/草案并同步索引，不修改runtime或冻结正文，不宣称B02完成；证据目录为`/private/tmp/lqcd-agent-b02-audit-yztzribs/`。

B02暂停时的最小复现表明：两个输入、identity与固定clock均相同、仅fresh physical root不同的0.4 foundation snapshots都通过production replay/cross-head校验，但`canonical_output_root`参与Run-created hash，导致execution/checkpoint heads不同；旧trace0.1删除显式`ephemeral.output_root`后，exact trace仍不相等。该历史诊断仍保留；B00C01新增来源绑定的0.2路径，B00C02补齐exit调用并通过完整复验，已解除B02该前置阻塞。不能用空head、通配符、运行时改写expected fixture或复用历史root绕过；诊断测试不进入matrix、不增加required coverage。

A02/A03 identity/artifact authority由B01复用，没有新增平行ledger或artifact index。B01不实现可信bootstrap admission、Pause/ControlOperation、capability activation、实际resource side effect或产品route；这些由原已批准B02和后续仍待独立批准的B03/B04分别实现。当前默认execution schema仍为`0.2`；不能把纯record/replay通过解释为durable/runtime final通过。

## 入口

- [Docs Index](README.md)
- [下一阶段改进方向](NEXT_STAGE_IMPROVEMENT_DIRECTIONS.md)
- [Phase A Overview](tickets/phase-a-control-contracts/OVERVIEW.md)
- [Verification Guide](VERIFICATION_GUIDE.md)

2026-09-18批准后：B02C01已单独冻结于`5e753d6`并进入in_progress；旧格式reader/source fingerprint及lineage绑定已实现、正在完成验证，详见[B02C01记录](tickets/completions/B02C01_COMPLETION.md)。这替代前述“尚未批准”现状，不改写审查历史，不把本次兼容修正当作B02完成。

2026-09-18验证完成：B02C01已completed，真实0.2 source只读Replay及历史fingerprint缺失证明通过78项定向、833项全量测试；B00/B01 fresh construction仍15/15、11/11。原B02继续in_progress，coverage仍26/remaining105，不能将本次兼容修正当作整票完成。

2026-09-18最新状态：B02C01 completed；B02恢复执行后补齐normal external消费、same-owner失败、prepared interrupt、normal-final close、recoverable timeout以及Analysis preparation控制端口。历史0.3 Replay/Fork reader同时验证真实revision/heads且读取完整checkpoint durability unit，来源不变；它依赖trusted原格式reader，不声称已有0.3生产creator。当前阻塞是B00 trace 0.2不能表示合法0.3 Fork到0.4 child的head引用，三类诊断已复现，[B00C03](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)为review、尚未批准实施。B02为blocked，construction slice及205/1488 runtime bindings未完成，covered26/remaining105。默认产品runtime仍0.2；B03/B04未实施。

2026-09-18本轮最终验证：完整pytest **1024 passed**，A02/A03 **139 passed**，Phase B **699项可收集**；fresh B00/B01仍15/15、11/11。Final仅105 coverage、2286 runtime、15 exit缺口。协议/catalog、generated bytes、冻结正文、links/diff/scope检查通过。B02继续blocked等待B00C03审批，三条historical trace拒绝诊断未计入coverage；证据目录`/private/tmp/lqcd-agent-b02-final-review-qxn1sask/`。

2026-09-21：[B00C03](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)已批准并完成。显式trace `0.3`验证原格式historical source、真实Fork reservation及0.4 child引用；旧0.1/0.2语义保持。源checkpoint完整main/WAL/SHM只读副本校验与逐文件不变测试通过。完整pytest **1063 passed**，Phase B **738项可收集**；fresh B00/B01仍15/15、11/11，mapped26/remaining105，final仅105/2286/15缺口。B02恢复原票执行，30项construction和205/1488 runtime bindings仍待完成；见[B00C03完成记录](tickets/completions/B00C03_COMPLETION.md)。这替代上述“B00C03待审批、B02因historical trace阻塞”的当前状态，不改写历史审查事实。

2026-09-21 reservation边界审查：B00C03已completed，其历史证明阻塞已解除；B02随后修复快照丢失卡住和合法grant replan被拒绝，两组回归101/45 passed。真实进程在首次reservation事务COMMIT前退出会完整回滚、没有可恢复的原operation；冻结B00 case笛卡尔展开却要求该边界产生原operation的materialization/domain-gap状态。六项复现及不可变重放对照通过，详见[B02记录](tickets/completions/B02_COMPLETION.md#2026-09-21--reservation-fault-case-executability-audit)。B02现为blocked，待审[B00C04](tickets/phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)，未实施该草案。当前mapped26/remaining105及原2286 runtime/15 exit缺口不变；此前“B02恢复执行”是发现此新缺口前的记录。

2026-09-21本轮验证完成：完整pytest **1086 passed**，Phase B可收集 **761项**；fresh B00/B01 **15/15、11/11**，final仅 **105 coverage / 2286 runtime / 15 exit** 缺口。冻结摘要、生成字节、scope及链接检查通过。B02因[B00C04](tickets/phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)待审仍blocked，详见[B02最终记录](tickets/completions/B02_COMPLETION.md#current-tree-final-verification-2026-09-21)。

## 2026-09-21 B00C04 integrated correction

B00C04已批准并in_progress，case0.2/trace0.4/进程证据实现进入验证。现行独立case2214，其中B02为1416；原2286/1488保留为历史验证事实。B02仍blocked，尚未修复本轮发现的lease失败分类、Pause完整性收尾、external claimed snapshot和Human后续失败，也无B02 slice。

B00C04逐项审查补充：11个仅能到达unavailable的phase不可能产生committed result；其22个case改为严格terminal_tombstone_replay，保留真实recovery_required及原owner unavailable，不改runtime状态。旧→新表为1370 retained/118 replaced，现行2214/B02 1416不变。

2026-09-21 B00C04完成：case0.2、trace0.4、直接production进程回执及严格分批验证落地；旧1488个B02 case为1370 retained/118 replaced，现行B02 **1416**、总数 **2214**，全部324 boundary及B03/B04集合不变。完整pytest **1118 passed**、新增定向 **32 passed**，fresh B00/B01 **15/15、11/11**，coverage26/remaining105。Global passed null、phase_b_complete false。B02验收前置阻塞已解除，接续原票处理已审定的runtime缺陷及完整验收；本修正票不代表B02完成。证据见[B00C04完成记录](tickets/completions/B00C04_COMPLETION.md)。

2026-09-21 C04补充审查：Fork `child.source_revision_cas`在首次reservation提交前，两项独立进程反例均完整回滚。沿用原票已批准的全boundary审查范围补齐这一遗漏；C04重新in_progress，B02暂为blocked。旧1488个B02 case现为1362 retained/126 replaced，现行总数 **2208**、B02 **1410**，减少78均有提交前反例；324 boundary、B03/B04及28 post-claim保持。之前2214/1416及C04完成报告保留为当时验证事实。coverage仍26/105；尚无B02 slice。

## 2026-09-21 — Integrated verification checkpoint

B02与C04现均in_progress：C04独立语义/来源/进程修正已通过定向验证，等待本轮集成全量复验；B02按既有批准修复实际运行缺陷。1112个control phase独立case离线探测及25项修正复验通过，其余298个supplemental case也已全部离线通过（组合原探测及48项复验），这些不替代fresh验收。三个独立进程的normal/cancel/interrupt全部六种顺序通过；Resume准入8项及committed Human后续计划丢失2项通过。新增完整source-bound轨迹terminal/Human/timeout/Fork/Replay分别83/100/81/48/35事件，每条两次fresh roots exact相等，实际来源和旧golden审查保存在本轮证据目录。covered仍26、remaining105，尚无B02 slice或runtime binding，未commit/push。

2026-09-21 C04集成补验完成：完整pytest1158 passed，fresh B00/B01 15/15、11/11；C04现completed，B02继续in_progress。现行独立case2208/B02 1410，covered26/remaining105，尚无B02 slice；此前blocked及补验in_progress为历史过程。详见[B00C04完成记录](tickets/completions/B00C04_COMPLETION.md)。

2026-09-21 B02验收接线：C04已completed后，新增B02完整30项slice、5条完整来源轨迹及1410个独立runtime case绑定。初始reservation的两项C04进程反例作为并列必需final证据保留，没有移除旧正负检查；历史trace回归只隔离其B00/B01前置slice，完整matrix另行验证。现行映射56/131、remaining75；B02仍in_progress，正执行fresh验收，不能将接线或离线通过当作完成。全局final规则未改变，其他票据798个runtime binding及15项exit仍未交付。

2026-09-24 B00C05续执行：用户批准补齐审阅建议并执行，ready冻结于`52c508b`；真实初始producer入口与case0.3修正已实现，70项定向检查通过，完整集成验证尚未完成。工作树独立集合为2199/B03 645，前置B02 1410、B04 144及28 post-claim保持；B03仍blocked，不能把此项修正计为canonical Backend完成。此前2208/654/798计数为case0.2冻结基线。

2026-09-24 B00C05完成：B00C05已完成并解除B03首次ExternalOperation reservation分类阻塞：真实初始producer与case0.3已验证，独立集合2199（B02 1410、B03 645、B04 144），324 boundaries和28 post-claim不变。Fresh B00/B01/B02为15/11/30，完整2617 passed、同Session B02-owned 1410/1410；mapped56/remaining75，final仅75 coverage / 789 runtime binding / 15 exit，global passed=null、Phase B未完成。B03恢复ready，canonical Backend与其28项验收仍待交付。

2026-09-24 B03接续审查：B00C05已completed并提交为`7af288c`；真实B02 Code target/C05 producer及A05/A06 contract-shaped数据反例确认trace0.4存在派生摘要投影缺口，B03现blocked，待审B00C06。反例不计canonical Backend验收；case0.3、2199/645及mapped56/remaining75不变。详见B03执行记录最后条目。

2026-09-24 B00C06：用户批准补强、冻结提交并执行，ready commit `cd29d9f`。显式 trace 0.5 / proof 0.2 及 A05 全链 contract/meta 证据正在集成验证，旧 trace、旧 goldens、src、case0.3 不变。B03 暂保持 blocked；通过后仅解除来源轨迹前置，预算事务和状态投影兼容仍须独立核验。

2026-09-24 B00C06完成：trace0.5/proof0.2 全链来源与四条验收路径通过，2677 passed、同 Session B02 runtime1410/1410，fresh B00/B01/B02为15/11/30；mapped56/remaining75，final仅75/789/15。旧trace、旧goldens、src、case0.3保持。B03来源阻塞已解除，但接续实证确认A05空字段投影超出原fingerprint-only golden授权，因该独立边界继续blocked，待窄范围补充审阅。

2026-09-24：已形成待审 [B00C07 状态投影与 golden 窄范围补充](tickets/phase-b-graph-harness/B00C07_A05_STATE_PROJECTION_GOLDEN_HANDOFF.md)。该票为 review，尚未批准或执行；只提出 B03 的版本隔离、已知 nullable projection 派生同步与兼容核验边界，不预先交付 runtime。原 B03 授权保留，但依其冻结 Stop Conditions 暂保持 blocked，待本补充批准后继续。

2026-09-24：B00C07已按用户同意补强，ready冻结于`7ab58ce`并完成文档交接。B03恢复ready；四个canonical paths来源修复与B02 needs_input fixture窄替换获得明确授权，尚未实现。先推进B03预算事务/失败恢复，再完成canonical实现与28/645验收；当前mapped56/remaining75、Phase B未完成。

2026-09-24 B03接续：B00C07已完成治理交接，但新注册member反例确认其B02 fixture替换与禁止trace0.5的限制冲突，B03再次blocked，待审B00C08。未修改production或golden；15项定向反例/回归通过。当前mapped56/remaining75，预算事务与canonical B03仍未实现。 见[B00C08待审票](tickets/phase-b-graph-harness/B00C08_B02_CANONICAL_EVIDENCE_TRACE_HANDOFF.md)。

2026-09-24：B00C08在13f3b74冻结并完成治理交接；B03恢复ready。Normal/timeout完整来源、source trace0.5、独立Analysis success前置及其golden审计范围已批准，尚待B03实现。预算事务与canonical交付未完成，mapped56/remaining75、Phase B未完成。

2026-09-24：B03因活动时间记账合同缺口blocked，B00C09设计票review。3秒Host setup在真实public Pause和新进程ledger replay中遗漏；不能靠增加Backend active_seconds解决Run-only计费。基础定向70 passed、workspace14 passed；完整canonical与28/645验收未完成，mapped56/remaining75保持。详见[B03最新执行记录](tickets/completions/B03_COMPLETION.md)。

本轮收尾：B02消费/失败收尾回归96 passed，协议/生成字节/冻结正文及181个链接校验通过。基础实现和阻塞记录保存为开发检查点；B03 blocked、B00C09 review，未push，不代表完整suite或B03验收通过。
