"""Current-version LQCD control entry point; help has no graph imports."""
import argparse
import json
import sys

def host_root(identifier):
    from .runtime import host_root as resolve
    return resolve(identifier)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "run", "resume", "replay", "fork", "cancel"):
        command = commands.add_parser(name)
        command.add_argument("--host", required=name not in ("start", "run"))
        command.add_argument("--case", default="case")
        command.add_argument("--key", required=True)
        if name in ("start", "run"):
            command.add_argument("--goal", default="Validate the synthetic observable")
            command.add_argument("--workflow", choices=("no-code", "code", "human"), default="no-code")
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
    from .runtime import execute
    import subprocess
    try:
        result = execute(args)
    except (ControlIntegrityError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
