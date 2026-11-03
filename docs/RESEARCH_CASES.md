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

## Canonical scientific workflow

Prepare private configurations for the normal scientific entry:

```bash
python -m lqcd_agent.research_cases prepare --python /path/to/trusted/python-with-numpy-and-scipy
python -m lqcd_agent run --case-config raw_data/research_cases/cases/c2-fit-comparison.json --live --key first-c2
```

Use `normalization-complex.json` for Normalization. The other configurations cover the fixed-energy constraint and missing-reference outcome. There are no separate research workflow profiles or fixed research-role agents. Explicit live use incurs API charges. The existing private `.env` selects the research Agents SDK model with `OPENAI_MODEL` and Codex with `LQCD_CODE_MODEL`.

The actual scientific Planner produces a validated implementation request. The existing CodeHost freezes its requirements, scope and budget, then Codex writes/tests the program with tools and native-proxied public networking inside the frozen profile, then returns changed paths rather than duplicating source in its final response. The worker reads the actual files into the existing proposal, and the Host independently validates and seals them. Measured arrays, individual bootstrap values, withheld references and the earlier analysis implementation stay outside programming prompts. A successful plan describes completed planning; coding and calculation can still be pending. A genuinely pending plan remains pending and cannot start Code.

SDK shell tools keep temporary files (including zsh here-documents) and Ruff caches in the task-owned temporary directory and suppress automatic Python bytecode. These fixed internal environment values control scratch locations, not authority. The native managed proxy blocks local/private and Unix services, and SDK `deny_all` rejects scope escalation while permitted tools remain automatic. The Host still scans the complete deliverable tree and rejects unexpected files, including hidden or binary cache files; it does not ignore or delete them to obtain a pass.

The live scientific entry starts the shared Host driver, which delivers completed Code through the original resume path without manual polling. Returned Host/Run/Pause identities remain available for read-only status and explicit control actions. Status does not launch work or renew the lease. Generated research coding requests a 900-second producer window and a 960-second worker lease, still clipped by the original Host deadline and remaining policy budget. Native work has a 400-second limit inside the roughly 450-second backend reservation, leaving room for delivery and sealing. The programming sandbox may use task-local test dependencies; independent private assessment and canonical Analysis use the selected scientific interpreter. Final delivery and sealing must also fit the original aggregate reservation. Background completion does not renew that reservation. An expired operation follows canonical cancellation/recovery; never extend or forge old authority. The normal `cancel` command restores the original Code stop adapter without loading API credentials, the data workspace or the scientific interpreter.

On delivery, the existing fresh Analysis preparation binds current Plan/Code, exact code tree, input snapshot, parameters, interpreter/library versions, disabled numeric-network policy and execution deadline. Analysis Engineer executes those sealed bytes through the same local sandbox primitive used by independent assessment, then publishes actual output through its existing Run-result/manifest path. Changed data, code or interpreter identity fail closed. The Host merges frozen parameters into the JSON passed as `argv[1]`; the source dataset does not need to be edited to add a case flag such as `fixed_ground_energy`. Parameters cannot replace source-data fields. No mock command or original analysis-package computation substitutes for execution.

Scientific Reviewer consumes the actual generated output. Host checks cover C2 fit/replica accounting and fixed-energy claims, plus paired complex normalization and percentile summaries. Generated output uses that contract directly; unrelated legacy-format diagnostic scans are not applicable. The initial model request contains aggregate diagnostics, provenance limits and prior findings, plus the method-step count and an instruction to read the complete method from its sealed context bundle. Named evidence tools can read registered analysis outputs, including replica-level results; they do not provide general access to raw input files or withheld answers. For the current Terra configuration, complete explicit input is counted before generation, with a 256,000-token hard ceiling and research compaction above 194,560. The initial scientific state remains verbatim and original evidence remains available; failed counting or excessive required context stops the request without silent truncation. Research compaction consumes the balanced eight-call attempt allowance, and generation allows up to 32,768 output tokens. See [context boundaries](ARCHITECTURE.md#research-roles-and-sdk-boundaries) for Code compaction and the distinction between per-request limits and cumulative cost. Incomplete model responses stay failed, with no automatic retry or partial-result publication. Provider interpretation cannot remove Host warnings or raise the confidence ceiling. The Run can conclude with a supported, qualified or inconclusive system outcome; it never fabricates a Human Response. Only requests for additional authority require the original scoped authorization response. Missing-input and failed execution outcomes retain diagnostics and can conclude inconclusively; extra execution authority remains separately scoped.

## Independent assessment

Assessment remains a separate consumer with no Run-advancement authority:

```bash
python -m lqcd_agent.research_evaluation \
  --host HOST --case CASE --run RUN --family c2 \
  --python /path/to/trusted/python-with-numpy-and-scipy
```

Use `--family normalization` for the other program. Both workflows share one numerical contract implementation and one sandbox execution primitive. The independent assessor additionally uses hidden calibration and withheld comparisons; these are not supplied to the production Planner, programmer or Reviewer. Independent assessment never repairs or advances a failed source Run.

Successful numerical output uses `status=ok`; C2 may report `partial` with explicit failed replicas. Normalization result and summary rows use the literal string tags `mode2` and `mode3`; numeric tags are rejected without coercion. Missing references use `needs_more_info` without invented normalized results. Fitting energy at one momentum does not by itself perform a dispersion comparison. Original resampling correspondence and physical fit/model suitability remain scoped scientific judgments; system conclusions must preserve their limitations and actual review provenance.

The selected scientific interpreter is separate from the core dependency lock. Its Python/NumPy/SciPy identity and runtime roots are recorded and checked against the frozen preparation. It must already contain required numerical packages. This local process has no API credential or model connection; numeric network access is disabled. Review exact generated source before measured-input qualification. Workspace read/write, outside access denial, blocked local HTTP/Unix services and SDK escalation rejection have synthetic boundary checks. CPU/wall/output bounds apply.

New input-pack manifests record `scientific_acceptance=not_system_reviewed`. Each immutable assessment records `assessment_kind=independent_check_only` and `scientific_acceptance=not_system_reviewed`, and binds source Run/Code, exact program/input, case manifest and validator version. Failed calibration prevents measured-input execution. The missing-reference assessment physically removes those records. Reports do not write accepted results, close a Run or fabricate a Human Response. These checks cannot grant system acceptance or establish physical validity, even when every numerical check passes. Qualification results belong in [Current state](REPO_CURRENT_STATE.md).
