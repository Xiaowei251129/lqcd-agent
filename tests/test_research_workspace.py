"""Operator commands create local assets and bind review to exact project evidence."""
import json
import sys

import pytest

from lqcd_agent.cli import main
from tests.support import command


def save_arguments(kind="wiki", asset_id="correlated-ratio"):
    return ("library-save", "--kind", kind, "--id", asset_id, "--title", "Correlated ratio",
            "--body-file", "note.md", "--scope", '{"ensemble":"fixture"}',
            "--source-url", "https://example.org/method")


def test_operator_project_and_library_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("LQCD_AGENT_WORKSPACE", str(tmp_path))
    assert command("project-list") == []
    assert command("library-search") == []
    assert not (tmp_path / "library").exists()
    project = command("project-create", "--id", "ratio", "--title", "Ratio study", "--goal", "Check correlation")
    assert project["case_config"] is None
    assert command("project-show", "--id", "ratio") == {"project": project, "runs": []}
    (tmp_path / "case.yaml").write_text("case_id: configured\ndata: {}\n")
    configured = command("project-create", "--id", "configured", "--title", "Configured",
                         "--goal", "Analyze", "--case-config", "case.yaml")
    assert configured["case_config"] == {"case_id": "configured", "data": {}}
    (tmp_path / "note.md").write_text("The correlated fixture preserves sample correspondence.")
    saved = command(*save_arguments())
    assert saved["status"] == "candidate"
    assert command("library-search", "--query", "correlated", "--status", "reviewed") == []
    reviewed = command("library-review", "--kind", "wiki", "--id", saved["id"], "--status", "reviewed",
                       "--rationale", "Read the referenced method; fixture applicability only.", "--expected-revision", "1")
    assert reviewed["status"] == "reviewed" and reviewed["review"]["actor"] == "operator"
    receipt = tmp_path / reviewed["review"]["record"]["path"]
    assert receipt.parent == tmp_path / "library" / "reviews"
    assert json.loads(receipt.read_bytes())["revision"] == 1
    command("library-review", "--kind", "wiki", "--id", saved["id"], "--status", "reviewed",
            "--rationale", "Stale", "--expected-revision", "1", expected_exit=1, rejection="Stale")
    edited = command(*save_arguments(), "--expected-revision", "2")
    assert edited["status"] == "candidate" and edited["review"] is None


def test_operator_method_registration_executes_independent_calibration(tmp_path, monkeypatch):
    from tests.test_research_library import method_program
    monkeypatch.setenv("LQCD_AGENT_WORKSPACE", str(tmp_path))
    (tmp_path / "note.md").write_text("Method for the stated finite normalization contract.")
    command(*save_arguments("method"))
    project = tmp_path / "projects" / "ratio"
    project.mkdir(parents=True)
    source = method_program()
    (project / "method.py").write_bytes(source)
    registered = command("library-register-method", "--id", "correlated-ratio", "--source", "projects/ratio/method.py",
                         "--family", "normalization", "--python", sys.executable,
                         "--rationale", "Finite executed registration", "--expected-revision", "1")
    assert registered['registered'] and registered['asset']['status']=="reviewed"
    asset = registered['asset']
    assert (tmp_path / asset["implementation"]["path"]).read_bytes() == source
    receipt = json.loads((tmp_path / asset["review"]["record"]["path"]).read_bytes())
    assert receipt['origin']=='human' and len(receipt['evidence'])==2
    command("library-register-method", "--id", "correlated-ratio", "--source", "note.md",
            "--family", "normalization", "--python", sys.executable, "--rationale", "Wrong scope",
            "--expected-revision", "2", expected_exit=1, rejection="project file")


def test_operator_rejects_private_paths_symlinks_and_forged_actor(tmp_path, monkeypatch):
    monkeypatch.setenv("LQCD_AGENT_WORKSPACE", str(tmp_path))
    (tmp_path / ".env").write_text("private")
    (tmp_path / "note.md").symlink_to(tmp_path / ".env")
    command(*save_arguments(), expected_exit=1, rejection="Redirected")
    (tmp_path / "note.md").unlink()
    (tmp_path / "note.md").write_text("A candidate")
    command(*save_arguments(), "--body-file", ".env", expected_exit=1, rejection="Hidden")
    command(*save_arguments(), "--scope", '{"a":1,"a":2}', expected_exit=1, rejection="Duplicate")
    command("library-review", "--kind", "wiki", "--id", "missing", "--status", "reviewed",
            "--rationale", "Forged", "--expected-revision", "1", "--actor", "reviewer-model",
            expected_exit=2, rejection="unrecognized arguments")
    assert not (tmp_path / "library" / "wiki" / "correlated-ratio").exists()


def test_run_parser_accepts_project_without_case_config(monkeypatch, capsys):
    import lqcd_agent.runtime
    requests = []
    monkeypatch.setattr(lqcd_agent.runtime, "execute", lambda request: requests.append(request) or {"dispatched": True})
    assert main(["run", "--project", "ratio", "--key", "next"]) == 0
    assert requests[0].project == "ratio" and requests[0].case_config is None
    assert json.loads(capsys.readouterr().out) == {"dispatched": True}
    with pytest.raises(SystemExit) as exited:
        main(["library-review", "--kind", "wiki", "--id", "entry", "--status", "candidate",
              "--rationale", "Not a review", "--expected-revision", "1"])
    assert exited.value.code == 2
