# Repository Current State

2026-10-19 B05审定：用户已明确批准B05为ready，并要求固定当前开发基线commit/push后执行。两项进入条件按用户确认视为满足；这不新增或改写实测通过结果，B05实施后的全部fresh final验收仍必需。冻结正文SHA256为`e8bf02217e2bd405023a6ccf2b8661d5f073eb332aa185b00155a146113bed1c`；实际执行、commit及结果见[独立记录](tickets/completions/B05_COMPLETION.md)。当前尚未实施B05，Phase B未完成；下方日期保留历史。

2026-10-19 当前：按用户明确授权完成C29，统一pytest evidence runner单次子进程时限由300秒改为450秒；真实runner中的C21 triple_success为395.88秒并通过原证据验证，现有evidence/process-hook37项和原拒绝探针1项通过。业务预算、其他child时限、全部既有断言及golden保持；这是等待时限调整，不是新增性能优化。完整4785项仍未在本轮重跑，B05保持review且未实施，Phase B未完成。见[独立完成记录](tickets/completions/B00C29_COMPLETION.md)；先前结果保留各自实际输入。

2026-10-18 测试维护：按用户授权整理开发反馈分层、单次验证 AST 复用和普通测试目录生命周期；原有断言及冻结验收保持，新增12项回归；定向及冒烟通过，但全量尝试受12项基线可复现的golden失败阻断，未获本轮全量通过。维护验证见[独立记录](tickets/corrections/TEST_INFRASTRUCTURE_MAINTENANCE.md)；B05仍draft，Phase B未完成，下面B04全量数字仅证明其原固定输入。

2026-10-17 当前：**B04 completed；B00–B04已完成；B05仍draft，Phase B未完成**。固定输入全仓 **4749/4749**（legacy325）、同Session独立owned **B02 1410／B03 645／B04 144**、fresh construction **15/11/30/28/47**通过；131 required／131 mapped／0 remaining。Final具体仅剩B05 **15个exit adapter**，全局passed仍null、phase_b_complete=false。正式144来自本轮真实production source/hook/case result，旧288份诊断仅作golden溯源。原超时/环境失败及重试保留，验证与文档交付manifest分别存档。见[完成记录](tickets/completions/B04_COMPLETION.md)。以下日期记录保留历史，无commit/push。

2026-10-17 当前：**B04 in_progress；C28及前置completed保持**。容量32.25GiB、C28交付5240输入与原47/144入口核对通过，执行前快照及冻结正文保存。原18/144正式hook/observation/case result接线及47construction映射已准备；代表case双fresh、7组stop和同批次正式case通过。本轮完整suite、同Session独立1410/645/144、construction15/11/30/28/47及final仅15exit尚待验收，不把映射当通过；B05draft/PhaseBfalse保持。见[记录](tickets/completions/B04_COMPLETION.md)。下方日期条目保留历史，无commit/push。


2026-10-16 当前：**C28 completed；B04独立入口通过，恢复ready；C26/C27 completed保持**。当前固定输入full **4678/4678**（legacy325）、同Session独立B02 **1410**／B03 **645**、fresh construction **15/11/30/28**及final原具体 **47/144/15**通过。仅修订一项旧meta生命周期假设；实际registry/owners不变。原144双fresh按原绑定只读验证source/诊断，不能证明正式144owned；B04仍owned **0/144**，原47construction/144owned待执行。原失败和重试保留，验证与文档交付输入分开存档。见[完成记录](tickets/completions/B00C28_COMPLETION.md)。以下日期条目保留历史，无commit/push。

2026-10-16 C28执行：**修订版C28经用户批准进入in_progress；B04仍blocked；C26/C27 completed保持**。两处证据边界已冻结；原C26七项和新增C28四项专项11/11通过，当前完整4678、同Session独立owned1410/645、fresh15/11/30/28及具体final47/144/15尚待完成。原144双fresh只读复核只证明来源/诊断，不代计B04 owned；正式47/144仍待B04。见[实际记录](tickets/completions/B00C28_COMPLETION.md)。以下日期条目保留历史，无commit/push。

2026-10-16 B04接续停止：**B04 blocked；[C28待审](tickets/phase-b-graph-harness/B00C28_B04_OWNED_BINDING_LIFECYCLE_META_HANDOFF.md) review；C26/C27 completed保持**。容量门槛通过、执行前4944文件快照及45份冻结正文保存后启动；双fresh正式绑定候选确认C26一项meta仍无条件要求canonical未绑定，合法真实case结果被原validator接受后旧`pytest.raises(Invalid)`报`DID NOT RAISE`。无case_result诊断仍为空owned，原六类拒绝各两份通过；实际matrix/registry/production/harness未改。C28仅待审测试生命周期修正，未实施；B04原47construction/144owned仍未完成，owned0/144、131/84/47、2199cases/324boundaries/28post-claim、原owners、B05draft与PhaseBfalse保持，无commit/push。以下日期记录保留历史。

2026-10-16 当前：**C27 completed；C26 经逐项独立复核 completed；B04 经独立入口复核恢复 ready**。显式 trace 0.12/proof 0.9 的四阶段故障来源、窄 CAS 记账和父恢复 Host fixture 已交付。固定输入完整 **4674/4674**（legacy325、新增96）、原 **18 boundaries/144 cases 各两份 fresh**、同 Session 独立 owned **B02 1410/B03 645**、fresh construction **15/11/30/28** 通过；final 原具体缺口仍为 **47/144/15**。B04 owned **0/144**，仍须原产品集成和正式47/144验收。131/84/47、2199cases/324boundaries/28post-claim、原owners、B05 draft与Phase B false保持。交付文档与实际验收输入分别存档，不重标Session，无commit/push。以下日期条目保留历史。 见[完成记录](tickets/completions/B00C27_COMPLETION.md)与[来源合同](tickets/corrections/B00C27_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_CONTRACT.md)。

2026-10-15 C27恢复执行：**C27 in_progress；C26/B04仍blocked**。清理后容量与当前输入重新核验通过，冻结正文、执行前4944文件快照及manifest已保存；按原授权先恢复ready再启动。第五轮重新固定输入，验收完整4674（原4578+96新增）、原144双fresh、同Session独立owned1410/645、fresh construction15/11/30/28及具体final47/144/15。尚无本轮整票通过声明；B04 owned0/144、131/84/47及原owners保持。下方记录保留历史。

2026-10-15 磁盘清理后：99份旧临时fixture备份经无损重压缩和完整tar字节校验，删除冗余旧压缩副本；另清理7个编译缓存，合计减少约5.17GiB（未扣审计记录少量占用）。当前可用约15.14GiB，已满足C27原10.75GiB容量门槛。旧native/sealed/反例及归档恢复能力保留，仓库实现未变。C27/C26/B04仍保持blocked；下一步为C27重新入口核验及完整4674/144双fresh/owned验收，清理不代表整票通过。下方容量不足记录为清理前历史。 见[清理记录](tickets/completions/B00C27_COMPLETION.md)。

