# B00C02 Completion Record

- Ticket：[B00C02 Semantic Trace Exit Binding](../phase-b-graph-harness/B00C02_SEMANTIC_TRACE_EXIT_BINDING.md)。
- Status：2026-09-16，用户批准ready后执行并完成。B00C01全部条件已复验通过，可关闭；B02前置阻塞解除、恢复`ready`，但其runtime和30项验收仍未完成。
- Commit：`10db77c735ae52aa1e0df947ff7c3a908185a4bc`，message为`docs: approve B00C02 semantic trace exit binding`。只提交本票ready快照；没有夹带既有未提交实现、没有push。实现与文档收尾保持未提交，供review。
- Scope：代码只改`tests/phase_b/harness/exit_checks.py:normalized_pytest`两处调用；测试只扩充`test_source_bound_traces.py`已有隔离subprocess场景。其余仅为本票Allowed Files内的状态、验证和历史追加说明。
- Deviations：无。没有新增schema、依赖、owner、scenario、slice或runtime功能。

## Fix and Proof

先扩充真实subprocess回归，确认`validate_exit → normalized_pytest → normalize`路径在修复前失败于`invalid_evidence:trace_binding:trusted_session_required`，而不是只调用codec制造诊断。

修复为observations和case_results的`normalize(row["trace"], binding=value)`。`value`是退出检查已经通过父Session、raw artifact checksum、pytest node和适用scenario验证的envelope；不是proof自己声明的binding。校验顺序、原始source checks、trace0.1语义和固定退出清单不变。

同一回归执行两次独立fresh pytest invocation，使用不同token与physical Run root，经真实writer、父validator、runtime-case比较及`validate_exit`生成相同semantic evidence digest。直接检查规范化bytes不包含proof、token或实际临时路径。

对observations和case_results分别注入旧token、每个错误worktree/contract digest及source tamper；重新计算外层文件SHA后仍由proof验证拒绝。另将pytest envelope和内部proof一致改成旧token/摘要，确认父Session仍拒绝，不能靠内部自洽获得授权。现有旧trace、benchmark假通过及final错误分类回归保持通过。

## Verification

- 修复前单项回归：1 failed，错误为上述missing trusted binding；修复后相关source-bound、final/exit及B02诊断测试：**74 passed**。
- `RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b/test_source_bound_traces.py`：**46 passed**。
- `RUN_LIVE_LLM_TESTS=0 pytest -q tests/phase_b`：**174 passed**。
- `RUN_LIVE_LLM_TESTS=0 pytest -q`：**499 passed**。
- Phase A validator：131 required、101 semantic + 3 structural mutations、178 publication-order及6项JSON/catalog检查通过。
- Generated protocol `--check`：byte-equal；`compileall`通过，bytecode位于`/private/tmp/lqcd-agent-b00c02-LZvk0k/pycache`。
- Fresh B00/B01 construction：**15/15、11/11**；全局26 covered、105 remaining、passed=null，两完成标志false。
- Fresh final：按预期非零，错误分类exact为105 coverage、2286 runtime、15 exit缺口，无parser、collection、invalid-evidence或internal error，两完成标志false。

证据根目录：`/private/tmp/lqcd-agent-b00c02-LZvk0k/`。`*-preflight-report.json`属于文档收尾前的输入；收尾后重新生成`b00-report.json`、`b01-report.json`和`final-report.json`并核对当前worktree摘要。实际项目仍缺runtime和B05 exit adapters，隔离退出检查通过不等于Phase B final通过。

## Governance and Preservation

B00C01/B00C02/B02正文与各自ready快照一致，只更新YAML lifecycle。C01及B02历史记录只追加本次关闭/解除阻塞事实；原停止结论保留为当时事实。Phase A、generated module、matrix、registry/final obligations/seals、固定fixtures、src（包括既有B02 WIP）及B03–B05均未被本轮改变。Markdown links、scope、ownership及`git diff --check`复核通过。

本次实际冻结命令：

```bash
git add -- docs/tickets/phase-b-graph-harness/B00C02_SEMANTIC_TRACE_EXIT_BINDING.md
git diff --cached --check
git diff --cached --stat
git commit -m "docs: approve B00C02 semantic trace exit binding"
```

## Follow-ups

B02可以按原冻结票继续实现完整control接口、可信bootstrap、Pause/Resume、child saga、lease/capability及真实process-restart/concurrency验收。本corrective只解除验收前置阻塞，不实施这些runtime，也不将B02标记completed。B03–B05仍draft。
