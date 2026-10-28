# Current state

Updated 2026-10-27. This is the current capability and qualification record; detailed historical evidence belongs in the linked maintenance records.

## Scope and implemented behavior

The system is an AI Research Partner for LQCD. Its current installed numerical programs are effective-mass estimation and matrix-element normalization checks; they are capabilities/examples, not the limit of the research vision. Software checks and synthetic calibration do not establish physics readiness.

- CLI, Python clients and the loopback demo share one canonical engine. The control plane owns progression, leases, budgets, authorization and immutable publication; LangGraph reads committed transitions. Protocol/state/execution schema remains `0.4`, artifact schema `0.1`.
- Planning, analysis, scientific review, deterministic coordination and Human Gate operate through scoped ports. Provider review shares Host numerical diagnostics and cannot erase warnings or lower the human-confirmation floor. Remediation/history is included in retained role context; oversized required context fails explicitly.
- Scientific starts freeze raw-data content identity, including absence. Analysis checks the exact consumed stream; replay/fork preserve the source identity. Read-only inspection verifies existing authority without executing agents. Terminal evidence archives are hash-bound, bounded and non-executing.
- Explicit live mode uses OpenAI Responses and the independent Codex SDK, with application-owned private credentials. Coding enables tools, task-authorized networking and SDK automatic review, while the Host retains final proposal/application/sealing/verification. Every observed SDK invocation, including an abandoned invocation confirmed stopped by the Host, is charged and audited.
- Four private C2/Normalization cases now assess independent Codex-written programs, without calculating through the original analysis package or changing its inputs. Measured values/references remain outside programming prompts. This case workbench is separate from the installed scientific registry and cannot advance a Run or accept physics results.
- Pure identities, lifecycle rules and artifact contracts are independent of orchestration/I/O. Unused output projections, auxiliary readers and compatibility helpers are removed. Control ownership, permissions, human confirmation and WAL/FULL durability remain unchanged.
- One generated hash lock covers runtime, development and build dependencies; all pre-maintenance runtime versions are preserved. CI keeps read-only permissions, narrow static checks, macOS integration and separate Linux source/build checks. Only detail-free CI outcomes are eligible for short retention.
- Runtime execution is qualified for native macOS, using the fixed canonical `/private/tmp` parent. Retired deployment profiles, configuration overrides and admission records are removed; other runtime platforms fail closed. Native local-filesystem, private-Host, boot/PID, WAL/FULL and human-confirmation checks remain in force.

## Current verification

Final native Mac integration passed **166 tests and all 9 numerical benchmark cases** in 282.45 seconds. Source digest remained unchanged: `f40be13c11659a9384e09824a342552b44fb162f55bcdcb290cf3a71991bc182`. Application build: `9853a555d508ec05671575418e5946ca76836976a5720b1dc6176b842c60b042`. Ruff, protocol/build projections, strict JSON, relative links, temporary-directory compilation and credential/ignore checks passed.

All **four research cases plus two synthetic calibrations** passed independent assessment: C2 window/model comparison and fixed-energy interpretation; paired complex normalization and physically missing references. C2's three checks took 108.46 seconds; Normalization's took 2.39 seconds, including local sandbox/interpreter overhead. These are local family-assessment timings, not service latency guarantees. All 14 original source files retain their extraction hashes. No physics result was accepted.

A corrected live C2 trial used 17 SDK tools, delivered verified Code and reached Human Gate. Earlier failed/canceled trials retain their original outcomes. Normalization's independent program is verified and numerically qualified, but its earlier generation Run remains failed after a control-progression defect; this is not a successful end-to-end Normalization Run. The defect is corrected and regression-tested. Detailed evidence and limits are in the [research-case maintenance record](maintenance/RESEARCH_CASES_CODEX.md); earlier qualification stays in the [original local record](maintenance/LOCAL_MACOS_QUALIFICATION.md).

Local detailed reports stay in ignored `check-results/` and owned scratch roots. CI outcome artifacts are produced on the CI runner. Reproduction commands and evidence semantics are in [Verification](VERIFICATION_GUIDE.md).

## Deployment qualification

| Environment | Evidence and boundary |
| --- | --- |
| Local MacBook / Python 3.12 | Native offline checks cover actual processes, SQLite settings, wheel installation and scientific Human Gate. |
| Local live checks | Prior Responses/synthetic checks passed; corrected C2 Codex generation/delivery reached Human Gate. Independent C2/Normalization numerical assessment passed. Neither result grants scientific acceptance. |
| GitHub macOS / Ubuntu | Historical baseline: both jobs passed for cleanup commit `a8081d1` in [remote CI](https://github.com/Xiaowei251129/lqcd-agent/actions/runs/40575964984). These jobs do not certify the current uncommitted case work. macOS runs full integration; Ubuntu performs static/numerical/build checks only. |

## Remaining work

General scientific-runtime integration and broader research-quality evaluation remain separate work. Human review must establish physical suitability, fit choices and original resampling correspondence; matching replica IDs alone cannot establish that provenance. Current case reports remain pending scientific review and have no Run-advancement authority.

Use [Architecture](ARCHITECTURE.md), [Data and security](SECURITY_AND_DATA_POLICY.md), and [Engineering decisions](DECISION_LOG.md) for the current contracts and rationale. Previous maintenance details remain in their original records and Git history rather than being repeated here.