2026-10-15 当前：**C27 blocked（完整验收容量不足）；C26/B04保持blocked**。第四轮原生来源验收133通过、1失败后停止；首次C22 prefix必要父目录的校验遗漏已在批准范围内修复，补跑12/12、C25–C27专项125/125通过。当前精确收集4674项（原4578+96新增），尚无修复后全量/同Session owned/全部144双fresh通过声明。可用约5.75GiB，完整重跑预估至少10.75GiB；3285候选临时目录无可安全清理项，全部旧native/sealed/反例保留。B04 owned0/144、原47construction/144owned/15exit、131/84/47及2199cases与owners保持。C27完成后仍须C26独立审计及B04入口；无需因本次局部修复新增纠偏票。下方日期条目保留历史。 见[本轮记录](tickets/completions/B00C27_COMPLETION.md)。

2026-10-14 C27实施接续：**C27 in_progress；C26/B04仍blocked**。显式trace0.12/proof0.9、原生四阶段/原调用来源、窄CAS记账和有界Host fixture已进入专项验证；原9组18份fresh来源及119项专项通过，补充control拒绝分支已复核。原144双fresh、完整当前输入full/独立owned/construction及交接尚待完成，不提前声明整票通过。B04 owned0/144、47construction、131/84/47、2199 cases、18/144与15exit及原owners保持。下方日期记录保留历史。 见[来源补充合同](tickets/corrections/B00C27_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_CONTRACT.md)与[执行记录](tickets/completions/B00C27_COMPLETION.md)。

2026-10-14：**C27 in_progress；C26/B04 blocked**。用户已批准执行C27，正文worktree冻结；容量入口通过，正在接续两项补充与C26全部验收。B04 owned0/144、47construction、131/84/47和原owners保持。见[执行记录](tickets/completions/B00C27_COMPLETION.md)。以下为历史状态。

2026-10-14 C26执行停止：**C26 blocked；[C27合并补充待审](tickets/phase-b-graph-harness/B00C27_B04_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_FIXTURE_HANDOFF.md) review；B04仍blocked；C23/C24/C25 completed保持**。已保留S0–S3捕获/私有来源候选并通过C25原29项回归，但原重复publication使capability revision真实增加，Human父恢复创建的后续Pause identity在双fresh不同；当前冻结“无新增业务写入”和旧identity规则不足以直接交付。新0.12尚未启用，完整144 source-bound/full/owned/construction未完成，不能声明C26已解决B04阻塞。C27拟合并窄CAS记账分类、显式测试Host fixture接续及C26全部剩余验收，尚未批准或实施；B04 owned0/144、47construction、131/84/47及2199/324/28/144/15与原owners保持，无commit/push。见[C26实际记录](tickets/completions/B00C26_COMPLETION.md)。下方日期条目保留历史。

2026-10-14 C26 修订与临时目录清理：**[C26 修订版](tickets/phase-b-graph-harness/B00C26_B04_FAULT_SOURCE_AND_OWNED_ACTIVATION_HANDOFF.md)仍为 review；B04 blocked；C23/C24/C25 completed保持**。修订明确独立原生capture anchor、S0–S3四阶段及故障/合法恢复/重复调用差异、SQLite完整持久单元、重算candidate hash的拒绝验收和容量preflight；正式反例入口改为confirmed-probes。无引用且关闭的1073个生成目录经19批无损归档、79406成员校验后移除展开副本，净释放约7.54GiB，可用约11.47GiB；163个当前反例文件及保留根完整。仅修订文档，尚未批准或实施0.12，不创建C26完成声明；B04仍owned0/144、47construction待完成，原131/84/47、2199/324/28/144/15和owners保持，无commit/push。下方记录保留历史。

2026-10-14 B04正式接线探针停止：**B04 blocked；C26 review；C23/C24/C25 completed保持**。原故障工厂双fresh诊断通过，但删除capability／损坏canonical member后，故障前Run来源在0.10与显式0.11重验仍严格拒绝；正式B04绑定还会使C25“必须未绑定”的meta断言失败。两类缺口已保存原生反例并合并待审，未改production/harness/registry/expected，未实施0.12。B04仍owned0/144、47construction未完成，131/84/47、2199/324/28/144/15和owners保持。当前没有新full/owned完成声明；下方日期条目保留历史。见[C26待审票](tickets/phase-b-graph-harness/B00C26_B04_FAULT_SOURCE_AND_OWNED_ACTIVATION_HANDOFF.md)。

2026-10-14 C23 接续完成：**C23/C24/C25 completed；B04 经 C23 A6 独立入口复核恢复 ready**。原未消费 normal final、ConsumptionFailure 来源和 child Session 接线阻塞已消除。C23 A1–A6 全部通过；本轮在已批准的共同冻结代码输入上重新执行原验证器与只读来源审计，未重跑全部测试、未重标 Session。B04 仍须完成原 47 construction／144 owned 及剩余产品验收，当前 owned 0/144、131 required/84 mapped/47 remaining，B05 draft、Phase B false。下方原日期记录保留历史。见[C23 独立完成记录](tickets/completions/B00C23_COMPLETION.md)。

2026-10-14 C24 接续完成：**C24/C25 completed；C23 经独立入口复核恢复 ready；B04 保持 blocked**。C24 原10项要求及C23 A1–A5/A4b均已独立核验：共同冻结输入的完整4578（legacy325）、同Session独立owned B02 1410/B03 645、90来源测试、16类双fresh、8个native四消费者188组拒绝、七类停止路由，以及fresh construction15/11/30/28与final具体47/144/15均通过。依据已批准C25 Requirements 12复核原始证据，不重标Session；本轮重新执行原validators和只读来源审计，未重跑effect或修改实现。C23尚须独立A6/B04入口与整票交付；B04owned0/144、131/84/47、2199/324/28/144/15、原owners、B05draft及PhaseBfalse保持。无commit/push。见[独立完成记录](tickets/completions/B00C24_COMPLETION.md)。以下日期条目保留历史。

2026-10-14 当前：**C25 completed；C24 经独立入口复核恢复 ready；C23/B04 保持 blocked**。四类原 spawn 入口使用真实 request 的 Session；144 个原用例各完成两份 fresh native 诊断，原 hook/receipt/raw 全部保留，正式 B04 owned 仍 0/144。共同固定输入完整 **4578/4578**（含 legacy325、新 C25 29）、同 Session 独立 owned **B02 1410/B03 645**、来源90项/16类双 fresh/8个四消费者188组拒绝、停止路由7项、fresh construction **15/11/30/28** 通过；final 精确仍 **47/144/15**。C24/C23 原整票交接及 B04 入口仍须独立完成；Phase B false。验收代码与随后文档/lifecycle交付分别存档，无 commit/push。见[完成与交接记录](tickets/completions/B00C25_COMPLETION.md)。以下日期条目保留历史。

