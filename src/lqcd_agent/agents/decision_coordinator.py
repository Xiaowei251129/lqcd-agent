"""Deterministic Host diagnosis; model outputs cannot grant control authority."""

RISK_SEVERITY = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def validate_product_diagnostic(value):
    """Validate A01 diagnostics without granting route or scientific authority."""
    from lqcd_agent.control.strict_json import closed, digest_value, require, text
    closed(value, ("status", "category", "affected_layer", "evidence", "retryability", "candidates",
                   "confidence", "fingerprint", "human_need", "risk"))
    require(value["status"] in ("success", "failed", "needs_input", "needs_human", "pending"), "Unknown product outcome")
    text(value["category"])
    require(value["affected_layer"] in ("plan", "code", "analysis", "review", "none"), "Unknown affected layer")
    require(value["retryability"] in ("retryable", "not_retryable", "new_evidence_required"), "Unknown retryability")
    require(value["confidence"] in ("unique", "ambiguous", "insufficient"), "Unknown diagnosis confidence")
    require(value["human_need"] in (None, "clarification", "approval", "external_action"), "Unknown Human need")
    require(value["risk"] in RISK_SEVERITY, "Unknown diagnostic risk")
    require(type(value["candidates"]) is list and value["candidates"] == sorted(set(value["candidates"])) and
            set(value["candidates"]) <= {"method_planner", "code_agent", "analysis_engineer", "scientific_reviewer"},
            "Invalid remediation candidates")
    require(type(value["evidence"]) is list, "Missing diagnostic evidence")
    for reference in value["evidence"]:
        closed(reference, ("artifact_id", "member", "sha256"))
        text(reference["artifact_id"])
        text(reference["member"])
        digest_value(reference["sha256"])
    digest_value(value["fingerprint"], nullable=True)
    require(value["status"] == "success" or bool(value["evidence"]), "Failure requires attributable evidence")
    return value


def product_coordinator_diagnosis(diagnostics, *, local_risk_floor):
    """Merge bounded evidence; the control selector admits the resulting action."""
    from copy import deepcopy
    from lqcd_agent.control.strict_json import require
    require(type(diagnostics) is list and diagnostics, "Coordinator requires bounded source diagnostics")
    require(local_risk_floor in RISK_SEVERITY, "Missing deterministic risk floor")
    values = [validate_product_diagnostic(deepcopy(value)) for value in diagnostics]
    result = values[-1]
    risks = [local_risk_floor, *[value["risk"] for value in values]]
    result["risk"] = max(risks, key=RISK_SEVERITY.__getitem__)
    candidates = sorted({candidate for value in values for candidate in value["candidates"]})
    result["candidates"] = candidates
    if len(candidates) > 1 or any(value["confidence"] != "unique" for value in values):
        result["confidence"] = "ambiguous"
    if result["risk"] in ("high", "critical") and result["human_need"] is None:
        result["human_need"] = "approval"
    return validate_product_diagnostic(result)
