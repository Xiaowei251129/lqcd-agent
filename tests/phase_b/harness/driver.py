"""Single-session construction and fail-closed final acceptance orchestration."""
from .contracts import EXIT_CHECKS
from .strict_json import Invalid, require
from .matrix import selected_scenarios
from .report import empty_report, counts, error, validate_report
from .pytest_evidence import run_pytest, validate_pytest, validate_observations, collect_pytest
from .failpoints import runtime_gaps, validate_runtime
from .exit_checks import production_adapters, validate_exit, validate_adapter_targets


def execute(inputs, session, mode, ticket=None, *, _adapters=None, _pytest_runner=run_pytest):
    """Underscored injection points are for isolated tests, never exposed by the project CLI."""
    report = empty_report(mode, ticket)
    report["digests"] = session.digests
    required, covered, specs = inputs["required"], inputs["covered"], inputs["specs"]
    remaining = [rid for rid in required if rid not in covered]
    report["requirements"] = counts(required=required, covered=covered, passed=None, remaining=remaining)
    report["runtime_evidence"].update(required_case_ids=list(specs), missing_case_ids=list(specs))
    scenarios = selected_scenarios(inputs["matrix"], mode, ticket)
    try:
        if mode == "construction":
            require(ticket in inputs["slices"], "construction", "ticket_id")
            owned = inputs["slices"][ticket]
            local = [rid for rid in owned if any(rid in s["contract_refs"] for s in scenarios)]
            report["construction"] = counts(required=owned, covered=local, passed=None)
            for rid in owned:
                if rid not in local:
                    error(report, "coverage_gap", rid, "construction")
        else:
            adapters = production_adapters(inputs) if _adapters is None else _adapters
            require(not set(adapters) - set(EXIT_CHECKS), "adapters", "unknown_check")
            for rid in remaining:
                error(report, "coverage_gap", rid, "requirements")
            missing = runtime_gaps(inputs["registry"], specs, scenarios)
            for cid in missing:
                error(report, "runtime_evidence_gap", cid, "binding")
            report["runtime_evidence"]["status"] = "missing"
            for row in report["exit_checks"]:
                if row["check_id"] not in adapters:
                    row["status"] = "missing"
                    error(report, "exit_evidence_gap", row["check_id"], "adapter")
            if _adapters is None:
                collect_pytest(session, sorted({n for s in scenarios for n in s["pytest_nodeids"]}))
                validate_adapter_targets(inputs, session, adapters)
        if not report["errors"]:
            selection = sorted({n for s in scenarios for n in s["pytest_nodeids"]})
            evidence = _pytest_runner(session, selection)
            validate_pytest(evidence, session, selection)
            passing = validate_observations(evidence, scenarios, inputs["root"], all_scenarios=inputs["matrix"]["scenarios"])
            if mode == "construction":
                passed = [r for r in owned if all(s["scenario_id"] in passing for s in scenarios if r in s["contract_refs"])]
                report["construction"].update(counts(passed=passed))
            else:
                passed_cases = validate_runtime(evidence, inputs["registry"], specs, scenarios, inputs["root"])
                missing = [c for c in specs if c not in passed_cases]
                report["runtime_evidence"].update(status="passed" if not missing else "missing",
                                                   passed_case_ids=passed_cases, missing_case_ids=missing)
                for cid in missing:
                    error(report, "runtime_evidence_gap", cid, "trigger")
                passed = []
                for rid in required:
                    obligations = [o for o in inputs["obligations"]["runtime_obligations"] if rid in o["contract_refs"]]
                    if all(s["scenario_id"] in passing for s in scenarios if rid in s["contract_refs"]) and all(
                            cid in passed_cases for o in obligations for cid in o["case_ids"]):
                        passed.append(rid)
                report["requirements"].update(counts(passed=passed))
                report["requirements_zero_gap"] = passed == required and not missing and not remaining
                for row in report["exit_checks"]:
                    cid = row["check_id"]
                    try:
                        envelope = adapters[cid].run(session)
                        row["evidence_digests"] = validate_exit(envelope, cid, session, adapters[cid])
                        row["status"] = "passed"
                    except Invalid as exc:
                        row["status"] = "failed"
                        error(report, **exc.error)
                    except Exception:
                        row["status"] = "failed"
                        error(report, "internal_error", cid, "adapter")
        session.unchanged()
    except Invalid as exc:
        error(report, **exc.error)
        report["requirements_zero_gap"] = False
    except Exception:
        error(report, "internal_error", "driver", "execution")
        report["requirements_zero_gap"] = False
    report["phase_b_complete"] = bool(report["requirements_zero_gap"] and not report["errors"]
                                     and all(r["status"] == "passed" for r in report["exit_checks"]))
    validate_report(report)
    return report


def exit_code(report):
    if report["mode"] == "final":
        return 0 if report["phase_b_complete"] else 1
    c = report["construction"]
    return 0 if not report["errors"] and c["passed_ids"] == c["required_ids"] and c["required_ids"] else 1
