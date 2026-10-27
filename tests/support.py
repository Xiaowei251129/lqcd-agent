"""Small direct-process helpers; no acceptance matrix or evidence authority."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

OWNED = []

def own(path):
    path = Path(path)
    identity = path.stat()
    if not any(p == path for p, _, _ in OWNED):
        OWNED.append((path, identity.st_dev, identity.st_ino))
    return path

def mkdtemp(*args, **kwargs):
    return str(own(tempfile.mkdtemp(*args, **kwargs)))

def command(*arguments, expected_exit=0, rejection=None):
    child = subprocess.run([sys.executable, "-B", "-m", "lqcd_agent", *arguments],
                           capture_output=True, timeout=450)
    assert child.returncode == expected_exit, child.stderr.decode()
    if expected_exit:
        assert rejection and rejection in child.stderr.decode()
        return None
    result = json.loads(child.stdout)
    if arguments[0] in ("start", "run") and "--host" not in arguments:
        from lqcd_agent.inspection import host_root
        own(host_root(result["host"]))
    return result
