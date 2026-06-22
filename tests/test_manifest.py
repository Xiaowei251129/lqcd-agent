import json
from pathlib import Path

from lqcd_agent.tools.manifest import build_manifest, write_manifest_json


def test_manifest_includes_required_provenance_fields(tmp_path: Path) -> None:
    case_config = tmp_path / "case.yaml"
    case_config.write_text('case_id: "case_a"\n', encoding="utf-8")
    output_dir = tmp_path / "case_a" / "run_a"
    output_dir.mkdir(parents=True)
    run_result = output_dir / "run_result.json"
    run_result.write_text('{"run_success": true}\n', encoding="utf-8")
    commands = [
        {
            "command_id": "cmd_001",
            "command": "mock:success",
            "command_kind": "mock",
            "working_directory": str(tmp_path),
            "timeout_seconds": 60,
            "started_at": "2026-06-10T00:00:00+00:00",
            "completed_at": "2026-06-10T00:00:00+00:00",
            "return_code": 0,
            "stdout": "",
            "stderr": "",
            "produced_files": [],
            "status": "passed",
        }
    ]

    manifest = build_manifest(
        run_id="run_a",
        case_id="case_a",
        repo_root=tmp_path,
        run_output_dir=output_dir,
        input_files=[case_config],
        output_files=[run_result],
        commands=commands,
        status="success",
        summary="Recorded provenance.",
    )
    manifest_path = write_manifest_json(output_dir, manifest)
    written = json.loads(Path(manifest_path).read_text(encoding="utf-8"))

    assert written["run_id"] == "run_a"
    assert written["case_id"] == "case_a"
    assert written["git_commit"] == written["git"]["commit"]
    assert "git_status_summary" in written
    assert written["config_hash"]
    assert written["input_files"][0]["sha256"]
    assert written["output_files"][0]["sha256"]
    assert written["commands"] == commands
    assert "python" in written["tool_versions"]
    assert written["environment_summary"]["run_output_dir"] == str(output_dir.resolve())
