"""The single closed, deterministic PhaseBAcceptanceReport 0.1 contract."""
from .contracts import DIGEST_KEYS, EXIT_CHECKS, TICKETS
from .strict_json import keys, require, strings, canonical
from .session import validate_digests

CATEGORIES = ("coverage_gap", "runtime_evidence_gap", "exit_evidence_gap", "invalid_input",
              "invalid_evidence", "check_failed", "internal_error")
STATUSES = ("not_run", "passed", "failed", "missing")
FIELDS = {"schema_version", "mode", "ticket_id", "digests", "construction", "requirements",
          "runtime_evidence", "exit_checks", "requirements_zero_gap", "phase_b_complete", "errors"}


def counts(**groups):
    value = {}
    for name, ids in groups.items():
        value[name] = None if ids is None else len(ids)
        value[name + "_ids"] = ids
    return value


def empty_report(mode, ticket):
    return {"schema_version": "0.1", "mode": mode, "ticket_id": ticket,
            "digests": dict.fromkeys(DIGEST_KEYS),
            "construction": counts(required=None, covered=None, passed=None) if mode == "construction" else None,
            "requirements": counts(required=None, covered=None, passed=None, remaining=None),
            "runtime_evidence": {"status": "not_run", "required_case_ids": [], "passed_case_ids": None,
                                 "missing_case_ids": [], "failed_case_ids": []},
            "exit_checks": [{"check_id": cid, "status": "not_run", "evidence_digests": []} for cid in EXIT_CHECKS],
            "requirements_zero_gap": False, "phase_b_complete": False, "errors": []}


def error(report, category, object_id, field_path):
    row = {"category": category, "object_id": object_id, "field_path": field_path}
    if row not in report["errors"]:
        report["errors"].append(row)
    report["errors"].sort(key=lambda x: (x["category"], x["object_id"], x["field_path"]))


def validate_report(report):
    keys(report, FIELDS, "report")
    require(report["schema_version"] == "0.1" and report["mode"] in ("construction", "final"), "report", "mode")
    require(report["ticket_id"] in TICKETS if report["mode"] == "construction" else report["ticket_id"] is None,
            "report", "ticket_id")
    validate_digests(report["digests"], nullable=True)
    for name, groups in (("requirements", ("required", "covered", "passed", "remaining")),
                         ("construction", ("required", "covered", "passed"))):
        value = report[name]
        if name == "construction" and report["mode"] == "final":
            require(value is None, "report", name)
            continue
        keys(value, {g + suffix for g in groups for suffix in ("", "_ids")}, name)
        for g in groups:
            ids = value[g + "_ids"]
            if ids is None:
                require(value[g] is None, name, g)
            else:
                strings(ids, name, g, nonempty=False, ordered=False)
                require(type(value[g]) is int and value[g] == len(ids), name, g)
        if value["required_ids"] is not None:
            required = value["required_ids"]
            for g in groups[1:]:
                ids = value[g + "_ids"]
                if ids is not None:
                    require(ids == [i for i in required if i in ids], name, g)
            if name == "requirements":
                require(value["remaining_ids"] == [i for i in required if i not in value["covered_ids"]], name, "remaining")
    runtime = report["runtime_evidence"]
    keys(runtime, {"status", "required_case_ids", "passed_case_ids", "missing_case_ids", "failed_case_ids"}, "runtime")
    require(runtime["status"] in STATUSES, "runtime", "status")
    for key in ("required_case_ids", "missing_case_ids", "failed_case_ids"):
        strings(runtime[key], "runtime", key, nonempty=False)
    if runtime["passed_case_ids"] is not None:
        strings(runtime["passed_case_ids"], "runtime", "passed_case_ids", nonempty=False)
        groups = runtime["passed_case_ids"] + runtime["missing_case_ids"] + runtime["failed_case_ids"]
        require(sorted(groups) == runtime["required_case_ids"], "runtime", "case_partition")
    require(type(report["exit_checks"]) is list and len(report["exit_checks"]) == len(EXIT_CHECKS), "report", "exit_checks")
    for cid, row in zip(EXIT_CHECKS, report["exit_checks"]):
        keys(row, {"check_id", "status", "evidence_digests"}, cid)
        require(row["check_id"] == cid and row["status"] in STATUSES, cid, "status")
        strings(row["evidence_digests"], cid, "evidence_digests", nonempty=False)
        require(all(len(s) == 64 and all(c in "0123456789abcdef" for c in s) for s in row["evidence_digests"]), cid, "digest")
        require(row["status"] != "passed" or bool(row["evidence_digests"]), cid, "passing_evidence")
        require(row["status"] not in ("not_run", "missing") or row["evidence_digests"] == [], cid, "no_evidence")
    require(type(report["errors"]) is list, "report", "errors")
    order = []
    for row in report["errors"]:
        keys(row, {"category", "object_id", "field_path"}, "error")
        require(row["category"] in CATEGORIES and all(type(v) is str and v for v in row.values()), "error", "value")
        order.append((row["category"], row["object_id"], row["field_path"]))
    require(order == sorted(set(order)), "report", "error_order")
    for flag in ("requirements_zero_gap", "phase_b_complete"):
        require(type(report[flag]) is bool, "report", flag)
    if report["mode"] == "construction":
        require(report["requirements"]["passed"] is None and report["requirements"]["passed_ids"] is None
                and runtime["status"] == "not_run" and runtime["passed_case_ids"] is None
                and all(r["status"] == "not_run" for r in report["exit_checks"])
                and not report["requirements_zero_gap"] and not report["phase_b_complete"], "report", "construction_boundary")
    if report["requirements_zero_gap"]:
        require(report["mode"] == "final" and report["requirements"]["remaining"] == 0
                and report["requirements"]["passed_ids"] == report["requirements"]["required_ids"]
                and runtime["status"] == "passed" and runtime["passed_case_ids"] == runtime["required_case_ids"], "report", "zero_gap")
    require(report["phase_b_complete"] == (report["requirements_zero_gap"] and not report["errors"]
            and all(r["status"] == "passed" for r in report["exit_checks"])), "report", "completion")
    canonical(report)
    return report
