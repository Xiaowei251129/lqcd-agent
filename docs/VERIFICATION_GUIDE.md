# Verification Guide

2026-10-19 当前政策：[C29](tickets/phase-b-graph-harness/B00C29_PYTEST_RUNNER_TIMEOUT_450.md)按用户明确授权将统一`run_pytest`单次子进程上限从300秒改为450秒；`run_pytest_batches`与collect入口继续共用该runner。原selection、双fresh、Session/证据验证及其他child上限保持。C29已完成：真实runner中C21子进程395.88秒通过，原evidence/process-hook37项及拒绝探针1项通过；完整4785项回归仍待完成，B05仍review且未实施。以下日期记录中的300秒是当时政策，不回写旧结果。

2026-10-17 B04完成：当前验收目录`/private/tmp/lqcd-agent-b04-execution-20261017-vnz2rk_k`保存固定输入manifest、全仓exact4749的原C04有界批次/合并envelope和同Session独立B02 1410/B03 645/B04 144报告。全部原validator实际运行；300秒outer/60秒child不放宽，失败批次保留并拆分原限重跑。Unix socket负例在允许本地socket的正常环境运行。144新golden保持C28批准候选字节及原288份双fresh来源；它们只作溯源，正式owned由本轮144真实case结果证明。Construction15/11/30/28/47与final具体15exit分别留报告；验证和后续文档交付manifest分离，不重标Session。 见[完成记录](tickets/completions/B04_COMPLETION.md)。以下日期条目为历史记录。

2026-10-16 当前：**C28 completed；B04独立入口通过，恢复ready；C26/C27 completed保持**。当前固定输入full **4678/4678**（legacy325）、同Session独立B02 **1410**／B03 **645**、fresh construction **15/11/30/28**及final原具体 **47/144/15**通过。仅修订一项旧meta生命周期假设；实际registry/owners不变。原144双fresh按原绑定只读验证source/诊断，不能证明正式144owned；B04仍owned **0/144**，原47construction/144owned待执行。原失败和重试保留，验证与文档交付输入分开存档。见[完成记录](tickets/completions/B00C28_COMPLETION.md)。以下日期条目保留历史，无commit/push。

2026-10-16 当前：**C27 completed；C26 经逐项独立复核 completed；B04 经独立入口复核恢复 ready**。显式 trace 0.12/proof 0.9 的四阶段故障来源、窄 CAS 记账和父恢复 Host fixture 已交付。固定输入完整 **4674/4674**（legacy325、新增96）、原 **18 boundaries/144 cases 各两份 fresh**、同 Session 独立 owned **B02 1410/B03 645**、fresh construction **15/11/30/28** 通过；final 原具体缺口仍为 **47/144/15**。B04 owned **0/144**，仍须原产品集成和正式47/144验收。131/84/47、2199cases/324boundaries/28post-claim、原owners、B05 draft与Phase B false保持。交付文档与实际验收输入分别存档，不重标Session，无commit/push。以下日期条目保留历史。 见[完成记录](tickets/completions/B00C27_COMPLETION.md)与[来源合同](tickets/corrections/B00C27_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_CONTRACT.md)。

2026-10-15 当前：**C27 blocked（完整验收容量不足）；C26/B04保持blocked**。第四轮原生来源验收133通过、1失败后停止；首次C22 prefix必要父目录的校验遗漏已在批准范围内修复，补跑12/12、C25–C27专项125/125通过。当前精确收集4674项（原4578+96新增），尚无修复后全量/同Session owned/全部144双fresh通过声明。可用约5.75GiB，完整重跑预估至少10.75GiB；3285候选临时目录无可安全清理项，全部旧native/sealed/反例保留。B04 owned0/144、原47construction/144owned/15exit、131/84/47及2199cases与owners保持。C27完成后仍须C26独立审计及B04入口；无需因本次局部修复新增纠偏票。下方日期条目保留历史。 见[本轮记录](tickets/completions/B00C27_COMPLETION.md)。

2026-10-14 C27实施接续：**C27 in_progress；C26/B04仍blocked**。显式trace0.12/proof0.9、原生四阶段/原调用来源、窄CAS记账和有界Host fixture已进入专项验证；原9组18份fresh来源及119项专项通过，补充control拒绝分支已复核。原144双fresh、完整当前输入full/独立owned/construction及交接尚待完成，不提前声明整票通过。B04 owned0/144、47construction、131/84/47、2199 cases、18/144与15exit及原owners保持。下方日期记录保留历史。 见[来源补充合同](tickets/corrections/B00C27_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_CONTRACT.md)与[执行记录](tickets/completions/B00C27_COMPLETION.md)。

2026-10-14 C26执行停止：**C26 blocked；[C27合并补充待审](tickets/phase-b-graph-harness/B00C27_B04_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_FIXTURE_HANDOFF.md) review；B04仍blocked；C23/C24/C25 completed保持**。已保留S0–S3捕获/私有来源候选并通过C25原29项回归，但原重复publication使capability revision真实增加，Human父恢复创建的后续Pause identity在双fresh不同；当前冻结“无新增业务写入”和旧identity规则不足以直接交付。新0.12尚未启用，完整144 source-bound/full/owned/construction未完成，不能声明C26已解决B04阻塞。C27拟合并窄CAS记账分类、显式测试Host fixture接续及C26全部剩余验收，尚未批准或实施；B04 owned0/144、47construction、131/84/47及2199/324/28/144/15与原owners保持，无commit/push。见[C26实际记录](tickets/completions/B00C26_COMPLETION.md)。下方日期条目保留历史。

2026-10-14 B04正式接线探针停止：**B04 blocked；C26 review；C23/C24/C25 completed保持**。原故障工厂双fresh诊断通过，但删除capability／损坏canonical member后，故障前Run来源在0.10与显式0.11重验仍严格拒绝；正式B04绑定还会使C25“必须未绑定”的meta断言失败。两类缺口已保存原生反例并合并待审，未改production/harness/registry/expected，未实施0.12。B04仍owned0/144、47construction未完成，131/84/47、2199/324/28/144/15和owners保持。当前没有新full/owned完成声明；下方日期条目保留历史。见[C26待审票](tickets/phase-b-graph-harness/B00C26_B04_FAULT_SOURCE_AND_OWNED_ACTIVATION_HANDOFF.md)。

2026-10-14 C23 接续完成：**C23/C24/C25 completed；B04 经 C23 A6 独立入口复核恢复 ready**。原未消费 normal final、ConsumptionFailure 来源和 child Session 接线阻塞已消除。C23 A1–A6 全部通过；本轮在已批准的共同冻结代码输入上重新执行原验证器与只读来源审计，未重跑全部测试、未重标 Session。B04 仍须完成原 47 construction／144 owned 及剩余产品验收，当前 owned 0/144、131 required/84 mapped/47 remaining，B05 draft、Phase B false。下方原日期记录保留历史。见[C23 独立完成记录](tickets/completions/B00C23_COMPLETION.md)。

2026-10-14 C24 接续完成：**C24/C25 completed；C23 经独立入口复核恢复 ready；B04 保持 blocked**。C24 原10项要求及C23 A1–A5/A4b均已独立核验：共同冻结输入的完整4578（legacy325）、同Session独立owned B02 1410/B03 645、90来源测试、16类双fresh、8个native四消费者188组拒绝、七类停止路由，以及fresh construction15/11/30/28与final具体47/144/15均通过。依据已批准C25 Requirements 12复核原始证据，不重标Session；本轮重新执行原validators和只读来源审计，未重跑effect或修改实现。C23尚须独立A6/B04入口与整票交付；B04owned0/144、131/84/47、2199/324/28/144/15、原owners、B05draft及PhaseBfalse保持。无commit/push。见[独立完成记录](tickets/completions/B00C24_COMPLETION.md)。以下日期条目保留历史。

2026-10-14 当前：**C25 completed；C24 经独立入口复核恢复 ready；C23/B04 保持 blocked**。四类原 spawn 入口使用真实 request 的 Session；144 个原用例各完成两份 fresh native 诊断，原 hook/receipt/raw 全部保留，正式 B04 owned 仍 0/144。共同固定输入完整 **4578/4578**（含 legacy325、新 C25 29）、同 Session 独立 owned **B02 1410/B03 645**、来源90项/16类双 fresh/8个四消费者188组拒绝、停止路由7项、fresh construction **15/11/30/28** 通过；final 精确仍 **47/144/15**。C24/C23 原整票交接及 B04 入口仍须独立完成；Phase B false。验收代码与随后文档/lifecycle交付分别存档，无 commit/push。见[完成与交接记录](tickets/completions/B00C25_COMPLETION.md)。以下日期条目保留历史。

2026-10-13 C23 执行停止：**C23 blocked；B04 blocked；[C24 待审](tickets/phase-b-graph-harness/B00C24_CONSUMPTION_FAILURE_SOURCE_HANDOFF.md) review**。新 0.11 来源及七类 B04 停止路由双 fresh 局部检查 7/7 通过；Resume-first ConsumptionFailure 的 active-time/失败身份来源另有真实阻塞，C23 整票及最终 Session 验收未完成。131/84/47、2199 cases、B04 owned0/144 保持；新版本尚未完成交付，旧合同不变，无 commit/push。见[实际记录](tickets/completions/B00C23_COMPLETION.md)。以下为保留的历史记录。

2026-10-11最新：**C21 completed；B04 ready**。历史Code科学leaf、Task protected Human reference与显式trace0.9/proof0.6原整票验收通过：固定输入full **4191/4191**（PhaseB3866、legacy325）、source/meta **49/49**、同Session独立owned **B02 1410/B03 645**、fresh原CLI construction **15/11/30/28**及final具体 **47/144/15**。独立B04入口审查后依原授权恢复ready，非自动整票完成；generic unsafe recovery及剩余产品集成/47 construction/144 owned仍待B04执行，owned0/144保持。原0.1–0.8/default/wire/预算/authority、131/84/47、2199/324/28/15与owners保持，B05draft、PhaseBfalse。验收输入与随后文档/YAML交付分别保存，不retag旧Session。见[完成与接续记录](tickets/completions/B00C21_COMPLETION.md)。无commit/push；以下日期条目保留历史。

2026-10-08当前资源停止：**C21 blocked；B04 blocked**。C21来源/产品接缝已实施，最终固定输入source/meta **49/49**、fresh construction **15/11/30/28**及final具体 **47/144/15**通过；完整4191仅通过 **475**，当前full/独立owned1410/645尚未完成。磁盘剩余约401MiB，已保存全部原始证据和资源停止记录，等待至少10GiB额外空间或其他可写路径后接续A6。不是整票completed，B04owned0/144、131/84/47、2199/324/28/15及owners、B05draft/PhaseBfalse保持；无commit/push。见[实际记录](tickets/completions/B00C21_COMPLETION.md)。以下日期条目保留历史。

