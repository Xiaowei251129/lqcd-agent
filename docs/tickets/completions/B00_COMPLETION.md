# B00 Completion Record

- Ticket：[B00 — Acceptance Foundation](../phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md)。
- Status：`completed`，2026-09-15；只完成B00 acceptance foundation，不表示Phase B完成。
- Commit：用户批准B00为ready后，在`f654f446640e52f94ffc2a9d41fb1c53775cb5b7`冻结。该提交保存此前Phase B草稿/规划修改和B00 ready metadata；执行后仅改B00 YAML lifecycle，正文与该commit byte-equal。实现修改尚未创建第二个commit，也没有push。
- Deviations：无批准边界变更；未修改Phase A冻结文件、旧runtime/tests、dependency、configs、evaluation或B01–B05正文。收尾核验的shared-node slice isolation局部修复见[B00 Maintenance](../corrections/B00_MAINTENANCE.md)，保持原合同与验收边界。

## Changed

- `src/lqcd_agent/control/{__init__,protocol,_generated_protocol}.py`：递归immutable machine projection与纯lookup；不读docs/test authority，不接入现有graph。
- `scripts/generate_phase_b_protocol.py`：exact bytes验证后确定性生成；`--check`重新渲染并逐字节比较。
- `scripts/validate_phase_b_acceptance.py`及`tests/phase_b/harness/`：strict JSON/closed schemas、owner partition、fixture/callable/path验证、exact trace、fresh subprocess evidence、输入摘要、closed report及统一final driver。
- `tests/phase_b/acceptance_matrix.json`、15项meta fixtures与expected trace：只包含15项B00 construction scenarios；不会用placeholder填入另外116项requirements。
- `tests/phase_b/failpoint_registry.json`、`final_obligations.json`与独立seals：324个边界、2286条final case，含7个entry phase × 4种stop/authority组合。适用性以frozen continuation policy及明确的拒绝/不确定副作用条件限制，不能授权redispatch或自动停止。
- `tests/phase_b/conftest.py`与三个test modules：collectable meta proofs、真实pytest子进程负向探针、隔离final adapters、strict schema/path/ownership/工作树与hook source tests。
- Docs Index、Architecture、Evals/Observability、Verification Guide、Current State、Decision Log、Phase B Overview及completion index同步foundation与runtime边界。

## Verified

执行前full-suite baseline：`RUN_LIVE_LLM_TESTS=0 pytest -q` → **325 passed**。

| Check | Result |
| --- | --- |
| Phase A validator | 131 requirements；101 semantic + 3 structural mutations；178 publication-order mutations；6 JSON/catalog negatives通过 |
| Generator `--check` | fresh render与tracked generated module byte-equal |
| Phase B collection/suite | 80 collectable tests；80 passed，无skip/xfail/deselect |
| Full deterministic pytest | 405 passed |
| Construction CLI | exit 0；owned/covered/passed exact为15个A07 meta IDs；global covered=15、remaining=116、passed=null |
| Real final negative probe | exit 1；exact 116 coverage gaps、2286 runtime case gaps、15 exit adapter gaps；没有parser、collection、evidence或internal errors |
| Compileall | src、tests与两个B00 scripts通过 |
| Governance | B00 frozen body、Phase A文件及B01–B05正文不变；无删除/重命名/越界改动；relative links、metadata、stale-doc与diff检查通过 |

最终fresh reports位于`/private/tmp/lqcd-agent-b00-verified-epS1Sy/construction-report.json`与`/private/tmp/lqcd-agent-b00-verified-epS1Sy/final-negative-report.json`，原始证据分别在同目录下的`construction/`与`final/`。这些是本地临时验证产物，不是tracked pass authority；未来验证须重新创建session。

Report本身保存当次`worktree_inputs`摘要；本记录不回写该摘要或report摘要，以避免“completion文档参与输入摘要、摘要又写回文档”的自引用。最终证据在本记录及lifecycle收尾后重新生成；原始token与临时路径不进入canonical report或normalized evidence digest。

### Exact acceptance inputs

| Input | SHA-256 |
| --- | --- |
| Control Protocol | `7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8` |
| Requirement catalog | `ed39a0b35feb3372e7647436ee588699c16b7c05555a03c791f69760626a9726` |
| Generated projection | `f6b51a1c5522e4ad4f01089683b4ef47685fecc9a1f0860f3a99db7d28d7ee8d` |
| Matrix | `3d2535a6449ff9cc3d92b1547235fc8484198474cc86d795b6ceaad03ebc9d0d` |
| Registry bytes | `2f60090a4483dba42a77f156148364f6971c07137a8c56c8032e13be4a83a133` |
| Final obligations bytes | `1349930274e5508065ac555ed6cfe41fa6a98c466f69b8dd76f60daaf8a76615` |

独立canonical inventory seal为`861b7030b96e08e28170a0d5130f9c39c5e505d4dcec1f9ecdfea794222866cb`，canonical final-obligations seal为`95b1e49b97e1d6379e3d12725b6b781f4c80e506384082df6e5317ced4d0f3c7`；前者排除后续可追加的hook/case binding，二者与上述raw bytes摘要用途不同。

## Evidence Boundaries and Follow-ups

- `requirements_zero_gap=false`、`phase_b_complete=false`。15项仅为B00 construction通过；META-006/015及其他相关requirements的完整final验收仍需实际production证据。
- 所有registry hooks为null、case bindings为空；真实final在preflight后停止。没有运行standalone full mock benchmark、B05 CLI smoke、live provider、Codex SDK或raw-data evaluation。Full pytest包含既有synthetic/legacy回归，但不替代B05独立exit evidence。
- Required pytest子进程负向测试实际覆盖skip、xfail、strict/non-strict XPASS、setup/teardown failure、deselect、unknown/duplicate result和stale token；测试用临时project，不产生真实project completion。
- 隔离final成功/失败测试覆盖131项已映射仍缺CLI/benchmark/legacy、missing hook/case/trigger、trace/outcome drift、不同worktree/contract/token、执行中输入变化、内部异常，以及benchmark退出0但case/checklist失败。成功时normalized report跨fresh tokens一致。
- META-009–015直接调用Phase A的独立语义检查及positive-control mutations，不以脚本exit code冒充runtime证明。后续生产hook须先证明实际触发，再联结恢复后case result、passing nodeid与exact trace。
- B01–B05保持`draft`，ownership仍为15/11/30/28/47且B05无owned slice。下一步仅审阅B01；runtime、hook bindings及B05真实exit adapters由相应ticket经批准后实现，不由本记录授权。
