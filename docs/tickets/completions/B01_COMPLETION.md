# B01 Completion Record

- Ticket：[B01 — Execution 0.4 Control Foundation](../phase-b-graph-harness/B01_EXECUTION_0_4_CONTROL_FOUNDATION.md)。
- Status：`completed`，2026-09-16；仅为pure control foundation，不表示durable operations或Phase B完成。
- Commit：用户批准ready后，以`537d10ceda203fdea5c20266f994a20641cfc5ab`冻结。本次唯一commit保存此前B00实现/maintenance、B01 ready及相关规划文档；执行后只修改B01 YAML lifecycle，正文byte-equal。B01实现保留未提交供review，没有push。
- Deviations：无批准边界变更。没有改写Phase A、B00历史、B02–B05正文、registry/final obligations/seals、既有tests、dependencies、graph routes、provider/config或existing Runs。未发现需修复的前置实现缺陷，因此没有新增maintenance/corrective record。

## Changed

- `control/strict_json.py`：duplicate-key/closed/canonical JSON、numeric/scalar检查、typed integrity error和immutable byte snapshots。
- `control/records.py`、`execution.py`：0.4 record union/build/parse、连续global event head、纯append bytes与Run/Attempt/Human lifecycle replay；复用A02 identity和A03生命周期/index validators，不提供writer或public mutation。
- `control/budget.py`：冻结profiles、canonical policy、typed unknown usage、semantic context/fingerprint及budget event validation；ledger replay派生usage、conservative unsettled charge、occurrence、grant和bounded decision facts，不负责admission或外部settlement授权。
- `control/clock.py`：Host/Fake port、wall/monotonic校验；Host setup仅Run、Backend直到result和seal完成同时计Run/Attempt、被动等待零active、Attempt/verification同时计时。计量不改变Attempt lifecycle。
- `control/projections.py`、`integrity.py`：bounded projection、无自引用checkpoint manifest、显式Run root只读校验；复用A03完整双向registry规则，没有新的preflight例外、repair或parallel authority。
- `graph/state.py`：仅新增显式0.4 control projection Agent-output guard；原0.2 initializer/wrapper行为未改。`control/__init__.py`同步module边界说明。
- `tests/phase_b/`：追加canonical B01 owned slice、11项construction scenarios/fixtures、4份exact traces及25项foundation tests；未修改B00 meta infrastructure或future slices。
- Architecture、State Schema、Artifact Contracts、Evals、Verification Guide、Docs Index、Current State、Decision Log、Phase B Overview及completion index同步当前事实。

## Verified

执行前fresh baseline：full pytest **420 passed**；B00 construction **15/15**；真实final只有**116 coverage / 2286 runtime / 15 exit**缺口。证据在`/private/tmp/lqcd-agent-b01-execution-ji57iV/baseline-construction.json`和`baseline-final.json`。

| Check | Result |
| --- | --- |
| Phase A validator | 131 requirements；101 semantic + 3 structural、178 publication-order、6 JSON/catalog mutations通过 |
| Generated protocol `--check` | byte-equal |
| B01 foundation | 25 passed |
| Phase B collection/suite | 120 collectable；120 passed，无skip/xfail/deselect |
| A02/A03 focused | 139 passed；既有tests未改 |
| Full deterministic pytest | 445 passed，`RUN_LIVE_LLM_TESTS=0` |
| B00 fresh construction | owned/covered/passed exact 15/15；global 26 covered / 105 remaining |
| B01 fresh construction | exit 0；owned/covered/passed exact 11/11；global 26 covered / 105 remaining，passed/passed_ids null |
| Real final negative | exit 1；exact 105 coverage、2286 runtime、15 exit gaps；无额外解析/collection/evidence/internal error |
| Compileall / diff | src、tests及B00 scripts通过；`git diff --check`通过 |
| Governance | 冻结bytes、ticket body、ownership/dependency、Allowed Files、Markdown links、stale-doc及无删除/重命名检查通过 |

