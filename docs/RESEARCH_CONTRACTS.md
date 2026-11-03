# Research assets and observable contracts

Start with an empty library and create a Project from an executable case configuration:

```bash
lqcd-agent project-create --id c2-study --title "C2 stability" --goal "Assess excited-state sensitivity" --case-config configs/example.json
lqcd-agent project-show --id c2-study
lqcd-agent run --project c2-study --live --key first-study
```

The example configuration is a fixture; supply your intended data and scientific contract. A Project may retain a question before configuration, but numerical execution requires a configured case. Explicit live activation permits paid API work. The CLI and workbench share the same unattended Host driver and original workspace `.env`.

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
