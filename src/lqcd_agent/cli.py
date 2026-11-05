"""Current-version LQCD control entry point; help has no graph imports."""
import argparse
import json
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser('doctor', help='Verify this deployment without loading credentials or calling models')
    verify = commands.add_parser('verify-archive', help='Check a portable evidence bundle without extraction')
    verify.add_argument('--archive-path', required=True)
    project = commands.add_parser("project-create", help="Create an empty local research project")
    project.add_argument("--id", required=True)
    project.add_argument("--title", required=True)
    project.add_argument("--goal", required=True)
    project.add_argument("--case-config", help="Workspace-relative JSON/YAML case configuration")
    project.add_argument("--data-path", help="Workspace-relative data file under raw_data/; the agents prepare the analysis configuration")
    project.add_argument("--source-kind", help="Explicit data provenance, for example measured_lattice_data or fitted_measured_bootstrap")
    project.add_argument("--python", help="Absolute trusted scientific Python interpreter")
    commands.add_parser("project-list", help="List local project metadata")
    show = commands.add_parser("project-show", help="Show a project and its archived Run evidence")
    show.add_argument("--id", required=True)
    contribution = commands.add_parser("project-contribute", help="Record optional scientific input without starting work or granting permissions")
    contribution.add_argument("--id", required=True)
    contribution.add_argument("--expected-digest", required=True, help="Current Project SHA-256 from project-show")
    contribution.add_argument("--key", required=True)
    contribution.add_argument("--body", required=True)
    contribution.add_argument("--kind", choices=("scientific_comment", "question", "evidence"), default="scientific_comment")
    contribution.add_argument("--evidence", action="append", default=[], help="Registered Project evidence SHA-256")
    search = commands.add_parser("library-search", help="Search current local assets and review states")
    search.add_argument("--query", default="")
    search.add_argument("--kind", choices=("wiki", "skill", "method"))
    search.add_argument("--status", choices=("candidate", "reviewed", "contested", "superseded"))
    search.add_argument("--scope")
    search.add_argument("--limit", type=int, default=20)
    for name in ("library-save", "library-review", "library-register-method"):
        asset = commands.add_parser(name)
        asset.add_argument("--id", required=True)
        asset.add_argument("--expected-revision", type=int, default=0, required=name != "library-save")
        if name != "library-register-method":
            asset.add_argument("--kind", choices=("wiki", "skill", "method"), required=True)
        if name == "library-save":
            asset.add_argument("--title", required=True)
            asset.add_argument("--body-file", required=True, help="Workspace-relative text file")
            asset.add_argument("--scope", required=True, help="JSON object or list describing applicability")
            asset.add_argument("--source-url", action="append", default=[])
        else:
            asset.add_argument("--rationale", required=True)
            if name == "library-review":
                asset.add_argument("--status", choices=("reviewed", "contested", "superseded"), required=True)
                asset.add_argument("--evidence", action="append", default=[], help="Workspace-relative project evidence")
            else:
                asset.add_argument("--source", required=True, help="Workspace-relative project Python file")
                asset.add_argument("--family", choices=("c2", "normalization"), required=True, help="Host independent calibration contract")
                asset.add_argument("--python", required=True, help="Absolute trusted scientific interpreter")
    for name in ("start", "run", "resume", "replay", "fork", "cancel", "status", "archive"):
        command = commands.add_parser(name)
        command.add_argument("--host", required=name not in ("start", "run"))
        command.add_argument("--case", default="case")
        if name != "archive":
            command.add_argument("--key", required=name != "status", help="Idempotency key for this operation")
        if name in ("start", "run"):
            command.add_argument("--goal", default=None)
            command.add_argument("--live", action="store_true", help="Opt in to application API calls; coding uses bounded proposals")
            command.add_argument("--workflow", choices=("no-code", "code", "human"), default="no-code")
            if name == "run":
                command.add_argument("--case-config")
                command.add_argument("--project", help="Use the goal and case configuration frozen in a local project")
                command.add_argument("--project-digest", help="Expected current Project SHA-256")
                command.add_argument("--intake-parent", help="Continue a completed preparation that needs information, using its original Host, case and task budget")
        else:
            command.add_argument("--run", required=True)
            if name in ("resume", "cancel"):
                command.add_argument("--pause", required=True)
            if name == "resume":
                command.add_argument("--response", help="Human business response JSON")
            if name in ("replay", "fork"):
                command.add_argument("--source-digest", required=True)
    args = parser.parse_args(argv)
    from .control.strict_json import ControlIntegrityError
    import subprocess
    import sqlite3
    try:
        if args.command == 'doctor':
            from .diagnostics import doctor
            result = doctor()
        elif args.command.startswith(('project-', 'library-')):
            from .research.workspace import execute_workspace
            result = execute_workspace(vars(args))
        else:
            from .runtime import ApplicationRequest, execute
            result = execute(ApplicationRequest(**vars(args)))
    except (ControlIntegrityError, OSError, ValueError, subprocess.SubprocessError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