最终fresh reports在`/private/tmp/lqcd-agent-b01-execution-ji57iV/`下的`b00-construction-release.json`、`construction-release.json`和`final-release.json`；对应evidence目录为`b00-construction-release/`、`construction-release/`、`final-release/`。这些临时文件不是tracked pass authority，未来必须重新验证。

最终报告在本记录及lifecycle收尾后生成；不将worktree/report摘要写回参与摘要的文档，避免自引用。报告和raw evidence分别保留本次input digest与invocation token绑定；canonical报告不含不稳定token或临时路径。

## Construction Evidence Boundaries

- Required tests调用production serializers/replay/validators，不以手写expected dict自报pass；exact traces保留record order、identity、head、policy/fingerprint、clock classification和typed failure。Trace不声称纯clock probe启动了Attempt。
- Negative cases覆盖非法版本/duplicate/unknown/missing/wrong scalar、identity gap/parent/cross-Run、重复start/terminal、domain/control正交、nonterminal null target、部分bootstrap/checkpoint、旧bounded head、nullable omission、policy/reservation/grant/fingerprint tamper与unknown usage。收尾补充`initializing -> failed`在policy/admission尚未写入时的纯lifecycle正例，避免成功bootstrap顺序误挡冻结失败边；同一Human budget-window response不能签发第二个grant。
- 真实A03注册的nonempty artifact由0.4适配器验证；协调修改producer/target并重算history/index/state/checkpoint摘要仍被语义检查拒绝。验证前后输入bytes保持不变。A03C01未承诺的任意全历史协调重写密码学检测不在本票中添加。
- `ExecutionReplay`接受可校验的纯publication prefix，但不返回durable恢复或执行许可。Stable-root检查再要求A03反向closure及checkpoint exact pair。Checkpoint manifest不替代B02 checkpointer/ownership proof；合法Run edge不替代Pause record、claim或capability。
- `requirements_zero_gap=false`、`phase_b_complete=false`。全部B01 scenarios为construction；registry、final obligations及seals未改，未绑定hook，2286 runtime cases和15 exit checks仍缺证据。
- 未运行live provider、Codex SDK、standalone benchmark、B05 CLI smoke或历史outputs；full pytest内既有synthetic/legacy回归不替代B05独立exit evidence。

## Git Commands

批准冻结前先检查`git status --short`、diff和摘要，再按明确路径暂存；没有使用`git add .`：

```bash
git add -- docs/ARCHITECTURE.md docs/DECISION_LOG.md \
  docs/EVALS_AND_OBSERVABILITY.md docs/README.md docs/REPO_CURRENT_STATE.md \
  docs/VERIFICATION_GUIDE.md docs/tickets/completions/README.md \
  docs/tickets/completions/B00_COMPLETION.md docs/tickets/corrections/README.md \
  docs/tickets/corrections/B00_MAINTENANCE.md \
  docs/tickets/phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md \
  docs/tickets/phase-b-graph-harness/B01_EXECUTION_0_4_CONTROL_FOUNDATION.md \
  docs/tickets/phase-b-graph-harness/OVERVIEW.md \
  scripts/generate_phase_b_protocol.py scripts/validate_phase_b_acceptance.py \
  src/lqcd_agent/control tests/phase_b
git diff --cached --check
git diff --cached --stat
git commit -m "feat: complete B00 acceptance foundation and freeze B01 ready"
git show --stat --oneline HEAD
```

这是执行前的实际提交命令记录，不是要求现在再次暂存/提交B01实现。`--cached`检查暂存区，`commit`保存本地快照，`show`核对该快照；没有执行`git push`。

## Follow-ups

- B02：独立review/批准后实现trusted bootstrap admission、coordinator/ControlOperation、Pause、source proof及durable publication；不能把builder、`allow`字符串或construction pass作为权限。
- B03：接入外部Backend/clock/resource evidence与实际hooks；B04：后续route/resource/grant/stop enforcement。对应final scenarios仍保留原requirement owner。
- B05：真实exit adapters和跨系统final证明；B02–B05仍为draft，不因本票完成自动取得执行授权。
