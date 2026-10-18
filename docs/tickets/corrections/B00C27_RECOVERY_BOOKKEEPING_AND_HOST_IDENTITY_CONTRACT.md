# B00C27 原恢复记账与 Host identity 来源补充合同

2026-10-16 状态：**C27/C26已completed，显式0.12/proof0.9来源合同已交付**。C26原Requirements 1–10经独立审计通过；B04经独立入口恢复ready，正式owned仍0/144。下方实施中/候选条目保留历史，当前字段规则以本合同及C27批准补充为准。见[C27完成记录](../completions/B00C27_COMPLETION.md)和[C26独立交接](../completions/B00C26_COMPLETION.md)。

## 状态与边界

用户批准执行的 C27 承接 C26 全部剩余实现与验收。当前为实施候选，最终验收及 C26/B04 独立交接尚待完成；不能把本合同当作 completed 证据。批准范围见 [C27](../phase-b-graph-harness/B00C27_B04_RECOVERY_BOOKKEEPING_AND_HOST_IDENTITY_FIXTURE_HANDOFF.md)，原闭合声明见 [C26](B00C26_B04_FAULT_SOURCE_CONTRACT.md)，实际结果见 [C27 completion](../completions/B00C27_COMPLETION.md)。

显式 trace 0.12 / proof 0.9 继承 0.11 / 0.8，proof 仅增加单项 `fault_sources`。旧版本、default、Session、process receipt 与正式 registry 均不改变。本补充不授予 production 恢复权限，不执行 Agent effect，不登记 B04 owned。

## 原生证据与阶段

外部 expected binding 的 native invocation token 和完整 case ID 决定固定 anchor 目录。proof 中的 anchor、source、stage 引用必须与该独立位置的原 bytes、链、实际 request/receipt 和完整快照一致。候选自己重算 hash 不构成信任来源。

S0 为真实 child 退出并消费 receipt、原来源验证成功后且注入前；S1 为原故障完成后、原 recovery 前；S2 为 first recovery 和全部 contender 结束后；S3 为原 repeat/reentry 完成后。全 roots 来自原 Run 来源、typed workspace 及 Code→Analysis 原 process source 的 base repository。文件清单保留路径、类型、mode、size 和原 bytes SHA；SQLite main/WAL/SHM 完整保留，在私有副本解析全表/schema。新快照按内容去重并用标准库 XZ 无损压缩，raw 用 gzip；读取兼容此前 gzip 快照，旧捕获不重写。解压后的完整 bytes、size 和 SHA 是验证依据，不能少留 bytes 或把副本变成生产根。

每次验读重读原 anchor 与 S3/live durable 状态，再以有界 source resolver 验证各阶段。resolver 仅用于新版本的私有只读视图；原 validator 条件保持。不可构成合法后态 raw 时保留真实 collector 错误、实际损坏 bytes 和独立原 validator 拒绝，不能以 S0 代替。

## 原调用记录

闭合 call 字段为 `entry`、`request`、`owner`、`before_snapshot`、`after_snapshot`、`identities_before`、`identities_after`、`return`、`exception`。request 来自原实际调用的 bound signature，owner 保存实际 worker/capability/invocation epoch。成功无返回的 budget publication 保持 return=null；异常有 type/message 且 return=null。每次原调用前后清单、相邻调用与四阶段边界必须连续，阶段之间仅允许精确验证的派生 collector evidence。

owner race 保存每个实际 contender 的请求、actor、worker、PID 和真实 return/exception，以及原 in_progress/terminal 观察。不得删除败者观察或替换胜者。原结果仍由原 durable operation/journal 验证。

## 精确重复记账

只允许原实际重复 `ArtifactEffectPort.publish_budget` 或 `InvocationLeases.publish_started` 的成功保存使同一 capability revision 增加一次。完整 payload、authorization、worker、epoch、state 和其他行保持；每个保存有真实调用前后清单，增量逐次核对。normalized 显示 before/after revision 与 successful_saves。completion/reentry 不取得这一例外；任何额外 settlement、业务写入、owner 或 operation phase/revision 变化拒绝。

新增 C22 prefix 文件必须逐字段匹配实际 journal revision、完整 journal bytes/hash、原 publication、native binding 和文件名摘要，且被原 0.11 来源验证。normalized 以已验证 capability/revision 表示此派生文件；完整 Session 相关文件名和 bytes 留在原证据中。

## 有界 Host fixture

