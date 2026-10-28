# Current state

Updated 2026-10-28. This is the current capability and qualification record; detailed historical evidence belongs in the linked maintenance records.

## Scope and implemented behavior

The system is an AI Research Partner for LQCD. Its current installed numerical programs are effective-mass estimation and matrix-element normalization checks; they are capabilities/examples, not the limit of the research vision. Software checks and synthetic calibration do not establish physics readiness.

- CLI, Python clients and the loopback demo share one canonical engine. The control plane owns progression, leases, budgets, authorization and immutable publication; LangGraph reads committed transitions. Protocol/state/execution schema remains `0.4`, artifact schema `0.1`.
- Planning, analysis, scientific review, deterministic coordination and Human Gate operate through scoped ports. Provider review shares Host numerical diagnostics and cannot erase warnings or lower the human-confirmation floor. Remediation/history is included in retained role context; oversized required context fails explicitly.
- Scientific starts freeze raw CSV/JSON content identity, including absence. Analysis checks the exact consumed stream; replay/fork preserve the source identity. Read-only inspection verifies existing authority without executing agents. Terminal evidence archives are hash-bound, bounded and non-executing.
- Explicit live mode uses OpenAI Responses and the independent Codex SDK, with application-owned private credentials. Coding enables tools, task-authorized networking and SDK automatic review, while the Host retains final proposal/application/sealing/verification. Every observed SDK invocation, including an abandoned invocation confirmed stopped by the Host, is charged and audited.
- Explicit generated-program cases now connect the real scientific Planner → Codex → Analysis Engineer → Scientific Reviewer → Human Gate through the normal scientific entry. Fresh preparation binds Plan/Code, JSON input, disjoint parameters and numerical environment. Analysis publishes actual calculation output through its existing writer. Generated programs stay Run-local and are not automatically installed in the registry.
- Four private C2/Normalization cases assess independent Codex-written programs, without calculating through the original analysis package or changing its inputs. Measured arrays and withheld references remain outside programming prompts. Canonical Reviewer receives aggregate Host diagnostics; independent hidden calibration/reference assessment remains a separate consumer without Run-advancement or scientific-acceptance authority.
- Pure identities, lifecycle rules and artifact contracts are independent of orchestration/I/O. Unused output projections, auxiliary readers and compatibility helpers are removed. Control ownership, permissions, human confirmation and WAL/FULL durability remain unchanged.
- One generated hash lock covers runtime, development and build dependencies; all pre-maintenance runtime versions are preserved. CI keeps read-only permissions, narrow static checks, macOS integration and separate Linux source/build checks. Only detail-free CI outcomes are eligible for short retention.
- Runtime execution is qualified for native macOS, using the fixed canonical `/private/tmp` parent. Retired deployment profiles, configuration overrides and admission records are removed; other runtime platforms fail closed. Native local-filesystem, private-Host, boot/PID, WAL/FULL and human-confirmation checks remain in force.

## Current verification

Local native Mac qualification passed **181 tests and all 9 numerical benchmark cases** in 386.69 seconds. Source digest remained unchanged: `7448e101fa8044a17e3dd56496fd71852d375402f73e3d8d753aa16992855a71`. Application build: `4789add656b124170ebb59b3957e147455f66b128bea22e9febd92f6385be032`. Ruff, protocol/build projections, strict JSON, relative links, temporary-directory compilation and credential/ignore checks passed. The final commit removes only two trailing blank lines from `execution.py` after this local qualification; its Python AST is unchanged. The resulting build is `aa84bdbdd0aa5f4a784671f16ee2f4146870eacc11c2a2f960b6d3cfe1a294f8`. Remote CI qualifies the exact pushed revision.

Current real `gpt-6.1-terra` trials completed scientific planning, Codex generation/delivery, full-input calculation and provider-backed scientific review for both C2 and Normalization. All four scientific artifact slots succeeded; both Runs remain at Human Gate with pending approval and no accepted terminal result. Reviewer input retained the complete aggregates within the unchanged context bound: 5,614 characters for C2 and 5,654 for Normalization. The Reviewer uses a 4,096-token output allowance; Planner defaults and control budgets remain unchanged. Model choice is local private configuration, not a model-specific execution branch.

Both exact final programs passed **all four research cases plus two hidden synthetic calibrations**, including the fixed-energy interpretation and physically missing reference. C2 family assessment took 39.41 seconds including local sandbox/interpreter overhead; this is not a service-latency guarantee. All 14 original source files retain their extraction hashes. No physics result was accepted.

Live failures exposed pending-plan interpretation, redundant diagnostic evidence, cancellation assembly, output-tag ambiguity and tool-cache contamination; the corresponding fixes and regressions preserve the original authority and approval policy. Earlier failed, canceled, incomplete-provider and numerically rejected trials retain their original outcomes. No failed Run was repaired by relabeling or bypassing its guards. Historical workbench details remain in the [research-case maintenance record](maintenance/RESEARCH_CASES_CODEX.md) and [original local record](maintenance/LOCAL_MACOS_QUALIFICATION.md).

Local detailed reports stay in ignored `check-results/` and owned scratch roots. CI outcome artifacts are produced on the CI runner. Reproduction commands and evidence semantics are in [Verification](VERIFICATION_GUIDE.md).

## Deployment qualification

| Environment | Evidence and boundary |
| --- | --- |
| Local MacBook / Python 3.12 | Native offline checks cover actual processes, SQLite settings, wheel installation and scientific Human Gate. |
| Local live checks | Current Terra Planner/Codex/Analysis/Reviewer loops for both families reached Human Gate with successful current evidence. Source identity and scientific provenance warnings remain explicit. No scientific acceptance was granted. |
| GitHub macOS / Ubuntu | Historical baseline: both jobs passed for cleanup commit `a8081d1` in [remote CI](https://github.com/Xiaowei251129/lqcd-agent/actions/runs/40575964984). Verify the exact pushed commit for current remote qualification. macOS runs full integration; Ubuntu performs static/numerical/build checks only. |

## Remaining work

Broader research-quality evaluation, additional scientific output contracts and controlled promotion of reusable generated programs remain future work. Human review must establish physical suitability, fit choices and original resampling correspondence; matching replica IDs alone cannot establish that provenance. Current scientific results remain pending human confirmation. Independent case reports have no Run-advancement authority.

Use [Architecture](ARCHITECTURE.md), [Data and security](SECURITY_AND_DATA_POLICY.md), and [Engineering decisions](DECISION_LOG.md) for the current contracts and rationale. Previous maintenance details remain in their original records and Git history rather than being repeated here.
