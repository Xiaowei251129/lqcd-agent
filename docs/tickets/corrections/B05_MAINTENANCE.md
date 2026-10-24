# B05 Integration Maintenance

## 2026-10-19: isolate product-generated idempotency keys by Run

- Ticket: [B05](../phase-b-graph-harness/B05_ACCEPTANCE_INTEGRATION_AND_END_TO_END_HARNESS.md); approved baseline `79c1eb1`.
- Counterexample: real CLI Replay created its child successfully, then the original product graph rejected the first advance with `Same-key request conflict`. Parent and child used `product-advance:attempt_000001` in the same Coordinator. Original failed Host: `/private/tmp/lqcd-agent-phase-b-host-ai7fjp7p`; CLI test evidence: `/private/tmp/lqcd-agent-b05-execution-20261019-hvo2m1_7/cli-tests-1.log`.
- Root cause: product-generated advance, Human Pause and Code Pause keys included only the Run-local Attempt ID, although their existing idempotency scopes are shared by a Coordinator.
- Change: include the canonical Run locator digest in those three existing internal keys. Request schemas, original scope, request conflict checks, ownership, ordering and effect fencing stay unchanged. No compatibility alias, alternate key lookup or fallback was added.
- Verification: pending fresh CLI child/multiple-Run and original strict trajectory validation. Earlier failed inputs retain their original identities; no final passing claim.

## 2026-10-19: isolate trusted verification workspaces by producer

- Counterexample: `/private/tmp/lqcd-agent-phase-b-host-fmpxpd3u` contains an independently completed Replay child and its parent in `consumption_failure_unavailable_recorded`. Both Code Attempts use local ID `attempt_000002`; the child has already materialized `verification_workspaces/attempt_000002_verification`. The parent is correctly refused by exclusive workspace creation, then quarantined by the original consumption failure path. Evidence: `cli-code-history-3.log` in the B05 execution root.
- Root cause: the shared trusted verifier root used the Run-local Attempt ID as its globally shared directory name.
- Change: use the immutable globally unique producer operation ID for that existing verification workspace ID; update the passive trace collector to read the corresponding actual directory. Keep exclusive creation, fresh tree verification, fencing, result schemas, stop/quarantine handling and original source validators. No overwrite, reuse, alias or alternate lookup is added.
- Verification: pending fresh dual-Run Code and original strict source tests. The prior golden review had nine positive nodes pass and its tenth node was deliberately interrupted before this source edit; that review is incomplete and is not final evidence. Its candidate files, original source fingerprint, logs and source roots are retained separately under `before-verification-collision-fix` and the original source ownership ledger. New source inputs require fresh review and final acceptance.

## 2026-10-19: isolate fresh Analysis workspaces by complete target identity

- Counterexample: after the trusted-verifier namespace fix, `/private/tmp/lqcd-agent-phase-b-host-jnnkag1q` reproduces a second shared-directory collision. The Replay child completes; the parent's advance fails at `transition_heads_verified` with `Workspace identity was replaced`, then follows the original terminal failure path. Evidence: `cli-code-child-4.log`.
- Root cause: the shared Analysis workspace root used `analysis_` plus the Run-local target Attempt ID, so two Runs targeting the same Attempt number shared one physical destination.
- Change: derive the existing opaque Analysis workspace ID from the full existing target identity (case, Run, Attempt and kind). No fields, schema, policy, authority, source eligibility or freshness checks change. Existing manifest/spec checksums bind the actual derived identity. No directory reuse, alias, overwrite or fallback is introduced.
- Verification: pending a new fixed-source dual-Run probe and independent expected/source review. This physical identity correction must preserve every original outcome, owner, event order, budget and assertion; unsupported semantic drift remains a B05 Stop Condition.

## 2026-10-19: verification result and candidate withdrawal at the baseline Stop

- The full-target Analysis and producer-scoped verification candidates passed the fresh dual-Run Code regression in 97.73 seconds (`cli-code-child-5.log`). The new CLI's original external stop-port assembly passed external cancel in 8.79 seconds (`cli-external-cancel-6.log`). These are focused candidate results, not full acceptance.
- Independent baseline reproduction then confirmed that original B04 Code exact expected already fails on unmodified `79c1eb1`, with the actual baseline package fingerprint; its two fresh traces agree and differ from old expected at 89 semantic hashes. Root cause/provenance is not yet fully established. See `confirmed-baseline-blocker.json` and [C30 review](../phase-b-graph-harness/B00C30_B04_GOLDEN_BASELINE_PROVENANCE.md).
- B05 stopped under its frozen scope. All candidate implementation and expected changes were preserved in the external candidate patch/tree/manifest, then all active source/test/script/expected bytes were restored to the pushed baseline. The fixes described above are candidate work, not current delivered capability. Old source roots, failures and interrupted reviews remain intact; no public contract, old validator, assertion or timeout was weakened.
