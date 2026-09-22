"""Deterministic external/domain decisions; these are not B04 runtime policy."""
from lqcd_agent.control.operations import RepauseAdmission
from lqcd_agent.control.strict_json import digest


class SyntheticRepauseAdapter:
    """Supply both frozen A04 branches while B02 verifies bindings and ordering."""

    def repause(self, view):
        policy, budget = view["policy"], view["budget"]
        required = {"control_attempts_per_run": 1 + policy["terminal_reserve"]["control_attempts"],
                    "transitions_per_run": 1 + policy["terminal_reserve"]["transitions"]}
        dimensions = {name: {**counts, "projected_after": counts["used"] + required.get(name, 0)}
                      for name, counts in budget["dimensions"].items()}
        sufficient = all(row["projected_after"] <= policy["limits"][name] for name, row in dimensions.items())
        binding = {**view["binding"], "terminal_tail_capacity": dimensions}
        body = {"schema_version": "0.1", "proposal_id": digest(binding), "proposed_action": "repause", "target_kind": "human_gate",
                "risk": "low", "fingerprint_digest": None, "occurrence": 0, "dimensions": dimensions, "budget_grant_id": None,
                "decision": "allow" if sufficient else "halt", "reason_code": "synthetic_external_domain_capacity",
                "next_control_action": "publish_pause" if sufficient else "close_run"}
        return RepauseAdmission("sufficient" if sufficient else "insufficient", {**body, "decision_digest": digest(body)})