2026-10-08当前：**C21 in_progress；B04 blocked**。显式trace0.9/proof0.6候选闭合历史Code科学leaf及Task Human reference，保留原wire/hash、完整owner和0.1–0.8规则；[来源合同](tickets/corrections/B00C21_PRIOR_CODE_EVIDENCE_SOURCE_CONTRACT.md)、[实际记录](tickets/completions/B00C21_COMPLETION.md)。真实产品重试/Grant/timeout/unsafe及publication专项已有部分通过，当前完整Session、owned与construction尚待验收。B04 generic unsafe recovery及47/144仍归B04；原131/84/47、2199/324/28/15与owners、B05draft/PhaseBfalse保持。以下日期记录保留历史。

2026-10-08最新：**C15/C16/C17/C18/C19/C20 completed；B04 ready**。C20补齐C10当前failure显式0.8入口，保留旧版本拒绝；C18与C15–C17各自原要求已独立复核，共同固定Session完整**4139/4139**、legacy325、同Sessionowned**B02 1410/B03 645**、construction**15/11/30/28**及final具体**47/144/15**通过。见[C20完成记录](tickets/completions/B00C20_COMPLETION.md)、[C18完成记录](tickets/completions/B00C18_COMPLETION.md)和[B04独立入口](tickets/completions/B04_COMPLETION.md)。B04按原授权经独立入口核对恢复ready，尚未completed/owned0-of-144；Code parent/fallback/fresh Analysis/publication及47/144仍待执行，B05draft、PhaseBfalse、131/84/47、2199/15/owners保持。验证输入与随后文档交付manifest分开，无commit/push。下列日期条目保留历史。

2026-10-08当前接续：**C20/C18 in_progress；C15/C16/C17/B04 blocked**。C10显式来源入口修复及原测试/新专项通过，C18依原授权恢复最终验收；[C20记录](tickets/completions/B00C20_COMPLETION.md)。尚未声明完整当前Session通过，旧版本/production/131/84/47/2199/15/owners保持，未commit/push；下列条目保留历史。

2026-10-08当前：用户批准执行[C20](tickets/phase-b-graph-harness/B00C20_C10_CURRENT_FAILURE_SOURCE_VERSION_HANDOFF.md)，ready正文已冻结，现**in_progress**。仅交接C10当前failure显式来源入口，原0.6/0.7规则和production保持；实际结果见[C20记录](tickets/completions/B00C20_COMPLETION.md)。C18/C17/C16/C15/B04仍blocked，C19completed；完整固定Session尚未重验，未commit/push。下列条目保留历史。

2026-10-07当前交接：C15按授权已执行部分Host fingerprint/Grant与0.8来源，部分18项专项通过；canonical Code audit/fresh Analysis来源触发未列profile的冻结Stop，**C15 blocked、C16 review、B04 blocked**。候选来源profile已撤回，整票当前Session/owned/construction尚未完成，B04owned0/144及131/84/47/15exit保持。见[C15实际记录](tickets/completions/B00C15_COMPLETION.md)；以下历史检查点保留。

## 使用原则

验证应与改动风险相匹配。开发过程中使用下面的分层入口；runtime、graph、schema 或测试基础设施改动在合并/交付前仍须通过完整 deterministic suite，并按 ticket 完成额外验收。分层不改变任何冻结 ticket 的必验集合、断言或完成判定；局部通过不能证明整票或 Phase B 通过。

当前golden基线审定使用Python 3.12.7、`/Users/xiang/.local/python_vev/bin/python`、pytest 9.0.3、LangGraph 1.2.10及`langgraph-checkpoint-sqlite` 3.1.1。执行前记录实际`sys.executable`、`sys.version`和安装版本；这里的`python`须解析到该审定解释器。原expected来自1.1.5/3.1.0环境，mixed及成功Code/C21 trace还绑定真实分析命令与解释器配置；依赖或解释器变化不是normalizer可忽略的字段。不同环境不能直接继承通过声明，也不能只更新golden绕过差异；先按[维护记录](tickets/corrections/TEST_INFRASTRUCTURE_MAINTENANCE.md)复核来源、摘要传播和完整回归。此处记录验收环境，不改变`pyproject.toml`的依赖声明或增加另一套测试入口。

当前执行入口是 [Docs Index](README.md) 与 [Tickets](tickets/README.md)。第一阶段原始计划和 prompt 历史只从 milestone tag 查看，不存在当前执行权威。

## 快速检查

所有修改先运行 `git diff --check`。纯文档修改检查链接、metadata、scope；涉及协议/目录时另运行 Phase A validator，不因文字编辑重复执行 runtime。

日常开发的三个入口：

| 层级 | 命令 | 用途 |
| --- | --- | --- |
| 冒烟 | `python -m pytest -q -m smoke` | 四项现有 canonical 检查：bootstrap/capability、workspace fencing、Fake Backend restart、无 Code 的完整产品图；不是全部控制或科学能力验收 |
| 定向回归 | `python -m pytest -q tests/phase_b/test_bootstrap_control.py` | 根据实际修改选择完整相关模块，必要时加上下游模块；不使用自动猜测的变更过滤器 |
| 完整回归 | `RUN_LIVE_LLM_TESTS=0 python -m pytest -q` | 合并/交付前完整收集和执行；默认 pytest 的选择保持全量，包含慢测试与双 fresh 检查 |

需要定位慢项时使用 `--durations=20`。`smoke` 是显式 opt-in marker，不写入默认 `addopts`，不修改 matrix、runtime obligations、exit checks 或 skip/xfail 规则。正式验收继续使用下文原 CLI/Session 及冻结要求；本轮维护不实施 B05。

### 临时测试数据

Phase B 的目录分配统一通过 `harness.temporary.mkdtemp` 登记；原 `/private/tmp` 路径和 prefix 保持不变。每次最外层 pytest 创建自己的 ownership ledger，嵌套 pytest/子进程继承同一清单。只有所有 session-finish hooks 成功、pytest 零退出且没有活动 multiprocessing child 时，才清理本次普通测试登记的目录；删除前逐根核对 device/inode，替换目录或 symlink 保留，不跟随到外部目录。

失败/中断、活动子进程、清理错误及设置了 `PHASE_B_EVIDENCE_REQUEST` 的正式运行保留数据，并打印清单路径。正式运行的绝对 source references 因而仍可在父验证器中使用；不清理旧目录、历史证据或其他运行。`LQCD_PYTEST_TEMP_LEDGER` 是内部子进程交接状态，不是用户配置选项。pytest 外单独调用 helper 时没有 session owner，目录继续由调用者管理。

验收输入校验仅在当前 `validate_matrix`/`validate_inventory` 调用中复用相同源字节的 AST；每次引用仍重新读取源字节并检查路径与 qualified name。没有跨 Session 缓存、证明通过缓存或 worktree digest 豁免。

维护依据和验证结果见[测试基础设施维护记录](tickets/corrections/TEST_INFRASTRUCTURE_MAINTENANCE.md)。

完整回归入口：

```bash
git diff --check
pytest -q
```

只做文档迁移时，还应检查：

- Markdown relative links 全部指向现有文件；
- `git diff --name-status` 没有意外的 `D` 或 `R`；
- 没有修改 `src/`、`tests/`、configs 或 runtime schema；
- milestone tag 仍 peel 到锁定 commit；
- ticket metadata 与目录结构符合治理规则。

## 第二阶段文档完整性

当前 source-of-truth 文件：

```bash
test -f docs/README.md
test -f docs/PROJECT_SPEC.md
test -f docs/ARCHITECTURE.md
test -f docs/AGENT_ROLES_AND_BOUNDARIES.md
test -f docs/STATE_SCHEMA.md
test -f docs/ARTIFACT_CONTRACTS.md
test -f docs/SECURITY_AND_DATA_POLICY.md
test -f docs/EVALS_AND_OBSERVABILITY.md
test -f docs/VERIFICATION_GUIDE.md
test -f docs/REPO_CURRENT_STATE.md
test -f docs/DECISION_LOG.md
test -f docs/milestones/V0_2_DEMO_BASELINE.md
test -f docs/tickets/README.md
test -f docs/tickets/TEMPLATE.md
```

阶段骨架必须包含：

- `phase-a-control-contracts/`：Overview、A01–A07、A02C01、tracked Control Protocol和requirement catalog；
- `phase-b-graph-harness/`：本轮只有 Overview；
- `phase-c-code-agent/`：本轮只有 Overview；
- `phase-d-agent-capabilities/`：本轮只有 Overview；
- `phase-e-integrated-benchmark/`：本轮只有 Overview。

## Deterministic Runtime 验证

完整本地 suite：

```bash
pytest -q
```

常用针对性检查：

```bash
pytest tests/test_graph_smoke.py tests/test_routing.py tests/test_state_schema.py -q
pytest tests/test_analysis_engineer.py tests/test_command_runner.py tests/test_manifest.py -q
pytest tests/test_scientific_reviewer.py tests/test_decision_coordinator.py -q
pytest tests/test_approval_packet.py tests/test_memory.py tests/test_report.py -q
pytest tests/test_llm_config.py tests/test_llm_mock_provider.py -q
```

### Phase A Control Protocol 静态验证

A02C01与A04–A07从`review`提升为`ready`前及各design/corrective ticket执行时必须运行tracked design validator：

```bash
python scripts/validate_phase_a_control_protocol.py
```

该检查strict读取[`CONTROL_PROTOCOL_0_4.json`](tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json) machine schema 0.4和[`PHASE_B_REQUIREMENT_CATALOG.json`](tickets/phase-a-control-contracts/PHASE_B_REQUIREMENT_CATALOG.json) catalog 0.4.0，验证ControlOperation graph终结、multi-successor guard互斥/穷尽、tagged evidence与incoming edge匹配、十二种variant overlay、单一transaction domain、normal/cancel/interrupt CAS交错、winner-observation组合owner状态、request-owned normal safe-stop candidate classification、每个trigger class/context的唯一stop route、cancel branch到resolution tuple/phase闭包、START/Replay/Fork/ordinary Transition的commit-gated capability、exact terminal lifecycle、reservation到ExternalOperation tuple及source proof到request Run/lineage的绑定、Replay source-policy确定性分类、stable paused/terminal fork、Pause aborted/interrupted/quarantined finality、Run lifecycle循环、independent graph seal、variant phase dominance、pre-start DAG、field binding、131个ticket/catalog stable IDs及protocol SHA。本次还补齐normal-result stop的原子Pause/Run handoff、ExternalOperation pre-start与Attempt执行授权分离、不可变authorization下的独立execution lease，以及Cancel unavailable保守结算；本轮补齐recoverable timeout原Attempt失败消费与advance持有的fresh Analysis准备，以及消费后的活动绑定释放、RecoveryDecision目标授权和严格JSON/对象结构校验；最新修复由原resume owner完成post-claim完整性失败的消费者停止、结算与failed/unavailable收尾，不依赖Code artifact；101项semantic、3项structural、178项publication-order mutations及6项JSON/catalog负向检查验证这些边界。它是design-time lint，不表示Phase B runtime、fault fixture或acceptance matrix已经实现；B00仍须把同一合同转为collectable tests和normalized traces。

### A04 Pause/Resume 设计合同验收

A04是文档限定design ticket。执行时运行：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

并静态核对：

