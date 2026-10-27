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
- Runtime execution is qualified for native macOS, using the fixed canonical `/private/tmp` parent. Retired deployment profiles, configuration overrides and admission records are removed; other runtime platforms fail closed. Native local-filesystem, private-Host, boot/PID, WAL/FULL and human-confirmation checks remain in force.

## Current verification

Final native Mac integration passed **144 tests and all 9 numerical benchmark cases** in 255.70 seconds. Source digest remained unchanged: `a64a78720526b7da74ff129fac6ed586df8103ed6639912e48319b9ae16f42fd`. Application build: `a1d99fcd9324e711bb3c90626bba8ca419d117f59fbfc9944670654b36646673`. Native doctor and the explicitly authorized live coding and synthetic scientific checks also passed. Scientific acceptance remains pending at Human Gate. Detailed local evidence is in the [qualification record](maintenance/LOCAL_MACOS_QUALIFICATION.md).

Local detailed reports stay in ignored `check-results/` and owned scratch roots. CI outcome artifacts are produced on the CI runner. Reproduction commands and evidence semantics are in [Verification](VERIFICATION_GUIDE.md).

## Deployment qualification

| Environment | Evidence and boundary |
| --- | --- |
| Local MacBook / Python 3.12 | Native offline checks cover actual processes, SQLite settings, wheel installation and scientific Human Gate. |
| Current local live checks | Bounded Codex proposal/application/verification and Responses planning/review passed on synthetic examples with `gpt-6-luna`. Read-only status and idempotent Resume passed; scientific Human Gate remains pending. |
| GitHub macOS / Ubuntu | The previous HEAD's workflow failed before starting any job. Its job-level `runner` context was moved to step-level environment configuration and regression-checked locally; a new remote run awaits push. Ubuntu performs static/numerical/build checks only. |

## Remaining work

Push the current changes and verify the updated remote CI. General scientific code execution and research-quality evaluation remain separate work; human scientific acceptance is still required.

Use [Architecture](ARCHITECTURE.md), [Data and security](SECURITY_AND_DATA_POLICY.md), and [Engineering decisions](DECISION_LOG.md) for the current contracts and rationale. Previous maintenance details remain in their original records and Git history rather than being repeated here.
