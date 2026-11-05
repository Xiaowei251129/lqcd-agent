# LQCD Agent

An AI Research Partner for LQCD with controlled planning, code/analysis work, scientific review, autonomous conclusions, optional human participation and attributable results. Offline mode uses deterministic roles and a Fake coding backend. Explicit live mode uses the Python OpenAI Agents SDK for PI/Postdoc/Reviewer research and the independent Codex SDK backend for bounded coding proposals. Each installation starts with an empty local research library. Software checks do not establish physics readiness.

Scientific validation is shared by offline and model-assisted review: models interpret Host diagnostics and cannot erase numerical warnings. Planner and Reviewer receive validated remediation and the current project research state through retained context bundles; complete history and original evidence remain available through named reads. Credentials and live activation belong to application assembly. See the [architecture](docs/ARCHITECTURE.md) for research-role and execution boundaries.

## Use

```bash
source .venv/bin/activate
lqcd-agent --help
lqcd-agent doctor
lqcd-agent start --key example
lqcd-agent run --case-config configs/example.json --key science
lqcd-agent-workbench --port 8000
```

The operator workspace defaults to the current directory; set the absolute `LQCD_AGENT_WORKSPACE` to use another owned workspace. Case `raw_data_path` values resolve under its `raw_data/`; `.env` and optional `.venv`/`.runtime` belong to that workspace, independently of where the package is installed. Resume, replay and fork require the original workspace. Status and cancellation do not require credentials, and cancellation remains available if the data workspace is unavailable.

The workbench binds to `127.0.0.1`. CLI, workbench and scientific cases use the same canonical engine. The CLI returns the Host, Run and Pause identifiers needed for resume, cancel, fork and replay; see each subcommand's `--help`.

## Projects and a growing local library

Create Projects in the workbench or with `lqcd-agent project-create`. Each Run freezes its project version; plans, code, numerical results and questions accumulate as verified project evidence. `library/wiki`, `library/skills` and `library/methods` begin empty. They never import your private wiki. Research agents can propose and independently review scoped assets. Reviewed methods additionally require actual Host-executed independent calibration; operator review is optional and attributable.

In the workbench, open a Project and select a research task to follow its preparation and linked analyses. From **Results**, select a fit window or observable to inspect its evidence, attach a question or compare completed analyses. See the [workbench guide](docs/WORKBENCH.md).

Project research begins with PI/Postdoc preparation before the formal scientific Run. An executable configuration is optional: supply the question, constraints, a workspace-relative data path and scientific Python, or start with a question alone. The Host profiles only declared data and records missing inputs. The roles can read literature and local evidence, identify assumptions and produce a supported executable contract. A ready preparation automatically starts scientific work; concrete missing prerequisites remain visible questions without a mandatory human approval or an open execution lease.

```bash
lqcd-agent project-create --id c2-study --title "C2 study" \
  --goal "Compare window sensitivity and preserve all failed replicas" \
  --data-path raw_data/c2.json --source-kind measured_lattice_data --python /absolute/scientific/python3
lqcd-agent run --project c2-study --live --key prepare-c2
```

