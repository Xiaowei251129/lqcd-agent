# Ticket Corrections and Maintenance Records

本目录保存冻结ticket执行后发现的问题。

- 不改变合同边界的局部修复可以写maintenance record；
- 改变schema、架构、public contract、Allowed Files、恢复策略或验收边界时，必须创建新的ready corrective ticket；
- correction record只描述问题、根因、改动、验证和关联ticket，不修改原ticket；
- 2026-08-22治理规则生效前已经完成但没有独立ticket的纠偏，必须标记为historical/retroactive，不得伪称当时存在冻结corrective ticket。

当前记录：

- [`A07 Security Status Maintenance`](A07_SECURITY_STATUS_MAINTENANCE.md)
- [`A02 Human Gate Commit-order Clarification`](A02_HUMAN_GATE_COMMIT_ORDER_CLARIFICATION.md)
- [`A03 Transition Publication-order Clarification`](A03_TRANSITION_PUBLICATION_ORDER_CLARIFICATION.md)
- [`A03_LEGACY_CORRECTIVE_HISTORY.md`](A03_LEGACY_CORRECTIVE_HISTORY.md)

已完成的独立corrective ticket：

- [`A03C01 Execution Head Integrity`](../phase-a-control-contracts/A03C01_EXECUTION_HEAD_INTEGRITY.md)

本轮新增maintenance：

- [`B00 Shared-node Slice Isolation`](B00_MAINTENANCE.md)

执行中或待批准的独立corrective：

- [`B00C01 Source-bound Semantic Traces`](../phase-b-graph-harness/B00C01_SOURCE_BOUND_SEMANTIC_TRACES.md)：`blocked`，见[执行记录](../completions/B00C01_COMPLETION.md)。
- [`B00C02 Semantic Trace Exit Binding`](../phase-b-graph-harness/B00C02_SEMANTIC_TRACE_EXIT_BINDING.md)：`draft`，仅提出遗漏调用文件的最小追加范围，尚未批准执行。

2026-09-16后续关闭：上述B00C01/B00C02已完成；旧条目保留为当时状态。B00C02独立批准后补齐exit binding并通过完整复验，B02解除该前置阻塞、恢复ready但未完成runtime。见[B00C02完成记录](../completions/B00C02_COMPLETION.md)。

- 2026-09-16 resumed B02 maintenance: [`B02 frozen bootstrap action validation`](B02_MAINTENANCE.md).

- 2026-09-18：[B02可执行性审查](B02_EXECUTABILITY_REVIEW.md)核对合同缺口、旧格式reader、external控制与验收接线；[B02C01 Legacy Source Fingerprint](../phase-b-graph-harness/B02C01_LEGACY_SOURCE_FINGERPRINT.md)为`review`草案，待用户批准，未改变当前合同或完成B02。

- 2026-09-18后续：用户批准B02C01并在`5e753d6`冻结ready；实施状态见[B02C01执行记录](../completions/B02C01_COMPLETION.md)。前述review条目保留为审查时事实。

- 2026-09-18：[B00C03 historical Fork trace proposal](../phase-b-graph-harness/B00C03_HISTORICAL_FORK_SOURCE_TRACES.md)（`review`、未批准/未实施）：真实0.3来源Fork可运行，但冻结trace 0.2无法验证其历史head；三种拒绝及本轮已修复的read-only/terminal竞争问题见[B02 maintenance](B02_MAINTENANCE.md)。B02暂停于该前置验收边界。

- 2026-09-21：[B00C04 reservation fault-case proposal](../phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)为review、未实施；真实COMMIT前完整回滚缺少对应独立outcome，B02暂停于冻结验收范围。复现与本轮修复见[B02 maintenance](B02_MAINTENANCE.md#2026-09-21--reservation-fault-case-executability-audit)。

- [B00C04](../phase-b-graph-harness/B00C04_RESERVATION_FAULT_CASE_SEMANTICS.md)已按用户统一计划扩充并冻结，case0.2/trace0.4/进程证据修正in_progress；B02运行修复仍归原maintenance。

2026-09-21：[B02 maintenance](B02_MAINTENANCE.md)已追加本轮lease、Pause/external/Human失败收尾、close重试和只读Resume准入修复的验证结果；C04验收前置与原B02运行范围分别闭合。

- 2026-09-22：[B00–B02完成核验与B03–B05草案审查](B00_B05_READINESS_REVIEW.md)：复核前置交付与验收输入一致性；修订后续draft的owner/失败分类、B03预留责任、trace基线及分批验收范围，保持未批准执行。

- 2026-09-24：[B03 resource transaction maintenance](B03_MAINTENANCE.md)：原 resume 的独立 verification reservation/settlement、事务外 consumer、双重 fence 与失败 snapshot 接线；B03 仍执行中。
