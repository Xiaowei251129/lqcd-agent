# C2 and Normalization research cases

These first cases assess independently written Codex programs on measured-derived inputs. Their source is the operator's `1-c2pt-fit`, `2-bm-new` and `3-normalize-new` analysis outputs. No original data or notebooks are modified. No calculation calls or imports the original `lqcd-analysis` package.

| Case | Task | Required interpretation |
| --- | --- | --- |
| `c2-fit-comparison` | Compare correlated one/two-state symmetric fits over adjacent windows, using all configurations and 200 bootstrap replicas. | Explain covariance handling, failures, uncertainty and window/model assumptions; a preferred fit needs scientific review. |
| `c2-dispersion-constraint` | Repeat with the ground energy fixed from the supplied rest energy and momentum. | The imposed energy is not an independent validation of dispersion; uncertainty is conditional on that scalar constraint. |
| `normalization-complex` | Compute complex mode2/mode3 ratios on paired replicas before reporting components and percentile uncertainties. | Preserve sample IDs and reference identity. |
| `normalization-missing-reference` | Remove the prescribed zero-momentum reference from the extracted assessment input. | Report missing information without invented values or successful normalization. |

The task definitions and JSON interfaces live in `lqcd_agent.research_cases`. C2 uses the full `pz=6` CSV with source-column configuration identity, `Nt=64`, binsize 10, seed 2026, 200 resamples and inclusive windows `[4,13]`, `[5,13]`, `[6,13]`. Normalization retains both complex components and original replica IDs at `pz=0,6`, `bT=0,2`, `bz=0,2,4`. It retains failed observations rather than silently discarding or replacing them. Published replica IDs do not independently prove the unavailable original resampling-index plan; that remains a scientific provenance limit.

## Private input extraction

Run from the operator workspace using its `.venv`:

```bash
python -m lqcd_agent.research_cases extract \
  --project /path/to/analysis_l64c64a076_m140_src5 \
  --correlator /path/to/c2pt_5_5_k6_pz6_real.csv
python -m lqcd_agent.research_cases verify
```

The single pack is `raw_data/research_cases/`, excluded from Git. Extraction refuses overwrites, checks source bytes before/after, preserves replica identities and separates inputs from withheld reference outputs. The manifest binds asset hashes and records source paths/hashes locally. Existing results are comparison evidence, not certified physics truth. Keep this pack and detailed assessment outputs private.

## Codex programming and assessment

Research coding uses the same CodeHost, external-operation ownership, final proposal validation, syntax verification and CLI Resume protocol as the existing coding example. Its profiles are `research-c2` and `research-normalization`. Explicit live use incurs API charges. The model receives schema, mathematical requirements, synthetic calibration and a blank `analysis.py`; measured inputs, references and the existing analysis implementation are withheld. Tools, network access and automatic approval review are enabled for coding. Task deadlines and budget limits still apply.

After verified Code delivery, the canonical Run pauses for human input; the trusted preparation does not execute arbitrary research Python in the Host interpreter. The independent assessment command consumes only a current successful Code artifact and materializes its exact verified source into a separate sandbox:

```bash
python -m lqcd_agent.research_evaluation \
  --host HOST --case CASE --run RUN --family c2 \
  --python /path/to/trusted/python-with-numpy-and-scipy
```

Use `--family normalization` for the other program. The operator-selected scientific interpreter is separate from the core application's locked dependencies; its path/runtime roots are recorded with execution evidence. It must already contain the packages required by the generated program.

Start generation with `python -m lqcd_agent start --workflow research-c2 --live --key first-c2` (or `research-normalization`). Use the returned Host/Run/Pause identities with the normal `status` and `resume` commands to deliver a completed coding operation promptly. Status is read-only and does not renew the lease. Coding has a 600-second task deadline and a 660-second worker lease. An expired operation must follow canonical cancellation/recovery; never extend or forge its old authority. These are fixed task fixtures, not live scientific planning/review agents.

Successful numerical output uses `status=ok`; C2 may report `partial` with explicit failed replicas. Missing references use `needs_more_info` and no normalized results. The C2 program reports `dispersion_independently_tested=false` for this fitting task: independently fitting energy permits a later comparison but does not perform that comparison.

Assessment first runs a hidden synthetic calibration. C2 checks recovery of a known two-state ground energy, complete scan/replica accounting, real-data one-state comparison and fixed-energy interpretation. Normalization checks every paired complex replica, failure masks, original IDs, percentile summaries, existing real-component comparisons and explicit missing-reference behavior. It does not score fit choice or scientific prose by keyword matching. Physical suitability, original resampling correspondence and research conclusions require human review.

The grading process has no model connection or API credential. Its explicit Codex sandbox profile excludes references/original source paths and denies outside-workspace reads and writes, with read access for the selected interpreter/libraries. Network access remains enabled as requested. Review the exact generated source before using measured inputs; the qualified programs read their supplied JSON and write only standard output. Synthetic probes cover permitted workspace read/write, denied outside access and an allowed loopback connection. CPU/wall/output bounds apply. The discarded low-level `command/exec` approach did not pass boundary probes and is not retained as a fallback.

Each immutable assessment records the source Run status, Code artifact/program hash, validator hash/full runtime fingerprint, case manifest, actual input hashes, interpreter, results and limitations. Failed calibration is retained and prevents execution of measured inputs. The missing-reference case physically removes those records before execution rather than trusting a flag. The report binds the independent program to the assessed inputs; data-blind generation needs no free-text dataset marker in its goal. Assessment does not change Run state, write `accepted_results`, close a Run or fabricate a Human Response. Numerical pass is not physics acceptance. Current results and qualification status belong only in [Current state](REPO_CURRENT_STATE.md).
