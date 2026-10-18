---
ticket_id: B00C16
phase: phase-b-graph-harness
status: completed
type: corrective-implementation
depends_on: [B00, B03, B00C15]
---

# B00C16：canonical Code 工具审计与独立 owner 来源交接

## Goal

补充 C15 trace0.8/proof0.5 的 canonical A05 工具审计来源，使原 B03 Code、trusted verification 和真实 fresh Analysis 的合法材料能进入四条消费路径。C15是纠偏目标，不要求先completed；创建不代表批准或实施，C15/B04保持blocked。本票完成后独立复核C15原全部验收，不直接完成C15或恢复B04。

## Why

2026-10-07 C15已局部实现ordinary科学fingerprint、Coordinator阶段validated Grant发行及原advance单次消费，18项部分专项通过；尚无整票/full Session通过。用原产品Planner selector分配Code target，组合原B03 reservation/prestart/dispatch/Pause/normal final/consume/release/checkpoint及fresh Analysis端口，实际Code与Analysis完成、Coordinator记录真实failure；源材料被保留的A05 projector拒绝`invalid_input:a05_material:audit_owner`。

原production `workspace.validate_tool_audit`的0.1闭合字段为`tool_event_index,task_id,workspace_id,tool_id,argv_digest,cwd,start_at,end_at,status,affected_paths,output_digest,resource_usage`。现有harness material kind `tool_audit`要求每行展开case/run/attempt/producer/workspace owner及`started_at/finished_at`，其合同级fixture与production wire不能混用。向真实audit添加字段会被原production schema拒绝，不能修audit bytes或用contract-shaped audit冒充执行。

原端口raw/normalized、owner及scope证据见`/private/tmp/lqcd-agent-b00c15-execution-20261007-elbi4nii/`的`code-source-True.json`、`canonical-audit-stop-result.json`。候选0.8分支曾通过，但scope复核确认新增来源profile须先批准，已从仓库交付撤回，保存在`canonical-audit-candidate-a05_trace.py`。两个独立真实Run的Code来源各自可验证；合并原材料时还复现`ordinary_trace:foreign_source`（`multi-owner-code-raw.json/result.json`），指出旧SHA单owner假设；这不是same-Run重试验收，也不计B04 owned，执行本票须另实跑same-Run owner共享场景。

## Read First

- [AGENTS](../../../AGENTS.md)、[docs](../../README.md)、[工作流](../README.md)、[模板](../TEMPLATE.md)、[安全策略](../../SECURITY_AND_DATA_POLICY.md)；
- [C15冻结票](B00C15_PRODUCT_FAILURE_FINGERPRINT_AND_GRANT_SOURCE_HANDOFF.md)、[执行记录](../completions/B00C15_COMPLETION.md)、[B04记录](../completions/B04_COMPLETION.md)与[maintenance](../corrections/B04_MAINTENANCE.md)；
- B03冻结票/completion、A05/A06/A07、Protocol/catalog；
- `code_agent/{workspace,schemas,artifacts,verification,analysis_handoff}.py`、`harness/{a05_trace,ordinary_trace,product_failure_trace,trace}.py`及C15原端口helper。

## Scope

- 仅0.8/proof0.5新增闭合`canonical_tool_audit` material profile；原material字段仍为`kind,sha256,content,owner`，proof顶层、failure/Grant声明不变，不增加runtime wire；
- 按真实Code bundle/task/manifest/producer绑定audit owner，复用原A05闭合validator及原bytes/sha/size/seal/result/audit关联；
- 新版本中逐owner证明相同raw内容的合法共享，保留注册/call/event occurrence关系，不以SHA覆盖owner；
- 必要被动collector、专用B00 meta/固定expected/四消费者及C15已批准当前Human入口的0.8交接，保留历史0.7 expected和所有原不变量；
- 当前输入回归及C15后续责任交接；不完成B04产品整票。

## Non-goals

- 不修改production、A05 schema、Code parent、预算primitive/算法/limits/reserve、Grant权限/目标/消费、Session、case/owner/分类；
- 不交付provider/backend、依赖或B05 adapter，不commit/push。

## Allowed Files

- `harness/{a05_trace,ordinary_trace,product_failure_trace,trace}.py`仅显式0.8 profile/来源owner解析；旧版本分支不变；
- `helpers/{control_traces,ordinary_sources,ordinary_maximum,ordinary_human,product_failure_sources,trace_sources}.py`仅实际来源的被动捕获、当前入口交接；
- 新`test_b00c16_canonical_code_audit_sources.py`、`test_b00c16_trace_consumers.py`、`fixtures/b00c16/`、`expected_traces/b00c16/`；C15专用tests/fixtures/expected只作原合同接线；
- C11 Human snapshot/consumer、C12 packet/consumer、C13 continuation/consumer及对应Human fixtures仅C15已批准0.8交接，保留nodeids/observe IDs/业务结果；新expected使用新路径，旧0.7原字节保持；
- `acceptance_matrix.json`仅B00 A07-META-006/015的上述meta；其他expected仅审定runtime fingerprint/派生head/reference，保存before/after raw和双fresh逐项差异；
- 本票YAML、新独立contract/completion、C15/B04 completion与maintenance追加、当前状态/Overview/索引和必要源文档/Decision Log。

## Do Not Touch

