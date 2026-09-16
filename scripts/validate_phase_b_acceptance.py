"""Validate the real project matrix using freshly generated, session-bound evidence."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests/phase_b"))

from harness.contracts import TICKETS
from harness.driver import execute, exit_code
from harness.inputs import load_inputs
from harness.report import empty_report, error, validate_report
from harness.session import Session
from harness.strict_json import Invalid, canonical, require, write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("construction", "final"))
    parser.add_argument("--ticket", choices=TICKETS)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = empty_report(args.mode, args.ticket)
    try:
        require((args.mode == "construction") == (args.ticket is not None), "cli", "ticket")
        require(not args.report.resolve().is_relative_to(ROOT) and not args.report.exists(), "cli", "fresh_report")
        inputs = load_inputs()
        session = Session(ROOT, args.evidence_dir, inputs["digests"])
        report = execute(inputs, session, args.mode, args.ticket)
    except Invalid as exc:
        error(report, **exc.error)
    except Exception:
        error(report, "internal_error", "cli", "inputs")
    # A malformed CLI selection cannot be represented as a valid ticket; argparse rejects it above.
    try:
        validate_report(report)
        require(not args.report.resolve().is_relative_to(ROOT), "cli", "report_outside_inputs")
        write_new(args.report, report)
    except (Invalid, OSError):
        print("Acceptance failed: invalid selection or report destination.", file=sys.stderr)
        return 1
    local = report["construction"]
    print(f"Phase B {args.mode}: construction_passed={local['passed'] if local else 'not_applicable'} "
          f"remaining={report['requirements']['remaining']} "
          f"runtime_missing={len(report['runtime_evidence']['missing_case_ids'])} "
          f"phase_b_complete={report['phase_b_complete']} errors={len(report['errors'])}")
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
