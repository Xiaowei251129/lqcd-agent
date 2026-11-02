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
    csv_inputs: tuple[tuple[str, str], ...]
    optional_csv_inputs: tuple[tuple[str, str], ...]
    text_columns: tuple[str, ...]
    produced_outputs: tuple[str, ...]

    @property
    def required_inputs(self):
        return tuple(name for name, _ in self.csv_inputs)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["required_inputs"] = list(self.required_inputs)
        payload["csv_inputs"] = dict(self.csv_inputs)
        payload["optional_csv_inputs"] = dict(self.optional_csv_inputs)
        for key in ("tags", "produced_outputs", "text_columns"):
            payload[key] = list(payload[key])
        return payload


PROGRAMS: tuple[AnalysisProgram, ...] = (
    AnalysisProgram(
        name="single_exponential_effective_mass",
        category="two_point_fit",
        callable_path="lqcd_agent.analysis_programs.two_point_fit.program.single_exponential_effective_mass",
        description="Estimate effective masses from positive two-point correlator values.",
        tags=("two_point", "effective_mass", "correlator"),
        csv_inputs=(("times", "t"), ("correlator_values", "value")),
        optional_csv_inputs=(("correlator_errors", "error"),),
        text_columns=(),
        produced_outputs=("effective_mass_estimates",),
    ),
    AnalysisProgram(
        name="matrix_element_normalization_check",
        category="matrix_element",
        callable_path="lqcd_agent.analysis_programs.matrix_element.program.check_matrix_element_normalization",
        description="Check whether z=0 real matrix elements satisfy a target normalization.",
        tags=("matrix_element", "normalization", "diagnostic"),
        csv_inputs=(("matrix_elements", "rows"),),
        optional_csv_inputs=(),
        text_columns=("component",),
        produced_outputs=("normalization_diagnostics",),
    ),
)


def available_programs() -> list[AnalysisProgram]:
    return list(PROGRAMS)


def program_inventory() -> list[dict[str, object]]:
    return [program.to_dict() for program in PROGRAMS]


def requested_programs(config):
    def values(value):
        return [str(item).strip() for item in value] if isinstance(value, list) else [str(value).strip()] if value else []
    tags = values(config.get('analysis_program_tags'))
    outputs = values(config.get('target_observables'))
    return set(filter(None, tags)), set(filter(None, outputs))


def canonical_program_selection(program, config, inventory=None):
    if not config.get('raw_data_path'):
        return None
    descriptor = next((item for item in PROGRAMS if item.name == program.get('name') and
                       item.callable_path == program.get('callable_path')), None)
    if descriptor is None:
        return None
    mapping = {key: 'raw_data_csv.' + column for key, column in descriptor.csv_inputs}
    columns = ((inventory or {}).get('dataset_snapshot') or {}).get('columns', [])
    mapping.update((key, 'raw_data_csv.' + column) for key, column in descriptor.optional_csv_inputs
                   if column in columns)
    return {'name': descriptor.name, 'category': descriptor.category, 'callable_path': descriptor.callable_path,
            'input_mapping': mapping, 'output_path': 'analysis_outputs/'+descriptor.produced_outputs[0]+'.json',
            'required_outputs': list(descriptor.produced_outputs)}


def matching_programs(case_config, repo_inventory):
    tags, outputs = requested_programs(case_config)
    return [program for program in repo_inventory.get('analysis_programs', []) if isinstance(program, dict) and
            ((tags and tags <= set(program.get('tags', []))) or outputs.intersection(program.get('produced_outputs', [])))]


def selected_analysis_programs(case_config, repo_inventory):
    return [choice for program in matching_programs(case_config, repo_inventory)
            if (choice := canonical_program_selection(program, case_config, repo_inventory)) is not None]