只有显式 C26 native 原节点在原 parent recovery 作用域安装既有 HostIdentities。namespace 固定为 `b00c27-parent-recovery:<完整 case ID>`，连续 first/repeat/reentry 共用 provider；退出及异常恢复原 provider。真实 UUID 仍写入原 journal 并进入旧 0.11 normalized，不增加 identity alias 或任意 hex exclusion。

每阶段和每调用保留 namespace、各 allocation site 的 ordinal 及实际 allocation 列表。validator 按既有公式重算 UUID、验证连续 ordinal、唯一性，并将真实后续 control operation 与原 resume/decision/Run 关系对照。Session token、nonce、PID、时间和故障 bytes 不固定。

## 合法恢复差异

Invocation 仅按原 frozen started/budget/completion intent 逐 bytes 核对 publication。Control 的原 reservation、immutable request、phase graph/evidence、publication epoch/revision 和 actual return 必须相符。terminal artifact index/checkpoint 来自原 close snapshot；A03 投影删除必须匹配原 frozen invalidation 的 owner 和 SHA；fresh Analysis 的 spec/manifest、base git tree、Code 成员、change/patch、最终 tree 及实际 workspace ownership 均独立核验。完整 schema、foreign rows、其他文件与多余目录继续拒绝。

## 验收与交接

专项应验证四消费者、原两个 CAS 反例、Human allow/halt、race、fresh Analysis、缺失/篡改/重绑/重排/重算候选摘要、旧拒绝与材料敏感性。完整当前输入仍要求原 4578 加新增测试、legacy325、原18/144双 fresh、同 Session B02 1410/B03 645、fresh construction15/11/30/28及 final具体47/144/15。完成 C27 后另审 C26，再核验 B04 入口；不以本合同提前保证 B04 全部产品验收通过。

## 拒绝来源与本次读取复用

实际损坏的 execution ledger 由原 `execution.parse_ledger` 独立拒绝；旧normalizer可能仍接受故障前partial trace，两者分别保留，不伪称旧规则已拒绝所有后态。normalized记录精确的追加字节与已验证前态，完整损坏bytes/hash留在proof。每次消费重新验证anchor、blob和live来源；仅同一次调用中，原raw bytes及完整逻辑状态均相等的阶段才复用已完成的原validator结果，不设跨次/跨进程信任缓存。

## 原 index publication 的原子替换前缀

原`replace_projection`在真实before cut留下的`.artifact_index_<content SHA>.tmp`属于原frozen intent的可物化前缀。仅在完整S1前像为该冻结index bytes、文件名精确由其SHA导出、S2正式index等于同一bytes且mode保持时，验证原恢复消费临时文件。不存在通用`.tmp`删除豁免；全部物理bytes和路径保留，normalized明确记录`atomic_artifact_index_consumption`及目标index，其材料语义由原后态来源验证约束。


2026-10-15 局部实现核对：被动collector在生成C22派生prefix前使用原严格JSON parser读取原index。无completion intent的原invocation integrity-conflict若index不可解析，四阶段保留原bytes与null raw，并独立重现原parser拒绝；旧历史prefix仍按原规则验证。这补齐已批准不可用后态的实际来源，不改变旧normalizer拒绝或历史来源语义。专项双fresh及相邻atomic index回归2项通过，整票仍待最终输入验收。


2026-10-15 原advance完整性失败接续：新verifier逐字段验证原`fail_advance`创建的关联`close_run`，包括parent failure phase/cause、原advance_owner、旧control heads、冻结policy、request/trigger/reservation/precondition与Host分配；仅接受实际原unavailable close的phase/status/error及完整closure行，run_status仍null，不授予terminal文件发布。该原Control recovery分支属于C26/C27批准范围；双fresh专项通过，整票验收仍待完成。

## 2026-10-15 必要prefix父目录的局部校验补全

原first recovery后，已逐字段验证的C22 prefix首次落盘可同时创建其root级`trace_prefix_evidence`父目录。新call snapshot continuity仅从已通过原journal/owner/publication/binding及内容文件名校验的prefix推导这个必要目录，并要求实际目录类型；其余逻辑state必须完全相同。额外目录/文件、错误类型或既有目录变化不被放行。该规则补齐原批准派生collector文件来源，不改production或旧版本。专项12/12与C25–C27的125/125通过，当前仍因完整验收容量不足blocked；全量与独立交接待完成，见[C27记录](../completions/B00C27_COMPLETION.md)。
