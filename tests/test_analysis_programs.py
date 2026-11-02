from lqcd_agent.analysis_programs import program_inventory
from lqcd_agent.analysis_programs.registry import selected_analysis_programs
from lqcd_agent.analysis_programs.matrix_element import check_matrix_element_normalization
from lqcd_agent.analysis_programs.two_point_fit import single_exponential_effective_mass
from lqcd_agent.tools.repo_inventory import build_repo_inventory


def test_program_registry_exposes_reusable_programs() -> None:
    inventory = program_inventory()

    assert any(program["category"] == "two_point_fit" for program in inventory)
    assert any(program["category"] == "matrix_element" for program in inventory)
    selected = selected_analysis_programs(
        {"raw_data_path": "raw_data/matrix.csv", "target_observables": ["normalization_diagnostics"]},
        {"analysis_programs": inventory},
    )
    assert selected[0]["name"] == "matrix_element_normalization_check"
    assert selected[0]["input_mapping"] == {"matrix_elements": "raw_data_csv.rows"}


def test_two_point_effective_mass_program() -> None:
    result = single_exponential_effective_mass([0, 1, 2], [1.0, 0.5, 0.25])

    assert result["status"] == "success"
    assert result["effective_mass_estimates"][0]["effective_mass"] > 0
    assert result["diagnostic_flags"] == []
    assert result["fit_window_diagnostics"]["status"] == "not_evaluated"


def test_two_point_effective_mass_program_flags_fit_window_dependence() -> None:
    result = single_exponential_effective_mass(
        [0, 1, 2, 3],
        [1.0, 0.82, 0.60, 0.385],
        [0.025, 0.030, 0.035, 0.040],
    )

    assert result["status"] == "success"
    assert result["diagnostic_flags"] == ["fit_window_dependence"]
    assert result["fit_window_diagnostics"]["status"] == "warning"
    assert result["fit_window_diagnostics"]["fit_window_dependence"] is True


def test_two_point_effective_mass_program_does_not_flag_noisy_valid_window() -> None:
    result = single_exponential_effective_mass(
        [0, 1, 2, 3],
        [1.0, 0.73, 0.55, 0.40],
        [0.060, 0.065, 0.070, 0.080],
    )

    assert result["status"] == "success"
    assert result["diagnostic_flags"] == []
    assert result["fit_window_diagnostics"]["status"] == "pass"


def test_matrix_element_normalization_program() -> None:
    result = check_matrix_element_normalization(
        [
            {"z": 0, "Pz": 5, "component": "real", "value": 1.01},
            {"z": 1, "Pz": 5, "component": "real", "value": 0.7},
        ]
    )

    assert result["status"] == "success"
    assert result["all_passed"] is True


def test_repo_inventory_guides_codex_to_analysis_programs(tmp_path) -> None:
    inventory = build_repo_inventory(tmp_path)

    assert inventory["analysis_programs"]
    assert "Reuse existing analysis_programs" in inventory["analysis_program_guidance"]
