"""Registry for reusable analysis programs."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AnalysisProgram:
    name: str
    category: str
    callable_path: str
    description: str
    tags: tuple[str, ...]
    required_inputs: tuple[str, ...]
    produced_outputs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in ["tags", "required_inputs", "produced_outputs"]:
            payload[key] = list(payload[key])
        return payload


PROGRAMS: tuple[AnalysisProgram, ...] = (
    AnalysisProgram(
        name="single_exponential_effective_mass",
        category="two_point_fit",
        callable_path="lqcd_agent.analysis_programs.two_point_fit.program.single_exponential_effective_mass",
        description="Estimate effective masses from positive two-point correlator values.",
        tags=("two_point", "effective_mass", "correlator"),
        required_inputs=("times", "correlator_values"),
        produced_outputs=("effective_mass_estimates",),
    ),
    AnalysisProgram(
        name="matrix_element_normalization_check",
        category="matrix_element",
        callable_path="lqcd_agent.analysis_programs.matrix_element.program.check_matrix_element_normalization",
        description="Check whether z=0 real matrix elements satisfy a target normalization.",
        tags=("matrix_element", "normalization", "diagnostic"),
        required_inputs=("matrix_elements",),
        produced_outputs=("normalization_diagnostics",),
    ),
)


def available_programs() -> list[AnalysisProgram]:
    return list(PROGRAMS)


def find_programs(*, category: str | None = None, tags: list[str] | tuple[str, ...] | None = None) -> list[AnalysisProgram]:
    requested_tags = set(tags or [])
    matches: list[AnalysisProgram] = []
    for program in PROGRAMS:
        if category is not None and program.category != category:
            continue
        if requested_tags and not requested_tags.issubset(set(program.tags)):
            continue
        matches.append(program)
    return matches


def program_inventory() -> list[dict[str, object]]:
    return [program.to_dict() for program in PROGRAMS]