2026-10-14：**修订版C25获用户批准并进入in_progress；C24/C23/B04保持blocked**。本次同时处理真实child Session交接和独立native诊断hook隔离，原registry/validator/owners保持；专项与完整验收正在执行，尚无整票通过声明。见[执行记录](tickets/completions/B00C25_COMPLETION.md)。无commit/push，以下历史保留。

2026-10-13 当前：**C24 blocked；C23/B04 blocked；[C25 待审](tickets/phase-b-graph-harness/B00C25_B04_PROCESS_SESSION_BINDING_HANDOFF.md) review**。C24 来源专用90项、16类双fresh和8个native四消费者通过；完整4549集合已验证4261（含legacy325），B04 spawned child使用unit-only来源导致原生父子binding断言失败，两类工厂已独立复现。修复超出C24冻结清单，按Stop保存反例并停止；尚无完整full/独立owned通过声明。construction15/11/30/28和final原47/144/15已核验，B04仍owned0/144。见[实际记录](tickets/completions/B00C24_COMPLETION.md)。C25未批准或实施；无commit/push，以下历史保留。

2026-10-13：**C24 修订获用户批准并进入 in_progress；C23/B04 保持 blocked**。补齐真实 ConsumptionFailure、未接纳 Backend claim 来源和分离的停止验收；尚无本轮完整通过声明。见[执行记录](tickets/completions/B00C24_COMPLETION.md)。以下历史保留。

2026-10-13 C23 执行停止：**C23 blocked；B04 blocked；[C24 待审](tickets/phase-b-graph-harness/B00C24_CONSUMPTION_FAILURE_SOURCE_HANDOFF.md) review**。新 0.11 来源及七类 B04 停止路由双 fresh 局部检查 7/7 通过；Resume-first ConsumptionFailure 的 active-time/失败身份来源另有真实阻塞，C23 整票及最终 Session 验收未完成。131/84/47、2199 cases、B04 owned0/144 保持；新版本尚未完成交付，旧合同不变，无 commit/push。见[实际记录](tickets/completions/B00C23_COMPLETION.md)。以下为保留的历史记录。

2026-10-13 执行 C23：**C23 in_progress；B04 blocked**。入口和冻结正文已核对，正在实施显式0.11/0.8来源及原整票验收；当前未声明专项/full通过，B04 owned0/144及47construction保持。见[执行记录](tickets/completions/B00C23_COMPLETION.md)。以下历史保留，无commit/push。

2026-10-13 清理与批准：**[修订版 C23](tickets/phase-b-graph-harness/B00C23_UNCONSUMED_CODE_FINAL_STOP_SOURCE_HANDOFF.md) ready；B04 blocked**。用户已批准三个 B04 测试文件的显式 0.11 接线范围，正文及摘要已在 worktree 冻结；新版本尚未实施。无引用旧测试目录经无损归档校验后清理，反例和验收来源保留。B04 仍 owned 0/144、47 construction 未完成；C23 完成及独立入口复核后才恢复 B04 ready。见[批准及清理记录](tickets/completions/B04_COMPLETION.md)。以下条目保留历史，无 commit/push。

2026-10-13最新接续停止：**B04 blocked；[C23待审](tickets/phase-b-graph-harness/B00C23_UNCONSUMED_CODE_FINAL_STOP_SOURCE_HANDOFF.md) review；C22及前置completed保持**。本轮144个独立case工厂双fresh局部复核通过，原registry/matrix/native owned仍未绑定，B04owned0/144、131/84/47保持。新增七类产品停止检查中六类双fresh局部通过；normal safe-stop final未消费时原close_run安全halted/重复readonly，但显式0.10缺真实receipt来源，仅加入真实旧receipt profile仍因无Code registration/full owner被拒绝。双fresh原生产反例已保存，按B04冻结Stop创建新显式来源review，未批准/实施新版本，未改production/旧validator/旧expected/owners；47construction/144owned/full尚未完成，B05draft/PhaseBfalse，无commit/push。见[实际记录](tickets/completions/B04_COMPLETION.md)。以下条目保留历史。

2026-10-13 B04接续执行：用户授权“继续执行B04”，C22 completed交付输入及原full4273/legacy325、同Session owned1410/645、fresh15/11/30/28、具体final47/144/15已独立核对。执行前快照/manifest和31份冻结正文保存后，仅B04 YAML进入 **in_progress**。先显式消费已批准0.10/0.7来源，再继续全部产品集成、47construction/144owned；目前owned0/144、131/84/47及原case/owners、B05draft/PhaseBfalse保持，尚未声明本轮整票通过，无commit/push。见[实际记录](tickets/completions/B04_COMPLETION.md)。以下条目保留历史。

2026-10-13最新：**C22 completed；B04 ready**。显式trace0.10/proof0.7普通已结算publication prefix来源交接完成，固定输入full **4273/4273**（Phase B 3948、legacy 325）、C22专用 **61/61**、同Session独立owned **B02 1410/B03 645**、fresh原CLI construction **15/11/30/28**及final具体 **47/144/15**通过。独立B04入口审查通过后依原授权恢复ready；B04原47 construction/144 owned及剩余产品集成未完成，owned0/144保持。原0.1–0.9/default/production/wire/预算/authority、131/84/47、2199/324/28/144/15及owners保持，B05 draft、Phase B false。验证输入和随后文档/YAML交付分别保存，不retag旧Session，无commit/push。见[完成与交接记录](tickets/completions/B00C22_COMPLETION.md)。以下条目保留历史。

2026-10-12 C22执行：用户明确授权“执行C22”，ready正文已冻结，现 **C22 in_progress；B04 blocked**。仅显式trace0.10/proof0.7来源、被动collector与专用meta交接；[执行记录](tickets/completions/B00C22_COMPLETION.md)。新版本及完整当前Session验收正在实施，未声明completed、未代计B04 owned；原131/84/47、2199/324/28/144/15、owners、B05draft/PhaseBfalse保持，无commit/push。以下条目保留历史。

2026-10-12当前停止：**B04 blocked；[C22待审](tickets/phase-b-graph-harness/B00C22_ORDINARY_SETTLED_PUBLICATION_PREFIX_SOURCE_HANDOFF.md) review；C21 completed**。null active_pause及原completion publication两项B04局部修复共同37/37通过；12种产品轨迹各双fresh严格0.9相等。原进程actual settlement已发布但domain registration未完成的合法prefix被旧agent_registered_diagnostic规则拒绝，双fresh已保存，按冻结Stop提出新显式来源交接，未批准/实施新版本、未改旧expected/owners。见[实际记录](tickets/completions/B04_COMPLETION.md)。本轮full/owned/construction未完成，B04owned0/144、131/84/47、2199/324/28/15及owners、B05draft、PhaseBfalse保持；C21历史不retag，以下条目保留历史，无commit/push。

