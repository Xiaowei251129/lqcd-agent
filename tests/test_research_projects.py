"""Projects retain scientific context and evidence without acquiring Run authority."""
from contextlib import closing
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile

import pytest

from lqcd_agent.control.clock import FakeClock
from lqcd_agent.control.coordinator import Coordinator
from lqcd_agent.control.interfaces import StartRunRequest
from lqcd_agent.control.storage import execution_scratch_root
from lqcd_agent.control.strict_json import ControlIntegrityError, canonical_bytes, digest, loads
from lqcd_agent.inspection import read_snapshot
from lqcd_agent.research.projects import ProjectStore
from lqcd_agent.science import ScientificAgent
from tests.support import own


def scientific_run(workspace, store, project, agent_type=ScientificAgent):
    from lqcd_agent.runtime import assemble
    from lqcd_agent.tools.dataset import snapshot_dataset
    config = {"schema_version": "0.1", "case_id": "project-science", "source_kind": "synthetic_placeholder",
              "physics_goal": project["goal"]}
    host = own(Path(tempfile.mkdtemp(prefix="lqcd-agent-host-", dir=execution_scratch_root())))
    with closing(Coordinator(host, clock=FakeClock(100, 0))) as coordinator:
        agent = agent_type(host, config, workspace=workspace)
        runtime, actor, _ = assemble(coordinator, agent, workflow="scientific", initialize=True)
        goal = {"goal": project["goal"], "workflow": "scientific", "live": False, "workspace": str(workspace),
                "case_config": config, "dataset_snapshot": snapshot_dataset(config, workspace),
                "project_id": project["id"], "project_revision": project["revision"],
                "project_sha256": project["sha256"], "project_snapshot": project}
        inputs = {"root_goal": goal, "input_snapshot": {"kind": "scientific_case", "case_config": config}}
        admitted = runtime.plane.start_run(StartRunRequest(config["case_id"], inputs, digest(inputs), "project-start"), actor=actor)
        locator = admitted["result"]["run_locator"]
        runtime.run(locator)
    return read_snapshot(host, locator)


def test_project_metadata_is_versioned_without_run_status(tmp_path):
    store = ProjectStore(tmp_path)
    assert store.list() == []
    project = store.create("ratio-study", "Ratio study", "Can the data distinguish momentum dependence?")
    assert project["case_config"] is None and "run_status" not in project
    assert store.runs(project["id"]) == []
    revised = store.revise(project["id"], expected_digest=project["sha256"], goal="Test a restricted momentum range.",
                           case_config={"schema_version": "0.1"})
    assert store.read(project["id"], 1) == project
    assert store.list() == [revised]
    with pytest.raises(ControlIntegrityError, match="Stale"):
        store.revise(project["id"], expected_digest=project["sha256"], title="Unseen competing edit")
    with pytest.raises(ControlIntegrityError, match="already exists"):
        store.create(project["id"], "Duplicate", "Duplicate")
    with pytest.raises(ControlIntegrityError):
        store.create("../escape", "Escaped", "Invalid path")
    with pytest.raises(ControlIntegrityError, match="text exceeds"):
        store.create("oversize", "Title", "x" * 32001)


