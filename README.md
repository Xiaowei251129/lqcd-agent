# LQCD Agent

An AI Research Partner for LQCD with controlled planning, code/analysis work, scientific review, human decisions and attributable results. Offline mode uses deterministic roles and a Fake coding backend. Explicit live mode uses OpenAI Responses for planning/review and an independent Codex SDK backend for bounded coding proposals. Software checks do not establish physics readiness.

Scientific validation is shared by offline and model-assisted review: models interpret Host diagnostics and cannot erase numerical warnings. Planner and Reviewer receive validated remediation and relevant history through their retained context bundles. Provider credentials and live activation belong to application assembly; scientific roles accept constructed providers. See the [architecture maintenance record](docs/maintenance/ARCHITECTURE_SIMPLIFICATION.md).

## Use

```bash
source .venv/bin/activate
lqcd-agent --help
lqcd-agent doctor
lqcd-agent start --key example
lqcd-agent run --case-config configs/example.json --key science
lqcd-agent-demo --port 8000
```

The operator workspace defaults to the current directory; set the absolute `LQCD_AGENT_WORKSPACE` to use another owned workspace. Case `raw_data_path` values resolve under its `raw_data/`; `.env` and optional `.venv`/`.runtime` belong to that workspace, independently of where the package is installed. Resume, replay and fork require the original workspace. Status and cancellation do not require credentials, and cancellation remains available if the data workspace is unavailable.

The demo binds to `127.0.0.1`. CLI, demo and scientific cases use the same canonical engine. The CLI returns the Host, Run and Pause identifiers needed for resume, cancel, fork and replay; see each subcommand's `--help`.

## Application API and coding

Create a private `.env` from `.env.example`, set `OPENAI_API_KEY`, and run `chmod 600 .env`. The file is ignored by Git. Planner, reviewer and Codex use this application key; models default to `gpt-6-luna`. Nothing depends on your interactive Codex session or login.

```bash
lqcd-agent run --case-config configs/example.json --live --key live-science
lqcd-agent start --workflow code --live --key live-code
lqcd-agent status --host HOST --case case --run RUN
lqcd-agent resume --host HOST --case case --run RUN --pause PAUSE --key consume-code
```

Copy Host, Run and Pause identifiers from the JSON output. Poll `status` until `coding_backend.status` is `completed`, then resume within the 240-second coding window. Resume applies the bounded proposal, seals it, independently checks syntax and consumes it through the existing control path. Use `cancel` with the same identifiers to stop the original job. Status does not call a model or renew a lease. Backend failures are retained under the private Host's `coding_jobs` directory. Status opens the existing authority read-only, verifies its schema and Run heads, and returns a `next_action`; it does not assemble graph or Code executors. A concurrent head change produces an inspection error rather than a stale cached result.

The current coding workflow is a small integration example: change `sample.py` so `value()` returns integer 2. The Host checks its exact allowed AST before execution. Codex proposes UTF-8 files; it cannot run commands or directly edit the workspace. The current runtime is qualified for local macOS process identity and termination. It does not enable arbitrary generated-program execution. Scientific case planning that requires a new analysis implementation still pauses for a scoped implementation decision; a sample program is never substituted for scientific code.

Live requests transmit the supplied task and selected context to OpenAI and incur API usage. Codex's private job records contain turn IDs and reported token usage; control `llm_calls` counts logical invocations, not transport retries. SDK jobs have a time limit, not a guaranteed dollar/token cap. Use project spending limits for billing control. See [security boundaries](docs/SECURITY_AND_DATA_POLICY.md).

## Evidence lifecycle

Scientific Runs bind the content identity of their raw CSV input, including its absence, before execution. Replay and fork keep that identity; changed data require a new Run. Analysis manifests identify the bytes actually used. Model proposals contain scientific decisions; the Host constructs executable mappings and artifact identity. Provider-backed roles retain complete local context evidence and send bounded role views with verifiable references. See [architecture](docs/ARCHITECTURE.md) and [verification](docs/VERIFICATION_GUIDE.md) for evidence reads and boundaries.

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

Current control declarations live in [contracts/control.json](contracts/control.json); regenerate with `python scripts/generate_protocol.py`. Only current Runs are supported. Old runtime paths, historical acceptance, ticket archives and old demo/benchmark implementations have been removed.

[Current state](docs/REPO_CURRENT_STATE.md) · [Architecture](docs/ARCHITECTURE.md) · [Data and security](docs/SECURITY_AND_DATA_POLICY.md)