2026-10-12接续：**B04 in_progress；C21 completed**。用户授权继续整票；当前C21交付输入与前置4191/325、owned1410/645、construction15/11/30/28、具体final47/144/15入口已核对。generic unsafe recovery的active_pause=null已在B04原范围局部修复，真实三种unsafe Code路径及原产品专项19/19通过，见[B04维护记录](tickets/corrections/B04_MAINTENANCE.md)。剩余路由/故障绑定与47/144继续执行，尚无本轮整票验收通过声明，131/84/47、2199/324/28/15及owners、B05draft、PhaseBfalse保持；历史保留，无commit/push。

2026-10-11最新：**C21 completed；B04 ready**。历史Code科学leaf、Task protected Human reference与显式trace0.9/proof0.6原整票验收通过：固定输入full **4191/4191**（PhaseB3866、legacy325）、source/meta **49/49**、同Session独立owned **B02 1410/B03 645**、fresh原CLI construction **15/11/30/28**及final具体 **47/144/15**。独立B04入口审查后依原授权恢复ready，非自动整票完成；generic unsafe recovery及剩余产品集成/47 construction/144 owned仍待B04执行，owned0/144保持。原0.1–0.8/default/wire/预算/authority、131/84/47、2199/324/28/15与owners保持，B05draft、PhaseBfalse。验收输入与随后文档/YAML交付分别保存，不retag旧Session。见[完成与接续记录](tickets/completions/B00C21_COMPLETION.md)。无commit/push；以下日期条目保留历史。

2026-10-11接续：磁盘空间已恢复，当前输入和冻结正文核对一致，依用户授权恢复 **C21 in_progress；B04 blocked**。源码候选及0.9/0.6来源保持；新的完整当前Session、owned1410/645、construction15/11/30/28与final具体47/144/15验收正在执行，旧partial不retag。B04owned0/144、原131/84/47和2199/324/28/15/owners、B05draft、PhaseBfalse保持。见[实际记录](tickets/completions/B00C21_COMPLETION.md)。以下记录保留历史。

2026-10-08当前资源停止：**C21 blocked；B04 blocked**。C21来源/产品接缝已实施，最终固定输入source/meta **49/49**、fresh construction **15/11/30/28**及final具体 **47/144/15**通过；完整4191仅通过 **475**，当前full/独立owned1410/645尚未完成。磁盘剩余约401MiB，已保存全部原始证据和资源停止记录，等待至少10GiB额外空间或其他可写路径后接续A6。不是整票completed，B04owned0/144、131/84/47、2199/324/28/15及owners、B05draft/PhaseBfalse保持；无commit/push。见[实际记录](tickets/completions/B00C21_COMPLETION.md)。以下日期条目保留历史。

2026-10-08最新：**C21 in_progress；B04 blocked**。用户批准“执行C21”，已冻结原正文并保存当前输入快照。历史Code evidence与Task Human scope来源修复及原接缝/四消费者/同Session最终验收正在执行；尚无本轮整票通过声明，原131/84/47、2199/15/owners保持。见[C21记录](tickets/completions/B00C21_COMPLETION.md)，无commit/push；下列条目保留历史。

2026-10-08最新接续结果：**B04 blocked；C21 review；C15–C20保持completed**。产品Code parent候选已组合原B03端口，success/needs_input/failed三项和原prestart合计**27 passed**；此前三条0.8来源各双fresh接受且normalized相等。真实Code失败经Human批准后再次Code的两fresh路径，在第二次消费后被Host拒绝`Code evidence lacks a scientific profile`：当前Task科学leaf/0.8 recipe未覆盖packet必带的前次Code结果。按冻结Stop保存反例并创建[C21待审](tickets/phase-b-graph-harness/B00C21_PRIOR_CODE_EVIDENCE_CAUSAL_SOURCE_HANDOFF.md)，未实施新规则。见[B04结果](tickets/completions/B04_COMPLETION.md)与[maintenance](tickets/corrections/B04_MAINTENANCE.md)。本轮full Session/owned/construction未完成，前置4139结果仅证明原固定输入；B04owned0/144、131/84/47、2199/324/28/15及原owners保持，B05draft、PhaseBfalse，无commit/push。下列条目保留历史。

2026-10-08最新执行：**B04 in_progress**。C15–C20已完成，当前交付输入及独立入口复核通过后，按用户“继续执行B04”保存快照并接续Code/fallback/fresh Analysis/publication及原47/144；尚未声明本轮完成。见[B04完成记录](tickets/completions/B04_COMPLETION.md)。下列条目保留历史。

2026-10-08最新：**C15/C16/C17/C18/C19/C20 completed；B04 ready**。C20补齐C10当前failure显式0.8入口，保留旧版本拒绝；C18与C15–C17各自原要求已独立复核，共同固定Session完整**4139/4139**、legacy325、同Sessionowned**B02 1410/B03 645**、construction**15/11/30/28**及final具体**47/144/15**通过。见[C20完成记录](tickets/completions/B00C20_COMPLETION.md)、[C18完成记录](tickets/completions/B00C18_COMPLETION.md)和[B04独立入口](tickets/completions/B04_COMPLETION.md)。B04按原授权经独立入口核对恢复ready，尚未completed/owned0-of-144；Code parent/fallback/fresh Analysis/publication及47/144仍待执行，B05draft、PhaseBfalse、131/84/47、2199/15/owners保持。验证输入与随后文档交付manifest分开，无commit/push。下列日期条目保留历史。

2026-10-08当前接续：**C20/C18 in_progress；C15/C16/C17/B04 blocked**。C10显式来源入口修复及原测试/新专项通过，C18依原授权恢复最终验收；[C20记录](tickets/completions/B00C20_COMPLETION.md)。尚未声明完整当前Session通过，旧版本/production/131/84/47/2199/15/owners保持，未commit/push；下列条目保留历史。

2026-10-08当前：用户批准执行[C20](tickets/phase-b-graph-harness/B00C20_C10_CURRENT_FAILURE_SOURCE_VERSION_HANDOFF.md)，ready正文已冻结，现**in_progress**。仅交接C10当前failure显式来源入口，原0.6/0.7规则和production保持；实际结果见[C20记录](tickets/completions/B00C20_COMPLETION.md)。C18/C17/C16/C15/B04仍blocked，C19completed；完整固定Session尚未重验，未commit/push。下列条目保留历史。

2026-10-08当前：**C19 completed；C18/C17/C16/C15/B04 blocked；C20 review**。C19可达性验收已交付，C18按原授权补齐专项；同Session实跑4122项，4120 passed、2项C10失败。mixed派生expected已审计同步并fresh复验；剩余C10当前失败入口仍走0.6，显式交接超出冻结清单，见[C20待审](tickets/phase-b-graph-harness/B00C20_C10_CURRENT_FAILURE_SOURCE_VERSION_HANDOFF.md)与[C18实际记录](tickets/completions/B00C18_COMPLETION.md)。owned B02 1410/B03 645、construction15/11/30/28及final具体47/144/15已在该执行输入核验；未声明新交付输入full通过。B04 owned0/144、131/84/47、2199/15/owners保持，未commit/push。下列条目保留历史。