def test_closed_run_capture_is_scoped_idempotent_and_readable_without_host(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    project = store.create("ratio-study", "Ratio study", "Inspect synthetic normalization evidence.")
    snapshot = scientific_run(tmp_path, store, project)
    assert snapshot.state["run_status"] == "completed"
    (snapshot.host / ".env").write_text("DO_NOT_CAPTURE=secret")
    (snapshot.root / "unregistered.json").write_text('{"private":"unregistered"}')
    captured = store.capture_run(snapshot)
    index = loads((snapshot.root/'artifact_index.json').read_bytes())
    terminal = loads(Path(index['current']['terminal']['state_paths']['memory_update_path']).read_bytes())
    assert not captured['preliminary'] and captured['outcome_source'] == 'scientific_terminal'
    assert captured['scientific_outcome'] == terminal['scientific_outcome']
    assert captured['decision_origin'] == terminal['decision_origin'] == 'system'
    assert terminal['authorization_decision'] is None
    assert captured["resumable"] is False
    assert any(item["source"] == "scientific" for item in captured["evidence"])
    assert not any(".env" in item["name"] or "unregistered" in item["name"] for item in captured["evidence"])
    assert store.capture_run(snapshot) == captured
    # A later scientific revision must not change the original Run's frozen project.
    store.revise(project["id"], expected_digest=project["sha256"], goal="A different future question.")
    assert store.capture_run(snapshot) == captured

    def unavailable(*args, **kwargs):
        raise AssertionError("Browsing captured evidence must not reopen a Host")

    monkeypatch.setattr("lqcd_agent.research.projects.read_snapshot", unavailable)
    assert store.runs(project["id"]) == [captured]
    for item in captured["evidence"]:
        assert sha256(store.evidence(project["id"], item["sha256"])).hexdigest() == item["sha256"]
    other = store.create("other", "Other", "An unrelated project.")
    with pytest.raises(ControlIntegrityError, match="not registered"):
        store.evidence(other["id"], captured["evidence"][0]["sha256"])


def test_capture_revalidates_supplied_snapshot_and_workspace(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("project", "Project", "A synthetic scientific question.")
    snapshot = scientific_run(tmp_path, store, project)
    forged = replace(snapshot, state={**snapshot.state, "execution_head": "0" * 64})
    with pytest.raises(ControlIntegrityError, match="changed before"):
        store.capture_run(forged)
    foreign = tmp_path / "other-workspace"
    foreign.mkdir()
    other = ProjectStore(foreign)
    other.create("project", "Project", "A synthetic scientific question.")
    with pytest.raises(ControlIntegrityError, match="another project workspace"):
        other.capture_run(snapshot)


@pytest.mark.parametrize("foreign_kind", ["producer", "symlink"])
def test_capture_rejects_cross_producer_and_redirected_scientific_members(tmp_path, foreign_kind):
    class InvalidSidecarAgent(ScientificAgent):
        def run(self, node, context, *, timeout_seconds):
            result = super().run(node, context, timeout_seconds=timeout_seconds)
            if node == "scientific_reviewer":
                foreign = self.host / "domain" / "foreign" / "other" / "run" / "value.json"
                foreign.parent.mkdir(parents=True)
                foreign.write_bytes(canonical_bytes({"private": "other producer"}))
                relative = str(foreign.relative_to(self.host))
                if foreign_kind == "symlink":
                    identity = context["identity"]
                    link = self.host / "domain" / identity["attempt_id"] / identity["case_id"] / identity["run_id"] / "link.json"
                    link.symlink_to(foreign)
                    relative = str(link.relative_to(self.host))
                result["content"]["domain_result"]["member_digests"][relative] = sha256(foreign.read_bytes()).hexdigest()
            return result

    store = ProjectStore(tmp_path)
    project = store.create("project", "Project", "Validate capture scope.")
    snapshot = scientific_run(tmp_path, store, project, InvalidSidecarAgent)
    with pytest.raises(ControlIntegrityError, match="producer scope"):
        store.capture_run(snapshot)
    assert store.runs(project["id"]) == []


def test_captured_blob_tampering_does_not_change_recorded_result(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("project", "Project", "Retain scientific evidence.")
    captured = store.capture_run(scientific_run(tmp_path, store, project))
    identifier = captured["evidence"][0]["sha256"]
    path = tmp_path / "projects" / project["id"] / "evidence" / identifier
    path.write_bytes(b"changed")
    with pytest.raises(ControlIntegrityError, match="digest changed"):
        store.evidence(project["id"], identifier)
    assert store.runs(project["id"])[0]["sha256"] == captured["sha256"]
