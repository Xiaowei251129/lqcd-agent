"""C19 separates a reachability proof from contract-only capacity predicates."""
from copy import deepcopy
from hashlib import sha256
from itertools import product
from pathlib import Path

import pytest

from lqcd_agent.control.budget import CONTROL_KINDS, WORK_KINDS, policy
from lqcd_agent.control.protocol import PROTOCOL
from lqcd_agent.control.strict_json import canonical_bytes, digest
from lqcd_agent.graph.analysis_graph import ProductRouteAdapter
from lqcd_agent.graph.routing import select_product_route
from test_b04_product_graph import diagnostic


PROFILES = {"balanced_v1": (16, 16, 40), "phase_b_test": (8, 8, 20)}
PATHS = {"ordinary_publisher": (7, 8), "terminal_publisher": (4, 5),
         "ordinary_repause": (6, 7), "terminal_repause": (3, 4)}
COUNT_DIMENSIONS = ("work_attempts_per_run", "control_attempts_per_run", "transitions_per_run")


def capacity_proof(profile, path):
    """Enumerate a superset of legal counts, independently of sampled Runs."""
    assert set(PROTOCOL["budget_policy_selection_contract"]["allowlisted_profiles"]) == set(PROFILES)
    selected = policy(profile).value
    limits = tuple(selected["limits"][key] for key in COUNT_DIMENSIONS)
    assert limits == PROFILES[profile]
    assert selected["terminal_reserve"] == {"control_attempts": 5, "transitions": 6}
    assert selected["grant"]["extends_global_ceilings"] is False
    assert not set(WORK_KINDS) & set(CONTROL_KINDS)
    work_limit, control_limit, transition_limit = limits
    control_required, transition_required = PATHS[path]
    # Include one END even at Human prefixes, making this set conservative.
    counts = [(w, c, t) for w, c, t in product(range(work_limit + 1),
              range(control_limit + 1), range(transition_limit + 1)) if t <= w + c + 1]
    sufficient = [transition_limit - t for w, c, t in counts if control_limit - c >= control_required]
    lower = transition_limit - work_limit - control_limit + control_required - 1
    assert sufficient and min(sufficient) == lower and lower > transition_required
    result = {"classification": "reachability_proof_not_runtime", "profile": profile, "path": path,
              "policy_digest": selected["policy_digest"], "limits": list(limits),
              "control_required": control_required, "transition_required": transition_required,
              "count_superset_size": len(counts), "minimum_remaining_transitions": lower,
              "independent_transition_threshold_candidates": sum(t <= transition_required for t in sufficient)}
    if path.endswith("repause"):
        after_validator = control_required - 1
        possible = [transition_limit - t for w, c, t in counts if control_limit - c >= after_validator]
        post_lower = transition_limit - work_limit - control_limit + after_validator - 1
        assert min(possible) == post_lower and post_lower > transition_required
        result["after_original_resume_validator"] = {"minimum_control": after_validator,
                                                     "minimum_transitions": post_lower}
    return result


@pytest.mark.parametrize("profile,path", product(PROFILES, PATHS))
def test_capacity_reachability_proof(profile, path, tmp_path):
    report = capacity_proof(profile, path)
    repo = Path(__file__).resolve().parents[2]
    sources = ["src/lqcd_agent/control/" + name + ".py" for name in
               ("budget", "execution", "records", "operations", "pause")]
    sources += ["src/lqcd_agent/graph/routing.py", "src/lqcd_agent/graph/analysis_graph.py",
                "docs/tickets/phase-a-control-contracts/CONTROL_PROTOCOL_0_4.json"]
    report["reviewed_source_sha256"] = {name: sha256((repo / name).read_bytes()).hexdigest() for name in sources}
    output = tmp_path / "reachability-proof.json"
    output.write_bytes(canonical_bytes(report))
    print("REACHABILITY_PROOF", output)


