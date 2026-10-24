# B00C30 Execution Record

- Ticket: [B00C30](../phase-b-graph-harness/B00C30_B04_GOLDEN_BASELINE_PROVENANCE.md).
- Status: **blocked**; B05 remains blocked and Phase B is incomplete.
- Authorization: the user explicitly approved C30 execution, followed by an independent B05 entry check and continuation.
- Baseline: `79c1eb1a6d56f01f8e42db44d7a6a3122613dddb` on xgao.
- Frozen body SHA-256: `adc41ecdfb94e7ae2e0c1f45312aba7ffd44dd6bf637d2f030cc2d13cfce18b0`.
- Evidence root: `/private/tmp/lqcd-agent-c30-execution-20261019-ubr1acn3`.
- Input manifest: 5662 files, with all expected preimages preserved separately; free space at entry approximately 128.6 GiB. The unimplemented B05 candidate tree remains external and is not a C30 passing input.

## Baseline reproduction

The original unmodified Git archive independently reproduces the B04 Code success failure again: two fresh traces agree, then original exact comparison raises `invalid_evidence:trace:exact`. The test failed in 94.34 seconds, without a timeout or changed assertions. Log and directory ownership ledger are retained in the evidence root.

## Provenance audit and Stop Condition

- An independent Git archive of `057a836` was reconstructed under the preserved actual LangGraph 1.1.5 / SQLite checkpointer 3.1.0 packages, without changing dependency declarations or patching runtime fingerprints. Its actual application build is `df2cd8314c25a0d391278c705cb6c97c206e91dbe5b5b8e18ff6684f07ba0f61`. The imported module path, actual interpreter/version and fingerprint are saved in `original-reconstruction-fingerprint.json`.
- The original dual-fresh success test still fails with the original exact error: **130.33 seconds** using canonical `python`, and **130.77 seconds** using that environment's `python3`. These are new diagnostic sources, not original native evidence or old Session results. Both failures and all source roots remain intact.
- Passive preimage capture calls the original normalizer and unchanged digest function, records inputs, verifies every recorded SHA, and asserts instrumentation leaves normalization unchanged. The independently derived build/dependency DAG maps the current trace exactly to both actual reconstructed old-build/old-dependency traces. This explains **37 of 89** changed normalized leaves. **52 remain unmatched against the old golden**, beginning at the post-Code Analysis resource decision.
- The remaining dependency chain includes the real Analysis configuration (allowed command, runtime executable/version, analysis runtime fingerprint and runtime-policy digest), then its proposal, budget, execution and artifact references. Historical records identify `/opt/anaconda3/bin/python`; that environment is absent here. The previous maintenance record explicitly says the historical configuration preimage is unavailable. Searches of retained raw/audit material, Git input snapshots and task-relevant local archives found no authentic before configuration/source that resolves these hashes. It would be incorrect to assert that every remaining hash difference is harmless configuration drift.
- **C30 Requirements 2–3 and its first Stop Condition are not satisfied:** the corresponding original source/input/version cannot be restored, and all differences cannot be proven to lie within the permitted environment/build transformation. Under AGENTS.md Ticket Execution, the frozen body cannot be widened during execution. C30 is blocked; its ready body remains unchanged.

## Candidate and B05 entry

`unapproved-current-host-proposal.json` provides a reviewable single-scenario proposal outside the repository, with original/proposed SHA, all 89 leaf differences and both genuine fresh current sources. All directly visible non-digest fields are unchanged. This is **not an approved expected update**, proof of the missing old preimages, complete impact inventory or passing acceptance. No repository expected was changed.

The independent B05 entry check is negative: C30 is not complete and the original exact counterexample remains failing. B05 stays blocked under its unchanged frozen body; its candidate source/tests/adapters remain outside the worktree. Complete collection succeeds at 4785 nodes. Full C30 regression, independent B04 required/owned evidence and B05 final were not run as passing acceptance on a repaired input, because no admissible repaired input was established. Historical passing evidence is not relabelled.

## Required resolution

Recover the original raw/preimage sources or the original trusted Analysis environment/configuration. If those are no longer available, a separate approved corrective scope must explicitly authorize a new actual Host configuration baseline and its independent behavioral/source checks, while retaining the old expected and unresolved provenance limitation. That approval must not pretend to recover missing evidence or waive exact comparison, assertions, complete selection, Session binding or the 450-second limit.

## Scope and preservation

Production, existing tests, scripts and all expected bytes remain identical to `79c1eb1`; no compatibility path, fallback, runtime schema or assertion was added. No original source/evidence was removed or merged. The six new diagnostic Run roots, old evidence and B05 candidate package remain recoverable. Only lifecycle/status and separate audit records changed. No commit/push after the already-pushed baseline.


## Verification on the unchanged production/test input

- Fresh complete collection: **4785 tests collected in 4.51 seconds**; collection is not a passing full-suite receipt.
- Separate full legacy selection: **325/325 passed in 83.19 seconds**, with no failures, errors or skips. Original tests and reference material are unchanged; log and JUnit XML are retained.
- Phase A validator: passed all 131 requirements, protocol/catalog structure, semantics/freeze and original negative mutations. Protocol SHA remains `7447087f73caae2668a8e71e12fc40e426ebefee5864e3499a3f9cbd1a9322b8`.
- Python compileall for src/tests/scripts passed with bytecode directed to the external evidence root.
- Strict JSON/duplicate-key, Markdown links, frozen-body/history/source scope and diff checks are recorded in `stopped-scope-and-doc-audit.json`. Documentation delivery bytes are separate from the unchanged production/test input exercised above.

Final scope audit: 5496 protected code/test/script/config files equal the pushed baseline; all 78 protected historical records and 49 prior ticket bodies unchanged; C30 frozen body exact. Strict JSON/duplicate keys checked in 2532 files; 2001 relative Markdown links resolve. Historical absolute evidence references are recorded separately and are not treated as current available sources. `git diff --check` passed.
