"""Deterministic inputs and asserted construction invariants, not result evidence."""
from .trace import event

INVARIANTS = {
    1: ["closed_objects", "strict_json"],
    2: ["exact_catalog_digest", "nine_owners", "required_131"],
    3: ["coverage_set_equality", "owned_slice_only"],
    4: ["fresh_pytest_evidence", "no_skips_or_xfails"],
    5: ["exact_trace", "semantic_identity_preserved"],
    6: ["independent_inventory", "runtime_not_claimed"],
    7: ["evidence_classes_separate"],
    8: ["final_requires_runtime_and_exit", "sequential_slices"],
    9: ["exhaustive_graphs", "unique_terminal_evidence"],
    10: ["immutable_projection", "single_contract_authority"],
    11: ["single_transaction_domain", "unique_cas_winner"],
    12: ["exact_reservation_overlays", "twelve_variants"],
    13: ["disjoint_exhaustive_branches", "tagged_unions"],
    14: ["composite_owners", "unique_stop_route"],
    15: ["independent_semantic_mutations", "post_claim_28", "producer_dominance"],
}


def meta_trace():
    return {"schema_version": "0.1", "events": [
        event("projection_loaded", index=0, run_id="meta-run", phase="construction", owner="B00",
              execution_head="head-0", binding_digest="binding-0", guard_passed=True),
        event("projection_compared", index=1, run_id="meta-run", phase="construction", owner="B00",
              execution_head="head-1", binding_digest="binding-0", guard_passed=True),
    ]}
