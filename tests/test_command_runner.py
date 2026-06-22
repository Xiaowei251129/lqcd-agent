import json
import shlex
import sys
from pathlib import Path

from lqcd_agent.tools.command_runner import run_command


def test_mock_command_writes_synthetic_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "case_a" / "run_a"

    result = run_command(
        command="mock:write_synthetic_matrix_elements",
        cwd=tmp_path,
        output_dir=output_dir,
        run_id="run_a",
        case_id="case_a",
    )
    output = output_dir / "analysis_outputs" / "synthetic_matrix_elements.json"
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["status"] == "passed"
    assert result["return_code"] == 0
    assert result["produced_files"] == [str(output)]
    assert payload["source_kind"] == "synthetic"


def test_golden_mock_command_writes_synthetic_output_with_high_risk_flag(tmp_path: Path) -> None:
    output_dir = tmp_path / "l64c64a076_m140" / "golden"

    result = run_command(
        command="mock:write_golden_example_matrix_elements",
        cwd=tmp_path,
        output_dir=output_dir,
        run_id="golden",
        case_id="l64c64a076_m140",
    )
    output = output_dir / "analysis_outputs" / "synthetic_matrix_elements.json"
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["status"] == "passed"
    assert payload["source_kind"] == "synthetic"
    assert payload["golden_example"]["case_id"] == "l64c64a076_m140"
    assert "severe_demo_requires_human_approval" in payload["diagnostic_flags"]


def test_local_command_requires_exact_allowlist(tmp_path: Path) -> None:
    result = run_command(
        command="python -c 'print(1)'",
        cwd=tmp_path,
        output_dir=tmp_path / "case_a" / "run_a",
        run_id="run_a",
        case_id="case_a",
    )

    assert result["status"] == "blocked"
    assert result["return_code"] is None
    assert "allowlist" in result["stderr"]


def test_configured_local_command_records_produced_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "case_a" / "run_a"
    script = tmp_path / "write_output.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)\n"
        "Path(sys.argv[1]).write_text('ok\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    output = output_dir / "analysis_outputs" / "local.txt"
    command = shlex.join([sys.executable, str(script), str(output)])

    result = run_command(
        command=command,
        cwd=tmp_path,
        output_dir=output_dir,
        run_id="run_a",
        case_id="case_a",
        allowed_commands=[command],
    )

    assert result["status"] == "passed"
    assert result["return_code"] == 0
    assert result["produced_files"] == [str(output)]
