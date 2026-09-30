"""Claimed canonical consumption retains its original failure and stop owner."""
from .b03_consumption_cases import _canonical_evidence
from .b03_uncertain_consumer_cases import _failure_evidence
from .runtime_cases import exercise_phase_case


COMPETITION_PHASES = {
    "consumption_failure.failure_intent_worker_race": "control.resume_run.continue_execution.consumption_failure_ownership_reserved",
    "release.post_claim_system_stop": "control.resume_run.continue_execution.pause_claimed_recorded",
}


def consumer_competition_recovery(case_id):
    boundary, side, outcome = case_id.rsplit(".", 2)
    phase = COMPETITION_PHASES[boundary]
    race = boundary == "consumption_failure.failure_intent_worker_race"
    return exercise_phase_case(case_id, fixture_case=f"{phase}.{side}.{outcome}", fault_point=phase,
        canonical_resume="success" if race else None,
        canonical_consumer_stop={"safe": True, "reject": True} if race else None,
        competition="failure_worker_race" if race else "post_claim_system_stop",
        evidence_check=_failure_evidence if race else _canonical_evidence)
