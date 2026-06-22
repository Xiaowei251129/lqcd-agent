# Evals and Observability

## Evaluation Scope

The Phase 8 evaluation library uses synthetic cases only. It must not depend on real raw numeric data. Raw-data-backed and reference-output-backed cases are deferred until Phase 11, after the data policy and reference-output policy are implemented.

Actual graph runs write artifacts under `<output_root>/<case_id>/<run_id>/`, including repo-local `outputs/<case_id>/<run_id>/` when explicitly requested. The Phase 8 evaluation runner writes its default actual-run artifacts and `evaluation_summary.csv` under `/private/tmp/lqcd-agent-phase8-evaluation`. These actual run directories are not evaluation baselines.

Future curated baselines belong under `evaluation/reference_outputs/`. Expected risk levels, recommended actions, required warnings, and human-gate expectations belong under `evaluation/expected_behavior/`.

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
