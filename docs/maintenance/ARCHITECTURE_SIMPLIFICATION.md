# Architecture simplification

Date: 2026-10-27. Audited baseline: `9540fbc6a73328dcb6c28b1a76ca0e03668e17b1`.

## Audit and scope

The operator authorized items 1–3 first, then 4–5, with unchanged permissions, human confirmation and persistence guarantees. The audit reproduced a negative matrix uncertainty being severe/low-confidence in deterministic review but passing with high confidence through the mock provider path. It also found 20 obsolete artifact writer/helper functions without current workflow callers, repeated ledger parsing within individual reads/journal validations, validated remediation/history dropped at the scientific adapter, and provider configuration owned by both application assembly and roles.

An instrumented fresh offline example made 566 ledger parses over 26 distinct byte sequences, reading 15,160,608 bytes. Parsing accounted for 2.724 seconds of 8.714 seconds. This was a diagnostic sample, not an estimate of safely removable work: many parses enforce current invocation authority. A separate caller-count probe attributed 282 parses to capability activation, 149 to the byte-append boundary and 51 to root integrity validation.

## Implementation and removals

1. Reviewer correlator/fit/matrix diagnostics, context warnings and analysis-failure evidence now have one Host implementation. Provider interpretation can add findings/checks, but cannot replace numerical sections, erase Host warnings or exceed their confidence ceiling. Failure preserves the diagnostics. Removed the parallel provider diagnostic path, duplicated Mock numerical logic and model-owned diagnostic schema fields. The externally produced report still contains Host diagnostic sections.
2. Deleted direct artifact initialization, registration, invalidation, protection and projection writers, plus their now-unused helpers and exports: 20 functions and 469 registry lines. Controlled publication remains the writer, with the same shared registration preflight, lifecycle validation and projection rules. Frozen protocol enums were not changed.
3. Adjacent node/context consumers share one parsed ledger/index; post-effect reads remain fresh. Ordinary budget and verification journals validate the starting prefix once per invocation of their validator, extend immutable records, replay the complete resulting chain and compare exact frozen bytes at every entry. Removed redundant parse-after-append calls. No cache survives a validation call, and no lease fence, head comparison, sync or transaction boundary was removed.
4. Scientific roles receive the already validated remediation packet and bounded relevant history. Both the outbound request and immutable local context retain these fields. Context remains data, not authority; the 6,000-character limit fails explicitly without truncation. This implements context continuity using existing evidence retention, not autonomous model retrieval or additional provider calls.
5. Application assembly is the provider/credential entry point. Removed `llm/provider_factory.py`, its obsolete dry-run CLI, role `provider_config_path` branches and unused raw configuration storage. Standalone roles accept constructed providers. The OpenAI, DeepSeek and Mock adapters remain; injected live adapters retain their explicit activation requirements. Application live mode and private credential precedence are unchanged.

No new runtime framework, compatibility alias, configuration switch, global cache, permission, automatic acceptance or persistence authority was added. Replaced mock/factory tests were removed or merged into current behavior tests.

## Validation

- Shared scientific validation and context selection: 44 tests passed.
- Initial workflow/archive/CLI/durability selection: 29 passed, four failed because the sandbox denied the existing native boot-session query. The failed report remains `/private/tmp/lqcd-agent-check-xe3t_mqg/result.json`.
- The original control/durability selection, with native system access and no test substitutions: 33 passed in 171.10 seconds; `/private/tmp/lqcd-agent-check-5t6l2ea4/result.json`.
- Context, provider activation/credentials, scientific assembly, immutable extension and journal-tamper regressions: 33 passed in 103.18 seconds; `/private/tmp/lqcd-agent-check-z8d2wwdv/result.json`.

- Final integration: **149 tests and all 9 numerical benchmark cases passed** in 225.04 seconds, including wheel installation, actual process/stop behavior, unchanged human decisions, cancellation, replay, archive and durability checks. Source digest stayed unchanged: `580838c3d92524f76d8259e22c551563b2c3179db83b7cbf32b4c55ef9094a77`. Report: `/private/tmp/lqcd-agent-check-sgq32fii/result.json`, also referenced by ignored `check-results/integration.json`.
- Current protocol generation, strict JSON/duplicate-key checks, changed Markdown relative links, Python compilation to `/private/tmp`, and `git diff --check` passed. No credentials or local acceptance artifacts are part of the diff. Source files have a net reduction of 974 lines, excluding the generated build manifest.

## Performance

Three fresh-process samples were taken before editing and again after integration, with no concurrent test run. Native durability remained enabled and all measured Runs completed consistently:

| Median, seconds | Before | After |
| --- | ---: | ---: |
| Offline start | 8.506 | 8.371 |
| Read-only status | 0.232 | 0.270 |

Because the startup difference was small and status was slower, a separate alternating comparison used three pairs of baseline/current source snapshots, the same interpreter and workspace, and no package bytecode in either snapshot. Both application build identities were checked for every sample. The final paired measurements were:

| Operation | Baseline median / maximum, seconds | Current median / maximum, seconds |
| --- | ---: | ---: |
| Offline start | 9.541 / 9.552 | 9.451 / 9.917 |
| Read-only status | 0.365 / 0.385 | 0.360 / 0.610 |

These small samples show essentially unchanged end-to-end latency, with substantial variation and a current status outlier retained in the report. They do not establish a significant speedup or a tail-latency guarantee. An earlier exploratory alternating comparison had unequal package bytecode conditions; it is retained separately and is not used for the final latency conclusion.

The final instrumented example made **464 ledger parses over 26 distinct byte sequences**, versus 566/26 before: 102 fewer parses (18.0%). Parsed bytes fell from 15,160,608 to 12,840,310. The single final probe measured 2.452 seconds inside parsing and 7.942 seconds overall. This demonstrates less repeated parsing, not proportional end-to-end acceleration; activation/integrity checks and durable publication remain. The current fixed context probe reports Planner 2,020 message + 1,626 schema characters and Reviewer 1,406 + 1,274 characters; these are not token or billing measurements.

Ignored evidence: `check-results/architecture-before.json`, `architecture-after.json`, `architecture-interleaved.json`, `architecture-interleaved-exploratory.json`, and `architecture-parse-after.json`. The final build is `1279f94eca21dc837df66eeee433d672bbaf5397c50896d901b456f7d77c4324`; protocol and graph topology fingerprints match the baseline. Fresh measurement Hosts and temporary source snapshots are retained locally, outside Git.

## Qualification limits

These are offline engineering checks and local measurements. Paid API calls and remote CI have not been rerun for that build. Existing scientific confirmation remains a human decision. Autonomous evidence retrieval, arbitrary generated scientific execution and physics acceptance are not claimed by this maintenance.
