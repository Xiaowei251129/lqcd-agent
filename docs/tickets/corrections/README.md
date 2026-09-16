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
