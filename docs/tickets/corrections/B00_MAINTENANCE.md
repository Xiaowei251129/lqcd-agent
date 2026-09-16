# B00 Maintenance Record

## 2026-09-15 — Preserve shared-node slice isolation

- Ticket：[B00 Acceptance Foundation](../phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md)；执行基线`f654f44`。
- 问题：收尾核验发现，matrix合同允许不同slice/stage复用pytest nodeid，但初版observation validator只认可本次selected scenarios。Shared node同时记录另一个合法scenario时，会被误判为unknown evidence，影响后续B01–B05接入。
- 根因：把“允许出现的已知scenario”和“本次可以计入通过数的selected scenario”用了同一个集合。
- 修复：driver把已验证matrix的known scenarios一并传给observation validator；known但未selected的记录不计入当前slice。Selected记录仍必须完整、唯一、typed result/invariants/trace exact匹配；未知或重复记录仍拒绝，global passed保持null。B00 meta proofs也只隔离自己的construction slice，不要求未来project matrix永远只有B00或registry永远没有bindings。
- 回归：`test_meta_003`新增shared-node隔离与unknown拒绝，原15项ownership与counts不变；focused suite为80 passed，full suite为405 passed。Construction仍15/15、global remaining=116；真实final仍只报告116/2286/15三类预期缺口。
- 范围：只修改B00新建test-owned validator/meta tests及本票记录；没有改变matrix/report/evidence schema、public contract、Allowed Files、验收边界、Phase A bytes或B01–B05正文，无需新的corrective ticket。

## 2026-09-15 — Canonical ownership ordering

- Ticket：[B00 Acceptance Foundation](../phase-b-graph-harness/B00_ACCEPTANCE_FOUNDATION.md)；用户批准本次contract-preserving maintenance，不重新执行B00或改写冻结正文。
- 问题：审阅B01时发现合法slice无法接入。`strings()`要求`owned_requirement_ids`按字典序排列，matrix又要求与按合同展示顺序保存的`OWNED[tid]`列表相等；B01两种排序都在scenario校验前被拒绝。
- 修复：matrix只将expected ownership改为`sorted(OWNED[tid])`；输入仍必须canonical ordered，`OWNED`集合、slice依赖顺序、global report的catalog顺序及所有strict拒绝条件不变。没有修改schema、public contract、验收边界或frozen inventory，无需corrective ticket。
- 永久回归：增加5个合法slice前缀、6类ownership mutation和4类slice顺序/资格mutation，共15项测试；每个负向测试先证明未变异副本有效。所有副本只含B00 construction scenarios，增加B01–B04 slices后coverage仍为15、remaining仍为116，不向真实matrix写入未来slice、scenario或passing evidence。既有错误owner用例改用canonical输入，以免仅由排序检查拒绝。
- Red/green：修复前新增prefix回归为1 passed、4 failed，失败均定位`B01:owned_requirement_ids`；修复后专项回归16 passed，Phase B suite **95 passed**，完整deterministic suite **420 passed**，本轮修改前full-suite baseline为405 passed。
- 验收：Phase A validator确认131 requirements、101 semantic + 3 structural、178 publication-order及6 JSON/catalog mutations；generated protocol byte-equal、compileall、links和diff检查通过。Fresh B00 construction为15/15；真实final非零，只有116 coverage、2286 runtime和15 exit预期缺口，global passed为null，`requirements_zero_gap=false`、`phase_b_complete=false`。文档收尾后重新生成fresh evidence，避免复用修改前的worktree摘要。
- 治理：Phase A bytes、B00冻结正文及completion、旧maintenance条目、B02–B05、真实matrix/registry/final obligations/seals保持不变；没有runtime/API/schema改动，不commit/push。Current State追加当前维护结果，原始80/405测试结果保留为历史事实，现有corrections索引链接不重复添加。
- 同轮草稿：用户另行批准修订[B01](../phase-b-graph-harness/B01_EXECUTION_0_4_CONTROL_FOUNDATION.md)，区分generated与冻结prose-only静态定义的来源，保留clock/只读validator边界，并移除B01 durable hook交付/写权限。该草稿修订不由B00维护授权执行B01；B01仍为`draft`，ownership与依赖不变。
