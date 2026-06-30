# Evals and Observability

## Evaluation Scope

The Phase 8 evaluation library uses synthetic cases only. It must not depend on real raw numeric data. Raw-data-backed and reference-output-backed cases are deferred until Phase 11, after the data policy and reference-output policy are implemented.

Actual graph runs write artifacts under `<output_root>/<case_id>/<run_id>/`, including repo-local `outputs/<case_id>/<run_id>/` when explicitly requested. The Phase 8 evaluation runner writes its default actual-run artifacts and `evaluation_summary.csv` under `/private/tmp/lqcd-agent-phase8-evaluation`. These actual run directories are not evaluation baselines.

Future curated baselines belong under `evaluation/reference_outputs/`. Expected risk levels, recommended actions, required warnings, and human-gate expectations belong under `evaluation/expected_behavior/`.

## Phase 10C Advisor-demo Benchmark

Phase 10C was implemented on 2026-06-23 as a separate advisor-demo benchmark
from the Phase 8 synthetic good/ambiguous/bad evaluation library. Phase 8 checks
existing mock workflow behavior. Phase 10C demonstrates the provider-backed
multi-agent system on controlled synthetic scientific scenarios with hidden
expected behavior and teacher-readable actual-vs-expected conclusions.

Phase 10C scenarios live under `evaluation/synthetic_benchmarks/`:

- `scenarios/*.input.json` contains agent-visible scenario metadata.
- `data/*.csv` contains small synthetic fixtures.
- `expected/*.expected.json` contains instructor-only expected behavior.
- `case_sets/demo.json` and `case_sets/full.json` select scenario groups.

The demo case set covers clean synthetic fit, noisy valid fit, fit-window
contamination, normalization violation, and targeted rerun. The full set also
covers plateau instability, invalid uncertainty, missing input, and a controlled
code-fix branch.

Each scenario should provide or generate synthetic data that the Analysis
Engineer consumes to produce case-specific analysis and fit artifacts. The
existing fixed mock matrix-element payload is not sufficient as the satisfying
output for Phase 10C advisor-demo scenarios.

Instructor-only expected behavior is stored as expected sidecar JSON and is not
passed to agents as input. Expected behavior defines the expected qualitative
conclusion, numeric tolerances where applicable, expected risk and recommended
action, expected graph route, required or forbidden reviewer warnings, expected
memory status, and Human Approval Gate expectations.

Phase 10C validates whether the system can reason over controlled artifacts and
reach the right structured conclusion. It does not validate final LQCD physics
claims, accepted real-data results, paper-level conclusions, or Phase 11
raw-data-backed evidence chains.

Required Phase 10C advisor-facing outputs:

- `synthetic_rehearsal_summary.md`
- live-provider-only `advisor_demo_report.md`
- per-scenario `analysis_outputs/synthetic_benchmark_input.json`
- generated or provided synthetic data artifact
- case-specific analysis and fit summary artifacts
- per-scenario demonstration checklist with actual-vs-expected status
- route trace and artifact inspection paths

The live-provider benchmark must be explicitly enabled and must not run during
ordinary tests. The mock-provider benchmark remains the network-free regression
mode for normal development and CI-style checks.

Run the mock-provider demo benchmark with:

```bash
python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py --provider mock --case-set demo --output-dir /private/tmp/lqcd-agent-phase10c-mock
```

Run the full mock-provider suite with `--case-set full`. The optional
live-provider rehearsal requires explicit opt-in:

```bash
RUN_LIVE_LLM_TESTS=1 python evaluation/synthetic_benchmarks/run_synthetic_benchmarks.py \
  --provider-config <phase10b-provider-config> \
  --case-set demo \
  --output-dir /private/tmp/lqcd-agent-phase10c-live
```

## Required Synthetic Cases

Good case:

- Structured matrix elements are internally consistent versus `z` and `Pz`.
- Expected risk: low.
- Expected route: Memory and Report Node without approval packet.
- Expected memory: accepted.

Ambiguous case:

- Matrix elements contain mild warnings or incomplete evidence.
- Expected risk: medium.
- Expected route: Memory and Report Node with pending or review-recommended status.
- Expected memory: pending.

Bad case:

- Matrix elements contain severe diagnostic flags or inconsistent behavior.
- Expected risk: high.
- Expected route: Human Approval Gate with approval packet.
- Expected memory: pending memory/report artifacts with `accepted_result: false` until a valid human decision allows a different category.

Run the synthetic cases with:

```bash
python evaluation/run_evaluation.py
```

The evaluation runner refuses to delete an existing case/run directory by default.
Use a new run id prefix or pass `--force-clean` only when replacing synthetic
evaluation artifacts is intentional.

## Observability Artifacts

Each run should expose:

- graph-state snapshot or summary
- checkpoint metadata
- node transition log
- routing decisions
- command provenance
- warnings and errors
- artifact paths
- decision rationale

## Metrics

Initial metrics:

- case status
- risk level
- approval required
- node retry count
- command success rate
- artifact validation status
- warning count by severity
- context-window status

## Future Raw-data-backed Evals

Phase 11 may add raw-data-backed or reference-output-backed evaluations only after:

- raw-data manifests and checksums are defined
- raw numeric data access is explicitly approved
- reference outputs are versioned or append-only
- expected behavior is stored outside `raw_data/`
- reference outputs are kept separate from `outputs/` actual-run artifacts

## Related Documents

- [Project Specification](PROJECT_SPEC.md)
- [Architecture](ARCHITECTURE.md)
- [Verification Guide](VERIFICATION_GUIDE.md)
- [Security and Data Policy](SECURITY_AND_DATA_POLICY.md)