- A04在`ready`后只有YAML lifecycle metadata改变，冻结正文与执行前hash一致；A01–A03/A03C01保持`completed`，A05–A07正文、protocol与catalog bytes不变；
- Architecture、State Schema、Artifact Contracts和Security Policy一致区分已确认的A04目标合同与当前schema `0.2` runtime；
- 只有stable exact paused/opened/public-checkpoint closure可以resume，三类typed Pause、single-use claim、terminal owner、cancel/interrupt、compatibility及Replay/Fork isolation均保留；
- A04的21个required IDs继续存在于catalog，A07/Phase B承担fault-injection和runtime acceptance，不把design validator当成实现测试；
- Allowed Files、Do Not Touch、Markdown relative links、ticket metadata和删除/重命名审计通过，且`src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`及accepted artifacts没有A04产生的diff。

A04明确不运行runtime、benchmark或live-provider测试；其完成证明合同同步和静态一致性，不证明Pause/Resume API已可执行。

### A05 Code Agent 设计合同验收

A05是文档限定design ticket。执行时运行：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

并静态核对：

- A05在`ready`后只有YAML lifecycle metadata改变，冻结正文SHA-256保持一致；A01–A04/A02C01/A03C01保持`completed`，A06/A07正文、protocol与catalog exact bytes不变；
- Architecture和Agent Roles一致冻结`CodeAgentSubgraph`控制层与replaceable `CodingBackend`执行层，且current `legacy_codex_handoff`没有被重命名、迁移或当作canonical Code Agent；
- State Schema与Artifact Contracts记录schema `0.1` task/external-result/result、workspace manifest/seal、canonical bundle、bounded projection、trusted verification和`AnalysisExecutionSpec`，同时明确它们尚未进入当前schema `0.2` runtime；
- Security Policy保留Attempt-isolated immutable base、normalized path/tool/network policy、no-secrets/no-control-repo writes、single-operation dispatch、strict containment、fresh verification、Human authorization与no-promotion边界；
- A04 `external_result` Pause、A06 reservation/settlement与ExternalOperation single-winner/final-evidence合同没有出现第二套resume、budget、route或terminal authority；
- Phase B Fake和未来real backend使用同一port/validator/verifier/registry/fresh Analysis path；Python Codex SDK只保留为独立C00全部required capabilities通过后的条件性候选；
- A05的29个required IDs继续存在于catalog，A07/Phase B承担deterministic scenarios与runtime acceptance，不把design validator当成实现测试；
- Allowed Files、Do Not Touch、Markdown relative links、ticket metadata和删除/重命名审计通过，且`src/`、`tests/`、`evaluation/`、`configs/`、`raw_data/`、`outputs/`及accepted artifacts没有A05产生的diff。

A05明确不运行runtime、benchmark或live-provider测试；其完成证明Code Agent目标合同及文档闭合，不证明subgraph、backend、workspace、resume、containment或fresh Analysis runtime已经实现。

### A06 Budget 与 Stop 设计合同验收

A06是文档限定design ticket。执行时运行：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

并静态核对：

- A06在`ready`后只有YAML lifecycle metadata改变，冻结正文SHA-256保持一致；A01–A05/A02C01/A03C01保持`completed`，A07正文、protocol与catalog exact bytes不变；
- Architecture、Agent Roles、State Schema、Artifact Contracts和Security Policy一致记录trusted control plane为唯一budget authority，`BudgetPolicy/Decision/FailureFingerprint/BudgetGrant 0.1`、schema `0.4` budget events与bounded projection尚未进入当前schema `0.2` runtime；
- `balanced_v1`与harness-only `phase_b_test`是唯一profiles；Cycle/Attempt/Transition/automatic route从authoritative records计数，LLM/tool/verification及Code Backend aggregate在side effect前reservation，crash按maximum且不退款/redispatch；
- semantic context fingerprint排除execution identity，自同一Run第二次exact occurrence起禁止automatic fallback；typed Human grant只为exact route/fingerprint/target增加一次机会且不能突破global ceilings或terminal reserve；
- 每个Run保留5 Control Attempts/6 Transitions的terminal tail，invalid response只有保留3 Control/4 Transitions时才可repause；Pause deadline过期resume零mutation，stop proof不完整固定为quarantine及`recovery_required`/`terminal_closure: unavailable`；
- A06的21个required IDs与catalog scenario set一致；A07/Phase B承担fake clock、fault injection、normalized trace和runtime acceptance，不把design validator当成budget manager实现测试；
- Docs Index、Phase Overview、Current State、Decision Log与completion index一致记录A06完成、A07 ready，并明确A06没有修改runtime、graph、checkpoint、tests、configs、providers、data、accepted artifacts或历史Run；
- Allowed Files、Do Not Touch、Markdown relative links、ticket metadata、删除/重命名和stale-documentation审计通过。

A06明确不运行runtime、benchmark或live-provider测试；其完成证明预算、重复失败与停止目标合同闭合，不证明budget ledger、resource enforcement、trusted clock、grant或stop runtime已经存在。

### A07 Phase B Harness Acceptance 设计合同验收

A07是Phase A最后一张文档限定design ticket。执行时运行：

```bash
git diff --check
python scripts/validate_phase_a_control_protocol.py
```

并静态核对：

- A07在`ready`后只有YAML lifecycle metadata改变，冻结正文SHA-256保持一致；A01–A06/A02C01/A03C01保持`completed`且正文未修改，protocol与catalog exact bytes不变；
- catalog owner集合exact等于A01、A02、A02C01、A03、A03C01、A04、A05、A06、A07，共131项required requirements；A07的15个`A07-META-*` IDs与catalog scenario set一致；
- Evals/Observability记录required control acceptance、compatibility regression与capability evaluation分离，六层模型、exact normalized trace、双client/process concurrency、deterministic fault injection与matrix zero-gap gate完整；
- Phase A Overview标记completed；Phase B Overview记录B00–B05的固定职责和依赖、阶段entry/exit gate，并明确当前仍为planned且没有ready implementation ticket；
- B00–B05 ticket文件、`tests/phase_b/acceptance_matrix.json`、runtime、tests或fixtures均未创建，本次不把design validator当作Phase B scenario pass；
- Docs Index、Current State、Decision Log与completion index一致记录A07及Phase A完成，下一步只是起草和确认B00；
- Allowed Files、Do Not Touch、Markdown relative links、ticket metadata、删除/重命名和A07范围内现行状态文档审计通过。

A07明确不运行pytest、benchmark或live-provider测试；其完成证明“Phase B怎样验收”已经冻结，不证明任何Layer 0–5 scenario、matrix或runtime已实现。

### Phase B Acceptance Foundation（B00）

[B00C01](tickets/phase-b-graph-harness/B00C01_SOURCE_BOUND_SEMANTIC_TRACES.md)与[B00C02](tickets/phase-b-graph-harness/B00C02_SEMANTIC_TRACE_EXIT_BINDING.md)已完成来源绑定的trace `0.2`及exit接线。Actual为`raw_with_proof`，先核验本次token/完整digests、canonical source hashes、引用DAG、production replay及Run/root，再比较固定`semantic_expected`；只投影已验证的Execution绝对clock及Run root下完整路径，保留身份、owner、phase、route、budget及material语义。旧`0.1`不变，两版不可跨版本比较。Writer、父validator、runtime case和exit normalizer均显式传递会话绑定；canonical报告不带raw proof、token或实际临时路径。真实双subprocess和stale/tamper回归见[B00C02完成记录](tickets/completions/B00C02_COMPLETION.md)。这些是验收基础，不证明B02/runtime或B05退出适配器已实现。

B00提供可执行的[generator](../scripts/generate_phase_b_protocol.py)、[acceptance CLI](../scripts/validate_phase_b_acceptance.py)、[matrix](../tests/phase_b/acceptance_matrix.json)、[registry](../tests/phase_b/failpoint_registry.json)及[独立final obligations](../tests/phase_b/final_obligations.json)。协议以[B00冻结票据](tickets/phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md)为准；当前包含B00/B01/B02 construction证据；B02独立runtime证据另行验证，全阶段仍未完成。

```bash
B00_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b00-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
RUN_LIVE_LLM_TESTS=0 pytest --collect-only -q tests/phase_b
RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b
python scripts/validate_phase_b_acceptance.py \
  --mode construction --ticket B00 \
  --evidence-dir "$B00_EVIDENCE_DIR/construction" \
  --report "$B00_EVIDENCE_DIR/construction-report.json"
! python scripts/validate_phase_b_acceptance.py \
  --mode final \
  --evidence-dir "$B00_EVIDENCE_DIR/final" \
  --report "$B00_EVIDENCE_DIR/final-negative-report.json"
RUN_LIVE_LLM_TESTS=0 pytest -q
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

Evidence子目录与report文件必须不存在，并位于仓库外；不能复用旧目录。CLI自行生成token、冻结实际source/tests/scripts/configs/synthetic inputs/docs/manifests的path/type/mode/bytes摘要，启动禁用live opt-in的fresh pytest subprocess，最后复核输入未变化。不要在验收期间修改仓库。公开CLI没有test runner、旧evidence或任意shell命令注入选项。

选择B00/B01/B02 construction时，owned/covered/passed分别exact为15/11/30；global covered=56、remaining=75、passed/passed_ids=null，两个完成标志false。Construction报告的runtime仍为not_run，不以单票construction代替1410个独立case证据；独立case0.3总数2199，剩余789个其他票据binding未完成，15项exit尚未接入。

真实final先验证全部输入、独立清单、required node collection与适配器selection；当前预期非零，只有75项coverage_gap、789项runtime_evidence_gap、15项exit_evidence_gap。不能仅凭非零就通过负向验收；任何parser、collection、invalid evidence或internal error都须处理。当前preflight存在缺口，因此不会执行全阶段runtime/exit；报告仍将2199个case列为未在该次final执行，不能与单独B02-owned fresh通过的1410项混淆。

Final具备前置条件后重新执行两个stage的required scenarios，并分派Layer 0–5、cross-system fault/concurrency、Phase B/full/synthetic/legacy suites、compileall、full mock benchmark、CLI smoke和documentation/scope。实际适配器由B05接入`tests/phase_b/harness/exit_checks.py:production_adapters`，不得改变固定check IDs、schema、stage或完成逻辑。每层selection由matrix派生，cross-system由独立case binding派生，suite selection必须等于fresh全目录collection；B05不能用passing子集替代full suite。

Pytest writer分别记录collection/deselection、setup/call/teardown、skip/xfail/XPASS、逐scenario typed result/invariants/trace、production hook触发与恢复后的case result。Future hooks通过注入的test observer登记真实production调用位置，不让runtime读取test fixture。Final逐项联结本次node pass、hook source、触发、outcome与exact trace；inventory、源码函数名或自报passing均不足以通过。

Exit envelope只引用本次evidence目录内的raw bytes SHA-256。Report使用排除token与allowlisted trace ephemeral字段后的semantic evidence digest，不透传raw token-bearing文件摘要；保留identity/head/authority/digest语义。Benchmark必须覆盖`full.json`全部case和全部13项checklist，退出0或顶层passed=true不够；CLI smoke必须证明ledger/state/checkpoint/artifact/budget/Pause/child/accepted invariants。文档适配器还须记录semantic review依据，关键词扫描不能替代合同审阅。

B00已用隔离synthetic adapters永久测试final完整成功、缺exit/hook/post-claim case、stale token/worktree/contract、内部异常及benchmark虚假成功；隔离fixture不能生成project completion。Schema compatibility和bootstrap admission的production反例仍分别由B02/B03/B04实现，B00未新增其runtime。

只有131项所有适用scenarios及runtime obligations均通过才可`requirements_zero_gap=true`；还需全部exit checks通过且errors为空才可`phase_b_complete=true`。当前二者均为false。后续票仍须独立review并获用户批准。

### B01 Pure Execution Foundation

```bash
B01_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b01-XXXXXX)"
python scripts/validate_phase_a_control_protocol.py
python scripts/generate_phase_b_protocol.py --check
RUN_LIVE_LLM_TESTS=0 pytest --collect-only -q tests/phase_b
RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b/test_execution_0_4_foundation.py
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B01 \
  --evidence-dir "$B01_EVIDENCE_DIR/construction" --report "$B01_EVIDENCE_DIR/construction-report.json"