The data need a supported scientific contract and attributable metadata; see [research intake and clarification](docs/RESEARCH_CONTRACTS.md#research-intake-and-clarification). The workbench can edit the starting inputs and record a reply. **Continue research** consumes the original task's remaining quota and deadline; **Start a new investigation** explicitly starts a new task. Merely commenting never dispatches work. Offline preparation reports that live research is disabled and makes no claim to have used PI/Postdoc models.

Live planning contains PI → Postdoc; analysis uses the existing Host and optional Codex backend; review contains independent Reviewer → PI synthesis. Research can conclude without a Human Response. Outcomes are `supported`, `qualified` or `inconclusive`, with `decision_origin=system`. Optional operator contributions and actual authorization decisions retain their own attribution; a permission response is not a scientific endorsement. Warnings and unresolved questions remain evidence. Optional operator contributions enter later research attempts; only additional authorization uses the human gate. PI follow-up experiments create linked Runs under the same task quota. See [research contracts and commands](docs/RESEARCH_CONTRACTS.md) and the [workbench guide](docs/WORKBENCH.md).

## Application API and coding

Create a private `.env` from `.env.example`, set `OPENAI_API_KEY`, and run `chmod 600 .env`. The file is ignored by Git. Planner, reviewer and Codex use this application key; models default to `gpt-6-luna`. Nothing depends on your interactive Codex session or login.

```bash
lqcd-agent run --case-config configs/example.json --live --key live-science
lqcd-agent start --workflow code --live --key live-code
lqcd-agent status --host HOST --case case --run RUN
lqcd-agent resume --host HOST --case case --run RUN --pause PAUSE --key consume-code
```

The live scientific `run` entry starts the shared background Host driver when admitted work remains; no manual delivery polling/resume is required. It uses the original workspace and its private `.env`, and survives the requesting CLI/browser. Status remains read-only.

The separate `--workflow code` demonstration keeps its explicit delivery interface. Copy Host, Run and Pause identifiers from its JSON output. Poll `status` until `coding_backend.status` is `completed`, then resume within the 240-second coding window. Resume applies the bounded proposal, seals it, independently checks syntax and consumes it through the existing control path. Use `cancel` with the same identifiers to stop the original job. Status does not call a model or renew a lease. Backend failures are retained under the private Host's `coding_jobs` directory. Status opens the existing authority read-only, verifies its schema and Run heads, and returns a `next_action`; it does not assemble graph or Code executors. A concurrent head change produces an inspection error rather than a stale cached result.

The `code` workflow is a small integration example: change `sample.py` so `value()` returns integer 2. The Host checks its exact allowed AST before execution. Codex can use tools, edit its disposable task workspace, test programs and access the network permitted by the frozen task. SDK `deny_all` maps to native `never`: commands within the frozen profile run normally, while scope-escalation requests are rejected. Permitted command internet uses the native public-network proxy, which blocks local/private services and Unix sockets. The Host validates the final UTF-8 file proposal, scope, sealed tree and verification evidence. Missing scientific implementations retain an explicit incomplete/inconclusive outcome; the sample program is never substituted for scientific code. The [first research cases](docs/RESEARCH_CASES.md) use separate task profiles and independent local assessment of Codex-written C2/Normalization programs.

Scientific Code can call `run_numerical_trial` on its current `analysis.py` with bounded synthetic JSON. The Host uses the selected scientific Python and the same isolated numerical executor, returns actual failure/output feedback, and seals exact development evidence in the Code bundle. Trials share the original Code time/tool allowance; they do not expose the private production dataset or withheld calibration answers. The final sealed program still receives formal Analysis and independent review. Development trial success is not scientific acceptance.

Live requests transmit the supplied task and selected context to OpenAI and incur API usage. The current Terra configuration counts each complete explicit model input before generation and enforces a 256,000-token ceiling. Research compaction preserves the initial scientific state verbatim and retains original evidence; count failure or excess stops the request without silent truncation. Research compaction consumes the balanced eight-call attempt allowance. Research and native Codex model requests also consume the shared task quota described below. Per-request context limits are deployment choices, not universal model capabilities; provider-side project spending limits remain separate billing controls; see [context thresholds and boundaries](docs/ARCHITECTURE.md#research-roles-and-sdk-boundaries) and [security boundaries](docs/SECURITY_AND_DATA_POLICY.md).

Deployment limits have one entry in [`src/lqcd_agent/settings.py`](src/lqcd_agent/settings.py): 256,000 explicit input tokens, 32,768 research output tokens including reasoning, 128,000 Code output tokens, and one shared 194,560-token compaction threshold. The shared research-task quota permits four linked Runs, including preparation and clarification attempts, 128 model requests, 8,000,000 explicit input-plus-output reservation units and a 3,600-second dispatch deadline. Each actual generation/compact request, including native SDK recovery, uses that same Host account; unknown usage retains its maximum reservation. Waiting for an optional reply does not extend that deadline. This is not a USD billing ceiling or a measurement of provider-internal context/tool fees. Change the source policy and rebuild; `.env` selects models and credentials, not separate token overrides.

## Evidence lifecycle

Scientific Runs bind the content identity of their raw CSV/JSON input, including its absence, before execution. Replay and fork keep that identity; changed data require a new Run. Analysis manifests identify the bytes actually used. Model proposals contain scientific decisions; the Host constructs executable mappings and artifact identity. Research roles retain complete local context evidence and can retrieve named sections through Host-accounted tools. Project histories remain read-only and inspectable if temporary execution storage is lost; raw datasets are not automatically backed up. See [architecture](docs/ARCHITECTURE.md) and [verification](docs/VERIFICATION_GUIDE.md) for evidence reads and boundaries.

```bash
lqcd-agent archive --host HOST --case CASE --run RUN
lqcd-agent verify-archive --archive-path /absolute/path/to/ARCHIVE.zip
```

Archive accepts only a terminated Run with committed closure. It writes a content-addressed ZIP inside that Host's private `archives/`, retains the source, and repeats exactly for unchanged evidence. The bundle contains Run files, a validated control snapshot and hash-bound scientific domain members. It excludes SQLite/checkpoint database files, backend homes and worktrees, application credentials and raw data stored outside the Run. Its limit is 256 MiB and 10,000 evidence members; it is a portable evidence bundle, not a database backup or an executable/restorable Run. Copy it to durable storage before operator cleanup of temporary Hosts. Verification checks inventory and hashes without extraction; preserve its SHA-256 through a trusted channel for origin verification. It does not independently establish scientific acceptance.

Python clients use the same application entry, for example `execute(ApplicationRequest('status', host=..., case=..., run=...))` from `lqcd_agent.runtime`. Request objects carry business inputs, never actor scopes or write roots.

## Develop

Read the [current state](docs/REPO_CURRENT_STATE.md) and [verification guide](docs/VERIFICATION_GUIDE.md). For a fresh Python 3.12 environment, set `TMPDIR` to the approved execution parent, then install the single hash-locked environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps --no-build-isolation -e .
```

Runtime dependencies are declared in [pyproject.toml](pyproject.toml), alongside development tools and a separate build-tool group. Regenerate the existing lock with its pinned uv version:

```bash
uv pip compile pyproject.toml --extra dev --group build --python-version 3.12 --universal --generate-hashes --output-file requirements.lock
uv pip check
ruff check src tests scripts setup.py
```

The compiler retains compatible existing pins. Use `--upgrade-package NAME` only for an intentional dependency update. Universal dependency markers do not qualify additional runtime platforms.

```bash
python scripts/check.py                          # 12 critical checks
python scripts/check.py tests/test_analysis_programs.py
python scripts/check.py --integration            # current tests once + numerical benchmark
python scripts/measure_cli.py --samples 3         # fresh offline Runs; retains measured Hosts
python scripts/measure_context.py                # offline prompt sizes and small numerical timing
```

The runner selects this checkout's `.venv`; it never imports a previous checkout. After source edits it regenerates the build manifest once. Standalone CLI users must run `python scripts/build_manifest.py` after editing runtime source; wheel builds regenerate the installed manifest without changing sources. Local execution uses the fixed, validated macOS `/private/tmp` parent; caller environment variables cannot redirect it.

The qualified development interpreter is Python 3.12; platform qualification is recorded in the current state. Use the qualified native macOS local filesystem and SQLite runtime. `doctor` checks actual storage admission and WAL/FULL/foreign-key settings in its own temporary root, without loading a key or calling a model.

The coordinator uses schema 3 and rejects old Hosts; there is no in-place migration or rewriting of prior accepted results. Use the original supported runtime to inspect original execution authority. Current control declarations live in [contracts/control.json](contracts/control.json); regenerate with `python scripts/generate_protocol.py`. Only current Runs are supported; version-control history retains retired implementations.

[Current state](docs/REPO_CURRENT_STATE.md) · [Architecture](docs/ARCHITECTURE.md) · [Data and security](docs/SECURITY_AND_DATA_POLICY.md)
