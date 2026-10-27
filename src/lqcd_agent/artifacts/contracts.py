"""Artifact fields and invalidation policy, without filesystem or registry access."""

ARTIFACT_SCHEMA_VERSION = "0.1"


ARTIFACT_SLOTS = (
    "plan",
    "code",
    "analysis",
    "review",
    "decision",
    "approval",
    "terminal",
)


SLOT_BY_ATTEMPT_KIND = {
    "method_planner": "plan",
    "code_agent": "code",
    "analysis_engineer": "analysis",
    "scientific_reviewer": "review",
    "decision_coordinator": "decision",
    "human_gate": "approval",
    "memory_report": "terminal",
}


INVALIDATED_SLOTS_BY_TARGET_KIND = {
    "method_planner": ARTIFACT_SLOTS,
    "code_agent": ARTIFACT_SLOTS[1:],
    "analysis_engineer": ARTIFACT_SLOTS[2:],
    "scientific_reviewer": ARTIFACT_SLOTS[3:],
    "decision_coordinator": ARTIFACT_SLOTS[4:],
    "memory_report": ARTIFACT_SLOTS[6:],
}


STATE_FIELDS_BY_SLOT = {
    "plan": ("method_plan_path", "coder_task_packet_path"),
    "code": ("code_change_summary_path", "tests_status_path"),
    "analysis": ("run_result_path", "analysis_outputs_dir"),
    "review": ("scientific_review_report_path",),
    "decision": ("decision_log_path",),
    "approval": ("approval_packet_dir", "human_decision_path"),
    "terminal": ("memory_update_path", "final_report_path"),
}


CANONICAL_CODE_PATH_FIELDS = (
    "code_agent_task_path",
    "code_agent_result_path",
    "code_change_manifest_path",
    "code_verification_results_path",
)


CODE_STATE_PATH_FIELDS = (*STATE_FIELDS_BY_SLOT["code"], *CANONICAL_CODE_PATH_FIELDS)


CODE_MEMBER_BY_STATE_FIELD = dict(zip(CANONICAL_CODE_PATH_FIELDS, (
    "code_agent_task.json", "code_agent_result.json", "change_manifest.json", "verification_results.json")))


def state_fields_for_slot(slot: str, schema_version: str) -> tuple[str, ...]:
    if slot == "code" and schema_version == "0.4":
        return CODE_STATE_PATH_FIELDS
    return STATE_FIELDS_BY_SLOT[slot]


POINTER_FIELDS = {
    "artifact_id",
    "slot",
    "cycle_id",
    "attempt_id",
    "attempt_kind",
    "status",
    "dependencies",
    "members",
    "state_paths",
}


def slots_for_target(target_attempt_kind: str, *, new_human_request: bool) -> tuple[str, ...]:
    if target_attempt_kind == "human_gate":
        return ("approval", "terminal") if new_human_request else ()
    try:
        return tuple(INVALIDATED_SLOTS_BY_TARGET_KIND[target_attempt_kind])
    except KeyError as exc:
        raise ValueError(f"Unsupported invalidation target kind: {target_attempt_kind}") from exc