! python scripts/validate_phase_b_acceptance.py --mode final \
  --evidence-dir "$B01_EVIDENCE_DIR/final" --report "$B01_EVIDENCE_DIR/final-negative-report.json"
RUN_LIVE_LLM_TESTS=0 pytest -q tests/test_execution_identity.py tests/test_artifact_registry.py tests/test_state_schema.py
RUN_LIVE_LLM_TESTS=0 pytest -q
python -m compileall -q src tests scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py
git diff --check
```

B01 construction的owned/covered/passed exact为11项；当前接入B02后的global为56 covered/75 remaining/passed null。Final按上节逐类验证缺口。Phase A protocol/catalog/generated bytes与ticket冻结正文保持；case0.2 inventory/obligations使用已批准B00C04的新seal，binding不能改变独立集合。Ownership保持15/11/30/28/47。

Foundation tests验证strict/canonical records、每条record推进head、A02 lifecycle/identity、Agent-output guard、immutable policy、unknown usage、fake clock、semantic fingerprint、reservation/grant事实与cross-head/projection拒绝路径。协调篡改负例重算所有外层摘要后仍须由语义校验拒绝；真实A03注册证据也经过0.4只读适配器。旧0.2 tests不改写。该suite不证明durable publication、Pause/Backend/claim、resource enforcement或B05 exit。

### A02 Execution Identity 验收

A02 的 targeted suite 必须同时覆盖 primitive、真实 compiled graph、demo Human continuation、legacy handoff compatibility 和最小 fallback identity harness：

```bash
pytest -q \
  tests/test_execution_identity.py \
  tests/test_state_schema.py \
  tests/test_routing.py \
  tests/test_graph_smoke.py \
  tests/test_approval_packet.py \
  tests/test_demo_server.py \
  tests/test_memory.py \
  tests/test_report.py \
  tests/test_run_graph_with_codex_handoff.py

python -m compileall -q src/lqcd_agent
```

验收不能只看 pass count，还必须检查：

- 每个新 Run 的 ledger 前四条 records 是 formal Run、initial Cycle、scheduled Planner Attempt、committed START Transition；
- current fixed/conditional/END routes 都通过 Transition commit，且 target wrapper 消费同一个预分配 Attempt；
- physical `codex_handoff` 的 canonical kind 始终是 `legacy_codex_handoff`，没有被伪装成 `code_agent`；
- Human Request/Response 有独立 IDs，validator/consumer/authorized-target lineage 可追踪，重复提交不会增加 Attempt counter 或重写 memory/report；
- re-review、analysis rerun、code fix 和 replan 只作为最小 StateGraph identity harness 证据，不被统计为 current product edge coverage；
- incomplete-Run re-entry 只证明 immutable identity/counter continuity，不被描述成 A04 durable resume。

A02 的完成证据已记录为 targeted suite `125 passed`、full suite `218 passed`，并包含 compileall、scope、29-file Markdown links、stale-doc scan、ticket metadata 和 `git diff --check`。后续修改该合同仍需重复本节检查，不能只沿用历史 pass count。

### A03 Artifact Namespace / Invalidation 验收

A03 targeted verification：

```bash
pytest -q tests/test_artifact_registry.py tests/test_execution_identity.py tests/test_state_schema.py
pytest -q tests/test_graph_smoke.py tests/test_run_graph_with_codex_handoff.py
pytest -q tests/test_method_planner_mock.py tests/test_analysis_engineer.py \
  tests/test_scientific_reviewer.py tests/test_decision_coordinator.py
pytest -q tests/test_approval_packet.py tests/test_codex_handoff_worker.py \
  tests/test_demo_server.py tests/test_memory.py tests/test_report.py
pytest -q
python -m compileall -q src tests evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py
```

除 pass count 外还必须检查：

- canonical member位于 `attempts/<attempt_id>/`，第二个同类 Attempt不改变第一个的 bytes/digest；
- history/index/state heads一致，current selection不使用目录扫描或 mtime；
- `registered` event冻结完整typed pointer和`node_name`，并将Run、Case、Cycle、Attempt、Kind、Node六个identity字段与execution ledger exact-equal；字段缺失、变化或不一致必须fail closed；
- history重放结果与index current exact-equal；普通registration必须紧邻唯一一次current-set，已clear artifact不得重新set；篡改pointer identity、status、members、state paths、跨slot引用或set/clear顺序必须fail closed；
- 每个current-clear必须同时匹配当时current artifact、target Attempt完整provenance、其inbound committed Transition和固定slot policy；transition/target/triggering Attempt/Cycle/reason任一不一致必须fail closed；
- 每个带target Attempt的committed Transition必须反向对应exactly one合法Attempt lifecycle；删除整个target lifecycle后即使同时删除其artifact并协调index/state paths仍必须fail closed；bounded state的current Attempt必须与ledger最新lifecycle exact-equal；
- Cycle、Attempt、Transition、Human Request和Human Response的Run-local deterministic ID/index必须唯一并从1连续到max；bounded state必须指向各类全局latest head，不能回滚到自身仍合法的旧Attempt、旧request或旧response；
- target-null committed Transition只允许terminal `end`/`__end__` route且全部target fields显式存在并为`None`；字段缺失不得当作null；非terminal Transition必须保留完整target tuple并exact匹配目标Attempt，协调删除target Attempt/artifact、回滚state并清空target仍必须fail closed；
- bounded execution-head state和Cycle/Attempt ledger中的nullable identity fields必须显式存在；删除字段即使其期望值为`None`也必须fail closed；
- 每个scheduled Attempt的input current IDs与target policy必须反向派生exact required-clear map；删除一个或全部required clear并协调修改history/index/state仍必须fail closed；legacy incomplete-Run re-entry必须在新Planner副作用前清除旧current；
- dependency必须与注册时replayed current chain一致，不能引用future、wrong-slot或替换后的non-current artifact；普通canonical member必须留在producing Attempt且与logical/projection path一一对应；
- `managed_projections`必须与replayed current members派生结果exact-equal；路径逃逸、protected/control target、重复key、额外/缺失entry、未知或错误owner必须fail closed；
- fixed projection bytes等于 current canonical member，invalidation后不再暴露旧 current；跨slot projection collision必须在写入前失败且保持history/index/projection bytes不变；external code/Human ingress可跳过内容digest比较，但仍必须通过路径、存在性和ownership校验；
- 四层 fallback StateGraph 都经过真实 commit、target allocation 与 side-effect前清除；replan创建新 Cycle，其余保持 Cycle；
- failed/pending target不恢复旧 pointer；Human Response snapshot必须与唯一submitted ledger identity/path/digest一致；accepted-result protection只允许当时current且status为accepted的terminal；未知kind、非terminal/non-accepted或重复protection必须在registry写入前失败；两类protected evidence在后续invalidation后仍可验证；
- Human Request ledger允许`created → packet_written? → satisfied?`且identity稳定；Human Response ledger必须形成合法有序且identity稳定的lifecycle；state声明的active response必须是latest request下max response identity并与其latest record及snapshot protection一致，删除response ledger/protection chain或回滚同一request内response后恢复必须fail closed；只有snapshot写入中的deterministic next response可使用一次受限preflight例外；
- finished Attempt output references必须反向覆盖其registered artifact，registered artifact必须具有合法scheduled/started lifecycle；删除started、整个registration/current-set或accepted/Human protection event必须fail closed；
- 已populated bounded state在initialize时必须先exact validation，不能被registry静默覆盖；仅counter/current/convenience paths全部为空的明确重建state可以从validated registry同步；history/index/execution ledger duplicate JSON key必须fail closed；
- unmanaged legacy fixture byte-for-byte不变；corrupt history/index/member digest fail closed；
- synthetic benchmark若需要检查已失效分析，只能通过 validated artifact history读取 historical evidence，不能恢复 `run_result_path` current。

A03/A03C01 CLI smoke必须写新的 `/private/tmp/lqcd-agent-a03*` output root，并核对 `artifact_history.jsonl`、`artifact_index.json`、execution heads、canonical paths、compatibility projections和accepted-result protection。A03 corrective verification还必须独立重跑stale Attempt、same-request stale Response和nonterminal target-null协调篡改。A03不要求 live provider。

provider dry-run 不发出 live call，也不得打印 secret：

```bash
python -m lqcd_agent.llm.provider_factory --config configs/runtime/openai.yaml --dry-run
python -m lqcd_agent.llm.provider_factory --config configs/runtime/deepseek.yaml --dry-run
```

## Graph 与 Demo 检查

deterministic smoke：

```bash
python -m lqcd_agent.graph.run_graph \
  --case configs/cases/mock_lqcd_goal.yaml \
  --output-dir /private/tmp/lqcd-agent-smoke
```

Golden Demo：

```bash
bash scripts/run_langgraph_demo.sh
```

Golden Demo 必须保持 synthetic、read-only provenance、高风险进入 Human Gate、未批准时 `accepted_result: false`。普通开发验证应优先写入 `/private/tmp`；不要把 repo-local `outputs/` 当成 reference evidence。

## Synthetic Evaluation 与 Benchmark

```bash
python evaluation/run_evaluation.py
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py \
  --provider mock \
  --case-set full \
  --output-dir /private/tmp/lqcd-agent-phase10c-mock