def ledger_capacity_witness(execution):
    """Check the proof premises against every prefix of an original ledger."""
    scheduled, inbound, ends = {}, set(), 0
    work = control = transitions = 0
    decisions = []
    selected = next(row["payload"]["policy"] for row in execution.values if row.get("event") == "policy_initialized")
    assert tuple(selected["limits"][key] for key in COUNT_DIMENSIONS) == PROFILES[selected["profile_id"]]
    for row in execution.values:
        if row["record_type"] == "attempt" and row["event"] == "scheduled":
            assert row["attempt_id"] not in scheduled
            scheduled[row["attempt_id"]] = row
            assert row["attempt_kind"] in WORK_KINDS + CONTROL_KINDS
            work += row["attempt_kind"] in WORK_KINDS
            control += row["attempt_kind"] in CONTROL_KINDS
        if row["record_type"] == "transition":
            transitions += 1
            target = row["target_attempt_id"]
            if target is None:
                ends += 1
                assert row["route"] == "end" and row["source_node"] == "memory_report"
            else:
                assert target not in inbound and target in scheduled
                assert row["transition_id"] == scheduled[target]["inbound_transition_id"]
                inbound.add(target)
        assert ends <= 1 and transitions <= work + control + 1
        assert work <= selected["limits"][COUNT_DIMENSIONS[0]] and control <= selected["limits"][COUNT_DIMENSIONS[1]]
        if row.get("event") == "decision_recorded" and row["payload"]["target_kind"] == "human_gate":
            payload = row["payload"]
            decisions.append({"head": digest(row), "action": payload["proposed_action"],
                              "decision": payload["decision"], "counts": [work, control, transitions],
                              "dimensions": payload["dimensions"]})
    dimensions = execution.projection.value["budget"]["dimensions"]
    assert [dimensions[key]["used"] for key in COUNT_DIMENSIONS] == [work, control, transitions]
    return {"classification": "original_port_runtime_witness", "profile": selected["profile_id"],
            "work": work, "control": control, "transitions": transitions, "end_count": ends,
            "prefixes_checked": len(execution.records), "execution_head": digest(execution.values[-1]),
            "human_capacity_decisions": decisions, "B04_owned": False}


@pytest.mark.parametrize("profile,path,control_offset,transition_offset",
                         product(PROFILES, PATHS, (-1, 0, 1), (-1, 0, 1)))
def test_contract_only_capacity_predicates(profile, path, control_offset, transition_offset):
    """Artificial views test predicates only; they are never persisted as Runs."""
    capacity_proof(profile, path)
    selected = policy(profile).value
    control_required, transition_required = PATHS[path]
    control, transitions = control_required + control_offset, transition_required + transition_offset
    dimensions = {key: {"used": 0, "remaining": limit} for key, limit in selected["limits"].items()}
    for key, remaining in (("control_attempts_per_run", control), ("transitions_per_run", transitions)):
        dimensions[key] = {"used": selected["limits"][key] - remaining, "remaining": remaining}
    budget = {"profile_id": profile, "dimensions": dimensions, "active_failure": None, "active_grant": None}
    terminal = path.startswith("terminal")
    if path.endswith("repause"):
        view = {"policy": selected, "budget": budget, "binding": {
                    "consumed_old_pause": "d" * 64, "finished_validator_attempt": "e" * 64,
                    "open_human_request": "contract-only-request", "derived_next_pause_identity": "contract-only-pause"},
                "human_continuation": {"mode": "terminal" if terminal else "ordinary",
                    "validator_transition_head": "a" * 64, "stop_sequence_id": "b" * 64 if terminal else None,
                    "budget_stop_transition_head": "c" * 64 if terminal else None}}
        before = deepcopy(view)
        admission = ProductRouteAdapter(None).repause(view)
        decision = admission.decision
        assert admission.capacity == ("sufficient" if control_offset >= 0 and transition_offset >= 0 else "insufficient")
    else:
        view = {"source": {"node_name": "decision_coordinator", "status": "succeeded", "attempt_id": "contract-only"},
                "state": {"run_id": "contract-only", "attempt_id": "contract-only", "budget": budget}}
        before = deepcopy(view)
        route = select_product_route(view, diagnostic(risk="high", human_need="approval"))
        decision = route["budget_decision"]
        ordinary = control >= 7 and transitions >= 8
        assert (route["stop_sequence_id"] is None) == ordinary
        assert route["trigger_reason"] == ("forward" if ordinary else "budget_stop")
        if not ordinary:
            scope = route["human_request"]["authorization_scope"]
            assert scope["work_target"] is None and "approve_budget_window" not in scope["allowed_decisions"]
    expected = (control >= control_required and transitions >= transition_required) if path.endswith("repause") else (
        control >= 4 and transitions >= 5)
    assert decision["decision"] == ("allow" if expected else "halt")
    assert decision["budget_grant_id"] is None and view == before