2026-10-07当前接续：**C19 completed，C18 in_progress**。C19交付输入/原冻结摘要已复核，依原授权恢复C18其余H1–V2；原生产候选保持，先补预算publication故障表及来源核验。见[C18记录](tickets/completions/B00C18_COMPLETION.md)。C15/C16/C17/B04仍blocked，尚无当前完整Session/owned通过声明，B04 owned0/144及131/84/47、2199/15/owners保持；未commit/push。下列条目保留历史。

2026-10-07当前：**C19 completed**。不可达 Human transition 阈值的窄验收补充已交付：8项证明、72项 contract-only 及7项原端口/回归通过（含C18三组双fresh、六份新ledger见证）。生产/冻结正文/原验收集合保持。见[C19记录](tickets/completions/B00C19_COMPLETION.md)。C18原授权可在输入复核后接续；C15/C16/C17/B04仍blocked，C18其余H1–V2及最终full Session尚未完成，B04 owned0/144、131/84/47、2199/15/owners保持。未commit/push；下列较早条目保留历史。

2026-10-07当前：**C18/C17/C16/C15/B04 blocked，C19 review**。C18 两项候选修复的三组双 fresh 和原 C13 两项通过；原固定 policy 下独立 transition 容量阈值不可达，冻结原端口验收条款需窄补充。见[C18记录](tickets/completions/B00C18_COMPLETION.md)与[C19待审](tickets/phase-b-graph-harness/B00C19_HUMAN_CAPACITY_REACHABILITY_ACCEPTANCE.md)；C19 未批准/实施。完整 C15–C17 验收及当前 full Session/owned 尚未完成，B04 owned0/144、131/84/47、2199/15/owners 保持，未 commit/push。下列较早条目保留历史。

2026-10-07 C18执行：用户授权修订版 C18，ready 正文冻结后进入 **in_progress**。普通/terminal repause 修复及 C15–C17 全部逐项验收正在执行；**C15/C16/C17/B04 仍 blocked**，尚无当前整票/full Session 通过声明，B04 owned0/144、131/84/47、2199/15/owners 保持。见[C18执行记录](tickets/completions/B00C18_COMPLETION.md)。未 commit/push；下列较早条目保留历史。

2026-10-07当前：**C17/C16/C15/B04 blocked，C18 review**。C17原terminal路由修复及5项专项通过；普通invalid response后repause错用terminal容量，合法纠正被原Resume拒绝；terminal invalid→纠正双fresh另暴露repause proposal raw-head来源未规范绑定。越界修复依冻结Stop停止，反例见[C17记录](tickets/completions/B00C17_COMPLETION.md)；[C18 修订待审](tickets/phase-b-graph-harness/B00C18_ORDINARY_REPAUSE_CAPACITY_SOURCE_HANDOFF.md)现承接 C15–C17 全部冻结验收：补齐 Human 全链、FP/Grant、完整预算故障表与四消费者逐项证据，区分预期 recovery/拒绝与真正 Stop，使用稳定候选的同一最终 Session。此次仅文档修订，未批准/实施；C15–C17 冻结正文不改。无完整当前Session/owned验收通过声明，B04owned0/144、131/84/47、2199/15及owners保持，未commit/push。下列较早状态保留历史。

2026-10-07当前：用户授权修订并执行C17，已明确合法幂等重试与非法重复消费边界，ready正文冻结后进入 **in_progress**。原Human容量/terminal接续及C16全部验收正在执行；**C16/C15/B04仍blocked**，B04 owned0/144及131/84/47、2199/15/原owners保持，未commit/push。见[C17执行记录](tickets/completions/B00C17_COMPLETION.md)；以下较早状态保留历史。

2026-10-07当前：**C16 blocked、C17 review、C15/B04 blocked**。C16来源候选与七组双fresh fixed expected已保存，生产源码保持；C13三项terminal收尾因重复失败先进入普通Human、control=5无sequence而被原Resume拒绝，需生产路由修复，超出C16冻结范围。[C17待审](tickets/phase-b-graph-harness/B00C17_REPEAT_ESCALATION_TERMINAL_RESERVE_HANDOFF.md)未批准/实施，见[C16反例记录](tickets/completions/B00C16_COMPLETION.md)。无完整当前Session/owned验收通过声明；B04 owned0/144、131/84/47、2199cases/15exit及原owners保持，未commit/push。下列较早状态保留历史。

2026-10-07 C16当前：**in_progress**，显式0.8 canonical audit/独立owner来源及当前Human入口交接已形成候选，双fresh七组固定expected与前置摘要审计已完成；当前四消费者、完整固定Session及owned/construction/final验收仍在进行。见[C16执行记录](tickets/completions/B00C16_COMPLETION.md)与[候选来源合同](tickets/corrections/B00C16_CANONICAL_CODE_AUDIT_SOURCE_CONTRACT.md)。**C15/B04仍blocked**，B04 owned0/144、131/84/47、2199cases/15exit及原owners保持，未commit/push。较早条目保留历史。

2026-10-07 C16执行：用户授权“执行C16”，ready正文摘要核对后进入 **in_progress**；当前来源与验收进行中，C15/B04仍blocked，B04 owned0/144及131/84/47/2199/15保持。见[C16](tickets/phase-b-graph-harness/B00C16_CANONICAL_CODE_AUDIT_SOURCE_HANDOFF.md)与独立completion，较早批准/待审状态保留历史，未commit/push。

2026-10-07 C16批准登记：用户明确“批准C16”，[C16](tickets/phase-b-graph-harness/B00C16_CANONICAL_CODE_AUDIT_SOURCE_HANDOFF.md)由review提升为 **ready**，正文冻结SHA256=`e7c10364d4dae3a982f36724f19c4db9cc57d2334d033a1473e259de8c8c7fc6`。本次仅登记批准，尚未启动实施；**C15/B04保持blocked**，来源缺口及整票验收尚未解除，B04 owned0/144、131/84/47、2199cases及15exit保持。冻结仅在当前worktree及私有审计副本，无committed snapshot，未commit/push；下列早前状态保留为历史检查点。

2026-10-07最新：**C15 blocked、C16 review、B04 blocked**。C15部分18项专项通过；实际Code/fresh Analysis来源因canonical audit与既有A05 profile不符而audit_owner拒绝，新增解释按冻结Stop待单独批准；候选分支已撤回，Human/matrix未验收接线已恢复，旧expected保持。[C16待审](tickets/phase-b-graph-harness/B00C16_CANONICAL_CODE_AUDIT_SOURCE_HANDOFF.md)未批准实施。无C15整票/full Session/owned1410/645当前通过声明；131/84/47、2199cases、B04owned0/144和15exit不变，历史条目保留。