```

两者默认都必须 network-free。runner 若需要清理已存在的 synthetic run，只有明确知道目标是临时评估目录时才使用 `--force-clean`。

## 可选 Live Checks

live provider tests/demo 默认不运行，也不属于普通 ticket 的完成条件。只有 ticket 明确要求、用户同意且本地 secrets 已安全配置时，才使用：

```bash
RUN_LIVE_LLM_TESTS=1 pytest -q
```

或对应 benchmark/graph 命令。不得把 key 写入 command、artifact 或文档。

## Ticket 完成检查

执行一个 `status: ready` ticket 时，完成前必须逐项核对：

1. 只修改 `Allowed Files`，没有触碰 `Do Not Touch`；
2. 满足 Acceptance Criteria 和 Verification；
3. 没有触发 Stop Conditions；
4. 相应核心文档已同步；
5. `REPO_CURRENT_STATE.md` 已更新；
6. 架构或政策变化已追加 `DECISION_LOG.md`；
7. ticket正文从`ready`起保持冻结，只更新YAML lifecycle metadata；
8. completion record位于`docs/tickets/completions/`，没有追加回原ticket；
9. 局部修复有maintenance record，改变合同边界的修复有独立ready corrective ticket；
10. ticket status 的变更经过用户要求或确认。

若 implementation 与文档不一致，应更新 source-of-truth 或停止并报告冲突，不能只在 completed ticket 中留下新合同。

## 第二阶段 Docs 治理验收

第二阶段文档迁移还必须满足：

- 不删除或移动现有文件；
- 第一阶段 Legacy 文件已从当前工作树删除，必要规则已迁入 `AGENTS.md`、Ticket Workflow、Template、安全策略和 Verification Guide；
- 初次文档迁移验收时 Phase A 七个 ticket 均为 `draft`；后续状态必须与各 ticket front matter、Phase Overview 和 `REPO_CURRENT_STATE.md` 一致；
- Phase B–E 没有提前创建执行 ticket；
- `v0.2-demo^{commit}` 仍为 `e73e4d3b967008f290259851caf05f28e087cd5b`；
- 当前 Markdown links 不再依赖已删除文件；历史原文仍可从 `v0.2-demo` 查看；
- 本地 Markdown link check、`git diff --check` 与 `pytest -q` 全部通过。

## B02 控制分支回归

B02恢复执行后的局部bootstrap/storage验证：

```bash
RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b/test_bootstrap_control.py tests/phase_b/test_durable_control_operations.py
```

这些测试在fresh `/private/tmp/lqcd-agent-b02-*`中运行，包括spawn独立解释器、pipe同步竞争、durable边界`os._exit`与原operation恢复。后续控制路径的定向验证入口为：

```bash
RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b/test_pause_control.py tests/phase_b/test_human_control.py tests/phase_b/test_child_control.py
RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b/test_advance_control.py tests/phase_b/test_terminal_control.py tests/phase_b/test_invocation_artifacts.py tests/phase_b/test_external_control.py
```

这些focused命令适合局部回归；完整B02验收还必须运行30项construction和全部1410个独立case。External tests的typed domain source/stop inputs只证明B02控制half；测试数量不等于需求数量，不代替B03/B04交付。

## 相关文档

- [Repository Current State](REPO_CURRENT_STATE.md)
- [Milestone Baseline](milestones/V0_2_DEMO_BASELINE.md)
- [Evals and Observability](EVALS_AND_OBSERVABILITY.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)

Phase A验证器将structure、semantics和freeze分别检查；104项协议变异中101项直接调用指定语义规则，3项验证结构，另保留6项JSON/catalog检查。每条规则先接受合法协议；结构摘要和graph摘要不能代替语义变异通过。内置28条消费失败路径覆盖stop/authority总函数。文档仅自动检查stable IDs、引用和显式枚举，不锁定自然语言措辞；文义一致性仍须人工review。

Publication顺序另有178项直接语义变异，覆盖六条线性控制路径的相邻逆序（同步修改dependency）、绕过、缺失与不可达阶段。独立安全顺序必须包含每个必需publication阶段，特别是running lifecycle先于checkpoint、ownership先于claim、claim先于consume以及eligibility先于terminal lifecycle；验收不能仅更新冻结摘要来放行顺序变化。

## B02C01 legacy source兼容验证

`pytest -q tests/phase_b/test_legacy_source_compatibility.py tests/phase_b/test_child_control.py`从未修改的production旧创建器生成0.2 sources，检查真实格式replay、canonical child/lineage、policy absence、wrong-schema/target/Pause缺失值拒绝、输入篡改、trusted-path限制、幂等、source不变及4个边界的before/after独立process重启。完整suite及fresh B00/B01 construction另行执行；B02C01不新增B02 slice或代表B02 30项验收完成。具体结果见[B02C01执行记录](tickets/completions/B02C01_COMPLETION.md)。

2026-09-18 B02最新复现：`pytest -q tests/phase_b/test_historical_source_control.py -k missing_trace`验证三种historical Fork trace表示均被现有B00拒绝；这是缺口诊断，不是验收成功。只读WAL/CAS/来源校验在同文件，normal-final竞争在`test_external_consumption_control.py`，preparation失败分类在`test_target_preparation_control.py`。新trace格式尚待[B00C03 review](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)批准；B02现blocked，实际回归和fresh报告见[B02 completion](tickets/completions/B02_COMPLETION.md)。

该轮最终实测：完整pytest 1024 passed；A02/A03 139 passed；Phase B collect-only 699项。Fresh B00/B01 construction仍15/15和11/11；final expected-failure只报告105/2286/15三类缺口。冻结输入、compileall、scope、链接及diff检查通过，详细日志与报告位于`/private/tmp/lqcd-agent-b02-final-review-qxn1sask/`。B00C03尚未实施，不能从这些回归数字推导B02通过。

2026-09-21：[B00C03](tickets/phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)已批准并完成。显式trace `0.3`验证原格式historical source、真实Fork reservation及0.4 child引用；旧0.1/0.2语义保持。源checkpoint完整main/WAL/SHM只读副本校验与逐文件不变测试通过。完整pytest **1063 passed**，Phase B **738项可收集**；fresh B00/B01仍15/15、11/11，mapped26/remaining105，final仅105/2286/15缺口。B02恢复原票执行，30项construction和205/1488 runtime bindings仍待完成；见[B00C03完成记录](tickets/completions/B00C03_COMPLETION.md)。这替代上述“B00C03待审批、B02因historical trace阻塞”的当前状态，不改写历史审查事实。

新入口：`pytest -q tests/phase_b/test_historical_source_traces.py tests/phase_b/test_source_bound_traces.py tests/phase_b/test_historical_source_control.py`。历史validator只接受已审查的原格式编码；非空历史artifact encoding及未知格式拒绝。新版本对lineage/CAS/request派生摘要验证preimage后做DAG投影，material和source revision不被删除。固定expected禁止测试运行时重写。

2026-09-21 reservation边界审查：B00C03已completed，其历史证明阻塞已解除；B02随后修复快照丢失卡住和合法grant replan被拒绝，两组回归101/45 passed。真实进程在首次reservation事务COMMIT前退出会完整回滚、没有可恢复的原operation；冻结B00 case笛卡尔展开却要求该边界产生原operation的materialization/domain-gap状态。六项复现及不可变重放对照通过，详见[B02记录](tickets/completions/B02_COMPLETION.md#2026-09-21--reservation-fault-case-executability-audit)。B02现为blocked，待审[B00C04](tickets/phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)，未实施该草案。当前mapped26/remaining105及原2286 runtime/15 exit缺口不变；此前“B02恢复执行”是发现此新缺口前的记录。

2026-09-21本轮验证完成：完整pytest **1086 passed**，Phase B可收集 **761项**；fresh B00/B01 **15/15、11/11**，final仅 **105 coverage / 2286 runtime / 15 exit** 缺口。冻结摘要、生成字节、scope及链接检查通过。B02因[B00C04](tickets/phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)待审仍blocked，详见[B02最终记录](tickets/completions/B02_COMPLETION.md#current-tree-final-verification-2026-09-21)。

## 2026-09-21 B00C04 integrated correction

B00C04验证中：现行case语义0.2要求旧→新disposition集合闭合，独立case2214、B02义务1416；0.1的2286/1488仅为历史数量。新增trace0.4严格验证external Pause资源预留记录引用；独立进程hook回执仅证明触发，case outcome与fixed trace仍由父测试及原validator验证。有界批次使用同一Session，逐批校验后精确合并selection/node/result集合。全局final门槛不变。

B00C04逐项审查补充：11个仅能到达unavailable的phase不可能产生committed result；其22个case改为严格terminal_tombstone_replay，保留真实recovery_required及原owner unavailable，不改runtime状态。旧→新表为1370 retained/118 replaced，现行2214/B02 1416不变。

2026-09-21 B00C04完成：case0.2、trace0.4、直接production进程回执及严格分批验证落地；旧1488个B02 case为1370 retained/118 replaced，现行B02 **1416**、总数 **2214**，全部324 boundary及B03/B04集合不变。完整pytest **1118 passed**、新增定向 **32 passed**，fresh B00/B01 **15/15、11/11**，coverage26/remaining105。Global passed null、phase_b_complete false。B02验收前置阻塞已解除，接续原票处理已审定的runtime缺陷及完整验收；本修正票不代表B02完成。证据见[B00C04完成记录](tickets/completions/B00C04_COMPLETION.md)。

2026-09-21 C04补充审查：Fork `child.source_revision_cas`在首次reservation提交前，两项独立进程反例均完整回滚。沿用原票已批准的全boundary审查范围补齐这一遗漏；C04重新in_progress，B02暂为blocked。旧1488个B02 case现为1362 retained/126 replaced，现行总数 **2208**、B02 **1410**，减少78均有提交前反例；324 boundary、B03/B04及28 post-claim保持。之前2214/1416及C04完成报告保留为当时验证事实。coverage仍26/105；尚无B02 slice。

2026-09-21 C04集成补验完成：完整pytest1158 passed，fresh B00/B01 15/15、11/11；C04现completed，B02继续in_progress。现行独立case2208/B02 1410，covered26/remaining105，尚无B02 slice；此前blocked及补验in_progress为历史过程。详见[B00C04完成记录](tickets/completions/B00C04_COMPLETION.md)。

## B02完整验收与复跑

当前B02已completed：construction30/30、205个boundary下1410个独立runtime case全部通过，完整2599项测试通过。具体输入/session、fixture审查和metadata闭合见[B02完成记录](tickets/completions/B02_COMPLETION.md)。以上日期条目中的旧状态和计数是历史事实。

先在全新的仓库外证据目录执行三票construction及全局负向检查：

```bash
B02_EVIDENCE_DIR="$(mktemp -d /private/tmp/lqcd-agent-b02-verify-XXXXXX)"
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B00 --evidence-dir "$B02_EVIDENCE_DIR/B00" --report "$B02_EVIDENCE_DIR/B00-report.json"
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B01 --evidence-dir "$B02_EVIDENCE_DIR/B01" --report "$B02_EVIDENCE_DIR/B01-report.json"
python scripts/validate_phase_b_acceptance.py --mode construction --ticket B02 --evidence-dir "$B02_EVIDENCE_DIR/B02" --report "$B02_EVIDENCE_DIR/B02-report.json"
python scripts/validate_phase_b_acceptance.py --mode final --evidence-dir "$B02_EVIDENCE_DIR/final" --report "$B02_EVIDENCE_DIR/final-report.json"
```

最后一条当前应非零，必须检查错误集合恰为75/789/15，不能忽略额外错误。要复跑同一冻结输入下的完整pytest并核查B02-owned证据，可在仓库根执行下面的命令。运行期间保持输入不变；任一批失败或输入摘要变化即停止，不能拼接不同session的通过批次。此入口复用B00的证据validator，不改变全局final门槛。

```bash
python - <<'PY'
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path[:0] = [str(Path('tests/phase_b').resolve()), str(Path('src').resolve())]
from harness.inputs import load_inputs
from harness.session import Session
from harness.pytest_evidence import run_pytest_batches, validate_observations
from harness.failpoints import runtime_gaps, validate_runtime
from harness.strict_json import write_new
inputs = load_inputs()
evidence_root = Path(tempfile.mkdtemp(prefix='lqcd-agent-b02-full-', dir='/private/tmp')) / 'session'
session = Session(inputs['root'], evidence_root, inputs['digests'])
env = {k: v for k, v in os.environ.items() if not k.startswith(('PYTEST_', 'PHASE_B_'))}
env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', RUN_LIVE_LLM_TESTS='0')
collection = subprocess.run([sys.executable, '-m', 'pytest', '--collect-only', '-q'],
    cwd=inputs['root'], env=env, capture_output=True, text=True, check=True)
