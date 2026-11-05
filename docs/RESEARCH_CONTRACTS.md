# Research assets and observable contracts

Start with an empty library and create a Project with a question and optional starting inputs:

```bash
lqcd-agent project-create --id c2-study --title "C2 stability" --goal "Assess excited-state sensitivity" --data-path raw_data/c2.json --source-kind measured_lattice_data --python /absolute/scientific/python3
lqcd-agent project-show --id c2-study
lqcd-agent run --project c2-study --live --key first-study
```

A Project may begin without a data path or executable configuration. Explicit live activation permits paid PI/Postdoc preparation and subsequent authorized analysis. The CLI and workbench share the same unattended Host driver and original workspace `.env`. `configs/example.json` remains a fixture, not measured C2 data.

## Research intake and clarification

`run --project` first profiles only the declared data, then PI frames the question and Postdoc proposes a supported method and missing analysis parameters. Source provenance, sample identities, physical definitions, supplied parameter values and executable paths are not model-editable. Missing metadata can be explicitly supplied by the operator in the starting configuration; it cannot overwrite source data fields. C2, Normalization and replica-observable JSON contracts and configured registered CSV programs are supported. Other formats remain explicit missing-input questions; this is not a universal file importer.

The starting `case_config` can be partial, for example:

```json
{"raw_data_path":"raw_data/c2.json","source_kind":"measured_lattice_data","generated_program":{"python":"/absolute/scientific/python3"}}
```

Use the actual source provenance; `--source-kind` and the workbench's **Data provenance** field set this declaration explicitly, without a default. A free-text scientific reply does not replace missing structured metadata. The scientific interpreter may also already exist at the workspace's `.runtime/bin/python3`. The Host profiles fields, dimensions and metadata without putting the correlator arrays into PI/Postdoc input. Model assumptions and unresolved questions remain recorded evidence. Natural-language scientific constraints inform the plan; only supported structured contracts have deterministic enforcement.

A `ready` preparation automatically admits the formal scientific Run from its sealed configuration. The original Project remains unchanged; the prepared configuration is inspectable in its Plan evidence. `needs_information` records specific questions and closes the preparation without physics acceptance or a lease waiting for a reply. Human scientific participation remains optional. Reply in the workbench or CLI, update missing input fields if needed, then explicitly continue:

```bash
lqcd-agent project-show --id c2-study
lqcd-agent project-contribute --id c2-study --expected-digest PROJECT_SHA256 --key reply-one --body "The requested scientific clarification."
lqcd-agent run --project c2-study --host HOST --case CASE --intake-parent PREPARATION_RUN --live --key continue-one
```

Continue uses the original task's remaining Run/model/token quota and original deadline. Every preparation, clarification and scientific Run uses one of the same four Run slots. A comment alone never starts a model, changes a frozen Run, grants permissions or renews the task. If the task is exhausted or expired, a deliberate new investigation is required. Existing evidence stays immutable. Offline preparation identifies disabled live research and does not simulate model readiness.

Scientific Code can test its current source with `run_numerical_trial`. Its small synthetic input and actual execution feedback are recorded in the Code bundle. The tool cannot select an interpreter, a data file, a shell command or additional permissions. Trials aid debugging; the final sealed program still runs through formal Analysis and review. Changing a scientific method must remain explicit in the plan/experiment record.

## Conclusions and additional experiments

Research can end without a Human Response. Terminal artifacts distinguish `supported`, `qualified` and `inconclusive` outcomes, actual decision provenance and remaining limitations. Optional operator input is scientific evidence, not execution authorization. Additional authority uses the original scoped pause/response mechanism.

The PI's final review discussion can include `next_experiment`, with `question`, `rationale`, `parameter_changes` (a list of `name` and JSON-string `value_json`) and `method_ids`. Supported changes create a linked Run through the existing Host. Dataset bytes, interpreter and permissions remain unchanged; selected methods must be reviewed local sources. Every child consumes the original shared task quota. Unsupported scope, repeated parameters, or exhausted resources leave a recorded unexecuted-proposal reason. Existing results remain immutable.

## Acquiring and reviewing assets

Roles can search the local library, query INSPIRE, read arXiv HTML and save candidates. Independent later-attempt reviewers can use `review_asset` with evidence IDs actually obtained from their reads. Candidates remain provisional until their exact version is reviewed. Human review is optional and records the actual operator identity.

The equivalent operator commands are:

```bash
lqcd-agent library-save --kind wiki --id ratio-notes --title "Ratio analysis notes" --body-file projects/c2-study/notes.md --scope '{"applicability":"specified ensemble and observable"}' --source-url https://arxiv.org/abs/2501.12345 --expected-revision 0
lqcd-agent library-search --query ratio
lqcd-agent library-review --kind wiki --id ratio-notes --status reviewed --rationale "Checked the cited argument within the stated scope" --expected-revision 1
```

The paper ID is command syntax, not a recommended or inspected scientific source. Supply actual sources. Textual review records bind source, scope, reviewer and rationale; they do not prove a paper's argument.

For a method, first create a `method` candidate, then supply project Python source implementing a supported family:

```bash
lqcd-agent library-register-method --id c2-fit --source projects/c2-study/analysis.py --family c2 --python /absolute/scientific/python3 --rationale "Independent calibration within the declared scope" --expected-revision 1
```

Registration executes the Host's independent finite C2 or Normalization cases in the scientific sandbox and binds exact program bytes, validator, numerical execution and scientific interpreter identity. It rejects uploaded validation JSON as proof. The same requirement applies to automatic method review. Unsupported generic methods remain candidates; passing these finite cases is not universal physics certification.

A case may include `method_dependencies: [{"id":"c2-fit","revision":2,"sha256":"..."}]`, using the exact reviewed record returned by registration/search. Admission freezes code and applicability as read-only coding inputs. Codex produces the Run's self-contained program. An edited, contested or stale dependency cannot reuse an old review.

## Replica observables

`generated_program.result_kind` supports `c2`, `normalization` and `replica_observables`. The latter is an extensible scalar-component result boundary; complex quantities declare separate real and imaginary components sharing their established replica group.

The frozen input must contain:

```json
{
  "replica_groups": [{"id":"paired","sample_ids":[10,20,30],"method":"bootstrap","provenance":"Describe original resampling construction and pairing evidence"}],
  "observable_contracts": [{"id":"matrix_real","definition":"Precisely define this scalar observable","unit":"dimensionless","group":"paired","kinematics":{"pz":1,"z":0}}]
}
```

Other data remain part of the same bound payload. Each output contains exactly `status`, `observables`, `assumptions` and `limitations`. An observable contains `id`, `samples` (`sample_id` and real `value`, or null for failure), `mean` and `error`. Every original ID occurs exactly once. Host checks use the sample mean and sample standard deviation for bootstrap, or `sqrt((N-1)/N * sum((x-mean)^2))` for jackknife. A failed jackknife sample or fewer than two valid values requires null estimates. Failed samples require partial status; missing information requires empty results and explicit limitations.

Other estimators need an explicitly specified contract. IDs and arithmetic do not establish physical independence, original resampling pairing, units or fit suitability. The autonomous report must retain these limitations and can conclude inconclusively. This interface does not qualify arbitrary lattice QCD workflows.