2026-10-07 C15执行中：用户授权执行修订版，ready正文冻结后仅YAML进入**in_progress**。部分Host/来源及18项专项已通过；Code/fresh Analysis探针已通过新来源，完整交接与验收仍在进行。B04保持**blocked**、owned0/144，131/84/47、2199cases、15exit不变。旧完整Session不能覆盖当前实现。见[C15实际记录](tickets/completions/B00C15_COMPLETION.md)；历史条目保留。

2026-10-07 C15修订待审：按用户指令补齐0.8/proof0.5闭合字段、逐failure/Grant owner与固定科学投影规则、Coordinator阶段发行/认证actor绑定及预算publication before/after故障验收。[当前待审状态](tickets/phase-b-graph-harness/B00C15_PRODUCT_FAILURE_FINGERPRINT_AND_GRANT_SOURCE_HANDOFF.md)仍 **review**，本次只修订文档；新版本/生产集成/合同交付尚未实施，B04继续 **blocked**、owned0/144，131/84/47及原case/owners不变。

2026-10-07最新：B04 接续执行已保留 Planner 早期控制依赖、科学接受 guard 和 ordinary exception/overrun/clock 主路径收尾修复；C13 审定后三份固定 expected 仅同步实际 runtime fingerprint/派生摘要，29项回归通过，legacy325通过。两个 fresh 原生产候选的合法 Host 因果 fingerprint 被原0.7拒绝 `failure_member_source`，触发冻结 Stop Conditions，B04现 **blocked**。新增 [C15待审](tickets/phase-b-graph-harness/B00C15_PRODUCT_FAILURE_FINGERPRINT_AND_GRANT_SOURCE_HANDOFF.md) 仅review、未批准实施，原源码未纳入fingerprint候选；Code/fallback/fresh Analysis/fingerprint/grant和47/144仍待完成，owned0/144、131/84/47及B05 draft/Phase B false保持。当前完整suite/同Session owned1410/645尚未重跑，执行前基线不能冒称覆盖本轮源码。收尾另审定12组旧golden的同类摘要，fresh construction15/11/30/28及final具体47/144/15负向集合通过；全仓collect3806仅为collection。验证输入与后续交付文档分开。以下日期条目保留历史。

## 状态摘要

2026-10-17现行摘要：B04 completed、B05 draft；full4749、owned1410/645/144及construction15/11/30/28/47通过，131mapped/0remaining，Phase B false。本节下方2026-10-05至10-07的状态及列表保留为历史检查点，以文首与B04完成记录为当前依据。

2026-10-07最新：用户批准实施B04接续计划，B04由ready进入in_progress，先修Planner早期控制依赖及ordinary异常收尾。执行前输入与2026-10-06 fresh完整3792/3792、owned1410/645及construction15/11/30/28基线exact一致。原票正文冻结，B04 owned仍0/144、47/144未完成；见[B04执行记录](tickets/completions/B04_COMPLETION.md)。以下条目保留之前检查点。

当前状态（2026-10-05 C13原验收完成）：C13 **completed**；C14单项范围纠偏已完成。原稳定源码正式Session全仓3792/3792、同Session B02 owned1410/B03 owned645、legacy325、fresh construction15/11/30/28及final具体47/144/15均经独立原始证据审计；本轮fresh C13专项另29/29通过。C13完成后独立B04入口复核通过，依原授权仅恢复**B04 ready**。B04仍owned0/144，Planner dependency、ordinary收尾及Code/fallback/Analysis/fingerprint/grant等原47/144责任待执行；131/84/47、2199 cases、324 boundaries、28 post-claim、15 exit/owners及B05 draft/Phase B false保持。正式验证输入与后续文档交付分开，无commit/push。见[C13完成记录](tickets/completions/B00C13_COMPLETION.md)与[B04入口记录](tickets/completions/B04_COMPLETION.md)。

以下既有摘要和日期条目保留历史检查点；早前C13 in_progress/blocked与B04 blocked状态由本次完成/入口复核接续。

- **更新时间**：2026-10-05
- **当前分支**：`codex/phase-11-agent-harness-upgrade`（已快进包含`xgao`的Phase A设计冻结提交`d0f108a`）
- **当前阶段**：Phase A、B00–B03和C10/C11/C12/C14已completed；C14解除C13单项C10范围阻塞后，C13按原授权恢复in_progress以复核原全部验收。B04仍blocked、owned0/144；B05 draft，Phase B未完成。
- **活动 ticket**：[C13](tickets/phase-b-graph-harness/B00C13_HUMAN_CONTINUATION_SOURCE_AND_PREFIX_HANDOFF.md)恢复in_progress，原source/Human/prefix修复及双fresh/golden审计保留；须独立复核原Acceptance Criteria全部项并完成交接。[C14](tickets/phase-b-graph-harness/B00C14_HOST_IDENTITY_REJECTION_ASSERTION_HANDOFF.md)已completed：原端口提前拒绝、一次effect/actual settlement/无domain发布/后继Work与独立member身份拒绝均通过。见[C14记录](tickets/completions/B00C14_COMPLETION.md)和[C13交接](tickets/completions/B00C13_COMPLETION.md)。B04 Planner dependency、ordinary收尾、Code/fallback/Analysis/fingerprint/grant及47/144仍待修。
- **稳定基线**：[`v0.2-demo`](milestones/V0_2_DEMO_BASELINE.md)
- **验证输入**：C14正式固定Session全仓3792/3792（Phase B3467、legacy325）、C13专项29/29、同Session owned B02 1410/1410与B03 645/645、fresh15/11/30/28通过；final仅原47 coverage/144 binding/15 adapter且具体ID集合exact。131/84/47、2199 cases、324 boundaries、28 post-claim、15 exit与owners保持，B04 owned0/144、global Phase B false。完成后的文档/lifecycle输入单独审计，不冒称固定Session覆盖新增交付输入。默认CLI仍schema0.2；无commit/push。

- **C10完成时最终验收（C11源码变动前）**：全仓 **3586 passed**（Phase B **3261**、legacy **325**），fresh construction **15/11/30/28**，同Session B02 **1410/1410**、B03 **645/645**；B04仍 **0/144**。证据见[B00C10完成记录](tickets/completions/B00C10_COMPLETION.md)。

下述接续核验为C10批准实施前的历史检查点；当前状态以上述摘要和最终完成记录为准。

2026-10-01接续核验：B04仍blocked，B00C10补强后仍review、未实施；Host identity fixture例外只是待审设计。当前前置专项**132 passed、5 golden failed**，五份双根normalized一致但expected尚待离线同步；Human validator出版、ordinary overrun收尾及Agent覆盖Host identity三项真实缺陷未修复。详见[B04接续审查](tickets/corrections/B04_CONTINUATION_READINESS_REVIEW.md)，其47/144及当前完整回归仍待完成。

## 当前稳定实现