(evidence_root / 'collection.txt').write_text(collection.stdout + collection.stderr)
selection = sorted(n for n in collection.stdout.splitlines() if n.startswith('tests/') and '::' in n)
assert selection and len(selection) == len(set(selection))
evidence = run_pytest_batches(session, selection, name='full', batch_size=25)
write_new(evidence_root / 'merged-pytest.json', evidence)
scenarios = inputs['matrix']['scenarios']
required_scenarios = [s for s in scenarios if s['required']]
observed = validate_observations(evidence, required_scenarios, inputs['root'], all_scenarios=scenarios)
assert set(observed) == {s['scenario_id'] for s in required_scenarios}
passed = validate_runtime(evidence, inputs['registry'], inputs['specs'], scenarios, inputs['root'])
boundaries = {e['failpoint_id'] for e in inputs['registry']['entries'] if e['boundary_owner'] == 'B02'}
required = [cid for cid, spec in inputs['specs'].items() if spec['failpoint_id'] in boundaries]
assert passed == required and len(required) == 1410 and len(boundaries) == 205
assert set(runtime_gaps(inputs['registry'], inputs['specs'], scenarios)) == set(inputs['specs']) - set(required)
session.unchanged()
write_new(evidence_root / 'B02-owned-runtime-report.json', {
    'schema_version': 'b02_owned_runtime_evidence_0.1', 'invocation_token': session.token,
    'digests': session.digests, 'full_suite_passed': len(selection), 'selected_nodeids': selection,
    'owned_boundaries': len(boundaries), 'owned_required_case_ids': required,
    'owned_passed_case_ids': passed, 'passing_scenario_ids': sorted(observed),
    'remaining_other_ticket_runtime_cases': len(inputs['specs']) - len(required),
    'requirements_passed': None, 'phase_b_complete': False})
print('Evidence:', evidence_root, 'full suite:', len(selection), 'B02 cases:', len(passed))
PY
```

此B02-owned report为局部验证证据，不是`PhaseBAcceptanceReport`成功报告。Global final仍须在后续全部映射、runtime bindings和exit adapters齐备时重新执行；不能导入此session复用为另一次final的证据。日常仅复跑受影响focused tests；完整验证已经通过后，只有新代码、失败或未解决疑点才需要重复。

## 2026-09-24 B00C05 case0.3

B00C05已完成并解除B03首次ExternalOperation reservation分类阻塞：真实初始producer与case0.3已验证，独立集合2199（B02 1410、B03 645、B04 144），324 boundaries和28 post-claim不变。Fresh B00/B01/B02为15/11/30，完整2617 passed、同Session B02-owned 1410/1410；mapped56/remaining75，final仅75 coverage / 789 runtime binding / 15 exit，global passed=null、Phase B未完成。B03恢复ready，canonical Backend与其28项验收仍待交付。 本次case版本保留0.1/0.2封存规则与摘要，旧trace0.1–0.4语义不变；B03的case版本入口由已批准B00C05显式替代，其冻结正文不改写。前置2599项通过为B02交付时的历史基线，2617项为本次C05 fresh完整验证。

## B00C06：A05 来源轨迹 0.5

显式 trace `0.5` 使用 proof `0.2`；分派入口仍为 `harness.trace.normalize/compare`。旧 `0.1–0.4` 不变，已有 expected 文件不升级。新增 `harness/a05_trace.py` 的 `CHECKSUMS`、`COMMON`、`PROFILE_REFS`、`EVENT_REFS` 和 `BUNDLE_MEMBERS` 是 project-owned derivation 表；调用者只能提交原始对象及类型声明，不能指定忽略字段或别名。来源验证不是 B03 runtime authority，也不替代 closed-schema、ingress、registry 或 trusted verification。

| 来源／字段 | 原始算法与依赖 | 身份／投影边界 |
| --- | --- | --- |
| Task、Manifest、Core、Receipt、Seal、External/Code Result、Analysis Spec 自描述 checksum | canonical JSON 去掉且仅去掉对应 self 字段后 SHA-256；完整对象另有完整 canonical SHA | 先验证 checksum；普通引用必须使用 self digest，A03 成员必须使用完整 bytes SHA，不能互换 |
| Task execution/artifact heads、budget envelope | 原版本 structural head replay；allow/code_agent BudgetDecision 的 exact event ID/path，且不晚于冻结 execution head | 相同 Case/Run/Attempt；task ID 必须等于 Attempt 的 code_task identity |
| Manifest → Task；Core → Task/Manifest/aggregate reservation；Pause binding → Core/reservation/Task/Manifest | 按指定 kind 和算法解析完整闭包 | Case/Run/Attempt/producer/workspace 的共享身份逐项相等；Pause identity 在关联来源中必须相等 |
| A06 reservation input/task/manifest/context；settlement evidence | 验证原格式完整 ledger；派生对象沿已知字段解析，material/config/policy/base/tree 摘要保留 | 资源 owner 不变；settlement 可引用 external final、verification、interrupt/failure 或 exact failure identity preimage |
| Failure identity | canonical JSON 全对象：owner/source_phase/source_revision/epoch/cause_type/cause | owner 必须匹配消费 operation；cause 材料文本不被通用字符串替换 |
| Receipt/Seal/External Result/Verification/Code Result/Delivery/Analysis Spec | receipt、seal、audit、change、verification、final、bundle/code 等引用按 derivation 表闭合 | Analysis 的 source Code Attempt 必须 exact；不把 Analysis 自己的 Attempt/workspace 当成 Code owner |
| A03 Code registered members、pointer、current index 嵌套副本 | 每个 canonical member 验证原始 SHA、字节数、Attempt namespace 和类型；pointer 必须与 registered source exact-match | backend_delivery 与 host_timeout 分别检查成员集合；已验证 size 随语义成员投影，避免根长度影响摘要 |
| tool_audit.jsonl、changes.patch | 原始 UTF-8 bytes SHA；audit 必须 canonical JSONL、连续 index、完整 owner 和有序时间 | patch 内容 SHA 保留；audit 命令、status、usage 保留 |
| workspace evidence | full canonical digest 绑定 manifest、managed identity、物理目录与 owner | 只允许独立 canonical `/private/tmp/lqcd-agent-*` 根；仅 evidence.workspace_path、verification.results[].cwd、audit[].cwd 可投影；其他材料路径拒绝冒用 |
| 时间、provider reference | 时间只在 profile 的精确位置规范化，验证数值与 start/end 顺序；provider reference 先检查同 operation 一致性 | lease/phase/status/route/usage 不排除；provider 身份不能跨 owner 复用 |
| 顶层七类摘要及 artifacts[].digest | 非空值须有 exact kind/算法/身份来源 | 禁止 literal fallback；missing/duplicate/orphan/cycle/mixed version/stale Session 均拒绝 |

Contract fixture 使用真实 B02 Run、planner artifact、Code target 和 C05 initial producer；其后 A05 对象为合同级来源样本，aggregate/settlement 通过 production builder/replayer，未据此宣称真实 Backend 执行或获得 B03 的 645 项 runtime credit。Normal、host_timeout、failed、unavailable 分别保存双 fresh 根证据与审定 expected；timeout 保留 absence，不补造 seal/receipt。

四条验收路径使用同一 normalizer：collector 写入前验证、matrix exact comparison、runtime case comparison、exit semantic digest。新增 isolated subprocess/hook 只证明验收器通路，不绑定 production registry。完整集成通过前，B03 继续 blocked；通过后仅其 A05 新轨迹采用 0.5。B03 verification 预算事务与 canonical/legacy 状态迁移仍需独立验证。

Control envelope 不能使已知 A05 引用退回 literal：包括真实 resume input 的 `external_final_digest`。内嵌 Task/ExternalOperation 等对象只有与已声明、已校验的完整 raw source exact-match 时才作为该来源投影；不可把包装后的 raw checksum 遗留在语义 hash 中。动态 ExternalOperation 使用 full-object profile，phase/status/lease/revision 保持材料语义，不与 immutable core 的 self digest 混用。

B00C06最终集成已完成：181项定向、2677项全量及同Session B02-owned1410项通过。上述实现已可用于B03新A05轨迹；B03因独立state projection/golden范围仍blocked，参见completion。

## B00C07 approved implementation handoff

2026-09-24：B00C07已按用户同意补强，ready冻结于`7ab58ce`并完成文档交接。B03恢复ready；四个canonical paths来源修复与B02 needs_input fixture窄替换获得明确授权，尚未实现。先推进B03预算事务/失败恢复，再完成canonical实现与28/645验收；当前mapped56/remaining75、Phase B未完成。

详见[B00C07冻结补充票](tickets/phase-b-graph-harness/B00C07_A05_STATE_PROJECTION_GOLDEN_HANDOFF.md)。旧0.2/0.3格式保持原字节，新0.4使用完整nullable path集合与独立status/usable；trace0.5仅修复受来源约束的四个canonical paths，旧trace版本保持。B02材料适配保留原控制断言并使用相同canonical validator；不得将文档交接当作已实现能力。

## B00C08 approved handoff

2026-09-24：B00C08在13f3b74冻结并完成治理交接；B03恢复ready。Normal/timeout完整来源、source trace0.5、独立Analysis success前置及其golden审计范围已批准，尚待B03实现。预算事务与canonical交付未完成，mapped56/remaining75、Phase B未完成。

[B00C08](tickets/phase-b-graph-harness/B00C08_B02_CANONICAL_EVIDENCE_TRACE_HANDOFF.md)明确替代C07受影响source证据不得升级0.5的限制，补齐upstream与safe-timeout材料。迁移source轨迹另存0.5 expected；无成员摘要的phase-only证据仍为0.1。Analysis前置使用独立success/usable bundle，normal needs_input不计canonical Analysis成功。以上为待实施边界。

## B00C09 活动时间账本复核

在相同源版本下运行 `pytest -q tests/phase_b/test_b03_active_time_boundary.py tests/phase_b/test_b00c09_active_time_ledger.py`，再执行冻结票列出的 prestart、reservation、verification、Pause、Phase B 与全仓回归。先用两个 fresh 根比较每个受影响 A05/B02 source-bound outcome 的完整 normalized trace；只有事件形状/identity不变且差异逐项限于 runtime `application_build` 派生的semantic digest/head时，才可在验收运行之前更新相应expected。该次旧/新路径及摘要清单保存在 `/private/tmp/lqcd-agent-b00c09-golden-review.json` 和 `/private/tmp/lqcd-agent-b00c09-b02-golden-review/`。B02旧fixture输入、expected排版、trace版本、case owner/outcome不变。

定向判据包括：setup 3 秒+未结算Backend maximum10得到Run13/Attempt10；setup3+Backend actual6+Attempt5（其中两个verifier各实测1秒）得到Run14/Attempt11且command count2；无调用Attempt6另增加Run/Attempt各6。检查首次stub COMMIT前回滚、COMMIT后setup exact续写、Pause部分前缀、same-owner normal/timeout/failure settlement、跨epoch maximum、过期恢复lease旧epoch拒绝和可信overage的`recovery_required`/unavailable收尾。只有独立reader与live projection相同且完整回归通过，才可完成B00C09；B03完整Backend/Bundle/Analysis和28/645仍按原票执行。

## B03 当前construction与局部runtime复核（2026-09-25）

当前matrix包含B03的28项owned construction映射，累计covered为84/131、remaining47；真实66个nodeid分布于26个construction场景。使用`python scripts/validate_phase_b_acceptance.py --mode construction --ticket B03`在新的外部evidence目录验证，报告必须为owned required/covered/passed **28/28/28**、global `phase_b_complete=false`。受限sandbox阻止Unix-domain socket负例创建测试对象；该节点及包含它的construction须在允许本地socket的执行环境运行，不能跳过或改成pass标记。

当前B03只绑定7/645个独立case：3个初始producer reservation rollback，4个ExternalOperation termination/final-evidence进程故障与结果回放。每个case须由同一fresh Session的passing pytest node、production `coordinator.boundary`子进程回执、恢复断言和固定exact trace共同证明；单独运行`pytest -q tests/phase_b/test_b03_runtime_cases.py`不替代`harness.failpoints.validate_runtime`。局部七项报告位于`/private/tmp/lqcd-agent-b03-runtime-seven-knrbyjp9/session/report.json`，完整645项与B02 1410项仍须在最终固定输入的同一fresh Session分批重验。

旧A05/B02/external来源golden的raw旧值、两个fresh新根、逐事件字段差异及normalized结果位于`/private/tmp/b03-golden-audit-current/`；10份expected在来源与事件序列审定后固定，原trace版本与各文件排版保留。当前final负向预检只有47个coverage、782个runtime binding、15个exit adapter缺口，不能把construction通过或7个局部runtime case解释为B03整票或Phase B完成。

随后又审定B00的`trace_source_bound.json`、`historical_trace_fork.json`及B02的`b02_recovery_control.json`。各自保存旧源码raw、当前两fresh根raw、逐字段差异与exact normalized结果，证据分别位于`/private/tmp/b03-b00-golden-audit/`和`/private/tmp/b03-recovery-golden-audit/`；当前累计13份来源expected。recovery轨迹43条事件只变更6个派生`execution_head`、3个`result_digest`，没有改变route、outcome、owner或事件顺序；trace0.5的真实member摘要虽跨根变化，但完整来源标准化必须相同，篡改仍拒绝。B03独立runtime仍仅7/645，不因来源修正而计为完成。

本轮固定输入全量回归为Phase B **2531 passed**、全仓 **2856 passed**；fresh同Session证据在`/private/tmp/lqcd-agent-b03-partial-session-xxm_nv_w/session/report.json`，construction **15/11/30/28**、B02 runtime **1410/1410**、B03已绑定 **7/7**。最终负向预检在`/private/tmp/lqcd-agent-b03-final-preflight-current-rcT33s/report.json`，仅有47 coverage、782 runtime binding（B03 638 + B04 144）、15 exit缺口，全局标志false。B03C01已completed；B03因12项不可达post-claim冻结case而blocked。[B03C02待审](tickets/phase-b-graph-harness/B03C02_POST_CLAIM_UNSTARTED_CASE_SEMANTICS.md)不改变当前case0.3测试方法；获批准前不得据其候选case0.4计通过。

## B03C02 case0.4 独立验证（2026-09-28）

现行case0.4仅替换六个未启动consumer阶段的12项旧`consumer_stop=unavailable` case。`tests/phase_b/post_claim_case_dispositions.json`逐项固定旧/新ID及新outcome；`case_0_3_failpoint_registry.json`与`case_0_3_final_obligations.json`保留旧0.3原始字节和seal。`test_post_claim_case_semantics.py`验证12 replaced、2187 retained、六项outcome变化、旧版本reader和篡改拒绝；`test_external_reservation_case_semantics.py`的0.2→0.3反例仍以旧0.3为终点。

12项新case各由原进程在故障owner的`consumption_failure_ownership_reserved` phase `after`武装，并只在紧随该事务的`coordinator.database_commit.after`产生真实production hook回执后退出；新进程重读原owner及冻结`started_intent=null`，验证`not_dispatched`、零stop adapter调用、Run authority与唯一terminal收尾。直接在phase `after`退出的六项反例会回滚failure owner，不能计为提交后case。两个独立fresh Session分别见`/private/tmp/lqcd-agent-b03c02-evidence-kd6qnv27/session`与`/private/tmp/lqcd-agent-b03c02-evidence-4xfwzgk_/session`，各有12/12 hook、passing nodeid、outcome及exact trace，trace快照digest一致。既有`invocation_authorized`四格回归另行运行，不计这12项；B03其余626项须继续按原645/645门槛完成。

当前输入的B00/B01/B02/B03 construction报告分别在`/private/tmp/lqcd-agent-b03c02-construction-wmqpdbu5/`，通过 **15/11/30/28**；B03已绑定19项的同Session核验在`/private/tmp/lqcd-agent-b03c02-runtime-nineteen-bzd0aos3/session`通过 **19/19**。B02的1410项独立case在`/private/tmp/lqcd-agent-b03c02-b02-runtime-0ovv07l5/session`同一token与冻结输入下通过 **1410/1410**；一次100-node批次触及300秒上限后，已重新核验前11批原始request/输出并将剩余312个nodeid分为25项批次，最终对全部1412节点执行完整合并验证。Final负向报告`/private/tmp/lqcd-agent-b03c02-final-preflight-1a78wjkb/report.json`仅含 **47 coverage / 770 runtime binding / 15 exit** 缺口；Phase B全局完成标志仍false。

2026-09-29最终全量回归：当前输入的Phase B `python -m pytest -q tests/phase_b` **2552 passed**、全仓`python -m pytest -q` **2877 passed**，均退出0；两次均设置`RUN_LIVE_LLM_TESTS=0`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`及`PYTHONPATH=tests/phase_b:src`。原始日志分别为`/private/tmp/b03c02-phase-b-full.log`和`/private/tmp/b03c02-full-repo.log`。B03C02已completed，但B03其余626项独立runtime仍须绑定，global final仍为负向。

