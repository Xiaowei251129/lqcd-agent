# Research assets and observable contracts

Start with an empty library and create a Project from a case configuration:

```bash
lqcd-agent project-create --id c2-study --title "C2 stability" --goal "Assess excited-state sensitivity" --case-config configs/example.json
lqcd-agent project-show --id c2-study
lqcd-agent run --project c2-study --live --key first-study
```

The example configuration is a fixture; replace it with your intended data and scientific contract. Live mode permits paid model work. A Project can be created without a case configuration to retain its question, but cannot start a numerical Run until configured. The workbench supports version-checked Project edits.

## Acquiring and reviewing assets

The SDK can search local assets, read evidence, query INSPIRE, read arXiv HTML and save a provisional candidate. Explicit operator commands provide the same local asset lifecycle without model calls:

```bash
lqcd-agent library-save --kind wiki --id ratio-notes --title "Ratio analysis notes" --body-file projects/c2-study/notes.md --scope '{"applicability":"specified ensemble and observable"}' --source-url https://arxiv.org/abs/2501.12345 --expected-revision 0
lqcd-agent library-search --query ratio
lqcd-agent library-review --kind wiki --id ratio-notes --status reviewed --rationale "Checked the cited argument within the stated scope" --expected-revision 1
```

The paper ID above is command syntax, not a recommended or verified scientific source. Supply actual inspected sources. Candidate content is not established knowledge. Review records bind the operator's exact decision, version, evidence and rationale; they do not prove a paper's argument.

For a method, create a `method` candidate, put Python code and validation reports inside a Project, then explicitly register it:

```bash
lqcd-agent library-register-method --id correlated-ratio --source projects/c2-study/ratio.py --validation projects/c2-study/validation.json --rationale "Reviewed independent calibration and applicability" --expected-revision 1
```

A validation record must bind `source_sha256`, `passed: true` and a nonempty `checks` list of named passing checks. The operator must establish that those checks were actually executed and sufficient. Registration checks those bindings and Python syntax; it does not execute the method or fabricate validation.

A case may include `method_dependencies: [{"id":"correlated-ratio","revision":2,"sha256":"..."}]`, using the exact current reviewed record returned by registration/search. Admission freezes its code and applicability. Codex may reuse that read-only source while producing the Run's self-contained program. An edited, contested or stale dependency cannot enter a new Run under an old review.

## Replica observables

`generated_program.result_kind` supports `c2`, `normalization` and `replica_observables`. The latter provides an extensible scalar-component result boundary; complex observables should declare separate real and imaginary components sharing their explicitly established replica group.

The frozen JSON input must contain:

```json
{
  "replica_groups": [{"id":"paired","sample_ids":[10,20,30],"method":"bootstrap","provenance":"Describe the original resampling construction and pairing evidence"}],
  "observable_contracts": [{"id":"matrix_real","definition":"Precisely define this scalar observable","unit":"dimensionless","group":"paired","kinematics":{"pz":1,"z":0}}]
}
```

Other input data remain part of the same bound payload. Each output contains exactly `status`, `observables`, `assumptions` and `limitations`. An observable contains `id`, `samples` (`sample_id` and real `value`, or null for failure), `mean` and `error`. Every original ID must occur exactly once. The Host checks the sample mean and sample standard deviation for bootstrap; for jackknife it checks `sqrt((N-1)/N * sum((x-mean)^2))`. A failed jackknife sample or fewer than two valid values requires null estimates. Failed samples require partial status. Missing information requires empty results and explicit limitations.

This contract deliberately fixes those estimators; percentile intervals, bias corrections and other estimators require a separately specified contract. It does not infer independence, physical configuration identity, resampling pairing, correct units or a valid fit model from IDs or arithmetic. Host warnings retain those limitations, and human scientific judgment remains required. It is a numerical interface for broader analyses, not validation of arbitrary lattice QCD workflows.
