# Scientific evidence and role context maintenance

Date: 2026-10-27. Base: `xgao` at `814ba84`. Scope: recommendations 1 and 2, then 3; recommendation 6 only where measurements support it.

## Audit and implementation

1. Raw CSV data was read separately from inventory inspection and was absent from the analysis manifest. A pathname could change without Replay detecting a new scientific input. Scientific start now freezes its content identity, including explicit absence; analysis hashes the stream it actually parses and compares it before invoking the registered calculation. Manifest and numerical output reuse this record. Replay/fork retain the original root identity. Dataset parsing is shared with header inspection and supports CR, LF, CRLF and quoted multiline UTF-8 fields.
2. Model responses repeated Host identity and executable metadata. Planner normalization could substitute selections or promote pending responses; an unused LLM Coordinator duplicated deterministic routing. One proposal schema now controls both provider constraints and validation. Models select registered program IDs and provide scientific content; Host materialization supplies identity, mappings and artifact paths. Unknown, duplicate, forged and inappropriate empty selections fail; pending remains pending. The obsolete Coordinator path, repair heuristics and corresponding obsolete tests were removed. Current deterministic routing and evidence-derived review warnings remain.
3. Whole operational inventories competed with scientific context under the prompt bound. Requests now retain one immutable, content-addressed evidence bundle and send a role-specific view with a section catalog. Verified local reads recover explicitly named sections or fields. Scientific goals, constraints, warnings and failure evidence remain in scope. Host file lists, executable mappings and full command logs stay available locally without filling the model view. This introduces no automatic model retrieval loop, cross-Run memory policy or additional provider calls.

No changes were made to canonical control contracts, code-agent permissions, the scientific human-confirmation floor, SQLite durability, resource ownership or stop arbitration. Existing scientific member hashing and archives cover the context files. Frozen legacy protocol enum values remain unchanged; they are not a retained execution path.

## Measurement and decision

The fixed offline fixture in `scripts/measure_context.py` measures serialized message characters and compact schema characters. Retained local reports are `check-results/research-evidence-before.json` and `check-results/research-evidence-after.json`.

| Request | Before: messages + schema | After: messages + schema | Total reduction |
| --- | ---: | ---: | ---: |
| Method Planner | 4,429 + 4,434 = 8,863 | 1,819 + 1,626 = 3,445 | 61.1% |
| Scientific Reviewer | 2,317 + 13,415 = 15,732 | 1,205 + 1,978 = 3,183 | 79.8% |

The eight-point numerical kernel took roughly 7–8 microseconds per call (50 samples). This does not justify another result cache or cache invalidation path. We implemented shared schema definitions and context projection; no concurrency, storage relaxation or provider cache configuration was added. These character counts are not token counts, measured API cost reductions or production latency guarantees. Large-dataset throughput and scientific quality were not inferred from this small fixture.

## Verification

The final edge-case selection passed 19 tests in 14.38 seconds. It covers provenance across file replacement, missing input, scientific Replay, proposal authority, empty selections, pending status, verifiable context reads, tampering, redirected evidence and CSV newline forms. Earlier affected selections passed 53 and 42 tests before the final boundary additions.

The initial integration run passed 112 tests but failed 11 with 16 setup errors because the desktop sandbox denied native boot-ID, process and loopback-server operations. Its report remains `/private/tmp/lqcd-agent-check-udc8ysf7/result.json`. No tests were weakened or skipped; the complete suite is rerun with native local permissions.

Final integration passed **143 tests and all 9 numerical benchmark cases** in 209.54 seconds. Source digest stayed unchanged: `6be6e5e03de8464a7db4e8ec27c45f918dd05004874b55905ec9f879e54841bb`. Application build: `60998d3cdba73673ab165650408e8c4788012470976b6f502b27d41e3c243269`. Evidence: `check-results/integration.json` → `/private/tmp/lqcd-agent-check-dxhqwfk8/result.json`.

The canonical protocol generator, strict changed-JSON parsing, Python compilation, Markdown links and whitespace all passed separately. Bytecode was directed to `/private/tmp/lqcd-compile-spa66ign`. Credentials, virtual environments and acceptance products stay ignored. Current milestone evidence belongs in [Current state](../REPO_CURRENT_STATE.md); the retrieval interface is described in [Verification](../VERIFICATION_GUIDE.md).

## Remaining qualification

No paid provider calls were made. The new proposal schema and projections need explicit live-provider qualification before claiming API latency, cost or scientific quality improvements. Scientific evaluation data and autonomous model-directed retrieval are outside this maintenance scope.