2026-09-29最新B03复核：当前219/645项静态绑定且同一fresh Session严格通过，报告为`/private/tmp/lqcd-agent-b03-runtime-twohundrednineteen-8kil56x6/session/report.json`；construction28/28，余426项。新增38项containment stop case两fresh根exact相同，原Backend cancel六项仍通过。current final预检`/private/tmp/lqcd-agent-b03-final-containment-219-report.json`只报告47 coverage、570 runtime binding与15 exit adapter缺口；全局runtime未执行。重复Code旧raw preimage已按原binding验证并还原expected，但六项current golden仍失败，production稳定前不覆盖；完整645项、B02 1410及Phase B/全仓最终验收仍须执行。


2026-09-29 B03最终验收输入准备：B03已有 **645/645** 静态runtime绑定及新增family的双fresh根exact审计。最终同一fresh Session的B03 645项/B02 1410项、construction 15/11/30/28及全仓回归仍待完成；B03保持in_progress，mapped84/131、remaining47，global `phase_b_complete=false`，B04/B05仍draft。详见[B03执行记录](tickets/completions/B03_COMPLETION.md)。早期219/379等条目是历史输入的检查点。


2026-09-29 B03完成：canonical Fake Backend、Host stop/unavailable、trusted Code消费/资源结算/Bundle、按producer/version的0.4状态投影和fresh Analysis交接通过验收。最终construction **15/11/30/28**，同一fresh Session的B03 **645/645**、B02 **1410/1410**，全仓 **3514 passed**（Phase B **3189 passed**）。Mapped **84/131、remaining47**；全局 `phase_b_complete=false`，B04/B05仍draft，默认产品runtime仍schema0.2。协议/catalog、case/owner/exit门槛与legacy合同保持。详见[B03完成记录](tickets/completions/B03_COMPLETION.md)；较早in_progress及219/379等条目保留为历史事实。未提交或推送。

2026-10-01 B00C10验证交接：trace0.6/proof0.3仅显式选择，0.5 ordinary反例仍须拒绝；新ordinary/Host identity/四消费者专项和两个fresh根fixed expected必须通过。当前同一Session对B02 1410、B03 645及全部仓库nodeid使用C04 run_pytest_batches有界分批，核验hook/outcome/nodeid/exact与输入绑定；不得把旧B03证据或C10 contract-only fixture计为当前runtime。实施及原始审计见[执行记录](tickets/completions/B00C10_COMPLETION.md)和[来源合同](tickets/corrections/B00C10_ORDINARY_RESOURCE_TRACE_CONTRACT.md)。

2026-10-01 B00C10最终验收：同一固定输入Session经C04有界分批及原验证器完整核验，全仓 **3586 passed**、Phase B **3261 passed**、legacy **325 passed**；新增C10 60项与原0.5反例2项通过。同Session B02 **1410/1410**、B03 **645/645** owned set/hook/outcome/nodeid/exact set-equal，fresh construction **15/11/30/28**。Protocol/generator、compileall、冻结字节、scope、local links和diff检查通过；12份旧golden离线仅同步已审定derived值。B04恢复ready，仍0/144、47 construction未完成，mapped84/131、remaining47、B05 draft与`phase_b_complete=false`保持。原始Session/token/输入manifest及中间废弃Session区别见[B00C10完成记录](tickets/completions/B00C10_COMPLETION.md)。

2026-10-02：C11/C12显式0.7/0.4来源验收已完成：同一固定Session3742节点、B02 1410/B03 645 exact owned，三项正式matrix observations和三类四消费者。源码/expected/matrix与验收manifest一致；合同文档交付后另建固定输入Session核验所需来源与文档，不把原full Session冒称新文档输入已通过。Unix socket权限反例保留原失败，在允许本地socket环境不改测试/跳过重跑，原Session有界合并。 见[C12完成记录](tickets/completions/B00C12_COMPLETION.md)、[C11基础合同](tickets/corrections/B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_CONTRACT.md)与[C12补充](tickets/corrections/B00C12_HUMAN_REQUEST_PACKET_TRACE_CONTRACT.md)。C12文档/lifecycle收尾中，C11/B04仍blocked，其产品问题与47/144未完成。

