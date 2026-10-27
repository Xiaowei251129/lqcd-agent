# Current state

Updated 2026-10-27. This is the current capability and qualification record; detailed historical evidence belongs in the linked maintenance records.

## Scope and implemented behavior

The system is an AI Research Partner for LQCD. Its current installed numerical programs are effective-mass estimation and matrix-element normalization checks; they are capabilities/examples, not the limit of the research vision. Software checks and synthetic calibration do not establish physics readiness.

- CLI, Python clients and the loopback demo share one canonical engine. The control plane owns progression, leases, budgets, authorization and immutable publication; LangGraph reads committed transitions. Protocol/state/execution schema remains `0.4`, artifact schema `0.1`.
- Planning, analysis, scientific review, deterministic coordination and Human Gate operate through scoped ports. Provider review shares Host numerical diagnostics and cannot erase warnings or lower the human-confirmation floor. Remediation/history is included in retained role context; oversized required context fails explicitly.
- Scientific starts freeze raw-data content identity, including absence. Analysis checks the exact consumed stream; replay/fork preserve the source identity. Read-only inspection verifies existing authority without executing agents. Terminal evidence archives are hash-bound, bounded and non-executing.
- Explicit live mode uses OpenAI Responses and the independent Codex SDK, with application-owned private credentials. Live coding remains bounded file proposal/application/sealing/verification. Missing general scientific implementations require a scoped implementation decision.
- Pure identities, lifecycle rules and artifact contracts are independent of orchestration/I/O. Unused output projections, auxiliary readers and compatibility helpers are removed. Control ownership, permissions, human confirmation and WAL/FULL durability remain unchanged.
- One generated hash lock covers runtime, development and build dependencies; all pre-maintenance runtime versions are preserved. CI keeps read-only permissions, narrow static checks, macOS integration and separate Linux source/build checks. Only detail-free CI outcomes are eligible for short retention.

## Current verification

Final integration passed **153 tests and all 9 numerical benchmark cases** in 226.49 seconds. Source digest remained unchanged: `d0bf63c08d1fb5e7ecffd34d76e8ef9e6540ad26ecc183acb55b71ae64c78ff2`. Application build: `ff3bcde8480b6b8f612a7a901172fd3b30fb247743cea909512f176eaaeef270`. The earlier staged selections passed 19 and 33 affected tests. Audit and performance details are in the [maintenance record](maintenance/GOVERNANCE_AND_CONTRACT_BOUNDARIES.md).

Local detailed reports stay in ignored `check-results/` and owned scratch roots. CI outcome artifacts are produced on the CI runner. Reproduction commands and evidence semantics are in [Verification](VERIFICATION_GUIDE.md).

## Deployment qualification

| Environment | Evidence and boundary |
| --- | --- |
| Local macOS / Python 3.12 | Native offline checks cover actual processes, SQLite settings, wheel installation and scientific Human Gate. |
| Earlier local live checks | Bounded coding and registered-program scientific checks passed for an earlier build; not repeated for this build. See [local qualification](maintenance/LOCAL_MACOS_QUALIFICATION.md). |
| GitHub macOS / Ubuntu | Workflow configured; remote execution for this build is not yet verified. Ubuntu performs static/numerical/build checks, not application storage admission. |
| OLCF | Earlier bounded SDK qualification remains scoped to its original build. Native storage/process qualification and a full suite have not been repeated here. User-namespace restrictions still prevent arbitrary command sandbox execution. |

## Remaining work

Run the updated remote CI and explicitly authorized live qualification for the resulting build. Repeat OLCF admission and native checks on the actual approved Lustre Host before claiming deployment qualification. General scientific code execution and research-quality evaluation remain separate work; human scientific acceptance is still required.

Use [Architecture](ARCHITECTURE.md), [Data and security](SECURITY_AND_DATA_POLICY.md), and [Engineering decisions](DECISION_LOG.md) for the current contracts and rationale. Previous maintenance details remain in their original records and Git history rather than being repeated here.
