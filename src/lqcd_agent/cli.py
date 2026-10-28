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
    for name in ("start", "run", "resume", "replay", "fork", "cancel", "status", "archive"):
        command = commands.add_parser(name)
        command.add_argument("--host", required=name not in ("start", "run"))
        command.add_argument("--case", default="case")
        if name != "archive":
            command.add_argument("--key", required=name != "status", help="Idempotency key for this operation")
        if name in ("start", "run"):
            command.add_argument("--goal", default=None)
            command.add_argument("--live", action="store_true", help="Opt in to application API calls; coding uses bounded proposals")
            command.add_argument("--workflow", choices=("no-code", "code", "human", "research-c2", "research-normalization"), default="no-code")
            if name == "run":
                command.add_argument("--case-config", required=True)
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