2026-10-02完成交接：C12已completed；独立逐项复核C11全部冻结Requirements/Acceptance Criteria后，C11按原授权completed。B04入口复核确认当前已知maximum/Human/packet/receipt来源Stop已解除，按原授权恢复ready；本轮未实施B04产品修复。B04仍0/144、47 construction/144 runtime未完成，131/84/47、2199 cases、324 boundaries、28 post-claim、15 exit及原owner保持，B05 draft、全局Phase B未完成。来源合同正文及已验收源码/expected/matrix保持；新增状态/索引仅记录事实，不声称原full Session覆盖收尾文档输入。见[C12完成记录](tickets/completions/B00C12_COMPLETION.md)、[C11独立交接](tickets/completions/B00C11_COMPLETION.md)及[B04入口复核](tickets/completions/B04_COMPLETION.md)。先前收尾中/blocked条目保留为当时事实。


2026-10-05，C13 已批准执行并冻结：Human 来源现在区分原 publication completion 的 materialization_pending 与真实 started/no-completion recovery_required；相同 Coordinator diagnostic bytes 按独立注册 owner 解析，真实 satisfied packet locator 绑定原 consumed response。最小 Human 接续、committed duplicate 只读及原 terminal tail reserve/停止链修复见[C13来源补充合同](tickets/corrections/B00C13_HUMAN_CONTINUATION_SOURCE_CONTRACT.md)。完整当前输入验收进行中，B04 保持 blocked、0/144；历史 C11/C12 条目不倒改。


2026-10-05状态补记：C13来源/最小Human实现和29项专项通过，完整当前输入为3791 passed/1 failed；单项旧C10 Host提前拒绝断言交接超出其冻结范围，C13/B04继续blocked。C14仅review，原合同、inventory/owners和B04未完成状态保持。见[C13阻塞记录](tickets/completions/B00C13_COMPLETION.md)及[C14待审票](tickets/phase-b-graph-harness/B00C14_HOST_IDENTITY_REJECTION_ASSERTION_HANDOFF.md)。


2026-10-05 C13合同验收闭合：已批准的独立member owner、Human实际接续、exact publication pending/started recovery区分及原停止链/terminal reserve修复现通过原全部验收，见[C13完成记录](tickets/completions/B00C13_COMPLETION.md)及[来源补充合同](tickets/corrections/B00C13_HUMAN_CONTINUATION_SOURCE_CONTRACT.md)。C14完成后稳定源码的正式同Session3792/3792与owned1410/645、fresh construction15/11/30/28和具体final47/144/15通过；当前源码/测试与该验证输入一致，本轮fresh C13另29/29通过，新增交付文档单独审计。C13 completed后独立入口复核恢复B04 ready，仅其生命周期变更；Planner dependency、ordinary收尾、Code/fallback/grant及原47/144未完成，B04仍0/144、Phase B false。没有新增版本、schema、owner、预算算法、authority或验收边界，旧C11/C12合同/expected与历史状态保持；以上早前blocked条目为原检查点。


2026-10-07 B04局部验证：新增控制失败10项和双fresh来源4项通过；产品/resource/Host专项35、原product/invalidation/C11/C12/identity专项73、C13审定后29、完整legacy325分别通过，不将重叠计数相加冒称full suite。三份C13固定expected仅审定两runtime fingerprint字段与完整派生preimage DAG，before/after raw保存。新因果fingerprint原端口反例导致B04 blocked，C15只review；当前完整suite和同Session owned1410/645未重跑，47/144不计通过。见[B04记录](tickets/completions/B04_COMPLETION.md)。

2026-10-07收尾：另12份旧golden按完整before/after preimage DAG及双fresh审定，仅runtime fingerprint/派生引用变化；补充原来源10项通过。fresh construction15/11/30/28通过，final具体47 coverage/144 binding/15 adapter负向集合exact；全仓collect3806，当前full/owned未实跑。B04 blocked/C15 review及原inventory/owners保持，详见B04 completion。


## C19 Human 容量可达性验收补充（2026-10-07）

采用[独立C19合同](tickets/corrections/B00C19_HUMAN_CAPACITY_REACHABILITY_ACCEPTANCE.md)：原计数证明和明确contract-only纯函数阈值测试，仅替代原固定policy下不可达的独立transition边界实跑方法。可达路径仍须原端口；专用测试纳入之后C18最终全仓exact collection，不计owned、不跳过其他验收。当前专项结果见[C19记录](tickets/completions/B00C19_COMPLETION.md)，不是C18完整Session通过声明。

## 2026-10-08 C18 完整扫描与显式版本入口核对

C19证明仅补充不可达transition验收；其80项已纳入C18当前Session。当前全仓必须同时核对所有实时调用产品的旧版本fixture入口。C18本轮完整4122项实际执行、4120通过；遗漏的C10 structured failure0.6入口仍按原规则拒绝，所需窄交接见 [C20 review](tickets/phase-b-graph-harness/B00C20_C10_CURRENT_FAILURE_SOURCE_VERSION_HANDOFF.md)。不得通过共享collector自动升版、修改旧normalizer或只跑专项宣称兼容。

C10 mixed的summary-only差异另以两before/两after完整preimage审计，在原授权内同步并fresh复验。原socket安全负例使用允许本机UNIX socket的环境，保留第一次沙箱拒绝和成功原回执，未skip。输入manifest、Session、后续expected/状态文档交付分别保存；完整gate未通过时保留blocked，即使owned和construction分别通过。


## 2026-10-12 — C22普通publication prefix验证边界

显式trace `0.10` / proof `0.7` 的执行候选见[C22独立来源合同](tickets/corrections/B00C22_ORDINARY_PUBLICATION_PREFIX_SOURCE_CONTRACT.md)。实际settled、domain registered、Invocation finished和Run closure分别核验；原frozen completion、真实published prefix及实际checkpoint不得混淆。被动采集快照不是runtime journal，不赋予effect或收尾权限；原authority有效时只用原端口补exact suffix，无法安全收尾仍保持原recovery分类。旧0.1–0.9/default/wire/hash和预算不变。

新来源专项61/61通过，完整当前native Session、独立B02 1410/B03 645、fresh construction15/11/30/28及final具体47/144/15仍待验收；B04 blocked/owned0-of-144、B05 draft、Phase B false。旧expected仅允许实际runtime fingerprint及证明完整的派生引用离线同步，不改变outcome、owners或exclusion。实际结果持续记录在[C22 completion](tickets/completions/B00C22_COMPLETION.md)，验证输入和后续文档交付分开保存。


2026-10-13 C22完成补记：显式0.10/0.7来源合同现已完整验收通过，full4273/legacy325、同Session owned1410/645、fresh15/11/30/28及final具体47/144/15；settled/registered/finished/closure及原suffix authority边界保持。B04仅经独立入口恢复ready，原47/144及产品集成仍待完成，B05draft/PhaseBfalse。见[C22完成记录](tickets/completions/B00C22_COMPLETION.md)；上方候选及旧日期记录保留历史。

## C24 当前验收入口（2026-10-13，in_progress）

新增 test_b00c23_unconsumed_code_final.py、test_b00c23_trace_consumers.py、test_b00c24_consumption_failure_source.py，验证原生产来源、五个停止维度双 fresh exact、failed/unsafe/authority unavailable 和真实四消费者。新 B00 meta 不增 case/registry 或 B04 ownership。最终仍须完整当前 Session、legacy325、独立owned1410/645、fresh15/11/30/28及具体final47/144/15；局部探针不是完成。见[C24记录](tickets/completions/B00C24_COMPLETION.md)。

## 2026-10-13 C24 候选验收状态

C24来源候选的90项原生专项、16类双fresh和8个native四消费者已验证；完整集合发现既存B04 spawn child Session接线问题，C24/C23/B04保持blocked，C25仅review。没有production/schema/authority变更或整票交付声明；旧版本/default和原验收集合保持。当前完整验收及同Session独立owned未完成，不能以早前unit-only工厂通过替代。见[C24实际记录](tickets/completions/B00C24_COMPLETION.md)和[C25待审](tickets/phase-b-graph-harness/B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md)。

## 2026-10-14 B04 原生诊断与正式 owned 的边界

[C25来源合同](tickets/corrections/B00C25_PROCESS_SESSION_BINDING_CONTRACT.md)规定：原144外层入口分别编排两个fresh原Session/run_pytest，内层保留真实hook及全部request/receipt/source，按测试局部binding调用原validate_runtime。完整外层不生成未绑定的B04 hook；内层失败必须传递，不能取消ACTIVE、伪造Writer或事后过滤。诊断不产生B04 owned，canonical registry/matrix保持。验收使用同一冻结代码输入的原bounded envelopes精确覆盖4578；组合超时保留失败并完整拆分，单项仍用原300秒上限。测试输入和文档/lifecycle交付分别存档。

## 2026-10-14 C24 独立验收与共同输入审计

按已批准C25 Requirements 12，C24在共同冻结的最终代码输入上形成独立报告；先逐文件核对可执行代码、测试、expected、matrix/registry/协议完全一致，文档/lifecycle差异另列manifest。重读原request/envelope并调用原pytest/matrix/runtime/exit validators，不能替换invocation_token或worktree digest。C24本轮独立复核full4578、legacy325、owned1410/645、90来源/16双fresh/8四消费者188拒绝/7stop，以及原CLI construction15/11/30/28和final精确47/144/15；原失败与超时日志保留，不宣称本轮重新运行全部effect。C23 A1–A5/A4b通过只恢复ready，A6独立入口仍由C23完成。见[独立验收记录](tickets/completions/B00C24_COMPLETION.md)。

## 2026-10-14 C23 独立验收与 B04 正式接续

C23按已批准C25 Requirements 12在同一冻结代码输入上完成独立A1–A6：本轮重新运行原pytest/matrix/runtime/exit validators及只读来源规范化，验证完整4578/legacy325、同Session owned1410/645、16模式双fresh、8native四消费者188负向、七停止route和原CLI construction15/11/30/28、final具体47/144/15。原测试未在本轮重跑，token/digests不重标，文档/lifecycle另列manifest。见[C23完成记录](tickets/completions/B00C23_COMPLETION.md)。

B04恢复ready仅代表入口可继续。正式144case不能只提交现有phase-only诊断；须使用真实Run source proof与原生产hook，并绑定原owners的registry/matrix，完成47construction及同当前输入的B04owned144/full。任何新来源或前置语义超出冻结B04边界时依Stop Conditions停止。


## 2026-10-16 C28 生命周期验收边界（实施中）

[C28说明](tickets/corrections/B00C28_OWNED_BINDING_LIFECYCLE_ACCEPTANCE.md)区分真实probe observation、候选绑定runtime及正式owned。原C27的144双fresh可按原Session只读验证来源/诊断空owned，不能补造case_result或声称当前正式144通过。C28完整当前输入回归和交接尚待完成，B04仍blocked。
