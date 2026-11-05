from lqcd_agent.analysis_programs.two_point_fit import single_exponential_effective_mass


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