2026-10-17新增稳定实现：显式canonical0.4入口及B04全部产品集成/47construction/144owned已完成，默认legacy0.2 CLI保留。下方既有实现列表是此前检查点；其中B04未完成描述已由本次交付接续。

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
- target route contract 在B04新canonical入口中部分接入，但完整fallback/Human/Code/grant/stop及47/144验收仍待完成；identity、invalidation及A04/A05/A06冻结合同保持，默认legacy入口不变。

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

2026-10-17当前固定输入：full4749（legacy325）、同Session owned1410/645/144、construction15/11/30/28/47与final具体仅15exit通过；global passed null、Phase B false。验证与随后文档交付manifest分开保存。以下较早验证结果保持原输入/日期，不作为当前整票结果。

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

2026-09-24：B03因活动时间记账合同缺口blocked，B00C09纠偏实施票为review，已补齐待审wire、发布与恢复边界，尚未获准执行。3秒Host setup在真实public Pause和新进程ledger replay中遗漏；不能靠增加Backend active_seconds解决Run-only计费。基础定向70 passed、workspace14 passed；完整canonical与28/645验收未完成，mapped56/remaining75保持。详见[B03最新执行记录](tickets/completions/B03_COMPLETION.md)。

本轮收尾：B02消费/失败收尾回归96 passed，协议/生成字节/冻结正文及181个链接校验通过。基础实现和阻塞记录保存为开发检查点；B03 blocked、B00C09 review，未push，不代表完整suite或B03验收通过。

2026-09-24 B00C09修订：待审票已明确 B00C05 首次 stub COMMIT 后再发布冻结的 setup event，保留 verification 资源的实测时长、覆盖 normal/timeout 与部分 Pause 的结算，并限定旧 golden 的派生更新。仍为 `review`，未获准实施；B03 保持 `blocked`。

2026-09-25 B00C09完成：活动时间区间、Pause与Attempt结算、nested verification和恢复门禁已按冻结合同实现；Phase B 2459 passed、全仓2784 passed，11份golden仅同步136个派生摘要值。B00C09为completed，B03恢复ready；canonical Backend/Bundle/Analysis和28/645验收仍未完成，mapped56/remaining75及Phase B全局未完成。见[B00C09完成记录](tickets/completions/B00C09_COMPLETION.md)。

2026-09-25 B03接续：fresh B02 construction为30/30、累计56/remaining75。B03在原授权下进入in_progress；Fake Backend持久化port、public Pause后dispatch、同operation receipt/result引用、deterministic containment与Host workspace seal基础已增加，98项相关定向回归通过。尚未完成可信ingress、normal final、Bundle、Analysis和28/645验收，未改动前置case owner与全局exit判断。见[B03执行记录](tickets/completions/B03_COMPLETION.md)。

2026-09-28 B03当前工作树：B03C01重复Code prior IDs与B03 canonical Backend、消费、Bundle、状态和fresh Analysis基础已实现；fresh construction为B00/B01/B02/B03 **15/11/30/28**，累计映射 **84/131、remaining47**。B03独立runtime仅 **7/645** 有本次子进程production hook、passing nodeid和exact trace，另638未绑定；B02 1410项同Session重验待执行。前次Phase B探索性全量为2527 passed、4 failed；其中canonical fixture恢复actor、trace0.5旧反例已按maintenance修复，第十三份B02 recovery expected经旧源码raw及当前双fresh根审定后只同步9个派生字段，相关定向22 passed，Phase B复验运行中。`phase_b_complete=false`，B03/B03C01仍in_progress，未提交或推送。见[B03执行记录](tickets/completions/B03_COMPLETION.md)。

2026-09-28固定输入复核：Phase B **2531 passed**、全仓 **2856 passed**，同一fresh Session的construction **15/11/30/28**、B02独立runtime **1410/1410** 与B03已绑定 **7/7** 通过；累计mapped **84/131、remaining47**，final仅 **47 coverage、782 runtime binding、15 exit** 缺口，`phase_b_complete=false`。B03C01重复Code纠偏已completed。B03冻结case0.3的六个未启动post-claim阶段共有12项`consumer_stop=unavailable`不可达，按原Stop Conditions转为blocked；[B03C02](tickets/phase-b-graph-harness/B03C02_POST_CLAIM_UNSTARTED_CASE_SEMANTICS.md)为review、未改case文件。B03仍缺638项独立runtime绑定；无提交或推送。详见[B03完成记录](tickets/completions/B03_COMPLETION.md)。

2026-10-01最终更新：B00C10 completed，B04来源类型阻塞解除并恢复ready。当前固定输入全仓 **3586 passed**（Phase B **3261**、legacy **325**），fresh construction **15/11/30/28**，同一Session B02 **1410/1410**、B03 **645/645**；12份前置golden仅离线审定指纹/派生值。Production/Phase A字节保持，B04三项已复现缺陷、47 construction/144 runtime仍未修复或验收。Mapped **84/131、remaining47**，B05仍draft、`phase_b_complete=false`；较早review/blocked及5 golden failed是历史检查点。证据见[B00C10完成记录](tickets/completions/B00C10_COMPLETION.md)。未提交或推送。

2026-10-01 C10后执行核验：fresh construction **15/11/30/28**、同Session定向 **17**与legacy **325**通过；final负向exact为 **47 coverage / 144 binding / 15 exit**，无额外错误。实际Planner critical/Analysis high+approval或Planner ambiguous仍会accepted；Human Resume、overrun/exception与Host字段问题未修复。原生产primitives的真实exception最大结算后已由原close_run提交failed，但trace0.6报`exception_settlement`；因B04不能修改B00 validator或放宽来源合同，当前改为blocked，待独立纠偏。见[B04最新核验](tickets/completions/B04_COMPLETION.md)。本轮仅审查与文档/lifecycle，无production或tests改动；C10仍completed，之前ready条目为历史检查点。

2026-10-01 B00C11创建：用户确认“来源纠偏＋B04接续”后，已创建[B00C11](tickets/phase-b-graph-harness/B00C11_ORDINARY_MAXIMUM_SETTLEMENT_TRACE_HANDOFF.md) review票及待审入口。拟议0.7/0.4、closed maximum来源、真实观测/原owner、四消费者与双fresh验收尚未实施；本轮只完成文档、metadata/links、范围和冻结检查，不复跑runtime或创建C11完成记录。B04保持blocked，原执行授权和47/144责任保持；C11经另行批准、执行、completed及入口复核后才可恢复B04 ready。C10继续completed，production/tests/验收输入及冻结历史保持，未commit/push。

2026-10-01 B00C11待审修订：用户要求按审查意见修订，票据现以clock_read_state区分原读取完成、callee异常导致end未执行及实际读失败；expected null不自动归clock_untrusted，真实异常可达callee_exception。Hard usage未知保留为异常/clock场景的material属性，取消独立usage-unknown原因/正向路径；补清只委托原读取的被动FakeClock port wrapper、禁止补读/跨阶段借用时间及对应正负验收。本轮仅修改待审票、当前状态及B04记录，0.7/0.4未实现、未新跑runtime/full suite；C11仍review、B04仍blocked、C10仍completed，原131/84/47、2199/144/15及owner集合保持，无commit/push。

