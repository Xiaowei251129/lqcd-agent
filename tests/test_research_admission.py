"""Admission preserves frozen project intent and isolates reusable coding bases."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
import sys
from threading import Barrier, Event

import pytest

from lqcd_agent.code_agent.codex_backend import CodexCodingBackend
from lqcd_agent.code_agent.workspace import immutable_git_tree
from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.strict_json import ControlIntegrityError
from lqcd_agent.inspection import host_root, list_runs, read_snapshot
from lqcd_agent.research.projects import ProjectStore
from lqcd_agent.research_codegen import prepare_research
from lqcd_agent.runtime import ApplicationRequest, submit
from tests.support import own


def test_committed_project_admission_replays_frozen_intent_after_local_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("LQCD_AGENT_WORKSPACE", str(tmp_path))
    data = tmp_path / "raw_data" / "fixture.csv"
    data.parent.mkdir()
    data.write_text("x,y\n1,2\n")
    config = {"schema_version": "0.1", "case_id": "project-admission", "source_kind": "synthetic_placeholder",
              "raw_data_path": "raw_data/fixture.csv", "physics_goal": "Check the fixture"}
    store = ProjectStore(tmp_path)
    project = store.create("fixture", "Fixture project", "Inspect a synthetic fixture", config)
    request = ApplicationRequest("run", project=project["id"], project_digest=project["sha256"], key="admit")
    first = submit(request)
    host = own(host_root(first.status["host"]))
    assert first.advance and first.status["run_status"] == "running"
    original = read_snapshot(host, first.status["run_locator"])
    data.unlink()
    store.revise(project["id"], expected_digest=project["sha256"], goal="A future question", case_config=None)

    def no_current_methods(*args, **kwargs):
        raise AssertionError("A committed retry must not refresh method dependencies")

    monkeypatch.setattr("lqcd_agent.research.methods.snapshot_methods", no_current_methods)
    repeated = replace(request, host=first.status["host"])
    again = submit(repeated)
    assert again.status == first.status and not again.advance
    assert list_runs(host) == [original.locator]
    assert read_snapshot(host, original.locator).state["execution_head"] == original.state["execution_head"]
    for change in ({"goal": "Different request"}, {"live": True}, {"project": "another-project"}):
        with pytest.raises(ControlIntegrityError, match="conflicts"):
            submit(replace(repeated, **change))
    with pytest.raises(ControlIntegrityError, match="Project changed"):
        submit(replace(repeated, key="a-new-admission"))
    another = tmp_path / "other-workspace"
    another.mkdir()
    monkeypatch.setenv("LQCD_AGENT_WORKSPACE", str(another))
    with pytest.raises(ControlIntegrityError, match="original operator workspace"):
        submit(repeated)


def test_same_host_keeps_independent_frozen_method_bases_without_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("LQCD_AGENT_WORKSPACE", str(tmp_path))
    def forbidden_dispatch(*args, **kwargs):
        raise AssertionError("Preparing coding inputs must not dispatch a model")
    monkeypatch.setattr(CodexCodingBackend, "dispatch", forbidden_dispatch)
    config = {"generated_program": {"python": sys.executable, "parameters": {}, "requirements": ["Synthetic fixture only"],
                                    "timeout_seconds": 10, "result_kind": "normalization"}}
    host = tmp_path / "host"
    host.mkdir()
    first_code, second_code = b"def ratio(a, b): return a / b\n", b"def ratio(a, b): return (a / b, 'checked')\n"
    def frozen(code):
        return [{"id": "ratio", "source": code.decode(), "source_sha256": sha256(code).hexdigest()}]
    with closing(Coordinator(host, clock=FakeClock(100, 0))) as coordinator:
        first, _ = prepare_research(coordinator, config, workspace=tmp_path, live=True, initialize=True,
                                    method_sources=frozen(first_code))
        second, _ = prepare_research(coordinator, config, workspace=tmp_path, live=True, initialize=True,
                                     method_sources=frozen(second_code))
        restored, _ = prepare_research(coordinator, config, workspace=tmp_path, live=True, initialize=False,
                                       method_sources=frozen(first_code))
        assert first.base_repository != second.base_repository
        assert restored.base_repository == first.base_repository
        assert first.backend.kind == second.backend.kind == "codex"
        assert first.backend.root == second.backend.root
        for prepared, source in ((first, first_code), (second, second_code), (restored, first_code)):
            files = immutable_git_tree(prepared.base_repository, prepared.task_policy["base_revision"])
            assert files["reused/ratio.py"] == source
            assert prepared.task_policy["write_paths"] == ["analysis.py"]
            assert "reused/ratio.py" in prepared.task_policy["read_paths"]


def test_concurrent_research_bases_publish_one_complete_git_tree(tmp_path, monkeypatch):
    from lqcd_agent.code_agent import workspace
    host = tmp_path/"host"
    host.mkdir()
    with closing(Coordinator(host)):
        pass
    config = {"generated_program": {"python": sys.executable, "parameters": {}, "requirements": ["Synthetic fixture"],
                                    "timeout_seconds": 10, "result_kind": "normalization"}}
    bases = host/"research_repositories"
    files = {"analysis.py": b'raise NotImplementedError("Implement the research task")\n'}
    target = bases/workspace.tree_digest(files)
    writing, release = Barrier(3), Event()
    publish = workspace.publish_exact

    def pause_before_git(target_file, content):
        writing.wait(timeout=10)
        assert release.wait(timeout=10)
        return publish(target_file, content)

    def prepare():
        with closing(Coordinator(host)) as coordinator:
            code, _ = prepare_research(coordinator, config, workspace=tmp_path, live=True, initialize=True)
            return code.base_repository, code.task_policy["base_revision"]

    monkeypatch.setattr(workspace, "publish_exact", pause_before_git)
    with ThreadPoolExecutor(2) as pool:
        writers = [pool.submit(prepare) for _ in range(2)]
        try:
            writing.wait(timeout=10)
            assert not target.exists()
        finally:
            release.set()
        first, second = (job.result(timeout=30) for job in writers)
    assert first == second and first[0] == target
    assert immutable_git_tree(*first) == files and list(bases.iterdir()) == [target]
