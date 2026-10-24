# B00C30 Baseline Provenance Audit

- Approved ticket: [B00C30](../phase-b-graph-harness/B00C30_B04_GOLDEN_BASELINE_PROVENANCE.md).
- Actual results and reproducible evidence: [execution record](../completions/B00C30_COMPLETION.md).
- Status: **blocked**. This audit did not change production or expected files and is not a golden repair approval.

## Finding

The baseline success trace differs from old expected at 89 semantic SHA leaves. A passive, checksum-verified DAG derivation of the actual application-build and dependency changes exactly reproduces fresh diagnostic traces generated from the original Git source with its old dependency versions, explaining 37 leaves. The remaining 52 begin at fresh Analysis and cannot be justified without the historical configuration/source preimages. The old Anaconda executable is absent, and retained audit records also document the missing preimage. Direct non-digest equality and two fresh current sources cannot establish the contents of missing historical hash preimages.

## Boundary

C30 Requirements 2–3 and its first Stop Condition require recovery of trustworthy original source/input/version and proof that all changes lie within the authorized transformation. AGENTS.md freezes ready bodies and requires an approved corrective scope for an acceptance-boundary change. Thus neither automatic actual-to-expected replacement nor relabelling the missing history as B05 CLI drift is permitted. C30 and B05 remain blocked; no implementation, validator, ownership or time limit changed.

## Reviewable next action

Restore the original raw/preimage material or original trusted Analysis environment. If it is irrecoverable, explicitly approve a bounded new actual Host configuration baseline with independent source/behavioral verification, preservation of old expected and full unchanged acceptance. A single-scenario proposal is preserved outside the repository in the C30 evidence root; it remains unapproved and unapplied. Nothing in this record treats its two agreeing fresh traces as proof of historical semantic equivalence.