- `src/`、Phase A、冻结正文、旧sealed证据、旧0.1–0.7解释/拒绝、runtime wire、budget/authority、安全与科学接受；
- B00 schemas/catalog/cases/Session/failpoint判定/exclusion、B02/B03 owned语义/owner、legacy tests、依赖、configs、raw/outputs/accepted/secrets、外部系统与B05。

## Requirements

1. 新kind只由0.8选择，旧`tool_audit`仍走原规则；0.1–0.7拒绝新kind。canonical audit闭合字段完全等于原production0.1 schema，未知字段、混合两种dialect、错task/workspace/tool/argv/path/clock/usage均拒绝；不能仅改kind名称放行。
2. 每个owner exact为原`case_id,run_id,attempt_id,producer_operation_id,workspace_id`。由已注册Code bundle的validated task/manifest交叉证明，校验真实原文件raw sha/size、Code result/audit/seal和原producer journal，不从同SHA或latest current猜owner。原audit task_id/workspace_id必须指向该owner；有内容的audit仍不得跨task/workspace复用。
3. 新profile只规范原已验证`start_at/end_at`为clock事实；cwd/repo-relative paths、tool/argv、output digest及usage保持material，不扩大exclusion或掩盖任意路径/hex。科学FP recipe、B03原wire context、原A05 validator不改。
4. 每个Code audit/patch material declaration的binding key为`(kind,sha256,完整owner tuple)`，与实际注册材料关系set-equal；同owner重复、缺失/orphan/foreign/错类型拒绝。相同bytes可共享科学内容，所有owner关系分别保存。验证实际同Run不同Code Attempt的空audit/相同patch、同内容诊断或verification结果时，应由其原registration/call/producer分别绑定；不能覆盖SHA映射、任选owner或全局digest alias。若现有proof字段不足以证明，按Stop停止，不能自增字段。
5. ordinary/fingerprint科学内容跨owner共享也只在0.8按实际registration/call/failure head验证；保留每个decl的owner。上述两Run合并材料是补充反例，不能代替同Run occurrence和Code重试实跑。
6. collector只捕获原字节与fenced事实；不改effect、selector、state、ledger、返回或停止。用原产品selector与B03端口组合meta，仍不交付Code parent/B04 owned。
7. C15 scope补充仅限本票新profile/共享owner交接；C15其余固定字段、Grant阶段/权限、预算故障表及全部原验收继续由C15完成。C16未完成或C15未独立通过时两票/B04不自动恢复。

## Deliverables

- 闭合新profile和独立owner模型、被动collector及静态双fresh expected；
- 原端口before/after raw、具体owner/bytes/clock/派生差异与四消费者证据；
- 当前Human0.8影响清单、完整当前输入回归、独立补充contract/completion和C15交接。

## Acceptance Criteria

- 两fresh根重建实际产品Planner→原B03成功Code→trusted verification→fresh Analysis→Coordinator failure；0.8通过，旧0.7保留其原拒绝；effect/dispatch/consume/settlement各单次，重读无effect；
- 空audit、nonempty audit、actualsame-Run多Code Attempt/相同patch及诊断/结果内容共享保持不同owner；必要Run内failure occurrence和replan材料来源实跑，不能合并不同Run冒充；
- missing/duplicate/orphan/foreign/stale Session、错owner/epoch/task/workspace/argv/time/usage/path、未知profile/字段、篡改sha/bytes和伪造effect材料必须拒绝；合法科学材料变化改变normalized/context，已证明clock/locator变化按原规则；
- 当前Session collector/matrix/runtime validator/exit digest四路径实跑，新meta owner=B00且不计B04；C11/C12/C13原实际结果、Human packet不变、single-use、suffix/recovery不变量保持；
- current fresh construction15/11/30/28、同当前Session B02 1410/B03 645、完整exact collection/suite、final具体47/144/15通过，不skip/xfail/过滤；历史材料不retag当前Session；
- 131required/84mapped/47remaining、2199cases、324boundaries、28post-claim、B04 144cases、15exit及owners保持。C16完成后只解除其来源缺口，另审C15未完成项目；不直接恢复B04。

## Verification

批准执行后使用原Session/native、有界分批和construction CLI实跑，报告实际nodeids及具体ID集合：

```bash
/opt/anaconda3/bin/python -m pytest tests/phase_b/test_b00c16_canonical_code_audit_sources.py tests/phase_b/test_b00c16_trace_consumers.py -q
/opt/anaconda3/bin/python -m pytest tests/phase_b/test_b00c15_product_failure_sources.py tests/phase_b/test_b00c15_budget_publication.py -q
/opt/anaconda3/bin/python -m pytest --collect-only -q
```

Review阶段只检查模板、依赖、links、scope、冻结摘要及diff，不实施profile或更改完成状态。

## Stop Conditions

- 需要production、wire/proof字段、budget/authority、case/owner/exclusion或未列新profile；
- canonical owner只能凭SHA/latest猜测，必须伪造audit/selector/state/ledger/停止或覆盖旧expected语义；
- 来源共享只能覆盖owner/放宽原A05 trust，或旧版本解释/拒绝出现语义变化；
- 必须跳过/过滤/历史证据才能验收。触发即blocked，保存反例另审，不扩大本票。

## Required Documentation Updates

执行后新增独立contract/completion，追加C15/B04记录及current state/Overview/索引，按实际合同更新源文档/Decision Log；创建阶段只记录review入口与两票blocked事实，保留全部历史，不虚构批准、profile交付或Session通过。
