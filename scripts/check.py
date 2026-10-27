"""Run relevant tests or the current integration profile once."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/bin/python"
if Path(sys.executable).absolute() != PYTHON:
    os.execv(str(PYTHON), [str(PYTHON), "-B", str(Path(__file__).resolve()), *sys.argv[1:]])
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.update(PYTHONDONTWRITEBYTECODE="1", RUN_LIVE_LLM_TESTS="0", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                  PATH=str(PYTHON.parent) + os.pathsep + os.environ.get("PATH", ""))
from lqcd_agent.control.storage import execution_scratch_root
CORE = [
 "tests/test_cli.py::test_cli_rejects_caller_authority_and_root_escape[arguments0-Invalid controlled Host identifier-1]",
 "tests/test_cli.py::test_multiple_runs_same_host_and_exact_repeated_start",
 "tests/test_durability.py::test_closed_coordinator_schema_and_consistent_backup",
 "tests/test_durability.py::test_closed_overlay_and_guarded_branch",
 "tests/test_durability.py::test_exact_publication_rejects_conflict_partial_and_link",
 "tests/test_durability.py::test_fresh_process_crash_materializes_only_committed_plan",
 "tests/test_durability.py::test_operation_lease_fences_old_epoch_and_queries_do_not_renew",
 "tests/test_durability.py::test_reservation_replay_and_conflict",
 "tests/test_durability.py::test_two_process_reservation_arbitration[False]",
 "tests/test_scratch.py::test_invalid_linux_parent_is_refused_without_fallback[symlink]",
 "tests/test_storage.py::test_actual_native_profile_keeps_wal_full_and_foreign_keys",
 "tests/test_storage.py::test_changed_admission_is_rejected_before_sqlite_changes[host_boot_id]"]

def identity():
    files = [p for base in ("src", "tests", "contracts", "configs", "scripts") for p in (ROOT/base).rglob("*")
             if p.is_file() and p.name != ".DS_Store" and "__pycache__" not in p.parts and not p.suffix == ".pyc" and not any(x.endswith(".egg-info") for x in p.parts)]
    files += [ROOT/name for name in ("pyproject.toml", "requirements.lock", "setup.py", "MANIFEST.in", ".github/workflows/check.yml")]
    return hashlib.sha256(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted(files)},sort_keys=True).encode()).hexdigest()

def write_ci_evidence(output, report, rows):
    """Export only test outcomes; detailed errors and runtime files stay local."""
    summary = {key: report.get(key) for key in
               ("mode", "passed", "selected", "source_sha256", "elapsed_seconds")}
    summary["benchmark_passed"] = report.get("benchmark", {}).get("passed")
    (output/"ci-summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    suite = ET.Element("testsuite", name="offline", tests=str(len(rows)))
    for row in rows:
        case = ET.SubElement(suite, "testcase", {key: row.attrib[key] for key in
                            ("name", "classname", "time") if key in row.attrib})
        for tag in ("failure", "error", "skipped"):
            if row.find(tag) is not None:
                ET.SubElement(case, tag)
    ET.ElementTree(suite).write(output/"ci-junit.xml", encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--integration", action="store_true")
    args = parser.parse_args()
    if args.integration and args.paths:parser.error("Choose integration or explicit test targets")
    for target in args.paths:
        path=(ROOT/target.split("::",1)[0]).resolve()
        if not path.exists() or not path.is_relative_to(ROOT/"tests"):parser.error("Targets must be under tests/")
    scratch=execution_scratch_root();os.environ["TMPDIR"]=str(scratch)
    run=Path(tempfile.mkdtemp(prefix="lqcd-agent-check-",dir=scratch))
    report={"mode":"integration" if args.integration else "targeted" if args.paths else "core", "passed":False,
            "created_utc":datetime.now(timezone.utc).isoformat(), "root":str(run)}
    started=time.monotonic()
    rows = []
    try:
        subprocess.run([str(PYTHON),"scripts/generate_protocol.py","--check"],check=True)
        subprocess.run([str(PYTHON),"scripts/build_manifest.py"],check=True)
        if args.integration:report["source_sha256"]=identity()
        import pytest
        class Selection:
            nodes=[]
            def pytest_collection_modifyitems(self,items):
                unique={i.nodeid:i for i in items};items[:]=[unique[n] for n in sorted(unique)];self.nodes=[i.nodeid for i in items]
        plugin=Selection();xml=run/"pytest.xml"
        paths=args.paths or (["tests"] if args.integration else CORE)
        code=pytest.main(["-q","--tb=short","-o","xfail_strict=true","--basetemp",str(run/"pytest"),"--junitxml",str(xml),*paths],plugins=[plugin])
        rows=ET.parse(xml).findall(".//testcase") if xml.exists() else []
        report.update(selection=plugin.nodes,selected=len(plugin.nodes),junit=str(xml),exit_code=int(code))
        report["passed"]=bool(code==0 and rows and len(rows)==len(plugin.nodes) and all(not any(c.tag in {"failure","error","skipped"} for c in r) for r in rows))
        if not args.paths:report["passed"]=report["passed"] and set(CORE)<=set(plugin.nodes)
        if args.integration and report["passed"]:
            from lqcd_agent.benchmark import run_benchmark
            report["benchmark"]=run_benchmark()
            (run/"benchmark.json").write_text(json.dumps(report["benchmark"],indent=2)+"\n")
            report["passed"]=report["benchmark"]["passed"] and identity()==report["source_sha256"]
    except Exception as error:
        report.update(passed=False,error=str(error));(run/"exception.txt").write_text(traceback.format_exc())
    report["elapsed_seconds"]=time.monotonic()-started
    (run/"result.json").write_text(json.dumps(report,indent=2)+"\n")
    output=ROOT/"check-results";output.mkdir(exist_ok=True)
    for name in (["latest","integration"] if args.integration else ["latest"]):
        stage=output/(name+".new");stage.write_text(json.dumps(report,indent=2)+"\n");stage.replace(output/(name+".json"))
    write_ci_evidence(output, report, rows)
    print(f"{report['mode']}: {'PASS' if report['passed'] else 'FAIL'}; {report.get('selected',0)} tests; {report['elapsed_seconds']:.2f}s; {run/'result.json'}",flush=True)
    return 0 if report["passed"] else 1

if __name__=="__main__":raise SystemExit(main())
