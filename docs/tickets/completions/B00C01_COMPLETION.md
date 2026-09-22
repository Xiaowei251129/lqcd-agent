# B00C01 Execution Record — Blocked, Not Completed

- Ticket：[B00C01](../phase-b-graph-harness/B00C01_SOURCE_BOUND_SEMANTIC_TRACES.md)。
- Status：2026-09-16，用户“批准修改”后开始执行；因冻结Allowed Files漏列一个必要调用文件，现为`blocked`，不表示验收完成。
- Commit：`d9af4e88be16ed85f1fa00a60a3d9e135f6a292e`仅冻结B00C01 ready正文，message为`docs: approve B00C01 source-bound semantic trace correction`；没有夹带既有B02改动，没有push。实现仍未提交。
- Preserved：Phase A、generated projection、B00/B01正文、B02正文与WIP runtime、B03–B05、registry/final obligations/seals及历史记录不变。B02仍blocked，没有启动剩余runtime实现。

## Implemented but Not Yet Complete

新增closed trace `0.2/raw_with_proof`与固定`semantic_expected`，旧`0.1`保持原义。Raw source先检查canonical hash、明确引用、execution replay、checkpoint manifest/state关联、Run/root及本次session绑定，再计算带版本和类型标记的semantic digest。仅投影已经验证的Execution绝对clock和Run root下完整路径；identity、owner、phase、route、budget和material内容仍参与exact comparison。

实现位于`tests/phase_b/harness/trace_proof.py`，并接入trace codec、matrix fixture、pytest writer/父validator及runtime case comparison。新增固定fixture、source helper和46项source-bound tests；B02原trace缺口诊断保留，追加1项新路径回归。这些均为验收基础测试，不证明durable checkpoint、Code Agent或B02的30项requirements。

Matrix仅为原B00 owner新增`B00-TRACE-001/002`两个construction scenarios，复用META-005/004；原scenario和slice保持不变，仍只有B00/B01，总ownership与coverage未增加。

## Stop Condition: Omitted Exit Call Site

`tests/phase_b/harness/exit_checks.py:normalized_pytest`在两类trace列表中仍调用`normalize(trace)`而不传binding。新版trace必须拒绝无可信会话绑定，因此合法proof也会在这里得到：

```text
invalid_evidence:trace_binding:trusted_session_required
```

已用`fresh_trace()`先完成带binding验证，再调用`normalized_pytest`复现。`validate_exit`虽先验证过raw evidence，该摘要调用仍需显式传入其envelope；不能改为接受trace自报binding，也不能直接删除raw校验。

该文件未列入B00C01 Allowed Files，是本轮冻结范围时遗漏的必要接线，不是B02 runtime缺少新功能。按Stop Conditions停止，没有改该文件或回写B00C01正文。仅提出独立[B00C02草稿](../phase-b-graph-harness/B00C02_SEMANTIC_TRACE_EXIT_BINDING.md)请求追加授权；草稿不是已批准实现，B00C01/B02都未解除阻塞。

## Verification Actually Run

- Source-bound与B02诊断文件：**48 passed**。
- Phase B：**174 passed**。
- 完整`RUN_LIVE_LLM_TESTS=0 pytest -q`：**499 passed**。
- Phase A validator：131 required、101 semantic + 3 structural mutations、178 publication-order及6项JSON/catalog检查通过。
- Generated protocol `--check`：byte-equal。
- `compileall`：通过；bytecode输出到`/private/tmp/lqcd-agent-b00c01-review-tjfmm4/pycache`。
- Fresh B00/B01 construction：**15/15、11/11**，coverage26、remaining105、global passed=null；两个完成标志false。
- Fresh final：非零，仅105 coverage、2286 runtime、15 exit缺口；两个完成标志false。该preflight不会执行未接入的exit adapters，因此不能发现或消除上述完整exit调用缺口。

证据目录为`/private/tmp/lqcd-agent-b00c01-review-tjfmm4/`。`*-preflight-report.json`记录文档收尾前的输入；文档收尾后重新生成`b00-report.json`、`b01-report.json`和`final-report.json`，不得跨工作树复用前者。

## Next Authorized Boundary

需要用户独立批准B00C02，补齐两处binding传递及真实`validate_exit`正/负向回归，然后重新核验B00C01全部条件。只有那时才能追加解除阻塞事实、完成B00C01并恢复原冻结B02；不能将当前499项测试通过解释为B00C01或B02完成。

## 2026-09-16 Addendum — Completed After B00C02

用户已独立批准B00C02，并以`10db77c`冻结其ready快照。B00C02补齐exit normalizer两处显式binding，真实`validate_exit`双fresh invocation及stale/tamper回归通过；source-bound 46 passed、相关74 passed、Phase B 174 passed、full suite 499 passed。Phase A、generator、compileall及治理检查通过；fresh B00/B01仍15/15和11/11，final只含105/2286/15预期缺口。

B00C01原验收条件至此全部复验完成，YAML改为completed；上文标题与blocked结论保留为此前停止时的事实，不代表最新状态。详见[B00C02完成记录](B00C02_COMPLETION.md)及`/private/tmp/lqcd-agent-b00c02-LZvk0k/`新证据。B02解除该前置阻塞、恢复ready；本次没有新增B02 runtime或其required passing coverage。