2026-10-01 B00C11 Human来源补充修订：双fresh审查确认原resume绝对payload_reference与注册相对member确为同一文件/bytes/SHA/snapshot，trace0.6仍因字面路径比较报human_owner；实际resume保持recovery_required，不证明Human产品流程成功。用户要求按建议修改C11，现将严格locator/原owner绑定、限定来源字段投影、grant_source/human_scope关联、双fresh/四消费者/路径负例及两项来源缺口分别解除的恢复门槛纳入review票。Grant/remediation合同级meta与真实dispatch明确分开，原0.1–0.6语义及B04产品责任保持。本轮仅待审文档与索引同步，未实施新版本、未新跑runtime/full suite、未创建C11完成记录或commit/push；B04继续blocked。

2026-10-01：用户明确批准执行C11，ready正文冻结后进入in_progress；新来源与完整验收进行中，B04仍blocked，未将审批等同缺口解除。结果另记C11 completion，冻结正文不回写。

2026-10-01 C11执行停止：用户批准后冻结ready正文并实施新0.7/0.4来源候选；原maximum异常结算/closure及Human snapshot入口单根可读取，但两个原resume fresh根的Human请求packet_reference为不同绝对路径，normalized从human_request:packet_written（原event_index31）起不一致，exact失败。冻结Requirement 4仅允许response/grant locator投影，不能直接去根或扩范围。因此C11 blocked、B04继续blocked；新候选未完成双根/四消费者及当前全量验收，旧C10 3586与B02/B03证据不代替本轮。见[C11执行记录](tickets/completions/B00C11_COMPLETION.md)。

2026-10-01补充纠偏创建：用户同意后新增[B00C12](tickets/phase-b-graph-harness/B00C12_HUMAN_REQUEST_PACKET_TRACE_HANDOFF.md)，status=review，目标是原Human请求packet的独立requesting/producer owner、原注册member/bytes及Invocation publication绑定；仅新增0.7/0.4限定来源规则，不改旧版本、C11冻结正文或product。创建阶段仅文档核对，无新实现、验收完成或Git publication。C11/B04仍blocked，C12未ready；131/84/47、2199 cases、324 boundaries、28 post-claim和15 exits保持。

2026-10-02 C12待审扩充：独立审查确认原packet_written为Human轨迹唯一残留根路径来源；另有真实Host exception receipt原端口结算/failed closure成功却被maximum_actual_error拒绝，C11 maximum/Human尚未正式登记matrix。用户要求由C12覆盖C11全部已知剩余阻塞，现已将closed receipt、正式meta、C11逐项全部来源验收及当前Session前置/完整回归纳入[B00C12](tickets/phase-b-graph-harness/B00C12_HUMAN_REQUEST_PACKET_TRACE_HANDOFF.md)完成门禁，不留下交还C11补修/补验收项。当前仅文档修订，C12 review、C11/B04 blocked；没有实施、正式交付合同或新的完成记录，未commit/push。C12 completed之后只交接C11独立证据复核/lifecycle，C11 completed后再复核B04入口；B04 Human、Host/风险guard、ordinary收尾、Code/fallback/grant及47/144问题保持，原131/84/47、2199/324/28/15与owner集合不变。

2026-10-02 C12批准登记：用户明确“批准修订版 C12”，已将[B00C12](tickets/phase-b-graph-harness/B00C12_HUMAN_REQUEST_PACKET_TRACE_HANDOFF.md)由review提升ready，正文冻结摘要`d41821f4df19acf765ff8932e70f9861cb290261eed52194ebdabf0c0822e2f8`；除YAML status外正文未改。冻结在当前worktree及私有审计副本，未commit/push，不声称存在committed snapshot。当前只批准登记、未启动实施，C11/B04仍blocked，0.7/0.4候选未交付；须完成C12全部来源/当前验收，再作C11独立完成交接与B04入口复核。原131/84/47、2199/324/28/15及B04 0/144保持。

2026-10-02完成交接：C12已completed；独立逐项复核C11全部冻结Requirements/Acceptance Criteria后，C11按原授权completed。B04入口复核确认当前已知maximum/Human/packet/receipt来源Stop已解除，按原授权恢复ready；本轮未实施B04产品修复。B04仍0/144、47 construction/144 runtime未完成，131/84/47、2199 cases、324 boundaries、28 post-claim、15 exit及原owner保持，B05 draft、全局Phase B未完成。来源合同正文及已验收源码/expected/matrix保持；新增状态/索引仅记录事实，不声称原full Session覆盖收尾文档输入。见[C12完成记录](tickets/completions/B00C12_COMPLETION.md)、[C11独立交接](tickets/completions/B00C11_COMPLETION.md)及[B04入口复核](tickets/completions/B04_COMPLETION.md)。先前收尾中/blocked条目保留为当时事实。

2026-10-05 C13 修订并获用户授权执行：已按独立审查区分 exact completion 的 in_progress/materialization_pending 与 started/no-completion 的 recovery_required，补清最小 Human control、停止链与 reserve 交接及 committed duplicate 边界。C13 ready 正文冻结后进入 in_progress；B04 仍 blocked，未宣称来源或完整回归已通过。执行见 [C13 completion](tickets/completions/B00C13_COMPLETION.md)；原 owner、131/84/47、2199 cases、15 exit 与 B04 0/144 保持。


2026-10-05 C13执行收尾：Human最小接续/来源修复和29项专项通过；固定同Session全仓3791 passed/1 failed，B02 owned1410/1410、B03 owned645/645、legacy325及fresh construction15/11/30/28通过，final原47/144/15 exact缺口保持。唯一失败为C10旧Host identity测试仍要求completed后normalizer拒绝，而生产端口已在publication前拒绝；修改该测试不在冻结C13范围，故C13 **blocked，未completed**，B04继续blocked/0-of-144。新增C14仅review，创建不代表批准或实施。见 [C13执行记录](tickets/completions/B00C13_COMPLETION.md) / [C14待审票](tickets/phase-b-graph-harness/B00C14_HOST_IDENTITY_REJECTION_ASSERTION_HANDOFF.md)。原131/84/47、2199 cases、324 boundaries、28 post-claim、15 exit与owners保持；Planner dependency、ordinary收尾、Code/fallback/Analysis/fingerprint/grant及B04 47/144仍待修。文档/lifecycle交付与固定验证输入分开，未commit/push。

2026-10-05 C14完成：正式固定输入3792/3792、独立owned1410/645及fresh15/11/30/28、final具体47/144/15和scope审核通过；C13恢复in_progress、B04仍blocked。仅旧Host身份负向测试与文档改变，原source/harness/helper/expected/matrix/owners保持；原B03 socket sandbox失败和首个full batch超时保存，新fresh原样/更小有界批次重跑通过。详见[C14完成记录](tickets/completions/B00C14_COMPLETION.md)。
