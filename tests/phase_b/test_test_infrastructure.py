"""Regression checks for source freshness and test-directory ownership."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

from harness.contracts import ROOT
from harness.strict_json import Invalid, callable_ref
from harness.temporary import LEDGER_ENV


def test_source_cache_reuses_parsing_but_checks_every_qualified_name(tmp_path, monkeypatch):
    import ast
    source = tmp_path / "source.py"
    source.write_text("def first(): pass\ndef second(): pass\nclass NotAFunction: pass\n")
    parse = ast.parse
    calls = []
    def tracked(raw):
        calls.append(raw)
        return parse(raw)
    monkeypatch.setattr(ast, "parse", tracked)
    cache = {}
    callable_ref(tmp_path, "source.py:first", source_cache=cache)
    callable_ref(tmp_path, "source.py:second", source_cache=cache)
    for name in ("missing", "NotAFunction"):
        with pytest.raises(Invalid):
            callable_ref(tmp_path, "source.py:" + name, source_cache=cache)
    assert len(calls) == 1


def test_source_cache_rereads_changed_bytes_even_with_the_same_mtime(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("def original(): pass\n")
    before = source.stat()
    cache = {}
    callable_ref(tmp_path, "source.py:original", source_cache=cache)
    source.write_text("def replaced(): pass\n")
    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(Invalid):
        callable_ref(tmp_path, "source.py:original", source_cache=cache)
    callable_ref(tmp_path, "source.py:replaced", source_cache=cache)
    source.write_text("def invalid syntax")
    with pytest.raises(Invalid, match="callable:source"):
        callable_ref(tmp_path, "source.py:replaced", source_cache=cache)


def test_source_cache_still_rejects_a_replaced_path_outside_the_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    source = root / "source.py"
    outside = tmp_path / "outside.py"
    source.write_text("def valid(): pass\n")
    outside.write_bytes(source.read_bytes())
    cache = {}
    callable_ref(root, "source.py:valid", source_cache=cache)
    source.unlink()
    source.symlink_to(outside)
    with pytest.raises(Invalid, match="path:containment"):
        callable_ref(root, "source.py:valid", source_cache=cache)


@contextmanager
def isolated_pytest(tmp_path, body, *, formal=False):
    result_file, ledger_file = tmp_path / "allocated.txt", tmp_path / "ledger.txt"
    source = '''\
from pathlib import Path
import os
from harness.temporary import LEDGER_ENV, mkdtemp

def test_owned_directory():
    root = Path(mkdtemp(prefix="lqcd-agent-lifecycle-check-", dir="/private/tmp"))
    Path(RESULT_FILE).write_text(str(root))
    Path(LEDGER_FILE).write_text(os.environ[LEDGER_ENV])
'''.replace("RESULT_FILE", repr(str(result_file))).replace("LEDGER_FILE", repr(str(ledger_file)))
    source += textwrap.indent(textwrap.dedent(body), "    ")
    test = tmp_path / "test_owned.py"
    test.write_text(source)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PYTEST_", "PHASE_B_")) and k != LEDGER_ENV}
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(ROOT / "tests/phase_b") + os.pathsep + str(ROOT / "src"))
    if formal:
        env["PHASE_B_EVIDENCE_REQUEST"] = str(tmp_path / "request.json")
    process = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "harness.temporary",
                              "-p", "no:cacheprovider", str(test)], cwd=tmp_path, env=env,
                             capture_output=True, text=True, timeout=30)
    assert result_file.is_file(), process.stdout + process.stderr
    root, ledger = Path(result_file.read_text()), Path(ledger_file.read_text())
    try:
        yield process, root
    finally:
        # These isolated failure/retention probes own all of these exact paths.
        if ledger.is_file():
            for row in reversed([json.loads(line) for line in ledger.read_text().splitlines()]):
                path = Path(row["path"])
                if path.is_symlink():
                    path.unlink()
                elif path.exists():
                    shutil.rmtree(path)
            shutil.rmtree(ledger.parent)
        saved = root.with_name(root.name + "-original")
        if saved.exists():
            shutil.rmtree(saved)


@pytest.mark.parametrize("mode", ["success", "failure", "formal", "interrupted", "active_child"])
def test_only_successful_ordinary_pytest_cleans_its_directories(tmp_path, mode):
    bodies = {
        "success": 'assert root.is_dir()\n',
        "failure": 'assert False, "retained counterexample"\n',
        "formal": 'assert root.is_dir()\n',
        "interrupted": 'raise KeyboardInterrupt()\n',
        "active_child": 'import multiprocessing, time\nmultiprocessing.get_context("spawn").Process(target=time.sleep, args=(30,), daemon=True).start()\n',
    }
    body = bodies[mode]
    with isolated_pytest(tmp_path, body, formal=mode == "formal") as (process, root):
        assert process.returncode == {"failure": 1, "interrupted": 2}.get(mode, 0), process.stdout + process.stderr
        assert root.exists() == (mode != "success")


def test_spawned_allocations_remain_until_the_owning_pytest_finishes(tmp_path):
    child_output = tmp_path / "child.txt"
    child = "from pathlib import Path; from harness.temporary import mkdtemp; " + \
            f"Path({str(child_output)!r}).write_text(mkdtemp(prefix='lqcd-agent-lifecycle-child-', dir='/private/tmp'))"
    body = f'''
import subprocess, sys
subprocess.run([sys.executable, "-c", {child!r}], check=True)
assert Path(Path({str(child_output)!r}).read_text()).is_dir()
'''
    with isolated_pytest(tmp_path, body) as (process, root):
        assert process.returncode == 0, process.stdout + process.stderr
        assert not root.exists() and not Path(child_output.read_text()).exists()


def test_nested_pytest_keeps_sources_until_its_parent_consumes_them(tmp_path):
    child_output = tmp_path / "nested-child.txt"
    child = f'''from pathlib import Path
from harness.temporary import mkdtemp
def test_child():
    Path({str(child_output)!r}).write_text(mkdtemp(prefix="lqcd-agent-lifecycle-nested-", dir="/private/tmp"))
'''
    body = f'''
import subprocess, sys
child = root / "test_child.py"
child.write_text({child!r})
subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "harness.temporary", "-p", "no:cacheprovider", str(child)], check=True)
assert Path(Path({str(child_output)!r}).read_text()).is_dir()
'''
    with isolated_pytest(tmp_path, body) as (process, root):
        assert process.returncode == 0, process.stdout + process.stderr
        assert not root.exists() and not Path(child_output.read_text()).exists()


def test_cleanup_does_not_follow_a_replaced_directory_symlink(tmp_path):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "protected.txt").write_text("unchanged")
    body = f'''
root.rename(root.with_name(root.name + "-original"))
root.symlink_to({str(foreign)!r}, target_is_directory=True)
'''
    with isolated_pytest(tmp_path, body) as (process, root):
        assert process.returncode == 0, process.stdout + process.stderr
        assert root.is_symlink()
        assert (foreign / "protected.txt").read_text() == "unchanged"
        assert "ownership ledger:" in process.stdout


def test_cleanup_does_not_delete_a_directory_with_replaced_identity(tmp_path):
    body = '''
root.rename(root.with_name(root.name + "-original"))
root.mkdir()
(root / "protected.txt").write_text("replacement is not owned")
'''
    with isolated_pytest(tmp_path, body) as (process, root):
        assert process.returncode == 0, process.stdout + process.stderr
        assert (root / "protected.txt").read_text() == "replacement is not owned"
        assert "ownership ledger:" in process.stdout
